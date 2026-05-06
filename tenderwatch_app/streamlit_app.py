"""TenderWatch Streamlit UI.

A simple professional workspace for finding cBrain F2-fit tenders.
"""

from __future__ import annotations

import html
import json
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

import streamlit as st
from sqlalchemy import func

from app import create_app  # type: ignore[attr-defined]
from app.extensions import db  # type: ignore[attr-defined]
from app.models import AppSettings, SourceHealth, TenderResult, TenderSource  # type: ignore[attr-defined]
from app.scraper import run_scan

try:
    from app.scraper import cleanup_irrelevant_tenders
except Exception:
    cleanup_irrelevant_tenders = None


BASE_DIR = Path(__file__).resolve().parent
app = create_app(start_scheduler=False)

st.set_page_config(
    page_title="TenderWatch - cBrain F2",
    page_icon="TW",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
<link rel="manifest" href="/static/manifest.json">
<link rel="apple-touch-icon" href="/static/icon-192.png">
<meta name="theme-color" content="#efe2d3">
<script src="/static/pwa.js" defer></script>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <style>
    :root {
        --bg: #efe2d3;
        --bg-soft: #f7efe4;
        --panel: #fff8f1;
        --panel-strong: #f4e6d7;
        --text: #1e140e;
        --muted: #3f3027;
        --line: #b99d84;
        --accent: #8f4a2f;
        --accent-strong: #6f3825;
        --accent-soft: #ead1c1;
        --good: #29451f;
        --watch: #5c360d;
        --bad: #6f241c;
    }

    html, body, .stApp, [class*="css"] {
        font-family: Inter, "Segoe UI", Arial, sans-serif;
        color: var(--text) !important;
    }

    p, span, label, li, div, h1, h2, h3, h4, h5, h6,
    [data-testid="stMarkdownContainer"],
    [data-testid="stCaptionContainer"],
    [data-testid="stMetricLabel"],
    [data-testid="stMetricValue"],
    [data-testid="stWidgetLabel"],
    [data-testid="stSidebar"] * {
        color: var(--text) !important;
    }

    [data-testid="stCaptionContainer"],
    [data-testid="stCaptionContainer"] *,
    .stCaption,
    small {
        color: var(--muted) !important;
    }

    .stApp {
        background: var(--bg);
    }

    [data-testid="stHeader"] {
        background: rgba(247, 239, 228, 0.96);
        border-bottom: 1px solid var(--line);
    }

    [data-testid="stSidebar"] {
        background: #e7d6c4;
        border-right: 1px solid var(--line);
    }

    .block-container {
        max-width: 1180px;
        padding-top: 1.2rem;
        padding-bottom: 2.2rem;
    }

    .app-title {
        margin: 0 0 0.2rem;
        font-size: 1.45rem;
        line-height: 1.25;
        font-weight: 780;
        color: var(--text);
    }

    .app-subtitle {
        margin: 0 0 1.1rem;
        color: var(--muted) !important;
        font-size: 0.94rem;
        line-height: 1.5;
    }

    .panel {
        border: 1px solid var(--line);
        background: var(--panel);
        border-radius: 8px;
        padding: 1rem;
        margin-bottom: 0.9rem;
    }

    .section-title {
        margin: 0 0 0.2rem;
        font-size: 1rem;
        font-weight: 760;
    }

    .section-subtitle {
        margin: 0;
        color: var(--muted) !important;
        font-size: 0.86rem;
        line-height: 1.45;
    }

    .tender-card {
        border: 1px solid var(--line);
        background: var(--panel);
        border-radius: 8px;
        padding: 0.95rem 1rem;
        margin-bottom: 0.75rem;
    }

    .tender-title {
        margin: 0;
        font-size: 1rem;
        line-height: 1.4;
        font-weight: 760;
    }

    .tender-meta {
        margin-top: 0.45rem;
        color: var(--muted) !important;
        font-size: 0.82rem;
        line-height: 1.45;
    }

    .badge {
        display: inline-block;
        border: 1px solid var(--line);
        border-radius: 999px;
        padding: 0.16rem 0.52rem;
        margin-right: 0.35rem;
        font-size: 0.74rem;
        font-weight: 720;
        background: #f6eadf;
    }

    .badge-good { color: var(--good) !important; background: #e4eadb; border-color: #9ead8c; }
    .badge-watch { color: var(--watch) !important; background: #f4e4cf; border-color: #c59d68; }
    .badge-bad { color: var(--bad) !important; background: #f1ddd7; border-color: #c4978c; }
    .badge-neutral { color: #2f2118 !important; background: var(--accent-soft); border-color: #bd947e; }

    .stButton > button {
        border-radius: 8px;
        border: 1px solid #c6ad96;
        background: #fff8f1;
        color: var(--text);
        min-height: 2.3rem;
        font-weight: 700;
    }

    .stButton > button[kind="primary"] {
        background: var(--accent);
        border-color: var(--accent-strong);
        color: #fff8f1;
    }

    .stButton > button[kind="primary"] *,
    .stButton > button[kind="primary"] p,
    .stButton > button[kind="primary"] span {
        color: #fff8f1 !important;
    }

    input, textarea, select,
    div[data-baseweb="select"] > div,
    div[data-baseweb="base-input"] {
        background: #fffaf5 !important;
        color: var(--text) !important;
        border-color: var(--line) !important;
    }

    div[data-baseweb="select"] *,
    div[data-baseweb="base-input"] *,
    div[data-baseweb="select"] svg {
        color: var(--text) !important;
        fill: var(--muted) !important;
    }

    div[data-baseweb="popover"],
    div[data-baseweb="popover"] > div,
    div[data-baseweb="menu"],
    ul[role="listbox"],
    div[role="listbox"] {
        background: var(--panel) !important;
        border-color: var(--line) !important;
        color: var(--text) !important;
        box-shadow: 0 12px 28px rgba(70, 48, 32, 0.18) !important;
    }

    div[data-baseweb="popover"] *,
    div[data-baseweb="menu"] *,
    ul[role="listbox"] *,
    div[role="listbox"] *,
    li[role="option"],
    div[role="option"] {
        color: var(--text) !important;
    }

    li[role="option"],
    div[role="option"] {
        background: var(--panel) !important;
    }

    li[role="option"]:hover,
    div[role="option"]:hover,
    li[role="option"][aria-selected="true"],
    div[role="option"][aria-selected="true"] {
        background: var(--accent-soft) !important;
        color: var(--text) !important;
    }

    input::placeholder,
    textarea::placeholder {
        color: #6c5848 !important;
        opacity: 1 !important;
    }

    button[data-baseweb="tab"],
    button[data-baseweb="tab"] * {
        color: var(--text) !important;
    }

    [data-testid="stMetric"] {
        border: 1px solid var(--line);
        background: var(--panel);
        border-radius: 8px;
        padding: 0.85rem;
    }

    [data-testid="stMetricValue"] {
        font-size: 1.45rem !important;
        font-weight: 780;
    }

    div[data-baseweb="tab-list"] {
        gap: 0.25rem;
        border-bottom: 1px solid var(--line);
    }

    button[data-baseweb="tab"] {
        border-radius: 8px 8px 0 0 !important;
        font-weight: 700 !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _safe(value: object) -> str:
    return html.escape(str(value or ""))


def _parse_json_list(value: str | None) -> list[str]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
        if isinstance(parsed, list):
            return [str(x) for x in parsed if str(x).strip()]
    except Exception:
        pass
    return []


def bootstrap_once() -> None:
    if st.session_state.get("_bootstrapped"):
        return
    with app.app_context():
        db.create_all()
        if not AppSettings.query.first():
            settings = AppSettings()  # type: ignore[call-arg]
            settings.include_global_sources = True
            settings.include_global_in_default_shortlist = False
            settings.auto_discovery_enabled = False
            settings.results_per_query = 8
            db.session.add(settings)
            db.session.commit()

        if TenderSource.query.count() == 0:
            try:
                from init_sources import DEFAULT_SOURCES  # type: ignore[import]
            except Exception:
                DEFAULT_SOURCES = []
            favorite_names = {
                "ICT Authority",
                "Kenya PPIP",
                "UNDP Procurement Notices",
                "UN Global Marketplace",
                "UNOPS Opportunities",
                "World Bank Procurement",
                "AfDB Procurement",
                "TradeMark Africa Procurement",
            }
            for name, url, source_group in DEFAULT_SOURCES:
                db.session.add(
                    TenderSource(  # type: ignore[call-arg]
                        name=name,
                        url=url,
                        active=True,
                        favorite=name in favorite_names,
                        source_group=source_group,
                        source_tags=json.dumps([source_group]),
                    )
                )
            db.session.commit()
    st.session_state["_bootstrapped"] = True


def get_settings() -> AppSettings:
    with app.app_context():
        settings = AppSettings.query.first()
        if not settings:
            settings = AppSettings()  # type: ignore[call-arg]
            db.session.add(settings)
            db.session.commit()
        return settings


def lane_for_tender(tender: TenderResult) -> str:
    rec = (tender.recommendation or "").upper()
    priority = (tender.priority_level or "").upper()
    fit = (tender.likely_fit_for_f2 or "").lower()
    status = (tender.procurement_status or "").lower()

    if rec == "NO-GO" or status in {"locked", "conditional_nogo", "excluded"}:
        return "Rejected"
    if rec in {"GO", "PURSUE"} or priority == "HIGH" or fit in {"true", "yes"}:
        return "Qualified"
    if rec == "REVIEW":
        return "Watchlist"
    return "Rejected"


def get_stats() -> dict[str, int]:
    with app.app_context():
        tenders = TenderResult.query.all()
        qualified = sum(1 for t in tenders if lane_for_tender(t) == "Qualified")
        watchlist = sum(1 for t in tenders if lane_for_tender(t) == "Watchlist")
        rejected = sum(1 for t in tenders if lane_for_tender(t) == "Rejected")
        saved = TenderResult.query.filter(TenderResult.saved.is_(True)).count()
        active_sources = TenderSource.query.filter(TenderSource.active.is_(True)).count()
        due_soon = 0
        today = datetime.utcnow().date()
        for tender in tenders:
            if lane_for_tender(tender) == "Rejected" or not tender.deadline:
                continue
            try:
                deadline = datetime.strptime(str(tender.deadline)[:10], "%Y-%m-%d").date()
            except Exception:
                continue
            if 0 <= (deadline - today).days <= 14:
                due_soon += 1
        return {
            "qualified": qualified,
            "watchlist": watchlist,
            "rejected": rejected,
            "saved": int(saved),
            "active_sources": int(active_sources),
            "due_soon": due_soon,
        }


def get_region_options() -> list[str]:
    with app.app_context():
        values = set()
        for column in (
            TenderResult.region,
            TenderResult.buyer_region,
            TenderResult.implementation_region,
            TenderResult.target_beneficiary_region,
        ):
            rows = db.session.query(column).distinct().all()
            for (value,) in rows:
                cleaned = (value or "").strip()
                if cleaned:
                    values.add(cleaned)
        return sorted(values, key=lambda value: value.lower())


def get_tenders(
    *,
    lane: str = "Active",
    search: str = "",
    region_filter: str = "",
    min_score: float = 0,
    days_window: int | None = 90,
    saved_only: bool = False,
    limit: int = 250,
) -> list[TenderResult]:
    with app.app_context():
        query = TenderResult.query
        if days_window is not None:
            query = query.filter(TenderResult.created_at >= _utcnow() - timedelta(days=days_window))
        if saved_only:
            query = query.filter(TenderResult.saved.is_(True))
        if min_score > 0:
            query = query.filter(TenderResult.score >= float(min_score))
        if search:
            term = f"%{search.strip()}%"
            query = query.filter(
                TenderResult.title.ilike(term)
                | TenderResult.description.ilike(term)
                | TenderResult.buyer.ilike(term)
                | TenderResult.keywords_matched.ilike(term)
            )
        if region_filter:
            region = region_filter.strip().lower()
            query = query.filter(
                (func.lower(TenderResult.region) == region)
                | (func.lower(TenderResult.buyer_region) == region)
                | (func.lower(TenderResult.implementation_region) == region)
                | (func.lower(TenderResult.target_beneficiary_region) == region)
            )
        rows = (
            query.order_by(TenderResult.score.desc(), TenderResult.ranking_score.desc(), TenderResult.created_at.desc())
            .limit(max(1, int(limit)))
            .all()
        )

    deduped: dict[str, TenderResult] = {}
    for tender in rows:
        key = (tender.link or "").strip().lower()
        if not key:
            continue
        old = deduped.get(key)
        if old is None or float(tender.score or 0) > float(old.score or 0):
            deduped[key] = tender

    out = list(deduped.values())
    if lane == "Active":
        return [t for t in out if lane_for_tender(t) in {"Qualified", "Watchlist"}]
    if lane == "Saved":
        return out
    return [t for t in out if lane_for_tender(t) == lane]


def run_scan_now(depth: str) -> int:
    depth_map = {
        "Quick": {"max_sources": 20, "timeout": 90},
        "Standard": {"max_sources": 40, "timeout": 180},
        "Deep": {"max_sources": 9999, "timeout": 300},
    }
    cfg = depth_map.get(depth, depth_map["Quick"])
    with app.app_context():
        rows = run_scan(
            flask_app=app,
            max_sources=cfg["max_sources"],
            scan_timeout_seconds=cfg["timeout"],
            discovery_mode="manual_like",
        )
    return int(len(rows or []))


def toggle_saved(tender_id: int) -> None:
    with app.app_context():
        tender = TenderResult.query.get(int(tender_id))
        if tender:
            tender.saved = not bool(tender.saved)
            db.session.commit()


def toggle_favorite(tender_id: int) -> None:
    with app.app_context():
        tender = TenderResult.query.get(int(tender_id))
        if tender:
            tender.favorite = not bool(tender.favorite)
            db.session.commit()


def get_sources() -> list[TenderSource]:
    with app.app_context():
        return TenderSource.query.order_by(TenderSource.favorite.desc(), TenderSource.active.desc(), TenderSource.name.asc()).all()


def add_source(name: str, url: str, group: str) -> tuple[bool, str]:
    name = (name or "").strip()
    url = (url or "").strip()
    if not name or not url:
        return False, "Name and URL are required."
    if not url.startswith(("http://", "https://")):
        return False, "URL must start with http:// or https://."

    with app.app_context():
        existing = TenderSource.query.filter(func.lower(TenderSource.url) == url.lower()).first()
        if existing:
            return False, "That source already exists."
        source = TenderSource(  # type: ignore[call-arg]
            name=name,
            url=url,
            active=True,
            favorite=False,
            source_group=group,
            source_tags=json.dumps([group]),
        )
        db.session.add(source)
        db.session.commit()
    return True, "Source added."


def toggle_source(source_id: int, field: str) -> None:
    with app.app_context():
        source = TenderSource.query.get(int(source_id))
        if not source:
            return
        if field == "active":
            source.active = not bool(source.active)
        elif field == "favorite":
            source.favorite = not bool(source.favorite)
        db.session.commit()


def delete_source(source_id: int) -> None:
    with app.app_context():
        source = TenderSource.query.get(int(source_id))
        if source:
            db.session.delete(source)
            db.session.commit()


def get_health_rows() -> list[SourceHealth]:
    with app.app_context():
        return SourceHealth.query.order_by(SourceHealth.last_scan_at.desc()).limit(12).all()


def save_basic_settings(
    *,
    auto_discovery_enabled: bool,
    include_global_sources: bool,
    results_per_query: int,
    discovery_queries: Iterable[str],
) -> None:
    with app.app_context():
        settings = AppSettings.query.first()
        if not settings:
            settings = AppSettings()  # type: ignore[call-arg]
            db.session.add(settings)
        settings.auto_discovery_enabled = bool(auto_discovery_enabled)
        settings.include_global_sources = bool(include_global_sources)
        settings.results_per_query = int(results_per_query)
        settings.discovery_queries = json.dumps([q.strip() for q in discovery_queries if q.strip()])
        db.session.commit()


def render_page_title(title: str, subtitle: str) -> None:
    st.markdown(f"<h1 class='app-title'>{_safe(title)}</h1>", unsafe_allow_html=True)
    st.markdown(f"<p class='app-subtitle'>{_safe(subtitle)}</p>", unsafe_allow_html=True)


def render_panel(title: str, subtitle: str = "") -> None:
    st.markdown(
        f"""
        <div class="panel">
            <p class="section-title">{_safe(title)}</p>
            <p class="section-subtitle">{_safe(subtitle)}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_tender_card(tender: TenderResult) -> None:
    lane = lane_for_tender(tender)
    score = float(tender.score or 0)
    badge_class = "badge-good" if lane == "Qualified" else "badge-watch" if lane == "Watchlist" else "badge-bad"
    score_class = "badge-good" if score >= 70 else "badge-watch" if score >= 35 else "badge-neutral"
    domains = _parse_json_list(getattr(tender, "inferred_domains", "") or "")
    deadline = tender.deadline or "Not stated"
    buyer = tender.buyer or tender.country or "Unknown buyer"
    description = (tender.description_translated or tender.description or "").strip()
    if len(description) > 260:
        description = description[:260].rstrip() + "..."

    st.markdown(
        f"""
        <div class="tender-card">
            <p class="tender-title">{_safe(tender.title)}</p>
            <div class="tender-meta">
                <span class="badge {badge_class}">{_safe(lane)}</span>
                <span class="badge {score_class}">F2 score {score:.0f}</span>
                <span class="badge badge-neutral">Deadline: {_safe(deadline)}</span>
            </div>
            <div class="tender-meta">{_safe(buyer)} | {_safe(tender.category or "Unclassified")}</div>
            <div class="tender-meta">{_safe(description)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    cols = st.columns([1.2, 1.2, 1.2, 4])
    with cols[0]:
        st.link_button("Open", tender.link or "#", use_container_width=True)
    with cols[1]:
        if st.button("Save" if not tender.saved else "Unsave", key=f"save_{tender.id}", use_container_width=True):
            toggle_saved(int(tender.id))
            st.rerun()
    with cols[2]:
        if st.button("Star" if not tender.favorite else "Unstar", key=f"fav_{tender.id}", use_container_width=True):
            toggle_favorite(int(tender.id))
            st.rerun()
    with cols[3]:
        if domains:
            st.caption("F2 domains: " + ", ".join(domains[:6]))
        elif tender.qualification_reason:
            st.caption(tender.qualification_reason)


def render_tender_list(tenders: list[TenderResult]) -> None:
    if not tenders:
        st.info("No matching F2-fit tenders right now.")
        return
    for tender in tenders:
        render_tender_card(tender)


bootstrap_once()

PAGES = ["Overview", "Scan", "Shortlist", "Sources", "Settings"]

with st.sidebar:
    st.markdown("### TenderWatch")
    st.caption("Simple F2 tender monitoring")
    page = st.radio("Navigation", PAGES, label_visibility="collapsed")
    st.divider()
    stats = get_stats()
    st.caption(f"Qualified: {stats['qualified']}")
    st.caption(f"Watchlist: {stats['watchlist']}")
    st.caption(f"Active sources: {stats['active_sources']}")


if page == "Overview":
    stats = get_stats()
    render_page_title("F2 Tender Desk", "A focused view of tenders that look relevant to cBrain F2.")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Qualified", stats["qualified"])
    m2.metric("Watchlist", stats["watchlist"])
    m3.metric("Due soon", stats["due_soon"])
    m4.metric("Saved", stats["saved"])

    render_panel("Best current opportunities", "Only tenders with enough F2 signal are shown here.")
    render_tender_list(get_tenders(lane="Active", days_window=90, limit=8))

    with st.expander("What qualifies as F2-fit?"):
        st.markdown(
            """
            TenderWatch now prioritizes records management, document management,
            workflow automation, case handling, correspondence/registry, licensing,
            service delivery processes, and public-sector administrative platforms.

            Generic ICT, websites, infrastructure, hardware, campaigns, and broad
            digital transformation items are rejected unless they contain a clear
            F2-style process or records need.
            """
        )

elif page == "Scan":
    render_page_title("Run Scan", "Scan active sources and keep only tenders with credible F2 fit.")

    c1, c2 = st.columns([1, 2])
    with c1:
        depth = st.selectbox("Scan depth", ["Quick", "Standard", "Deep"], index=0)
    with c2:
        st.markdown("<div style='height: 1.75rem'></div>", unsafe_allow_html=True)
        if st.button("Run scan", type="primary", use_container_width=True):
            started = time.time()
            with st.spinner("Scanning sources and applying F2 fit rules..."):
                new_count = run_scan_now(depth)
            elapsed = time.time() - started
            stats = get_stats()
            st.success(
                f"Scan finished in {elapsed:.1f}s. Added {new_count} new tender(s). "
                f"Active shortlist now has {stats['qualified'] + stats['watchlist']} item(s)."
            )

    render_panel("Latest active results", "Fresh qualified and watchlist tenders appear below.")
    region_options = ["All regions"] + get_region_options()
    selected_region = st.selectbox("Region", region_options, index=0)
    render_tender_list(
        get_tenders(
            lane="Active",
            region_filter="" if selected_region == "All regions" else selected_region,
            days_window=90,
            limit=20,
        )
    )

    health_rows = get_health_rows()
    if health_rows:
        with st.expander("Recent source health"):
            for row in health_rows:
                status = row.last_status or "unknown"
                st.caption(f"{row.source_name}: {status}, {row.last_candidates or 0} candidate(s)")

elif page == "Shortlist":
    render_page_title("Shortlist", "Review, save, and open the tenders worth human attention.")

    f1, f2, f3 = st.columns([2.5, 1.2, 1.2])
    with f1:
        search = st.text_input("Search", placeholder="records, workflow, case management")
    with f2:
        lane = st.selectbox("View", ["Active", "Qualified", "Watchlist", "Saved", "Rejected"], index=0)
    with f3:
        min_score = st.number_input("Min score", min_value=0, max_value=100, value=0, step=5)

    saved_only = lane == "Saved"
    tenders = get_tenders(
        lane=lane,
        search=search,
        min_score=float(min_score),
        days_window=None if lane in {"Saved", "Rejected"} else 90,
        saved_only=saved_only,
        limit=300,
    )

    q_count = sum(1 for t in tenders if lane_for_tender(t) == "Qualified")
    w_count = sum(1 for t in tenders if lane_for_tender(t) == "Watchlist")
    r_count = sum(1 for t in tenders if lane_for_tender(t) == "Rejected")
    c1, c2, c3 = st.columns(3)
    c1.metric("Qualified", q_count)
    c2.metric("Watchlist", w_count)
    c3.metric("Rejected shown", r_count)

    render_tender_list(tenders)

elif page == "Sources":
    render_page_title("Sources", "Keep the source list small, active, and reliable.")

    with st.expander("Add source", expanded=False):
        a1, a2 = st.columns(2)
        with a1:
            name = st.text_input("Name")
        with a2:
            url = st.text_input("URL")
        group = st.selectbox("Group", ["africa_priority", "africa_regional", "global_multilateral", "global_public", "experimental"])
        if st.button("Add source"):
            ok, message = add_source(name, url, group)
            st.success(message) if ok else st.error(message)
            if ok:
                st.rerun()

    sources = get_sources()
    st.caption(f"{sum(1 for s in sources if s.active)} active of {len(sources)} configured sources")

    for source in sources:
        with st.container(border=True):
            cols = st.columns([3.4, 1, 1, 1])
            with cols[0]:
                st.markdown(f"**{source.name}**")
                st.caption(source.url)
                st.caption(f"Group: {source.source_group or 'experimental'}")
            with cols[1]:
                st.write("Active" if source.active else "Paused")
            with cols[2]:
                if st.button("Pause" if source.active else "Activate", key=f"active_{source.id}", use_container_width=True):
                    toggle_source(int(source.id), "active")
                    st.rerun()
                if st.button("Star" if not source.favorite else "Unstar", key=f"source_fav_{source.id}", use_container_width=True):
                    toggle_source(int(source.id), "favorite")
                    st.rerun()
            with cols[3]:
                if st.button("Delete", key=f"delete_source_{source.id}", use_container_width=True):
                    delete_source(int(source.id))
                    st.rerun()

elif page == "Settings":
    settings = get_settings()
    render_page_title("Settings", "Only the settings that matter day to day.")

    auto_discovery_enabled = st.checkbox("Use web discovery", value=bool(settings.auto_discovery_enabled))
    include_global_sources = st.checkbox("Include global public-sector sources", value=bool(settings.include_global_sources))
    results_per_query = st.slider("Discovery results per query", 3, 20, int(settings.results_per_query or 8))

    queries = _parse_json_list(settings.discovery_queries)
    default_queries = "\n".join(
        queries
        or [
            "records management system tender",
            "document management workflow tender",
            "case management system public sector tender",
            "registry correspondence management tender",
        ]
    )
    query_text = st.text_area("Discovery queries", value=default_queries, height=120)

    if st.button("Save settings", type="primary"):
        save_basic_settings(
            auto_discovery_enabled=auto_discovery_enabled,
            include_global_sources=include_global_sources,
            results_per_query=results_per_query,
            discovery_queries=query_text.splitlines(),
        )
        st.success("Settings saved.")

    with st.expander("Maintenance"):
        if st.button("Clean closed or irrelevant tenders"):
            if cleanup_irrelevant_tenders is None:
                st.warning("Cleanup is not available in this environment.")
            else:
                with app.app_context():
                    cleanup_irrelevant_tenders()
                st.success("Cleanup complete.")

        provider_notes = [
            f"SerpAPI: {'configured' if os.getenv('SERPAPI_API_KEY') else 'not configured'}",
            f"Google CSE: {'configured' if os.getenv('GOOGLE_API_KEY') and os.getenv('GOOGLE_CX') else 'not configured'}",
            f"Bing: {'configured' if os.getenv('BING_API_KEY') else 'not configured'}",
        ]
        for note in provider_notes:
            st.caption(note)
