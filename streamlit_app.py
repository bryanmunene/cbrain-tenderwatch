"""Root Streamlit entrypoint for Community Cloud.

Streamlit Cloud defaults to ``streamlit_app.py`` at the repository root. This
wrapper runs the real TenderWatch app from ``tenderwatch_app/streamlit_app.py``.
"""

from __future__ import annotations

import sys
from pathlib import Path


APP_DIR = Path(__file__).resolve().parent / "tenderwatch_app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

import streamlit_app as _tenderwatch_streamlit_app  # noqa: F401,E402
