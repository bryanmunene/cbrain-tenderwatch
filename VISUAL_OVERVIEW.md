# TenderWatch - Visual System Overview

## 🎯 System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     USER INTERFACE (Web)                     │
│         Professional cBrain Branded Flask Templates           │
├─────────────────────────────────────────────────────────────┤
│  Scan Results │ Tender Details │ Sources │ Favorites │ Saved │
└────────────────────────────┬────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────┐
│                    FLASK ROUTES LAYER                        │
│  /scan  /tender/<id>  /sources  /favorites  /save  etc.      │
└────────────────────────────┬────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────┐
│                  CORE LOGIC LAYER                            │
├─────────────────────────────────────────────────────────────┤
│  ├─ Scoring Engine          (score_text)                     │
│  ├─ Web Scraper             (scan_source)                    │
│  ├─ Categorizer             (auto-classify)                  │
│  ├─ Learner                 (ML keywords)                    │
│  └─ Parser                  (deadline extraction)            │
└────────────────────────────┬────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────┐
│                DATABASE LAYER (SQLite)                       │
├─────────────────────────────────────────────────────────────┤
│  ├─ TenderSource       (tender sources)                      │
│  ├─ TenderResult       (discovered tenders)                  │
│  └─ LearnedKeyword     (ML learning data)                    │
└─────────────────────────────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────┐
│                EXTERNAL SOURCES                              │
│  (UNDP, World Bank, USAID, AfDB, UNDB, GEF, IFC, UNOPS)     │
└─────────────────────────────────────────────────────────────┘
```

---

## 🔄 Tender Discovery Flow

```
START
  │
  ▼
┌─────────────────────────┐
│ User Clicks "Run Scan"  │
└──────────┬──────────────┘
           │
           ▼
┌──────────────────────────────────┐
│ For Each Active Tender Source:   │
│  1. Fetch HTML from source URL   │
│  2. Parse HTML for tender links  │
│  3. Extract tender title         │
└──────────┬───────────────────────┘
           │
           ▼
┌──────────────────────────────────┐
│ Score Each Tender:               │
│  1. Match keywords               │
│  2. Calculate score (0-100%)     │
│  3. Apply source bias            │
│  4. Generate breakdown           │
└──────────┬───────────────────────┘
           │
           ▼
┌──────────────────────────────────┐
│ Categorize Tender:               │
│  1. Analyze title/text           │
│  2. Assign category              │
│  3. Calculate confidence         │
│  4. Extract deadline             │
└──────────┬───────────────────────┘
           │
           ▼
┌──────────────────────────────────┐
│ Store in Database:               │
│  1. Save tender record           │
│  2. Store scoring breakdown      │
│  3. Link to source               │
│  4. Record timestamp             │
└──────────┬───────────────────────┘
           │
           ▼
┌──────────────────────────────────┐
│ Display Results:                 │
│  1. Sort by score (highest first)│
│  2. Format for table display     │
│  3. Enable user interactions     │
└──────────┬───────────────────────┘
           │
           ▼
         END
```

---

## 📊 Scoring System Flow

```
Tender Text
    │
    ▼
┌──────────────────────────┐
│ Extract Keywords:        │
│ "document management"    │ ──→ Match: ✓
│ "system"                │ ──→ Match: ✓
│ "implementation"        │ ──→ Match: ✓
│ (45 total keywords)     │
└──────────┬───────────────┘
           │
           ▼
┌──────────────────────────┐
│ Group Matches:           │
│ EDMS: 5 keywords        │
│ ICT:  4 keywords        │
│ Procurement: 3 keywords │
└──────────┬───────────────┘
           │
           ▼
┌──────────────────────────┐
│ Calculate Base Score:    │
│ 12 matched / 45 total   │
│ = 26.7%                 │
└──────────┬───────────────┘
           │
           ▼
┌──────────────────────────┐
│ Apply Source Bias:       │
│ Source: UNDP (+10)      │
│ 26.7% + 10 = 36.7%      │
└──────────┬───────────────┘
           │
           ▼
┌──────────────────────────┐
│ Cap at Maximum:          │
│ Min: 0%, Max: 100%      │
│ Final: 36.7%            │
└──────────┬───────────────┘
           │
           ▼
┌──────────────────────────┐
│ Generate Breakdown:      │
│ {                        │
│   "score": 36.7,        │
│   "keywords": 12,       │
│   "groups": [...]       │
│ }                        │
└──────────┬───────────────┘
           │
           ▼
        Display
```

---

## 🎨 UI Layout Overview

### Main Scan Results Page
```
┌─────────────────────────────────────────────────────────┐
│ TenderWatch - cBrain F2 Platform                        │
├─────────────────────────────────────────────────────────┤
│ [Run Scan]  [Sort: Score ▼] [Newest ▼] [Deadline ▼]   │
├─────────────────────────────────────────────────────────┤
│
│ Tender Title 1           │ Source │ 87%  │ EDMS  │ ⭐ 👁 🔗
│ Tender Title 2           │ Source │ 76%  │ Case  │ ☆ 👁 🔗
│ Tender Title 3           │ Source │ 65%  │ ICT   │ ☆ 👁 🔗
│ Tender Title 4           │ Source │ 45%  │ Proc  │ ☆ 👁 🔗
│
├─────────────────────────────────────────────────────────┤
│ [Delete All Results]
└─────────────────────────────────────────────────────────┘
```

### Tender Detail Page
```
┌─────────────────────────────────────────────────────────┐
│ [← Back to Results]                                     │
├─────────────────────────────────────────────────────────┤
│                                                         │
│ Full Tender Title                          [★ Favorite]│
│ Added: January 23, 2025                                │
│                                                         │
│ Source: UNDP Kenya          │ Country: Kenya            │
│ Deadline: Feb 28, 2025      │ Category: [EDMS]         │
│                             │ Confidence: ██████░░ 85% │
│                                                         │
├─────────────────────────────────────────────────────────┤
│ DESCRIPTION                                             │
│ [Full tender details and requirements...]              │
│                                                         │
├─────────────────────────────────────────────────────────┤
│ MATCHED KEYWORDS        │ SCORING BREAKDOWN             │
│ ├─ document             │ ├─ Match: 85%               │
│ ├─ management           │ ├─ Keywords: 12/45         │
│ ├─ system               │ ├─ Groups:                  │
│ └─ ...                  │ │  ├─ EDMS: 5 keywords    │
│                         │ │  ├─ ICT: 4 keywords     │
│ DIRECT ACCESS           │ │  └─ Proc: 3 keywords    │
│ [🔗 Open Tender]        │ │                          │
│ https://source.com...   │ └─ Score: 85%              │
│                                                         │
├─────────────────────────────────────────────────────────┤
│ [🔖 Save] [🌟 Favorite]                                │
└─────────────────────────────────────────────────────────┘
```

### Sources Management Page
```
┌─────────────────────────────────────────────────────────┐
│ TENDER SOURCES - Manage Your Scan Sources              │
│                                                         │
│ ADD NEW SOURCE                                          │
│ [Source Name____] [https://...] [Add Source]           │
│                                                         │
├─────────────────────────────────────────────────────────┤
│
│ Source Name    │ URL              │ Status    │ Actions │
├────────────────┼──────────────────┼───────────┼─────────┤
│ UNDP Kenya     │ 🔗 https://...   │ ✓ Active  │ ⭐ 🗑  │
│ World Bank     │ 🔗 https://...   │ ✓ Active  │ ☆ 🗑   │
│ USAID          │ 🔗 https://...   │ ✓ Active  │ ☆ 🗑   │
│ AfDB           │ 🔗 https://...   │ ✓ Active  │ ☆ 🗑   │
│
├─────────────────────────────────────────────────────────┤
│ RECOMMENDED SOURCES                                     │
│ Kenya: PPRA, UNDB, GEF                                 │
│ Global: World Bank, UNDP, IFC                          │
└─────────────────────────────────────────────────────────┘
```

---

## 📱 User Interaction Map

```
┌────────────────────┐
│   MAIN DASHBOARD   │
│   (Scan Page)      │
└─────────┬──────────┘
          │
    ┌─────┴─────┐
    │           │
    ▼           ▼
┌──────────┐ ┌──────────────┐
│  Run     │ │  View        │
│  Scan    │ │  Results     │
└────┬─────┘ └────┬─────────┘
     │            │
     │     ┌──────┴────────┐
     │     │               │
     │     ▼               ▼
     │  ┌──────────┐  ┌──────────────┐
     │  │ Click    │  │ Mark         │
     │  │ Tender   │  │ Favorite ⭐  │
     │  └────┬─────┘  └──────────────┘
     │       │
     │       ▼
     │    ┌─────────────────────┐
     │    │ TENDER DETAIL PAGE  │
     │    │ - Full info         │
     │    │ - Scoring breakdown │
     │    │ - Direct link       │
     │    │ - Save/Favorite     │
     │    └──────────┬──────────┘
     │               │
     │     ┌─────────┴─────────┐
     │     │                   │
     │     ▼                   ▼
     │  ┌──────────┐      ┌──────────┐
     │  │ Save     │      │ Click    │
     │  │ Tender   │      │ to Visit │
     │  │ 🔖       │      │ Source   │
     │  └──────────┘      └──────────┘
     │
     │
     ▼
┌──────────────────┐
│  SOURCES PAGE    │
│ - Add source     │
│ - Manage sources │
│ - Favorites      │
└────┬─────────────┘
     │
     └──────┬─────────────┐
            │             │
            ▼             ▼
        ┌────────┐  ┌──────────┐
        │ View   │  │ View     │
        │Saved   │  │Favorites │
        │Tenders │  │Tenders   │
        └────────┘  └──────────┘
```

---

## 🔍 Data Storage Model

```
╔════════════════════════════════════════════════════════════╗
║                    TENDER SOURCE                           ║
╠════════════════════════════════════════════════════════════╣
║ id: 1                                                      ║
║ name: "UNDP Kenya"                                         ║
║ url: "https://www.ug.undp.org/tenders"                   ║
║ active: True           (Include in scans?)                ║
║ favorite: False        (User's favorite?)                 ║
║ created_at: 2025-01-23                                    ║
╚════════════════════════════════════════════════════════════╝
                         ▲
                         │ (source_id)
                         │
╔════════════════════════════════════════════════════════════╗
║                    TENDER RESULT                           ║
╠════════════════════════════════════════════════════════════╣
║ id: 42                                                     ║
║ title: "Digital Records Management System"                ║
║ link: "https://source.com/tender/12345"                  ║
║ description: "Full tender requirements..."                ║
║ buyer: "UNDP Kenya"                                        ║
║ country: "Kenya"                                           ║
║ deadline: "2025-02-28"                                     ║
║ score: 87.5            (Relevance 0-100%)                ║
║ keywords_matched: "document, management, system, ..."    ║
║ scoring_breakdown: {JSON with details}                    ║
║ saved: False           (User saved?)                      ║
║ favorite: True         (User favorite?)                   ║
║ category: "EDMS"                                           ║
║ confidence: 0.92       (Classification certainty)         ║
║ source_id: 1           (Link to TenderSource)             ║
║ created_at: 2025-01-23 16:30:00                          ║
╚════════════════════════════════════════════════════════════╝
```

---

## 🎯 Scoring Distribution Example

```
Tender Count Distribution by Score

100% ─────────────────────────────────────────────────────
 90% ─  ┌─────────────────────────────────────────────────
 80% ─  │              HIGHLY RELEVANT
 70% ─  │  ██ 2 tenders (87%, 82%)
 60% ─  │
 50% ─  │                MODERATELY RELEVANT
 40% ─  │  ██████ 6 tenders (65%, 58%, 52%, 48%, 45%, 42%)
 30% ─  │
 20% ─  │  ███████ 7 tenders (38%, 35%, 28%, 22%, 18%, 15%, 10%)
 10% ─  │                LOW RELEVANCE
  0% ─  │  ████ 4 tenders (8%, 6%, 4%, 2%)
      └─────────────────────────────────────────────────────
         
Action Recommended:
- Score 70%+: Apply immediately
- Score 40-69%: Review for potential fit
- Score 0-39%: Archive unless specific interest
```

---

## 🔄 Daily Usage Pattern

```
MORNING
  │
  ├─ 08:00 - Open app
  ├─ 08:01 - Click "Run Scan"
  ├─ 08:02 - ⏳ Wait for scan (~45 sec)
  ├─ 08:03 - Review top 5 tenders (score > 70%)
  ├─ 08:05 - Click details on 2-3 promising tenders
  ├─ 08:08 - Mark best ones as ⭐ favorite
  └─ 08:10 - Check "Favorites" page
          │
          ▼ Visit external sites for promising tenders
          │
MIDDAY
  │
  ├─ 13:00 - Review "Saved" tenders from morning
  └─ 13:15 - Plan responses
          │
          ▼ Prepare bids/applications
          │
EVENING
  │
  ├─ 18:00 - Check for updates
  ├─ 18:01 - Run another scan
  ├─ 18:02 - Check for new high-score tenders
  └─ 18:15 - Update priority tracking
```

---

## 🎯 Feature Relationships

```
┌─────────────────────────────────────────────────────────┐
│                   TENDER SCANNING                       │
│ (Find opportunities from multiple sources)              │
└────────────┬────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────┐
│               INTELLIGENT SCORING                       │
│ (Determine relevance to cBrain: 0-100%)                │
└────────────┬────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────┐
│            AUTO-CATEGORIZATION                          │
│ (Classify into business categories)                     │
└────────────┬────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────┐
│           RESULT ORGANIZATION                           │
│ (Sort, filter, save, favorite)                          │
└────────────┬────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────┐
│         USER DECISION MAKING                            │
│ (Which tenders to pursue)                               │
└─────────────────────────────────────────────────────────┘
```

---

## 📊 System Performance Profile

```
Operation              Time        Memory   Notes
─────────────────────────────────────────────────────────
App Startup            1 sec       ~50 MB  Initial load
Scan (8 sources)       45 sec      ~80 MB  Network I/O
Page Load              <1 sec      ~60 MB  Database query
Search/Filter          <100 ms     ~70 MB  In-memory
Save/Favorite          <50 ms      ~60 MB  DB write
Export (500 records)   2 sec       ~100 MB  CPU intensive

Database Size Growth
─────────────────────────────────────────────────────────
Records     Size        Query Time      Recommendation
1,000       ~2 MB       <10 ms         Good performance
10,000      ~15 MB      ~50 ms         Still OK
100,000     ~150 MB     ~200 ms        Consider PostgreSQL
1,000,000   ~1.5 GB     ~500 ms        Need PostgreSQL+Index
```

---

## ✅ System Readiness Verification

```
┌─────────────────────────────────────────────────────────┐
│ INSTALLATION                                            │
├─────────────────────────────────────────────────────────┤
│ ✓ Python 3.8+                                           │
│ ✓ Dependencies installed (pip install -r requirements)  │
│ ✓ Database created (python init_sources.py)             │
└─────────────────────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────┐
│ CORE FUNCTIONALITY                                      │
├─────────────────────────────────────────────────────────┤
│ ✓ Web server running (python run.py)                    │
│ ✓ UI accessible (http://localhost:5000)                │
│ ✓ Database connected                                    │
│ ✓ Sources loaded                                        │
└─────────────────────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────┐
│ SCANNING & SCORING                                      │
├─────────────────────────────────────────────────────────┤
│ ✓ Web scraper working                                   │
│ ✓ Scoring engine calculating                            │
│ ✓ Results saving to database                            │
│ ✓ Breakdown generation functional                       │
└─────────────────────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────┐
│ USER FEATURES                                           │
├─────────────────────────────────────────────────────────┤
│ ✓ Save/favorite tenders                                 │
│ ✓ Manage sources                                        │
│ ✓ View details with breakdown                           │
│ ✓ Sort and filter results                               │
│ ✓ Direct source links working                           │
└─────────────────────────────────────────────────────────┘
              │
              ▼
         READY TO USE! 🚀
```

---

## 🎓 Quick Reference Card

```
╔════════════════════════════════════════════════════════════╗
║          TENDERWATCH QUICK REFERENCE                      ║
╠════════════════════════════════════════════════════════════╣
║ MAIN PAGE    http://localhost:5000                        ║
║ SCAN RESULTS  View all tenders, sorted by score           ║
║ TENDER VIEW   Click title → See full details              ║
║ SOURCES       Manage tender source URLs                   ║
║ FAVORITES     View all ⭐ starred tenders                 ║
║ SAVED         View all 🔖 bookmarked tenders             ║
║                                                            ║
║ SCORE GUIDE                                               ║
║ 70-100%  ✅  Highly Relevant - Apply now                 ║
║ 40-69%   ⚠️   Worth reviewing                             ║
║ 0-39%    ❌  Probably not suitable                        ║
║                                                            ║
║ QUICK ACTIONS                                              ║
║ ⭐ = Star (favorite)   🔖 = Bookmark (save)              ║
║ 👁 = View details     🔗 = Open tender source            ║
║ 🗑 = Delete           🌍 = Visit website                 ║
║                                                            ║
║ KEYBOARD SHORTCUTS                                         ║
║ Ctrl+L  Focus table                                        ║
║ Ctrl+M  Go to main page                                    ║
║ Ctrl+S  Save current tender                               ║
╚════════════════════════════════════════════════════════════╝
```

---

**TenderWatch Visual Overview Complete** ✨

For more information, see the documentation guides!
