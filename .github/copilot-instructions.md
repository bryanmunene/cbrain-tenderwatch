
# Copilot Instructions for cBrain TenderWatch

## Architecture Overview

**TenderWatch** provides tender scanning in **two versions** with **shared backend logic**:

1. **Streamlit** (`tenderwatch_app/streamlit_app.py`): Single-file, auto-generated UI, recommended for quick deployment
2. **Flask** (`tenderwatch_app/app/`): MVC pattern, custom templates, Blueprint-based routes

### Core Data Flow
**Sources → Scraper → Translator → Scorer/Categorizer → Database → UI**

```
TenderSource (URL, active flag) OR Auto-Discovery (Google/Bing APIs)
    ↓
scraper.py: run_scan() fetches HTML OR run_auto_discovery() searches web
    ↓
translator.py: detect_language() + translate_to_english() (deep-translator)
    ↓
scoring.py: score_text() matches keywords → 5-100% score
categorizer.py: categorize() assigns category + confidence
    ↓
TenderResult (title, link, score, discovery_method, scoring_breakdown JSON)
    ↓
Flask routes.py OR streamlit_app.py
```

**Key deduplication:** `existing = {r.link for r in TenderResult.query.all()}` prevents duplicate tenders by URL

**Auto-Discovery NEW:** Dual API system (Google + Bing) searches entire web without manual source management. See `AUTO_DISCOVERY_SETUP.md` for full guide.

## Critical Setup Workflow

**MANDATORY: Database initialization before first run**

### Streamlit (Quick Start):
```powershell
cd tenderwatch_app
pip install -r requirements.txt
python init_sources.py          # REQUIRED: Seeds TenderSource table with 8 default sources
streamlit run streamlit_app.py  # Opens http://localhost:8501
```

### Flask (Full Control):
```powershell
cd tenderwatch_app
pip install -r requirements.txt
python init_sources.py          # REQUIRED: Seeds sources + creates instance/tenderwatch.db
python run.py                   # Runs http://localhost:5000 (or PORT env var)
```

**Flask App Context Pattern (CRITICAL):**
All database operations MUST be wrapped in `with app.app_context():` when run outside request handlers:
```python
from app import create_app
app = create_app()

with app.app_context():
    from app.models import TenderResult
    results = TenderResult.query.all()  # ✓ Correct
# TenderResult.query.all()  # ✗ RuntimeError: Working outside app context
```
This applies to: `init_sources.py`, `migrate_db.py`, Flask shell, Streamlit DB queries, scheduler functions

**Database location:** `tenderwatch_app/instance/tenderwatch.db` (auto-created by Flask on first run via `db.create_all()` in `app/__init__.py`)

**Production deployment:**
- Streamlit Cloud: Free forever, 1-click from GitHub (see `STREAMLIT_GUIDE.md`)
- Railway/Render: Use `Procfile` (`web: gunicorn run:app --chdir tenderwatch_app`)
  - Port auto-detected: `run.py` reads `PORT` env var (Railway/Render provide this)
  - Example: Railway sets `PORT=8080`, Flask binds to `0.0.0.0:8080`
- **PWA-enabled (Flask only):** Service worker + manifest.json for offline caching
- **Keep-alive strategies:** See `KEEP_ALIVE_SETUP.md` for preventing app sleep on free tiers
  - GitHub Actions workflows in `.github/workflows/` for automated scanning
    - `auto-scan.yml`: Runs `run_scan()` every hour via cron schedule
    - `keep-alive.yml`: Pings app URL every 5 minutes to prevent Streamlit Cloud sleep
    - Manual trigger available via `workflow_dispatch` event
  - UptimeRobot configuration for UI ping services

**Streamlit-Specific Patterns:**
- **Single-file architecture:** All UI logic in `streamlit_app.py` (~700 lines), imports backend from `app/` modules
- **DB initialization:** Call `init_db()` at module level (runs once on app load)
- **Flask context wrapper:** All DB queries use `with app.app_context():` block since Streamlit runs outside Flask request cycle
- **State management:** Use `st.session_state` for cross-page persistence (e.g., filters, selected tender)
- **Refresh trigger:** `st.rerun()` after DB mutations (save/delete/scan operations) to update UI
- **Custom CSS:** Injected via `st.markdown(..., unsafe_allow_html=True)` for cBrain theming
  - Gradient backgrounds: `linear-gradient(135deg, #2d3e50 0%, #2ba8d8 100%)`
  - Score coloring: `.high-score` (green), `.medium-score` (orange), `.low-score` (red)
- **Column layouts:** Use `st.columns([3, 1])` for dashboard metrics/sidebar patterns
- **Page config:** Must be first Streamlit command: `st.set_page_config(page_title="...", layout="wide")`

## Project-Specific Conventions

### Scoring Algorithm (scoring.py)
- **Base score:** Count unique matched keywords from `ALL_KEYWORDS` (imported from `keywords.py`)
- **Quality filtering:** Excludes generic standalone keywords (`GENERIC_STANDALONE_KEYWORDS`) like "bid", "tender", "rfp" when matched alone
  - Multi-word phrases containing these terms still count (e.g., "invitation to bid" for case management)
- **Multi-word bonus scoring:**
  - 4+ words: `word_count × 4` (16+ points, very specific)
  - 3 words: `word_count × 3` (9 points, specific)
  - 2 words: `word_count × 2` (4 points, somewhat specific)
  - 1 word: `+2` points (only for domain-specific terms like "edms", "dms", "ecm")
- **Normalization formula:** `((score - 8) / 32) × 90 + 10`, capped at 10-100%
  - Expected range: 8-40 points scale to 10-100%
  - Example: 20 points = ~44% score; 40 points = 100%
- **Source bias:** Added from `SOURCE_BIAS` dict (e.g., "undp": +10, "world bank": +8) — applied at categorization stage
- **Output:** Returns `(score, keywords_matched_str, breakdown_dict)` — breakdown stored as JSON in `TenderResult.scoring_breakdown`
  - Breakdown includes: `unique_keywords`, `matched_groups`, `match_percentage`, `keywords_found`

### AI/ML Enhancements (NEW)
- **Semantic Scoring (ai_scoring.py):** Uses sentence-transformers (`all-MiniLM-L6-v2`) for meaning-based relevance
  - `hybrid_score()` combines semantic (70%) + keyword (30%) scores when AI confidence >0.7
  - Fallback to keyword-only if model unavailable
  - Models cached globally for performance (first run: 5-10s, subsequent: <1s)
- **Entity Extraction (ai_entities.py):** spaCy NER extracts buyer, budget, deadline, location from text
  - `extract_entities()` returns dict with structured data
  - Fallback regex patterns if spaCy unavailable
  - Results stored in `TenderResult.entities_extracted` JSON field
- **Adaptive Learning (ai_learning.py):** Random Forest learns from saved/favorited tenders
  - `train_from_database()` requires ≥5 positive samples
  - `adjust_score()` blends original + learned preference (weighted by confidence)
  - Models saved in `tenderwatch_app/models/` directory
  - Retrain after significant user feedback or weekly
- **Toggle via AppSettings:** `ai_scoring_enabled`, `ai_learning_enabled`, `entity_extraction_enabled`
- **Complete AI Setup Workflow:**
  1. **PowerShell (Windows):** Run `setup_ai.ps1` (auto-installs all dependencies)
  2. **Manual setup (all platforms):**
     ```powershell
     cd tenderwatch_app
     pip install sentence-transformers spacy scikit-learn
     python -m spacy download en_core_web_sm  # 15-20MB download
     python migrate_ai_db.py                   # Adds AI columns to database
     ```
  3. **Verify installation:**
     ```python
     python -c "import spacy; nlp = spacy.load('en_core_web_sm'); print('✓ spaCy ready')"
     python -c "from sentence_transformers import SentenceTransformer; print('✓ Transformers ready')"
     ```
  4. **Disable AI if issues:** Run `disable_ai.py` to turn off all AI features (falls back to keyword scoring)
  5. **Model caching:** First scan with AI takes 5-10s (downloads `all-MiniLM-L6-v2` ~80MB), subsequent scans <1s
- **AI Troubleshooting:**
  - "Model not found": Run `python -m spacy download en_core_web_sm` again
  - "Out of memory": Disable AI via Settings UI or `disable_ai.py` script
  - "Slow scans": AI models cache on first run; wait 10s then retry
  - "Low confidence scores": Train model with ≥5 saved/favorited tenders via Settings → Retrain AI

### Category Assignment (categorizer.py)
- **Keyword groups:** 6 categories from `KEYWORD_GROUPS` (80+ keywords total):
  - Case & Complaint Management
  - Records & Document Management
  - Workflow & Business Process
  - ICT Infrastructure & Software
  - Procurement & Consulting
  - Construction & Infrastructure
- **Matching logic:** Sorts keywords by length (longest first) to prioritize specificity
  - "document management system" matches before generic "document"
- **Scoring:** `word_count × 2` per match; best category wins
- **Confidence:** `category_score / total_score` (0.0-1.0)
- **Example:** Title "EDMS for records management" → likely "Records & Document Management" (95%+ confidence)

### Scraper Pattern (scraper.py)
- **Generic scraper:** Targets all `<a href>` links containing regex pattern `tender|notice|opportunity|rfp|rfq|bid|procurement`
- **UNDP-specific:** Looks for "view_notice.cfm" in hrefs for specialized parsing
- **SSL fallback:** Tries `verify=True`, retries with `verify=False` on SSLError
- **Deduplication:** Set comprehension `existing = {r.link for r in TenderResult.query.all()}` before scan
  - Check `if full_url not in existing:` before adding new tender
- **Country mapping:** Uses `COUNTRY_MAP` dict (defaults Kenya sources to "Kenya", others to "Global")
- **Timeout:** 30s per request (`requests.get(url, timeout=30)`)

### Routes Structure (Flask routes.py)
All routes use Flask Blueprint `main` (registered in `__init__.py`):
- `/` — Dashboard with stats (total tenders, high scores, saved/favorites, category breakdown)
- `/scan` (POST) — Triggers `run_scan()`, returns results sorted by score desc, redirects to `/scan-results`
- `/tender/<int:tid>` — Detail view with scoring breakdown, matched keywords, categorization
- `/sources` — CRUD for tender sources (add, edit, delete, toggle active/favorite)
- `/discovery` — Auto-discovery dashboard with quota tracking, recent logs, manual trigger
- `/api/discovery/status` (GET) — JSON endpoint for quota status and recent discovery logs
- `/api/discovery/run` (POST) — Manual trigger for auto-discovery scan
- `/settings` — Auto-scan config (interval in minutes, notification toggles, auto-discovery API keys)
- `/api/source-status` (GET) — JSON endpoint returning source health (active status, tender counts)
- `/favorites`, `/saved` — Filtered views using query filters `filter_by(favorite=True)`

### Database Models (models.py)
- **TenderSource**: name, url, active (bool), favorite (bool)
- **TenderResult**: title, link (unique), description, score, scoring_breakdown (JSON), category, confidence, saved, favorite, notified
  - **AI fields**: semantic_score, ai_confidence, entities_extracted (JSON), ai_summary
  - **Discovery fields**: discovery_method ('manual', 'auto', 'priority'), search_query, search_source ('google', 'bing')
  - **Extracted fields**: buyer, country, deadline (parsed via `deadlines.py`)
- **PushSubscription**: endpoint (unique), p256dh_key, auth_key, user_agent, active (bool)
  - Stores Web Push API subscriptions for mobile/desktop notifications
- **DiscoveryLog**: run_type, queries_run, results_found, results_saved, google_quota_used, bing_quota_used, execution_time_seconds, error_message
  - Tracks auto-discovery runs with quota usage and statistics
- **LearnedKeyword**: (Optional) Stores learned keywords from `learner.py`
- **AppSettings**: auto_scan_enabled, scan_interval_minutes, notification_enabled
  - **AI settings**: ai_scoring_enabled, ai_learning_enabled, entity_extraction_enabled
  - **Auto-discovery settings**: auto_discovery_enabled, google_api_key, google_cx, bing_api_key, discovery_queries (JSON), results_per_query
  - **Notification settings**: notify_desktop, notify_email, min_score_to_notify, smtp_*
- All models use `db.Column` from `extensions.py` (shared db instance)

### Auto-Discovery System (NEW - auto_discovery.py)
- **SearchAPIManager**: Handles Google Custom Search + Bing Search API v7
  - `search_google()`: Query Google API (100/day free), returns list of dicts with title/link/snippet
  - `search_bing()`: Query Bing API (33/day free), returns list of dicts
  - `search_all()`: Combines both APIs with deduplication by URL
  - `get_quota_status()`: Returns current quota usage for both APIs (resets daily)
  - Quota tracking: Automatically stops at limit, resets at midnight UTC
- **TenderDiscovery**: Main discovery engine
  - `discover_tenders()`: Runs 14 default queries or custom queries from AppSettings
  - `_is_likely_tender()`: Filters results by positive keywords (tender, rfp, rfq) and excludes news/blogs/social
  - Default queries target: government procurement, EDMS, case management, regional (Kenya, Africa), source-specific (UNDP, World Bank)
- **Integration with run_scan()**: Auto-discovery runs after manual sources if `auto_discovery_enabled=True`
  - `run_auto_discovery()`: Initializes APIs from settings, discovers tenders, scores/categorizes/translates, saves with `discovery_method='auto'`
  - Logs each run in `DiscoveryLog` table with quota usage, results found, execution time
- **Setup**: Run `migrate_discovery.py` once to add discovery columns/tables
  - Get free API keys: Google Custom Search (100/day), Bing Search (33/day) = 133/day combined
  - Configure in Settings → Auto-Discovery section (Flask) or Settings sidebar (Streamlit)
  - View quota/logs in `/discovery` dashboard route

## Integration Points
- **Translation**: `translator.py` uses `deep-translator` for GoogleTranslator, `langdetect` for language detection
  - Fallback chain: deep-translator → MyMemory API → original text if all fail
  - Auto-detects language with `detect()`, uses `source_lang="auto"` by default
- **Auto-Discovery**: `auto_discovery.py` searches web via Google/Bing APIs for tender opportunities
  - Runs automatically with scheduled scans if `auto_discovery_enabled=True` in AppSettings
  - Manual trigger: POST to `/api/discovery/run` or "Run Discovery Now" button in UI
  - Quota management: Tracks usage per API, stops at limit, resets daily
  - Hybrid strategy: Manual sources scanned first (priority), then auto-discovery supplements
  - Setup guide: See `AUTO_DISCOVERY_SETUP.md` for API key instructions
- **Scheduler**: APScheduler runs `scheduled_scan()` every N minutes (configured in `AppSettings.scan_interval_minutes`)
  - Started in `scheduler.py`, initialized on app startup in `__init__.py`
  - Toggle via `AppSettings.auto_scan_enabled` boolean
- **Notifications**: Dual notification system for high-score tenders (≥min_score_to_notify):
  - **Desktop**: `notifications.py` uses `plyer` for native OS notifications
  - **Push**: `push_notifications.py` uses `pywebpush` + Web Push API for mobile/browser alerts
    - Requires VAPID keys (`vapid_private.pem`, `vapid_public.pem`) or env vars
    - Generate new keys: `python -c "from pywebpush import webpush; print(webpush.WebPusher.generate_vapid_keys())"`
    - VAPID subject: Set `VAPID_SUBJECT=mailto:admin@cbrain.net` (required for push API)
    - Subscriptions stored in `PushSubscription` model (endpoint, p256dh_key, auth_key)
    - Service worker in `static/service-worker.js` handles subscription + display
    - Only triggers for new tenders (`notified=False`), sets flag after notification
    - **Testing push notifications:**
      - Android Chrome: Open app → Settings → Enable notifications → Grant permission
      - iOS Safari 16.4+: Add to home screen first, then enable in Settings
      - Desktop: Click bell icon in browser address bar to grant permission
      - Verify subscription: Check `PushSubscription.query.all()` in Flask shell
      - Test send: Use `test_push_notifications.py` script with sample data
- **Deadline Parsing**: `deadlines.py` extracts dates from tender text
  - Regex pattern matches date formats: day-month-year with various separators
  - Converts formats like "15-Jan-2026", "15/01/2026" → "2026-01-15" (ISO format)
  - Stored in `TenderResult.deadline` field for sorting
- **Adaptive Learning**: `learner.py` stores matched keywords in `LearnedKeyword` table for future scoring improvements
  - Called automatically after categorization in `scraper.py`: `learn_keywords(title, category)`
  - Weights increase with repeated matches (future enhancement: use in scoring)
- **GitHub Actions Automation**: Scheduled workflows for unattended operations
  - `auto-scan.yml`: Hourly tender scanning without manual intervention
    - Runs `run_scan()` in Flask app context
    - Uploads database artifacts for backup (7-day retention)
    - Example: `python -c "from app import create_app; app = create_app(); ..."` pattern
    - **Database persistence strategies:**
      - Option 1: Commit database after scan (not recommended for SQLite on GitHub)
      - Option 2: Use PostgreSQL on Railway/Render with connection string in env vars
      - Option 3: Download artifacts manually from GitHub Actions → Artifacts tab
      - Option 4: Sync to cloud storage (S3, Google Drive) via `rclone` in workflow
      - Recommended: Deploy to Railway/Render with persistent PostgreSQL database
  - `keep-alive.yml`: Prevents app hibernation on free hosting tiers
    - Pings app URL every 5 minutes (Streamlit Cloud, Railway, Render)
    - Uses `curl` with timeout and retry logic
    - Alternative: UptimeRobot free tier (50 monitors, 5-min intervals)
- **UI Theming**: Bootstrap 5 + cBrain brand colors in `base.html` and Streamlit CSS:
  - Blue: `#1e3a8a` (primary buttons, headers)
  - Teal: `#0f766e` (accents, links)
  - Red: `#dc2626` (warnings, delete actions)
  - Dark background: `#0f172a` for reduced eye strain
- **PWA Features (Flask only)**: 
  - `service-worker.js` caches routes for offline access
  - `manifest.json` enables "Add to Home Screen" on mobile
  - `pwa.js` handles service worker registration

## Common Development Tasks

**Add new keyword group:**
1. Edit `keywords.py` → add to `KEYWORD_GROUPS` dict with category name + keyword list
2. Restart Flask app (keywords loaded on startup)
3. Example: `"New Category": ["keyword1", "multi word keyword", "keyword3"]`

**Add tender source:**
- Via UI: Navigate to `/sources` → "Add New Source" form
- Via code: Edit `init_sources.py`, delete `instance/tenderwatch.db`, re-run `python init_sources.py`
- **Critical:** URL must be publicly accessible, HTML-based (not PDF/API)

**Adjust scoring weights:**
- Edit `scoring.py` normalization formula (line ~32: `normalized_score = ((score - 2) / 13) * 95 + 5`)
- Change expected range: adjust `min_expected` (default: 2) and `max_expected` (default: 15)
- Edit `source_bias.py` to add/modify source-specific bonuses (e.g., `"undp": +10`)

**Debug failed scan:**
- Check `TenderSource.active = True` in database
- Test single source: Open Flask shell → `scan_source(TenderSource.query.get(1))`
- Inspect HTML structure: Add `print(soup.prettify())` in `scraper.py` after BeautifulSoup parsing
- Common issues: Site requires JavaScript (use Selenium), non-English content (check translator), SSL errors (already handled with fallback)

**View scoring breakdown:**
- Access `/tender/<id>` route → scroll to "Scoring Breakdown" section
- Or query database directly: `TenderResult.query.get(id).scoring_breakdown` (JSON string, parse with `json.loads()`)

**Migrate database schema:**
- Use `migrate_db.py` to add new columns without losing data
- Example pattern: `db.session.execute(text("ALTER TABLE tender_result ADD COLUMN new_field TEXT"))`

**Test push notifications end-to-end:**
1. **Generate VAPID keys:** `python -c "from pywebpush import webpush; keys = webpush.WebPusher.generate_vapid_keys(); print(f'Private:\n{keys["private_key"]}\n\nPublic:\n{keys["public_key"]}')"`
2. **Save keys:** Copy output to `vapid_private.pem` and `vapid_public.pem` OR set env vars
3. **Start app:** `streamlit run streamlit_app.py` or `python run.py`
4. **Subscribe (browser):**
   - Chrome/Edge: Open app → Click "Enable Notifications" → Allow permission
   - iOS Safari: Add to home screen first → Open app → Settings → Enable notifications
   - Firefox: Click bell icon in address bar → Allow
5. **Verify subscription:** Check database `PushSubscription.query.all()` or Settings UI "Active Subscriptions"
6. **Trigger notification:** Run scan with "Run Scan Now" button (score ≥ min_score_to_notify triggers push)
7. **Test manually:** Run `python test_push_notifications.py` to send test notification to all subscribers
8. **Debug failed sends:** Check browser console (F12) for "Service worker registration failed" errors

## Troubleshooting
- **No scan results:** Check if any `TenderSource.active = True` in DB (query via `/sources` or Flask shell)
- **Low scores (<20%):** Verify tender keywords match `keywords.py` entries (case-insensitive). Add domain-specific keywords if needed.
- **Duplicate tenders:** Scraper checks `link` uniqueness; if duplicates appear, manually delete via `/tender/<id>` or database query
- **Scheduler not running:** Verify `AppSettings.auto_scan_enabled = True` and `scan_interval_minutes > 0`, restart app
- **Translation failures:** Check internet connection (requires external API). Fallback returns original text.
- **Database locked errors (SQLite):** Close all connections, delete `.db-journal` file if present, restart app
- **PWA not installing:** Ensure Flask app served over HTTPS (required for service workers). Use ngrok for local testing.
- **Streamlit app context errors:** Ensure `app = create_app()` is called at module level (before any DB operations). Always wrap queries in `with app.app_context():`
- **Port conflicts:** Flask defaults to 5000, Streamlit to 8501. Override with `PORT` env var (Flask) or `--server.port` flag (Streamlit)

## Quick Testing Workflow
**Flask:**
```powershell
cd tenderwatch_app
python -c "from app import create_app; app = create_app(); app.app_context().push(); from app.models import *; print(f'Sources: {TenderSource.query.count()}, Results: {TenderResult.query.count()}')"
```

**Streamlit:**
```powershell
cd tenderwatch_app
streamlit run streamlit_app.py --server.port 8502  # Use alternate port if 8501 busy
```

**Database reset (DESTRUCTIVE):**
```powershell
cd tenderwatch_app
Remove-Item instance\tenderwatch.db  # PowerShell
python init_sources.py               # Recreate with default sources
```

---
See `README.md` for full features, `START_HERE.md` for quickstart, `VISUAL_OVERVIEW.md` for architecture diagrams.
