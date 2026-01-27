
# Copilot Instructions for cBrain TenderWatch

## Architecture Overview
**TenderWatch** is now available in **two versions**:

1. **Streamlit App** (Recommended - Simpler): Single-file app (`streamlit_app.py`) with auto-generated UI
2. **Flask App** (Original): Traditional web app with routes, templates, and full customization

**Data Flow:** Sources → Scraper → Translator → Scorer/Categorizer → Database → UI
- Sources stored in `TenderSource` model (managed via UI or `init_sources.py`)
- `run_scan()` in `scraper.py` fetches all active sources, extracts links, deduplicates by URL
- `translator.py` auto-translates non-English tenders using deep-translator + langdetect
- `scoring.py` scores 5-100% based on keyword matches (multi-word keywords weighted higher)
- `categorizer.py` assigns categories ("EDMS", "Case Management", etc.) with confidence scores
- Results stored in `TenderResult` model with score breakdown as JSON

## Critical Setup Workflow

### Streamlit Version (Simpler):
```powershell
cd tenderwatch_app
pip install -r requirements.txt
python init_sources.py
streamlit run streamlit_app.py    # Opens at http://localhost:8501
```

### Flask Version (Original):
```powershell
cd tenderwatch_app
pip install -r requirements.txt
python init_sources.py
python run.py                       # Runs at http://localhost:5000
```

**Quick Deploy to Internet:**
- **Streamlit Cloud:** streamlit.io/cloud → Deploy from GitHub → 1 click (FREE forever)
- **Railway:** railway.app → Deploy from GitHub → Auto-deploys in 2 min
- **Render:** render.com → New Web Service → Connect repo → Free forever
- See `STREAMLIT_GUIDE.md` for Streamlit deployment or `DEPLOYMENT.md` for Flask

## Project-Specific Conventions

### Scoring Algorithm (scoring.py)
- Base score = count of unique matched keywords from `ALL_KEYWORDS` (see `keywords.py`)
- Multi-word keyword bonus: +word_count points (e.g., "case management" = +2)
- Normalized to 5-100% using formula: `((score - 2) / 13) * 95 + 5`, capped at 100
- Source bias from `SOURCE_BIAS` dict (e.g., "undp": +10, "world bank": +8) added to final score
- Breakdown stored as JSON in `TenderResult.scoring_breakdown` field

### Category Assignment (categorizer.py)
- Uses `KEYWORD_GROUPS` dict (6 categories, 80+ keywords total)
- Longer keywords sorted first to avoid generic matches (e.g., "document management system" > "document")
- Score = word_count × 2 per match; best category wins
- Confidence = `category_score / total_score`
- Example: Title with "edms" + "records management" → likely "Records & Document Management" category

### Scraper Pattern (scraper.py)
- Generic scraper targets `<a href>` links containing "tender|notice|opportunity|rfp|rfq|bid|procurement"
- UNDP-specific: looks for "view_notice.cfm" in hrefs
- SSL verification fallback: tries `verify=True`, then `verify=False` on SSLError
- Deduplication via `existing = {r.link for r in TenderResult.query.all()}`
- Country mapping in `COUNTRY_MAP` (defaults Kenya sources to "Kenya", others to "Global")

### Routes Structure (routes.py)
All routes use Flask Blueprint `main`:
- `/` - Dashboard with stats (total tenders, high scores, saved/favorites)
- `/scan` (POST) - Triggers `run_scan()`, returns results sorted by score desc
- `/tender/<int:tid>` - Detail view with scoring breakdown, matched keywords
- `/sources` - CRUD for tender sources
- `/settings` - Auto-scan config (interval, notifications)
- `/api/source-status` - JSON endpoint for source health check

### Database Models (models.py)
- **TenderSource**: name, url, active (bool), favorite (bool)
- **TenderResult**: title, link (unique), description, score, scoring_breakdown (JSON), category, confidence, saved, favorite, notified
- **LearnedKeyword**: (Optional) Stores learned keywords from `learner.py`
- **AppSettings**: auto_scan_enabled, scan_interval_minutes, notification_enabled
- All models use `db.Column` from `extensions.py` (shared db instance)

## Integration Points
- **Translation**: `translator.py` uses `deep-translator` for GoogleTranslator, `langdetect` for language detection
- **Scheduler**: APScheduler runs `scheduled_scan()` every N minutes (configured in AppSettings)
- **Notifications**: `notifications.py` uses `plyer` for desktop alerts on new high-score tenders
- **UI**: Bootstrap 5 + cBrain colors (blue #1e3a8a, teal #0f766e, red #dc2626) in `base.html`

## Common Development Tasks

**Add new keyword group:**
1. Edit `keywords.py` → add to `KEYWORD_GROUPS` dict
2. Restart Flask app (keywords loaded on startup)

**Add tender source:**
- Via UI: `/sources` form
- Via code: Edit `init_sources.py`, delete `instance/tenderwatch.db`, re-run `python init_sources.py`

**Adjust scoring weights:**
- Edit `scoring.py` normalization formula (line 27: `normalized_score = ...`)
- Edit `source_bias.py` to change source bonuses

**Debug failed scan:**
- Check `TenderSource.active` = True
- Inspect scraper output: `print(soup.prettify())` in `scraper.py`
- Test single URL: `scan_source(TenderSource.query.get(1))`

**View scoring breakdown:**
- Access `/tender/<id>` → "Scoring Breakdown" section
- Or query `TenderResult.scoring_breakdown` JSON field directly

## Troubleshooting
- **No scan results:** Check if any `TenderSource.active = True` in DB
- **Low scores:** Verify tender keywords match `keywords.py` (case-insensitive)
- **Duplicate tenders:** Scraper checks `link` uniqueness; delete duplicates manually if needed
- **Scheduler not running:** Check `AppSettings.auto_scan_enabled = True`, restart app

---
See `README.md` for full features, `START_HERE.md` for quickstart, `VISUAL_OVERVIEW.md` for architecture diagrams.
