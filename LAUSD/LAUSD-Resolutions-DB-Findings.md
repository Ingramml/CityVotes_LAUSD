# LAUSD Resolutions Database - FileMaker WebDirect Findings

**Date:** 2026-02-12
**URL:** https://dnnlt3f.pcifmhosting.com/fmi/webd/RESOLUTIONS
**Platform:** FileMaker WebDirect (Vaadin-based, hosted by PCI FMHosting)

---

## Summary

LAUSD maintains a separate **Board Resolutions search database** powered by FileMaker WebDirect — distinct from the Legistar API already used for extraction. This database contains **2,742 resolutions** spanning from **May 2003 to January 2026** (22+ years).

This is a **supplementary data source** to the Legistar API. It contains resolution-specific data with full text and individual vote records that may complement or verify existing Legistar extractions.

---

## Technology Stack

| Property | Value |
|----------|-------|
| **Platform** | FileMaker WebDirect |
| **UI Framework** | Vaadin 8.18.0 (Java-based web framework) |
| **Hosting** | PCI FM Hosting (dnnlt3f.pcifmhosting.com) |
| **Communication** | WebSocket (Vaadin Push) + POST requests to `/fmi/webd/UIDL/` |
| **Authentication** | None (public access) |
| **Session Management** | Server-side (Vaadin stateful sessions) |
| **Database Title** | `RESOLUTIONS (17453 LA Unified School District (DNNLT3F))` |

### Key Technical Characteristics
- **No REST API** — all interaction happens via Vaadin's proprietary UIDL protocol (server-side state)
- **No direct URL per record** — navigation is session-based, not URL-based
- **Glass pane overlays** block standard Playwright clicks — must use `page.mouse.click()` with coordinates
- **Heartbeat mechanism** keeps session alive via `/fmi/webd/HEARTBEAT/`
- **PDF download** available per resolution (green PDF icon in list, "Download" button in detail)

---

## Data Model

### List View Fields

| Field | Description | Example |
|-------|-------------|---------|
| **Title** | Resolution title | "Celebration of Black History Month 2026 (Res-031-25/26)" |
| **Resolution #** | Resolution number | `031-25/26`, `034-25/26`, `Res-080-24/25` |
| **Action Date** | Date of board action | `1/27/2026` |
| **Show Details** | Button → detail view | — |
| **PDF** | Download resolution PDF | Green PDF icon |

### Detail View Fields

| Field | Description | Example |
|-------|-------------|---------|
| **Title** | Full resolution title | "Opposing the Unlawful Transfer of U.S. Department of Education Functions to Other Federal Agencies (Res-034-25/26)" |
| **Language** | Full resolution text (Whereas/Resolved clauses) | Complete multi-paragraph text |
| **Notice Date** | Date resolution was noticed | "Dec 16, 2025" |
| **Action Date** | Date of board action | "Jan 27, 2026" |
| **Action** | Outcome | "Adopted" |
| **Sponsor** | Primary sponsor (board member) | "Sherlett Newbill" |
| **Cosponsors** | List of cosponsoring members | (table of names) |
| **Moved by** | Member who moved the resolution | "Nick Melvoin" |
| **Second** | Member who seconded | "Rocio Rivas" |
| **Votes** | Individual board member votes | Name + Yes/No/Absent per member |
| **Student Votes** | Student board member advisory votes | Name + Yes/No |
| **Download** | PDF download button | — |

### Vote Values Observed
- **Yes** — Affirmative vote
- **Absent** — Member not present
- (Likely also: No, Abstain — not observed in sampled resolutions)

---

## Search Interface

### Basic Search (Step 1-2)
- **Title** — Keyword search (large text field)
- **Resolution #** — Number search
- **Search** button — Execute search
- **Show All** button — Display all 2,742 resolutions

### Advanced Search (Step 3)
- **Language** — Search within resolution text
- **Year** — Filter by year
- **Action Date** — Date filter (mm/dd/yyyy format)
- **Sponsor** — Filter by sponsoring member
- **Cosponsor** — Filter by cosponsor
- **Voter** — Filter by voter name
- **Student Voter** — Filter by student voter

---

## Sample Resolution Detail (2026)

**Title:** Opposing the Unlawful Transfer of U.S. Department of Education Functions to Other Federal Agencies (Res-034-25/26)

| Field | Value |
|-------|-------|
| Notice Date | Dec 16, 2025 |
| Action Date | Jan 27, 2026 |
| Action | Adopted |
| Sponsor | Sherlett Newbill |
| Moved by | Nick Melvoin |
| Second | Rocio Rivas |

**Cosponsors:** Scott Schmerelson, Rocio Rivas, Nick Melvoin, Karla Griego, Kelly Gonez, Tanya Ortiz Franklin, Jerry Yang

**Votes:**

| Member | Vote |
|--------|------|
| Kelly Gonez | Absent |
| Karla Griego | Yes |
| Nick Melvoin | Yes |
| Sherlett Newbill | Yes |
| Tanya Ortiz Franklin | Yes |
| Rocio Rivas | Yes |
| Scott Schmerelson | Yes |

**Student Votes:**

| Member | Vote |
|--------|------|
| Jerry Yang | Yes |

---

## Current Board Members (as of Jan 2026)

From the resolution detail data:
1. Kelly Gonez
2. Karla Griego
3. Nick Melvoin
4. Sherlett Newbill
5. Tanya Ortiz Franklin
6. Rocio Rivas
7. Scott Schmerelson

**Student Board Member:** Jerry Yang

---

## Data Volume

| Metric | Value |
|--------|-------|
| **Total Resolutions** | 2,742 |
| **Date Range** | May 2003 – January 2026 |
| **Resolution # Format** | `NNN-YY/YY` (e.g., `031-25/26`) or `Res-NNN-YY/YY` |

---

## Comparison with Existing Legistar Data

| Feature | FileMaker Resolutions DB | Legistar API |
|---------|--------------------------|--------------|
| **Scope** | Resolutions only | All matter types (resolutions, reports, appointments, etc.) |
| **Date Range** | 2003–2026 (22+ years) | Varies by query |
| **Full Text** | Built-in ("Language" field) | Requires Playwright scraping |
| **Vote Data** | Individual votes per resolution | Individual votes via `/EventItems/{id}/Votes` |
| **Sponsor/Cosponsor** | Explicit fields | Via `/matters/{id}/histories` (mover/seconder) |
| **Student Votes** | Separate section | May not be distinguished |
| **Resolution #** | Explicit field | `MatterFile` field |
| **PDF** | Direct download per resolution | Often null |
| **API Access** | No API — UI-only (FileMaker WebDirect) | REST API with OData |
| **Automation** | Difficult (Vaadin session-based UI) | Easy (standard HTTP requests) |

### Key Advantages of FileMaker DB
1. **Full resolution text built in** — no scraping needed
2. **Sponsor & Cosponsor explicitly listed** — clearer than Legistar's history endpoint
3. **Student votes separated** — distinct from regular board votes
4. **PDF download** — direct per-resolution PDF access
5. **22 years of history** — goes back to 2003
6. **Resolution numbers** — clearly formatted and searchable

### Key Limitations
1. **No API** — must scrape via Playwright (Vaadin UIDL protocol, not REST)
2. **Resolutions only** — does not include committee reports, appointments, etc.
3. **Session-based navigation** — no direct URLs per record
4. **Glass pane overlays** — standard Playwright click() fails; must use mouse coordinates
5. **Rate of extraction** — each resolution requires clicking Show Details and waiting for server round-trip

---

## Extraction Feasibility

### Approach: Playwright Automation
Since there's no API, extraction requires browser automation:

1. Navigate to the URL
2. Click "Show All" to load all 2,742 resolutions
3. Sort by Action Date (click column header via mouse coordinates)
4. For each resolution row, click "Show Details"
5. Extract all fields from the detail view via accessibility snapshot
6. Click "Next" to advance to the next resolution
7. Repeat until all 2020+ resolutions are captured

### Challenges
- **Vaadin WebSocket protocol** — server-side state means no bookmarkable URLs
- **Glass pane overlays** — require coordinate-based clicking, not selector-based
- **Session timeouts** — heartbeat needed to keep session alive
- **No pagination API** — must iterate through records one at a time via Next/Previous buttons
- **Estimated 2020+ resolutions** — roughly 800-1,000 resolutions (based on ~130/year average)

### Recommended Strategy
Given that the Legistar API already provides most of this data (votes, titles, dates, actions), this FileMaker database is best used as a **supplementary verification source** rather than a primary extraction target. Specific use cases:
1. **Cross-reference vote data** — verify Legistar votes against FileMaker records
2. **Fill in missing full text** — for the ~10% of items where Legistar scraping fails
3. **Capture sponsor/cosponsor data** — more explicit than Legistar's history endpoint
4. **Student vote extraction** — if needed as a separate data category
5. **PDF collection** — download resolution PDFs not available via Legistar

---

## Navigation Notes

- **"Return to LA Board Site"** button links back to the main LAUSD Board website
- **List/Detail toggle** — "List" button returns to list view, "Show Details" enters detail
- **Previous/Next** buttons navigate between resolutions in detail view
- **Sort** — clicking sort icons (small bar chart icons) in column headers toggles ascending/descending
- **Search** returns to the search form from any view
