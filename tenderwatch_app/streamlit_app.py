"""
TenderWatch - Streamlit (Redesigned)
Simple, focused, and modern UI for cBrain F2 tender monitoring.
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

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


# ------------------------------
# App setup
# ------------------------------
BASE_DIR = Path(__file__).resolve().parent
app = create_app(start_scheduler=False)

st.set_page_config(
    page_title="TenderWatch - cBrain F2",
    page_icon="TW",
    layout="wide",
    initial_sidebar_state="expanded",
)

if "ui_theme" not in st.session_state:
    st.session_state["ui_theme"] = "Clean White"

# Keep PWA hooks so install/notification experience remains available.
st.markdown(
    """
<link rel="manifest" href="/static/manifest.json">
<link rel="apple-touch-icon" href="/static/icon-192.png">
<meta name="theme-color" content="#1ea7ff">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="TenderWatch">
<meta name="mobile-web-app-capable" content="yes">
<script src="/static/pwa.js" defer></script>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800&display=swap');

    :root {
        --bg: #081c2f;
        --bg-2: #0d2b45;
        --card: #103552;
        --card-2: #133e61;
        --surface-soft: rgba(11, 38, 61, 0.82);
        --surface-mid: rgba(16, 56, 88, 0.9);
        --surface-strong: rgba(8, 31, 50, 0.96);
        --text: #f2f7fd;
        --muted: #aac0d6;
        --line: #2b587f;
        --line-strong: #4e88b7;
            --accent: #2b7ab7;
            --accent-2: #205f8f;
      --ok: #17b26a;
      --warn: #f1a532;
      --bad: #ef5a5a;
            --panel-bg: rgba(14, 52, 84, 0.72);
            --panel-line: #3771a2;
            --panel-title: #f4f9ff;
            --panel-sub: #a9c3de;
            --btn-text: #ffffff;
    }

    html, body, .stApp, [class*="css"] {
      font-family: "Manrope", "Segoe UI", sans-serif;
      color: var(--text);
    }

    .stApp {
      background:
                radial-gradient(900px 360px at 8% -12%, rgba(30, 167, 255, 0.16), transparent 60%),
                radial-gradient(760px 320px at 92% -16%, rgba(80, 191, 255, 0.1), transparent 60%),
        linear-gradient(165deg, var(--bg) 0%, var(--bg-2) 100%);
    }

    .block-container {
      max-width: 1240px;
            padding-top: 1.1rem;
            padding-bottom: 2.2rem;
    }

    [data-testid="stSidebar"] {
      background: linear-gradient(180deg, rgba(8, 28, 47, 0.98) 0%, rgba(12, 40, 63, 0.98) 100%);
      border-right: 1px solid var(--line-strong);
      box-shadow: inset -1px 0 0 rgba(120, 180, 230, 0.16);
    }

    [data-testid="stSidebar"] .block-container {
      padding-top: 1rem;
      padding-bottom: 1rem;
    }

    .sidebar-brand {
      border: 1px solid var(--line-strong);
      border-radius: 14px;
      padding: 0.85rem 0.9rem;
      margin-bottom: 0.8rem;
      background: linear-gradient(160deg, rgba(22, 73, 115, 0.94) 0%, rgba(12, 44, 72, 0.96) 100%);
      box-shadow: 0 8px 20px rgba(0, 0, 0, 0.18);
    }

    .sidebar-brand-title {
      margin: 0;
      font-size: 1rem;
      font-weight: 800;
      color: var(--text);
      letter-spacing: 0.01em;
    }

    .sidebar-brand-sub {
      margin: 0.22rem 0 0;
      color: var(--muted);
      font-size: 0.8rem;
      line-height: 1.4;
    }

    .hero {
      border: 1px solid var(--line);
            border-radius: 16px;
            padding: 1.1rem 1.15rem;
            background: linear-gradient(160deg, rgba(18, 60, 96, 0.88) 0%, rgba(12, 44, 72, 0.88) 100%);
      margin-bottom: 1rem;
    }

    .hero-title {
      margin: 0;
            font-size: 1.24rem;
            line-height: 1.28;
            letter-spacing: 0.01em;
      font-weight: 800;
      color: var(--text);
    }

    .hero-sub {
            margin-top: 0.28rem;
      color: var(--muted);
            font-size: 0.9rem;
            line-height: 1.45;
    }

    .pill {
      display: inline-block;
      border: 1px solid rgba(169, 195, 222, 0.35);
      border-radius: 999px;
            padding: 0.24rem 0.58rem;
      margin-right: 0.4rem;
      margin-top: 0.35rem;
            font-size: 0.72rem;
            letter-spacing: 0.01em;
      color: var(--text);
      background: rgba(16, 56, 88, 0.6);
      font-weight: 700;
    }

        h1, h2, h3 { color: var(--text) !important; letter-spacing: 0.01em; }
        h3 { margin-top: 0.45rem !important; margin-bottom: 0.45rem !important; }
    p, li, span { color: var(--text); }

    .stButton > button {
            border-radius: 12px;
      border: 1px solid rgba(255,255,255,0.15);
      background: linear-gradient(135deg, var(--accent) 0%, var(--accent-2) 100%);
      color: white;
      font-weight: 700;
    letter-spacing: 0.01em;
      min-height: 2.45rem;
      transition: transform 0.12s ease, box-shadow 0.12s ease;
            box-shadow: 0 6px 14px rgba(0,0,0,0.16);
    }

    .stButton > button:hover {
      transform: translateY(-1px);
            box-shadow: 0 9px 18px rgba(0,0,0,0.2);
    }

        [role="radiogroup"] {
            gap: 0.45rem;
            background: rgba(12, 41, 66, 0.52);
            border: 1px solid var(--line);
            border-radius: 14px;
            padding: 0.3rem;
        }

        [role="radiogroup"] label {
            border-radius: 10px;
            border: 1px solid transparent;
            padding: 0.12rem 0.15rem;
            transition: all 0.14s ease;
        }

        [role="radiogroup"] label:has(input:checked) {
            background: linear-gradient(135deg, rgba(43, 122, 183, 0.22), rgba(32, 95, 143, 0.2));
            border-color: rgba(169, 195, 222, 0.36);
        }

    .stTextInput input, .stNumberInput input, .stTextArea textarea, .stSelectbox select {
      border-radius: 10px !important;
      border: 1px solid var(--line) !important;
      background: rgba(13, 50, 80, 0.75) !important;
      color: var(--text) !important;
            font-size: 0.93rem !important;
    }

    .stExpander {
      border: 1px solid var(--line-strong);
      border-radius: 12px;
      background: linear-gradient(160deg, var(--surface-soft) 0%, rgba(14, 52, 84, 0.78) 100%);
      box-shadow: 0 8px 18px rgba(4, 18, 30, 0.18);
    }

    div[data-baseweb="tab-list"] {
      gap: 0.35rem;
      background: linear-gradient(160deg, rgba(10, 38, 62, 0.92) 0%, rgba(14, 52, 84, 0.84) 100%);
      border: 1px solid var(--line-strong);
      border-radius: 13px;
      padding: 0.28rem;
      margin-bottom: 0.65rem;
    }

    button[data-baseweb="tab"] {
      border-radius: 10px !important;
      color: var(--muted) !important;
      background: transparent !important;
      border: 1px solid transparent !important;
      font-weight: 700 !important;
    }

    button[data-baseweb="tab"][aria-selected="true"] {
      background: linear-gradient(135deg, rgba(43, 122, 183, 0.28), rgba(32, 95, 143, 0.24)) !important;
      border-color: rgba(120, 180, 230, 0.38) !important;
      color: var(--text) !important;
    }

    [data-testid="stMetric"] {
      border: 1px solid var(--line-strong);
      border-radius: 14px;
      background: linear-gradient(155deg, rgba(26, 82, 126, 0.96) 0%, rgba(16, 56, 88, 0.96) 100%);
      padding: 0.95rem;
      box-shadow: 0 10px 20px rgba(6, 23, 37, 0.18);
    }

    [data-testid="stMetricValue"] { color: var(--text); font-weight: 800; }
    [data-testid="stMetricValue"] { font-size: 1.6rem !important; letter-spacing: 0.01em; }
    [data-testid="stMetricLabel"] { color: #d6e8f7; font-weight: 700; font-size: 0.78rem; letter-spacing: 0.01em; }

    .result-card {
      border: 1px solid rgba(108, 168, 218, 0.34);
      border-left: 4px solid #66b3ee;
      border-radius: 14px;
      background: linear-gradient(160deg, rgba(12, 46, 72, 0.96) 0%, rgba(17, 56, 90, 0.9) 100%);
      padding: 0.95rem 1rem;
      margin-bottom: 0.75rem;
      box-shadow: 0 8px 20px rgba(4, 18, 30, 0.16);
    }

    .result-title {
      margin: 0;
            font-size: 1.05rem;
      font-weight: 800;
            line-height: 1.4;
      color: var(--text);
    }

    .result-meta {
            margin-top: 0.42rem;
      color: var(--muted);
            font-size: 0.8rem;
            line-height: 1.45;
    }

        .section-card {
            border: 1px solid rgba(104, 166, 218, 0.34);
            border-radius: 14px;
            background: linear-gradient(155deg, rgba(10, 38, 61, 0.98) 0%, rgba(16, 54, 86, 0.88) 100%);
            padding: 0.7rem 0.85rem;
            margin: 0.5rem 0 0.7rem;
            box-shadow: 0 8px 18px rgba(4, 18, 30, 0.14);
        }

        .section-card-title {
            margin: 0;
            color: var(--text);
            font-size: 0.98rem;
            font-weight: 800;
            letter-spacing: 0.01em;
        }

        .section-card-sub {
            margin-top: 0.18rem;
            color: var(--muted);
            font-size: 0.8rem;
            line-height: 1.45;
        }

    .score-badge {
      display: inline-block;
      border-radius: 999px;
      padding: 0.17rem 0.52rem;
      font-size: 0.74rem;
      font-weight: 800;
      border: 1px solid rgba(255,255,255,0.2);
    }

    .score-high { background: rgba(23,178,106,0.2); color: #d5ffe9; border-color: rgba(23,178,106,0.45); }
    .score-mid  { background: rgba(241,165,50,0.2); color: #ffefcf; border-color: rgba(241,165,50,0.45); }
    .score-low  { background: rgba(239,90,90,0.2); color: #ffdede; border-color: rgba(239,90,90,0.45); }

        .experience-panel {
            padding: 1rem 1.25rem;
            background: var(--panel-bg);
            border: 1px solid var(--panel-line);
            border-radius: 10px;
            margin-bottom: 1rem;
        }

        .experience-title {
            color: var(--panel-title);
            font-weight: 700;
            font-size: 1.05rem;
        }

        .experience-sub {
            color: var(--panel-sub);
            font-size: 0.9rem;
            margin-top: 0.25rem;
        }

        .pwa-action-wrap {
            text-align: center;
            margin: 0.8rem 0 1rem;
        }

        .pwa-action-btn {
            background: linear-gradient(135deg, var(--accent) 0%, var(--accent-2) 100%);
            color: var(--btn-text);
            border: 1px solid color-mix(in srgb, var(--accent) 60%, #ffffff 40%);
            padding: 10px 24px;
            border-radius: 10px;
            font-weight: 700;
            cursor: pointer;
            box-shadow: 0 8px 18px rgba(0, 0, 0, 0.18);
            transition: transform 0.12s ease, box-shadow 0.12s ease;
        }

        .pwa-action-btn:hover {
            transform: translateY(-1px);
            box-shadow: 0 12px 22px rgba(0, 0, 0, 0.22);
        }

        .scan-banner {
            border: 1px solid var(--line);
            border-radius: 14px;
            padding: 0.75rem 0.9rem;
            background: linear-gradient(155deg, color-mix(in srgb, var(--card) 88%, var(--accent) 12%), var(--card));
            margin: 0.35rem 0 0.9rem;
        }

        .scan-banner-title {
            margin: 0;
            font-weight: 800;
            font-size: 0.98rem;
            color: var(--text);
            line-height: 1.35;
        }

        .scan-banner-sub {
            margin-top: 0.2rem;
            color: var(--muted);
            font-size: 0.82rem;
            line-height: 1.45;
        }

        .insight-chip {
            border: 1px solid var(--line);
            border-radius: 12px;
            padding: 0.55rem 0.65rem;
            background: linear-gradient(155deg, var(--card) 0%, var(--card-2) 100%);
            margin-bottom: 0.45rem;
        }

        .insight-chip-k {
            color: var(--muted);
            font-size: 0.73rem;
            font-weight: 700;
            margin: 0;
            letter-spacing: 0.01em;
        }

        .insight-chip-v {
            color: var(--text);
                        font-size: 1.03rem;
            font-weight: 800;
            margin: 0.06rem 0 0;
        }

    @media (max-width: 820px) {
            .block-container {
                padding-left: 0.7rem;
                padding-right: 0.7rem;
                padding-top: 1rem;
            }
            .hero { padding: 0.92rem 0.9rem; border-radius: 14px; }
            .hero-title { font-size: 1.06rem; }
            .hero-sub { font-size: 0.84rem; }
            [data-testid="stMetric"] { padding: 0.78rem; border-radius: 12px; }
            [data-testid="stMetricValue"] { font-size: 1.35rem !important; }
            .result-card { padding: 0.84rem 0.88rem; border-radius: 12px; }
            .result-title { font-size: 0.96rem; }
            [role="radiogroup"] { gap: 0.25rem; padding: 0.24rem; border-radius: 12px; }
            [role="radiogroup"] label { border-radius: 8px; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

if st.session_state.get("ui_theme") == "Clean White":
        st.markdown(
                """
                <style>
                :root {
                    --bg: #ecf3fa;
                    --bg-2: #e3ecf6;
                    --card: #fbfdff;
                    --card-2: #f3f8fe;
                    --surface-soft: #eef5fb;
                    --surface-mid: #e7f0f8;
                    --surface-strong: #ddeaf6;
                    --text: #162536;
                    --muted: #5c7389;
                    --line: #c2d2e3;
                    --line-strong: #93b4d1;
                    --accent: #2f79b4;
                    --accent-2: #235d89;
                    --ok: #1d7f57;
                    --warn: #926116;
                    --bad: #a54444;
                    --panel-bg: #f4f9fe;
                    --panel-line: #c4d5e6;
                    --panel-title: #162535;
                    --panel-sub: #566b80;
                    --btn-text: #ffffff;
                }

                .stApp {
                    background:
                        radial-gradient(920px 360px at 10% -12%, rgba(47, 121, 180, 0.09), transparent 62%),
                        radial-gradient(760px 340px at 92% -16%, rgba(35, 93, 137, 0.07), transparent 62%),
                        linear-gradient(165deg, #f1f6fb 0%, #e6eef7 100%);
                }

                [data-testid="stSidebar"] {
                    background: linear-gradient(180deg, #dfeaf5 0%, #d7e6f2 100%);
                    border-right-color: #a8c0d7;
                    box-shadow: inset -1px 0 0 rgba(88, 129, 164, 0.12);
                }

                .sidebar-brand {
                    background: linear-gradient(155deg, #edf5fc 0%, #deebf7 100%);
                    border-color: #99b8d4;
                    box-shadow: 0 8px 16px rgba(27, 67, 98, 0.08);
                }

                .hero {
                    background: linear-gradient(160deg, #f8fbff 0%, #e9f2fa 100%) !important;
                    border-color: #aac1d7 !important;
                    box-shadow: 0 8px 18px rgba(18, 40, 61, 0.055);
                }

                .result-card {
                    background: linear-gradient(170deg, #ffffff 0%, #f3f8fd 100%) !important;
                    border-color: #bfd3e6 !important;
                    border-left-color: #4a93ce !important;
                    box-shadow: 0 8px 16px rgba(18, 40, 61, 0.05);
                }

                .section-card,
                .stExpander {
                    background: linear-gradient(170deg, #f7fbff 0%, #eef5fb 100%) !important;
                    border-color: #bfd1e2 !important;
                    box-shadow: 0 6px 14px rgba(18, 40, 61, 0.045);
                }

                [data-testid="stMetric"] {
                    background: linear-gradient(155deg, #ebf5fe 0%, #dcecfb 100%) !important;
                    border-color: #99b8d4 !important;
                    box-shadow: 0 8px 16px rgba(27, 67, 98, 0.07);
                }

                .stButton > button {
                    border-color: rgba(35, 93, 137, 0.36);
                    box-shadow: 0 6px 12px rgba(27, 67, 98, 0.13);
                }

                .stTextInput input, .stNumberInput input, .stTextArea textarea, .stSelectbox select {
                    background: #ffffff !important;
                    color: #1a2d3f !important;
                    border-color: #bed1e3 !important;
                }

                div[data-baseweb="tab-list"] {
                    background: #e8f1f9;
                    border-color: #b7cde0;
                }

                button[data-baseweb="tab"] {
                    color: #5d7387 !important;
                }

                button[data-baseweb="tab"][aria-selected="true"] {
                    background: linear-gradient(135deg, rgba(47, 121, 180, 0.14), rgba(35, 93, 137, 0.1)) !important;
                    border-color: #9fbdd8 !important;
                    color: #173148 !important;
                }

                [role="radiogroup"] {
                    background: rgba(233, 241, 249, 0.9);
                    border-color: #c8d7e7;
                }

                [role="radiogroup"] label:has(input:checked) {
                    background: linear-gradient(135deg, rgba(47, 121, 180, 0.12), rgba(35, 93, 137, 0.1));
                    border-color: #9bb8d3;
                }

                .score-high {
                    background: rgba(29, 127, 87, 0.14);
                    color: #14553a;
                    border-color: rgba(29, 127, 87, 0.36);
                }

                .score-mid {
                    background: rgba(146, 97, 22, 0.14);
                    color: #6e4a10;
                    border-color: rgba(146, 97, 22, 0.34);
                }

                .score-low {
                    background: rgba(165, 68, 68, 0.14);
                    color: #7a3131;
                    border-color: rgba(165, 68, 68, 0.34);
                }
                </style>
                """,
                unsafe_allow_html=True,
        )


# ------------------------------
# Data helpers
# ------------------------------
def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def bootstrap_once() -> None:
    if st.session_state.get("_bootstrapped"):
        return
    with app.app_context():
        db.create_all()
        settings = AppSettings.query.first()
        if not settings:
            settings = AppSettings()  # type: ignore[call-arg]
            settings.auto_scan_enabled = False
            settings.scan_interval_minutes = 60
            settings.notifications_enabled = True
            settings.min_score_to_notify = 70.0
            settings.include_global_sources = True
            settings.include_global_in_default_shortlist = False
            db.session.add(settings)
            db.session.commit()
    st.session_state["_bootstrapped"] = True


def get_settings() -> AppSettings:
    with app.app_context():
        s = AppSettings.query.first()
        if not s:
            s = AppSettings()  # type: ignore[call-arg]
            db.session.add(s)
            db.session.commit()
        return s


def get_stats() -> dict:
    with app.app_context():
        total = TenderResult.query.count()
        high_fit = TenderResult.query.filter(TenderResult.score >= 70).count()
        due_soon = 0
        saved = TenderResult.query.filter(TenderResult.saved.is_(True)).count()
        favorites = TenderResult.query.filter(TenderResult.favorite.is_(True)).count()
        active_sources = TenderSource.query.filter(TenderSource.active.is_(True)).count()

        rows = TenderResult.query.with_entities(TenderResult.deadline).all()
        today = datetime.utcnow().date()
        for (dval,) in rows:
            if not dval:
                continue
            try:
                d = datetime.strptime(str(dval)[:10], "%Y-%m-%d").date()
                days = (d - today).days
                if 0 <= days <= 7:
                    due_soon += 1
            except Exception:
                continue

        return {
            "total": total,
            "high_fit": high_fit,
            "due_soon": due_soon,
            "saved": saved,
            "favorites": favorites,
            "active_sources": active_sources,
        }


def get_tenders(
    search: str = "",
    min_score: float = 0,
    status: str = "All",
    favorites_only: bool = False,
    saved_only: bool = False,
    days_window: int | None = 30,
    sort_by: str = "score",
) -> list[TenderResult]:
    with app.app_context():
        q = TenderResult.query
        if days_window is not None:
            since = _utcnow() - timedelta(days=days_window)
            q = q.filter(TenderResult.created_at >= since)

        q = q.filter(TenderResult.score >= float(min_score))

        if search:
            term = f"%{search.strip()}%"
            q = q.filter(
                TenderResult.title.ilike(term)
                | TenderResult.description.ilike(term)
                | TenderResult.title_translated.ilike(term)
                | TenderResult.description_translated.ilike(term)
            )

        if status == "Open":
            q = q.filter(~TenderResult.procurement_status.in_(["locked", "conditional_nogo"]))
        elif status == "Locked":
            q = q.filter(TenderResult.procurement_status.in_(["locked", "conditional_nogo"]))

        if favorites_only:
            q = q.filter(TenderResult.favorite.is_(True))
        if saved_only:
            q = q.filter(TenderResult.saved.is_(True))

        if sort_by == "date":
            q = q.order_by(TenderResult.created_at.desc())
        else:
            q = q.order_by(TenderResult.score.desc(), TenderResult.created_at.desc())

        rows = q.limit(500).all()

    # Deduplicate by link, keep top score.
    best_by_link: dict[str, TenderResult] = {}
    for t in rows:
        k = (t.link or "").strip().lower()
        if not k:
            continue
        prev = best_by_link.get(k)
        if prev is None or float(t.score or 0) > float(prev.score or 0):
            best_by_link[k] = t
    return list(best_by_link.values())


def run_scan_now(depth: str) -> int:
    depth_map = {
        "Fast": {"max_sources": 20, "timeout": 90},
        "Balanced": {"max_sources": 35, "timeout": 180},
        "Full": {"max_sources": 9999, "timeout": 300},
    }
    cfg = depth_map.get(depth, depth_map["Fast"])
    with app.app_context():
        new_items = run_scan(
            flask_app=app,
            max_sources=cfg["max_sources"],
            scan_timeout_seconds=cfg["timeout"],
            discovery_mode="f2_ranked",
        )
    return len(new_items or [])


def toggle_favorite(tender_id: int) -> None:
    with app.app_context():
        t = TenderResult.query.get(tender_id)
        if t:
            t.favorite = not bool(t.favorite)
            db.session.commit()


def toggle_saved(tender_id: int) -> None:
    with app.app_context():
        t = TenderResult.query.get(tender_id)
        if t:
            t.saved = not bool(t.saved)
            db.session.commit()


def get_sources() -> list[TenderSource]:
    with app.app_context():
        return TenderSource.query.order_by(TenderSource.active.desc(), TenderSource.name.asc()).all()


def get_source_health_snapshot(limit: int = 8) -> list[SourceHealth]:
    with app.app_context():
        return (
            SourceHealth.query.order_by(SourceHealth.last_scan_at.desc())
            .limit(max(1, int(limit)))
            .all()
        )


def add_source(name: str, url: str, group: str = "africa_priority") -> tuple[bool, str]:
    name = (name or "").strip()
    url = (url or "").strip()
    if not name or not url:
        return False, "Name and URL are required."
    if not (url.startswith("http://") or url.startswith("https://")):
        return False, "URL must start with http:// or https://"

    with app.app_context():
        exists = TenderSource.query.filter(func.lower(TenderSource.url) == url.lower()).first()
        if exists:
            return False, "Source already exists."
        src = TenderSource()  # type: ignore[call-arg]
        src.name = name
        src.url = url
        src.active = True
        src.favorite = False
        src.source_group = group
        src.source_tags = json.dumps([group])
        db.session.add(src)
        db.session.commit()
    return True, "Source added."


def delete_sources(source_ids: list[int]) -> int:
    if not source_ids:
        return 0
    with app.app_context():
        count = 0
        for sid in source_ids:
            src = TenderSource.query.get(int(sid))
            if src:
                db.session.delete(src)
                count += 1
        db.session.commit()
        return count


def delete_all_sources() -> int:
    with app.app_context():
        count = TenderSource.query.count()
        TenderSource.query.delete()
        db.session.commit()
        return count


def set_all_sources_active(active: bool) -> int:
    with app.app_context():
        changed = TenderSource.query.filter(TenderSource.active.is_(not active)).update(
            {"active": active}, synchronize_session=False
        )
        db.session.commit()
        return int(changed or 0)


def toggle_source_active(source_id: int) -> None:
    with app.app_context():
        src = TenderSource.query.get(source_id)
        if src:
            src.active = not bool(src.active)
            db.session.commit()


# ------------------------------
# UI components
# ------------------------------
def render_hero(title: str, subtitle: str, pills: list[str] | None = None) -> None:
    pills_html = ""
    for p in (pills or []):
        pills_html += f"<span class='pill'>{p}</span>"
    st.markdown(
        f"""
        <div class='hero'>
          <p class='hero-title'>{title}</p>
          <div class='hero-sub'>{subtitle}</div>
          <div>{pills_html}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_section_card(title: str, subtitle: str) -> None:
        st.markdown(
                f"""
                <div class='section-card'>
                    <p class='section-card-title'>{title}</p>
                    <div class='section-card-sub'>{subtitle}</div>
                </div>
                """,
                unsafe_allow_html=True,
        )


def render_tender_card(t: TenderResult) -> None:
    score = float(t.score or 0)
    score_class = "score-high" if score >= 70 else "score-mid" if score >= 45 else "score-low"
    created = t.created_at.strftime("%Y-%m-%d") if t.created_at else "N/A"
    status = t.procurement_status or "open"
    country = t.country or "Unknown"
    category = t.category or "Unclassified"
    desc = (t.description_translated or t.description or "").strip()
    compact_mode = bool(st.session_state.get("compact_mode", False))
    desc_limit = 120 if compact_mode else 220
    if len(desc) > desc_limit:
        desc = desc[:desc_limit].rstrip() + "..."

    st.markdown(
        f"""
        <div class='result-card'>
          <p class='result-title'>{t.title}</p>
          <div class='result-meta'>
            <span class='score-badge {score_class}'>Score {score:.1f}%</span>
            &nbsp;&nbsp;{country} | {category} | {status} | {created}
          </div>
          <div class='result-meta' style='margin-top:0.45rem'>{desc}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    c1, c2, c3, c4 = st.columns([1.4, 1.2, 1.2, 1.8])
    with c1:
        if st.button("View Link", key=f"open_{t.id}", use_container_width=True):
            st.link_button("Open Tender", t.link, use_container_width=True)
    with c2:
        if st.button("Favorite", key=f"fav_{t.id}", use_container_width=True):
            toggle_favorite(int(t.id))
            st.rerun()
    with c3:
        if st.button("Save", key=f"save_{t.id}", use_container_width=True):
            toggle_saved(int(t.id))
            st.rerun()
    with c4:
        st.caption(f"Deadline: {t.deadline or 'N/A'}")


def render_quickstart() -> None:
    if st.session_state.get("quickstart_dismissed"):
        return
    with st.expander("Quick Start (First-time setup)", expanded=True):
        st.markdown("1. Go to **Sources** and confirm active portals.")
        st.markdown("2. Open **Scan & Results** and run a scan.")
        st.markdown("3. Save/Favorite high-fit tenders for follow-up.")
        if st.button("Got it", key="dismiss_quickstart"):
            st.session_state["quickstart_dismissed"] = True
            st.rerun()


# ------------------------------
# App pages
# ------------------------------
bootstrap_once()

NAV_PAGES = [
    "Dashboard",
    "Scan & Results",
    "Sources",
    "Favorites",
    "Saved",
    "Settings",
]

if "page" not in st.session_state:
    st.session_state["page"] = "Dashboard"

nav_labels = {
    "Dashboard": "Dashboard",
    "Scan & Results": "Scan",
    "Sources": "Sources",
    "Favorites": "Favorites",
    "Saved": "Saved",
    "Settings": "Settings",
}

nav_icons = {
    "Dashboard": "",
    "Scan & Results": "",
    "Sources": "",
    "Favorites": "",
    "Saved": "",
    "Settings": "",
}

with st.sidebar:
    st.markdown(
        """
        <div class='sidebar-brand'>
            <p class='sidebar-brand-title'>TenderWatch</p>
            <div class='sidebar-brand-sub'>Navigation and workspace controls</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    try:
        page = st.radio(
            "Navigation",
            NAV_PAGES,
            key="page",
            format_func=lambda x: nav_labels.get(x, x),
            label_visibility="visible",
        )
    except TypeError:
        page = st.radio(
            "Navigation",
            NAV_PAGES,
            key="page",
            format_func=lambda x: nav_labels.get(x, x),
        )

st.markdown("<div style='height:0.1rem'></div>", unsafe_allow_html=True)


if page == "Dashboard":
    stats = get_stats()
    render_hero(
        "Executive Dashboard",
        "Clean snapshot of F2 opportunities and team pipeline.",
        [
            f"Active Sources: {stats['active_sources']}",
            "Africa-first",
            "Simple workflow",
        ],
    )
    render_quickstart()

    k1, k2, k3 = st.columns(3)
    k1.metric("Live Opportunities", stats["total"])
    k2.metric("High Fit (>=70)", stats["high_fit"])
    k3.metric("Deadlines (7 days)", stats["due_soon"])

    k4, k5 = st.columns(2)
    k4.metric("Saved Pipeline", stats["saved"])
    k5.metric("Favorites", stats["favorites"])

    st.markdown("### Latest Opportunities")
    recent = get_tenders(min_score=25, days_window=30, sort_by="date")[:6]
    if not recent:
        st.info("No opportunities yet. Run a scan from Scan & Results.")
    else:
        for t in recent:
            render_tender_card(t)

elif page == "Scan & Results":
    if "scan_ux_bootstrap_v4" not in st.session_state:
        st.session_state["scan_query_v4"] = ""
        st.session_state["scan_min_score_v4"] = 0
        st.session_state["scan_scope_v4"] = "Active pipeline"
        st.session_state["scan_sort_v4"] = "score"
        st.session_state["scan_period_v4"] = "30 days"
        st.session_state["scan_favorites_only_v4"] = False
        st.session_state["scan_saved_only_v4"] = False
        st.session_state["scan_ux_bootstrap_v4"] = True

    render_hero(
        "Tender Radar",
        "A clear workspace for discovery, filtering, and shortlist decisions.",
        ["Run Scan", "Apply Filters", "Review Lanes"],
    )

    st.markdown(
        """
        <div class='scan-banner'>
            <p class='scan-banner-title'>Workflow: 1) run a scan, 2) set your filters, 3) review prioritized lanes.</p>
            <div class='scan-banner-sub'>Use Broad for discovery, Shortlist for qualified options, and Priority for immediate opportunities.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    left, right = st.columns([2.25, 1])

    with left:
        render_section_card("Controls", "Run scans, choose a mode, and adjust precision filters.")
        s1, s2, s3 = st.columns([1.1, 1.1, 2.1])
        with s1:
            scan_depth = st.selectbox("Scan Depth", ["Fast", "Balanced", "Full"], index=1, key="scan_depth_v4")
        with s2:
            st.markdown("<div style='height:1.6rem'></div>", unsafe_allow_html=True)
            if st.button("Launch Scan", key="launch_scan_v4", use_container_width=True):
                with st.spinner("Running scan and ranking tenders..."):
                    started = time.time()
                    new_count = run_scan_now(scan_depth)
                    elapsed = time.time() - started
                st.success(f"Scan complete. New tenders: {new_count} | Duration: {elapsed:.1f}s")
                st.rerun()
        with s3:
            st.caption("Balanced is recommended for daily use. Full is best for end-of-day deep discovery.")

        st.markdown("##### Quick Modes")
        m1, m2, m3, m4 = st.columns(4)
        with m1:
            if st.button("Broad", key="mode_scout_v4", use_container_width=True):
                st.session_state["scan_min_score_v4"] = 0
                st.session_state["scan_scope_v4"] = "All statuses"
                st.session_state["scan_period_v4"] = "7 days"
                st.session_state["scan_sort_v4"] = "date"
                st.rerun()
        with m2:
            if st.button("Shortlist", key="mode_qualified_v4", use_container_width=True):
                st.session_state["scan_min_score_v4"] = 40
                st.session_state["scan_scope_v4"] = "Active pipeline"
                st.session_state["scan_period_v4"] = "30 days"
                st.session_state["scan_sort_v4"] = "score"
                st.rerun()
        with m3:
            if st.button("Priority", key="mode_decision_v4", use_container_width=True):
                st.session_state["scan_min_score_v4"] = 70
                st.session_state["scan_scope_v4"] = "Active pipeline"
                st.session_state["scan_period_v4"] = "90 days"
                st.session_state["scan_sort_v4"] = "score"
                st.rerun()
        with m4:
            if st.button("Clear", key="mode_clear_v4", use_container_width=True):
                st.session_state["scan_query_v4"] = ""
                st.session_state["scan_min_score_v4"] = 0
                st.session_state["scan_scope_v4"] = "Active pipeline"
                st.session_state["scan_sort_v4"] = "score"
                st.session_state["scan_period_v4"] = "30 days"
                st.session_state["scan_favorites_only_v4"] = False
                st.session_state["scan_saved_only_v4"] = False
                st.rerun()

        f1, f2, f3, f4 = st.columns([2.1, 1, 1.1, 1])
        with f1:
            search = st.text_input(
                "Search Intent",
                placeholder="Try: records management, justice, donor-funded, cloud migration",
                key="scan_query_v4",
            )
        with f2:
            min_score = st.slider("Min Score", 0, 100, 0, key="scan_min_score_v4")
        with f3:
            scope = st.selectbox(
                "Scope",
                ["Active pipeline", "All statuses", "Locked only"],
                key="scan_scope_v4",
            )
        with f4:
            sort_by = st.selectbox("Rank by", ["score", "date"], key="scan_sort_v4")

        with st.expander("Precision Filters", expanded=False):
            p1, p2, p3 = st.columns(3)
            with p1:
                favorites_only = st.checkbox("Favorites only", key="scan_favorites_only_v4")
            with p2:
                saved_only = st.checkbox("Saved only", key="scan_saved_only_v4")
            with p3:
                period = st.selectbox("Time Window", ["7 days", "30 days", "90 days", "All"], key="scan_period_v4")

    with right:
        render_section_card("Live Insights", "Current filter posture at a glance.")
        st.markdown(
            f"""
            <div class='insight-chip'>
                <p class='insight-chip-k'>Mode signal</p>
                <p class='insight-chip-v'>{scope}</p>
            </div>
            <div class='insight-chip'>
                <p class='insight-chip-k'>Minimum fit threshold</p>
                <p class='insight-chip-v'>{min_score}%</p>
            </div>
            <div class='insight-chip'>
                <p class='insight-chip-k'>Window + sorting</p>
                <p class='insight-chip-v'>{period} | {sort_by}</p>
            </div>
            <div class='insight-chip'>
                <p class='insight-chip-k'>Current query</p>
                <p class='insight-chip-v'>{(search.strip()[:34] + '...') if len(search.strip()) > 34 else (search.strip() or 'None')}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown("##### Source Reliability")
        health_rows = get_source_health_snapshot(limit=6)
        if not health_rows:
            st.caption("No source health data yet. Run a scan to populate this view.")
        else:
            for row in health_rows:
                status = (row.last_status or "unknown").upper()
                candidates = int(row.last_candidates or 0)
                duration = float(row.last_duration_seconds or 0)
                st.caption(f"{row.source_name or 'Unknown'} | {status} | {candidates} candidates | {duration:.1f}s")

    status_map = {
        "Active pipeline": "Open",
        "All statuses": "All",
        "Locked only": "Locked",
    }

    window_map = {"7 days": 7, "30 days": 30, "90 days": 90, "All": None}
    tenders = get_tenders(
        search=search,
        min_score=float(min_score),
        status=status_map.get(scope, "Open"),
        favorites_only=favorites_only,
        saved_only=saved_only,
        days_window=window_map.get(period, 30),
        sort_by=sort_by,
    )

    high_lane = [t for t in tenders if float(t.score or 0) >= 70]
    mid_lane = [t for t in tenders if 40 <= float(t.score or 0) < 70]
    low_lane = [t for t in tenders if float(t.score or 0) < 40]

    render_section_card(
        "Action Lanes",
        f"{len(tenders)} matches | Priority {len(high_lane)} | Qualified {len(mid_lane)} | Explore {len(low_lane)}",
    )

    if not tenders:
        st.warning("No tenders match these filters. Try Broad mode or reduce Min Score.")
    else:
        lane_priority, lane_qualified, lane_explore = st.tabs(
            [
                f"Priority ({len(high_lane)})",
                f"Qualified ({len(mid_lane)})",
                f"Explore ({len(low_lane)})",
            ]
        )

        with lane_priority:
            if not high_lane:
                st.info("No high-fit tenders yet. Try lowering threshold or running a broader scan.")
            else:
                for t in high_lane[:80]:
                    render_tender_card(t)

        with lane_qualified:
            if not mid_lane:
                st.info("No qualified tenders in this lane.")
            else:
                for t in mid_lane[:80]:
                    render_tender_card(t)

        with lane_explore:
            if not low_lane:
                st.info("No exploratory tenders in this lane.")
            else:
                for t in low_lane[:80]:
                    render_tender_card(t)

elif page == "Sources":
    render_hero(
        "Source Management",
        "Keep sources clean and active. Bulk controls are one click.",
        ["Enable/Disable all", "Bulk delete"],
    )

    with st.expander("Add New Source", expanded=False):
        c1, c2 = st.columns(2)
        with c1:
            new_name = st.text_input("Source Name", key="new_source_name")
        with c2:
            new_url = st.text_input("Source URL", key="new_source_url")
        c3, c4 = st.columns([1.2, 2])
        with c3:
            group = st.selectbox("Group", ["africa_priority", "africa_regional", "global_watch"], key="new_source_group")
        with c4:
            st.caption("Use official, open-access tender portals.")
        if st.button("Add Source", key="add_source_btn"):
            ok, msg = add_source(new_name, new_url, group)
            if ok:
                st.success(msg)
                st.rerun()
            st.error(msg)

    render_section_card("Bulk Actions", "Enable, disable, or delete multiple sources quickly.")
    sources = get_sources()
    if "selected_source_ids" not in st.session_state:
        st.session_state["selected_source_ids"] = []

    b1, b2, b3, b4 = st.columns(4)
    with b1:
        if st.button("Enable All", use_container_width=True):
            changed = set_all_sources_active(True)
            st.success(f"Enabled {changed} source(s).")
            st.rerun()
    with b2:
        if st.button("Disable All", use_container_width=True):
            changed = set_all_sources_active(False)
            st.success(f"Disabled {changed} source(s).")
            st.rerun()
    with b3:
        if st.button("Delete Selected", use_container_width=True):
            deleted = delete_sources(st.session_state.get("selected_source_ids", []))
            st.success(f"Deleted {deleted} source(s).")
            st.session_state["selected_source_ids"] = []
            st.rerun()
    with b4:
        if st.button("Delete All", use_container_width=True):
            if st.session_state.get("confirm_delete_all"):
                deleted = delete_all_sources()
                st.success(f"Deleted all {deleted} source(s).")
                st.session_state["confirm_delete_all"] = False
                st.rerun()
            else:
                st.session_state["confirm_delete_all"] = True
                st.warning("Click Delete All again to confirm.")

    render_section_card("All Sources", "Review source status and toggle individual entries.")
    st.markdown("### All Sources")
    for s in sources:
        row = st.columns([0.7, 3.5, 1.6, 1.2, 1.2])
        with row[0]:
            checked = st.checkbox("", key=f"sel_{s.id}", value=s.id in st.session_state["selected_source_ids"])
            selected = set(st.session_state["selected_source_ids"])
            if checked:
                selected.add(s.id)
            else:
                selected.discard(s.id)
            st.session_state["selected_source_ids"] = sorted(selected)
        with row[1]:
            st.markdown(f"**{s.name}**  ")
            st.caption(s.url)
        with row[2]:
            st.caption(f"Group: {getattr(s, 'source_group', 'n/a')}")
        with row[3]:
            status = "Active" if s.active else "Paused"
            st.write(status)
        with row[4]:
            if st.button("Toggle", key=f"toggle_src_{s.id}"):
                toggle_source_active(int(s.id))
                st.rerun()

elif page == "Favorites":
    render_hero("Favorites", "Quick access to your starred opportunities.")
    render_section_card("Favorite Opportunities", "Your starred shortlist for rapid review.")
    favs = get_tenders(favorites_only=True, min_score=0, days_window=None, sort_by="score")
    st.caption(f"{len(favs)} favorite tender(s)")
    if not favs:
        st.info("No favorites yet. Mark items from Scan & Results.")
    else:
        for t in favs[:150]:
            render_tender_card(t)

elif page == "Saved":
    render_hero("Saved", "Your working shortlist for follow-up actions.")
    render_section_card("Saved Opportunities", "Operational queue for next actions and submissions.")
    saved = get_tenders(saved_only=True, min_score=0, days_window=None, sort_by="score")
    st.caption(f"{len(saved)} saved tender(s)")
    if not saved:
        st.info("No saved tenders yet. Save items from Scan & Results.")
    else:
        for t in saved[:150]:
            render_tender_card(t)

elif page == "Settings":
    settings = get_settings()
    render_hero(
        "Settings",
        "Basic settings first. Advanced controls are available but out of the way.",
        ["Simple by default", "Advanced on demand"],
    )

    tab_basic, tab_advanced, tab_experience = st.tabs(["Basic", "Advanced", "Experience"])

    with tab_basic:
        b1, b2 = st.columns(2)
        with b1:
            auto_scan_enabled = st.checkbox("Enable Auto Scan", value=bool(settings.auto_scan_enabled))
            scan_interval = st.number_input("Scan Interval (minutes)", min_value=5, max_value=1440, value=int(settings.scan_interval_minutes or 60), step=5)
            notifications_enabled = st.checkbox("Enable Notifications", value=bool(settings.notifications_enabled))
        with b2:
            min_notify = st.slider("Minimum Score for Alerts", min_value=0, max_value=100, value=int(settings.min_score_to_notify or 70))
            include_global_sources = st.checkbox("Include Global Sources", value=bool(settings.include_global_sources))
            include_global_shortlist = st.checkbox(
                "Include Global in Default Shortlist",
                value=bool(settings.include_global_in_default_shortlist),
            )

        if st.button("Save Basic Settings", key="save_basic_settings"):
            with app.app_context():
                s = AppSettings.query.first()
                if not s:
                    s = AppSettings()  # type: ignore[call-arg]
                    db.session.add(s)
                s.auto_scan_enabled = bool(auto_scan_enabled)
                s.scan_interval_minutes = int(scan_interval)
                s.notifications_enabled = bool(notifications_enabled)
                s.min_score_to_notify = float(min_notify)
                s.include_global_sources = bool(include_global_sources)
                s.include_global_in_default_shortlist = bool(include_global_shortlist)
                db.session.commit()
            st.success("Basic settings saved.")

    with tab_advanced:
        a1, a2 = st.columns(2)
        with a1:
            africa_only_mode = st.checkbox("Africa Only Mode", value=bool(settings.africa_only_mode))
            results_per_query = st.number_input(
                "Results Per Discovery Query",
                min_value=3,
                max_value=30,
                value=int(settings.results_per_query or 10),
                step=1,
            )
            auto_discovery_enabled = st.checkbox("Enable Auto Discovery", value=bool(settings.auto_discovery_enabled))
        with a2:
            serpapi_ready = bool((os.getenv("SERPAPI_API_KEY", "") or "").strip())
            google_ready = bool((os.getenv("GOOGLE_API_KEY", "") or "").strip() and (os.getenv("GOOGLE_CX", "") or "").strip())
            bing_ready = bool((os.getenv("BING_API_KEY", "") or "").strip())
            st.markdown("**Discovery Provider Health**")
            st.caption(f"SerpAPI: {'Configured' if serpapi_ready else 'Missing SERPAPI_API_KEY'}")
            st.caption(f"Google CSE: {'Configured' if google_ready else 'Missing GOOGLE_API_KEY or GOOGLE_CX'}")
            st.caption(f"Bing: {'Configured' if bing_ready else 'Missing BING_API_KEY'}")
            st.info("API keys are now read from environment variables and are not saved in the database.")

        discovery_queries_text = st.text_area(
            "Discovery Queries (one per line)",
            value="\n".join(json.loads(settings.discovery_queries)) if settings.discovery_queries else "",
            height=120,
        )

        if st.button("Save Advanced Settings", key="save_advanced_settings"):
            try:
                queries = [q.strip() for q in (discovery_queries_text or "").splitlines() if q.strip()]
                with app.app_context():
                    s = AppSettings.query.first()
                    if not s:
                        s = AppSettings()  # type: ignore[call-arg]
                        db.session.add(s)
                    s.africa_only_mode = bool(africa_only_mode)
                    s.results_per_query = int(results_per_query)
                    s.auto_discovery_enabled = bool(auto_discovery_enabled)
                    s.discovery_queries = json.dumps(queries)
                    db.session.commit()
                st.success("Advanced settings saved.")
            except Exception as exc:
                st.error(f"Could not save advanced settings: {exc}")

        st.markdown("---")
        st.subheader("Maintenance")
        m1, m2 = st.columns(2)
        with m1:
            if st.button("Run Cleanup (Closed/Awarded)", key="run_cleanup_closed"):
                if cleanup_irrelevant_tenders is None:
                    st.warning("Cleanup utility is unavailable in this environment.")
                else:
                    try:
                        with app.app_context():
                            cleanup_irrelevant_tenders()
                        st.success("Cleanup completed.")
                    except Exception as exc:
                        st.error(f"Cleanup failed: {exc}")
        with m2:
            if st.button("Reset Quick Start", key="reset_quickstart"):
                st.session_state["quickstart_dismissed"] = False
                st.success("Quick Start will show again on Dashboard.")

    with tab_experience:
        st.markdown(
            """
            <div class='experience-panel'>
                <div class='experience-title'>Install TenderWatch</div>
                <div class='experience-sub'>Add to your home screen for quick access.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        col1, col2 = st.columns(2)
        with col1:
            st.markdown(
                """
                **Mobile (Android/iOS):**
                1. Open this app in Chrome/Safari
                2. Tap the **Share** button (iOS) or browser menu (Android)
                3. Select **"Add to Home Screen"**
                4. The app icon will appear on your home screen
                """
            )

        with col2:
            st.markdown(
                """
                **Desktop (Chrome/Edge):**
                1. Look for the install button in the address bar
                2. Or click the floating install button (bottom-right)
                3. Click **"Install"** when prompted
                4. TenderWatch opens as a standalone app
                """
            )

        st.markdown(
            """
                        <div class='pwa-action-wrap'>
              <button onclick="window.TenderWatchPWA && window.TenderWatchPWA.promptInstall && window.TenderWatchPWA.promptInstall()"
                                            class='pwa-action-btn'>
                  Install TenderWatch
              </button>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown("---")
        st.markdown(
            """
            <div class='experience-panel'>
                <div class='experience-title'>Daily Scan Reminders</div>
                <div class='experience-sub'>Configure a daily reminder to review new tenders.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown(
            """
            **How it works:**
            - Click the notification setup button below
            - Choose your preferred time (e.g., 8:00 AM)
            - You will receive a notification every day to scan for new tenders
            - Works on both mobile and desktop (after installing the app)

            **Tips:**
            - For best results, **install the app** first
            - Allow notifications when your browser asks
            - Notifications can work when the browser is closed (supported devices)
            """
        )

        st.markdown(
            """
                        <div class='pwa-action-wrap'>
              <button onclick="window.TenderWatchPWA && window.TenderWatchPWA.setupNotifications && window.TenderWatchPWA.setupNotifications()"
                                            class='pwa-action-btn'>
                  Set Up Daily Notifications
              </button>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown("---")
        st.subheader("Notification Preferences")
        exp_notifications_enabled = st.checkbox(
            "Enable In-App Notifications",
            value=bool(settings.notifications_enabled),
            key="exp_notifications_enabled",
            help="Show notifications for high-score tenders during scans.",
        )
        exp_min_score = st.slider(
            "Minimum Score for Alerts",
            0,
            100,
            value=int(settings.min_score_to_notify or 70),
            key="exp_min_score",
            help="Only alert for tenders above this score.",
        )
        if st.button("Save Notification Preferences", key="save_exp_notification_prefs"):
            with app.app_context():
                s = AppSettings.query.first()
                if not s:
                    s = AppSettings()  # type: ignore[call-arg]
                    db.session.add(s)
                s.notifications_enabled = bool(exp_notifications_enabled)
                s.min_score_to_notify = float(exp_min_score)
                db.session.commit()
            st.success("Notification preferences saved.")

        st.markdown("---")
        st.subheader("UI Options")
        theme_idx = 0 if st.session_state.get("ui_theme") == "Deep Blue" else 1
        selected_theme = st.selectbox(
            "Theme",
            ["Deep Blue", "Clean White"],
            index=theme_idx,
            help="Choose a dark or white-background visual theme.",
        )
        st.session_state["ui_theme"] = selected_theme
        compact_mode = st.checkbox("Compact result cards", value=bool(st.session_state.get("compact_mode", False)))
        st.session_state["compact_mode"] = compact_mode
        if compact_mode:
            st.caption("Compact mode is enabled for tighter lists in Scan & Results.")
        else:
            st.caption("Comfort mode is enabled for easier readability.")


st.caption("cBrain TenderWatch | redesigned UI")
