#!/usr/bin/env python3
"""
Generate static JSON data files for the CityVotes LAUSD website.

Reads all LAUSD CSV data files and produces the complete data/ folder
structure expected by the CityVotes template.

Usage:
    python3 generate_site_data.py
"""

import csv
import json
import os
import re
import glob
from collections import defaultdict

# ============================================================================
# CONFIGURATION
# ============================================================================

LAUSD_DIR = os.path.join(os.path.dirname(__file__), 'LAUSD')
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), 'Frontend', 'data')

# Known fixed columns in the CSV files (everything else is a board member)
FIXED_COLUMNS = {
    'event_id', 'event_date', 'event_time', 'event_location',
    'event_item_id', 'agenda_number', 'agenda_sequence',
    'matter_file', 'matter_name', 'matter_title',
    'matter_type', 'matter_type_name', 'matter_status', 'matter_status_name',
    'matter_intro_date', 'matter_passed_date', 'matter_enactment_date',
    'matter_enactment_number', 'matter_requester', 'matter_body_name',
    'title', 'action', 'action_text', 'passed', 'vote_type', 'consent',
    'tally', 'mover', 'seconder', 'roll_call_flag',
    'agenda_link', 'minutes_link', 'video_link', 'attachment_links',
    'Agenda_item_fulltext',
    # FileMaker-specific columns
    'source', 'notice_date', 'sponsor', 'cosponsors', 'student_votes',
    # Legistar-specific columns
    'legislative_history',
}

# Name corrections
NAME_CORRECTIONS = {
    'Scott Schmererelson': 'Scott Schmerelson',
}

# Columns to exclude (not real board members)
EXCLUDE_MEMBERS = {'Superintendent'}

# Vote choice normalization
VOTE_CHOICE_MAP = {
    'Yes': 'AYE',
    'No': 'NAY',
    'Absent': 'ABSENT',
    'Abstain': 'ABSTAIN',
    'Recused': 'RECUSAL',
    'Excused': 'ABSENT',
    'Present': 'AYE',
}

# Outcome normalization from action field
ACTION_OUTCOME_MAP = {
    'Adopted': 'PASS',
    'Adopted as Amended': 'PASS',
    'Adopted by Consent Vote': 'PASS',
    'Approved': 'PASS',
    'Failed': 'FAIL',
    'Defeated': 'FAIL',
    'Postponed': 'TABLED',
    'Tabled': 'TABLED',
    'Withdrawn': 'WITHDRAWN',
    'Continued': 'CONTINUED',
    'Removed': 'REMOVED',
    'Received': 'PASS',
}

# LAUSD-specific topic classification keywords
TOPIC_KEYWORDS = {
    'Appointments': [
        'appoint', 'nomination', 'reappoint', 'personnel commission',
        'board officer', 'president', 'vice president', 'delegate',
        'superintendent search'
    ],
    'Budget & Finance': [
        'budget', 'financial', 'revenue', 'expenditure', 'appropriation',
        'funding', 'fiscal', 'audit', 'bond', 'tax', 'property tax',
        'proposition', 'lcff', 'allocation', 'cost', 'salary',
        'compensation', 'pension', 'measure us', 'measure ee'
    ],
    'Curriculum & Instruction': [
        'curriculum', 'instruction', 'academic', 'graduation',
        'ethnic studies', 'literacy', 'math', 'science', 'stem',
        'arts education', 'music program', 'physical education',
        'course', 'textbook', 'assessment', 'testing',
        'a-g requirement', 'college readiness', 'dual language',
        'bilingual', 'english learner', 'media literacy',
        'political education'
    ],
    'Contracts & Agreements': [
        'contract', 'agreement', 'mou', 'memorandum', 'vendor',
        'procurement', 'bid', 'rfp', 'proposal', 'consultant',
        'service agreement', 'lease', 'license'
    ],
    'Charter Schools': [
        'charter', 'renewal petition', 'charter school',
        'co-location', 'proposition 39', 'prop 39',
        'independent charter', 'kipp', 'green dot'
    ],
    'Safety & Student Welfare': [
        'safety', 'police', 'school police', 'security', 'emergency',
        'disaster', 'earthquake', 'fire', 'lockdown',
        'mental health', 'counselor', 'counseling', 'wellness',
        'suicide prevention', 'bullying', 'harassment', 'title ix',
        'restorative justice', 'discipline', 'suspension', 'expulsion'
    ],
    'Health & Nutrition': [
        'health', 'nutrition', 'meal', 'breakfast', 'lunch', 'food',
        'dental', 'vision', 'vaccination', 'immunization', 'nurse',
        'covid', 'pandemic', 'mask', 'quarantine',
        'tobacco', 'vaping', 'substance abuse'
    ],
    'Equity & Access': [
        'equity', 'access', 'inclusion', 'diversity', 'anti-racist',
        'title i', 'title iii', 'homeless', 'foster', 'unaccompanied',
        'immigrant', 'undocumented', 'lgbtq', 'gender identity',
        'disability', 'special education', 'iep', 'ada',
        'indigenous', 'native american', 'african american',
        'sanctuary', 'safe zone', 'respectful treatment',
        'land acknowledgement'
    ],
    'Facilities & Construction': [
        'facility', 'facilities', 'construction', 'renovation',
        'building', 'campus', 'school site', 'portable', 'modernization',
        'green', 'solar', 'sustainability', 'clean energy',
        'playground', 'field', 'gymnasium', 'auditorium', 'library'
    ],
    'Resolutions & Recognitions': [
        'recognition', 'commendation', 'proclamation',
        'memorial', 'celebration', 'heritage month', 'history month',
        'awareness', 'honoring', 'legacy', 'day of',
        'cesar chavez', 'mlk', 'women', 'black history',
        'pride', 'hispanic', 'aapi', 'awareness month',
        'digital citizenship week', 'runaway'
    ],
    'Student Programs': [
        'student program', 'after school', 'afterschool', 'sports',
        'athletics', 'extracurricular', 'arts program', 'music program',
        'stem program', 'summer school', 'tutoring', 'mentoring',
        'internship', 'career', 'work experience', 'esports'
    ],
    'Technology & Innovation': [
        'technology', 'computer', 'laptop', 'chromebook', 'device',
        'internet', 'wifi', 'broadband', 'digital', 'online',
        'distance learning', 'remote', 'virtual', 'software',
        'cybersecurity', 'data privacy', 'digital citizenship',
        'artificial intelligence'
    ],
    'Labor & Employment': [
        'labor', 'employment', 'utla', 'seiu', 'teamster', 'union',
        'collective bargaining', 'negotiation', 'strike', 'wage',
        'teacher', 'classified', 'hiring', 'recruitment', 'retention',
        'layoff', 'reduction in force', 'staffing'
    ],
    'Governance & Policy': [
        'governance', 'policy', 'board rule', 'bylaws', 'waiver',
        'compliance', 'inspector general', 'ethics',
        'transparency', 'accountability', 'oversight', 'legislation',
        'advocacy', 'federal', 'senate bill', 'assembly bill',
        'project 2025', 'minutes for board approval'
    ],
    'Transportation': [
        'transportation', 'bus', 'school bus', 'transit', 'routing',
        'fleet', 'vehicle', 'commute', 'safe passage'
    ],
}


# ============================================================================
# DATA INGESTION
# ============================================================================

def discover_csv_files():
    """Find all Votes CSV files in the LAUSD directory."""
    files = []
    for path in sorted(glob.glob(os.path.join(LAUSD_DIR, 'LAUSD-*-Votes.csv'))):
        basename = os.path.basename(path)
        # Quarterly: LAUSD-YYYY-QN-Votes.csv
        m = re.match(r'LAUSD-(\d{4})-Q(\d)-Votes\.csv', basename)
        if m:
            files.append({
                'path': path,
                'year': int(m.group(1)),
                'quarter': int(m.group(2)),
                'format': 'filemaker',
            })
            continue
        # Annual: LAUSD-YYYY-Votes.csv
        m = re.match(r'LAUSD-(\d{4})-Votes\.csv', basename)
        if m:
            files.append({
                'path': path,
                'year': int(m.group(1)),
                'quarter': None,
                'format': 'legistar',
            })
    return files


def detect_member_columns(fieldnames):
    """Identify which CSV columns are board member names."""
    members = []
    for col in fieldnames:
        if col not in FIXED_COLUMNS and col not in EXCLUDE_MEMBERS and col.strip():
            canonical = NAME_CORRECTIONS.get(col, col)
            members.append((col, canonical))
    return members


def load_csv_file(file_info):
    """Load a single CSV file and return normalized vote records."""
    records = []
    path = file_info['path']

    with open(path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        member_columns = detect_member_columns(reader.fieldnames)

        for row in reader:
            # Skip rows without a title or event_date
            title = (row.get('title') or '').strip()
            event_date = (row.get('event_date') or '').strip()
            if not event_date:
                continue

            # Collect member votes
            member_votes = {}
            has_any_vote = False
            for csv_col, canonical_name in member_columns:
                raw_vote = (row.get(csv_col) or '').strip()
                if raw_vote:
                    choice = VOTE_CHOICE_MAP.get(raw_vote)
                    if choice:
                        member_votes[canonical_name] = choice
                        has_any_vote = True

            # Determine if this is a voted item
            passed_val = (row.get('passed') or '').strip()
            roll_call = (row.get('roll_call_flag') or '').strip()
            is_voted = (passed_val in ('0', '1') or roll_call == '1' or has_any_vote)

            # Skip non-voted items (Roll Call, Reports, etc.) unless they have votes
            if not is_voted and not title:
                continue

            # Normalize outcome
            action = (row.get('action') or '').strip()
            outcome = normalize_outcome(passed_val, action)

            # Parse agenda sequence
            try:
                agenda_seq = int(row.get('agenda_sequence') or 0)
            except (ValueError, TypeError):
                agenda_seq = 0

            record = {
                'event_id': (row.get('event_id') or '').strip(),
                'event_date': event_date,
                'event_time': (row.get('event_time') or '').strip(),
                'event_location': (row.get('event_location') or '').strip(),
                'event_item_id': (row.get('event_item_id') or '').strip(),
                'agenda_number': (row.get('agenda_number') or '').strip(),
                'agenda_sequence': agenda_seq,
                'matter_file': (row.get('matter_file') or '').strip(),
                'title': title,
                'action': action,
                'passed': passed_val,
                'outcome': outcome,
                'vote_type': (row.get('vote_type') or '').strip(),
                'consent': (row.get('consent') or '').strip(),
                'tally': (row.get('tally') or '').strip(),
                'mover': (row.get('mover') or '').strip(),
                'seconder': (row.get('seconder') or '').strip(),
                'roll_call_flag': roll_call,
                'agenda_link': (row.get('agenda_link') or '').strip() or None,
                'minutes_link': (row.get('minutes_link') or '').strip() or None,
                'video_link': (row.get('video_link') or '').strip() or None,
                'fulltext': (row.get('Agenda_item_fulltext') or '').strip(),
                'sponsor': (row.get('sponsor') or '').strip(),
                'member_votes': member_votes,
                'is_voted': is_voted,
                'source_year': file_info['year'],
                'source_quarter': file_info['quarter'],
            }
            records.append(record)

    return records


def normalize_outcome(passed_val, action):
    """Determine vote outcome from passed field and action text."""
    if passed_val == '1':
        return 'PASS'
    if passed_val == '0':
        # Check action for special cases
        action_lower = action.lower()
        if 'adopted' in action_lower or 'approved' in action_lower:
            return 'PASS'
        return 'FAIL'

    # No passed value - check action
    if action:
        # Try exact match first
        if action in ACTION_OUTCOME_MAP:
            return ACTION_OUTCOME_MAP[action]
        # Try case-insensitive partial match
        action_lower = action.lower()
        if 'adopted' in action_lower or 'approved' in action_lower:
            return 'PASS'
        if 'failed' in action_lower or 'defeated' in action_lower:
            return 'FAIL'
        if 'tabled' in action_lower or 'postponed' in action_lower:
            return 'TABLED'
        if 'withdrawn' in action_lower:
            return 'WITHDRAWN'
        if 'continued' in action_lower:
            return 'CONTINUED'
        if 'removed' in action_lower:
            return 'REMOVED'

    return 'FLAG'


# ============================================================================
# TOPIC CLASSIFICATION
# ============================================================================

def classify_topics(title, fulltext='', max_topics=3):
    """Assign 0-3 topics based on keyword matching."""
    text = (title + ' ' + (fulltext or '')[:500]).lower()
    scores = {}
    for topic, keywords in TOPIC_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in text)
        if score > 0:
            scores[topic] = score

    sorted_topics = sorted(scores.items(), key=lambda x: -x[1])
    result = [t[0] for t in sorted_topics[:max_topics]]
    return result if result else ['General']


# ============================================================================
# DATA PROCESSING
# ============================================================================

def build_member_registry(all_records):
    """Build canonical member list from all vote records."""
    member_dates = defaultdict(lambda: {'first': None, 'last': None, 'files': set()})

    for rec in all_records:
        for name, choice in rec['member_votes'].items():
            info = member_dates[name]
            date = rec['event_date']
            source_key = (rec['source_year'], rec['source_quarter'])
            info['files'].add(source_key)
            if info['first'] is None or date < info['first']:
                info['first'] = date
            if info['last'] is None or date > info['last']:
                info['last'] = date

    # Find the most recent source file
    all_source_keys = set()
    for rec in all_records:
        all_source_keys.add((rec['source_year'], rec['source_quarter']))
    latest_source = max(all_source_keys)

    # Build member list sorted by last name
    members = []
    for name in sorted(member_dates.keys(), key=lambda n: n.split()[-1]):
        info = member_dates[name]
        is_current = latest_source in info['files']

        # Generate short name (last name, handling multi-word)
        parts = name.split()
        if len(parts) >= 3 and parts[-1] in ('III', 'Jr.', 'Sr.', 'II', 'IV'):
            short_name = parts[-2] + ' ' + parts[-1]
        elif name == 'Tanya Ortiz Franklin':
            short_name = 'Ortiz Franklin'
        elif name == 'Sherlett H. Newbill':
            short_name = 'Newbill'
        else:
            short_name = parts[-1]

        members.append({
            'full_name': name,
            'short_name': short_name,
            'position': 'Board Member',
            'start_date': info['first'],
            'end_date': None if is_current else info['last'],
            'is_current': is_current,
        })

    # Assign sequential IDs
    for i, member in enumerate(members, 1):
        member['id'] = i

    return members


def build_meetings(all_records):
    """Group records into meetings, merging same-day events."""
    # First group by event_id
    event_map = defaultdict(lambda: {
        'records': [],
        'date': None,
        'event_id': None,
        'agenda_link': None,
        'minutes_link': None,
        'video_link': None,
    })

    for rec in all_records:
        key = rec['event_id'] or rec['event_date']
        info = event_map[key]
        info['records'].append(rec)
        info['date'] = rec['event_date']
        info['event_id'] = rec['event_id']
        if rec['agenda_link'] and not info['agenda_link']:
            info['agenda_link'] = rec['agenda_link']
        if rec['minutes_link'] and not info['minutes_link']:
            info['minutes_link'] = rec['minutes_link']
        if rec['video_link'] and not info['video_link']:
            info['video_link'] = rec['video_link']

    # Merge events that fall on the same date into a single meeting
    date_map = defaultdict(list)
    for info in event_map.values():
        date_map[info['date']].append(info)

    merged = []
    for date, events in date_map.items():
        if len(events) == 1:
            merged.append(events[0])
        else:
            # Merge multiple same-day events into one
            combined = {
                'records': [],
                'date': date,
                'event_id': events[0]['event_id'],
                'agenda_link': None,
                'minutes_link': None,
                'video_link': None,
            }
            for ev in events:
                combined['records'].extend(ev['records'])
                if ev['agenda_link'] and not combined['agenda_link']:
                    combined['agenda_link'] = ev['agenda_link']
                if ev['minutes_link'] and not combined['minutes_link']:
                    combined['minutes_link'] = ev['minutes_link']
                if ev['video_link'] and not combined['video_link']:
                    combined['video_link'] = ev['video_link']
            merged.append(combined)

    # Sort meetings chronologically and assign IDs
    sorted_meetings = sorted(merged, key=lambda m: m['date'])
    meetings = []
    for i, info in enumerate(sorted_meetings, 1):
        voted_records = [r for r in info['records'] if r['is_voted']]
        meetings.append({
            'id': i,
            'event_id': info['event_id'],
            'meeting_date': info['date'],
            'meeting_type': 'regular',
            'legistar_url': None,
            'agenda_url': info['agenda_link'],
            'minutes_url': info['minutes_link'],
            'video_url': info['video_link'],
            'agenda_item_count': len(info['records']),
            'vote_count': len(voted_records),
            'non_voted_count': len(info['records']) - len(voted_records),
            'first_reading_count': 0,
            'records': info['records'],
        })

    return meetings


def build_votes(all_records, meetings, members):
    """Process all vote records and assign IDs."""
    # Create meeting lookup by event_id and date
    meeting_lookup = {}
    for meeting in meetings:
        meeting_lookup[meeting['event_id']] = meeting['id']
        meeting_lookup[meeting['meeting_date']] = meeting['id']
        # Register all event_ids from merged records
        for rec in meeting.get('records', []):
            if rec['event_id']:
                meeting_lookup[rec['event_id']] = meeting['id']

    # Create member lookup by name
    member_lookup = {m['full_name']: m['id'] for m in members}

    # Filter to voted items only, sort by date then sequence
    voted_records = [r for r in all_records if r['is_voted']]
    voted_records.sort(key=lambda r: (r['event_date'], r['agenda_sequence']))

    votes = []
    for i, rec in enumerate(voted_records, 1):
        # Compute tallies from member votes
        ayes = sum(1 for v in rec['member_votes'].values() if v == 'AYE')
        noes = sum(1 for v in rec['member_votes'].values() if v == 'NAY')
        abstain = sum(1 for v in rec['member_votes'].values() if v == 'ABSTAIN')
        absent = sum(1 for v in rec['member_votes'].values() if v == 'ABSENT')

        # Determine section
        section = 'CONSENT' if rec['consent'] == '1' else 'GENERAL'

        # Determine meeting ID
        meeting_id = meeting_lookup.get(rec['event_id']) or meeting_lookup.get(rec['event_date'])

        # Classify topics
        topics = classify_topics(rec['title'], rec['fulltext'])

        # Build member vote records
        member_vote_records = []
        for name, choice in sorted(rec['member_votes'].items()):
            mid = member_lookup.get(name)
            if mid:
                member_vote_records.append({
                    'member_id': mid,
                    'full_name': name,
                    'vote_choice': choice,
                })

        vote = {
            'id': i,
            'outcome': rec['outcome'],
            'ayes': ayes,
            'noes': noes,
            'abstain': abstain,
            'absent': absent,
            'item_number': rec['agenda_number'] or str(i),
            'section': section,
            'title': rec['title'],
            'description': rec['fulltext'],
            'meeting_date': rec['event_date'],
            'meeting_type': 'regular',
            'meeting_id': meeting_id,
            'topics': topics,
            'member_votes': member_vote_records,
            'event_item_id': rec['event_item_id'],
        }
        votes.append(vote)

    return votes


def compute_member_stats(member, votes):
    """Compute per-member statistics."""
    total = 0
    aye_count = nay_count = abstain_count = absent_count = recusal_count = 0
    votes_on_losing_side = 0
    votes_on_winning_side = 0
    close_vote_dissents = 0
    valid_votes = 0

    member_vote_history = []
    member_id = member['id']

    for vote in votes:
        # Find this member's vote
        member_choice = None
        for mv in vote['member_votes']:
            if mv['member_id'] == member_id:
                member_choice = mv['vote_choice']
                break

        if member_choice is None:
            continue

        total += 1

        if member_choice == 'AYE':
            aye_count += 1
        elif member_choice == 'NAY':
            nay_count += 1
        elif member_choice == 'ABSTAIN':
            abstain_count += 1
        elif member_choice == 'ABSENT':
            absent_count += 1
        elif member_choice == 'RECUSAL':
            recusal_count += 1

        # Dissent calculation
        outcome = vote['outcome']
        if outcome in ('PASS', 'FAIL') and member_choice in ('AYE', 'NAY'):
            valid_votes += 1
            is_dissent = (
                (outcome == 'PASS' and member_choice == 'NAY') or
                (outcome == 'FAIL' and member_choice == 'AYE')
            )
            if is_dissent:
                votes_on_losing_side += 1
                margin = abs(vote['ayes'] - vote['noes'])
                if margin <= 2:
                    close_vote_dissents += 1
            else:
                votes_on_winning_side += 1

        # Build vote history entry
        member_vote_history.append({
            'vote_id': vote['id'],
            'meeting_date': vote['meeting_date'],
            'item_number': vote['item_number'],
            'title': vote['title'],
            'vote_choice': member_choice,
            'outcome': outcome,
            'topics': vote['topics'],
            'meeting_type': vote['meeting_type'],
        })

    stats = {
        'total_votes': total,
        'aye_count': aye_count,
        'nay_count': nay_count,
        'abstain_count': abstain_count,
        'absent_count': absent_count,
        'recusal_count': recusal_count,
        'aye_percentage': round(aye_count / total * 100, 1) if total else 0,
        'participation_rate': round(
            (total - absent_count - abstain_count) / total * 100, 1
        ) if total else 0,
        'dissent_rate': round(
            votes_on_losing_side / valid_votes * 100, 1
        ) if valid_votes else 0,
        'votes_on_losing_side': votes_on_losing_side,
        'votes_on_winning_side': votes_on_winning_side,
        'close_vote_dissents': close_vote_dissents,
    }

    return stats, member_vote_history


def compute_alignment(members, votes):
    """Compute pairwise voting alignment between all member pairs."""
    # Build lookup: vote_id -> {member_id: choice}
    vote_choices = {}
    for vote in votes:
        choices = {}
        for mv in vote['member_votes']:
            choices[mv['member_id']] = mv['vote_choice']
        vote_choices[vote['id']] = choices

    pairs = []
    for i, m1 in enumerate(members):
        for m2 in members[i + 1:]:
            shared = 0
            agreements = 0
            for vote_id, choices in vote_choices.items():
                v1 = choices.get(m1['id'])
                v2 = choices.get(m2['id'])
                # Both must have participated (AYE or NAY)
                if v1 in ('AYE', 'NAY') and v2 in ('AYE', 'NAY'):
                    shared += 1
                    if v1 == v2:
                        agreements += 1

            if shared >= 10:  # Minimum threshold
                pairs.append({
                    'member1': m1['short_name'],
                    'member2': m2['short_name'],
                    'shared_votes': shared,
                    'agreements': agreements,
                    'agreement_rate': round(agreements / shared * 100, 1),
                })

    pairs.sort(key=lambda p: p['agreement_rate'], reverse=True)

    return {
        'success': True,
        'members': [m['short_name'] for m in members],
        'alignment_pairs': pairs,
        'most_aligned': pairs[:3] if pairs else [],
        'least_aligned': sorted(pairs, key=lambda p: p['agreement_rate'])[:3] if pairs else [],
    }


# ============================================================================
# JSON GENERATION
# ============================================================================

def write_json(filepath, data):
    """Write JSON file with proper formatting."""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, separators=(',', ':'))


def generate_stats_json(votes, meetings, members):
    """Generate stats.json."""
    total_votes = len(votes)
    pass_count = sum(1 for v in votes if v['outcome'] == 'PASS')
    unanimous_count = sum(1 for v in votes if v['noes'] == 0 and v['abstain'] == 0)

    dates = [v['meeting_date'] for v in votes if v['meeting_date']]
    date_start = min(dates) if dates else ''
    date_end = max(dates) if dates else ''

    total_agenda_items = sum(m['agenda_item_count'] for m in meetings)

    return {
        'success': True,
        'stats': {
            'total_meetings': len(meetings),
            'total_votes': total_votes,
            'total_council_members': len(members),
            'total_agenda_items': total_agenda_items,
            'total_non_voted_items': total_agenda_items - total_votes,
            'first_readings': 0,
            'pass_rate': round(pass_count / total_votes * 100, 1) if total_votes else 0,
            'unanimous_rate': round(unanimous_count / total_votes * 100, 1) if total_votes else 0,
            'date_range': {
                'start': date_start,
                'end': date_end,
            },
        },
    }


def generate_council_json(members, member_stats):
    """Generate council.json."""
    member_list = []
    for m in members:
        member_list.append({
            'id': m['id'],
            'full_name': m['full_name'],
            'short_name': m['short_name'],
            'position': m['position'],
            'start_date': m['start_date'],
            'end_date': m['end_date'],
            'is_current': m['is_current'],
            'stats': member_stats[m['id']],
        })
    return {'success': True, 'members': member_list}


def generate_council_member_json(member, stats, vote_history):
    """Generate council/{id}.json."""
    return {
        'success': True,
        'member': {
            'id': member['id'],
            'full_name': member['full_name'],
            'short_name': member['short_name'],
            'position': member['position'],
            'start_date': member['start_date'],
            'end_date': member['end_date'],
            'is_current': member['is_current'],
            'stats': stats,
            'recent_votes': sorted(vote_history, key=lambda v: v['meeting_date'], reverse=True),
        },
    }


def generate_meetings_json(meetings):
    """Generate meetings.json."""
    years = sorted(set(
        int(m['meeting_date'][:4]) for m in meetings if m['meeting_date']
    ), reverse=True)

    meeting_list = []
    for m in sorted(meetings, key=lambda x: x['meeting_date'], reverse=True):
        meeting_list.append({
            'id': m['id'],
            'event_id': m['event_id'],
            'meeting_date': m['meeting_date'],
            'meeting_type': m['meeting_type'],
            'legistar_url': m['legistar_url'],
            'agenda_url': m['agenda_url'],
            'minutes_url': m['minutes_url'],
            'video_url': m['video_url'],
            'agenda_item_count': m['agenda_item_count'],
            'vote_count': m['vote_count'],
            'non_voted_count': m['non_voted_count'],
            'first_reading_count': m['first_reading_count'],
        })

    return {'success': True, 'meetings': meeting_list, 'available_years': years}


def generate_meeting_detail_json(meeting, votes):
    """Generate meetings/{id}.json."""
    # Find votes for this meeting
    meeting_votes = {v['id']: v for v in votes if v['meeting_id'] == meeting['id']}

    agenda_items = []
    for rec in sorted(meeting['records'], key=lambda r: r['agenda_sequence']):
        if rec['is_voted']:
            # Find the corresponding vote
            vote = None
            for v in meeting_votes.values():
                if v['event_item_id'] == rec['event_item_id']:
                    vote = v
                    break

            agenda_items.append({
                'agenda_sequence': rec['agenda_sequence'],
                'item_type': 'voted',
                'item_number': rec['agenda_number'] or '',
                'title': rec['title'],
                'section': 'CONSENT' if rec['consent'] == '1' else 'GENERAL',
                'matter_file': rec['matter_file'] or None,
                'matter_type': 'Resolution',
                'topics': vote['topics'] if vote else ['General'],
                'vote': {
                    'id': vote['id'] if vote else None,
                    'outcome': rec['outcome'],
                    'ayes': vote['ayes'] if vote else 0,
                    'noes': vote['noes'] if vote else 0,
                    'abstain': vote['abstain'] if vote else 0,
                    'absent': vote['absent'] if vote else 0,
                } if vote else None,
            })
        else:
            agenda_items.append({
                'agenda_sequence': rec['agenda_sequence'],
                'item_type': 'non_voted',
                'category': 'other',
                'importance': 'low',
                'display_type': 'procedural',
                'title': rec['title'],
                'matter_file': rec['matter_file'] or None,
                'matter_type': None,
                'action': rec['action'] or None,
                'description': None,
                'topics': None,
                'vote': None,
            })

    return {
        'success': True,
        'meeting': {
            'id': meeting['id'],
            'event_id': meeting['event_id'],
            'meeting_date': meeting['meeting_date'],
            'meeting_type': meeting['meeting_type'],
            'legistar_url': meeting['legistar_url'],
            'agenda_url': meeting['agenda_url'],
            'minutes_url': meeting['minutes_url'],
            'video_url': meeting['video_url'],
            'vote_count': meeting['vote_count'],
            'non_voted_count': meeting['non_voted_count'],
            'first_reading_count': meeting['first_reading_count'],
            'agenda_item_count': meeting['agenda_item_count'],
            'agenda_items': agenda_items,
        },
    }


def generate_votes_json(votes):
    """Generate votes.json (all votes, no description)."""
    vote_list = []
    for v in sorted(votes, key=lambda x: x['meeting_date'], reverse=True):
        vote_list.append({
            'id': v['id'],
            'outcome': v['outcome'],
            'ayes': v['ayes'],
            'noes': v['noes'],
            'abstain': v['abstain'],
            'absent': v['absent'],
            'item_number': v['item_number'],
            'section': v['section'],
            'title': v['title'],
            'meeting_date': v['meeting_date'],
            'meeting_type': v['meeting_type'],
            'topics': v['topics'],
        })
    return {'success': True, 'votes': vote_list}


def generate_vote_detail_json(vote):
    """Generate votes/{id}.json."""
    return {
        'success': True,
        'vote': {
            'id': vote['id'],
            'item_number': vote['item_number'],
            'title': vote['title'],
            'description': vote['description'] or '',
            'outcome': vote['outcome'],
            'ayes': vote['ayes'],
            'noes': vote['noes'],
            'abstain': vote['abstain'],
            'absent': vote['absent'],
            'meeting_id': vote['meeting_id'],
            'meeting_date': vote['meeting_date'],
            'meeting_type': vote['meeting_type'],
            'member_votes': vote['member_votes'],
            'topics': vote['topics'],
        },
    }


# ============================================================================
# VALIDATION
# ============================================================================

def validate_data(votes, meetings, members):
    """Run integrity checks on generated data."""
    errors = []

    # Check meeting ID references
    meeting_ids = {m['id'] for m in meetings}
    for v in votes:
        if v['meeting_id'] and v['meeting_id'] not in meeting_ids:
            errors.append(f"Vote {v['id']} references unknown meeting {v['meeting_id']}")

    # Check member ID references
    member_ids = {m['id'] for m in members}
    for v in votes:
        for mv in v['member_votes']:
            if mv['member_id'] not in member_ids:
                errors.append(f"Vote {v['id']} references unknown member {mv['member_id']}")

    # Check no duplicate IDs
    vote_ids = [v['id'] for v in votes]
    if len(vote_ids) != len(set(vote_ids)):
        errors.append("Duplicate vote IDs found")

    meeting_id_list = [m['id'] for m in meetings]
    if len(meeting_id_list) != len(set(meeting_id_list)):
        errors.append("Duplicate meeting IDs found")

    return errors


# ============================================================================
# MAIN
# ============================================================================

def main():
    print('CityVotes LAUSD - Data Generation')
    print('=' * 50)

    # Phase 1: Discover and load CSV files
    print('\n1. Discovering CSV files...')
    csv_files = discover_csv_files()
    print(f'   Found {len(csv_files)} CSV files:')
    for f in csv_files:
        label = f'Q{f["quarter"]}' if f['quarter'] else 'Annual'
        print(f'   - {f["year"]} {label} ({f["format"]})')

    print('\n2. Loading data...')
    all_records = []
    for f in csv_files:
        records = load_csv_file(f)
        all_records.extend(records)
        label = f'Q{f["quarter"]}' if f['quarter'] else 'Annual'
        print(f'   {f["year"]} {label}: {len(records)} records')
    print(f'   Total: {len(all_records)} records')

    # Phase 2: Build member registry
    print('\n3. Building member registry...')
    members = build_member_registry(all_records)
    print(f'   Found {len(members)} board members:')
    for m in members:
        status = 'Current' if m['is_current'] else 'Former'
        print(f'   {m["id"]:2d}. {m["full_name"]:<25s} ({status}, {m["start_date"]} - {m["end_date"] or "present"})')

    # Phase 3: Build meetings
    print('\n4. Building meetings...')
    meetings = build_meetings(all_records)
    print(f'   {len(meetings)} meetings')

    # Phase 4: Build votes
    print('\n5. Processing votes...')
    votes = build_votes(all_records, meetings, members)
    print(f'   {len(votes)} voted items')

    # Phase 5: Compute member stats
    print('\n6. Computing member statistics...')
    member_stats = {}
    member_histories = {}
    for member in members:
        stats, history = compute_member_stats(member, votes)
        member_stats[member['id']] = stats
        member_histories[member['id']] = history
        print(f'   {member["full_name"]}: {stats["total_votes"]} votes, '
              f'{stats["aye_percentage"]}% aye, {stats["dissent_rate"]}% dissent')

    # Phase 6: Compute alignment
    print('\n7. Computing voting alignment...')
    alignment = compute_alignment(members, votes)
    print(f'   {len(alignment["alignment_pairs"])} pairs')
    if alignment['most_aligned']:
        top = alignment['most_aligned'][0]
        print(f'   Most aligned: {top["member1"]} & {top["member2"]} ({top["agreement_rate"]}%)')
    if alignment['least_aligned']:
        bottom = alignment['least_aligned'][0]
        print(f'   Least aligned: {bottom["member1"]} & {bottom["member2"]} ({bottom["agreement_rate"]}%)')

    # Phase 7: Validate
    print('\n8. Validating data integrity...')
    errors = validate_data(votes, meetings, members)
    if errors:
        for err in errors:
            print(f'   ERROR: {err}')
    else:
        print('   All checks passed!')

    # Phase 8: Generate JSON files
    print('\n9. Generating JSON files...')

    # Clean output directory
    if os.path.exists(OUTPUT_DIR):
        import shutil
        # Remove only generated subdirs, preserve README files
        for subdir in ['council', 'meetings', 'votes']:
            path = os.path.join(OUTPUT_DIR, subdir)
            if os.path.exists(path):
                shutil.rmtree(path)

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # stats.json
    stats = generate_stats_json(votes, meetings, members)
    write_json(os.path.join(OUTPUT_DIR, 'stats.json'), stats)
    print('   stats.json')

    # council.json
    council = generate_council_json(members, member_stats)
    write_json(os.path.join(OUTPUT_DIR, 'council.json'), council)
    print('   council.json')

    # council/{id}.json
    for member in members:
        data = generate_council_member_json(
            member, member_stats[member['id']], member_histories[member['id']]
        )
        write_json(os.path.join(OUTPUT_DIR, 'council', f'{member["id"]}.json'), data)
    print(f'   council/{{1..{len(members)}}}.json')

    # meetings.json
    meetings_data = generate_meetings_json(meetings)
    write_json(os.path.join(OUTPUT_DIR, 'meetings.json'), meetings_data)
    print('   meetings.json')

    # meetings/{id}.json
    for meeting in meetings:
        data = generate_meeting_detail_json(meeting, votes)
        write_json(os.path.join(OUTPUT_DIR, 'meetings', f'{meeting["id"]}.json'), data)
    print(f'   meetings/{{1..{len(meetings)}}}.json')

    # votes.json
    votes_data = generate_votes_json(votes)
    write_json(os.path.join(OUTPUT_DIR, 'votes.json'), votes_data)
    print('   votes.json')

    # votes-index.json
    years = sorted(set(int(v['meeting_date'][:4]) for v in votes), reverse=True)
    write_json(os.path.join(OUTPUT_DIR, 'votes-index.json'), {
        'success': True,
        'available_years': years,
    })
    print('   votes-index.json')

    # votes-{year}.json
    for year in years:
        year_votes = [v for v in votes if v['meeting_date'].startswith(str(year))]
        year_data = generate_votes_json(year_votes)
        write_json(os.path.join(OUTPUT_DIR, f'votes-{year}.json'), year_data)
    print(f'   votes-{{year}}.json for {years}')

    # votes/{id}.json
    for vote in votes:
        data = generate_vote_detail_json(vote)
        write_json(os.path.join(OUTPUT_DIR, 'votes', f'{vote["id"]}.json'), data)
    print(f'   votes/{{1..{len(votes)}}}.json')

    # alignment.json
    write_json(os.path.join(OUTPUT_DIR, 'alignment.json'), alignment)
    print('   alignment.json')

    # agenda-items.json - non-voted items for agenda search
    non_voted_items = []
    for meeting in meetings:
        for rec in meeting['records']:
            if not rec['is_voted'] and rec['title']:
                desc = rec['fulltext'][:200] if rec.get('fulltext') else None
                topics = classify_topics(rec['title'], rec.get('fulltext', ''))
                non_voted_items.append({
                    'event_item_id': rec['event_item_id'] or None,
                    'meeting_date': rec['event_date'],
                    'meeting_id': meeting['id'],
                    'agenda_sequence': rec['agenda_sequence'],
                    'title': rec['title'],
                    'matter_file': rec['matter_file'] or None,
                    'matter_type': None,
                    'action': rec['action'] or None,
                    'category': 'other',
                    'topics': topics if topics != ['General'] else [],
                    'description_preview': desc,
                })
    write_json(os.path.join(OUTPUT_DIR, 'agenda-items.json'), {
        'success': True,
        'agenda_items': non_voted_items,
    })
    print(f'   agenda-items.json ({len(non_voted_items)} items)')

    # Summary
    print('\n' + '=' * 50)
    print('GENERATION COMPLETE')
    print(f'  Members:  {len(members)}')
    print(f'  Meetings: {len(meetings)}')
    print(f'  Votes:    {len(votes)}')
    print(f'  Years:    {min(years)}-{max(years)}')
    print(f'  Output:   {OUTPUT_DIR}')

    # Count total files
    file_count = 0
    for root, dirs, files in os.walk(OUTPUT_DIR):
        file_count += len([f for f in files if f.endswith('.json')])
    print(f'  Files:    {file_count} JSON files')


if __name__ == '__main__':
    main()
