
# Copilot Instructions for cBrain TenderWatch

## Architecture Overview

**TenderWatch** provides tender scanning in **two versions** with **shared backend logic**:

1. **Streamlit** (`tenderwatch_app/streamlit_app.py`): Single-file, auto-generated UI, recommended for quick deployment
2. **Flask** (`tenderwatch_app/app/`): MVC pattern, custom templates, Blueprint-based routes

### Core Data Flow
**Sources → Scraper → Translator → Scorer/Categorizer → Database → UI**

```
TenderSource (URL, active flag) 
    ↓
scraper.py: run_scan() fetches HTML, extracts <a> links
    ↓
translator.py: detect_language() + translate_to_english() (deep-translator)
    ↓
scoring.py: score_text() matches keywords → 5-100% score
categorizer.py: categorize() assigns category + confidence
    ↓
TenderResult (title, link, score, scoring_breakdown JSON)
    ↓
Flask routes.py OR streamlit_app.py
```

**Key deduplication:** `existing = {r.link for r in TenderResult.query.all()}` prevents duplicate tenders by URL

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
- `/settings` — Auto-scan config (interval in minutes, notification toggles)
- `/api/source-status` (GET) — JSON endpoint returning source health (active status, tender counts)
- `/favorites`, `/saved` — Filtered views using query filters `filter_by(favorite=True)`

### Database Models (models.py)
- **TenderSource**: name, url, active (bool), favorite (bool)
- **TenderResult**: title, link (unique), description, score, scoring_breakdown (JSON), category, confidence, saved, favorite, notified
- **LearnedKeyword**: (Optional) Stores learned keywords from `learner.py`
- **AppSettings**: auto_scan_enabled, scan_interval_minutes, notification_enabled
- All models use `db.Column` from `extensions.py` (shared db instance)

## Integration Points
- **Translation**: `translator.py` uses `deep-translator` for GoogleTranslator, `langdetect` for language detection
  - Fallback chain: deep-translator → MyMemory API → original text if all fail
  - Auto-detects language with `detect()`, uses `source_lang="auto"` by default
- **Scheduler**: APScheduler runs `scheduled_scan()` every N minutes (configured in `AppSettings.scan_interval_minutes`)
  - Started in `scheduler.py`, initialized on app startup in `__init__.py`
  - Toggle via `AppSettings.auto_scan_enabled` boolean
- **Notifications**: `notifications.py` uses `plyer` for desktop alerts on new high-score tenders (≥70%)
  - Only triggers for new tenders (`notified=False`), sets flag after notification
- **Adaptive Learning**: `learner.py` stores matched keywords in `LearnedKeyword` table for future scoring improvements
  - Called automatically after categorization in `scraper.py`: `learn_keywords(title, category)`
  - Weights increase with repeated matches (future enhancement: use in scoring)
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
