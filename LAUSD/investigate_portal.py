#!/usr/bin/env python3
"""
LAUSD Legistar Web Portal Investigation
========================================
Uses Playwright (headless Chromium) to scrape the LAUSD Legistar portal
and identify data visible on the web that may NOT be captured via the API.
"""

import json
import re
import time
from datetime import datetime
from playwright.sync_api import sync_playwright, TimeoutError as PwTimeout

MEETING_URL = (
    "https://lausd.legistar.com/MeetingDetail.aspx?"
    "LEGID=2090&GID=216&G=33058515-3F29-4AE6-8A8E-1738CD521295"
)
BODY_URL = "https://lausd.legistar.com/MainBody.aspx"


def section(title):
    width = 90
    print(f"\n{'=' * width}")
    print(f"  {title}")
    print(f"{'=' * width}")


def subsection(title):
    bar = "-" * max(0, 70 - len(title))
    print(f"\n--- {title} {bar}")


# --------------------------------------------------------------------------- #
#  1. MEETING DETAIL PAGE
# --------------------------------------------------------------------------- #
def investigate_meeting_page(page):
    section("1. MEETING DETAIL PAGE")
    print(f"URL: {MEETING_URL}")

    page.goto(MEETING_URL, wait_until="networkidle", timeout=60000)
    page.wait_for_timeout(3000)

    # ---- Meeting header metadata ----
    subsection("Meeting Header / Metadata")
    header_selectors = [
        "#ContentPlaceHolder1_lblDate",
        "#ContentPlaceHolder1_lblTime",
        "#ContentPlaceHolder1_lblLocation",
        "#ContentPlaceHolder1_hypAgenda",
        "#ContentPlaceHolder1_hypMinutes",
        "#ContentPlaceHolder1_hypVideo",
    ]
    for sel in header_selectors:
        el = page.query_selector(sel)
        if el:
            text = el.inner_text().strip()
            href = el.get_attribute("href") or ""
            label = sel.split("_")[-1]
            print(f"  {label}: {text}  {'[link: ' + href + ']' if href else ''}")
        else:
            print(f"  {sel.split('_')[-1]}: (not found)")

    # Try broader metadata area
    meta_area = page.query_selector("#ContentPlaceHolder1_pnlHeading")
    if meta_area:
        all_text = meta_area.inner_text().strip()
        print(f"\n  Full header area text:\n    {all_text[:500]}")

    detail_table = page.query_selector("table.rgMasterTable") or page.query_selector("#ContentPlaceHolder1_tblHeading")
    if detail_table:
        print(f"\n  Detail table found, text: {detail_table.inner_text()[:400]}")

    # ---- Agenda PDF / Minutes PDF / Video links ----
    subsection("Document & Media Links")
    all_links = page.query_selector_all("a")
    doc_links = []
    for a in all_links:
        href = a.get_attribute("href") or ""
        text = a.inner_text().strip()
        if any(kw in href.lower() + text.lower() for kw in [
            "agenda", "minutes", "video", "media", "youtube", ".pdf",
            "granicus", "viewreport", "attachment"
        ]):
            doc_links.append((text[:80], href[:200]))
    for text, href in doc_links:
        print(f"  [{text}]  ->  {href}")
    if not doc_links:
        print("  (No document/media links found)")

    # ---- Agenda Items Table ----
    subsection("Agenda Items Table Structure")

    table = page.query_selector("#ContentPlaceHolder1_gridMain_ctl00")
    if not table:
        table = page.query_selector("table.rgMasterTable")
    if not table:
        table = page.query_selector("#ContentPlaceHolder1_gridMain")

    if table:
        headers = table.query_selector_all("th")
        header_texts = [h.inner_text().strip() for h in headers if h.inner_text().strip()]
        print(f"  Column headers ({len(header_texts)}):")
        for i, h in enumerate(header_texts):
            print(f"    [{i}] {h}")

        rows = table.query_selector_all("tr.rgRow, tr.rgAltRow")
        print(f"\n  Data rows found: {len(rows)}")
        for idx, row in enumerate(rows[:3]):
            cells = row.query_selector_all("td")
            print(f"\n  --- Row {idx} ({len(cells)} cells) ---")
            for ci, cell in enumerate(cells):
                text = cell.inner_text().strip()[:120]
                links_in_cell = cell.query_selector_all("a")
                link_info = ""
                if links_in_cell:
                    hrefs = [l.get_attribute("href") or "" for l in links_in_cell]
                    link_info = f"  [links: {', '.join(h[:80] for h in hrefs if h)}]"
                col_name = header_texts[ci] if ci < len(header_texts) else f"col_{ci}"
                if text or link_info:
                    print(f"    {col_name}: {text}{link_info}")
    else:
        print("  (Main agenda table not found with known selectors)")
        tables = page.query_selector_all("table")
        print(f"  Total <table> elements on page: {len(tables)}")
        for i, t in enumerate(tables[:10]):
            tid = t.get_attribute("id") or "(no id)"
            print(f"    table[{i}] id={tid}")

    # ---- Check for iframes ----
    subsection("Iframes on Page")
    iframes = page.query_selector_all("iframe")
    for i, iframe in enumerate(iframes):
        src = iframe.get_attribute("src") or "(no src)"
        print(f"  iframe[{i}]: {src[:200]}")
    if not iframes:
        print("  (No iframes found)")

    # ---- Collect legislation detail URLs ----
    subsection("Legislation Links from Meeting Page")
    leg_links = []
    all_anchors = page.query_selector_all("a[href*='LegislationDetail']")
    for a in all_anchors:
        href = a.get_attribute("href") or ""
        text = a.inner_text().strip()
        if href and "LegislationDetail" in href:
            full_url = href if href.startswith("http") else "https://lausd.legistar.com/" + href.lstrip("/")
            leg_links.append((text[:80], full_url))
    print(f"  Found {len(leg_links)} legislation detail links")
    for text, url in leg_links[:5]:
        print(f"    [{text}] -> {url}")

    return leg_links


# --------------------------------------------------------------------------- #
#  2. LEGISLATION DETAIL PAGE
# --------------------------------------------------------------------------- #
def investigate_legislation_page(page, leg_links):
    section("2. LEGISLATION DETAIL PAGE")

    if not leg_links:
        print("  No legislation links found from meeting page.")
        return {}

    _, leg_url = leg_links[0]
    print(f"  Navigating to: {leg_url}")
    page.goto(leg_url, wait_until="networkidle", timeout=60000)
    page.wait_for_timeout(3000)

    # ---- Legislation header info ----
    subsection("Legislation Header Fields")
    field_selectors = {
        "File#": "#ContentPlaceHolder1_lblFile2",
        "Type": "#ContentPlaceHolder1_lblType2",
        "Status": "#ContentPlaceHolder1_lblStatus2",
        "File_Created": "#ContentPlaceHolder1_lblIntroduced2",
        "On_Agenda": "#ContentPlaceHolder1_lblOnAgenda2",
        "Enactment#": "#ContentPlaceHolder1_lblEnactmentNumber2",
        "Enactment_Date": "#ContentPlaceHolder1_lblEnactmentDate2",
        "Title": "#ContentPlaceHolder1_lblTitle2",
        "Name": "#ContentPlaceHolder1_lblName2",
        "Sponsors": "#ContentPlaceHolder1_lblSponsors2",
        "Version": "#ContentPlaceHolder1_lblVersion2",
        "InControl": "#ContentPlaceHolder1_hypInControlValue",
        "Requester": "#ContentPlaceHolder1_lblRequester2",
        "Cost": "#ContentPlaceHolder1_lblCost2",
    }
    found_fields = {}
    for label, sel in field_selectors.items():
        el = page.query_selector(sel)
        if el:
            text = el.inner_text().strip()
            href = el.get_attribute("href") or ""
            if text:
                found_fields[label] = text
                print(f"  {label}: {text}  {'[' + href + ']' if href else ''}")

    # Also look for any label/value pairs we missed
    all_labels = page.query_selector_all("span[id*='lbl'], td.rgHeader, span.fieldLabel")
    extra_labels = set()
    for lbl in all_labels:
        lid = lbl.get_attribute("id") or ""
        text = lbl.inner_text().strip()
        if text and lid and "ContentPlaceHolder1" in lid:
            short = lid.split("_")[-1]
            if short not in [s.split("_")[-1] for s in field_selectors.values()]:
                extra_labels.add((short, text[:100]))
    if extra_labels:
        print(f"\n  Additional label elements found:")
        for short, text in sorted(extra_labels):
            print(f"    {short}: {text}")

    # ---- Detect tabs ----
    subsection("Tabs on Legislation Page")
    tab_names = []

    # Try Telerik RadTabStrip detection via JS
    telerik_tabs = page.evaluate("""
        () => {
            const results = [];
            const strips = document.querySelectorAll('[class*="RadTabStrip"], [class*="rts"]');
            strips.forEach(s => {
                results.push({tag: s.tagName, id: s.id || '', cls: s.className || '', text: s.innerText.substring(0, 200)});
            });
            const candidates = document.querySelectorAll('a[id*="Tab"], span[id*="Tab"], div[id*="Tab"]');
            candidates.forEach(c => {
                results.push({tag: c.tagName, id: c.id || '', cls: c.className || '', text: c.innerText.substring(0, 100)});
            });
            return results;
        }
    """)
    for item in telerik_tabs:
        text = item.get("text", "").strip()
        if text:
            for t in text.split("\n"):
                t = t.strip()
                if t and len(t) < 30 and t not in tab_names:
                    tab_names.append(t)
            print(f"    Found: tag={item['tag']} id={item['id'][:60]} text={text[:100]}")

    if not tab_names:
        # Broader search
        tabs = page.query_selector_all("a.rtsLink, span.rtsLink, li.rtsLI a")
        for t in tabs:
            text = t.inner_text().strip()
            if text and len(text) < 30:
                tab_names.append(text)
    
    print(f"\n  Detected tabs: {tab_names}")

    # ---- Click each tab and examine content ----
    for tab_name in tab_names:
        subsection(f"Tab: '{tab_name}'")
        try:
            tab_el = page.get_by_text(tab_name, exact=True).first
            if tab_el:
                tab_el.click()
                page.wait_for_timeout(2000)

                # Get visible panels
                visible_content = page.evaluate("""
                    () => {
                        const panels = document.querySelectorAll(
                            'div[class*="PageView"], div[id*="pnl"], div[id*="Panel"], div[id*="pageContent"]'
                        );
                        const results = [];
                        panels.forEach(p => {
                            const style = window.getComputedStyle(p);
                            if (style.display !== 'none' && style.visibility !== 'hidden') {
                                const text = p.innerText.trim();
                                if (text.length > 5) {
                                    results.push({id: p.id || '', text: text.substring(0, 800)});
                                }
                            }
                        });
                        return results;
                    }
                """)
                for panel in visible_content:
                    pid = panel.get("id", "(no id)")
                    text = panel.get("text", "")
                    if text:
                        print(f"    Panel {pid[:60]}:")
                        for line in text.split("\n")[:15]:
                            line = line.strip()
                            if line:
                                print(f"      {line[:120]}")
                        total_lines = text.count("\n")
                        if total_lines > 15:
                            print(f"      ... ({total_lines} total lines)")
        except Exception as e:
            print(f"    Error clicking tab '{tab_name}': {e}")

    # ---- Specifically investigate the HISTORY section ----
    subsection("Legislative History Table (focused)")
    # Try clicking History tab first
    try:
        hist_tab = page.get_by_text("History", exact=True).first
        if hist_tab:
            hist_tab.click()
            page.wait_for_timeout(2000)
    except:
        pass

    history_table = page.query_selector("#ContentPlaceHolder1_gridLegislation_ctl00")
    if not history_table:
        history_table = page.query_selector("table[id*='gridLegislation']")
    if not history_table:
        # Find any visible rgMasterTable
        tables = page.query_selector_all("table.rgMasterTable")
        for t in tables:
            style = t.evaluate("el => window.getComputedStyle(el).display")
            if style != "none":
                history_table = t
                break

    if history_table:
        headers = history_table.query_selector_all("th")
        header_texts = [h.inner_text().strip() for h in headers if h.inner_text().strip()]
        print(f"  History table columns: {header_texts}")

        rows = history_table.query_selector_all("tr.rgRow, tr.rgAltRow")
        print(f"  History rows: {len(rows)}")
        for idx, row in enumerate(rows[:5]):
            cells = row.query_selector_all("td")
            row_data = {}
            for ci, cell in enumerate(cells):
                col = header_texts[ci] if ci < len(header_texts) else f"col_{ci}"
                text = cell.inner_text().strip()
                links = cell.query_selector_all("a")
                hrefs = [l.get_attribute("href") or "" for l in links]
                if text or hrefs:
                    row_data[col] = text + (" [links: " + ", ".join(h[:60] for h in hrefs if h) + "]" if any(hrefs) else "")
            print(f"    Row {idx}: {json.dumps(row_data, indent=6)}")
    else:
        print("  (History table not found)")

    # ---- Check for ATTACHMENTS ----
    subsection("Attachments")
    try:
        att_tab = page.get_by_text("Attachments", exact=True).first
        if att_tab:
            att_tab.click()
            page.wait_for_timeout(2000)
    except:
        pass

    attachment_links = page.query_selector_all("a[href*='ViewReport'], a[href*='View.ashx'], a[href*='attachment']")
    if not attachment_links:
        attachment_links = page.query_selector_all("#ContentPlaceHolder1_gridAttachments a, a[href*='.pdf']")

    for a in attachment_links:
        text = a.inner_text().strip()
        href = a.get_attribute("href") or ""
        if text or href:
            print(f"  Attachment: [{text[:80]}] -> {href[:150]}")
    if not attachment_links:
        print("  (No attachment links found)")

    # ---- Check for LEGISLATION TEXT ----
    subsection("Legislation Text / Body")
    try:
        text_tab = page.get_by_text("Text", exact=True).first
        if text_tab:
            text_tab.click()
            page.wait_for_timeout(2000)
    except:
        pass

    text_area = page.query_selector("#ContentPlaceHolder1_divText, #ContentPlaceHolder1_lblFullText, [id*='FullText']")
    if text_area:
        full_text = text_area.inner_text().strip()
        print(f"  Text content ({len(full_text)} chars):")
        print(f"    {full_text[:500]}")
    else:
        print("  (No legislation text area found)")

    # ---- Full page audit ----
    subsection("Full Page Audit - All Visible Labels/Fields")
    all_data = page.evaluate("""
        () => {
            const results = [];
            const spans = document.querySelectorAll('span[id*="lbl"]');
            spans.forEach(s => {
                const text = s.innerText.trim();
                if (text && text.length > 0 && text.length < 300) {
                    results.push({id: s.id, text: text, tag: 'span'});
                }
            });
            return results;
        }
    """)
    seen = set()
    for item in all_data:
        key = item.get("id", "") + item.get("text", "")
        if key not in seen:
            seen.add(key)
            print(f"    id={item.get('id', '')[:60]}  text={item.get('text', '')[:100]}")

    return found_fields


# --------------------------------------------------------------------------- #
#  3. BOARD MEMBER PAGES
# --------------------------------------------------------------------------- #
def investigate_board_members(page):
    section("3. BOARD MEMBER / MAIN BODY PAGE")
    print(f"URL: {BODY_URL}")

    page.goto(BODY_URL, wait_until="networkidle", timeout=60000)
    page.wait_for_timeout(3000)

    subsection("Bodies / Committees Listed")
    body_links = page.query_selector_all("a[href*='DepartmentDetail']")
    print(f"  Found {len(body_links)} body/department links")
    for b in body_links[:15]:
        text = b.inner_text().strip()
        href = b.get_attribute("href") or ""
        if text:
            print(f"    {text}  ->  {href[:100]}")

    subsection("Board of Education Department Detail")
    board_link = None
    for b in body_links:
        text = b.inner_text().strip()
        if "board" in text.lower() and "education" in text.lower():
            board_link = b
            break
    if not board_link:
        for b in body_links:
            text = b.inner_text().strip()
            if "board" in text.lower():
                board_link = b
                break

    if board_link:
        href = board_link.get_attribute("href") or ""
        full_url = href if href.startswith("http") else "https://lausd.legistar.com/" + href.lstrip("/")
        print(f"  Navigating to: {full_url}")
        page.goto(full_url, wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(3000)

        member_table = page.query_selector("table.rgMasterTable")
        if member_table:
            headers = member_table.query_selector_all("th")
            header_texts = [h.inner_text().strip() for h in headers if h.inner_text().strip()]
            print(f"  Member table columns: {header_texts}")

            rows = member_table.query_selector_all("tr.rgRow, tr.rgAltRow")
            print(f"  Member rows: {len(rows)}")
            for idx, row in enumerate(rows[:10]):
                cells = row.query_selector_all("td")
                row_data = {}
                for ci, cell in enumerate(cells):
                    col = header_texts[ci] if ci < len(header_texts) else f"col_{ci}"
                    text = cell.inner_text().strip()
                    imgs = cell.query_selector_all("img")
                    img_info = ""
                    if imgs:
                        srcs = [img.get_attribute("src") or "" for img in imgs]
                        img_info = f" [images: {', '.join(s[:60] for s in srcs)}]"
                    links = cell.query_selector_all("a")
                    link_info = ""
                    if links:
                        hrefs = [l.get_attribute("href") or "" for l in links]
                        link_info = f" [links: {', '.join(h[:60] for h in hrefs if h)}]"
                    if text or img_info or link_info:
                        row_data[col] = (text + img_info + link_info)[:200]
                print(f"    Member {idx}: {json.dumps(row_data, indent=8)}")
        else:
            print("  (No member table found)")
            content = page.inner_text("body")
            print(f"  Page text (first 800 chars):\n    {content[:800]}")

    subsection("People Page")
    page.goto("https://lausd.legistar.com/People.aspx", wait_until="networkidle", timeout=60000)
    page.wait_for_timeout(3000)

    people_table = page.query_selector("table.rgMasterTable")
    if people_table:
        headers = people_table.query_selector_all("th")
        header_texts = [h.inner_text().strip() for h in headers if h.inner_text().strip()]
        print(f"  People table columns: {header_texts}")

        rows = people_table.query_selector_all("tr.rgRow, tr.rgAltRow")
        print(f"  People rows: {len(rows)}")
        for idx, row in enumerate(rows[:8]):
            cells = row.query_selector_all("td")
            row_data = {}
            for ci, cell in enumerate(cells):
                col = header_texts[ci] if ci < len(header_texts) else f"col_{ci}"
                text = cell.inner_text().strip()
                imgs = cell.query_selector_all("img")
                img_info = ""
                if imgs:
                    srcs = [img.get_attribute("src") or "" for img in imgs]
                    img_info = f" [img: {', '.join(s[:80] for s in srcs)}]"
                links = cell.query_selector_all("a")
                link_info = ""
                if links:
                    hrefs = [l.get_attribute("href") or "" for l in links]
                    link_info = f" [links: {', '.join(h[:80] for h in hrefs if h)}]"
                if text or img_info or link_info:
                    row_data[col] = (text + img_info + link_info)[:200]
            print(f"    Person {idx}: {json.dumps(row_data, indent=8)}")
    else:
        print("  (No people table found)")

    subsection("Individual Person Detail Page")
    person_links = page.query_selector_all("a[href*='PersonDetail']")
    if person_links:
        href = person_links[0].get_attribute("href") or ""
        name = person_links[0].inner_text().strip()
        full_url = href if href.startswith("http") else "https://lausd.legistar.com/" + href.lstrip("/")
        print(f"  Navigating to person: {name} -> {full_url}")
        page.goto(full_url, wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(3000)

        person_info = page.evaluate("""
            () => {
                const info = {};
                const img = document.querySelector('img[id*="imgPhoto"], img[id*="photo"], img[id*="Photo"]');
                if (img) info['photo_url'] = img.src;
                const spans = document.querySelectorAll('span[id*="ContentPlaceHolder1"]');
                spans.forEach(s => {
                    const id = s.id.split('_').pop();
                    const text = s.innerText.trim();
                    if (text) info[id] = text;
                });
                const links = document.querySelectorAll('a[id*="ContentPlaceHolder1"]');
                links.forEach(l => {
                    const id = l.id.split('_').pop();
                    const text = l.innerText.trim();
                    const href = l.href || '';
                    if (text || href) info[id] = text + (href ? ' [' + href + ']' : '');
                });
                return info;
            }
        """)
        print(f"  Person detail fields:")
        for k, v in person_info.items():
            print(f"    {k}: {str(v)[:200]}")

        tables = page.query_selector_all("table.rgMasterTable")
        for i, t in enumerate(tables):
            tid = t.get_attribute("id") or "(no id)"
            headers = [h.inner_text().strip() for h in t.query_selector_all("th") if h.inner_text().strip()]
            rows = t.query_selector_all("tr.rgRow, tr.rgAltRow")
            print(f"    Table[{i}] id={tid[:50]} cols={headers} rows={len(rows)}")
    else:
        print("  (No person detail links found)")


# --------------------------------------------------------------------------- #
#  4. COMPARE WITH CURRENT CSV COLUMNS
# --------------------------------------------------------------------------- #
def compare_with_csv(meeting_data, legislation_data):
    section("4. COMPARISON: WEB PORTAL vs. CURRENT CSV EXTRACTION")

    current_csv_fields = [
        "event_id", "event_date", "event_time", "event_location",
        "event_item_id", "agenda_number", "agenda_sequence",
        "matter_file", "matter_name", "matter_title", "matter_type",
        "matter_type_name", "matter_status", "matter_status_name",
        "matter_intro_date", "matter_passed_date",
        "matter_enactment_date", "matter_enactment_number",
        "matter_requester", "matter_body_name",
        "title", "action", "action_text", "passed", "vote_type",
        "consent", "tally", "mover", "seconder", "roll_call_flag",
        "agenda_link", "minutes_link", "video_link", "attachment_links",
        "Agenda_item_fulltext", "(member vote columns)"
    ]

    subsection("Current CSV Fields")
    for f in sorted(current_csv_fields):
        print(f"  - {f}")

    subsection("Web Portal Data NOT in Current CSV")
    potential_web_extras = [
        ("Sponsors/Co-sponsors", "Legislation detail page shows sponsor info beyond just 'requester'"),
        ("Legislative History (per-item)", "History tab shows date, action, result, action_details, vote per step"),
        ("Version Number", "Legislation version tracking on detail page"),
        ("Cost/Fiscal Impact", "Cost field on legislation detail page"),
        ("In Control (Committee)", "Which committee currently holds the item"),
        ("Person Photos", "Board member photos with URLs on People/Person detail pages"),
        ("Person District Numbers", "District assignments for board members"),
        ("Person Terms (Start/End)", "Term start/end dates for each member on Department pages"),
        ("Person Email/Website", "Contact info links on person detail pages"),
        ("Person Notes/Bio", "Biographical or notes field on person detail"),
        ("Attachment Filenames", "Individual attachment names (not just bulk links)"),
        ("Action Details Text", "Expanded action details per history entry"),
        ("Result (Pass/Fail text)", "Explicit pass/fail result text per history entry"),
        ("Meeting Agenda PDF URL", "Direct link to the agenda PDF document"),
        ("Meeting Minutes PDF URL", "Direct link to the minutes PDF document"),
        ("Meeting Video URL", "Direct link to video recording (Granicus/YouTube)"),
    ]

    for field, description in potential_web_extras:
        print(f"  * {field}")
        print(f"      {description}")

    subsection("Summary of Gaps")
    print(f"  Current CSV has {len(current_csv_fields)} field categories")
    print(f"  Web portal has up to {len(potential_web_extras)} additional data points")
    print()
    print("  HIGH-VALUE missing data (recommended to add):")
    high_value = [
        "Legislative History (per-item) - action trail with dates, results, votes",
        "Sponsors/Co-sponsors - who introduced/supported legislation",
        "In Control (Committee) - current committee assignment",
        "Person District Numbers - maps members to districts",
        "Attachment Filenames - descriptive names for each attachment file",
    ]
    for item in high_value:
        print(f"    >> {item}")


# --------------------------------------------------------------------------- #
#  MAIN
# --------------------------------------------------------------------------- #
def main():
    print("=" * 90)
    print("  LAUSD LEGISTAR WEB PORTAL INVESTIGATION")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 90)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )
        page = context.new_page()
        page.set_default_timeout(30000)

        # 1. Meeting Detail
        leg_links = investigate_meeting_page(page)

        # 2. Legislation Detail
        leg_data = investigate_legislation_page(page, leg_links)

        # 3. Board Members
        investigate_board_members(page)

        # 4. Comparison
        compare_with_csv({}, leg_data)

        browser.close()

    print("\n" + "=" * 90)
    print("  INVESTIGATION COMPLETE")
    print("=" * 90)


if __name__ == "__main__":
    main()
