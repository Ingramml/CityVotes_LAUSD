#!/usr/bin/env python3
"""Process LAUSD Q1 2020 FileMaker Resolutions data into CityVotes Research CSV format.

Combines data from two sources:
1. FileMaker Resolutions DB (via Playwright extraction) - resolutions, votes, sponsors
2. Granicus Video Archives (via clip_id probing) - meeting video/agenda URLs
"""

import json
import csv
import os
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
RAW_JSON = os.path.join(SCRIPT_DIR, "LAUSD-Q1-2020-Resolutions-Raw.json")
GRANICUS_JSON = os.path.join(SCRIPT_DIR, "LAUSD-Q1-2020-Granicus-Meetings.json")

# Board members in Q1 2020
BOARD_MEMBERS = [
    "Kelly Gonez",
    "Nick Melvoin",
    "Scott Schmerelson",
    "George McKenna III",
    "Jackie Goldberg",
    "Richard Vladovic",
    "Monica Garcia",
]

# Student board member(s)
STUDENT_MEMBERS = ["Frances Suavillo"]

# Resolution number fixes (smart quotes in titles caused mismatches)
RES_NUM_FIXES = {
    "Celebrating March as Women\u2019s History Month": "035-19/20",
}


def load_granicus_meetings():
    """Load Granicus meetings and build date -> open-session board meeting mapping."""
    if not os.path.exists(GRANICUS_JSON):
        print("WARNING: Granicus meetings JSON not found, video/agenda links will be empty")
        return {}

    with open(GRANICUS_JSON) as f:
        granicus = json.load(f)

    # Map dates to open-session board meetings (where resolutions are voted on)
    date_to_meeting = {}
    for meeting in granicus["meetings"]:
        if (meeting["status"] == "accessible"
                and not meeting["is_closed_session"]
                and meeting["meeting_type"] in ("Regular Board Meeting", "Special Board Meeting")
                and meeting.get("committee_name") is None):
            date = meeting["date"]
            # Prefer the afternoon open session (1:00 PM) over special meetings
            if date not in date_to_meeting or meeting.get("time") == "1:00 PM":
                date_to_meeting[date] = meeting

    return date_to_meeting


def load_and_fix_data():
    with open(RAW_JSON) as f:
        data = json.load(f)

    for item in data:
        if item["resolution_number"] == "UNKNOWN":
            for title_fragment, res_num in RES_NUM_FIXES.items():
                if title_fragment in item["title"]:
                    item["resolution_number"] = res_num
                    break

    # Verify no remaining UNKNOWNs
    unknowns = [r for r in data if r["resolution_number"] == "UNKNOWN"]
    if unknowns:
        print(f"WARNING: {len(unknowns)} resolutions still have UNKNOWN resolution numbers:")
        for u in unknowns:
            print(f"  - {u['title'][:80]}")

    return data


def parse_date(date_str):
    """Convert 'Mar 10, 2020' or 'Jan 14, 2020' to '2020-01-14' format."""
    try:
        dt = datetime.strptime(date_str, "%b %d, %Y")
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        return date_str


def generate_votes_csv(data, output_path, granicus_meetings):
    """Generate Votes CSV matching Columbus-OH schema with Granicus video/agenda links."""
    fieldnames = [
        "event_id", "event_date", "event_time", "event_location",
        "event_item_id", "agenda_number", "agenda_sequence",
        "matter_file", "matter_name", "matter_title",
        "matter_type", "matter_type_name", "matter_status", "matter_status_name",
        "matter_intro_date", "matter_passed_date", "matter_enactment_date",
        "matter_enactment_number", "matter_requester", "matter_body_name",
        "title", "action", "action_text", "passed", "vote_type", "consent",
        "tally", "mover", "seconder", "roll_call_flag",
        "agenda_link", "minutes_link", "video_link", "attachment_links",
        "Agenda_item_fulltext",
        "source",
        "notice_date", "sponsor", "cosponsors", "student_votes",
    ] + BOARD_MEMBERS

    rows = []
    event_dates = {}  # date -> event_id

    for i, res in enumerate(data):
        action_date = parse_date(res["action_date"])

        # Assign event_id based on date
        if action_date not in event_dates:
            event_dates[action_date] = f"FM-{action_date}"
        event_id = event_dates[action_date]

        # Build vote columns
        vote_map = {v["name"]: v["vote"] for v in res["votes"]}

        # Compute tally
        yes_count = sum(1 for v in res["votes"] if v["vote"] == "Yes")
        no_count = sum(1 for v in res["votes"] if v["vote"] == "No")
        absent_count = sum(1 for v in res["votes"] if v["vote"] == "Absent")
        tally_parts = []
        if yes_count: tally_parts.append(f"Ayes: {yes_count}")
        if no_count: tally_parts.append(f"Nays: {no_count}")
        if absent_count: tally_parts.append(f"Absent: {absent_count}")
        tally = "; ".join(tally_parts)

        # Determine passed flag
        passed = 1 if res["action"] in ("Adopted", "Adopted as Amended") else 0

        # Student votes as string
        student_votes_str = "; ".join(
            f"{sv['name']}: {sv['vote'] or 'Advisory'}" for sv in res["student_votes"]
        ) if res["student_votes"] else ""

        # Look up Granicus meeting for this date
        meeting = granicus_meetings.get(action_date, {})
        agenda_link = meeting.get("agenda_url", "")
        video_link = meeting.get("video_url", "")
        event_time = meeting.get("time", "")

        row = {
            "event_id": event_id,
            "event_date": action_date,
            "event_time": event_time,
            "event_location": "LAUSD Board Room",
            "event_item_id": f"FM-{res['resolution_number']}",
            "agenda_number": res["resolution_number"],
            "agenda_sequence": i + 1,
            "matter_file": f"Res-{res['resolution_number']}",
            "matter_name": "",
            "matter_title": res["title"],
            "matter_type": "Resolution",
            "matter_type_name": "Resolution",
            "matter_status": res["action"],
            "matter_status_name": res["action"],
            "matter_intro_date": parse_date(res["notice_date"]) if res["notice_date"] else "",
            "matter_passed_date": action_date if passed else "",
            "matter_enactment_date": "",
            "matter_enactment_number": "",
            "matter_requester": "",
            "matter_body_name": "Board of Education",
            "title": res["title"],
            "action": res["action"],
            "action_text": "",
            "passed": passed,
            "vote_type": "Roll Call",
            "consent": 0,
            "tally": tally,
            "mover": res["moved_by"],
            "seconder": res["second"],
            "roll_call_flag": 1,
            "agenda_link": agenda_link,
            "minutes_link": "",
            "video_link": video_link,
            "attachment_links": "",
            "Agenda_item_fulltext": res["language"],
            "source": "FileMaker Resolutions DB; Granicus Video Archives" if video_link else "FileMaker Resolutions DB",
            "notice_date": parse_date(res["notice_date"]) if res["notice_date"] else "",
            "sponsor": res["sponsor"],
            "cosponsors": "; ".join(res["cosponsors"]),
            "student_votes": student_votes_str,
        }

        # Add individual vote columns
        for member in BOARD_MEMBERS:
            row[member] = vote_map.get(member, "")

        rows.append(row)

    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} rows to {os.path.basename(output_path)}")


def generate_voted_items_csv(data, output_path, granicus_meetings):
    """Generate Voted-Items CSV (same as Votes but without individual vote columns)."""
    fieldnames = [
        "event_id", "event_date", "event_time", "event_location",
        "event_item_id", "agenda_number", "agenda_sequence",
        "matter_file", "matter_name", "matter_title",
        "matter_type", "matter_type_name", "matter_status", "matter_status_name",
        "matter_intro_date", "matter_passed_date", "matter_enactment_date",
        "matter_enactment_number", "matter_requester", "matter_body_name",
        "title", "action", "action_text", "passed", "vote_type", "consent",
        "tally", "mover", "seconder", "roll_call_flag",
        "agenda_link", "minutes_link", "video_link", "attachment_links",
        "Agenda_item_fulltext",
        "source",
        "notice_date", "sponsor", "cosponsors", "student_votes",
    ]

    rows = []
    for i, res in enumerate(data):
        action_date = parse_date(res["action_date"])

        yes_count = sum(1 for v in res["votes"] if v["vote"] == "Yes")
        no_count = sum(1 for v in res["votes"] if v["vote"] == "No")
        absent_count = sum(1 for v in res["votes"] if v["vote"] == "Absent")
        tally_parts = []
        if yes_count: tally_parts.append(f"Ayes: {yes_count}")
        if no_count: tally_parts.append(f"Nays: {no_count}")
        if absent_count: tally_parts.append(f"Absent: {absent_count}")
        tally = "; ".join(tally_parts)

        passed = 1 if res["action"] in ("Adopted", "Adopted as Amended") else 0

        student_votes_str = "; ".join(
            f"{sv['name']}: {sv['vote'] or 'Advisory'}" for sv in res["student_votes"]
        ) if res["student_votes"] else ""

        # Look up Granicus meeting for this date
        meeting = granicus_meetings.get(action_date, {})
        agenda_link = meeting.get("agenda_url", "")
        video_link = meeting.get("video_url", "")
        event_time = meeting.get("time", "")

        row = {
            "event_id": f"FM-{action_date}",
            "event_date": action_date,
            "event_time": event_time,
            "event_location": "LAUSD Board Room",
            "event_item_id": f"FM-{res['resolution_number']}",
            "agenda_number": res["resolution_number"],
            "agenda_sequence": i + 1,
            "matter_file": f"Res-{res['resolution_number']}",
            "matter_name": "",
            "matter_title": res["title"],
            "matter_type": "Resolution",
            "matter_type_name": "Resolution",
            "matter_status": res["action"],
            "matter_status_name": res["action"],
            "matter_intro_date": parse_date(res["notice_date"]) if res["notice_date"] else "",
            "matter_passed_date": action_date if passed else "",
            "matter_enactment_date": "",
            "matter_enactment_number": "",
            "matter_requester": "",
            "matter_body_name": "Board of Education",
            "title": res["title"],
            "action": res["action"],
            "action_text": "",
            "passed": passed,
            "vote_type": "Roll Call",
            "consent": 0,
            "tally": tally,
            "mover": res["moved_by"],
            "seconder": res["second"],
            "roll_call_flag": 1,
            "agenda_link": agenda_link,
            "minutes_link": "",
            "video_link": video_link,
            "attachment_links": "",
            "Agenda_item_fulltext": res["language"],
            "source": "FileMaker Resolutions DB; Granicus Video Archives" if video_link else "FileMaker Resolutions DB",
            "notice_date": parse_date(res["notice_date"]) if res["notice_date"] else "",
            "sponsor": res["sponsor"],
            "cosponsors": "; ".join(res["cosponsors"]),
            "student_votes": student_votes_str,
        }
        rows.append(row)

    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} rows to {os.path.basename(output_path)}")


def generate_persons_csv(data, output_path):
    """Generate Persons CSV from the vote data."""
    persons = {}

    for res in data:
        for v in res["votes"]:
            name = v["name"]
            if name not in persons:
                parts = name.rsplit(" ", 1)
                first = parts[0] if len(parts) > 1 else name
                last = parts[-1]
                # Handle "George McKenna III"
                if name == "George McKenna III":
                    first = "George"
                    last = "McKenna III"
                persons[name] = {
                    "PersonFullName": name,
                    "PersonFirstName": first,
                    "PersonLastName": last,
                    "PersonType": "Board Member",
                    "PersonActiveFlag": 1,
                }

        for sv in res["student_votes"]:
            name = sv["name"]
            if name not in persons:
                parts = name.rsplit(" ", 1)
                first = parts[0] if len(parts) > 1 else name
                last = parts[-1]
                persons[name] = {
                    "PersonFullName": name,
                    "PersonFirstName": first,
                    "PersonLastName": last,
                    "PersonType": "Student Board Member",
                    "PersonActiveFlag": 1,
                }

    fieldnames = [
        "PersonId", "PersonFullName", "PersonFirstName", "PersonLastName",
        "PersonType", "PersonActiveFlag", "PersonEmail", "PersonPhone", "PersonWWW",
    ]

    rows = []
    for i, (name, info) in enumerate(sorted(persons.items()), start=1):
        row = {
            "PersonId": f"FM-{i}",
            "PersonFullName": info["PersonFullName"],
            "PersonFirstName": info["PersonFirstName"],
            "PersonLastName": info["PersonLastName"],
            "PersonType": info["PersonType"],
            "PersonActiveFlag": info["PersonActiveFlag"],
            "PersonEmail": "",
            "PersonPhone": "",
            "PersonWWW": "",
        }
        rows.append(row)

    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} persons to {os.path.basename(output_path)}")


def main():
    data = load_and_fix_data()
    granicus_meetings = load_granicus_meetings()

    # Save fixed JSON back
    with open(RAW_JSON, "w") as f:
        json.dump(data, f, indent=2)
    print(f"Fixed and saved {len(data)} resolutions to JSON")

    # Generate CSVs
    votes_path = os.path.join(SCRIPT_DIR, "LAUSD-2020-Q1-Votes.csv")
    items_path = os.path.join(SCRIPT_DIR, "LAUSD-2020-Q1-Voted-Items.csv")
    persons_path = os.path.join(SCRIPT_DIR, "LAUSD-2020-Q1-Persons.csv")

    generate_votes_csv(data, votes_path, granicus_meetings)
    generate_voted_items_csv(data, items_path, granicus_meetings)
    generate_persons_csv(data, persons_path)

    # Summary
    print(f"\n=== LAUSD Q1 2020 Extraction Summary ===")
    print(f"Sources: FileMaker Resolutions DB + Granicus Video Archives")
    print(f"Period: January 1 - March 31, 2020")
    print(f"Resolutions: {len(data)}")

    dates = set(parse_date(r["action_date"]) for r in data)
    print(f"Meeting dates: {len(dates)} ({', '.join(sorted(dates))})")

    # Report Granicus coverage
    matched = sum(1 for d in dates if d in granicus_meetings)
    print(f"Granicus video matches: {matched}/{len(dates)} dates")
    for d in sorted(dates):
        if d in granicus_meetings:
            m = granicus_meetings[d]
            print(f"  {d}: clip {m['clip_id']} - {m['title']}")
        else:
            print(f"  {d}: NO GRANICUS MATCH")

    all_votes = []
    for r in data:
        all_votes.extend(r["votes"])
    vote_values = {}
    for v in all_votes:
        vote_values[v["vote"]] = vote_values.get(v["vote"], 0) + 1
    print(f"Total individual votes: {len(all_votes)}")
    print(f"Vote breakdown: {vote_values}")

    unique_sponsors = set(r["sponsor"] for r in data)
    print(f"Unique sponsors: {len(unique_sponsors)} ({', '.join(sorted(unique_sponsors))})")

    actions = {}
    for r in data:
        actions[r["action"]] = actions.get(r["action"], 0) + 1
    print(f"Actions: {actions}")

    # Report Granicus meetings not linked to resolutions
    print(f"\nGranicus meetings in Q1 2020: {len(granicus_meetings) + sum(1 for m in [] if True)}")
    if os.path.exists(GRANICUS_JSON):
        with open(GRANICUS_JSON) as f:
            g = json.load(f)
        print(f"  Total meetings found: {g['metadata']['total_meetings_found']}")
        print(f"  Accessible: {g['metadata']['total_accessible_meetings']}")
        print(f"  Restricted: {g['metadata']['total_restricted_meetings']}")


if __name__ == "__main__":
    main()
