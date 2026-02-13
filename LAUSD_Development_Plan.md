# CityVotes LAUSD - Site Development Plan

## Context

The CityVotes template (`template/`) is a production-ready static civic transparency website (Bootstrap 5, vanilla JS, static JSON data). The `LAUSD/` folder contains 5+ years of LAUSD Board of Education voting data (Q1 2020 through 2025) in CSV/JSON format from two sources: FileMaker Resolutions DB and Legistar API. The goal is to build a Python data generation script, customize the template for LAUSD, and produce a deploy-ready site.

---

## Step 1: Copy Template to Site Root

Create a `site/` directory from the template as the deploy target.

```
cp -r template/ site/
```

**Final structure:**
```
CityVotes_LAUSD/
├── LAUSD/                    # Source data (unchanged)
├── template/                 # Original template (unchanged)
├── generate_site_data.py     # NEW: data generation script
└── site/                     # Deploy target
    ├── index.html ... (all 10 HTML pages)
    ├── css/theme.css
    ├── js/api.js
    ├── vercel.json
    └── data/                 # Generated JSON files
```

---

## Step 2: Customize Template for LAUSD

### 2.1 Text Replacements (all 10 HTML files in `site/`)

| Find | Replace |
|------|---------|
| `{CityName}` | `LAUSD` |
| `Council Members` (headings/nav labels) | `Board Members` |
| `Council Member` (singular) | `Board Member` |
| `Council` (nav link text only) | `Board` |
| `City Council` (descriptions) | `Board of Education` |

**Files:** `site/index.html`, `council.html`, `council-member.html`, `meetings.html`, `meeting-detail.html`, `votes.html`, `vote-detail.html`, `agenda-search.html`, `about.html`, `contact.html`

### 2.2 Theme Colors (`site/css/theme.css`)

Update the 5 CSS custom properties to LAUSD navy/gold:

```css
--city-primary: #003366;
--city-primary-light: #004c99;
--city-primary-dark: #002244;
--city-accent: #FFB81C;
--city-accent-light: #FFD366;
```

### 2.3 About Page Content (`site/about.html`)

Update placeholders with LAUSD-specific info (date range, meeting schedule, board info).

---

## Step 3: Build `generate_site_data.py`

Single Python script (stdlib + csv/json only, no pandas dependency) that reads all LAUSD CSVs and generates the complete `site/data/` folder.

### 3.1 Data Ingestion

**Two CSV formats to handle:**

| Format | Files | Naming Pattern | Member Columns |
|--------|-------|---------------|----------------|
| FileMaker (2020-2024) | Quarterly | `LAUSD-{year}-Q{q}-Votes.csv` | End of header, after fixed columns |
| Legistar (2025) | Annual | `LAUSD-{year}-Votes.csv` | End of header, after fixed columns |

**Logic:**
1. Discover all `LAUSD-*-Votes.csv` files in `LAUSD/` directory
2. For each file, read the CSV header and identify board member columns by subtracting known fixed columns
3. Load corresponding `Voted-Items.csv` for vote metadata and `Persons.csv` for member info
4. Normalize into a unified internal structure: list of vote records, each with `member_votes` dict

**Key differences between formats:**
- FM has `source`, `notice_date`, `sponsor`, `cosponsors`, `student_votes` columns
- Legistar has `legislative_history` instead
- 2025 has name typo: `Scott Schmererelson` -> normalize to `Scott Schmerelson`
- Exclude `Superintendent` column (appears in 2022 Q2 as anomaly)

### 3.2 Member Resolution

Build canonical member registry from all CSV files:

| ID | Full Name | Short Name | Approx. Tenure |
|----|-----------|------------|----------------|
| 1 | Jackie Goldberg | Goldberg | 2020-2024 |
| 2 | Jerry Yang | Yang | 2025-present |
| 3 | Karla Griego | Griego | 2025-present |
| 4 | Kelly Gonez | Gonez | 2020-present |
| 5 | George McKenna III | McKenna III | 2020-2024 |
| 6 | Monica Garcia | Garcia | 2020-2022 |
| 7 | Nick Melvoin | Melvoin | 2020-present |
| 8 | Richard Vladovic | Vladovic | 2020 only |
| 9 | Rocio Rivas | Rivas | 2023-present |
| 10 | Scott Schmerelson | Schmerelson | 2020-present |
| 11 | Sherlett H. Newbill | Newbill | 2025-present |
| 12 | Tanya Ortiz Franklin | Ortiz Franklin | 2021-present |

- `start_date` / `end_date`: derived from earliest/latest vote date where member has a value
- `is_current`: true if member appears in the most recent data file
- `position`: `"Board Member"` for all (LAUSD has no mayor equivalent)
- IDs assigned alphabetically by last name

### 3.3 Meeting Construction

Group vote records by `event_id` (or `event_date` for FM data):
- Assign sequential integer IDs sorted chronologically
- `meeting_type`: default `"regular"` (LAUSD data doesn't distinguish; could parse from Granicus titles)
- Document links: `agenda_link`, `minutes_link`, `video_link` from CSV rows (take first non-null per meeting)
- Counts: `vote_count`, `agenda_item_count`, `non_voted_count`, `first_reading_count`

### 3.4 Vote Processing

For each voted item:
- `id`: Sequential integer sorted by date then `agenda_sequence`
- `item_number`: from `agenda_number` field
- `title`: from `title` field
- `description`: from `Agenda_item_fulltext` field (full text in vote detail, truncated elsewhere)
- `outcome`: Map from `passed` field and `action` field:
  - `passed=1` -> `PASS`
  - `passed=0` -> `FAIL`
  - null/empty + action contains "Adopted"/"Approved" -> `PASS`
  - Otherwise map specific actions (Tabled, Withdrawn, etc.)
- `section`: `consent=1` -> `CONSENT`, else `GENERAL`
- Vote choice normalization: `Yes->AYE`, `No->NAY`, `Absent->ABSENT`, `Abstain->ABSTAIN`, `Recused->RECUSAL`, `Excused->ABSENT`
- Compute tallies: count of each vote type from member columns

### 3.5 Topic Classification (LAUSD-Specific)

Replace generic city-council categories with education-relevant topics:

| Category | Key Terms |
|----------|-----------|
| Appointments | appoint, commission, superintendent, board officer |
| Budget & Finance | budget, fiscal, funding, bond, salary, lcff |
| Curriculum & Instruction | curriculum, instruction, academic, ethnic studies, literacy, graduation |
| Contracts & Agreements | contract, agreement, mou, vendor, procurement |
| Charter Schools | charter, renewal, petition, proposition 39 |
| Safety & Student Welfare | safety, security, mental health, counseling, discipline, bullying |
| Health & Nutrition | health, nutrition, meal, food, covid, vaccination |
| Equity & Access | equity, inclusion, diversity, title i, homeless, foster, special education, iep |
| Facilities & Construction | facility, construction, renovation, modernization, bond measure |
| Resolutions & Recognitions | resolution, recognition, commendation, heritage month, awareness |
| Student Programs | after school, sports, athletics, arts program, tutoring, mentoring |
| Technology & Innovation | technology, computer, laptop, digital, distance learning |
| Labor & Employment | labor, utla, seiu, union, collective bargaining, teacher, hiring |
| Governance & Policy | governance, policy, board rule, compliance, audit, legislation |
| Transportation | transportation, bus, school bus, transit |
| General | (fallback) |

Algorithm: keyword match on title + first 500 chars of fulltext, assign top 3 by match count.

### 3.6 Metrics Computation

All pre-computed per the formulas in `template/data/Template_ReadMe.md`:

- **Per-member stats**: aye_count, nay_count, abstain_count, absent_count, recusal_count, aye_percentage, participation_rate, dissent_rate, votes_on_losing_side, close_vote_dissents
- **Global stats**: total_votes, total_meetings, pass_rate, unanimous_rate, date_range
- **Alignment**: For each pair of members, count shared votes (both AYE or NAY, not absent/abstain/recusal) and agreements (same choice). Require minimum 10 shared votes to include pair. Top/bottom 3 for most/least aligned.

### 3.7 JSON Output

Generate all files into `site/data/`:

```
site/data/
├── stats.json
├── council.json
├── council/1.json ... council/12.json
├── meetings.json
├── meetings/1.json ... meetings/N.json
├── votes.json
├── votes-index.json
├── votes-2020.json ... votes-2025.json
├── votes/1.json ... votes/N.json
├── alignment.json
└── agenda-items.json
```

Every JSON file includes `"success": true` wrapper per template schema.

---

## Step 4: Data Integrity Validation

Built into `generate_site_data.py` as a verification pass after generation:

1. **Tally consistency**: Computed ayes/noes/absent/abstain match member vote counts
2. **ID referential integrity**: All vote.meeting_id exist in meetings, all member_votes.member_id exist in council
3. **No duplicate IDs** across meetings, votes, members
4. **Date range consistency**: stats.json date_range matches actual min/max meeting dates
5. **JSON parse check**: Every generated file is valid JSON
6. **Coverage report**: Print summary of members, meetings, votes per year

---

## Step 5: Verification & Testing

1. **Local preview**: `python3 -m http.server 8000` from `site/` directory
2. **Smoke test each page**:
   - Home: KPIs display, council grid renders, alignment cards show
   - Board: All 12 members appear, Current/Former badges correct
   - Board Member: Stats, voting history table, filters work
   - Meetings: List renders, document badges link correctly
   - Votes: Search/filter work, pagination works
   - Vote Detail: Member votes display, tallies match
3. **Spot-check known vote**: Verify Res-017-24/25 (Land Acknowledgement) shows 6 Ayes, 1 Absent (Tanya Ortiz Franklin absent), correct member votes
4. **Board transitions**: Monica Garcia/Richard Vladovic show as "Former", 2025 members show as "Current"
5. **Alignment**: Most/least aligned pairs are reasonable

---

## Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `generate_site_data.py` | **CREATE** | Master data generation script (~600-800 lines Python) |
| `site/` (entire directory) | **CREATE** | Copy of template/ |
| `site/css/theme.css` | **MODIFY** | Update 5 color variables for LAUSD |
| `site/*.html` (10 files) | **MODIFY** | Replace {CityName}, Council->Board terminology |
| `site/data/**/*.json` | **GENERATED** | All JSON data files (output of generate_site_data.py) |

**Key existing files referenced:**
- `template/data/Template_ReadMe.md` - JSON schema contract (the source of truth)
- `template/js/api.js` - Data loading paths (no changes needed)
- `LAUSD/LAUSD-*-Votes.csv` - Primary data source
- `LAUSD/LAUSD-*-Voted-Items.csv` - Vote metadata source
- `LAUSD/LAUSD-*-Persons.csv` - Member info source
- `LAUSD/process_lausd_quarter.py` - Reference for FM data processing patterns
