"""
TenderWatch - Streamlit Version
Simple, powerful tender scanning for cBrain F2 Platform
"""

import json
import importlib
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict
from urllib.parse import urlencode, urlsplit, urlunsplit

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
from app.keywords import ALL_KEYWORDS
from app.ml_ranker import (
    blend_score,
    feedback_counts,
    model_status,
    predict_relevance,
    record_feedback,
    train_relevance_model,
)

NAV_PAGES = ["Dashboard", "Scan & Results", "Sources", "Favorites", "Saved", "Settings"]
NAV_QUERY_MAP = {
    "dashboard": "Dashboard",
    "scan": "Scan & Results",
    "sources": "Sources",
    "favorites": "Favorites",
    "saved": "Saved",
    "settings": "Settings",
}


def _qp_value(name: str, default: str = "") -> str:
    val = st.query_params.get(name, default)
    if isinstance(val, list):
        return str(val[0]) if val else str(default)
    if val is None:
        return str(default)
    return str(val)


def _qp_bool(name: str, default: bool = False) -> bool:
    raw = _qp_value(name, "1" if default else "0").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _qp_int(name: str, default: int = 0) -> int:
    raw = _qp_value(name, str(default))
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default


def _nav_href(nav: str, **params) -> str:
    query: Dict[str, str] = {"nav": nav}
    query["tap"] = str(int(time.time() * 1000))
    for key, value in params.items():
        if value is None:
            continue
        if isinstance(value, bool):
            query[key] = "true" if value else "false"
        else:
            query[key] = str(value)
    return "?" + urlencode(query)

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
<link rel="apple-touch-icon" href="/static/icon-192.png">
<link rel="icon" type="image/png" sizes="192x192" href="/static/icon-192.png">
<link rel="icon" type="image/png" sizes="144x144" href="/static/icon-144.png">
<meta name="theme-color" content="#38bdf8">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="TenderWatch">
<meta name="mobile-web-app-capable" content="yes">
<meta name="application-name" content="TenderWatch">
<meta name="msapplication-TileColor" content="#38bdf8">
<meta name="msapplication-TileImage" content="/static/icon-144.png">
<script src="/static/pwa.js" defer></script>
""", unsafe_allow_html=True)

# Force a single dark theme for consistent readability.
st.session_state.theme = 'dark'

# Professional visual system
st.markdown(f"""
<style>
    @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&display=swap');

    /* Theme Variables */
    :root {{
        --bg-primary: {'#061a2f' if st.session_state.theme == 'dark' else '#f3faff'};
        --bg-secondary: {'#0d2742' if st.session_state.theme == 'dark' else '#deefff'};
        --text-primary: {'#eaf7ff' if st.session_state.theme == 'dark' else '#0b2035'};
        --text-secondary: {'#a7c8df' if st.session_state.theme == 'dark' else '#3a5872'};
        --border-color: {'#2f5d80' if st.session_state.theme == 'dark' else '#bfd9ef'};
        --card-bg: {'#0d2338' if st.session_state.theme == 'dark' else '#ffffff'};
        --accent: {'#38bdf8' if st.session_state.theme == 'dark' else '#0284c7'};
        --accent-strong: {'#0ea5e9' if st.session_state.theme == 'dark' else '#0369a1'};
        --table-row: {'#12304a' if st.session_state.theme == 'dark' else '#edf7ff'};
        --glow-rose: {'rgba(56, 189, 248, 0.30)' if st.session_state.theme == 'dark' else 'rgba(2,132,199,0.14)'};
        --glow-amber: {'rgba(125, 211, 252, 0.26)' if st.session_state.theme == 'dark' else 'rgba(56,189,248,0.10)'};
    }}

    @keyframes cardRise {{
        from {{
            opacity: 0;
            transform: translateY(6px);
        }}
        to {{
            opacity: 1;
            transform: translateY(0);
        }}
    }}

    @keyframes sweep {{
        0% {{
            transform: translateX(-120%) skewX(-20deg);
            opacity: 0;
        }}
        35% {{
            opacity: 0.26;
        }}
        100% {{
            transform: translateX(220%) skewX(-20deg);
            opacity: 0;
        }}
    }}

    @keyframes gradientShift {{
        0% {{
            background-position: 0% 50%;
        }}
        100% {{
            background-position: 100% 50%;
        }}
    }}

    @keyframes haloPulse {{
        0%, 100% {{
            box-shadow: 0 0 0 0 rgba(56, 189, 248, 0.0);
        }}
        50% {{
            box-shadow: 0 0 0 6px rgba(56, 189, 248, 0.14);
        }}
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
            radial-gradient(1200px 520px at 10% -14%, {'rgba(56, 189, 248, 0.24)' if st.session_state.theme == 'dark' else 'rgba(2,132,199,0.10)'}, transparent 62%),
            radial-gradient(900px 460px at 94% -18%, {'rgba(14, 165, 233, 0.20)' if st.session_state.theme == 'dark' else 'rgba(56,189,248,0.10)'}, transparent 60%),
            radial-gradient(600px 300px at 48% 112%, {'rgba(125, 211, 252, 0.14)' if st.session_state.theme == 'dark' else 'rgba(14,165,233,0.08)'}, transparent 66%),
            linear-gradient(180deg, {'#061a2f' if st.session_state.theme == 'dark' else '#f3faff'} 0%, {'#0b2239' if st.session_state.theme == 'dark' else '#eaf5ff'} 100%);
        background-size: 120% 120%, 120% 120%, 120% 120%, 100% 100%;
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
        background: linear-gradient(135deg, var(--accent) 0%, var(--accent-strong) 100%);
        color: white;
        border-radius: 10px;
        padding: 0.52rem 1.05rem;
        font-weight: 600;
        border: 1px solid rgba(255, 214, 194, 0.20);
        box-shadow: 0 10px 20px rgba(0, 0, 0, 0.20);
        transition: background-color 0.2s ease, transform 0.12s ease, box-shadow 0.18s ease;
    }}

    .stButton>button:hover {{
        background: var(--accent-strong);
        transform: translateY(-3px);
        box-shadow: 0 14px 26px rgba(0, 0, 0, 0.28);
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
        animation: cardRise 0.35s ease-out both;
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
        background:
            radial-gradient(460px 220px at 20% -20%, rgba(56, 189, 248, 0.18), transparent 70%),
            radial-gradient(380px 180px at 100% -10%, rgba(125, 211, 252, 0.16), transparent 68%),
            {'#0a2035' if st.session_state.theme == 'dark' else '#d9edff'};
        border-right: 1px solid {'#2f5d80' if st.session_state.theme == 'dark' else '#8bb7d9'};
    }}

    [data-testid="stSidebar"] * {{
        color: #eaf7ff !important;
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
        border-color: {'#3f80aa' if st.session_state.theme == 'dark' else '#78acd1'};
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
        background: {'#2a1b31' if st.session_state.theme == 'dark' else '#f6e8df'};
        border: 1px solid var(--border-color);
        color: var(--text-primary);
    }}

    /* Banner */
    .hero-banner {{
        background:
            radial-gradient(340px 120px at 12% -25%, rgba(56, 189, 248, 0.22), transparent 72%),
            radial-gradient(300px 140px at 88% -38%, rgba(125, 211, 252, 0.22), transparent 74%),
            {'linear-gradient(120deg,#0f2b45 0%,#163a5d 100%)' if st.session_state.theme == 'dark' else 'linear-gradient(120deg,#eaf5ff 0%,#d9ecff 100%)'};
        border: 1px solid var(--border-color);
        border-radius: 12px;
        padding: 1rem 1.1rem;
        color: var(--text-primary);
        box-shadow: 0 14px 30px rgba(4, 10, 19, 0.30);
        margin-bottom: 1.25rem;
        animation: cardRise 0.45s ease-out both;
    }}
    .hero-banner .title {{
        color: transparent;
        background: linear-gradient(90deg, #eaf7ff 0%, #7dd3fc 38%, #38bdf8 72%, #eaf7ff 100%);
        background-size: 200% auto;
        -webkit-background-clip: text;
        background-clip: text;
        font-size: 1.05rem;
        font-weight: 700;
        margin: 0;
        animation: gradientShift 7s linear infinite alternate;
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
        background: {'rgba(37, 79, 112, 0.72)' if st.session_state.theme == 'dark' else '#dcefff'};
        color: {'#eaf7ff' if st.session_state.theme == 'dark' else '#12314b'};
        margin-right: 0.5rem;
        font-size: 0.8rem;
        font-weight: 600;
        border: 1px solid rgba(125, 211, 252, 0.30);
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

    .kpi-grid {{
        display: grid;
        grid-template-columns: repeat(5, minmax(0, 1fr));
        gap: 0.75rem;
        margin-bottom: 0.75rem;
    }}

    .st-key-kpi_total button,
    .st-key-kpi_high_fit button,
    .st-key-kpi_deadline_7d button,
    .st-key-kpi_saved button,
    .st-key-kpi_favorites button {{
        width: 100%;
        min-height: 108px;
        border-radius: 14px;
        border: 1px solid rgba(125, 211, 252, 0.34);
        padding: 0.82rem 0.95rem;
        text-align: left;
        white-space: pre-line;
        line-height: 1.23;
        color: var(--text-primary) !important;
        font-weight: 600;
        letter-spacing: 0.01em;
        position: relative;
        overflow: hidden;
        transition: transform 0.18s ease, box-shadow 0.18s ease, border-color 0.18s ease;
        animation: cardRise 0.45s ease-out both;
    }}

    .st-key-kpi_total button::before,
    .st-key-kpi_high_fit button::before,
    .st-key-kpi_deadline_7d button::before,
    .st-key-kpi_saved button::before,
    .st-key-kpi_favorites button::before {{
        content: "";
        position: absolute;
        top: -26%;
        left: -120%;
        width: 72%;
        height: 170%;
        transform: skewX(-20deg);
        background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.18), transparent);
        animation: sweep 7.5s linear infinite;
    }}

    .st-key-kpi_total button::after,
    .st-key-kpi_high_fit button::after,
    .st-key-kpi_deadline_7d button::after,
    .st-key-kpi_saved button::after,
    .st-key-kpi_favorites button::after {{
        content: "";
        position: absolute;
        top: -20%;
        left: -135%;
        width: 85%;
        height: 150%;
        transform: skewX(-22deg);
        background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.14), transparent);
        transition: left 0.8s ease;
    }}

    .st-key-kpi_total button:hover,
    .st-key-kpi_high_fit button:hover,
    .st-key-kpi_deadline_7d button:hover,
    .st-key-kpi_saved button:hover,
    .st-key-kpi_favorites button:hover {{
        transform: translateY(-3px);
        box-shadow: 0 12px 24px rgba(0, 0, 0, 0.28);
        border-color: rgba(125, 211, 252, 0.62);
        animation: haloPulse 1.8s ease-in-out infinite;
    }}

    .st-key-kpi_total button:hover::after,
    .st-key-kpi_high_fit button:hover::after,
    .st-key-kpi_deadline_7d button:hover::after,
    .st-key-kpi_saved button:hover::after,
    .st-key-kpi_favorites button:hover::after {{
        left: 155%;
    }}

    .st-key-kpi_total button {{
        background: linear-gradient(135deg, {'#123b5d' if st.session_state.theme == 'dark' else '#eaf5ff'} 0%, {'#1d5e90' if st.session_state.theme == 'dark' else '#d6ecff'} 100%);
        border-color: {'#3b81b0' if st.session_state.theme == 'dark' else '#9bc6e8'};
        animation-delay: 0s;
    }}

    .st-key-kpi_high_fit button {{
        background: linear-gradient(135deg, {'#103e4f' if st.session_state.theme == 'dark' else '#e8f9ff'} 0%, {'#17607a' if st.session_state.theme == 'dark' else '#d3f0ff'} 100%);
        border-color: {'#2f7f9f' if st.session_state.theme == 'dark' else '#97cfe9'};
        animation-delay: 0.05s;
    }}

    .st-key-kpi_deadline_7d button {{
        background: linear-gradient(135deg, {'#183652' if st.session_state.theme == 'dark' else '#edf7ff'} 0%, {'#25557c' if st.session_state.theme == 'dark' else '#d8ecff'} 100%);
        border-color: {'#4578a4' if st.session_state.theme == 'dark' else '#a5cae8'};
        animation-delay: 0.1s;
    }}

    .st-key-kpi_saved button {{
        background: linear-gradient(135deg, {'#113f47' if st.session_state.theme == 'dark' else '#e9fbff'} 0%, {'#1a5f68' if st.session_state.theme == 'dark' else '#d8f3ff'} 100%);
        border-color: {'#418995' if st.session_state.theme == 'dark' else '#a4d7e5'};
        animation-delay: 0.15s;
    }}

    .st-key-kpi_favorites button {{
        background: linear-gradient(135deg, {'#1a3152' if st.session_state.theme == 'dark' else '#eef6ff'} 0%, {'#274a76' if st.session_state.theme == 'dark' else '#dcecff'} 100%);
        border-color: {'#4a78aa' if st.session_state.theme == 'dark' else '#a9c7e8'};
        animation-delay: 0.2s;
    }}

    .kpi-label {{
        font-size: 0.76rem;
        font-weight: 600;
        letter-spacing: 0.02em;
        color: var(--text-secondary);
        text-transform: uppercase;
    }}

    .kpi-value {{
        margin-top: 0.35rem;
        font-size: 1.35rem;
        line-height: 1.2;
        font-weight: 700;
        color: var(--text-primary);
    }}

    .kpi-delta {{
        margin-top: 0.2rem;
        font-size: 0.75rem;
        color: var(--text-secondary);
    }}

    .tone-navy {{
        background: linear-gradient(135deg, {'#123b5d' if st.session_state.theme == 'dark' else '#eaf5ff'} 0%, {'#1d5e90' if st.session_state.theme == 'dark' else '#d6ecff'} 100%);
        border-color: {'#3b81b0' if st.session_state.theme == 'dark' else '#9bc6e8'};
    }}

    .tone-green {{
        background: linear-gradient(135deg, {'#102e28' if st.session_state.theme == 'dark' else '#edf9f2'} 0%, {'#0f2621' if st.session_state.theme == 'dark' else '#e4f3ea'} 100%);
        border-color: {'#2b5a50' if st.session_state.theme == 'dark' else '#c2e3d1'};
    }}

    .tone-amber {{
        background: linear-gradient(135deg, {'#183652' if st.session_state.theme == 'dark' else '#edf7ff'} 0%, {'#25557c' if st.session_state.theme == 'dark' else '#d8ecff'} 100%);
        border-color: {'#4578a4' if st.session_state.theme == 'dark' else '#a5cae8'};
    }}

    .tone-plum {{
        background: linear-gradient(135deg, {'#1a3152' if st.session_state.theme == 'dark' else '#eef6ff'} 0%, {'#274a76' if st.session_state.theme == 'dark' else '#dcecff'} 100%);
        border-color: {'#4a78aa' if st.session_state.theme == 'dark' else '#a9c7e8'};
    }}

    .tone-cyan {{
        background: linear-gradient(135deg, {'#2f4b28' if st.session_state.theme == 'dark' else '#eefae9'} 0%, {'#3d632f' if st.session_state.theme == 'dark' else '#dff1d2'} 100%);
        border-color: {'#7fb36a' if st.session_state.theme == 'dark' else '#b8d9a3'};
    }}

    .scan-hero {{
        border: 1px solid var(--border-color);
        border-radius: 14px;
        padding: 0.95rem 1rem;
        margin-bottom: 0.8rem;
        position: relative;
        overflow: hidden;
        background:
            radial-gradient(420px 130px at 8% -32%, rgba(56,189,248,0.22), transparent 72%),
            radial-gradient(320px 150px at 92% -38%, rgba(125,211,252,0.18), transparent 74%),
            linear-gradient(120deg, rgba(17,49,76,0.94) 0%, rgba(11,31,50,0.94) 100%);
        box-shadow: 0 10px 24px rgba(6, 14, 25, 0.24);
        animation: cardRise 0.45s ease-out both;
    }}

    .scan-hero::after {{
        content: "";
        position: absolute;
        inset: 0;
        background: linear-gradient(105deg, transparent 35%, rgba(255,255,255,0.08) 50%, transparent 65%);
        transform: translateX(-115%);
        animation: sweep 8.5s ease-in-out infinite;
        pointer-events: none;
    }}

    .scan-hero-title {{
        margin: 0;
        color: #eaf7ff;
        font-size: 1.08rem;
        font-weight: 680;
        letter-spacing: 0.01em;
    }}

    .scan-hero-sub {{
        margin-top: 0.32rem;
        color: #b9def5;
        font-size: 0.86rem;
        line-height: 1.4;
    }}

    .section-kicker {{
        color: var(--text-secondary);
        font-size: 0.76rem;
        font-weight: 640;
        letter-spacing: 0.06em;
        text-transform: uppercase;
        margin-bottom: 0.25rem;
    }}

    .st-key-preset_kenya button,
    .st-key-preset_africa button,
    .st-key-preset_global button {{
        border: 1px solid rgba(148, 163, 184, 0.35) !important;
        background: rgba(56, 189, 248, 0.22) !important;
    }}

    .st-key-preset_kenya button:hover,
    .st-key-preset_africa button:hover,
    .st-key-preset_global button:hover {{
        background: rgba(125, 211, 252, 0.38) !important;
    }}

    .quick-preset-note {{
        color: var(--text-secondary);
        font-size: 0.78rem;
        margin-top: 0.25rem;
    }}

    .result-card {{
        border: 1px solid var(--border-color);
        border-radius: 14px;
        padding: 0.95rem 1rem 0.85rem;
        margin-bottom: 0.8rem;
        background: linear-gradient(140deg, rgba(18, 48, 74, 0.94) 0%, rgba(10, 30, 49, 0.94) 100%);
        position: relative;
        overflow: hidden;
        animation: cardRise 0.38s ease-out both;
        transition: transform 0.16s ease, box-shadow 0.16s ease;
    }}

    .result-card:hover {{
        transform: translateY(-2px);
        box-shadow: 0 10px 22px rgba(3, 9, 19, 0.28);
    }}

    .result-card::before {{
        content: "";
        position: absolute;
        inset: 0 auto 0 0;
        width: 4px;
        background: #38bdf8;
    }}

    .result-card::after {{
        content: "";
        position: absolute;
        top: -60%;
        left: -80%;
        width: 48%;
        height: 220%;
        transform: rotate(14deg);
        background: linear-gradient(90deg, transparent, rgba(255,255,255,0.07), transparent);
        animation: sweep 10s linear infinite;
        pointer-events: none;
    }}

    .result-card.high::before {{
        background: #16a34a;
    }}

    .result-card.med::before {{
        background: #d97706;
    }}

    .result-card.low::before {{
        background: #8b6f64;
    }}

    .result-header {{
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        gap: 0.75rem;
    }}

    .result-title {{
        margin: 0;
        color: #eaf7ff;
        font-size: 1.03rem;
        line-height: 1.35;
        font-weight: 650;
        max-width: 86%;
    }}

    .result-badges {{
        display: flex;
        flex-direction: column;
        gap: 0.35rem;
        align-items: flex-end;
    }}

    .badge-score {{
        border-radius: 999px;
        padding: 0.26rem 0.58rem;
        font-size: 0.74rem;
        font-weight: 700;
        letter-spacing: 0.01em;
        border: 1px solid rgba(255,255,255,0.15);
        color: #eaf7ff;
        background: rgba(30, 74, 111, 0.72);
    }}

    .badge-score.high {{
        background: rgba(22, 163, 74, 0.23);
        border-color: rgba(22, 163, 74, 0.55);
        color: #dcfce7;
    }}

    .badge-score.med {{
        background: rgba(217, 119, 6, 0.23);
        border-color: rgba(217, 119, 6, 0.55);
        color: #fef3c7;
    }}

    .badge-score.low {{
        background: rgba(139, 111, 100, 0.30);
        border-color: rgba(187, 149, 132, 0.45);
        color: #eaf7ff;
    }}

    .meta-chips {{
        display: flex;
        flex-wrap: wrap;
        gap: 0.4rem;
        margin-top: 0.62rem;
    }}

    .meta-chip {{
        border-radius: 999px;
        padding: 0.2rem 0.52rem;
        font-size: 0.72rem;
        font-weight: 560;
        border: 1px solid rgba(148, 163, 184, 0.32);
        color: #e1f4ff;
        background: rgba(31, 70, 103, 0.42);
    }}

    .meta-chip.deadline {{
        border-color: rgba(56, 189, 248, 0.58);
        background: rgba(14, 116, 144, 0.24);
    }}

    .meta-chip.deadline.urgent {{
        border-color: rgba(14, 165, 233, 0.62);
        background: rgba(2, 132, 199, 0.26);
    }}

    .meta-chip.deadline.overdue {{
        border-color: rgba(239, 68, 68, 0.6);
        background: rgba(153, 27, 27, 0.3);
    }}
    .meta-chip.direct {{
        border-color: rgba(16, 185, 129, 0.58);
        background: rgba(5, 150, 105, 0.26);
        color: #d1fae5;
    }}

    .result-summary {{
        margin-top: 0.55rem;
        color: #b9def5;
        font-size: 0.84rem;
        line-height: 1.45;
        max-width: 100%;
    }}

    .result-actions {{
        margin-top: 0.75rem;
        padding-top: 0.65rem;
        border-top: 1px dashed rgba(148, 163, 184, 0.28);
    }}

    .keyword-card {{
        margin-top: 0.62rem;
        padding: 0.55rem 0.65rem;
        border: 1px solid rgba(148, 163, 184, 0.30);
        border-radius: 10px;
        background: rgba(21, 52, 79, 0.55);
    }}

    .keyword-card-title {{
        color: #bfe4fb;
        font-size: 0.72rem;
        font-weight: 650;
        letter-spacing: 0.02em;
        text-transform: uppercase;
        margin-bottom: 0.35rem;
    }}

    .keyword-chips {{
        display: flex;
        flex-wrap: wrap;
        gap: 0.35rem;
    }}

    .keyword-chip {{
        border-radius: 999px;
        padding: 0.18rem 0.5rem;
        font-size: 0.71rem;
        font-weight: 560;
        border: 1px solid rgba(103, 128, 165, 0.5);
        color: #e1f4ff;
        background: rgba(26, 66, 100, 0.52);
    }}

    .keyword-empty {{
        font-size: 0.76rem;
        color: #9cc7df;
    }}

    .result-muted {{
        color: #8fbad3;
        font-size: 0.74rem;
        font-weight: 520;
        letter-spacing: 0.01em;
        margin-top: 0.45rem;
    }}

    .deadline-pill {{
        border-radius: 999px;
        padding: 0.22rem 0.55rem;
        font-size: 0.7rem;
        font-weight: 700;
        border: 1px solid rgba(148, 163, 184, 0.38);
        color: #eaf7ff;
        background: rgba(24, 59, 91, 0.45);
    }}

    .deadline-pill.urgent {{
        border-color: rgba(14, 165, 233, 0.62);
        background: rgba(2, 132, 199, 0.26);
        color: #e0f2fe;
    }}

    .deadline-pill.upcoming {{
        border-color: rgba(56, 189, 248, 0.62);
        background: rgba(14, 116, 144, 0.30);
        color: #e0f2fe;
    }}

    .deadline-pill.overdue {{
        border-color: rgba(239, 68, 68, 0.6);
        background: rgba(153, 27, 27, 0.32);
        color: #fee2e2;
    }}

    @media (max-width: 1200px) {{
        .kpi-grid {{
            grid-template-columns: repeat(2, minmax(0, 1fr));
        }}
    }}

    @media (prefers-reduced-motion: reduce) {{
        .stApp,
        h1,
        .hero-banner,
        .scan-hero,
        .scan-hero::after,
        .result-card,
        .result-card::after,
        .st-key-kpi_total button,
        .st-key-kpi_high_fit button,
        .st-key-kpi_deadline_7d button,
        .st-key-kpi_saved button,
        .st-key-kpi_favorites button {{
            animation: none !important;
            transition: none !important;
        }}
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


def _exclude_expired_tenders(tenders):
    """Hide tenders with a parsed deadline in the past."""
    today = _utcnow().date()
    out = []
    for tender in tenders:
        d = _parse_deadline_value(getattr(tender, "deadline", ""))
        if d is None or d >= today:
            out.append(tender)
    return out


def _exclude_stale_no_deadline_tenders(tenders):
    """Hide low-signal no-deadline tenders that are typically stale notices."""
    out = []
    for tender in tenders:
        deadline_val = _parse_deadline_value(getattr(tender, "deadline", ""))
        if deadline_val is not None:
            out.append(tender)
            continue

        score = float(getattr(tender, "score", 0) or 0)
        likely = (getattr(tender, "likely_fit_for_f2", "") or "").strip().lower()
        category = (getattr(tender, "category", "") or "").strip().lower()
        lifecycle = (getattr(tender, "timing_status", "") or "").strip().lower()

        # Common stale/noisy profile: no deadline + low score + uncertain/discuss + pipeline/general category.
        looks_stale = (
            score < 45
            and likely in {"uncertain", "discuss", "conditional"}
            and category in {"pipeline", "general", "uncategorized", "unclassified"}
            and lifecycle in {"", "open", "pre_notice"}
        )
        if looks_stale:
            continue
        out.append(tender)
    return out


def _lifecycle_label(value: str) -> str:
    mapping = {
        "open": "Open",
        "pre_notice": "Pre-Notice",
        "awarded": "Awarded",
        "clarification": "Clarification",
        "cancelled": "Cancelled",
    }
    return mapping.get((value or "").strip().lower(), "Open")


MARKET_FOCUS_OPTIONS = ["Kenya First", "Africa First", "Global Reach"]
AFRICA_COUNTRIES = {
    "algeria", "angola", "benin", "botswana", "burkina faso", "burundi", "cabo verde",
    "cameroon", "central african republic", "chad", "comoros", "congo",
    "democratic republic of the congo", "djibouti", "egypt", "equatorial guinea",
    "eritrea", "eswatini", "ethiopia", "gabon", "gambia", "ghana", "guinea",
    "guinea-bissau", "ivory coast", "cote d ivoire", "kenya", "lesotho", "liberia",
    "libya", "madagascar", "malawi", "mali", "mauritania", "mauritius", "morocco",
    "mozambique", "namibia", "niger", "nigeria", "rwanda", "sao tome and principe",
    "senegal", "seychelles", "sierra leone", "somalia", "south africa",
    "south sudan", "sudan", "tanzania", "togo", "tunisia", "uganda", "zambia",
    "zimbabwe",
}
AFRICA_HINT_TERMS = {
    "africa", "african", "kenya", "uganda", "tanzania", "rwanda", "ghana",
    "nigeria", "south africa", "zambia", "ethiopia", "eswatini", "afdb",
}
AFRICA_CCTLD_TOKENS = {
    ".ke", ".ug", ".tz", ".rw", ".za", ".gh", ".ng", ".zm", ".et", ".sz",
    ".bw", ".mz", ".mw", ".na", ".sn", ".ci", ".cm", ".ma", ".tn", ".eg",
    ".dz", ".ao", ".zw", ".mu",
}


def _norm_text(value: str) -> str:
    return (value or "").strip().lower()


def _matches_market_focus(tender, market_focus: str) -> bool:
    focus = _norm_text(market_focus)
    if not focus or focus in {"all", "global reach", "global", "worldwide"}:
        return True

    country = _norm_text(getattr(tender, "country", ""))
    buyer = _norm_text(getattr(tender, "buyer", ""))
    source = _norm_text(getattr(tender, "search_source", ""))
    link = _norm_text(getattr(tender, "link", ""))
    title = _norm_text(getattr(tender, "title_translated", "") or getattr(tender, "title", ""))
    haystack = f"{country} {buyer} {source} {title} {link}"
    haystack_no_country = f"{buyer} {source} {title} {link}"
    has_ke_domain = ".ke" in link
    has_other_africa_domain = any(token in link for token in AFRICA_CCTLD_TOKENS if token != ".ke")

    if focus in {"kenya first", "kenya", "kenya_first"}:
        # Prefer URL signal over stale stored country values.
        if has_other_africa_domain and not has_ke_domain:
            return "kenya" in haystack_no_country
        return has_ke_domain or ("kenya" in haystack_no_country) or (country == "kenya")

    if focus in {"africa first", "africa", "africa_first"}:
        if country in AFRICA_COUNTRIES:
            return True
        if any(term in haystack for term in AFRICA_HINT_TERMS):
            return True
        return any(token in link for token in AFRICA_CCTLD_TOKENS)

    return True


F2_FILTER_STATUSES = {"true", "strategic", "discuss", "conditional", "uncertain"}
STRICT_F2_STATUSES = {"true", "strategic", "discuss", "conditional"}
NOISY_TITLE_HINTS = (
    "clarification",
    "corrigendum",
    "addendum",
    "award",
    "winner",
    "minutes",
    "pre-bid meeting",
)

# Optional: load API key from Streamlit secrets for persistent cloud deployments.
try:
    if "SERPAPI_API_KEY" in st.secrets and st.secrets["SERPAPI_API_KEY"]:
        os.environ["SERPAPI_API_KEY"] = str(st.secrets["SERPAPI_API_KEY"])
except Exception:
    pass

# Hide generic governance terms from per-result keyword chips.
GENERIC_KEYWORD_BLOCKLIST = {
    "government",
    "public sector",
    "public institution",
    "government agency",
    "ministry",
    "department",
    "authority",
    "commission",
    "judiciary",
    "local authority",
    "county government",
    "parastatal",
    "state corporation",
    "municipal",
    "municipality",
    "unavailable",
    "keyword unavailable",
    "keyword: unavailable",
    # Generic broad-capture terms (too weak on their own)
    "ict",
    "tender",
    "tender discovery",
}

GENERIC_RESULT_TITLE_HINTS = {
    "procurement plans",
    "procurement plan",
    "procurement reports",
    "report",
    "reports",
    "guidance",
    "guideline",
    "guidelines",
    "manual",
    "policy",
    "procedure",
    "strategic plan",
    "master plan",
    "masterplan",
    "service charter",
    "tender board decisions",
    "board decisions",
    "available bidding opportunities",
    "public procurement information portal",
    "government procurement portal",
    "view projects",
    "tenders and proposal",
}

OPPORTUNITY_RESULT_TITLE_HINTS = {
    "request for",
    "invitation",
    "tender advert",
    "tender document",
    "expression of interest",
    "eoi",
    "rfp",
    "rfq",
    "tender no",
    "bid no",
    "lot ",
    "submission deadline",
}

LISTING_URL_PATH_HINTS = {
    "home",
    "tender",
    "tenders",
    "procurement",
    "opportunity",
    "opportunities",
    "notice",
    "notices",
    "publications",
    "publication",
    "resources",
    "guidance",
    "guidelines",
    "procurementplans",
    "plans",
}


def _keyword_count(matched: str) -> int:
    if not matched:
        return 0
    return len(_keyword_list(matched, fallback_text="", limit=50))


def _keyword_list(matched: str, fallback_text: str = "", limit: int = 8):
    if not matched:
        parts = []
    else:
        parts = []
        for token in matched.split(","):
            t = token.strip()
            if not t:
                continue
            # Normalize display prefixes like "DOMAIN:term" / "keyword: term" / "broad:term"
            t = re.sub(r"^(keyword|broad|domain)\s*:\s*", "", t, flags=re.IGNORECASE).strip()
            if ":" in t:
                head, tail = t.split(":", 1)
                if head.isalpha() and len(head) <= 16:
                    t = tail.strip()
            # Remove trailing summaries like "(+3 more)" if present.
            t = re.sub(r"\(\+\d+\s+more\)\s*$", "", t).strip()
            if t:
                parts.append(t)

    # Fallback extraction from title/description if stored keyword list is empty.
    if not parts and fallback_text:
        text = fallback_text.lower()
        # Prefer longer phrases first to avoid generic substring noise.
        for kw in sorted(ALL_KEYWORDS, key=len, reverse=True):
            k = (kw or "").strip().lower()
            if not k:
                continue
            if k in text:
                parts.append(k)

    if not parts:
        return []

    seen = set()
    unique = []
    for p in parts:
        key = p.lower()
        if "unavailable" in key:
            continue
        if key in GENERIC_KEYWORD_BLOCKLIST:
            continue
        if key in seen:
            continue
        seen.add(key)
        unique.append(p)
        if len(unique) >= limit:
            break
    return unique


def _has_display_keywords(tender) -> bool:
    if _keyword_list(getattr(tender, "keywords_matched", ""), fallback_text="", limit=1):
        return True
    # Keep potentially relevant rows visible when DB keyword payload is thin.
    return bool(_direct_match_keywords(tender, limit=1))


def _tender_fallback_text(tender) -> str:
    display_title = tender.title_translated if tender.title_translated and tender.title_translated != tender.title else tender.title
    description_line = (tender.description_translated or tender.description or "").replace("\n", " ").strip()
    return f"{display_title} {description_line}".strip()


def _direct_match_keywords(tender, limit: int = 3):
    text = _tender_fallback_text(tender).lower()
    if not text:
        return []
    matches = []
    for kw in sorted(ALL_KEYWORDS, key=len, reverse=True):
        k = (kw or "").strip().lower()
        if not k or k in GENERIC_KEYWORD_BLOCKLIST or "unavailable" in k:
            continue
        if k in text:
            matches.append(k)
            if len(matches) >= limit:
                break
    return matches


def _why_matched_summary(tender):
    try:
        raw = getattr(tender, "scoring_breakdown", "") or ""
        breakdown = json.loads(raw) if isinstance(raw, str) and raw else {}
    except Exception:
        breakdown = {}

    matched_phrases = breakdown.get("matched_phrases", []) or []
    noisy_phrases = {"tender discovery", "discovery:tender"}
    matched_phrases = [
        p for p in matched_phrases
        if (p or "").strip().lower() not in noisy_phrases
    ]
    domains = breakdown.get("domains_matched", []) or []
    priority = breakdown.get("priority", "") or getattr(tender, "priority_level", "")
    fit = breakdown.get("likely_fit_for_F2", "") or getattr(tender, "likely_fit_for_f2", "")
    keywords_found = int(breakdown.get("keywords_found", 0) or 0)
    return {
        "keywords_found": keywords_found,
        "matched_phrases": matched_phrases[:6],
        "domains": domains[:6],
        "priority": priority,
        "fit": fit,
    }


def _has_keyword_signal(tender) -> bool:
    # Keep only rows with explicit matched keywords or a direct F2 keyword hit in text.
    if _keyword_count(getattr(tender, "keywords_matched", "")) > 0:
        return True
    return bool(_direct_match_keywords(tender, limit=1))


def _looks_like_generic_result_target(tender) -> bool:
    title = (getattr(tender, "title_translated", "") or getattr(tender, "title", "") or "").strip().lower()
    link = (getattr(tender, "link", "") or "").strip()

    if not title or not link:
        return True

    has_opportunity_title_hint = any(h in title for h in OPPORTUNITY_RESULT_TITLE_HINTS)
    has_generic_title_hint = any(h in title for h in GENERIC_RESULT_TITLE_HINTS)

    parsed = urlsplit(link)
    host = (parsed.netloc or "").lower().strip()
    path = (parsed.path or "").strip("/").lower()
    path_tokens = [tok for tok in path.split("/") if tok]
    is_pdf = path.endswith(".pdf")

    is_blocked_host = host in {"youtube.com", "www.youtube.com", "youtu.be"}
    is_home_or_listing = (
        (not path and not parsed.query)
        or (len(path_tokens) == 1 and path_tokens[0] in LISTING_URL_PATH_HINTS and not parsed.query and not is_pdf)
        or (len(path_tokens) <= 2 and path_tokens[-1] in {"tenders", "procurement", "opportunities", "publications"} and not is_pdf)
    )

    if is_blocked_host:
        return True
    if has_generic_title_hint and not has_opportunity_title_hint:
        return True
    if is_home_or_listing and not has_opportunity_title_hint:
        return True
    return False


def _apply_result_visibility_filters(tenders):
    before_keyword_signal = len(tenders)
    tenders = [t for t in tenders if _has_keyword_signal(t)]
    removed_no_keyword_signal = before_keyword_signal - len(tenders)

    before_generic_target = len(tenders)
    tenders = [t for t in tenders if not _looks_like_generic_result_target(t)]
    removed_generic_targets = before_generic_target - len(tenders)
    return tenders, removed_no_keyword_signal, removed_generic_targets


def _passes_strict_quality(tender, min_score: int = 20) -> bool:
    score = float(getattr(tender, "score", 0) or 0)
    if score < min_score:
        return False

    likely_fit = (getattr(tender, "likely_fit_for_f2", "") or "").strip().lower()
    if likely_fit not in STRICT_F2_STATUSES:
        return False

    procurement_status = (getattr(tender, "procurement_status", "") or "").strip().lower()
    if procurement_status in {"locked", "conditional_nogo"}:
        return False

    timing_status = (getattr(tender, "timing_status", "") or "").strip().lower()
    if timing_status in {"awarded", "clarification", "cancelled"}:
        return False

    title = (getattr(tender, "title_translated", "") or getattr(tender, "title", "") or "").lower()
    if any(hint in title for hint in NOISY_TITLE_HINTS):
        return False

    deadline_exists = _parse_deadline_value(getattr(tender, "deadline", "")) is not None
    description = (
        (getattr(tender, "description_translated", "") or getattr(tender, "description", "") or "")
        .replace("\n", " ")
        .strip()
    )
    kw_count = _keyword_count(getattr(tender, "keywords_matched", ""))

    # Avoid weak cards: thin metadata + low confidence + no deadline.
    if not deadline_exists and len(description) < 80 and score < 45:
        return False
    if kw_count < 2 and score < 40:
        return False
    if not deadline_exists and kw_count < 3 and score < 50:
        return False

    return True

def init_db(perform_translation=False):
    """Initialize database with app context"""
    with app.app_context():
        # Curated baseline focused on Kenya/Africa first, then global.
        # tuple format: (name, url, favorite, active_by_default)
        default_sources_data = [
            # Kenya (primary market)
            ("Kenya PPIP", "https://tenders.go.ke/website/tenders/all", True, True),
            ("ICT Authority", "https://icta.go.ke/tenders/", True, True),
            ("KEMSA Tenders", "https://www.kemsa.co.ke/tenders/", True, True),
            ("KRA Tenders", "https://www.kra.go.ke/en/tenders", True, True),
            ("KAA Procurement", "https://www.kaa.go.ke/business-opportunities/procurement/", True, True),
            ("KETRACO Tenders", "https://www.ketraco.co.ke/procurement/tenders/open-tenders", True, True),
            ("KPA Tenders", "https://kpa.co.ke/procurement/", True, True),
            ("Kenya Railways", "https://krc.co.ke/tenders/", True, True),
            ("NTSA Tenders", "https://ntsa.go.ke/tenders/", False, True),
            ("CAK Tenders", "https://cak.go.ke/tenders", False, True),
            ("KEBS Tenders", "https://www.kebs.org/index.php?option=com_content&view=article&id=190", False, True),
            ("CBK Tenders", "https://www.centralbank.go.ke/tenders/", False, True),
            ("NEMA Tenders", "https://www.nema.go.ke/index.php/tenders", False, True),

            # Africa focus (including cBrain presence regions)
            ("South Africa eTender", "https://www.etenders.gov.za/", True, True),
            ("Uganda PPDA", "https://www.ppda.go.ug/", True, True),
            ("Tanzania PPRA", "https://www.ppra.go.tz/", True, True),
            ("Nigeria BPP", "https://www.bpp.gov.ng/", True, True),
            ("Nigeria BPP P-COMS", "https://pcoms.bpp.gov.ng/", False, True),
            ("Ghana PPA", "https://ppa.gov.gh/", True, True),
            ("GHANEPS", "https://www.ghaneps.gov.gh/", True, True),
            ("Zambia ZPPA", "https://www.zppa.org.zm/", False, True),
            ("Rwanda RPPA", "https://www.rppa.gov.rw/", False, False),
            ("TradeMark Africa Procurement", "https://trademarkafrica.com/procurement/", True, True),
            ("AfDB Procurement", "https://www.afdb.org/en/projects-and-operations/procurement", True, True),
            ("Eswatini SPPRA", "https://www.sppra.co.sz", False, True),

            # Global official sources (including cBrain footprint markets)
            ("UNDP Procurement Notices", "https://procurement-notices.undp.org/", True, True),
            ("UN Global Marketplace", "https://www.ungm.org/Public/Notice", True, True),
            ("UNOPS Opportunities", "https://www.unops.org/business-opportunities", True, True),
            ("World Bank Procurement", "https://projects.worldbank.org/en/projects-operations/procurement", True, True),
            ("DevBusiness (World Bank)", "https://devbusiness.un.org/", True, True),
            ("WFP Procurement", "https://www.wfp.org/procurement", False, True),
            ("WHO Procurement", "https://www.who.int/about/accountability/procurement", False, True),
            ("FAO Procurement", "https://www.fao.org/unfao/procurement/", False, True),
            ("ILO Procurement", "https://www.ilo.org/procurement/", False, True),
            ("TED Europa Tenders", "https://ted.europa.eu/en/search/result", True, True),
            ("UK Find a Tender", "https://www.find-tender.service.gov.uk/Search", True, True),
            ("Denmark Udbud", "https://udbud.dk/", False, True),
            ("Germany BUND", "https://www.service.bund.de/Content/DE/Ausschreibungen/Suche/Formular.html", False, False),
            ("France BOAMP", "https://www.boamp.fr/", False, False),
            ("SAM.gov (US Federal)", "https://sam.gov/search/?index=opp&page=1&sort=-modifiedDate", False, False),
            ("Australia AusTender", "https://www.tenders.gov.au/", False, False),
            ("India CPPP", "https://eprocure.gov.in/eprocure/app", False, False),
            ("Singapore GeBIZ", "https://www.gebiz.gov.sg/", False, False),
            ("EU Funding & Tenders", "https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/opportunities/topic-search", False, False),
            ("Commonwealth Secretariat Procurement", "https://thecommonwealth.org/procurement", False, True),
            ("IDB Procurement Projects", "https://www.iadb.org/en/how-we-can-work-together/procurement/procurement-projects", False, True),
            ("AIIB Project Procurement", "https://www.aiib.org/en/opportunities/business/project-procurement/index.html", False, True),
            ("EIB Procurement Calls", "https://www.eib.org/en/about/procurement/all/index.htm", False, True),
        ]
        low_signal_sources = {
            "DgMarket",
            "Global Tenders",
            "Tenders Info",
            "Tendersinfo Kenya",
            "BidDetail",
            "Tender Yetu Platform",
            "MyGov Kenya",
            "DevEx Funding",
            "ReliefWeb Jobs",
            "TenderNews",
            "TendersOnTime",
        }
        low_signal_domains = (
            "dgmarket",
            "globaltenders",
            "tendersinfo",
            "tenderyetu",
            "opentender",
            "devex.com/funding",
            "reliefweb.int/jobs",
            "tendernews",
            "tendersontime",
        )
        hard_block_sources = {
            "MyGov Kenya",
            "Tender Yetu Platform",
            "DgMarket",
            "Global Tenders",
            "Tenders Info",
            "Tendersinfo Kenya",
            "BidDetail",
        }
        hard_block_domains = (
            "tenderyetu",
            "mygov.go.ke/?s=tender",
            "dgmarket",
            "globaltenders",
            "tendersinfo",
            "biddetail",
            "opentender",
        )
        url_replacements = {
            "https://www.ppda.or.ug/": "https://www.ppda.go.ug/",
            "https://tenders.go.ke/": "https://tenders.go.ke/website/tenders/all",
            "https://www.kaa.go.ke/corporate/procurement/": "https://www.kaa.go.ke/business-opportunities/procurement/",
            "https://www.kpa.co.ke/Tenders/Pages/default.aspx": "https://kpa.co.ke/procurement/",
            "https://www.ntsa.go.ke/tenders/": "https://ntsa.go.ke/tenders/",
            "https://ppaghana.org/tenders.asp": "https://ppa.gov.gh/",
            "https://www.ketraco.co.ke/tenders": "https://www.ketraco.co.ke/procurement/tenders/open-tenders",
            "https://www.kengen.co.ke/index.php/procurement.html": "https://www.kengen.co.ke/",
            "https://www.service.bund.de/Content/EN/Ausschreibungen/Suche/Formular.html": "https://www.service.bund.de/Content/DE/Ausschreibungen/Suche/Formular.html",
        }
        
        # Add missing sources (check by URL to avoid duplicates)
        existing_urls = {_canonicalize_url(s.url) for s in TenderSource.query.all()}
        added_count = 0
        for row in default_sources_data:
            if len(row) == 4:
                name, url, is_favorite, active_by_default = row
            else:
                name, url, is_favorite = row
                active_by_default = bool(is_favorite)
            if _canonicalize_url(url) not in existing_urls:
                source = TenderSource(
                    name=name,
                    url=url,
                    active=bool(active_by_default),
                    favorite=bool(is_favorite),
                )
                db.session.add(source)
                added_count += 1
        
        if added_count > 0:
            db.session.commit()
            print(f" Added {added_count} new tender sources")

        # Normalize known outdated source URLs.
        updated_urls = 0
        for source in TenderSource.query.all():
            src_url = _canonicalize_url(source.url)
            for old_url, new_url in url_replacements.items():
                if src_url == _canonicalize_url(old_url):
                    source.url = new_url
                    updated_urls += 1
                    break
        if updated_urls > 0:
            db.session.commit()
            print(f" Updated {updated_urls} source URL(s) to current official endpoints")

        # Keep noisy aggregators available, but disabled by default.
        disabled_count = 0
        for source in TenderSource.query.all():
            name_low = (source.name or "").strip()
            url_low = (source.url or "").lower()
            is_low_signal = (
                name_low in low_signal_sources
                or any(dom in url_low for dom in low_signal_domains)
            )
            if is_low_signal and source.active and not source.favorite:
                source.active = False
                disabled_count += 1
        if disabled_count > 0:
            db.session.commit()
            print(f"Disabled {disabled_count} low-signal sources by default")

        # Strictly disable known non-official/aggregator endpoints even if favorited previously.
        blocked_count = 0
        for source in TenderSource.query.all():
            name_low = (source.name or "").strip()
            url_low = (source.url or "").lower()
            is_blocked = (
                name_low in hard_block_sources
                or any(dom in url_low for dom in hard_block_domains)
            )
            if is_blocked and source.active:
                source.active = False
                blocked_count += 1
        if blocked_count > 0:
            db.session.commit()
            print(f"Strict-disabled {blocked_count} blocked source(s)")
        
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


def get_tenders(filters=None, days_window=30, created_after=None):
    """Get tenders with optional filters."""
    with app.app_context():
        query = TenderResult.query
        if created_after is None and filters:
            created_after = filters.get("created_after")
        if created_after is not None:
            query = query.filter(TenderResult.created_at >= created_after)
        if days_window is not None:
            since = _utcnow() - timedelta(days=days_window)
            query = query.filter(TenderResult.created_at >= since)
        
        if filters:
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
            min_score = filters.get("min_score")
            if min_score is not None:
                try:
                    min_score = float(min_score)
                except (TypeError, ValueError):
                    min_score = 0.0
                if min_score > 0:
                    query = query.filter(TenderResult.score >= min_score)
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
                f2_clause = (
                    TenderResult.likely_fit_for_f2.in_(list(F2_FILTER_STATUSES))
                )
                query = query.filter(f2_clause)
                query = query.filter(~TenderResult.procurement_status.in_(["locked", "conditional_nogo"]))
            if filters.get('open_only'):
                query = query.filter(
                    ~TenderResult.procurement_status.in_(["locked", "conditional_nogo"])
                )
                query = query.filter(
                    ~TenderResult.timing_status.in_(["awarded", "clarification", "cancelled"])
                )
        
        # Sort (baseline in SQL; final ranking can be blended with ML below).
        sort_by = filters.get('sort_by', 'score') if filters else 'score'
        if sort_by == 'score':
            query = query.order_by(TenderResult.score.desc())
        elif sort_by == 'date':
            query = query.order_by(TenderResult.created_at.desc())
        elif sort_by == 'deadline':
            query = query.order_by(TenderResult.deadline.asc())

        tenders = query.all()

        if filters:
            market_focus = filters.get("market_focus")
            if market_focus and market_focus != "All":
                tenders = [t for t in tenders if _matches_market_focus(t, market_focus)]

        if filters and filters.get("exclude_expired"):
            tenders = _exclude_expired_tenders(tenders)
        if filters and filters.get("exclude_stale_no_deadline"):
            tenders = _exclude_stale_no_deadline_tenders(tenders)

        if filters and filters.get("strict_quality", False):
            # Always hide explicitly excluded/no-go opportunities in strict view.
            tenders = [
                t for t in tenders
                if (getattr(t, "likely_fit_for_f2", "") or "").strip().lower() not in {"excluded", "no-go"}
            ]
            if filters.get("f2_only"):
                strict_min_score = int(filters.get("strict_min_score", 20) or 20)
                tenders = [t for t in tenders if _passes_strict_quality(t, min_score=strict_min_score)]

        # ML blending for score-sorted lists.
        if sort_by == "score":
            blended = []
            for t in tenders:
                ml_score = predict_relevance(t)
                try:
                    setattr(t, "_ml_score", ml_score if ml_score is not None else None)
                    setattr(t, "_rank_score", blend_score(float(t.score or 0), ml_score))
                except Exception:
                    pass
                blended.append(t)
            tenders = sorted(blended, key=lambda x: float(getattr(x, "_rank_score", x.score or 0.0)), reverse=True)

        return tenders


def get_tenders_with_fallback(filters=None):
    """Get tenders with progressive fallback when strict filters return nothing."""
    if not filters:
        return get_tenders(), True, ""

    base = get_tenders(filters)
    allow_broad_fallback = bool(filters.get("allow_broad_fallback"))
    min_target_results = int(filters.get("min_target_results", 8) or 8)

    if base and (not allow_broad_fallback or len(base) >= min_target_results):
        return base, bool(filters.get("f2_only")), ""

    if base and allow_broad_fallback and len(base) < min_target_results:
        relaxed = dict(filters)
        relaxed["strict_quality"] = False
        relaxed["min_score"] = min(float(filters.get("min_score", 0) or 0), 40.0)
        widened = get_tenders(relaxed)
        if len(widened) > len(base):
            return widened, bool(relaxed.get("f2_only")), (
                f"Only {len(base)} strict matches found. Showing broader set ({len(widened)})."
            )
        return base, bool(filters.get("f2_only")), ""

    if not allow_broad_fallback:
        return [], bool(filters.get("f2_only")), "No tenders matched current filters. Enable 'Broaden if empty' to expand results."

    if not filters.get('f2_only'):
        if filters.get("open_only"):
            relaxed = dict(filters)
            relaxed["open_only"] = False
            widened = get_tenders(relaxed)
            if widened:
                return widened, False, "No open tenders matched. Showing locked/conditional opportunities too."
        anytime = get_tenders(filters, days_window=None)
        if anytime:
            return anytime, False, "No recent matches found. Displaying earlier results."
        return [], False, "No tenders matched current filters."

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


def get_source_performance(days=30, limit=12):
    with app.app_context():
        since = _utcnow() - timedelta(days=days)
        active_sources = TenderSource.query.filter_by(active=True).all()
        rows = []
        for source in active_sources:
            q = TenderResult.query.filter(
                TenderResult.source_id == source.id,
                TenderResult.created_at >= since,
            )
            total = q.count()
            if total == 0:
                continue
            high_fit = q.filter(TenderResult.score >= 70).count()
            avg_score = db.session.query(db.func.avg(TenderResult.score)).filter(
                TenderResult.source_id == source.id,
                TenderResult.created_at >= since,
            ).scalar() or 0.0
            last_seen = db.session.query(db.func.max(TenderResult.created_at)).filter(
                TenderResult.source_id == source.id,
                TenderResult.created_at >= since,
            ).scalar()
            rows.append({
                "source_id": source.id,
                "source": source.name,
                "total": int(total),
                "high_fit": int(high_fit),
                "hit_rate": round((high_fit / total) * 100, 1) if total else 0.0,
                "avg_score": round(float(avg_score), 1),
                "last_seen": last_seen.strftime("%Y-%m-%d") if last_seen else "N/A",
            })
    rows.sort(key=lambda r: (r["total"], r["high_fit"], r["avg_score"]), reverse=True)
    return rows[:max(1, limit)]


def _source_health(row):
    total = int(row.get("total", 0) or 0)
    hit_rate = float(row.get("hit_rate", 0.0) or 0.0)
    avg_score = float(row.get("avg_score", 0.0) or 0.0)

    if total >= 10 and hit_rate >= 18 and avg_score >= 55:
        return "Strong"
    if total >= 5 and (hit_rate < 5 or avg_score < 30):
        return "Weak"
    return "Watch"


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
            record_feedback(tender.id, "favorite" if tender.favorite else "unfavorite", 1.0 if tender.favorite else -1.0)
            return True
    return False

def toggle_saved(tender_id):
    """Toggle saved status"""
    with app.app_context():
        tender = TenderResult.query.get(tender_id)
        if tender:
            tender.saved = not tender.saved
            db.session.commit()
            record_feedback(tender.id, "save" if tender.saved else "unsave", 1.0 if tender.saved else -0.7)
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

def delete_multiple_sources(source_ids):
    """Delete multiple tender sources"""
    with app.app_context():
        try:
            for source_id in source_ids:
                source = TenderSource.query.get(source_id)
                if source:
                    db.session.delete(source)
            db.session.commit()
            return True
        except Exception:
            return False

def delete_all_sources():
    """Delete all tender sources"""
    with app.app_context():
        try:
            TenderSource.query.delete()
            db.session.commit()
            return True
        except Exception:
            return False

def run_tender_scan(scan_depth="fast", discovery_mode="f2_ranked"):
    """Run tender scan"""
    started = time.time()
    depth_map = {
        "fast": {"max_sources": 25, "translate": False, "timeout_s": 75, "per_source_cap": 20},
        "balanced": {"max_sources": 35, "translate": False, "timeout_s": 150, "per_source_cap": 25},
        "full": {"max_sources": None, "translate": True, "timeout_s": 240, "per_source_cap": 30},
    }
    depth_cfg = depth_map.get((scan_depth or "fast").lower(), depth_map["fast"])
    if (discovery_mode or "").lower() == "manual_like":
        # Broader recall profile to mimic manual portal searching.
        manual_depth_map = {
            "fast": {"max_sources": 20, "translate": False, "timeout_s": 75, "per_source_cap": 30},
            "balanced": {"max_sources": 35, "translate": False, "timeout_s": 150, "per_source_cap": 35},
            "full": {"max_sources": None, "translate": False, "timeout_s": 240, "per_source_cap": 40},
        }
        depth_cfg = manual_depth_map.get((scan_depth or "fast").lower(), manual_depth_map["fast"])
    with app.app_context():
        new_tenders = run_scan(
            flask_app=app,
            max_sources=depth_cfg["max_sources"],
            scan_timeout_seconds=depth_cfg["timeout_s"],
            discovery_mode=discovery_mode,
            max_new_per_source=depth_cfg["per_source_cap"],
        )
    # Run translation only in full scans to keep manual scans responsive.
    if depth_cfg["translate"] and new_tenders:
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
    st.caption("Kenya and Africa first. Global expansion ready.")
    st.markdown("---")

    def _queue_sidebar_nav(target_page: str) -> None:
        """Queue sidebar navigation for next rerun to avoid mutating radio state post-render."""
        if target_page in NAV_PAGES:
            st.session_state["_pending_sidebar_page"] = target_page

    requested_nav_raw = _qp_value("nav", "").strip().lower()
    requested_nav = NAV_QUERY_MAP.get(requested_nav_raw)
    nav_request_key = f"{requested_nav_raw}|{_qp_value('tap', '')}"
    if "sidebar_page" not in st.session_state:
        st.session_state["sidebar_page"] = "Dashboard"
    if requested_nav and st.session_state.get("_last_nav_request_key") != nav_request_key:
        st.session_state["sidebar_page"] = requested_nav
        st.session_state["_last_nav_request_key"] = nav_request_key
    pending_nav = st.session_state.pop("_pending_sidebar_page", None)
    if pending_nav in NAV_PAGES:
        st.session_state["sidebar_page"] = pending_nav

    page = st.radio(
        "Navigation",
        NAV_PAGES,
        label_visibility="collapsed",
        key="sidebar_page",
    )
    
    st.markdown("---")
    
    st.caption("2026 cBrain TenderWatch | build 2026-02-17c")

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

    if "dashboard_market_focus" not in st.session_state:
        st.session_state["dashboard_market_focus"] = "Africa First"
    if st.session_state.get("dashboard_market_focus") not in MARKET_FOCUS_OPTIONS:
        st.session_state["dashboard_market_focus"] = "Africa First"

    focus_col, focus_note_col = st.columns([1.3, 3.7])
    with focus_col:
        dashboard_market_focus = st.selectbox(
            "Market Focus",
            MARKET_FOCUS_OPTIONS,
            key="dashboard_market_focus",
            help="Filter dashboard lists to Kenya, Africa, or global opportunities.",
        )
    with focus_note_col:
        st.caption("Dashboard is now streamlined. Open the detailed panel below only when deeper analysis is needed.")

    c1, c2, c3, c4, c5 = st.columns(5)

    with c1:
        label = f"LIVE OPPORTUNITIES\n{stats['total']}\n{stats.get('delta_total') or ''}"
        if st.button(label, key="kpi_total", width="stretch"):
            _queue_sidebar_nav("Scan & Results")
            st.session_state["results_mode"] = "historical"
            st.session_state["scan_sort_by"] = "date"
            st.rerun()

    with c2:
        label = f"HIGH FIT PIPELINE\n{stats['high_score']}\n{stats.get('delta_high_score') or ''}"
        if st.button(label, key="kpi_high_fit", width="stretch"):
            _queue_sidebar_nav("Scan & Results")
            st.session_state["results_mode"] = "historical"
            st.session_state["scan_sort_by"] = "score"
            st.rerun()

    with c3:
        label = f"DEADLINES IN 7 DAYS\n{stats.get('upcoming_7d', 0)}\nTime-sensitive"
        if st.button(label, key="kpi_deadline_7d", width="stretch"):
            _queue_sidebar_nav("Scan & Results")
            st.session_state["results_mode"] = "historical"
            st.session_state["scan_sort_by"] = "deadline"
            st.rerun()

    with c4:
        label = f"SAVED QUEUE\n{stats['saved']}\n{stats.get('delta_saved') or ''}"
        if st.button(label, key="kpi_saved", width="stretch"):
            _queue_sidebar_nav("Saved")
            st.rerun()

    with c5:
        label = f"FAVORITES\n{stats['favorites']}\n{stats.get('delta_favorites') or ''}"
        if st.button(label, key="kpi_favorites", width="stretch"):
            _queue_sidebar_nav("Favorites")
            st.rerun()

    st.markdown("---")
    st.subheader("Action Queue")

    urgent_col, fit_col = st.columns(2)
    with urgent_col:
        st.markdown("#### Upcoming Deadlines (Next 30 Days)")
        upcoming_deadlines = get_upcoming_deadlines(limit=20, horizon_days=30)
        if dashboard_market_focus != "Global Reach":
            upcoming_deadlines = [
                item for item in upcoming_deadlines
                if _matches_market_focus(item[1], dashboard_market_focus)
            ]
        upcoming_deadlines = upcoming_deadlines[:8]
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
            'market_focus': dashboard_market_focus,
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
    with st.expander("Detailed Pipeline & Source Performance", expanded=False):
        st.subheader("Pipeline Overview")

        col_a, col_b = st.columns([2, 1])
        with col_a:
            recent = get_tenders({'sort_by': 'date', 'market_focus': dashboard_market_focus})[:12]
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
            if recent:
                cat_counts: Dict[str, int] = {}
                for tender in recent:
                    cat = tender.category or "Unclassified"
                    cat_counts[cat] = int(cat_counts.get(cat, 0)) + 1
                cat_df = pd.DataFrame(
                    list(cat_counts.items()),
                    columns=['Category', 'Count']
                ).sort_values('Count', ascending=False)
                st.dataframe(cat_df, hide_index=True, width="stretch")
            else:
                st.caption("No category distribution available yet.")

        st.markdown("---")
        st.subheader("Source Performance")
        source_rows = get_source_performance(days=30, limit=10)
        if source_rows:
            weak_sources = [r for r in source_rows if _source_health(r) == "Weak"]
            action_col1, action_col2 = st.columns([2, 5])
            with action_col1:
                if st.button("Disable weak sources", key="disable_weak_sources_btn", width="stretch"):
                    disabled = 0
                    for r in weak_sources:
                        try:
                            if toggle_source(r["source_id"]):
                                disabled += 1
                        except Exception:
                            continue
                    if disabled:
                        st.success(f"Disabled {disabled} weak source(s).")
                    else:
                        st.info("No weak sources were disabled.")
                    st.rerun()
            with action_col2:
                st.caption("Health is based on last 30 days: volume, high-fit hit rate, and average score.")

            for row in source_rows:
                health = _source_health(row)
                c1, c2, c3, c4, c5, c6, c7 = st.columns([3.3, 0.9, 0.9, 0.9, 0.9, 0.9, 1.2])
                with c1:
                    st.markdown(f"**{row['source']}**")
                    st.caption(f"Last seen: {row['last_seen']} | Health: {health}")
                with c2:
                    st.metric("Results", row["total"])
                with c3:
                    st.metric("High Fit", row["high_fit"])
                with c4:
                    st.metric("Hit Rate", f"{row['hit_rate']}%")
                with c5:
                    st.metric("Avg Score", f"{row['avg_score']}")
                with c6:
                    st.metric("Health", health)
                with c7:
                    if health == "Weak":
                        if st.button("Disable", key=f"disable_src_{row['source_id']}", width="stretch"):
                            if toggle_source(row["source_id"]):
                                st.success(f"Disabled {row['source']}.")
                                st.rerun()
                    else:
                        st.caption(" ")
        else:
            st.caption("No source activity yet in the last 30 days.")

elif page == "Scan & Results":
    st.title("Tender Radar")
    if "results_mode" not in st.session_state:
        st.session_state["results_mode"] = "fresh"  # fresh | session_scan | historical
    if "scan_anchor_utc" not in st.session_state:
        st.session_state["scan_anchor_utc"] = None

    requested_mode = _qp_value("mode", "").strip().lower()
    if requested_mode in {"fresh", "session_scan", "historical"}:
        st.session_state["results_mode"] = requested_mode
        if requested_mode != "session_scan":
            st.session_state["scan_anchor_utc"] = None

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
            f"duration: {info.get('duration_s', 0):.1f}s | "
            f"depth: {info.get('scan_depth', 'fast')}"
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
        st.markdown(
            """
            <div class="scan-hero">
                <div class="scan-hero-title">Tender Command Center</div>
                <div class="scan-hero-sub">
                    Run scans and review opportunities with a simple search and sort workflow.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        ctl1, ctl2, ctl3, ctl4 = st.columns([1.2, 1.4, 1.1, 1.1])
        with ctl1:
            st.markdown("<div class='section-kicker'>Scan Depth</div>", unsafe_allow_html=True)
            scan_depth = st.selectbox(
                "Scan Depth",
                ["fast", "balanced", "full"],
                index=1,
                label_visibility="collapsed",
                help="Fast: priority sources. Balanced: broader coverage. Full: all active sources + translation.",
            )
        with ctl2:
            st.markdown("<div class='section-kicker'>Discovery</div>", unsafe_allow_html=True)
            discovery_mode_label = st.selectbox(
                "Discovery Mode",
                ["F2-ranked", "Manual-like"],
                index=1,
                label_visibility="collapsed",
                help="F2-ranked is stricter and cleaner. Manual-like is broader for scouting.",
            )
            discovery_mode = "manual_like" if discovery_mode_label == "Manual-like" else "f2_ranked"
        with ctl3:
            st.markdown("<div class='section-kicker'>Action</div>", unsafe_allow_html=True)
            if st.button("Run Scan", key="top_scan_button", type="primary", width="stretch"):
                scan_anchor = _utcnow()
                started = time.time()
                with st.spinner("Scanning sources..."):
                    new_tenders = run_tender_scan(scan_depth=scan_depth, discovery_mode=discovery_mode)
                elapsed = time.time() - started
                st.session_state["last_scan_info"] = {
                    "timestamp": _utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
                    "new_count": len(new_tenders),
                    "duration_s": elapsed,
                    "scan_depth": scan_depth,
                    "discovery_mode": discovery_mode,
                }
                if new_tenders:
                    st.session_state["results_mode"] = "session_scan"
                    st.session_state["scan_anchor_utc"] = scan_anchor
                    st.success(f"Scan completed. Found {len(new_tenders)} new tenders.")
                else:
                    st.session_state["results_mode"] = "historical"
                    st.session_state["scan_anchor_utc"] = None
                    st.info("Scan completed with no new tenders. Showing latest available results.")
                st.rerun()
        with ctl4:
            st.markdown("<div class='section-kicker'>View</div>", unsafe_allow_html=True)
            if st.button("Historical", key="load_historical_button", width="stretch"):
                st.session_state["results_mode"] = "historical"
                st.session_state["scan_anchor_utc"] = None
                st.rerun()
            if st.session_state.get("results_mode") != "fresh":
                if st.button("Fresh", key="start_fresh_results_button", width="stretch"):
                    st.session_state["results_mode"] = "fresh"
                    st.session_state["scan_anchor_utc"] = None
                    st.rerun()

        st.markdown("---")

        results_mode = st.session_state.get("results_mode", "fresh")
        if results_mode == "fresh":
            st.markdown(
                """
                <div style='padding:1rem 1.1rem;border:1px solid var(--border-color);border-radius:12px;background:var(--card-bg);margin-bottom:1rem;'>
                    <div style='font-weight:650;color:var(--text-primary);margin-bottom:0.35rem;'>Fresh View</div>
                    <div style='color:var(--text-secondary);font-size:0.92rem;line-height:1.45;'>
                        This page starts clean for a neater workflow. Run a new scan to populate current results, or load historical results for analytics/reporting.
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.stop()
    
        # Filters and Export
        col_filter, col_export = st.columns([4, 1])

        if "scan_market_focus" not in st.session_state:
            st.session_state["scan_market_focus"] = "Africa First"
        if st.session_state.get("scan_market_focus") not in MARKET_FOCUS_OPTIONS:
            st.session_state["scan_market_focus"] = "Africa First"
        scan_market_focus = st.session_state["scan_market_focus"]
    
        with col_filter:
            st.subheader("Filters")
    
        with col_export:
            # CSV Export button
            all_tenders_for_export = get_tenders({"market_focus": scan_market_focus})
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

        focus1, focus2, focus3 = st.columns(3)
        with focus1:
            if st.button(
                "Kenya Search",
                key="scan_focus_kenya_button",
                width="stretch",
                type="primary" if scan_market_focus == "Kenya First" else "secondary",
            ):
                st.session_state["scan_market_focus"] = "Kenya First"
                st.rerun()
        with focus2:
            if st.button(
                "Africa Search",
                key="scan_focus_africa_button",
                width="stretch",
                type="primary" if scan_market_focus == "Africa First" else "secondary",
            ):
                st.session_state["scan_market_focus"] = "Africa First"
                st.rerun()
        with focus3:
            if st.button(
                "Global Search",
                key="scan_focus_global_button",
                width="stretch",
                type="primary" if scan_market_focus == "Global Reach" else "secondary",
            ):
                st.session_state["scan_market_focus"] = "Global Reach"
                st.rerun()

        qp_search = _qp_value("search", "")
        if st.session_state.get("scan_search") is None:
            st.session_state["scan_search"] = qp_search

        sort_options = ["score", "date", "deadline"]
        qp_sort = _qp_value("sort", "score")
        if qp_sort not in sort_options:
            qp_sort = "score"
        if st.session_state.get("scan_sort_by") not in sort_options:
            st.session_state["scan_sort_by"] = qp_sort

        active_discovery_mode = st.session_state.get("last_scan_info", {}).get("discovery_mode", "f2_ranked")
        manual_like_view = active_discovery_mode == "manual_like"

        # Simple controls only.
        qc1, qc2 = st.columns([2.2, 1.0])
        with qc1:
            search = st.text_input(
                "Search",
                placeholder="Search titles or descriptions...",
                key="scan_search",
            )
        with qc2:
            sort_by = st.selectbox("Sort By", sort_options, key="scan_sort_by")

        # Simple query: search + sort only.
        filters = {
            'market_focus': scan_market_focus,
            'sort_by': sort_by,
            'search': search,
            'created_after': st.session_state.get("scan_anchor_utc") if results_mode == "session_scan" else None,
        }
    
        fallback_notice = ""
        applied_focus = scan_market_focus
        tenders = get_tenders(filters)
        tenders, removed_no_keyword_signal, removed_generic_targets = _apply_result_visibility_filters(tenders)

        if not tenders and (search or scan_market_focus != "Global Reach"):
            # Fallback 1: clear search but keep focus.
            if search:
                relaxed_filters = dict(filters)
                relaxed_filters["search"] = ""
                relaxed = get_tenders(relaxed_filters)
                relaxed, _, _ = _apply_result_visibility_filters(relaxed)
                if relaxed:
                    tenders = relaxed
                    fallback_notice = "No matches for current search. Showing results with search cleared."

            # Fallback 2: broaden focus to global if still empty.
            if not tenders and scan_market_focus != "Global Reach":
                broad_filters = dict(filters)
                broad_filters["market_focus"] = "Global Reach"
                broad = get_tenders(broad_filters)
                broad, _, _ = _apply_result_visibility_filters(broad)
                if broad:
                    tenders = broad
                    fallback_notice = f"No matches in `{scan_market_focus}`. Showing global results."
                    applied_focus = "Global Reach (fallback)"

        if sort_by == "deadline":
            tenders = sorted(
                tenders,
                key=lambda t: (_parse_deadline_value(getattr(t, "deadline", "")) is None, _parse_deadline_value(getattr(t, "deadline", "")) or datetime.max.date())
            )

        if manual_like_view:
            st.caption("Manual-like mode active: broader discovery results are shown.")
        if fallback_notice:
            st.warning(fallback_notice)
        if removed_no_keyword_signal > 0:
            st.caption(f"Hidden {removed_no_keyword_signal} results with no keyword signal.")
        if removed_generic_targets > 0:
            st.caption(f"Hidden {removed_generic_targets} generic/non-opportunity links.")
        st.markdown(f"**{len(tenders)} tenders found** | Focus: `{applied_focus}`")
        st.markdown("---")

        if tenders:
            high_fit_count = sum(1 for t in tenders if float(getattr(t, "score", 0) or 0) >= 70)
            urgent_deadline_count = 0
            for t in tenders:
                dl = _deadline_meta(getattr(t, "deadline", "")).get("days_left")
                if dl is not None and 0 <= int(dl) <= 7:
                    urgent_deadline_count += 1
            open_count = sum(
                1
                for t in tenders
                if (getattr(t, "procurement_status", "") or "").strip().lower() not in {"locked", "conditional_nogo"}
            )
            k1, k2, k3 = st.columns(3)
            with k1:
                st.metric("High Fit (70+)", high_fit_count)
            with k2:
                st.metric("Urgent Deadlines (7d)", urgent_deadline_count)
            with k3:
                st.metric("Open Opportunities", open_count)
            st.markdown("---")
    
        # Display tenders (card-only)
        if tenders:
            for tender in tenders:
                # Determine score styling
                if tender.score >= 70:
                    score_level = "high"
                    score_label = "High"
                elif tender.score >= 40:
                    score_level = "med"
                    score_label = "Medium"
                else:
                    score_level = "low"
                    score_label = "Low"

                with st.container():
                    display_title = tender.title_translated if tender.title_translated and tender.title_translated != tender.title else tender.title
                    is_translated = tender.title_translated and tender.title_translated != tender.title
                    deadline_meta = _deadline_meta(tender.deadline)
                    lifecycle = _lifecycle_label(tender.timing_status)
                    deadline_class = deadline_meta["style"] if deadline_meta["style"] in {"urgent", "upcoming", "overdue"} else ""
                    title_suffix = " [Translated]" if is_translated else ""
                    created_label = tender.created_at.strftime("%Y-%m-%d") if tender.created_at else "Unknown date"

                    chips = []
                    if tender.category and tender.category != "Unclassified":
                        chips.append(f"<span class='meta-chip'>Category: {tender.category}</span>")
                    if tender.country and tender.country != "Unknown":
                        chips.append(f"<span class='meta-chip'>Country: {tender.country}</span>")
                    chips.append(f"<span class='meta-chip'>Lifecycle: {lifecycle}</span>")
                    if tender.priority_level:
                        chips.append(f"<span class='meta-chip'>Priority: {tender.priority_level}</span>")
                    if tender.likely_fit_for_f2:
                        chips.append(f"<span class='meta-chip'>F2 Fit: {tender.likely_fit_for_f2}</span>")
                    ml_score = getattr(tender, "_ml_score", None)
                    if ml_score is not None:
                        chips.append(f"<span class='meta-chip'>ML: {ml_score * 100:.0f}%</span>")
                    description_line = (tender.description_translated or tender.description or "").replace("\n", " ").strip()
                    if len(description_line) > 220:
                        description_line = f"{description_line[:220].rstrip()}..."
                    keywords = _keyword_list(
                        getattr(tender, "keywords_matched", ""),
                        fallback_text=_tender_fallback_text(tender),
                        limit=4,
                    )
                    for kw in keywords:
                        chips.append(f"<span class='meta-chip'>Keyword: {kw}</span>")
                    direct_hits = _direct_match_keywords(tender, limit=2)
                    for kw in direct_hits:
                        chips.append(f"<span class='meta-chip direct'>Direct match: {kw}</span>")
                    chips.append(f"<span class='meta-chip deadline {deadline_class}'>Deadline: {deadline_meta['label']}</span>")
                    chips_html = "".join(chips)

                    deadline_status = deadline_meta["style"].upper() if deadline_meta["style"] != "none" else "NO DEADLINE"

                    st.markdown(
                        f"""
                        <div class="result-card {score_level}">
                            <div class="result-header">
                                <h3 class="result-title">{display_title}{title_suffix}</h3>
                                <div class="result-badges">
                                    <span class="badge-score {score_level}">{score_label} {tender.score:.0f}%</span>
                                    <span class="deadline-pill {deadline_class}">{deadline_status}</span>
                                </div>
                            </div>
                            <div class="meta-chips">{chips_html}</div>
                            <div class="result-muted">Captured: {created_label}</div>
                            <div class="result-summary">{description_line or 'No description available.'}</div>
                            <div class="result-actions"></div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

                    why = _why_matched_summary(tender)
                    with st.expander("Why this matched", expanded=False):
                        st.markdown(
                            f"Priority: `{why['priority'] or 'N/A'}` | "
                            f"F2 fit: `{why['fit'] or 'N/A'}` | "
                            f"Keywords found: `{why['keywords_found']}`"
                        )
                        if direct_hits:
                            st.markdown("Direct phrase matches:")
                            for kw in direct_hits:
                                st.markdown(f"- `{kw}`")
                        if why["matched_phrases"]:
                            st.markdown("Scoring phrases:")
                            for kw in why["matched_phrases"][:4]:
                                st.markdown(f"- `{kw}`")
                        if why["domains"]:
                            st.markdown("Domains:")
                            st.markdown(", ".join([f"`{d}`" for d in why["domains"]]))

                    col1, col2, col3, col4 = st.columns(4)

                    with col1:
                        fav_label = "Favorited" if tender.favorite else "Favorite"
                        if st.button(fav_label, key=f"fav_{tender.id}", width="stretch"):
                            toggle_favorite(tender.id)
                            st.rerun()

                    with col2:
                        save_label = "Saved" if tender.saved else "Save"
                        if st.button(save_label, key=f"save_{tender.id}", width="stretch"):
                            toggle_saved(tender.id)
                            st.rerun()

                    with col3:
                        st.link_button("View Source", tender.link, width="stretch")

                    with col4:
                        if st.button("Details", key=f"detail_{tender.id}", width="stretch"):
                            record_feedback(tender.id, "view", 0.25, flask_app=app)
                            st.session_state['selected_tender'] = tender.id
                            st.rerun()
        else:
            st.info("No results match the selected filters.")

elif page == "Sources":
    st.title("Tender Sources")
    
    # Initialize session state for checkboxes
    if 'selected_sources' not in st.session_state:
        st.session_state.selected_sources = []
    
    tab1, tab2 = st.tabs(["Manage Sources", "Add New Source"])
    
    with tab1:
        sources = get_sources()
        
        if sources:
            # Bulk action buttons
            col_bulk1, col_bulk2, col_bulk3 = st.columns([2, 1, 1])
            with col_bulk2:
                if st.button("Delete Selected", key="delete_selected_btn", use_container_width=True):
                    if st.session_state.selected_sources:
                        if st.session_state.get('confirm_delete_selected'):
                            if delete_multiple_sources(st.session_state.selected_sources):
                                st.success(f"Deleted {len(st.session_state.selected_sources)} source(s)")
                                st.session_state.selected_sources = []
                                st.session_state.confirm_delete_selected = False
                                time.sleep(1)
                                st.rerun()
                        else:
                            st.session_state.confirm_delete_selected = True
                            st.warning(f"Click again to confirm deletion of {len(st.session_state.selected_sources)} source(s)")
                    else:
                        st.warning("Please select sources to delete")
            
            with col_bulk3:
                if st.button("Delete All", key="delete_all_btn", use_container_width=True):
                    if st.session_state.get('confirm_delete_all'):
                        if st.session_state.get('confirm_delete_all_final'):
                            if delete_all_sources():
                                st.success(f"Deleted all {len(sources)} source(s)")
                                st.session_state.selected_sources = []
                                st.session_state.confirm_delete_all = False
                                st.session_state.confirm_delete_all_final = False
                                time.sleep(1)
                                st.rerun()
                        else:
                            st.session_state.confirm_delete_all_final = True
                            st.error("⚠️ FINAL WARNING: Click again to permanently delete ALL sources")
                    else:
                        st.session_state.confirm_delete_all = True
                        st.warning(f"Click again to confirm deletion of all {len(sources)} source(s)")
            
            st.markdown("---")
            
            # Display sources with checkboxes
            for source in sources:
                with st.container():
                    col_check, col_info, col_toggle, col_visit, col_del = st.columns([0.5, 3, 1, 1, 1])
                    
                    with col_check:
                        is_selected = st.checkbox(
                            "Select",
                            value=source.id in st.session_state.selected_sources,
                            key=f"select_{source.id}",
                            label_visibility="collapsed"
                        )
                        if is_selected and source.id not in st.session_state.selected_sources:
                            st.session_state.selected_sources.append(source.id)
                        elif not is_selected and source.id in st.session_state.selected_sources:
                            st.session_state.selected_sources.remove(source.id)
                    
                    with col_info:
                        status = "🟢 Active" if source.active else "⚫ Inactive"
                        fav = "⭐ Favorite" if source.favorite else ""
                        st.markdown(f"**{source.name}** {status} {fav}")
                        st.caption(source.url)
                    
                    with col_toggle:
                        toggle_label = "Disable" if source.active else "Enable"
                        if st.button(toggle_label, key=f"toggle_{source.id}", use_container_width=True):
                            toggle_source(source.id)
                            st.success(f"Source {'disabled' if source.active else 'enabled'}!")
                            st.rerun()
                    
                    with col_visit:
                        st.link_button("Visit", source.url, use_container_width=True)
                    
                    with col_del:
                        if st.button("Delete", key=f"del_{source.id}", use_container_width=True):
                            if delete_source(source.id):
                                st.success("Source deleted.")
                                if source.id in st.session_state.selected_sources:
                                    st.session_state.selected_sources.remove(source.id)
                                time.sleep(0.5)
                                st.rerun()
                    
                    st.markdown("---")
                    
            # Show selected count
            if st.session_state.selected_sources:
                st.info(f"✓ {len(st.session_state.selected_sources)} source(s) selected")
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

        st.subheader("Web-Wide Discovery (SerpAPI)")
        st.caption("Enable API-based global web discovery and merge discovered opportunities into scan results.")

        auto_discovery_enabled = st.checkbox(
            "Enable Web Discovery",
            value=settings.auto_discovery_enabled if settings and hasattr(settings, "auto_discovery_enabled") else False,
            help="When enabled, scans will also discover tenders from search APIs (not only your configured source list).",
        )

        st.markdown("**SerpAPI (recommended for global coverage)**")
        has_db_serp_key = bool(settings and getattr(settings, "bing_api_key", ""))
        has_secret_serp_key = bool(os.getenv("SERPAPI_API_KEY", "").strip())
        if has_db_serp_key and has_secret_serp_key:
            st.caption("SerpAPI key is saved in DB and available via secrets/env.")
        elif has_db_serp_key:
            st.caption("SerpAPI key is currently saved in DB.")
        elif has_secret_serp_key:
            st.caption("SerpAPI key is loaded from Streamlit secrets/env.")
        serpapi_key_input = st.text_input(
            "SerpAPI Key",
            value="",
            type="password",
            placeholder="Paste SerpAPI key to set/update",
            help="Leave blank to keep current saved key.",
        )

        existing_queries_raw = settings.discovery_queries if settings and hasattr(settings, "discovery_queries") and settings.discovery_queries else ""
        discovery_queries_default = ""
        if existing_queries_raw:
            try:
                parsed_q = json.loads(existing_queries_raw)
                if isinstance(parsed_q, list):
                    discovery_queries_default = "\n".join([str(q) for q in parsed_q if str(q).strip()])
                else:
                    discovery_queries_default = str(existing_queries_raw)
            except Exception:
                discovery_queries_default = str(existing_queries_raw)

        discovery_queries_text = st.text_area(
            "Discovery Queries (one per line)",
            value=discovery_queries_default,
            height=120,
            help="Leave empty to use default discovery queries.",
        )

        results_per_query = st.slider(
            "Results per query",
            min_value=3,
            max_value=30,
            value=int(settings.results_per_query) if settings and hasattr(settings, "results_per_query") and settings.results_per_query else 10,
            help="Number of search results to request per query.",
        )

        if st.button("Save Discovery Settings", key="save_discovery_settings_button", width="stretch"):
            discovery_queries_list = [q.strip() for q in (discovery_queries_text or "").splitlines() if q.strip()]
            discovery_queries_json = json.dumps(discovery_queries_list) if discovery_queries_list else ""
            if settings:
                settings.auto_discovery_enabled = auto_discovery_enabled
                if serpapi_key_input:
                    settings.bing_api_key = serpapi_key_input.strip()
                settings.discovery_queries = discovery_queries_json
                settings.results_per_query = int(results_per_query)
                db.session.commit()
            else:
                settings = AppSettings(
                    auto_discovery_enabled=auto_discovery_enabled,
                    bing_api_key=serpapi_key_input.strip() if serpapi_key_input else "",
                    discovery_queries=discovery_queries_json,
                    results_per_query=int(results_per_query),
                )
                db.session.add(settings)
                db.session.commit()
            st.success("Discovery settings saved.")
            st.rerun()
        st.markdown("---")

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

        st.subheader("ML Relevance Model")
        ml_status = model_status()
        fb_stats = feedback_counts(days=180)
        ml_col1, ml_col2, ml_col3, ml_col4 = st.columns(4)
        with ml_col1:
            st.metric("Feedback Events", fb_stats.get("total", 0))
        with ml_col2:
            st.metric("Positive", fb_stats.get("positive", 0))
        with ml_col3:
            st.metric("Negative", fb_stats.get("negative", 0))
        with ml_col4:
            st.metric("Model", "Ready" if ml_status.get("available") else "Not trained")

        if ml_status.get("available"):
            st.caption(
                f"Trained: {ml_status.get('trained_at', 'N/A')} | "
                f"Samples: {ml_status.get('samples', 0)} "
                f"(+{ml_status.get('positives', 0)} / -{ml_status.get('negatives', 0)})"
            )
        else:
            st.caption("Model is not trained yet. Keep using Save/Favorite/Details to build feedback signals.")

        if st.button("Train/Re-train Relevance Model", key="train_ml_model_btn"):
            result = train_relevance_model(min_samples=40)
            if result.trained:
                st.success(
                    f"{result.message} "
                    f"Samples={result.samples}, Pos={result.positives}, Neg={result.negatives}"
                )
            else:
                st.warning(
                    f"{result.message} "
                    f"Current samples={result.samples}, Pos={result.positives}, Neg={result.negatives}"
                )
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
                    style='background: #0284c7; 
                           color: white; 
                           border: none; 
                           padding: 12px 32px; 
                           border-radius: 8px; 
                           font-size: 1rem; 
                           font-weight: 600; 
                           cursor: pointer;
                           box-shadow: 0 4px 12px rgba(2, 132, 199, 0.38);'>
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
        
        st.markdown("---")
        
        # Save button
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            if st.button("Save Settings", key="save_settings_button", type="primary", width="stretch"):
                discovery_queries_list = [q.strip() for q in (discovery_queries_text or "").splitlines() if q.strip()]
                discovery_queries_json = json.dumps(discovery_queries_list) if discovery_queries_list else ""

                if settings:
                    settings.auto_discovery_enabled = auto_discovery_enabled
                    if serpapi_key_input:
                        settings.bing_api_key = serpapi_key_input.strip()
                    if google_api_key_input:
                        settings.google_api_key = google_api_key_input.strip()
                    settings.google_cx = (google_cx_input or "").strip()
                    settings.discovery_queries = discovery_queries_json
                    settings.results_per_query = int(results_per_query)

                    settings.notifications_enabled = notification_enabled
                    settings.min_score_to_notify = float(min_score)
                    # Email notifications removed from Streamlit app settings.
                    settings.notify_email = False
                    settings.email_recipients = ""
                    settings.smtp_username = ""
                    settings.smtp_password = ""
                    db.session.commit()
                    st.success("Settings saved.")
                else:
                    new_settings = AppSettings(
                        auto_discovery_enabled=auto_discovery_enabled,
                        bing_api_key=serpapi_key_input.strip() if serpapi_key_input else "",
                        google_api_key=google_api_key_input.strip() if google_api_key_input else "",
                        google_cx=(google_cx_input or "").strip(),
                        discovery_queries=discovery_queries_json,
                        results_per_query=int(results_per_query),
                        notifications_enabled=notification_enabled,
                        min_score_to_notify=float(min_score),
                        notify_email=False
                    )
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

