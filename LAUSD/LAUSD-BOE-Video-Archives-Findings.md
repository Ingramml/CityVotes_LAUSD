# LAUSD BOE Video Archives & Agenda Site - Findings

**Date:** 2026-02-12
**URL:** https://boe.lausd.org/apps/pages/index.jsp?uREC_ID=4429226&type=d&pREC_ID=2668980
**Platform:** Edlio CMS (boe.lausd.org) + Granicus embedded iframe (lausd.granicus.com)

---

## Summary

The LAUSD Board of Education website hosts a **"Board Meeting and Committee Meeting Media and Files"** page. It embeds a **Granicus video/agenda archive** via iframe, providing access to meeting videos, agenda PDFs, and timestamped agenda item indices. The archive covers **July 1995 – April 2025** across board meetings and committee meetings.

---

## Site Structure

### Parent Site: boe.lausd.org (Edlio CMS)

**Left Navigation Links:**

| Link | URL | Description |
|------|-----|-------------|
| Board of Education Home | `/` | Main BOE page |
| Board Members | `pREC_ID=2681347` | Member bios |
| **Video Archives** | `pREC_ID=2668980` | **This page** — Granicus iframe |
| Board Resolutions | `dnnlt3f.pcifmhosting.com/fmi/webd/RESOLUTIONS` | FileMaker DB (already documented) |
| Bond Oversight | `bondoversight.lausd.org` | Bond oversight |
| IAU | `pREC_ID=4445229` | Independent Analysis Unit |
| Charter Petitions | `pREC_ID=2667368` | Charter school petitions |

### Embedded Iframe: Granicus Archive

**Base URL:** `https://lausd.granicus.com/ViewPublisher.php?view_id=4`

Three expandable archive sections:

| Section | Date Range | Content |
|---------|-----------|---------|
| **Board Committee Meetings** | 10/23/2012 – 4/22/2025 | Committee of the Whole, Facilities, Special Ed, Curriculum, Charter, Safety, etc. |
| **Board Meetings** | 12/11/2012 – 4/9/2025 | Regular & Special Board Meetings |
| **Archived Videos** | 7/24/1995 – 12/17/2013 | Historical board meeting videos |

---

## Per-Meeting Data Available

Each meeting entry provides:

| Field | Example |
|-------|---------|
| **Title** | "04-08-25 Regular Board Meeting, 11:00 AM - English" |
| **Date/Time** | "Apr 8, 2025 - 11:03 AM" |
| **Duration** | "08h 05m" |
| **Agenda** link | PDF via `AgendaViewer.php?view_id=4&clip_id={id}` |
| **Video** link | `MediaPlayer.php?view_id=4&clip_id={id}` |

### Bilingual Coverage
Most meetings appear in **paired entries** (Spanish + English), each with separate video streams and agenda documents.

---

## Granicus MediaPlayer Detail

Navigating to a Video link opens a rich media player page:

**URL Pattern:** `https://lausd.granicus.com/player/clip/{clip_id}?view_id=4`

### Features:
- **Video player** with full meeting recording
- **Agenda PDF** displayed alongside video (with page thumbnails)
- **Timestamped agenda index** — clickable agenda items jump to video timestamps:
  - Welcome and Introductions
  - Labor Partners
  - Numbered agenda items (e.g., "1. 060-24/25 Measure US Overview...")
  - Public Comment
  - Adjournment
- **Tabs:** Agenda (PDF viewer), Streaming Video Support
- **Actions:** Index, Share, Download, Embed

### Agenda PDF Content
The agenda PDFs include:
- Committee name, date, time, location
- Committee members listed by name
- District members and external representatives
- Board Secretariat contact info
- Full agenda with item numbers and descriptions

---

## Granicus RSS Feeds (Programmatic Access)

### Available RSS Feeds

| Feed | URL | Content |
|------|-----|---------|
| **Agendas** | `ViewPublisherRSS.php?view_id=4&mode=agendas` | Agenda document links |
| **Minutes** | `ViewPublisherRSS.php?view_id=4&mode=minutes` | Minutes links (currently empty) |
| **Audio Podcast** | `ViewPublisherRSS.php?view_id=4&mode=podcast` | Audio files |
| **Video Podcast** | `ViewPublisherRSS.php?view_id=4&mode=vpodcast` | Video files with download URLs |

### RSS Item Fields

| Field | Description | Example |
|-------|-------------|---------|
| `guid` | Unique identifier | (non-permalink) |
| `title` | Meeting name + date + time + language | "04-08-25 Regular Board Meeting, 11:00 AM - English" |
| `pubDate` | Publication timestamp (RFC 822) | "Tue, 08 Apr 2025 11:03:00 -0800" |
| `gran:pubDateParts` | Structured date components | year, month, day, hour, minute, second, timezone |
| `link` | Agenda/Media player URL | `AgendaViewer.php?...clip_id=4608` |
| `description` | HTML with access links | CDATA with paragraph |
| `enclosure` | Media file (video podcast only) | URL + type=video/x-ms-wmv |

### Video Podcast Key URLs per Item

| URL Type | Pattern |
|----------|---------|
| **Media Player** | `https://lausd.granicus.com/MediaPlayer.php?view_id=4&clip_id={id}` |
| **Download** | `https://lausd.granicus.com/DownloadFile.php?view_id=4&clip_id={id}` |
| **Agenda PDF** | `https://lausd.granicus.com/AgendaViewer.php?view_id=4&clip_id={id}` (redirects to DocumentViewer.php) |

### RSS Feed Limitations
- Appears capped at **~100 most recent items** per feed
- For historical data, must use the embedded iframe/UI directly

---

## Granicus View IDs

| view_id | Content | Status |
|---------|---------|--------|
| **2** | Streaming Media Archive (organized by committee) | Active — 100 RSS items |
| **4** | LAUSD Archives (embedded in BOE site) | Active — 100 RSS items |
| 1, 3, 5, 6 | N/A | 404 / Empty |

### View ID 2 — Committee-Organized Archive
`https://lausd.granicus.com/ViewPublisher.php?view_id=2`

Organized by committee with categories:
- Regular Board Meetings (May 2023 – Apr 2025)
- Committee of the Whole (May 2023 – Apr 2025)
- Facilities and Procurement Committee (Jan 2024 – Apr 2025)
- Special Education Committee (May 2023 – Jan 2025)
- Curriculum and Instruction Committee (Jan 2024 – Oct 2024)
- Charter School Committee (Nov 2023 – Apr 2024)
- Safety and School Climate Committee (Sep 2023 – Feb 2025)
- Children & Families in Early Education Committee (Sep 2023 – Jan 2025)
- Greening Schools and Climate Resilience Committee (May 2023 – Mar 2025)
- Special Closed Session Meetings (various 2023–2025)
- Annual Meetings (Dec 2023, Dec 2024)

---

## Relationship to Existing Data Sources

```
┌──────────────────────────────────────────────────────────────┐
│                    LAUSD Data Ecosystem                       │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Legistar API (PRIMARY)                                      │
│  └─ Votes, agenda items, matters, events                     │
│  └─ webapi.legistar.com/v1/lausd/                            │
│                                                              │
│  FileMaker Resolutions DB (SUPPLEMENTARY)                    │
│  └─ 2,742 resolutions with full text, sponsor, votes         │
│  └─ dnnlt3f.pcifmhosting.com/fmi/webd/RESOLUTIONS           │
│                                                              │
│  Granicus Video/Agenda Archive (SUPPLEMENTARY)  ◄── THIS     │
│  └─ Meeting videos, agenda PDFs, timestamped indices         │
│  └─ lausd.granicus.com (view_id=4, view_id=2)               │
│  └─ RSS feeds for programmatic access                        │
│                                                              │
│  BOE Website (PORTAL)                                        │
│  └─ Links all sources together                               │
│  └─ boe.lausd.org                                            │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### What Granicus Adds That Legistar Doesn't

| Feature | Granicus | Legistar |
|---------|----------|----------|
| Meeting video recordings | Full video per meeting | No video |
| Timestamped agenda indices | Clickable video timestamps per item | No timestamps |
| Agenda PDFs | Always available | Often null |
| Spanish-language versions | Separate video/agenda per language | English only |
| Committee member lists | In agenda PDF headers | Limited person data |
| Video duration | Per meeting | N/A |
| Download/embed options | Video + audio download | N/A |

### What Granicus Does NOT Have

- Individual vote records (use Legistar API or FileMaker DB)
- Resolution full text (use FileMaker DB)
- Sponsor/cosponsor data (use FileMaker DB)
- Structured matter/event data (use Legistar API)
- OData query filtering (use Legistar API)

---

## Extraction Recommendations

### For CityVotes Research Purposes
Granicus is primarily useful for:
1. **Agenda PDF collection** — reliable PDFs for every meeting (Legistar PDFs often null)
2. **Meeting video links** — for verification of contested votes
3. **Committee structure** — agenda PDFs list committee members explicitly
4. **Date/time verification** — cross-reference meeting dates with Legistar events

### Programmatic Access
```bash
# Get recent agenda links via RSS
curl "https://lausd.granicus.com/ViewPublisherRSS.php?view_id=4&mode=agendas"

# Get video download links via RSS
curl "https://lausd.granicus.com/ViewPublisherRSS.php?view_id=4&mode=vpodcast"

# Direct agenda PDF for a specific meeting
# (redirects to DocumentViewer.php with PDF)
curl -L "https://lausd.granicus.com/AgendaViewer.php?view_id=4&clip_id={CLIP_ID}"

# Video download
curl -L "https://lausd.granicus.com/DownloadFile.php?view_id=4&clip_id={CLIP_ID}"
```

### clip_id Mapping
The `clip_id` values in Granicus do not directly correspond to Legistar `EventId` values. To link them, match on **meeting date + body name**.
