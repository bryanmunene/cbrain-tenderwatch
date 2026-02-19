"""app.deadlines

Deadline extraction + timing utilities.

This module intentionally stays lightweight (regex-based, no heavy date parser) because it's
called frequently during scans.

Key improvements vs the previous version:
- Much broader date-format coverage (ISO, DMY/MDY numeric, month names, ordinal suffixes)
- Prefers dates appearing near deadline/closing keywords
- Picks the *earliest future* date when multiple dates exist (helps avoid grabbing publication dates)
- Configurable minimum-days-to-deadline via env var MIN_DAYS_TO_DEADLINE
"""

from __future__ import annotations

import os
import re
from datetime import date, datetime, timedelta, timezone
from typing import Iterable, List, Optional, Tuple

# -----------------------------------------------------------------------------
# Config
# -----------------------------------------------------------------------------

# Default timing constraint used by is_deadline_valid().
# Can be overridden in production without code changes.
MIN_DAYS_TO_DEADLINE = int(os.getenv("MIN_DAYS_TO_DEADLINE", "7"))

# Guardrails for sanity (avoid parsing nonsense years)
MIN_YEAR = 2000
MAX_YEAR = 2100


# -----------------------------------------------------------------------------
# Month names (English + a few common FR/ES/PT variants)
# -----------------------------------------------------------------------------

MONTHS = {
    # English
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
    # French (common)
    "janvier": 1,
    "fevrier": 2,
    "février": 2,
    "mars": 3,
    "avril": 4,
    "mai": 5,
    "juin": 6,
    "juillet": 7,
    "aout": 8,
    "août": 8,
    "septembre": 9,
    "octobre": 10,
    "novembre": 11,
    "decembre": 12,
    "décembre": 12,
    # Spanish (common)
    "enero": 1,
    "febrero": 2,
    "marzo": 3,
    "abril": 4,
    "mayo": 5,
    "junio": 6,
    "julio": 7,
    "agosto": 8,
    "septiembre": 9,
    "setiembre": 9,
    "octubre": 10,
    "noviembre": 11,
    "diciembre": 12,
    # Portuguese (common)
    "janeiro": 1,
    "fevereiro": 2,
    "marco": 3,
    "março": 3,
    "abril": 4,
    "maio": 5,
    "junho": 6,
    "julho": 7,
    "agosto": 8,
    "setembro": 9,
    "outubro": 10,
    "novembro": 11,
    "dezembro": 12,
}


# -----------------------------------------------------------------------------
# Regexes (precompiled for speed)
# -----------------------------------------------------------------------------

# Preferred contexts (we look for dates near these)
_CTX_RE = re.compile(
    r"\b(?:deadline|closing\s*date|closing\s*time|closing|close\s*on|closing\s*on|due\s*date|submission\s*deadline|bid\s*submission)\b",
    flags=re.IGNORECASE,
)

# ISO: 2026-02-15 or 2026/02/15
_ISO_RE = re.compile(r"\b(20\d{2})[\-/\.](\d{1,2})[\-/\.](\d{1,2})\b")

# DMY numeric: 15/02/2026, 15-2-26, 15.02.2026
_DMY_NUM_RE = re.compile(
    r"\b(\d{1,2})(?:st|nd|rd|th)?[\-/\.]\s*(\d{1,2})[\-/\.]\s*(\d{2,4})\b",
    flags=re.IGNORECASE,
)

# DMY month name: 15 Feb 2026, 15 February, 2026
_DMY_MON_RE = re.compile(
    r"\b(\d{1,2})(?:st|nd|rd|th)?\s*[\-/\.]?\s*([a-zA-Z\u00C0-\u017F]{3,15})\s*[\-/\.,]?\s*(\d{2,4})\b",
    flags=re.IGNORECASE,
)

# MDY month name: Feb 15 2026, February 15, 2026
_MDY_MON_RE = re.compile(
    r"\b([a-zA-Z\u00C0-\u017F]{3,15})\s*(\d{1,2})(?:st|nd|rd|th)?\s*[\-/\.,]?\s*(\d{2,4})\b",
    flags=re.IGNORECASE,
)


def _utcnow() -> datetime:
    """Keep naive UTC for compatibility with existing DB datetime usage."""

    return datetime.now(timezone.utc).replace(tzinfo=None)


def _coerce_year(y: int) -> int:
    # Handle 2-digit years in a pragmatic way.
    if y < 100:
        y = 2000 + y
    return y


def _month_from_token(tok: str) -> Optional[int]:
    tok = (tok or "").strip().lower()
    if not tok:
        return None
    if tok.isdigit():
        try:
            m = int(tok)
            return m if 1 <= m <= 12 else None
        except Exception:
            return None
    # Normalize accents minimally by lookup on full token or first 3 letters.
    if tok in MONTHS:
        return MONTHS[tok]
    k3 = tok[:3]
    return MONTHS.get(k3)


def _safe_date(y: int, m: int, d: int) -> Optional[date]:
    y = _coerce_year(y)
    if y < MIN_YEAR or y > MAX_YEAR:
        return None
    try:
        return date(y, m, d)
    except Exception:
        return None


def _extract_dates(text: str) -> List[date]:
    """Extract *all* plausible dates from text."""

    out: List[date] = []

    # ISO first (least ambiguous)
    for y, m, d in _ISO_RE.findall(text):
        dt = _safe_date(int(y), int(m), int(d))
        if dt:
            out.append(dt)

    # DMY numeric
    for d, m, y in _DMY_NUM_RE.findall(text):
        di = int(d)
        mi = int(m)
        yi = int(y)
        # If month looks invalid but day could be month (US format), swap.
        if mi > 12 and di <= 12:
            di, mi = mi, di
        dt = _safe_date(yi, mi, di)
        if dt:
            out.append(dt)

    # DMY month name
    for d, mon, y in _DMY_MON_RE.findall(text):
        mi = _month_from_token(mon)
        if not mi:
            continue
        dt = _safe_date(int(y), mi, int(d))
        if dt:
            out.append(dt)

    # MDY month name
    for mon, d, y in _MDY_MON_RE.findall(text):
        mi = _month_from_token(mon)
        if not mi:
            continue
        dt = _safe_date(int(y), mi, int(d))
        if dt:
            out.append(dt)

    # De-dupe while keeping order
    seen = set()
    uniq: List[date] = []
    for dt in out:
        if dt not in seen:
            seen.add(dt)
            uniq.append(dt)
    return uniq


def parse_deadline(text: str) -> Optional[str]:
    """Extract a best-effort deadline date from text.

    Returns:
        ISO date string (YYYY-MM-DD) or None.
    """

    if not text:
        return None

    t = (text or "").strip().lower()
    if not t:
        return None

    # 1) Prefer date near explicit deadline/closing keywords
    for m in _CTX_RE.finditer(t):
        window = t[m.end() : m.end() + 140]
        cands = _extract_dates(window)
        if cands:
            # Pick the earliest future date in the window, else earliest.
            today = _utcnow().date()
            future = [d for d in cands if d >= today]
            chosen = min(future) if future else min(cands)
            return chosen.isoformat()

    # 2) Fallback: pick earliest future date in the whole text (helps avoid publication dates)
    cands = _extract_dates(t)
    if not cands:
        return None

    today = _utcnow().date()
    future = [d for d in cands if d >= today]
    chosen = min(future) if future else max(cands)
    return chosen.isoformat()


def extract_dates(text: str) -> List[date]:
    """Public helper: return all plausible dates found in text.

    Useful for stale-notice filtering when no explicit deadline is extracted.
    """
    if not text:
        return []
    t = (text or "").strip().lower()
    if not t:
        return []
    return _extract_dates(t)


def check_timing_constraints(deadline_str: str, publication_date: datetime = None):
    """F2-Aligned Timing Constraints (HARD FILTERS).

    - Submission deadline >= MIN_DAYS_TO_DEADLINE days from scan date
    - Publication/float date <= 3 months from scan date

    If dates are missing, do NOT auto-exclude - downgrade confidence instead.

    Returns:
        tuple: (is_valid, confidence_modifier, reason)
        - is_valid: True if passes timing constraints OR dates missing
        - confidence_modifier: 0 (pass), -0.1 to -0.3 (warning), or -0.5 (fail but include)
        - reason: Human-readable explanation
    """

    now = _utcnow()
    min_deadline = now + timedelta(days=MIN_DAYS_TO_DEADLINE)
    max_publication_age = now - timedelta(days=90)  # 3 months ago

    # Case 1: Both dates missing - include with slight confidence penalty
    if not deadline_str and not publication_date:
        return (True, -0.1, "No dates available - included with lower confidence")

    # Case 2: Parse deadline if provided
    if deadline_str:
        try:
            deadline = datetime.strptime(deadline_str, "%Y-%m-%d")
            if deadline < min_deadline:
                days_until = (deadline - now).days
                if days_until < 0:
                    return (False, -0.5, f"Deadline passed ({deadline_str})")
                return (False, -0.3, f"Deadline too soon ({days_until} days)")
        except ValueError:
            # Invalid date format - include with warning
            pass

    # Case 3: Check publication date if provided
    if publication_date:
        if publication_date < max_publication_age:
            days_old = (now - publication_date).days
            return (True, -0.2, f"Publication is {days_old} days old - may be stale")

    return (True, 0, "Timing OK")


def is_deadline_valid(deadline_str: str, min_days: Optional[int] = None) -> bool:
    """Simple check: is deadline >= min_days from now?

    Returns True if valid OR if deadline is missing (don't exclude).
    """

    if not deadline_str:
        return True

    if min_days is None:
        min_days = MIN_DAYS_TO_DEADLINE

    try:
        deadline = datetime.strptime(deadline_str, "%Y-%m-%d")
        min_deadline = _utcnow() + timedelta(days=int(min_days))
        return deadline >= min_deadline
    except Exception:
        return True
