# LAUSD Data Field Comparison: Legistar API vs. FileMaker Resolutions DB

**Date:** 2026-02-12

---

## Side-by-Side Field Comparison

| Data Category | Field | Legistar API | FileMaker Resolutions DB |
|---------------|-------|:------------:|:------------------------:|
| **Identity** | | | |
| | Resolution/File Number | `MatterFile` (e.g., "Res-031-25/26") | Resolution # (e.g., "031-25/26") |
| | Unique ID | `MatterId`, `EventItemId` | None (no API, session-based) |
| | Direct URL per record | `EventInSiteURL` | None (no permalink) |
| **Title & Text** | | | |
| | Title | `MatterTitle` / `EventItemTitle` | Title field |
| | Full Resolution Text | Playwright scraping (~90% coverage) | "Language" field (built-in, 100%) |
| | Text Format | HTML (scraped from web portal) | Plain text (rendered in UI) |
| **Dates** | | | |
| | Notice Date | Not directly available | Notice Date |
| | Action Date | `EventDate` / `MatterAgendaDate` | Action Date |
| | Introduction Date | `MatterIntroDate` | Not available |
| **Classification** | | | |
| | Matter Type | `MatterTypeName` (19 types) | N/A (resolutions only) |
| | Matter Status | `MatterStatusName` | Not available |
| | Action Taken | `EventItemActionName` | Action (e.g., "Adopted") |
| | Passed Flag | `EventItemPassedFlag` (1/0/null) | Implied by Action field |
| | Vote Type | Computed (Roll Call/Voice/Consent/No Vote) | Not classified |
| **Sponsorship** | | | |
| | Primary Sponsor | Via `/matters/{id}/histories` (MoverName) | Sponsor field (explicit) |
| | Cosponsors | Not directly available | Cosponsors table (explicit list) |
| | Moved By | `/histories` → `MatterHistoryMoverName` | Moved by field |
| | Seconded By | `/histories` → `MatterHistorySeconderName` | Second field |
| **Vote Data** | | | |
| | Individual Board Votes | `/EventItems/{id}/Votes` → VoteValueName | Votes table (Name + Yes/No/Absent) |
| | Vote Values | Aye, Nay, Absent, Recused, Abstained, Excused | Yes, Absent (others likely available) |
| | Student Votes | Not distinguished from board votes | Separate "Student Votes" section |
| | Vote Tally | `/histories` → `MatterHistoryTally` | Not available (individual votes only) |
| **Legislative History** | | | |
| | Multi-step History | `/matters/{id}/histories` (Postponed→Adopted) | Not available |
| | History Body | `MatterHistoryActionBodyName` | Not available |
| **Meeting Context** | | | |
| | Meeting/Event ID | `EventId` | Not available |
| | Meeting Body | `EventBodyName` | Not available |
| | Agenda Sequence | `EventItemAgendaSequence` | Not available |
| | Meeting Time/Location | `EventTime`, `EventLocation` | Not available |
| **Documents** | | | |
| | Attachments | `/matters/{id}/attachments` | Not available |
| | PDF Download | Often null (`EventAgendaFile`) | Per-resolution PDF (always available) |
| | Agenda PDF | `EventAgendaFile` (often null) | Not available |
| | Minutes PDF | `EventMinutesFile` (often null) | Not available |
| **People** | | | |
| | Board Members | `/persons` (mostly system accounts) | Populated from vote records |
| | Person IDs | `VotePersonId` / `PersonId` | None |
| **Scope** | | | |
| | Item Types Covered | All 19 matter types | Resolutions only |
| | Bodies Covered | All 12 bodies | Board of Education only |
| | Date Range | Varies by query | May 2003 – Jan 2026 (22+ years) |
| | Total Records | Varies (e.g., ~651 items/year) | 2,742 resolutions total |

---

## Unique to Each Source

### Fields Only in Legistar API
| Field | Endpoint | Notes |
|-------|----------|-------|
| `MatterId` / `EventItemId` | Various | Unique numeric identifiers |
| `MatterTypeId` / `MatterTypeName` | `/matters` | 19 matter types (not just resolutions) |
| `MatterStatusName` | `/matters` | Current status tracking |
| `MatterIntroDate` | `/matters` | When item was introduced |
| `EventItemAgendaSequence` | `/events/{id}/EventItems` | Order on agenda |
| `EventItemPassedFlag` | `/events/{id}/EventItems` | Explicit pass/fail flag |
| `VotePersonId` | `/EventItems/{id}/Votes` | Links to person records |
| Multi-step legislative history | `/matters/{id}/histories` | Postponed→Adopted workflow |
| Attachments | `/matters/{id}/attachments` | Supporting documents |
| Non-resolution items | Various | Committee reports, appointments, etc. |

### Fields Only in FileMaker Resolutions DB
| Field | Location | Notes |
|-------|----------|-------|
| Notice Date | Detail view | When resolution was first noticed |
| Sponsor | Detail view | Explicit primary sponsor (not just mover) |
| Cosponsors (full list) | Detail view table | All cosponsoring members |
| Student Votes (separate) | Detail view table | Distinguished from board member votes |
| Resolution PDF | List + Detail view | Always available, direct download |
| Full text (100% coverage) | "Language" field | No scraping needed |

---

## Field Quality Comparison

| Quality Metric | Legistar API | FileMaker DB |
|----------------|:------------:|:------------:|
| **Completeness of vote data** | High (Aye/Nay/Absent/Recused/Abstained/Excused) | Medium (Yes/Absent observed) |
| **Full text availability** | ~90% (requires Playwright scraping) | ~100% (built-in) |
| **Sponsor identification** | Indirect (via history mover) | Direct (explicit Sponsor field) |
| **Cosponsor identification** | Not available | Direct (explicit list) |
| **Student vote distinction** | Not distinguished | Separate section |
| **Programmatic access** | Easy (REST API, OData) | Difficult (Vaadin UI only) |
| **Record linking** | Excellent (IDs, foreign keys) | None (no IDs or URLs) |
| **Scope breadth** | All matter types, all bodies | Resolutions only |
| **Historical depth** | Varies | 22+ years (2003-2026) |

---

## Recommended Usage Strategy

```
Primary Source:     Legistar API (programmatic, broad coverage, linkable)
Supplementary:      FileMaker Resolutions DB (for fields Legistar lacks)
```

### Use FileMaker DB to supplement Legistar data for:
1. **Sponsor/Cosponsor** — Legistar only has mover/seconder from history; FileMaker has explicit sponsor + cosponsor list
2. **Notice Date** — Not available in Legistar
3. **Student Votes** — Not distinguished in Legistar
4. **Full Text Gaps** — For the ~10% of items where Legistar Playwright scraping fails
5. **PDF Collection** — FileMaker has reliable per-resolution PDFs; Legistar PDFs are often null
6. **Verification** — Cross-check vote records between the two sources
