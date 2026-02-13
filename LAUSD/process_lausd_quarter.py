#!/usr/bin/env python3
"""
Process LAUSD FileMaker Resolutions raw JSON into CityVotes Research CSV format.

Usage:
    python3 process_lausd_quarter.py 2021 1    # Process Q1 2021
    python3 process_lausd_quarter.py 2023 3    # Process Q3 2023

Reads: LAUSD-Q{quarter}-{year}-Resolutions-Raw.json
Writes: LAUSD-{year}-Q{quarter}-Votes.csv, LAUSD-{year}-Q{quarter}-Voted-Items.csv,
        LAUSD-{year}-Q{quarter}-Persons.csv

Optionally merges Granicus video/agenda links if LAUSD-Q{quarter}-{year}-Granicus-Meetings.json exists.
"""

import json
import csv
import os
import sys
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def parse_date(date_str):
    """Convert 'Mar 10, 2020' or 'Jan 14, 2020' to '2020-01-14' format."""
    if not date_str:
        return ""
    for fmt in ("%b %d, %Y", "%m/%d/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(date_str.strip(), fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return date_str


def load_granicus_meetings(year, quarter):
    """Load Granicus meetings JSON if available. Returns date -> meeting mapping."""
    path = os.path.join(SCRIPT_DIR, f"LAUSD-Q{quarter}-{year}-Granicus-Meetings.json")
    if not os.path.exists(path):
        return {}

    with open(path) as f:
        granicus = json.load(f)

    date_to_meeting = {}
    for meeting in granicus.get("meetings", []):
        if (meeting.get("status") == "accessible"
                and not meeting.get("is_closed_session")
                and meeting.get("meeting_type") in ("Regular Board Meeting", "Special Board Meeting")
                and meeting.get("committee_name") is None):
            date = meeting["date"]
            if date not in date_to_meeting or meeting.get("time") == "1:00 PM":
                date_to_meeting[date] = meeting
    return date_to_meeting


def get_board_members(data):
    """Extract unique board member names from vote data."""
    members = []
    seen = set()
    for res in data:
        for v in res.get("votes", []):
            name = v["name"]
            if name not in seen:
                seen.add(name)
                members.append(name)
    return members


def compute_tally(votes):
    """Compute vote tally string from vote list."""
    counts = {}
    for v in votes:
        val = v.get("vote", "")
        if val:
            counts[val] = counts.get(val, 0) + 1
    parts = []
    if counts.get("Yes", 0): parts.append(f"Ayes: {counts['Yes']}")
    if counts.get("No", 0): parts.append(f"Nays: {counts['No']}")
    if counts.get("Absent", 0): parts.append(f"Absent: {counts['Absent']}")
    if counts.get("Abstain", 0): parts.append(f"Abstain: {counts['Abstain']}")
    return "; ".join(parts)


def generate_votes_csv(data, output_path, board_members, granicus):
    """Generate Votes CSV with per-member vote columns."""
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
    ] + board_members

    rows = []
    event_dates = {}

    for i, res in enumerate(data):
        action_date = parse_date(res["action_date"])
        if action_date not in event_dates:
            event_dates[action_date] = f"FM-{action_date}"

        vote_map = {v["name"]: v["vote"] for v in res.get("votes", [])}
        tally = compute_tally(res.get("votes", []))
        passed = 1 if res.get("action", "") in ("Adopted", "Adopted as Amended") else 0

        student_votes_str = "; ".join(
            f"{sv['name']}: {sv.get('vote') or 'Advisory'}" for sv in res.get("student_votes", [])
        ) if res.get("student_votes") else ""

        meeting = granicus.get(action_date, {})
        agenda_link = meeting.get("agenda_url", "")
        video_link = meeting.get("video_url", "")
        event_time = meeting.get("time", "")

        row = {
            "event_id": event_dates[action_date],
            "event_date": action_date,
            "event_time": event_time,
            "event_location": "LAUSD Board Room",
            "event_item_id": f"FM-{res.get('resolution_number', 'UNKNOWN')}",
            "agenda_number": res.get("resolution_number", ""),
            "agenda_sequence": i + 1,
            "matter_file": f"Res-{res.get('resolution_number', '')}",
            "matter_name": "",
            "matter_title": res.get("title", ""),
            "matter_type": "Resolution",
            "matter_type_name": "Resolution",
            "matter_status": res.get("action", ""),
            "matter_status_name": res.get("action", ""),
            "matter_intro_date": parse_date(res.get("notice_date", "")),
            "matter_passed_date": action_date if passed else "",
            "matter_enactment_date": "",
            "matter_enactment_number": "",
            "matter_requester": "",
            "matter_body_name": "Board of Education",
            "title": res.get("title", ""),
            "action": res.get("action", ""),
            "action_text": "",
            "passed": passed,
            "vote_type": "Roll Call",
            "consent": 0,
            "tally": tally,
            "mover": res.get("moved_by", ""),
            "seconder": res.get("second", ""),
            "roll_call_flag": 1,
            "agenda_link": agenda_link,
            "minutes_link": "",
            "video_link": video_link,
            "attachment_links": "",
            "Agenda_item_fulltext": res.get("language", ""),
            "source": "FileMaker Resolutions DB; Granicus Video Archives" if video_link else "FileMaker Resolutions DB",
            "notice_date": parse_date(res.get("notice_date", "")),
            "sponsor": res.get("sponsor", ""),
            "cosponsors": "; ".join(res.get("cosponsors", [])),
            "student_votes": student_votes_str,
        }

        for member in board_members:
            row[member] = vote_map.get(member, "")
        rows.append(row)

    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} rows to {os.path.basename(output_path)}")


def generate_voted_items_csv(data, output_path, granicus):
    """Generate Voted-Items CSV (no per-member vote columns)."""
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
        tally = compute_tally(res.get("votes", []))
        passed = 1 if res.get("action", "") in ("Adopted", "Adopted as Amended") else 0

        student_votes_str = "; ".join(
            f"{sv['name']}: {sv.get('vote') or 'Advisory'}" for sv in res.get("student_votes", [])
        ) if res.get("student_votes") else ""

        meeting = granicus.get(action_date, {})

        row = {
            "event_id": f"FM-{action_date}",
            "event_date": action_date,
            "event_time": meeting.get("time", ""),
            "event_location": "LAUSD Board Room",
            "event_item_id": f"FM-{res.get('resolution_number', 'UNKNOWN')}",
            "agenda_number": res.get("resolution_number", ""),
            "agenda_sequence": i + 1,
            "matter_file": f"Res-{res.get('resolution_number', '')}",
            "matter_name": "",
            "matter_title": res.get("title", ""),
            "matter_type": "Resolution",
            "matter_type_name": "Resolution",
            "matter_status": res.get("action", ""),
            "matter_status_name": res.get("action", ""),
            "matter_intro_date": parse_date(res.get("notice_date", "")),
            "matter_passed_date": action_date if passed else "",
            "matter_enactment_date": "",
            "matter_enactment_number": "",
            "matter_requester": "",
            "matter_body_name": "Board of Education",
            "title": res.get("title", ""),
            "action": res.get("action", ""),
            "action_text": "",
            "passed": passed,
            "vote_type": "Roll Call",
            "consent": 0,
            "tally": tally,
            "mover": res.get("moved_by", ""),
            "seconder": res.get("second", ""),
            "roll_call_flag": 1,
            "agenda_link": meeting.get("agenda_url", ""),
            "minutes_link": "",
            "video_link": meeting.get("video_url", ""),
            "attachment_links": "",
            "Agenda_item_fulltext": res.get("language", ""),
            "source": "FileMaker Resolutions DB; Granicus Video Archives" if meeting.get("video_url") else "FileMaker Resolutions DB",
            "notice_date": parse_date(res.get("notice_date", "")),
            "sponsor": res.get("sponsor", ""),
            "cosponsors": "; ".join(res.get("cosponsors", [])),
            "student_votes": student_votes_str,
        }
        rows.append(row)

    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} rows to {os.path.basename(output_path)}")


def generate_persons_csv(data, output_path):
    """Generate Persons CSV from vote data."""
    persons = {}
    for res in data:
        for v in res.get("votes", []):
            name = v["name"]
            if name not in persons:
                first, last = split_name(name)
                persons[name] = {"first": first, "last": last, "type": "Board Member"}
        for sv in res.get("student_votes", []):
            name = sv["name"]
            if name not in persons:
                first, last = split_name(name)
                persons[name] = {"first": first, "last": last, "type": "Student Board Member"}

    fieldnames = [
        "PersonId", "PersonFullName", "PersonFirstName", "PersonLastName",
        "PersonType", "PersonActiveFlag", "PersonEmail", "PersonPhone", "PersonWWW",
    ]
    rows = []
    for i, (name, info) in enumerate(sorted(persons.items()), start=1):
        rows.append({
            "PersonId": f"FM-{i}",
            "PersonFullName": name,
            "PersonFirstName": info["first"],
            "PersonLastName": info["last"],
            "PersonType": info["type"],
            "PersonActiveFlag": 1,
            "PersonEmail": "", "PersonPhone": "", "PersonWWW": "",
        })

    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} persons to {os.path.basename(output_path)}")


def split_name(name):
    """Split full name into first/last, handling suffixes like 'III'."""
    suffixes = {"III", "IV", "Jr.", "Sr.", "Jr", "Sr"}
    parts = name.split()
    if len(parts) >= 3 and parts[-1] in suffixes:
        return " ".join(parts[:-2]), " ".join(parts[-2:])
    if len(parts) >= 2:
        return " ".join(parts[:-1]), parts[-1]
    return name, name


def main():
    if len(sys.argv) < 3:
        print("Usage: python3 process_lausd_quarter.py <year> <quarter>")
        sys.exit(1)

    year = int(sys.argv[1])
    quarter = int(sys.argv[2])

    raw_path = os.path.join(SCRIPT_DIR, f"LAUSD-Q{quarter}-{year}-Resolutions-Raw.json")
    if not os.path.exists(raw_path):
        print(f"ERROR: {raw_path} not found. Run extract_lausd_filemaker.py first.")
        sys.exit(1)

    with open(raw_path) as f:
        data = json.load(f)

    if not data:
        print(f"No records in {os.path.basename(raw_path)}, skipping CSV generation.")
        return

    granicus = load_granicus_meetings(year, quarter)
    board_members = get_board_members(data)

    votes_path = os.path.join(SCRIPT_DIR, f"LAUSD-{year}-Q{quarter}-Votes.csv")
    items_path = os.path.join(SCRIPT_DIR, f"LAUSD-{year}-Q{quarter}-Voted-Items.csv")
    persons_path = os.path.join(SCRIPT_DIR, f"LAUSD-{year}-Q{quarter}-Persons.csv")

    generate_votes_csv(data, votes_path, board_members, granicus)
    generate_voted_items_csv(data, items_path, granicus)
    generate_persons_csv(data, persons_path)

    # Summary
    print(f"\n=== LAUSD {year} Q{quarter} Summary ===")
    print(f"Resolutions: {len(data)}")
    dates = set(parse_date(r["action_date"]) for r in data)
    print(f"Meeting dates: {len(dates)} ({', '.join(sorted(dates))})")
    print(f"Board members: {len(board_members)} ({', '.join(board_members)})")

    total_votes = sum(len(r.get("votes", [])) for r in data)
    print(f"Total individual votes: {total_votes}")

    actions = {}
    for r in data:
        a = r.get("action", "Unknown")
        actions[a] = actions.get(a, 0) + 1
    print(f"Actions: {actions}")

    if granicus:
        matched = sum(1 for d in dates if d in granicus)
        print(f"Granicus video matches: {matched}/{len(dates)} dates")


if __name__ == '__main__':
    main()
