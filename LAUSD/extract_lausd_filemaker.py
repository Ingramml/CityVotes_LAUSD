#!/usr/bin/env python3
"""
Extract LAUSD resolutions from FileMaker WebDirect for any quarter.

Usage:
    python3 extract_lausd_filemaker.py 2021 1    # Q1 2021
    python3 extract_lausd_filemaker.py 2023 3    # Q3 2023

Output: LAUSD-Q{quarter}-{year}-Resolutions-Raw.json in the script directory.

Based on field mapping discovered during Q1 2020 extraction (2026-02-12).
FileMaker WebDirect uses Vaadin 8.18.0 with a glass pane overlay that
blocks standard clicks — requires coordinate-based mouse clicks for buttons
and JavaScript dispatchEvent for field activation.
"""

import asyncio
import json
import os
import sys
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
FM_URL = "https://dnnlt3f.pcifmhosting.com/fmi/webd/RESOLUTIONS"

# Detail view field mapping (stable across sessions)
FIELDS = {
    'title': 'fm_object_4',
    'language': 'fm_object_8',
    'action_date': 'fm_object_28',
    'notice_date': 'fm_object_30',
    'sponsor': 'fm_object_33',
    'cosponsor_name': 'fm_object_42',
    'moved_by': 'fm_object_45',
    'second': 'fm_object_47',
    'action': 'fm_object_49',
    'vote_name': 'fm_object_51',
    'vote_value': 'fm_object_53',
    'student_name': 'fm_object_76',
    'student_vote': 'fm_object_77',
    'position': 'fm_object_79',
}

BUTTONS = {
    'next': 'fm_object_85',
    'list': 'fm_object_87',
}

QUARTER_DATES = {
    1: ("1/1/{year}", "3/31/{year}"),
    2: ("4/1/{year}", "6/30/{year}"),
    3: ("7/1/{year}", "9/30/{year}"),
    4: ("10/1/{year}", "12/31/{year}"),
}


async def get_center(page, css_selector):
    """Get center coordinates of a DOM element."""
    return await page.evaluate(f"""() => {{
        const el = document.querySelector('{css_selector}');
        if (!el) return null;
        const r = el.getBoundingClientRect();
        return {{ x: r.x + r.width / 2, y: r.y + r.height / 2 }};
    }}""")


async def activate_field(page, fm_class):
    """Activate a FileMaker field by dispatching mouse events past the glass pane."""
    await page.evaluate(f"""() => {{
        const el = document.querySelector('.{fm_class} .text');
        if (!el) return false;
        ['mousedown', 'mouseup', 'click'].forEach(t => {{
            el.dispatchEvent(new MouseEvent(t, {{bubbles: true, cancelable: true}}));
        }});
        return true;
    }}""")
    await asyncio.sleep(0.5)


async def click_button(page, fm_class, wait=1.5):
    """Click a FileMaker button using coordinates (bypasses glass pane)."""
    center = await get_center(page, f'.{fm_class}')
    if not center:
        raise RuntimeError(f"Button .{fm_class} not found on page")
    await page.mouse.click(center['x'], center['y'])
    await asyncio.sleep(wait)


async def read_field(page, fm_class):
    """Read text content of a FileMaker field."""
    return await page.evaluate(f"""() => {{
        const el = document.querySelector('.{fm_class} .text');
        return el ? el.textContent.trim() : '';
    }}""")


async def read_portal_pairs(page, name_class, value_class):
    """Read name/value pairs from a FileMaker portal."""
    return await page.evaluate(f"""() => {{
        const names = document.querySelectorAll('.{name_class} .text');
        const values = document.querySelectorAll('.{value_class} .text');
        const out = [];
        for (let i = 0; i < names.length; i++) {{
            const n = names[i] ? names[i].textContent.trim() : '';
            const v = values[i] ? values[i].textContent.trim() : '';
            if (n) out.push({{ name: n, vote: v }});
        }}
        return out;
    }}""")


async def read_portal_single(page, fm_class):
    """Read a single-column portal."""
    return await page.evaluate(f"""() => {{
        const els = document.querySelectorAll('.{fm_class} .text');
        return Array.from(els).map(e => e.textContent.trim()).filter(Boolean);
    }}""")


async def wait_for_vaadin(page, timeout=30):
    """Wait for Vaadin to finish server communication."""
    for _ in range(timeout * 2):
        busy = await page.evaluate("""() => {
            const apps = window.vaadin && window.vaadin.clients;
            if (!apps) return false;
            return Object.values(apps).some(c => c.isActive && c.isActive());
        }""")
        if not busy:
            return
        await asyncio.sleep(0.5)


async def find_search_button(page):
    """Find the Search button (fm_object_67 on the search form)."""
    return await get_center(page, '.fm_object_67')


async def dump_visible_objects(page):
    """Debug helper: dump all visible fm_object elements."""
    return await page.evaluate("""() => {
        const els = document.querySelectorAll('[class*="fm_object_"]');
        const result = [];
        for (const el of els) {
            const cls = Array.from(el.classList).find(c => c.startsWith('fm_object_'));
            const r = el.getBoundingClientRect();
            if (r.width > 0 && r.height > 0) {
                result.push({
                    cls,
                    text: el.textContent.trim().substring(0, 60),
                    y: Math.round(r.y),
                    w: Math.round(r.width),
                    h: Math.round(r.height)
                });
            }
        }
        return result;
    }""")


async def extract_current_record(page):
    """Extract all fields from the currently displayed record."""
    record = {
        'title': await read_field(page, FIELDS['title']),
        'language': await read_field(page, FIELDS['language']),
        'action_date': await read_field(page, FIELDS['action_date']),
        'notice_date': await read_field(page, FIELDS['notice_date']),
        'sponsor': await read_field(page, FIELDS['sponsor']),
        'moved_by': await read_field(page, FIELDS['moved_by']),
        'second': await read_field(page, FIELDS['second']),
        'action': await read_field(page, FIELDS['action']),
        'cosponsors': await read_portal_single(page, FIELDS['cosponsor_name']),
        'votes': await read_portal_pairs(page, FIELDS['vote_name'], FIELDS['vote_value']),
        'student_votes': await read_portal_pairs(page, FIELDS['student_name'], FIELDS['student_vote']),
        'resolution_number': 'UNKNOWN',
    }
    return record


async def extract_quarter(year, quarter):
    """Main extraction routine for a given year and quarter."""
    from playwright.async_api import async_playwright

    start = QUARTER_DATES[quarter][0].format(year=year)
    end = QUARTER_DATES[quarter][1].format(year=year)
    date_range = f"{start}...{end}"
    label = f"{year} Q{quarter}"

    print(f"[{label}] Starting extraction: {date_range}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={'width': 1280, 'height': 900})
        page = await context.new_page()

        # 1. Navigate to FileMaker WebDirect
        print(f"[{label}] Loading FileMaker...")
        try:
            await page.goto(FM_URL, timeout=90000, wait_until='networkidle')
        except Exception:
            await page.goto(FM_URL, timeout=90000, wait_until='load')
        await asyncio.sleep(5)

        # Check if Vaadin app loaded
        vaadin_check = await page.evaluate("() => !!document.querySelector('.v-app')")
        if not vaadin_check:
            print(f"[{label}] Waiting for Vaadin to initialize...")
            await asyncio.sleep(10)
            vaadin_check = await page.evaluate("() => !!document.querySelector('.v-app')")
            if not vaadin_check:
                print(f"[{label}] ERROR: Vaadin never loaded")
                await browser.close()
                return []

        # Debug: show what's on the page
        objects = await dump_visible_objects(page)
        print(f"[{label}] Page loaded with {len(objects)} FM objects")

        # Verify we're on the search form (should have fm_object_67 = Search button)
        search_pos = await find_search_button(page)
        if not search_pos:
            print(f"[{label}] ERROR: Not on search form (fm_object_67 not found)")
            for obj in objects[:10]:
                print(f"  {obj['cls']}: {obj['text']}")
            await browser.close()
            return []

        # 2. Enter search criteria in Action Date field
        # On the search form, fm_object_53 is the Action Date field
        print(f"[{label}] Entering search criteria: {date_range}")
        field_exists = await page.evaluate("() => !!document.querySelector('.fm_object_53 .text')")
        if not field_exists:
            print(f"[{label}] ERROR: Action Date field (fm_object_53) not found")
            await browser.close()
            return []

        await activate_field(page, 'fm_object_53')
        await page.keyboard.type(date_range, delay=30)
        await asyncio.sleep(0.5)

        # 3. Click Search button
        print(f"[{label}] Clicking Search at ({search_pos['x']:.0f}, {search_pos['y']:.0f})")
        await page.mouse.click(search_pos['x'], search_pos['y'])
        print(f"[{label}] Search submitted, waiting for results...")
        await asyncio.sleep(4)
        await wait_for_vaadin(page)

        # 4. Detect which layout we landed on
        post_objects = await dump_visible_objects(page)
        print(f"[{label}] After search: {len(post_objects)} FM objects on page")

        # Check for "No records match" error
        error_text = await page.evaluate("""() => {
            const els = document.querySelectorAll('div');
            for (const el of els) {
                const t = el.textContent || '';
                if (t.includes('No records match') || t.includes('no records')) return t.trim().substring(0, 200);
            }
            return '';
        }""")
        if error_text:
            print(f"[{label}] No records found for this quarter")
            await browser.close()
            return []

        # Search results land on LIST VIEW
        # List view fields: fm_object_22=date, fm_object_23=title, fm_object_53=resolution#
        # fm_object_62 = "Show Details" button to switch to detail view

        # 5. Scrape resolution numbers from list view first
        list_data = await page.evaluate("""() => {
            const dates = document.querySelectorAll('.fm_object_22 .text');
            const titles = document.querySelectorAll('.fm_object_23 .text');
            const resNums = document.querySelectorAll('.fm_object_53 .text');
            const rows = [];
            const count = Math.max(dates.length, titles.length, resNums.length);
            for (let i = 0; i < count; i++) {
                const d = dates[i] ? dates[i].textContent.trim() : '';
                const t = titles[i] ? titles[i].textContent.trim() : '';
                const r = resNums[i] ? resNums[i].textContent.trim() : '';
                if (d || t || r) rows.push({ date: d, title: t, res_num: r });
            }
            return rows;
        }""")

        total = len(list_data)
        print(f"[{label}] Found {total} resolutions in list view")
        if total == 0:
            await browser.close()
            return []

        for item in list_data:
            print(f"[{label}]   {item['date']} | {item['res_num']} | {item['title'][:50]}")

        # 6. Click "Show Details" to switch to detail view
        show_details = await get_center(page, '.fm_object_62')
        if not show_details:
            print(f"[{label}] ERROR: 'Show Details' button (fm_object_62) not found")
            await browser.close()
            return []

        print(f"[{label}] Clicking 'Show Details'...")
        await page.mouse.click(show_details['x'], show_details['y'])
        await asyncio.sleep(3)
        await wait_for_vaadin(page)

        # 7. Verify we're now in detail view (should have position counter)
        counter = await read_field(page, FIELDS['position'])
        print(f"[{label}] Detail view position: '{counter}'")

        if not counter or 'of' not in counter.lower():
            # Debug: dump what we see
            detail_objects = await dump_visible_objects(page)
            print(f"[{label}] WARNING: Not in expected detail view. Objects:")
            for obj in detail_objects[:15]:
                print(f"  {obj['cls']}: '{obj['text'][:50]}'")
            await browser.close()
            return []

        parts = counter.lower().split('of')
        # "1 of 8 Resolutions" -> extract the number after "of"
        after_of = parts[1].strip()
        detail_total = int(''.join(c for c in after_of.split()[0] if c.isdigit()))
        print(f"[{label}] Detail view shows {detail_total} records")

        # 8. Extract each record from detail view
        records = []
        for i in range(detail_total):
            record = await extract_current_record(page)

            # Match resolution number from list data
            if i < len(list_data) and list_data[i]['res_num']:
                record['resolution_number'] = list_data[i]['res_num']

            records.append(record)

            title_preview = record['title'][:55] + '...' if len(record['title']) > 55 else record['title']
            print(f"[{label}]   [{i+1}/{detail_total}] {record['resolution_number']} - {title_preview}")

            # Navigate to next record
            if i < detail_total - 1:
                await click_button(page, BUTTONS['next'], wait=2)
                await wait_for_vaadin(page)

        # Check for still-unknown resolution numbers
        unknowns = [r for r in records if r['resolution_number'] == 'UNKNOWN']
        if unknowns:
            print(f"[{label}] WARNING: {len(unknowns)} records still have UNKNOWN resolution numbers")

        await browser.close()
        print(f"[{label}] Extraction complete: {len(records)} records")
        return records


def save_results(year, quarter, records):
    """Save extracted records to JSON file."""
    output = os.path.join(SCRIPT_DIR, f"LAUSD-Q{quarter}-{year}-Resolutions-Raw.json")
    with open(output, 'w') as f:
        json.dump(records, f, indent=2)
    print(f"Saved {len(records)} records to {os.path.basename(output)}")
    return output


async def main():
    if len(sys.argv) < 3:
        print("Usage: python3 extract_lausd_filemaker.py <year> <quarter>")
        print("  year: 2021-2024")
        print("  quarter: 1-4")
        sys.exit(1)

    year = int(sys.argv[1])
    quarter = int(sys.argv[2])

    if quarter not in (1, 2, 3, 4):
        print(f"Invalid quarter: {quarter}. Must be 1-4.")
        sys.exit(1)

    records = await extract_quarter(year, quarter)
    if records:
        save_results(year, quarter, records)
        print(f"\nDone! {len(records)} resolutions extracted for {year} Q{quarter}")
    else:
        print(f"\nNo resolutions found for {year} Q{quarter}")
        # Create empty JSON to signal completion
        save_results(year, quarter, [])


if __name__ == '__main__':
    asyncio.run(main())
