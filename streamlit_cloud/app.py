"""Streamlit Community Cloud entrypoint for TenderWatch.

This wrapper keeps the cloud dependency file small while running the real app
from ``tenderwatch_app/streamlit_app.py``.
"""

from __future__ import annotations

import sys
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1] / "tenderwatch_app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

import streamlit_app  # noqa: F401,E402
