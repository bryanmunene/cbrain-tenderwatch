"""
TenderWatch - Streamlit Version
Simple, powerful tender scanning for cBrain F2 Platform
"""

import json
import importlib
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import pandas as pd
import streamlit as st
from sqlalchemy import or_, text

# Ensure project root is on sys.path and avoid module name collisions.
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if "app" in sys.modules and not hasattr(sys.modules["app"], "__path__"):
    del sys.modules["app"]
importlib.invalidate_caches()

# Initialize database
from app import create_app
from app.extensions import db
from app.models import TenderSource, TenderResult, AppSettings
from app.scraper import run_scan, cleanup_irrelevant_tenders
from app.scoring import score_text
from app.categorizer import categorize

# Set page config
st.set_page_config(
    page_title="TenderWatch - cBrain",
    page_icon="",
    layout="wide",
    initial_sidebar_state="expanded"
)

# PWA Installation Support - inject manifest and service worker
st.markdown("""
<link rel="manifest" href="/static/manifest.json">
<link rel="apple-touch-icon" href="/static/icons/apple-touch-icon.png">
<link rel="icon" type="image/png" sizes="192x192" href="/static/icons/icon-192.png">
<link rel="icon" type="image/png" sizes="32x32" href="/static/icons/icon-32.png">
<meta name="theme-color" content="#2563eb">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="TenderWatch">
<meta name="mobile-web-app-capable" content="yes">
<meta name="application-name" content="TenderWatch">
<meta name="msapplication-TileColor" content="#2563eb">
<meta name="msapplication-TileImage" content="/static/icons/icon-144.png">
<script src="/static/pwa.js" defer></script>
""", unsafe_allow_html=True)

# Initialize session state for theme
if 'theme' not in st.session_state:
    st.session_state.theme = 'light'

# Professional visual system
st.markdown(f"""
<style>
    @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&display=swap');

    /* Theme Variables */
    :root {{
        --bg-primary: {'#091424' if st.session_state.theme == 'dark' else '#f3f6fb'};
        --bg-secondary: {'#0f1d32' if st.session_state.theme == 'dark' else '#e7edf5'};
        --text-primary: {'#e7edf7' if st.session_state.theme == 'dark' else '#0d1b2a'};
        --text-secondary: {'#9fb0c8' if st.session_state.theme == 'dark' else '#39485c'};
        --border-color: {'#21354f' if st.session_state.theme == 'dark' else '#cfd8e5'};
        --card-bg: {'#102037' if st.session_state.theme == 'dark' else '#ffffff'};
        --accent: {'#3d8bfd' if st.session_state.theme == 'dark' else '#1f5fbf'};
        --accent-strong: {'#2f78e6' if st.session_state.theme == 'dark' else '#184b97'};
        --table-row: {'#0f223d' if st.session_state.theme == 'dark' else '#f8fbff'};
    }}

    html, body, [class*="css"] {{
        font-family: "IBM Plex Sans", "Segoe UI", Arial, sans-serif;
        font-size: 14px;
    }}

    /* Main background */
    .main {{
        background: var(--bg-primary);
        background-attachment: fixed;
    }}

    .stApp {{
        background:
            radial-gradient(1200px 500px at 10% -10%, {'rgba(61,139,253,0.14)' if st.session_state.theme == 'dark' else 'rgba(31,95,191,0.10)'}, transparent 60%),
            radial-gradient(800px 400px at 90% -20%, {'rgba(88,166,255,0.10)' if st.session_state.theme == 'dark' else 'rgba(116,149,189,0.10)'}, transparent 58%),
            var(--bg-primary);
    }}

    .block-container {{
        max-width: 1400px;
        padding-top: 1.4rem;
        padding-bottom: 2.5rem;
    }}

    /* Modern card styling */
    [data-testid="stMetricValue"] {{
        font-size: 1.28rem;
        font-weight: 700;
        color: var(--text-primary);
        line-height: 1.2;
    }}

    [data-testid="stMetricLabel"] {{
        color: var(--text-secondary);
        font-weight: 600;
        font-size: 0.8rem;
    }}

    /* Button styling */
    .stButton>button {{
        background: var(--accent);
        color: white;
        border-radius: 10px;
        padding: 0.52rem 1.05rem;
        font-weight: 600;
        border: none;
        box-shadow: none;
        transition: background-color 0.2s ease, transform 0.12s ease;
    }}

    .stButton>button:hover {{
        background: var(--accent-strong);
        transform: translateY(-1px);
        box-shadow: none;
    }}

    /* Headers */
    h1, h2, h3, h4 {{
        color: var(--text-primary);
        font-weight: 650;
        letter-spacing: -0.01em;
    }}

    h1 {{
        font-size: 1.6rem;
        margin-bottom: 0.25rem;
    }}

    h2 {{
        font-size: 1.3rem;
    }}

    h3 {{
        font-size: 1.1rem;
    }}

    p, .stMarkdown {{
        color: var(--text-primary);
    }}

    .stCaption {{
        color: var(--text-secondary);
    }}

    [data-testid="stMarkdownContainer"] p,
    [data-testid="stMarkdownContainer"] li,
    [data-testid="stMarkdownContainer"] span {{
        color: var(--text-primary);
    }}

    /* Score badges */
    .high-score {{
        background: #166534;
        color: white;
        padding: 0.5rem 1rem;
        border-radius: 10px;
        font-weight: 700;
        display: inline-block;
        font-size: 1.2rem;
    }}
    .medium-score {{
        background: #b45309;
        color: white;
        padding: 0.5rem 1rem;
        border-radius: 10px;
        font-weight: 700;
        display: inline-block;
        font-size: 1.2rem;
    }}
    .low-score {{
        background: #b91c1c;
        color: white;
        padding: 0.5rem 1rem;
        border-radius: 10px;
        font-weight: 700;
        display: inline-block;
        font-size: 1.2rem;
    }}

    /* Input styling */
    .stTextInput>div>div>input, .stSelectbox>div>div>select, .stNumberInput>div>div>input, .stDateInput input {{
        border-radius: 10px;
        border: 1px solid var(--border-color);
        background: var(--card-bg) !important;
        color: var(--text-primary) !important;
        min-height: 2.35rem;
    }}

    .stTextInput>div>div>input:focus, .stSelectbox>div>div>select:focus {{
        border-color: var(--accent) !important;
        box-shadow: 0 0 0 1px var(--accent) inset;
    }}

    /* Card containers */
    .stExpander {{
        background: var(--card-bg);
        border-radius: 12px;
        border: 1px solid var(--border-color);
        box-shadow: none;
    }}

    /* Sidebar styling */
    [data-testid="stSidebar"] {{
        background: {'#0b1a2f' if st.session_state.theme == 'dark' else '#12253f'};
        border-right: 1px solid {'#223b5a' if st.session_state.theme == 'dark' else '#304b6d'};
    }}

    [data-testid="stSidebar"] * {{
        color: #e2e8f0 !important;
    }}

    /* Metric cards */
    [data-testid="stMetric"] {{
        background: var(--card-bg);
        padding: 1rem;
        border-radius: 10px;
        border: 1px solid var(--border-color);
        box-shadow: none;
        transition: border-color 0.2s ease;
    }}
    
    [data-testid="stMetric"]:hover {{
        transform: none;
        border-color: {'#38587d' if st.session_state.theme == 'dark' else '#9eb2cb'};
    }}

    /* Info/Success/Warning/Error boxes */
    .stAlert {{
        border-radius: 12px;
        border-left: 4px solid;
    }}

    /* Tab styling */
    .stTabs [data-baseweb="tab-list"] {{
        gap: 8px;
    }}
    
    .stTabs [data-baseweb="tab"] {{
        border-radius: 12px;
        padding: 0.65rem 1.2rem;
        font-weight: 600;
        background: {'#0e2038' if st.session_state.theme == 'dark' else '#e9eff7'};
        border: 1px solid var(--border-color);
        color: var(--text-primary);
    }}

    /* Banner */
    .hero-banner {{
        background: {'linear-gradient(120deg,#0d203b 0%,#102846 100%)' if st.session_state.theme == 'dark' else 'linear-gradient(120deg,#edf3fa 0%,#e6eef8 100%)'};
        border: 1px solid var(--border-color);
        border-radius: 12px;
        padding: 1rem 1.1rem;
        color: var(--text-primary);
        box-shadow: none;
        margin-bottom: 1.25rem;
    }}
    .hero-banner .title {{
        color: var(--text-primary);
        font-size: 1.05rem;
        font-weight: 700;
        margin: 0;
    }}
    .hero-banner .subtitle {{
        color: var(--text-secondary);
        font-size: 0.86rem;
        margin-top: 0.25rem;
    }}
    .pill {{
        display: inline-block;
        padding: 0.25rem 0.6rem;
        border-radius: 999px;
        background: {'#1c3657' if st.session_state.theme == 'dark' else '#cdd9ea'};
        color: {'#dce9fa' if st.session_state.theme == 'dark' else '#13263f'};
        margin-right: 0.5rem;
        font-size: 0.8rem;
        font-weight: 600;
    }}

    /* Dataframe styling */
    [data-testid="stDataFrame"] {{
        border-radius: 12px;
        overflow: hidden;
        border: 1px solid var(--border-color);
        background: var(--card-bg);
    }}

    [data-testid="stDataFrame"] [role="row"] {{
        background: var(--table-row);
    }}

    [data-testid="stDataFrame"] * {{
        color: var(--text-primary) !important;
    }}

    .stLinkButton a {{
        border-radius: 10px !important;
        border: 1px solid var(--border-color) !important;
        background: var(--card-bg) !important;
        color: var(--text-primary) !important;
    }}

    .stCaption {{
        font-size: 0.76rem;
    }}

    .stAlert p, .stAlert li, .stAlert span {{
        color: var(--text-primary) !important;
    }}
</style>
""", unsafe_allow_html=True)

# Initialize Flask app context for database.
# Avoid long-lived global cache mismatches between Flask app and SQLAlchemy instance
# across Streamlit hot reloads by validating binding each run.
def _is_db_bound(flask_app) -> bool:
    try:
        with flask_app.app_context():
            db.session.execute(text("SELECT 1"))
        return True
    except RuntimeError as exc:
        if "not registered with this 'SQLAlchemy' instance" in str(exc):
            return False
        raise


def get_flask_app():
    cached_app = st.session_state.get("_flask_app")
    cached_db_id = st.session_state.get("_flask_app_db_id")
    current_db_id = id(db)

    if cached_app is not None and cached_db_id == current_db_id and _is_db_bound(cached_app):
        return cached_app

    flask_app = create_app(start_scheduler=False, init_db=True)
    st.session_state["_flask_app"] = flask_app
    st.session_state["_flask_app_db_id"] = current_db_id
    return flask_app


app = get_flask_app()


def _utcnow():
    # Keep naive UTC for DB compatibility while avoiding utcnow() deprecation.
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _canonicalize_url(url: str) -> str:
    raw = (url or "").strip()
    if not raw:
        return ""
    try:
        parts = urlsplit(raw)
        scheme = (parts.scheme or "https").lower()
        netloc = parts.netloc.lower()
        path = parts.path.rstrip("/")
        return urlunsplit((scheme, netloc, path, "", ""))
    except Exception:
        return raw.rstrip("/").lower()


def _parse_deadline_value(deadline_str):
    value = (deadline_str or "").strip()
    if not value:
        return None
    # Most stored values are YYYY-MM-DD; tolerate trailing text.
    token = value[:10]
    try:
        return datetime.strptime(token, "%Y-%m-%d").date()
    except Exception:
        return None


def _deadline_meta(deadline_str):
    deadline_date = _parse_deadline_value(deadline_str)
    if not deadline_date:
        return {
            "label": "No deadline",
            "style": "none",
            "days_left": None,
            "date": None,
        }
    today = _utcnow().date()
    days_left = (deadline_date - today).days
    if days_left < 0:
        return {"label": f"Overdue ({abs(days_left)}d)", "style": "overdue", "days_left": days_left, "date": deadline_date}
    if days_left <= 3:
        return {"label": f"Urgent ({days_left}d)", "style": "urgent", "days_left": days_left, "date": deadline_date}
    if days_left <= 14:
        return {"label": f"Upcoming ({days_left}d)", "style": "upcoming", "days_left": days_left, "date": deadline_date}
    return {"label": deadline_date.strftime("%Y-%m-%d"), "style": "scheduled", "days_left": days_left, "date": deadline_date}


def _apply_deadline_window(tenders, deadline_window):
    if not deadline_window or deadline_window == "All":
        return tenders
    if deadline_window == "No deadline":
        return [t for t in tenders if _parse_deadline_value(getattr(t, "deadline", "")) is None]

    window_map = {"Next 7 days": 7, "Next 14 days": 14, "Next 30 days": 30}
    max_days = window_map.get(deadline_window)
    if max_days is None:
        return tenders

    filtered = []
    for tender in tenders:
        meta = _deadline_meta(getattr(tender, "deadline", ""))
        if meta["days_left"] is None:
            continue
        if 0 <= meta["days_left"] <= max_days:
            filtered.append(tender)
    return filtered


def _lifecycle_label(value: str) -> str:
    mapping = {
        "open": "Open",
        "pre_notice": "Pre-Notice",
        "awarded": "Awarded",
        "clarification": "Clarification",
        "cancelled": "Cancelled",
    }
    return mapping.get((value or "").strip().lower(), "Open")

def init_db(perform_translation=False):
    """Initialize database with app context"""
    with app.app_context():
        # Validated baseline (live-audited: reachable + parseable tender links).
        default_sources_data = [
            ("UNDP Procurement Notices", "https://procurement-notices.undp.org/", True),
            ("UN Global Marketplace", "https://www.ungm.org/Public/Notice", True),
            ("UNOPS Opportunities", "https://www.unops.org/business-opportunities", True),
            ("World Bank Procurement", "https://projects.worldbank.org/en/projects-operations/procurement", True),
            ("TED Europa Tenders", "https://ted.europa.eu/en/search/result", True),
            ("UK Find a Tender", "https://www.find-tender.service.gov.uk/Search", True),
            ("WFP Procurement", "https://www.wfp.org/procurement", False),
            ("WHO Procurement", "https://www.who.int/about/accountability/procurement", False),
            ("FAO Procurement", "https://www.fao.org/unfao/procurement/", False),
            ("ILO Procurement", "https://www.ilo.org/procurement/", False),
            ("Uganda PPDA", "https://www.ppda.go.ug/", True),
            ("Tanzania PPRA", "https://www.ppra.go.tz/", True),
            ("Nigeria BPP", "https://www.bpp.gov.ng/", True),
            ("South Africa eTender", "https://www.etenders.gov.za/", True),
            ("New Zealand GETS", "https://www.gets.govt.nz/ExternalIndex.htm", False),
            ("Philippines PhilGEPS", "https://www.philgeps.gov.ph/", False),
            ("ICT Authority", "https://icta.go.ke/tenders/", True),
            ("Kenya Public Procurement Portal", "https://tenders.go.ke/", True),
            ("Kenya PPIP", "https://tenders.go.ke/website/tenders/all", True),
            ("EU Funding & Tenders", "https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/opportunities/topic-search", False),
            ("DFFE Tenders (South Africa)", "https://www.dffe.gov.za/tenders", True),
            ("TradeMark Africa Procurement", "https://trademarkafrica.com/procurement/", True),
            ("Eswatini SPPRA", "https://www.sppra.co.sz", True),
            ("Tender Yetu Platform", "https://www.tenderyetu.com/", False),
            ("Singapore GeBIZ", "https://www.gebiz.gov.sg/", True),
            ("KEMSA Tenders", "https://www.kemsa.co.ke/tenders/", True),
            ("NSSF Tenders", "https://www.nssf.or.ke/tenders", True),
            ("MyGov Kenya", "https://www.mygov.go.ke/?s=tender", True),
        ]
        low_signal_sources = {
            "DgMarket",
            "Global Tenders",
            "Tenders Info",
            "Tendersinfo Kenya",
            "BidDetail",
            "Tender Yetu Platform",
        }
        
        # Add missing sources (check by URL to avoid duplicates)
        existing_urls = {_canonicalize_url(s.url) for s in TenderSource.query.all()}
        added_count = 0
        for name, url, is_favorite in default_sources_data:
            if _canonicalize_url(url) not in existing_urls:
                source = TenderSource(name=name, url=url, active=True, favorite=is_favorite)
                db.session.add(source)
                added_count += 1
        
        if added_count > 0:
            db.session.commit()
            print(f" Added {added_count} new tender sources")

        # Keep noisy aggregators available, but disabled by default.
        disabled_count = 0
        for source in TenderSource.query.all():
            if source.name in low_signal_sources and source.active and not source.favorite:
                source.active = False
                disabled_count += 1
        if disabled_count > 0:
            db.session.commit()
            print(f"Disabled {disabled_count} low-signal sources by default")
        
        # Optional translation pass (throttled by caller).
        if perform_translation:
            translate_untranslated_tenders()

def translate_untranslated_tenders(limit=20):
    """Translate tenders that don't have translations yet."""
    from app.translator import translate_to_english, detect_language
    
    with app.app_context():
        # Find tenders where title_translated is empty or same as title
        untranslated = TenderResult.query.filter(
            (TenderResult.title_translated.is_(None)) |
            (TenderResult.title_translated == "") |
            (TenderResult.title_translated == TenderResult.title)
        ).limit(limit).all()
        
        if untranslated:
            print(f"Translating {len(untranslated)} untranslated tenders...")
            translated_count = 0
            updated_count = 0
            
            for tender in untranslated:
                # Check if title is non-English
                detected_lang = detect_language(tender.title)
                if detected_lang != "en":
                    translated_title = translate_to_english(tender.title)
                    if translated_title and translated_title.lower() != tender.title.lower():
                        tender.title_translated = translated_title
                        translated_count += 1
                        updated_count += 1
                else:
                    # Mark English tenders as translated (same as original)
                    if tender.title_translated != tender.title:
                        tender.title_translated = tender.title
                        updated_count += 1
            
            if updated_count > 0:
                db.session.commit()
                print(f"Translation pass complete: translated {translated_count}, updated {updated_count}")


def maybe_translate_untranslated_tenders(force=False, limit=20, cooldown_seconds=900):
    """Throttle translation passes to keep UI responsive."""
    now = time.time()
    last_run = st.session_state.get("last_translation_run_ts", 0)
    if force or (now - last_run) >= cooldown_seconds:
        translate_untranslated_tenders(limit=limit)
        st.session_state["last_translation_run_ts"] = now


def bootstrap_once():
    """Run bootstrap tasks once per Streamlit session."""
    if st.session_state.get("bootstrap_done"):
        return
    init_db(perform_translation=False)
    st.session_state["bootstrap_done"] = True


def get_tenders(filters=None, days_window=30):
    """Get tenders with optional filters."""
    with app.app_context():
        query = TenderResult.query
        if days_window is not None:
            since = _utcnow() - timedelta(days=days_window)
            query = query.filter(TenderResult.created_at >= since)
        
        if filters:
            if filters.get('min_score'):
                query = query.filter(TenderResult.score >= filters['min_score'])
            if filters.get('category') and filters['category'] != "All":
                query = query.filter(TenderResult.category == filters['category'])
            if filters.get('search'):
                search_term = f"%{filters['search']}%"
                query = query.filter(
                    TenderResult.title.ilike(search_term) | 
                    TenderResult.title_translated.ilike(search_term) |
                    TenderResult.description.ilike(search_term) |
                    TenderResult.description_translated.ilike(search_term)
                )
            if filters.get('favorites_only'):
                query = query.filter(TenderResult.favorite == True)
            if filters.get('saved_only'):
                query = query.filter(TenderResult.saved == True)
            
            # New filters: Priority, Status, Country, F2 Fit
            if filters.get('priority') and filters['priority'] != "All":
                query = query.filter(TenderResult.priority_level == filters['priority'])
            if filters.get('status') and filters['status'] != "All":
                query = query.filter(TenderResult.procurement_status == filters['status'])
            if filters.get('lifecycle') and filters['lifecycle'] != "All":
                query = query.filter(TenderResult.timing_status == filters['lifecycle'])
            if filters.get('country') and filters['country'] != "All":
                query = query.filter(TenderResult.country == filters['country'])
            if filters.get('f2_fit') and filters['f2_fit'] != "All":
                query = query.filter(TenderResult.likely_fit_for_f2 == filters['f2_fit'])
            if filters.get('f2_only'):
                f2_statuses = ["true", "strategic", "discuss", "conditional"]
                f2_clause = or_(
                    TenderResult.likely_fit_for_f2.in_(f2_statuses),
                    (TenderResult.keywords_matched.isnot(None) & (TenderResult.keywords_matched != ""))
                )
                query = query.filter(f2_clause)
            if filters.get('open_only'):
                query = query.filter(
                    ~TenderResult.procurement_status.in_(["locked", "conditional_nogo"])
                )
                query = query.filter(
                    ~TenderResult.timing_status.in_(["awarded", "clarification", "cancelled"])
                )
        
        # Sort
        sort_by = filters.get('sort_by', 'score') if filters else 'score'
        if sort_by == 'score':
            query = query.order_by(TenderResult.score.desc())
        elif sort_by == 'date':
            query = query.order_by(TenderResult.created_at.desc())
        elif sort_by == 'deadline':
            query = query.order_by(TenderResult.deadline.asc())
        
        return query.all()


def get_tenders_with_fallback(filters=None):
    """Get tenders with progressive fallback when strict filters return nothing."""
    if not filters:
        return get_tenders(), True, ""

    if not filters.get('f2_only'):
        base = get_tenders(filters)
        if base:
            return base, False, ""

        if filters.get("open_only"):
            relaxed = dict(filters)
            relaxed["open_only"] = False
            widened = get_tenders(relaxed)
            if widened:
                return widened, False, "No open tenders matched. Showing locked/conditional opportunities too."
        anytime = get_tenders(filters, days_window=None)
        if anytime:
            return anytime, False, "No recent matches found. Displaying earlier results."
        return base, False, ""

    filtered = get_tenders(filters)
    if filtered:
        return filtered, True, ""

    relaxed = dict(filters)
    relaxed['f2_only'] = False
    widened = get_tenders(relaxed)
    if widened:
        return widened, False, "No F2-only matches found. Displaying all results."

    if relaxed.get("open_only"):
        relaxed["open_only"] = False
        widest = get_tenders(relaxed)
        if widest:
            return widest, False, "No open F2 tenders found. Showing all statuses."

    anytime = get_tenders(relaxed, days_window=None)
    if anytime:
        return anytime, False, "No recent matches found. Displaying earlier results."
    return widened, False, "No tenders matched current filters."

def get_sources():
    """Get all tender sources"""
    with app.app_context():
        return TenderSource.query.all()

def get_stats():
    """Get dashboard statistics with trend deltas."""
    with app.app_context():
        now = _utcnow()
        one_month_ago = now - timedelta(days=30)
        two_months_ago = now - timedelta(days=60)

        total = TenderResult.query.filter(TenderResult.created_at >= one_month_ago).count()
        high_score = TenderResult.query.filter(
            TenderResult.score >= 70,
            TenderResult.created_at >= one_month_ago
        ).count()
        saved = TenderResult.query.filter_by(saved=True).filter(
            TenderResult.created_at >= one_month_ago
        ).count()
        favorites = TenderResult.query.filter_by(favorite=True).filter(
            TenderResult.created_at >= one_month_ago
        ).count()
        active_sources = TenderSource.query.filter_by(active=True).count()
        
        # Get categories (last month only)
        categories = db.session.query(
            TenderResult.category,
            db.func.count(TenderResult.id).label('count')
        ).filter(TenderResult.created_at >= one_month_ago).group_by(TenderResult.category).all()

        prev_total = TenderResult.query.filter(
            TenderResult.created_at >= two_months_ago,
            TenderResult.created_at < one_month_ago
        ).count()
        prev_high_score = TenderResult.query.filter(
            TenderResult.score >= 70,
            TenderResult.created_at >= two_months_ago,
            TenderResult.created_at < one_month_ago
        ).count()
        prev_saved = TenderResult.query.filter_by(saved=True).filter(
            TenderResult.created_at >= two_months_ago,
            TenderResult.created_at < one_month_ago
        ).count()
        prev_favorites = TenderResult.query.filter_by(favorite=True).filter(
            TenderResult.created_at >= two_months_ago,
            TenderResult.created_at < one_month_ago
        ).count()

        upcoming_7d = 0
        current_tenders = TenderResult.query.filter(TenderResult.created_at >= one_month_ago).all()
        for tender in current_tenders:
            meta = _deadline_meta(tender.deadline)
            if meta["days_left"] is not None and 0 <= meta["days_left"] <= 7:
                upcoming_7d += 1

        def _fmt_delta(current, previous):
            delta = current - previous
            sign = "+" if delta >= 0 else ""
            return f"{sign}{delta} vs prior 30d"
        
        return {
            'total': total,
            'high_score': high_score,
            'saved': saved,
            'favorites': favorites,
            'active_sources': active_sources,
            'categories': dict(categories) if categories else {},
            'upcoming_7d': upcoming_7d,
            'delta_total': _fmt_delta(total, prev_total),
            'delta_high_score': _fmt_delta(high_score, prev_high_score),
            'delta_saved': _fmt_delta(saved, prev_saved),
            'delta_favorites': _fmt_delta(favorites, prev_favorites),
        }


def get_upcoming_deadlines(limit=8, horizon_days=30):
    with app.app_context():
        since = _utcnow() - timedelta(days=30)
        tenders = (
            TenderResult.query
            .filter(TenderResult.created_at >= since)
            .all()
        )
    upcoming = []
    for tender in tenders:
        meta = _deadline_meta(tender.deadline)
        if meta["days_left"] is None:
            continue
        if 0 <= meta["days_left"] <= horizon_days:
            upcoming.append((meta["days_left"], tender, meta))
    upcoming.sort(key=lambda item: item[0])
    return upcoming[:limit]

def toggle_favorite(tender_id):
    """Toggle favorite status"""
    with app.app_context():
        tender = TenderResult.query.get(tender_id)
        if tender:
            tender.favorite = not tender.favorite
            db.session.commit()
            return True
    return False

def toggle_saved(tender_id):
    """Toggle saved status"""
    with app.app_context():
        tender = TenderResult.query.get(tender_id)
        if tender:
            tender.saved = not tender.saved
            db.session.commit()
            return True
    return False

def toggle_source(source_id):
    """Toggle source active status"""
    with app.app_context():
        source = TenderSource.query.get(source_id)
        if source:
            source.active = not source.active
            db.session.commit()
            return True
    return False

def add_source(name, url):
    """Add new tender source"""
    with app.app_context():
        canonical = _canonicalize_url(url)
        existing = TenderSource.query.all()
        if any(_canonicalize_url(s.url) == canonical for s in existing):
            return False
        source = TenderSource(name=name, url=url, active=True)
        db.session.add(source)
        db.session.commit()
        return True

def delete_source(source_id):
    """Delete tender source"""
    with app.app_context():
        source = TenderSource.query.get(source_id)
        if source:
            db.session.delete(source)
            db.session.commit()
            return True
    return False

def run_tender_scan():
    """Run tender scan"""
    started = time.time()
    with app.app_context():
        new_tenders = run_scan(flask_app=app)
    # Run a throttled translation pass after scanning to avoid repeated churn on reruns.
    maybe_translate_untranslated_tenders(force=False, limit=20, cooldown_seconds=300)
    elapsed = time.time() - started
    print(f"[DEBUG] run_tender_scan: Found {len(new_tenders)} new tenders in {elapsed:.1f}s.")
    return new_tenders

# Initialize database once per user session
bootstrap_once()

# Sidebar
with st.sidebar:
    st.title("TenderWatch")
    st.markdown("**cBrain F2 TenderWatch**")
    st.markdown("---")
    
    page = st.radio(
        "Navigation",
        ["Dashboard", "Scan & Results", "Sources", "Favorites", "Saved", "Settings"],
        label_visibility="collapsed"
    )
    
    st.markdown("---")
    
    # Subtle theme toggle at bottom
    if st.button("Switch Theme", key="theme_toggle", help="Toggle light/dark theme"):
        st.session_state.theme = 'dark' if st.session_state.theme == 'light' else 'light'
        st.rerun()
    
    st.caption("2026 cBrain TenderWatch")

# Main content based on selected page
if page == "Dashboard":
    st.title("Executive Dashboard")
    st.markdown("A concise view of active cBrain F2 opportunities and immediate actions.")

    stats = get_stats()

    header_left, header_right = st.columns([3, 2])
    with header_left:
        st.markdown("### Portfolio Snapshot")
        st.caption("Current portfolio view")
    with header_right:
        if st.session_state.get("last_scan_info"):
            info = st.session_state["last_scan_info"]
            st.info(
                f"Last scan: {info.get('timestamp', 'n/a')} | "
                f"New: {info.get('new_count', 0)} | "
                f"Duration: {info.get('duration_s', 0):.1f}s"
            )
        else:
            st.info(f"Active sources: {stats['active_sources']}. Run a scan from `Scan & Results`.")

    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("Total Opportunities", stats['total'], delta=stats.get('delta_total'))
    with col2:
        st.metric("High Fit (>=70)", stats['high_score'], delta=stats.get('delta_high_score'))
    with col3:
        st.metric("Deadlines in 7 Days", stats.get('upcoming_7d', 0))
    with col4:
        st.metric("Saved", stats['saved'], delta=stats.get('delta_saved'))
    with col5:
        st.metric("Favorites", stats['favorites'], delta=stats.get('delta_favorites'))

    st.markdown("---")
    st.subheader("Action Queue")

    urgent_col, fit_col = st.columns(2)
    with urgent_col:
        st.markdown("#### Upcoming Deadlines (Next 30 Days)")
        upcoming_deadlines = get_upcoming_deadlines(limit=8, horizon_days=30)
        if upcoming_deadlines:
            for _, tender, meta in upcoming_deadlines:
                c1, c2, c3 = st.columns([6, 2, 2])
                with c1:
                    st.markdown(f"**{tender.title}**")
                    st.caption(f"{tender.country or 'Global'} | {tender.category or 'Unclassified'}")
                with c2:
                    st.markdown(f"**{meta['label']}**")
                with c3:
                    st.link_button("Open", tender.link, width="stretch")
        else:
            st.caption("No active deadlines found in the next 30 days.")

    with fit_col:
        st.markdown("#### High-Fit Recent Opportunities")
        recent_high_fit = get_tenders({
            'sort_by': 'score',
            'min_score': 70,
            'open_only': True,
            'f2_only': True,
        })[:8]
        if recent_high_fit:
            rows = []
            for t in recent_high_fit:
                d_meta = _deadline_meta(t.deadline)
                rows.append({
                    "Title": t.title_translated if t.title_translated and t.title_translated != t.title else t.title,
                    "Score": round(t.score or 0, 1),
                    "Country": t.country or "",
                    "Deadline": d_meta["label"],
                    "Status": _lifecycle_label(t.timing_status),
                    "Link": t.link,
                })
            st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
        else:
            st.caption("No high-fit open tenders currently. Run a fresh scan.")

    st.markdown("---")
    st.subheader("Pipeline Overview")

    col_a, col_b = st.columns([2, 1])
    with col_a:
        recent = get_tenders({'sort_by': 'date'})[:12]
        if recent:
            table_rows = []
            for tender in recent:
                d_meta = _deadline_meta(tender.deadline)
                table_rows.append({
                    "Title": tender.title_translated if tender.title_translated and tender.title_translated != tender.title else tender.title,
                    "Score": round(tender.score or 0, 1),
                    "Category": tender.category or "Unclassified",
                    "Country": tender.country or "Global",
                    "Deadline": d_meta["label"],
                    "Lifecycle": _lifecycle_label(tender.timing_status),
                    "Added": tender.created_at.strftime('%Y-%m-%d') if tender.created_at else "",
                })
            st.dataframe(pd.DataFrame(table_rows), hide_index=True, width="stretch")
        else:
            st.info("No recent tenders. Run a scan to populate your pipeline.")

    with col_b:
        st.markdown("#### Categories")
        if stats['categories']:
            cat_df = pd.DataFrame(
                list(stats['categories'].items()),
                columns=['Category', 'Count']
            ).sort_values('Count', ascending=False)
            st.dataframe(cat_df, hide_index=True, width="stretch")
        else:
            st.caption("No category distribution available yet.")

elif page == "Scan & Results":
    st.title("Scan & Results")

    st.markdown("""
    <div class="hero-banner">
        <div class="title">cBrain F2 Opportunity Radar</div>
        <div class="subtitle">
            <span class="pill">F2 Focus</span>
            <span class="pill">Open Tenders</span>
            <span class="pill">Live Sources</span>
            Opportunity monitoring and qualification pipeline.
        </div>
    </div>
    """, unsafe_allow_html=True)

    if st.session_state.get("last_scan_info"):
        info = st.session_state["last_scan_info"]
        st.caption(
            f"Last scan: {info.get('timestamp', 'n/a')} | "
            f"new tenders: {info.get('new_count', 0)} | "
            f"duration: {info.get('duration_s', 0):.1f}s"
        )
    
    # Check if a tender is selected for detail view
    if 'selected_tender' in st.session_state and st.session_state['selected_tender']:
        tender_id = st.session_state['selected_tender']
        with app.app_context():
            tender = TenderResult.query.get(tender_id)
            if tender:
                # Back button
                if st.button("Back to Results", key="back_from_detail"):
                    st.session_state['selected_tender'] = None
                    st.rerun()
                
                st.markdown("---")
                
                # Tender title with score (prefer translated if available)
                display_title = tender.title_translated if tender.title_translated and tender.title_translated != tender.title else tender.title
                score_color = "#10b981" if tender.score >= 70 else "#f59e0b" if tender.score >= 40 else "#ef4444"
                st.markdown(f"""
                <div style='padding: 1rem 1.25rem; background: var(--card-bg); border: 1px solid var(--border-color); border-radius: 10px; margin-bottom: 1rem;'>
                    <div style='display: flex; justify-content: space-between; align-items: center;'>
                        <h2 style='color: var(--text-primary); margin: 0; font-size: 1.3rem;'>{display_title}</h2>
                        <span style='background: {score_color}; color: white; padding: 6px 12px; border-radius: 8px; font-weight: 600; font-size: 1rem;'>{tender.score:.0f}%</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                # Details in columns
                col1, col2 = st.columns(2)
                
                with col1:
                    detail_deadline = _deadline_meta(tender.deadline)
                    st.markdown("### Basic Information")
                    st.markdown(f"**Category:** {tender.category or 'Uncategorized'}")
                    st.markdown(f"**Country:** {tender.country or 'Not specified'}")
                    st.markdown(f"**Lifecycle:** {_lifecycle_label(tender.timing_status)}")
                    st.markdown(f"**Deadline:** {tender.deadline or 'Not specified'}")
                    st.markdown(f"**Deadline Status:** {detail_deadline['label']}")
                    st.markdown(f"**Found on:** {tender.created_at.strftime('%Y-%m-%d %H:%M') if tender.created_at else 'Unknown'}")
                    
                    st.markdown("### Source")
                    st.link_button("View Original Tender", tender.link, width="stretch")
                
                with col2:
                    st.markdown("### Scoring Details")
                    st.markdown(f"**Match Score:** {tender.score:.1f}%")
                    st.markdown(f"**Confidence:** {(tender.confidence or 0) * 100:.0f}%")
                    
                    if tender.keywords_matched:
                        st.markdown("**Matched Keywords:**")
                        keywords = tender.keywords_matched.split(", ") if tender.keywords_matched else []
                        for kw in keywords[:10]:
                            st.markdown(f"- {kw}")
                        if len(keywords) > 10:
                            st.markdown(f"*...and {len(keywords) - 10} more*")
                
                st.markdown("---")
                
                # Description (prefer translated if available)
                st.markdown("### Description")
                display_description = tender.description_translated if tender.description_translated and tender.description_translated != tender.description else tender.description
                st.markdown(display_description or "No description available.")
                
                # Show original language notice if translated
                if tender.title_translated and tender.title_translated != tender.title:
                    st.markdown("---")
                    st.markdown("### Original Language")
                    with st.expander("View Original (Non-English)"):
                        st.markdown(f"**Original Title:** {tender.title}")
                        if tender.description and tender.description != tender.description_translated:
                            st.markdown(f"**Original Description:** {tender.description}")
                
                # Scoring breakdown
                if tender.scoring_breakdown:
                    st.markdown("### Scoring Breakdown")
                    try:
                        import json
                        breakdown = json.loads(tender.scoring_breakdown) if isinstance(tender.scoring_breakdown, str) else tender.scoring_breakdown
                        
                        if isinstance(breakdown, dict):
                            if 'unique_keywords' in breakdown:
                                st.markdown(f"**Keywords Found:** {breakdown.get('keywords_found', 0)} / {breakdown.get('total_keywords_in_system', 'N/A')}")
                            if 'matched_groups' in breakdown:
                                st.markdown("**Matched Categories:**")
                                for group in breakdown.get('matched_groups', []):
                                    st.markdown(f"- **{group.get('group', 'Unknown')}**: {group.get('count', 0)} keywords")
                    except:
                        st.code(tender.scoring_breakdown)
                
                st.markdown("---")
                
                # Action buttons
                col1, col2, col3 = st.columns(3)
                with col1:
                    fav_label = "Remove Favorite" if tender.favorite else "Add Favorite"
                    if st.button(fav_label, key="detail_fav", width="stretch"):
                        toggle_favorite(tender.id)
                        st.rerun()
                with col2:
                    save_label = "Unsave" if tender.saved else "Save"
                    if st.button(save_label, key="detail_save", width="stretch"):
                        toggle_saved(tender.id)
                        st.rerun()
                with col3:
                    if st.button("Back to Results", key="detail_back", width="stretch"):
                        st.session_state['selected_tender'] = None
                        st.rerun()
            else:
                st.error("Tender not found")
                st.session_state['selected_tender'] = None
    else:
        # Normal scan & results view
        col1, col2 = st.columns([3, 1])
    
        with col1:
            st.markdown("Scan and review opportunities.")
    
        with col2:
            if st.button("Run Scan", key="top_scan_button", type="primary", width="stretch"):
                started = time.time()
                with st.spinner("Scanning sources..."):
                    new_tenders = run_tender_scan()
                elapsed = time.time() - started
                st.session_state["last_scan_info"] = {
                    "timestamp": _utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
                    "new_count": len(new_tenders),
                    "duration_s": elapsed,
                }
                if new_tenders:
                    st.success(f"Scan completed. Found {len(new_tenders)} new tenders.")
                else:
                    st.info("Scan completed. No new tenders were found.")
                st.rerun()
    
        st.markdown("---")
    
        # Filters and Export
        col_filter, col_export = st.columns([4, 1])
    
        with col_filter:
            st.subheader("Filters")
    
        with col_export:
            # CSV Export button
            all_tenders_for_export = get_tenders()
            if all_tenders_for_export:
                csv_data = "Title,Link,Score,Category,Country,Deadline,Days_Left,Lifecycle,Priority,Procurement_Status,F2_Fit\n"
                for t in all_tenders_for_export:
                    d_meta = _deadline_meta(t.deadline)
                    days_left = "" if d_meta["days_left"] is None else int(d_meta["days_left"])
                    csv_data += f'"{t.title}","{t.link}",{t.score},"{t.category or ""}","{t.country or ""}","{t.deadline or ""}","{days_left}","{_lifecycle_label(t.timing_status)}","{t.priority_level or ""}","{t.procurement_status or ""}","{t.likely_fit_for_f2 or ""}"\n'
            
                st.download_button(
                    label="Export CSV",
                    data=csv_data,
                    file_name=f"tenders_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv",
                    help="Download all tenders as CSV"
                )
    
        # Row 1: Score, Category, Sort, Search
        col1, col2, col3, col4 = st.columns(4)
    
        with col1:
            min_score = st.slider("Minimum Score", 0, 100, 0, 5)
    
        with col2:
            all_tenders = get_tenders()
            categories = ["All"] + sorted(list(set([t.category for t in all_tenders if t.category]))) if all_tenders else ["All"]
            category = st.selectbox("Category", categories)
    
        with col3:
            sort_by = st.selectbox("Sort By", ["score", "date", "deadline"])
    
        with col4:
            search = st.text_input("Search", placeholder="Search titles...", help="Search in tender titles")
        
        # Row 2: Priority, Procurement, Lifecycle, Country, F2 Fit, Toggles
        col5, col6, col7, col8, col9, col10, col11, col12 = st.columns(8)
        
        with col5:
            priority_options = ["All", "HIGH", "MEDIUM", "LOW", "STRATEGIC", "CONDITIONAL", "LOCKED"]
            priority_filter = st.selectbox("Priority", priority_options, help="Filter by F2 priority level")
        
        with col6:
            status_options = ["All", "open", "locked", "locked_but_open", "conditional_nogo", "conditional_strategic", "conditional_discuss"]
            status_filter = st.selectbox("Procurement Status", status_options, help="Filter by platform lock-in status")
        
        with col7:
            lifecycle_options = ["All", "open", "pre_notice", "clarification", "awarded", "cancelled"]
            lifecycle_filter = st.selectbox("Lifecycle", lifecycle_options, help="Tender lifecycle status")

        with col8:
            countries = ["All"] + sorted(list(set([t.country for t in all_tenders if t.country and t.country != "Unknown"]))) if all_tenders else ["All"]
            country_filter = st.selectbox("Country", countries, help="Filter by country")

        with col9:
            f2_fit_options = ["All", "true", "strategic", "discuss", "uncertain", "conditional", "no-go"]
            f2_fit_filter = st.selectbox("F2 Fit", f2_fit_options, help="Filter by F2 fit likelihood")

        with col10:
            f2_only = st.checkbox("F2-only", value=True, help="Show only F2-relevant tenders.")

        with col11:
            open_only = st.checkbox("Open-only", value=True, help="Hide locked or no-go opportunities.")

        with col12:
            deadline_window = st.selectbox(
                "Deadline Window",
                ["All", "Next 7 days", "Next 14 days", "Next 30 days", "No deadline"],
                help="Filter tenders by submission deadline window."
            )

        # Get filtered tenders
        filters = {
            'min_score': min_score,
            'category': category,
            'sort_by': sort_by,
            'search': search,
            'priority': priority_filter,
            'status': status_filter,
            'lifecycle': lifecycle_filter,
            'country': country_filter,
            'f2_fit': f2_fit_filter,
            'f2_only': f2_only,
            'open_only': open_only,
        }
    
        tenders, applied_f2_only, fallback_message = get_tenders_with_fallback(filters)
        tenders = _apply_deadline_window(tenders, deadline_window)

        if sort_by == "deadline":
            tenders = sorted(
                tenders,
                key=lambda t: (_parse_deadline_value(getattr(t, "deadline", "")) is None, _parse_deadline_value(getattr(t, "deadline", "")) or datetime.max.date())
            )

        if fallback_message:
            st.warning(fallback_message)
        elif f2_only and not applied_f2_only:
            st.warning("No F2-only matches found. Displaying all results.")
        st.markdown(f"**{len(tenders)} tenders found**")
        st.markdown("---")
    
        # Display tenders (table-first)
        if tenders:
            table_tab, cards_tab = st.tabs(["Table View", "Card View"])

            with table_tab:
                table_rows = []
                for tender in tenders:
                    d_meta = _deadline_meta(tender.deadline)
                    title = tender.title_translated if tender.title_translated and tender.title_translated != tender.title else tender.title
                    table_rows.append({
                        "Title": title,
                        "Score": round(tender.score or 0, 1),
                        "Buyer": tender.buyer or "",
                        "Days Left": "" if d_meta["days_left"] is None else int(d_meta["days_left"]),
                        "Deadline": tender.deadline or "",
                        "Deadline Status": d_meta["label"],
                        "Lifecycle": _lifecycle_label(tender.timing_status),
                        "Country": tender.country or "",
                        "Category": tender.category or "",
                        "Priority": tender.priority_level or "",
                        "Procurement": tender.procurement_status or "",
                        "Added": tender.created_at.strftime("%Y-%m-%d") if tender.created_at else "",
                        "Link": tender.link,
                    })
                table_df = pd.DataFrame(table_rows)
                st.dataframe(table_df, hide_index=True, width="stretch")

            with cards_tab:
                for tender in tenders:
                    # Determine score styling (neutral enterprise palette)
                    if tender.score >= 70:
                        score_emoji = "HIGH"
                        score_color = "#1e3a8a"
                    elif tender.score >= 40:
                        score_emoji = "MED"
                        score_color = "#334155"
                    else:
                        score_emoji = "LOW"
                        score_color = "#475569"

                    # Clean simple card layout
                    with st.container():
                        # Header row (prefer translated title if available)
                        display_title = tender.title_translated if tender.title_translated and tender.title_translated != tender.title else tender.title
                        is_translated = tender.title_translated and tender.title_translated != tender.title
                        col_title, col_score = st.columns([5, 1])
                        deadline_meta = _deadline_meta(tender.deadline)
                        with col_title:
                            title_suffix = " [Translated]" if is_translated else ""
                            st.markdown(f"### {display_title}{title_suffix}")
                        with col_score:
                            st.markdown(f"<span style='background: {score_color}; color: white; padding: 0.5rem 1rem; border-radius: 8px; font-weight: 600;'>{score_emoji} {tender.score:.0f}%</span>", unsafe_allow_html=True)
                            if deadline_meta["style"] == "overdue":
                                st.markdown("<span style='background:#991b1b;color:white;padding:0.2rem 0.5rem;border-radius:6px;font-size:0.72rem;font-weight:600;'>OVERDUE</span>", unsafe_allow_html=True)
                            elif deadline_meta["style"] == "urgent":
                                st.markdown("<span style='background:#9a3412;color:white;padding:0.2rem 0.5rem;border-radius:6px;font-size:0.72rem;font-weight:600;'>URGENT</span>", unsafe_allow_html=True)
                            elif deadline_meta["style"] == "upcoming":
                                st.markdown("<span style='background:#1d4ed8;color:white;padding:0.2rem 0.5rem;border-radius:6px;font-size:0.72rem;font-weight:600;'>UPCOMING</span>", unsafe_allow_html=True)
                            elif deadline_meta["style"] == "scheduled":
                                st.markdown("<span style='background:#334155;color:white;padding:0.2rem 0.5rem;border-radius:6px;font-size:0.72rem;font-weight:600;'>SCHEDULED</span>", unsafe_allow_html=True)
                            else:
                                st.markdown("<span style='background:#6b7280;color:white;padding:0.2rem 0.5rem;border-radius:6px;font-size:0.72rem;font-weight:600;'>NO DEADLINE</span>", unsafe_allow_html=True)

                        # Tags row
                        tags = []
                        if tender.category and tender.category != "Unclassified":
                            tags.append(f"Category: {tender.category}")
                        if tender.country:
                            tags.append(f"Country: {tender.country}")
                        tags.append(f"Deadline: {deadline_meta['label']}")

                        if tags:
                            st.markdown(" | ".join(tags))

                        # Action buttons
                        col1, col2, col3, col4 = st.columns(4)

                        with col1:
                            fav_label = "Favorited" if tender.favorite else "Favorite"
                            if st.button(fav_label, key=f"fav_{tender.id}"):
                                toggle_favorite(tender.id)
                                st.rerun()

                        with col2:
                            save_label = "Saved" if tender.saved else "Save"
                            if st.button(save_label, key=f"save_{tender.id}"):
                                toggle_saved(tender.id)
                                st.rerun()

                        with col3:
                            st.link_button("View Source", tender.link)

                        with col4:
                            if st.button("Details", key=f"detail_{tender.id}"):
                                st.session_state['selected_tender'] = tender.id
                                st.rerun()

                        st.markdown("---")
        else:
            st.info("No results match the selected filters.")

elif page == "Sources":
    st.title("Tender Sources")
    
    tab1, tab2 = st.tabs(["Manage Sources", "Add New Source"])
    
    with tab1:
        sources = get_sources()
        
        if sources:
            for source in sources:
                with st.container():
                    col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
                    
                    with col1:
                        status = "Active" if source.active else "Inactive"
                        fav = "" if source.favorite else ""
                        st.markdown(f"**{source.name}** {status} {fav}")
                        st.caption(source.url)
                    
                    with col2:
                        toggle_label = "Disable" if source.active else "Enable"
                        if st.button(toggle_label, key=f"toggle_{source.id}", width="stretch"):
                            toggle_source(source.id)
                            st.success(f"Source {'disabled' if source.active else 'enabled'}!")
                            st.rerun()
                    
                    with col3:
                        st.link_button("Visit", source.url, width="stretch")
                    
                    with col4:
                        if st.button("Delete", key=f"del_{source.id}"):
                            delete_source(source.id)
                            st.success("Source deleted.")
                            st.rerun()
                    
                    st.markdown("---")
        else:
            st.warning("No sources configured.")
            st.info("Use 'Add New Source' to configure your first tender source.")
    
    with tab2:
        st.markdown("### Add New Tender Source")
        
        with st.form("add_source_form"):
            name = st.text_input("Source Name", placeholder="e.g., UNDP Kenya")
            url = st.text_input("Source URL", placeholder="https://...")
            
            submitted = st.form_submit_button("Add Source", type="primary")
            
            if submitted:
                if name and url:
                    if url.startswith('http://') or url.startswith('https://'):
                        if add_source(name, url):
                            st.success(f"Added source: {name}")
                            st.rerun()
                        else:
                            st.warning("Source already exists (same URL).")
                    else:
                        st.error("URL must start with http:// or https://")
                else:
                    st.error("Please provide both name and URL")

elif page == "Favorites":
    st.title("Favorite Tenders")
    
    filters = {'favorites_only': True, 'sort_by': 'score'}
    tenders = get_tenders(filters)
    
    st.markdown(f"**{len(tenders)} favorite tenders**")
    st.markdown("---")
    
    if tenders:
        for tender in tenders:
            score_color = "#10b981" if tender.score >= 70 else "#f59e0b" if tender.score >= 40 else "#ef4444"
            
            with st.expander(f"**[{tender.score:.1f}%]** {tender.title}"):
                col1, col2 = st.columns([3, 1])
                
                with col1:
                    st.markdown(f"**Category:** {tender.category}")
                    st.markdown(f"**Description:** {tender.description[:200]}...")
                    st.link_button("View Original", tender.link)
                
                with col2:
                    st.markdown(f"**Score:** <span style='color:{score_color};'>{tender.score:.1f}%</span>", unsafe_allow_html=True)
                    
                    if st.button("Remove from Favorites", key=f"unfav_{tender.id}"):
                        toggle_favorite(tender.id)
                        st.rerun()
    else:
        st.info("No favorite tenders yet. Mark tenders as favorites from the Scan & Results page.")

elif page == "Saved":
    st.title("Saved Tenders")
    
    filters = {'saved_only': True, 'sort_by': 'score'}
    tenders = get_tenders(filters)
    
    st.markdown(f"**{len(tenders)} saved tenders**")
    st.markdown("---")
    
    if tenders:
        for tender in tenders:
            score_color = "#10b981" if tender.score >= 70 else "#f59e0b" if tender.score >= 40 else "#ef4444"
            
            with st.expander(f"**[{tender.score:.1f}%]** {tender.title}"):
                col1, col2 = st.columns([3, 1])
                
                with col1:
                    st.markdown(f"**Category:** {tender.category}")
                    st.markdown(f"**Description:** {tender.description[:200]}...")
                    st.link_button("View Original", tender.link)
                
                with col2:
                    st.markdown(f"**Score:** <span style='color:{score_color};'>{tender.score:.1f}%</span>", unsafe_allow_html=True)
                    
                    if st.button("Remove from Saved", key=f"unsave_{tender.id}"):
                        toggle_saved(tender.id)
                        st.rerun()
    else:
        st.info("No saved tenders yet. Save tenders from the Scan & Results page for later review.")

elif page == "Settings":
    st.title("Settings")
    
    with app.app_context():
        settings = AppSettings.query.first()

        st.subheader("Maintenance")
        col_m1, col_m2 = st.columns(2)
        with col_m1:
            if st.button("Run Translation Pass", key="run_translation_pass"):
                maybe_translate_untranslated_tenders(force=True, limit=30, cooldown_seconds=0)
                st.success("Translation pass completed.")
        with col_m2:
            if st.button("Clean Closed/Awarded", key="run_cleanup_closed"):
                cleanup_irrelevant_tenders()
                st.success("Closed/awarded tenders cleanup completed.")
        st.markdown("---")
        
        # Install App Section
        st.markdown("""
            <div style='padding: 1rem 1.25rem; background: var(--card-bg); border: 1px solid var(--border-color); border-radius: 10px; margin-bottom: 1rem;'>
                <div style='color: var(--text-primary); font-weight: 700; font-size: 1.05rem;'>Install TenderWatch</div>
                <div style='color: var(--text-secondary); font-size: 0.9rem; margin-top: 0.25rem;'>Add to your home screen for quick access.</div>
            </div>
        """, unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("""
            **Mobile (Android/iOS):**
            1. Open this app in Chrome/Safari
            2. Tap the **Share** button (iOS) or browser menu (Android)
            3. Select **"Add to Home Screen"**
            4. The app icon will appear on your home screen!
            """)
        
        with col2:
            st.markdown("""
            **Desktop (Chrome/Edge):**
            1. Look for the install button in the address bar
            2. Or click the floating install button (bottom-right)
            3. Click **"Install"** when prompted
            4. TenderWatch will open as a standalone app!
            """)
        
        st.markdown("---")
        
        # Daily Notifications Section
        st.markdown("""
            <div style='padding: 1rem 1.25rem; background: var(--card-bg); border: 1px solid var(--border-color); border-radius: 10px; margin-bottom: 1rem;'>
                <div style='color: var(--text-primary); font-weight: 700; font-size: 1.05rem;'>Daily Scan Reminders</div>
                <div style='color: var(--text-secondary); font-size: 0.9rem; margin-top: 0.25rem;'>Configure a daily reminder to review new tenders.</div>
            </div>
        """, unsafe_allow_html=True)
        
        st.markdown("""
        **How it works:**
        - Click the notification setup button below
        - Choose your preferred time (e.g., 8:00 AM)
        - You'll receive a notification every day to scan for new tenders
        - Works on both mobile and desktop (after installing the app)
        
        **Tips:**
        - For best results, **install the app** first
        - Allow notifications when your browser asks
        - Notifications work even when the browser is closed (on supported devices)
        """)
        
        # JavaScript button for notification setup
        st.markdown("""
        <div style='text-align: center; margin: 1rem 0;'>
            <button onclick="window.TenderWatchPWA && window.TenderWatchPWA.setupNotifications()" 
                    style='background: #1d4ed8; 
                           color: white; 
                           border: none; 
                           padding: 12px 32px; 
                           border-radius: 8px; 
                           font-size: 1rem; 
                           font-weight: 600; 
                           cursor: pointer;
                           box-shadow: 0 4px 12px rgba(16, 185, 129, 0.4);'>
                 Set Up Daily Notifications
            </button>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("---")
        
        # Notification Settings
        st.subheader("Notification Preferences")
        
        notification_enabled = st.checkbox("Enable In-App Notifications", 
                                          value=settings.notifications_enabled if settings and hasattr(settings, 'notifications_enabled') else False,
                                          help="Show notifications for high-score tenders during scans")
        
        min_score = st.slider("Minimum Score for Alerts", 0, 100, 
                             value=int(settings.min_score_to_notify) if settings else 70,
                             help="Only alert for tenders above this score")
        
        st.markdown("---")
        
        # Email Notification Settings
        st.subheader("Email Notifications")
        
        email_enabled = st.checkbox("Enable Email Notifications", 
                                   value=settings.notify_email if settings and hasattr(settings, 'notify_email') else False,
                                   help="Send email alerts for high-score tenders")
        
        if email_enabled:
            st.info("Email notifications will be sent for new tenders above the configured score threshold.")
            
            col1, col2 = st.columns(2)
            
            with col1:
                email_recipients = st.text_area("Recipients (comma-separated)", 
                                               value=settings.email_recipients if settings and hasattr(settings, 'email_recipients') else "",
                                               placeholder="email1@example.com, email2@example.com",
                                               help="Enter email addresses separated by commas")
                
                smtp_server = st.text_input("SMTP Server",
                                           value=settings.smtp_server if settings and hasattr(settings, 'smtp_server') else "smtp.gmail.com",
                                           placeholder="smtp.gmail.com")
            
            with col2:
                smtp_port = st.number_input("SMTP Port",
                                           value=settings.smtp_port if settings and hasattr(settings, 'smtp_port') else 587,
                                           min_value=1, max_value=65535)
                
                smtp_username = st.text_input("SMTP Username",
                                             value=settings.smtp_username if settings and hasattr(settings, 'smtp_username') else "",
                                             placeholder="your.email@gmail.com")
                
                smtp_password = st.text_input("SMTP Password", 
                                             type="password",
                                             value="",
                                             placeholder="App Password (not regular password)",
                                             help="For Gmail, use an App Password from your Google Account settings")
            
            # Test email button
            if st.button("Send Test Email", key="test_email_btn"):
                if smtp_username and smtp_password and email_recipients:
                    try:
                        from app.notifications import send_email_notification
                        
                        # Create a mock tender for testing
                        class MockTender:
                            def __init__(self):
                                self.title = "TEST: Sample Tender Title"
                                self.title_translated = "TEST: Sample Tender Title"
                                self.score = 85.0
                                self.category = "Case & Complaint Management"
                                self.buyer = "Test Organization"
                                self.country = "Kenya"
                                self.deadline = "2025-12-31"
                                self.link = "https://example.com/tender/123"
                        
                        # Create mock settings with current values
                        class MockSettings:
                            pass
                        
                        mock_settings = MockSettings()
                        mock_settings.email_recipients = email_recipients
                        mock_settings.smtp_server = smtp_server
                        mock_settings.smtp_port = smtp_port
                        mock_settings.smtp_username = smtp_username
                        mock_settings.smtp_password = smtp_password
                        
                        # Send test email
                        success = send_email_notification(mock_settings, [MockTender()])
                        if success:
                            st.success("Test email sent successfully.")
                        else:
                            st.error("Failed to send test email. Verify SMTP settings.")
                    except Exception as e:
                        st.error(f"Error: {str(e)}")
                else:
                    st.warning("Please provide SMTP settings and recipients first.")
        
        st.markdown("---")
        
        # Save button
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            if st.button("Save Settings", key="save_settings_button", type="primary", width="stretch"):
                if settings:
                    settings.notifications_enabled = notification_enabled
                    settings.min_score_to_notify = float(min_score)
                    settings.notify_email = email_enabled if 'email_enabled' in dir() else False
                    if email_enabled:
                        settings.email_recipients = email_recipients
                        settings.smtp_server = smtp_server
                        settings.smtp_port = smtp_port
                        settings.smtp_username = smtp_username
                        if smtp_password:
                            settings.smtp_password = smtp_password
                    db.session.commit()
                    st.success("Settings saved.")
                else:
                    new_settings = AppSettings(
                        notifications_enabled=notification_enabled,
                        min_score_to_notify=float(min_score),
                        notify_email=email_enabled if 'email_enabled' in dir() else False
                    )
                    if email_enabled:
                        new_settings.email_recipients = email_recipients
                        new_settings.smtp_server = smtp_server
                        new_settings.smtp_port = smtp_port
                        new_settings.smtp_username = smtp_username
                        if smtp_password:
                            new_settings.smtp_password = smtp_password
                    db.session.add(new_settings)
                    db.session.commit()
                    st.success("Settings saved.")
        
        st.markdown("---")
        
        # ML Learning Section
        st.subheader("Machine Learning")
        st.markdown("""
        TenderWatch learns from your saved and favorited tenders to improve relevance scoring.
        The more tenders you save, the smarter it gets!
        """)
        
        # Show ML status
        try:
            from app.ml_ranker import get_model_status, train_ranker_model, update_golden_embeddings
            
            ml_status = get_model_status()
            
            col1, col2, col3 = st.columns(3)
            with col1:
                status_icon = "" if ml_status.get('sentence_model_loaded') else ""
                st.metric("Sentence Model", status_icon)
            with col2:
                status_icon = "" if ml_status.get('ranker_model_loaded') else ""
                st.metric("Ranker Model", status_icon)
            with col3:
                st.metric("Golden Tenders", ml_status.get('golden_tenders_count', 0))
            
            if ml_status.get('ranker_trained_at'):
                st.caption(f"Model trained: {ml_status['ranker_trained_at'][:10]} on {ml_status.get('ranker_positive_count', 0)} positive samples")
            
            # Train button
            col1, col2 = st.columns(2)
            with col1:
                if st.button(" Update Golden Embeddings", help="Update semantic model with saved/favorited tenders"):
                    with st.spinner("Updating embeddings..."):
                        success = update_golden_embeddings()
                        if success:
                            st.success("Golden embeddings updated.")
                        else:
                            st.warning("No saved or favorited tenders available for learning.")
            
            with col2:
                if st.button("Train Ranker Model", help="Train ML model to rank tenders based on your preferences"):
                    with st.spinner("Training model..."):
                        success, message = train_ranker_model()
                        if success:
                            st.success(message)
                        else:
                            st.warning(message)
        
        except ImportError as e:
            st.warning(f"ML features not available: {e}")
            st.caption("Install with: pip install sentence-transformers lightgbm")
        except Exception as e:
            st.error(f"ML error: {e}")
        
        st.markdown("---")
        
        st.subheader("Database Statistics")
        stats = get_stats()
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Total Tenders in Database", stats['total'])
            st.metric("Active Sources", stats['active_sources'])
        
        with col2:
            st.metric("Saved Tenders", stats['saved'])
            st.metric("Favorite Tenders", stats['favorites'])
        
        st.markdown("---")
        
        st.subheader("About")
        st.markdown("""
        **TenderWatch v2.0** - Streamlit Edition
        
        Automated tender scanning and opportunity tracking for cBrain's F2 platform.
        
        - Intelligent keyword-based scoring
        - Automatic categorization
        - Multi-source scanning
        - Persistent storage
        - Installable as app (PWA)
        - Daily notification reminders
        
        For support, see the documentation.
        """)

