# Auto-Discovery Feature - Quick Reference

## What Changed?

**Before:** Manual source management required adding tender sites one-by-one, limiting growth.

**After:** Automatic web-wide discovery using Google + Bing APIs finds tenders from any site, even ones you don't know about.

---

## New Files Added

### Core Module
- **`app/auto_discovery.py`** (450 lines)
  - `SearchAPIManager`: Handles Google/Bing API calls with quota tracking
  - `TenderDiscovery`: Main discovery engine with default search queries
  - Functions: `search_google()`, `search_bing()`, `search_all()`, `discover_tenders()`

### Templates
- **`app/templates/discovery.html`** (250 lines)
  - Discovery dashboard with quota visualization
  - Manual discovery trigger button
  - Recent discovery run logs

### Migration & Setup
- **`migrate_discovery.py`** (110 lines)
  - Adds discovery columns to `TenderResult` and `AppSettings`
  - Creates `DiscoveryLog` table
  - Run once before using auto-discovery

- **`AUTO_DISCOVERY_SETUP.md`** (400 lines)
  - Complete guide to getting API keys
  - Step-by-step configuration
  - Quota management and optimization tips
  - Troubleshooting FAQ

---

## Modified Files

### Database Models (`app/models.py`)
**TenderResult:**
- Added `discovery_method` (VARCHAR): 'manual', 'auto', 'priority'
- Added `search_query` (VARCHAR): Query that found this tender
- Added `search_source` (VARCHAR): 'google', 'bing', or source name

**AppSettings:**
- Added `auto_discovery_enabled` (BOOLEAN): Toggle auto-discovery
- Added `google_api_key` (VARCHAR): Google Custom Search API key
- Added `google_cx` (VARCHAR): Google Custom Search Engine ID
- Added `bing_api_key` (VARCHAR): Bing Search API key
- Added `discovery_queries` (TEXT): JSON array of custom queries
- Added `results_per_query` (INTEGER): Results to fetch per query

**New Model - DiscoveryLog:**
- Tracks discovery runs with statistics
- Fields: queries_run, results_found, results_saved, google_quota_used, bing_quota_used, execution_time

### Scraper (`app/scraper.py`)
**Modified `run_scan()`:**
- Added `include_auto_discovery` parameter (default: True)
- Runs manual sources first, then auto-discovery
- Merged results with deduplication

**New `run_auto_discovery()`:**
- Initializes search APIs from settings
- Runs discovery with custom or default queries
- Scores/categorizes/translates auto-discovered tenders
- Logs discovery run statistics

### Routes (`app/routes.py`)
**Modified `/settings`:**
- Added auto-discovery configuration form
- Saves API keys and custom queries

**New Routes:**
- `/discovery` - Discovery dashboard with stats
- `/api/discovery/status` - JSON quota/log status
- `/api/discovery/run` (POST) - Manual discovery trigger

### Templates
**`app/templates/settings.html`:**
- Added auto-discovery settings section
- API key inputs with password masking
- Custom query JSON editor
- Results per query slider

**`app/templates/base.html`:**
- Added "Auto-Discovery" link to navigation menu

### Streamlit App (`streamlit_app.py`)
**Settings Page:**
- Added auto-discovery toggle
- API key configuration inputs
- Custom query editor
- Integrated with save settings flow

---

## Usage

### Quick Start

1. **Run migration:**
   ```powershell
   cd tenderwatch_app
   python migrate_discovery.py
   ```

2. **Get API keys** (see `AUTO_DISCOVERY_SETUP.md`):
   - Google Custom Search API (free 100/day)
   - Bing Search API (free 33/day)

3. **Configure:**
   - Flask: Settings → Auto-Discovery section
   - Streamlit: Sidebar → Settings → Auto-Discovery

4. **Test:**
   - Flask: Visit `/discovery` → Click "Run Discovery Now"
   - Streamlit: Click "Run Scan Now" (includes auto-discovery)

### API Quotas

| API    | Free Tier | Paid Tier |
|--------|-----------|-----------|
| Google | 100/day   | $5/1000   |
| Bing   | 33/day    | $7/1000   |
| **Combined** | **133/day** | **~$0.06/search** |

**For typical usage:** Stay within free tier indefinitely.

### Default Search Queries

System uses 14 pre-configured queries:
- "government tender procurement"
- "RFP document management system"
- "tender EDMS records management"
- "bid opportunity workflow automation"
- Regional: "tender Kenya government", "procurement opportunity Africa"
- Domain-specific: "tender electronic document management"
- Source-specific: "UNDP procurement notice", "World Bank tender"

**Customize:** Add your own in Settings → Discovery Queries (JSON array).

---

## Architecture

### Discovery Flow

```
User triggers scan
    ↓
Manual sources (priority) scanned first
    ↓
Auto-discovery enabled?
    ↓ Yes
Initialize SearchAPIManager with API keys
    ↓
For each search query:
    ├─ Query Google API (if key provided)
    └─ Query Bing API (if key provided)
    ↓
Combine results (deduplicate by URL)
    ↓
Filter relevance (_is_likely_tender)
    ↓
For each discovered tender:
    ├─ Check if URL already exists
    ├─ Score with AI or traditional scoring
    ├─ Categorize
    ├─ Translate
    ├─ Extract entities (if AI enabled)
    └─ Save to TenderResult (discovery_method='auto')
    ↓
Log discovery run (quota usage, results, time)
    ↓
Return combined manual + auto results
```

### Quota Tracking

`SearchAPIManager` tracks quota daily:
- Resets at midnight UTC
- Stops API calls when quota exhausted
- Returns remaining quota in `get_quota_status()`
- Logged in `DiscoveryLog` table per run

### Relevance Filtering

`_is_likely_tender()` checks:
- **Positive keywords:** tender, rfp, rfq, procurement, bid, proposal
- **Negative keywords:** news, blog, Wikipedia, social media
- **URL checks:** Filters out video sites, training courses

Only tenders with positive indicators and NO negative indicators are saved.

---

## Configuration Examples

### Minimal (Google only)

```
Google API Key: AIzaSyXXXXXXXXXXXXXXXXXXXXXXXXXX
Google CX: 0123456789abcdefg:hijklmnopqr
Bing API Key: (leave blank)
Results per Query: 10
```

### Optimal (Both APIs)

```
Google API Key: AIzaSyXXXXXXXXXXXXXXXXXXXXXXXXXX
Google CX: 0123456789abcdefg:hijklmnopqr
Bing API Key: XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
Results per Query: 10
Custom Queries: ["RFP EDMS Kenya 2026", "tender case management Africa"]
```

### Conservative (Low quota)

```
Results per Query: 5  (reduces API calls by 50%)
Custom Queries: ["government tender EDMS"]  (1 query = 2 API calls)
```

---

## Monitoring

### Discovery Dashboard (`/discovery`)

**Metrics:**
- Total auto-discovered tenders
- Discovery run count
- Average execution time
- API quota usage (real-time)

**Logs Table:**
- Date/time of each run
- Queries executed
- Results found vs. saved
- Google/Bing quota consumed
- Execution time
- Error messages (if any)

### API Endpoints

**`/api/discovery/status` (GET):**
```json
{
  "enabled": true,
  "quota": {
    "google": { "used": 45, "limit": 100, "remaining": 55 },
    "bing": { "used": 12, "limit": 33, "remaining": 21 },
    "reset_date": "2026-02-05"
  },
  "recent_logs": [...]
}
```

**`/api/discovery/run` (POST):**
```json
{
  "success": true,
  "tenders_found": 23,
  "message": "Auto-discovery complete: 23 new tenders found"
}
```

---

## Integration with Existing Features

### Works With
✅ **Manual sources** - Preserved as "priority sources"  
✅ **AI scoring** - Auto-discovered tenders scored with hybrid AI/keyword  
✅ **Entity extraction** - Extracts buyer, deadline, location from discovered tenders  
✅ **Adaptive learning** - User feedback improves discovery query ranking  
✅ **Notifications** - Push notifications sent for high-score auto-discovered tenders  
✅ **Scheduled scans** - Auto-discovery runs with scheduled scans if enabled  
✅ **Filters** - Filter by `discovery_method='auto'` in UI

### Coexistence Strategy

**Manual sources:** High-value, known sources (UNDP, World Bank)  
**Auto-discovery:** Unknown/emerging sources, regional portals

**Best practice:**
1. Start with manual sources for critical feeds
2. Enable auto-discovery to supplement
3. Monitor auto-discovered tenders in dashboard
4. Promote successful auto-discovered sources to manual for priority

---

## Troubleshooting

### "Auto-discovery not initialized"
- API keys not saved in Settings
- Check Settings → Auto-Discovery → Save

### "Invalid API key"
- Wrong key format
- Regenerate from Google Cloud Console / Azure Portal
- Check for spaces when copy-pasting

### "Quota exceeded"
- Google: Wait for midnight UTC reset
- Use Bing only (still 33/day available)
- Reduce `results_per_query` to 5

### "No results found"
- Queries too specific → Broaden terms
- All results already exist in database → Normal
- APIs returning zero results → Check API console for errors

### "Slow performance (>60s)"
- 14 queries × 2 APIs = 28 network calls
- Reduce custom queries to 5-7
- Lower `results_per_query` to 5
- Consider running less frequently

---

## Migration Rollback

If you need to disable auto-discovery:

```powershell
# Option 1: Via Settings UI
Settings → Auto-Discovery → Uncheck "Enable Auto-Discovery" → Save

# Option 2: Via Database (advanced)
python -c "from app import create_app; app = create_app(); app.app_context().push(); from app.models import AppSettings; s = AppSettings.query.first(); s.auto_discovery_enabled = False; from app.extensions import db; db.session.commit(); print('Disabled')"

# Option 3: Remove columns (irreversible)
# Not recommended - just disable via settings instead
```

---

## Performance Impact

**Without auto-discovery:**
- Scan time: 5-15 seconds (manual sources only)
- Database size: Grows slowly, limited by manual sources

**With auto-discovery:**
- Scan time: 30-90 seconds (adds 25-75s)
- Database size: Grows faster, more diverse tenders
- Network: 28+ API calls per run (14 queries × 2 APIs)

**Optimization tips:**
- Run discovery 2-4 times/day (not hourly)
- Use fewer custom queries (5-7 instead of 14)
- Set `results_per_query` to 5 for faster scans
- Schedule during off-peak hours (midnight-6am)

---

## Future Enhancements

**Planned features:**
- Auto-promote sources based on success rate
- Machine learning for query optimization
- Regional query templates (Africa, Asia, etc.)
- Domain-specific query packs (healthcare, infrastructure, IT)
- Discovery analytics dashboard with charts
- Email digest of top auto-discovered tenders

---

## Support

**Documentation:**
- Setup: `AUTO_DISCOVERY_SETUP.md`
- API guides: See Google/Bing API documentation links in setup guide
- Quota management: Discovery dashboard

**Debugging:**
- Check `/discovery` logs for errors
- View API quota status in dashboard
- Test single query manually on Google/Bing

**Questions?** Review setup guide FAQ section or check discovery logs for detailed error messages.
