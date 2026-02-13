#!/usr/bin/env python3
"""
Extract LAUSD Board of Education voting data for a specified year.
Output: CSV with one row per agenda item, columns for each board member's vote.

This script captures:
- All agenda items with their outcomes (action, passed flag)
- Per-item votes from /EventItems/{id}/Votes (Aye, Nay, Abstained, Recused, Excused)
- Board member attendance for each meeting (from attendance roll call)
- Consent items use attendance as proxy (all present = Aye)
- Meeting-level links: agenda PDF, minutes PDF, video
- EventItem fields: agenda_sequence, consent, mover, seconder, tally, action_text
- Matter details (via /matters/{id}): type_name, status_name, intro date, body_name, title
- Attachment links (via /matters/{id}/attachments): pipe-delimited hyperlinks
- Persons CSV: contact data for all persons in the system

Usage:
    python extract_lausd.py --year 2025
    python extract_lausd.py --year 2025 --skip-text
    python extract_lausd.py --year 2025 --body 138

Requirements:
    pip install requests playwright
    playwright install chromium
"""

import argparse
import requests
import csv
import time
from pathlib import Path
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BASE_URL = "https://webapi.legistar.com/v1/lausd"
LEGISTAR_WEB = "https://lausd.legistar.com"

# LAUSD Board of Education = BodyId 138
DEFAULT_BODY_ID = 138

VOTE_MAP = {
    'Aye': 'Yes',
    'Nay': 'No',
    'Abstained': 'Abstain',
    'Recused': 'Recused',
    'Excused': 'Excused',
    'Absent': 'Absent',
    'Present': 'Present',
}


def get_year_dates(year: int) -> tuple:
    """Return (start_date, end_date) for the given year."""
    return f"{year}-01-01", f"{year + 1}-01-01"


def get_output_paths(output_dir: Path, year: int) -> dict:
    """Generate standardized output file paths."""
    prefix = f"LAUSD-{year}"
    return {
        'votes': output_dir / f"{prefix}-Votes.csv",
        'voted_items': output_dir / f"{prefix}-Voted-Items.csv",
        'persons': output_dir / f"{prefix}-Persons.csv",
    }


class LAUSDExtractionWorkflow:
    """Complete LAUSD Board of Education data extraction workflow."""

    def __init__(self, year: int, body_id: int = DEFAULT_BODY_ID,
                 skip_text: bool = False, output_dir: Path = None):
        self.year = year
        self.body_id = body_id
        self.skip_text = skip_text
        self.start_date, self.end_date = get_year_dates(year)
        self.output_dir = output_dir or Path(__file__).parent
        self.output_paths = get_output_paths(self.output_dir, year)
        self.session = self._create_session()
        self.all_members = set()
        self.attendance_by_meeting = {}
        self.meeting_links = {}
        self.matter_cache = {}

    def _create_session(self) -> requests.Session:
        session = requests.Session()
        retry = Retry(total=5, backoff_factor=1,
                      status_forcelist=[429, 500, 502, 503, 504])
        adapter = HTTPAdapter(max_retries=retry)
        session.mount('http://', adapter)
        session.mount('https://', adapter)
        return session

    def _api_get(self, url, params=None):
        time.sleep(0.25)
        try:
            response = self.session.get(url, params=params, timeout=30)
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            print(f"  Error fetching {url}: {e}")
            time.sleep(2)
            return None

    def fetch_persons(self) -> dict:
        print("Fetching persons list...")
        persons_raw = self._api_get(f"{BASE_URL}/persons") or []
        persons_by_name = {}
        for p in persons_raw:
            name = p.get('PersonFullName', '')
            if name:
                persons_by_name[name] = p
        print(f"Found {len(persons_by_name)} persons")
        return persons_by_name

    def fetch_meetings(self) -> list:
        print(f"\nFetching {self.year} meetings (BodyId={self.body_id})...")
        params = {
            "$filter": f"EventBodyId eq {self.body_id} and EventDate ge datetime'{self.start_date}' and EventDate lt datetime'{self.end_date}'",
            "$orderby": "EventDate asc"
        }
        meetings = self._api_get(f"{BASE_URL}/events", params) or []
        print(f"Found {len(meetings)} meetings")
        return meetings

    def fetch_event_items(self, event_id: int) -> list:
        return self._api_get(f"{BASE_URL}/events/{event_id}/EventItems") or []

    def fetch_roll_calls(self, event_item_id: int) -> list:
        """Get attendance roll call data."""
        return self._api_get(f"{BASE_URL}/EventItems/{event_item_id}/RollCalls") or []

    def fetch_item_votes(self, event_item_id: int) -> list:
        """Get actual per-item legislation votes."""
        return self._api_get(f"{BASE_URL}/EventItems/{event_item_id}/Votes") or []

    def fetch_matter_details(self, matter_id: int):
        return self._api_get(f"{BASE_URL}/matters/{matter_id}")

    def fetch_matter_attachments(self, matter_id: int) -> list:
        return self._api_get(f"{BASE_URL}/matters/{matter_id}/attachments") or []

    def fetch_matter_histories(self, matter_id: int) -> list:
        return self._api_get(f"{BASE_URL}/matters/{matter_id}/histories") or []

    def collect_event_items(self, meetings: list) -> list:
        print("\n=== Phase 1: Collecting API data ===")
        all_items = []

        for meeting in meetings:
            event_id = meeting['EventId']
            event_date = meeting['EventDate'][:10]
            print(f"\nProcessing meeting {event_date} (EventId: {event_id})...")

            self.meeting_links[event_id] = {
                'agenda_link': meeting.get('EventAgendaFile') or '',
                'minutes_link': meeting.get('EventMinutesFile') or '',
                'video_link': meeting.get('EventVideoPath') or '',
                'insite_url': meeting.get('EventInSiteURL') or '',
                'event_location': meeting.get('EventLocation') or '',
                'event_time': meeting.get('EventTime') or '',
            }

            items = self.fetch_event_items(event_id)
            print(f"  Found {len(items)} agenda items")

            # First pass: find attendance roll call
            for item in items:
                title_upper = (item.get('EventItemTitle') or '').upper()
                if 'ROLL CALL' in title_upper or 'ATTENDANCE' in title_upper:
                    roll_calls = self.fetch_roll_calls(item['EventItemId'])
                    attendance = {}
                    for rc in roll_calls:
                        name = rc['RollCallPersonName']
                        value = rc['RollCallValueName']
                        self.all_members.add(name)
                        attendance[name] = value
                    self.attendance_by_meeting[event_id] = attendance
                    if attendance:
                        print(f"  Found attendance roll call: {len(attendance)} members")
                    break

            # Second pass: record all items
            meeting_attendance = self.attendance_by_meeting.get(event_id, {})
            for item in items:
                title = item.get('EventItemTitle', '') or ''
                if not title.strip():
                    continue

                item_data = {
                    'event_id': event_id,
                    'event_date': event_date,
                    'event_time': self.meeting_links[event_id]['event_time'],
                    'event_location': self.meeting_links[event_id]['event_location'],
                    'event_item_id': item['EventItemId'],
                    'agenda_number': item.get('EventItemAgendaNumber', ''),
                    'agenda_sequence': item.get('EventItemAgendaSequence', ''),
                    'matter_file': item.get('EventItemMatterFile', ''),
                    'matter_name': item.get('EventItemMatterName', ''),
                    'matter_type': item.get('EventItemMatterType', ''),
                    'matter_status': item.get('EventItemMatterStatus', ''),
                    'title': title,
                    'action': item.get('EventItemActionName', ''),
                    'action_text': item.get('EventItemActionText', ''),
                    'passed': item.get('EventItemPassedFlag'),
                    'consent': item.get('EventItemConsent', ''),
                    'tally': item.get('EventItemTally', ''),
                    'mover': item.get('EventItemMover', ''),
                    'seconder': item.get('EventItemSeconder', ''),
                    'roll_call_flag': item.get('EventItemRollCallFlag', 0),
                    'matter_id': item.get('EventItemMatterId'),
                    'matter_title': '',
                    'matter_type_name': '',
                    'matter_status_name': '',
                    'matter_intro_date': '',
                    'matter_passed_date': '',
                    'matter_enactment_date': '',
                    'matter_enactment_number': '',
                    'matter_requester': '',
                    'matter_body_name': '',
                    'attachment_links': '',
                    'legislative_history': '',
                    'attendance': meeting_attendance,
                    'agenda_link': self.meeting_links[event_id]['agenda_link'],
                    'minutes_link': self.meeting_links[event_id]['minutes_link'],
                    'video_link': self.meeting_links[event_id]['video_link'],
                    'Agenda_item_fulltext': '',
                }
                all_items.append(item_data)

        # Third pass: fetch per-item votes
        voted = [i for i in all_items if i['passed'] is not None]
        print(f"\nFetching per-item votes for {len(voted)} voted items...")
        found_votes = 0
        for idx, item in enumerate(voted, 1):
            if idx % 50 == 0:
                print(f"  Progress: {idx}/{len(voted)} items checked...")
            votes = self.fetch_item_votes(item['event_item_id'])
            item_votes = {}
            for v in votes:
                name = v.get('VotePersonName', '')
                value = v.get('VoteValueName', '')
                if name:
                    self.all_members.add(name)
                    item_votes[name] = value
            item['item_votes'] = item_votes
            if item_votes:
                found_votes += 1

        for item in all_items:
            if 'item_votes' not in item:
                item['item_votes'] = {}

        print(f"Per-item votes found for {found_votes}/{len(voted)} voted items")
        return all_items

    def enrich_matter_data(self, all_items: list):
        print("\n=== Phase 1.5: Fetching matter details and attachments ===")
        unique_matter_ids = set()
        for item in all_items:
            mid = item.get('matter_id')
            if mid:
                unique_matter_ids.add(mid)
        print(f"Unique matters to fetch: {len(unique_matter_ids)}")

        for i, mid in enumerate(sorted(unique_matter_ids), 1):
            if i % 50 == 0:
                print(f"  [{i}/{len(unique_matter_ids)}] Fetching matter {mid}...")
            details = self.fetch_matter_details(mid)
            attachments = self.fetch_matter_attachments(mid)
            histories = self.fetch_matter_histories(mid)
            self.matter_cache[mid] = {'details': details, 'attachments': attachments, 'histories': histories}

        for item in all_items:
            mid = item.get('matter_id')
            if mid and mid in self.matter_cache:
                details = self.matter_cache[mid].get('details')
                if details:
                    item['matter_title'] = details.get('MatterTitle', '') or ''
                    item['matter_type_name'] = details.get('MatterTypeName', '') or ''
                    item['matter_status_name'] = details.get('MatterStatusName', '') or ''
                    intro = details.get('MatterIntroDate', '') or ''
                    item['matter_intro_date'] = intro[:10] if intro else ''
                    passed_d = details.get('MatterPassedDate', '') or ''
                    item['matter_passed_date'] = passed_d[:10] if passed_d else ''
                    enact_d = details.get('MatterEnactmentDate', '') or ''
                    item['matter_enactment_date'] = enact_d[:10] if enact_d else ''
                    item['matter_enactment_number'] = details.get('MatterEnactmentNumber', '') or ''
                    item['matter_requester'] = details.get('MatterRequester', '') or ''
                    item['matter_body_name'] = details.get('MatterBodyName', '') or ''

                attachments = self.matter_cache[mid].get('attachments', [])
                if attachments:
                    links = [a.get('MatterAttachmentHyperlink', '') for a in attachments
                             if a.get('MatterAttachmentHyperlink')]
                    item['attachment_links'] = '|'.join(links)

                histories = self.matter_cache[mid].get('histories', [])
                if histories:
                    steps = []
                    for h in sorted(histories, key=lambda x: x.get('MatterHistoryActionDate', '')):
                        date = (h.get('MatterHistoryActionDate') or '')[:10]
                        body = h.get('MatterHistoryActionBodyName', '')
                        action = h.get('MatterHistoryActionName', '')
                        action_text = h.get('MatterHistoryActionText', '')
                        mover = h.get('MatterHistoryMoverName', '')
                        seconder = h.get('MatterHistorySeconderName', '')
                        version = h.get('MatterHistoryVersion', '')
                        step = f"{date}: {body} - {action}"
                        if mover:
                            step += f" (Mover: {mover}"
                            if seconder:
                                step += f", Seconder: {seconder}"
                            step += ")"
                        steps.append(step)
                    item['legislative_history'] = ' | '.join(steps)

        print(f"Matter details populated for {sum(1 for i in all_items if i.get('matter_title'))} items")

    def scrape_legislation_urls(self, page, meeting_insite_url: str) -> dict:
        """Scrape meeting page to map matter file numbers to LegislationDetail URLs."""
        file_to_url = {}
        try:
            page.goto(meeting_insite_url, wait_until="domcontentloaded")
            page.wait_for_load_state("networkidle")
            time.sleep(1)

            links = page.eval_on_selector_all(
                'a[href*="LegislationDetail"]',
                '''els => els.map(el => ({
                    fileNumber: el.textContent.trim(),
                    href: el.href
                }))'''
            )
            for link in links:
                if link['fileNumber']:
                    file_to_url[link['fileNumber']] = link['href']

            print(f"  Scraped {len(file_to_url)} legislation URLs from meeting page")
        except Exception as e:
            print(f"  Error scraping meeting page: {e}")

        return file_to_url

    def extract_full_text(self, page, legislation_url: str) -> str:
        """Extract full text from a LegislationDetail page's Text tab."""
        if "FullText=1" not in legislation_url:
            separator = "&" if "?" in legislation_url else "?"
            if "Options=" in legislation_url:
                legislation_url = legislation_url.replace("Options=", "Options=ID|Text|")
            else:
                legislation_url += f"{separator}Options=ID|Text|"
            legislation_url += "&FullText=1"

        try:
            page.goto(legislation_url, wait_until="domcontentloaded")
            page.wait_for_load_state("networkidle")
            time.sleep(0.5)

            text_div = page.query_selector('#ctl00_ContentPlaceHolder1_divText')
            if text_div:
                text = text_div.inner_text().strip()
                return text if text else None

            return None
        except Exception as e:
            print(f"    Error extracting text: {e}")
            return None

    def scrape_full_text(self, all_items: list):
        """Phase 2: Scrape full text using Playwright."""
        from playwright.sync_api import sync_playwright

        print("\n=== Phase 2: Scraping full legislative text via Playwright ===")
        items_with_matter = [i for i in all_items if i['matter_file']]
        print(f"Items with matter files to scrape: {len(items_with_matter)}")

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            file_to_url_all = {}
            processed_meetings = set()

            for item in items_with_matter:
                event_id = item['event_id']
                if event_id not in processed_meetings:
                    insite_url = self.meeting_links[event_id].get('insite_url', '')
                    if insite_url:
                        print(f"\nScraping meeting page for EventId {event_id}...")
                        file_to_url = self.scrape_legislation_urls(page, insite_url)
                        file_to_url_all.update(file_to_url)
                    processed_meetings.add(event_id)

            total = len(items_with_matter)
            extracted = 0
            skipped = 0
            for i, item in enumerate(items_with_matter, 1):
                matter_file = item['matter_file']
                legislation_url = file_to_url_all.get(matter_file)

                if not legislation_url:
                    skipped += 1
                    continue

                if i % 10 == 0 or i == 1:
                    print(f"  [{i}/{total}] Extracting text for {matter_file}...", end=" ")
                full_text = self.extract_full_text(page, legislation_url)

                if full_text:
                    item['Agenda_item_fulltext'] = full_text
                    extracted += 1
                    if i % 10 == 0 or i == 1:
                        print(f"OK ({len(full_text)} chars)")
                else:
                    if i % 10 == 0 or i == 1:
                        print("No text found")

                time.sleep(0.3)

            browser.close()

        print(f"\nFull text extraction complete: {extracted} extracted, {skipped} skipped (no URL)")

    def _assign_votes(self, item, members_list):
        """Assign vote values based on per-item votes or attendance fallback."""
        votes = {}
        item_votes = item.get('item_votes', {})
        has_real_votes = any(v is not None and v != '' for v in item_votes.values()) if item_votes else False
        if has_real_votes:
            votes['vote_type'] = 'Roll Call'
            for member in members_list:
                if member in item_votes:
                    mapped = VOTE_MAP.get(item_votes[member], item_votes[member])
                    votes[member] = mapped if mapped is not None else ''
                else:
                    att = item['attendance'].get(member, '')
                    if att in ('Absent', 'Excused'):
                        votes[member] = 'Absent'
                    else:
                        votes[member] = ''
        elif item.get('passed') == 1:
            votes['vote_type'] = 'Voice/Consent'
            for member in members_list:
                att = item['attendance'].get(member, '')
                if att in ('Absent', 'Excused'):
                    votes[member] = 'Absent'
                else:
                    votes[member] = 'Yes'
        elif item.get('passed') is not None:
            votes['vote_type'] = 'No Vote'
            for member in members_list:
                votes[member] = ''
        else:
            votes['vote_type'] = ''
            for member in members_list:
                votes[member] = ''
        return votes

    def load_existing_text(self) -> dict:
        """Load existing text from previous CSV for preservation."""
        text_map = {}
        csv_path = self.output_paths['votes']
        if csv_path.exists():
            try:
                with open(csv_path, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        key = row.get('event_item_id', '')
                        text = row.get('Agenda_item_fulltext', '')
                        if key and text:
                            text_map[key] = text
                print(f"Loaded {len(text_map)} existing text entries for preservation")
            except Exception as e:
                print(f"Warning: could not load existing text: {e}")
        return text_map

    def write_output(self, all_items: list, persons_by_name: dict):
        members_list = sorted(list(self.all_members))
        print(f"\nFound {len(members_list)} board members: {members_list}")
        print(f"Total agenda items: {len(all_items)}")

        output_file = self.output_paths['votes']
        fieldnames = [
            'event_id', 'event_date', 'event_time', 'event_location',
            'event_item_id', 'agenda_number', 'agenda_sequence',
            'matter_file', 'matter_name', 'matter_title', 'matter_type', 'matter_type_name',
            'matter_status', 'matter_status_name',
            'matter_intro_date', 'matter_passed_date', 'matter_enactment_date', 'matter_enactment_number',
            'matter_requester', 'matter_body_name',
            'title', 'action', 'action_text', 'passed', 'vote_type', 'consent', 'tally', 'mover', 'seconder',
            'roll_call_flag', 'agenda_link', 'minutes_link', 'video_link', 'attachment_links',
            'legislative_history', 'Agenda_item_fulltext',
        ] + members_list

        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for item in all_items:
                row = {k: item.get(k, '') for k in fieldnames if k not in members_list}
                row.update(self._assign_votes(item, members_list))
                writer.writerow(row)

        print(f"\nCSV written to: {output_file}")

        # Voted items only
        voted_items = [i for i in all_items if i['passed'] is not None]
        output_voted = self.output_paths['voted_items']
        with open(output_voted, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for item in voted_items:
                row = {k: item.get(k, '') for k in fieldnames if k not in members_list}
                row.update(self._assign_votes(item, members_list))
                writer.writerow(row)

        print(f"Voted items CSV: {output_voted}")
        print(f"Total voted items: {len(voted_items)}")

        # Persons CSV
        output_persons = self.output_paths['persons']
        with open(output_persons, 'w', newline='', encoding='utf-8') as f:
            person_fields = [
                'PersonId', 'PersonFullName', 'PersonFirstName', 'PersonLastName',
                'PersonEmail', 'PersonActiveFlag', 'PersonPhone', 'PersonWWW',
            ]
            writer = csv.DictWriter(f, fieldnames=person_fields)
            writer.writeheader()
            for name in sorted(persons_by_name.keys()):
                p = persons_by_name[name]
                writer.writerow({k: p.get(k, '') for k in person_fields})

        print(f"Persons CSV: {output_persons} ({len(persons_by_name)} persons)")

    def run(self):
        print("=" * 70)
        print(f"LAUSD Board of Education Data Extraction - {self.year}")
        print(f"Date range: {self.start_date} to {self.end_date}")
        print("=" * 70)

        persons_by_name = self.fetch_persons()
        meetings = self.fetch_meetings()

        if not meetings:
            print(f"\nNo meetings found for {self.year}")
            return

        all_items = self.collect_event_items(meetings)
        self.enrich_matter_data(all_items)

        # Phase 2: Web scraping for full text
        if not self.skip_text:
            self.scrape_full_text(all_items)
        else:
            print("\n[Skipping Phase 2: Full text scraping (--skip-text)]")
            text_map = self.load_existing_text()
            if text_map:
                preserved = 0
                for item in all_items:
                    eid = str(item['event_item_id'])
                    if eid in text_map:
                        item['Agenda_item_fulltext'] = text_map[eid]
                        preserved += 1
                print(f"Preserved {preserved} text entries from existing CSV")

        self.write_output(all_items, persons_by_name)

        print("\n" + "=" * 70)
        print("Extraction complete!")
        print("=" * 70)


def main():
    parser = argparse.ArgumentParser(
        description="LAUSD Board of Education Data Extraction",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python extract_lausd.py --year 2025
    python extract_lausd.py --year 2024
    python extract_lausd.py --year 2025 --body 197  # Committee of the Whole
        """
    )
    parser.add_argument("--year", type=int, required=True,
                        help="Year to extract (e.g., 2025)")
    parser.add_argument("--body", type=int, default=DEFAULT_BODY_ID,
                        help=f"Body ID to extract (default: {DEFAULT_BODY_ID} = Board of Education)")
    parser.add_argument("--skip-text", action="store_true",
                        help="Skip Playwright full text extraction (Phase 2)")
    parser.add_argument("--output-dir", type=Path,
                        help="Override default output directory")

    args = parser.parse_args()

    workflow = LAUSDExtractionWorkflow(
        year=args.year,
        body_id=args.body,
        skip_text=args.skip_text,
        output_dir=args.output_dir
    )
    workflow.run()


if __name__ == "__main__":
    main()
