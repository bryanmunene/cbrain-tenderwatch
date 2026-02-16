"""app.categorizer

Lightweight categorization based on keyword domains.

This file is called often during scans, so we:
- precompute sorted keyword lists once at import time
- normalize both text and keywords similarly to app.keywords to improve recall
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

import re
import app.keywords as kw


KEYWORD_DOMAINS = getattr(kw, "KEYWORD_DOMAINS", {})

_normalize_text = getattr(kw, "_normalize", None)
_normalize_phrase = getattr(kw, "_normalize_phrase", None)


@dataclass(frozen=True)
class _KW:
    norm: str
    orig: str
    word_count: int


def _norm_phrase(s: str) -> str:
    s = (s or "").strip()
    if not s:
        return ""
    if callable(_normalize_phrase):
        try:
            return _normalize_phrase(s)
        except Exception:
            return s.lower()
    # Fallback: collapse separators and whitespace
    s = s.lower()
    s = re.sub(r"[-/\\_|]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _norm_text(s: str) -> str:
    s = (s or "").strip()
    if not s:
        return ""
    if callable(_normalize_text):
        try:
            return _normalize_text(s)
        except Exception:
            pass
    s = s.lower()
    s = re.sub(r"\s+", " ", s)
    return s


# Precompute per-category keyword lists (normalized, longest first).
_DOMAIN_KWS: dict[str, list[_KW]] = {}
for category, keywords in (KEYWORD_DOMAINS or {}).items():
    kws: list[_KW] = []
    for k in keywords or []:
        k = (k or "").strip()
        if not k:
            continue
        norm = _norm_phrase(k)
        if not norm:
            continue
        wc = len(norm.split())
        kws.append(_KW(norm=norm, orig=k, word_count=wc))
    # Longest/multi-word first helps avoid generic matches dominating
    kws.sort(key=lambda x: (x.word_count, len(x.norm)), reverse=True)
    _DOMAIN_KWS[category] = kws


def categorize(title: str, text: str = "", source_name: str | None = None):
    """Categorize tenders based on keyword hits.

    Returns:
        (best_category, matched_keywords_str, confidence_float)
    """

    combined = _norm_text(f"{title} {text}")
    if not combined:
        return "Unclassified", "", 0.0

    scores = defaultdict(float)
    matched_keywords = defaultdict(set)

    for category, kws in _DOMAIN_KWS.items():
        for k in kws:
            if k.norm and k.norm in combined:
                # Weight multi-word keywords higher
                score_value = max(1, k.word_count) * 2
                scores[category] += score_value
                matched_keywords[category].add(k.orig)

    if not scores:
        return "Unclassified", "", 0.0

    # Pick best category; tie-breaker: more multi-word matches
    def _tie_key(cat: str):
        multi = sum(1 for kw_ in matched_keywords[cat] if len(str(kw_).split()) > 1)
        return (scores[cat], multi)

    best_category = max(scores, key=_tie_key)

    total = sum(scores.values())
    confidence = float(scores[best_category] / total) if total else 0.0
    keywords_used = ", ".join(sorted(matched_keywords[best_category]))

    return best_category, keywords_used, round(confidence, 3)
