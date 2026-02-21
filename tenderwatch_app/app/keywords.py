from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from typing import Any, Dict, List, Optional, Tuple


@dataclass(frozen=True)
class ScanProfile:
    name: str
    max_days_since_publication: int
    min_days_to_deadline: int


GLOBAL_PROFILE = ScanProfile("GLOBAL", max_days_since_publication=120, min_days_to_deadline=0)
AFRICA_STRICT_PROFILE = ScanProfile("AFRICA_STRICT", max_days_since_publication=45, min_days_to_deadline=0)


NORMALIZATION: Dict[str, Any] = {
    "lowercase": True,
    "collapse_whitespace": True,
    "max_text_chars": 300_000,
}

_PATTERN_CACHE: Dict[str, re.Pattern] = {}


def _normalize(text: str) -> str:
    if not text:
        return ""
    t = text[: NORMALIZATION["max_text_chars"]]
    if NORMALIZATION["lowercase"]:
        t = t.lower()
    t = re.sub(r"[-/\\_|]+", " ", t)
    t = re.sub(r"[\"'`]+", " ", t)
    t = re.sub(r"[\(\)\[\]\{\},:;]+", " ", t)
    if NORMALIZATION["collapse_whitespace"]:
        t = re.sub(r"\s+", " ", t).strip()
    return t


def _normalize_phrase(phrase: str) -> str:
    p = (phrase or "").strip().lower()
    p = re.sub(r"[-/\\_|]+", " ", p)
    p = re.sub(r"\s+", " ", p).strip()
    return p


def _compile_phrase(phrase: str) -> re.Pattern:
    p = _normalize_phrase(phrase)
    if not p:
        return re.compile(r"(?!x)x")
    escaped = re.escape(p).replace(r"\ ", r"\s+")
    return re.compile(rf"(?<!\w){escaped}(?!\w)", flags=re.UNICODE)


def _phrase_hit(text: str, phrase: str) -> bool:
    key = _normalize_phrase(phrase)
    if not key:
        return False
    pat = _PATTERN_CACHE.get(key)
    if pat is None:
        pat = _compile_phrase(key)
        _PATTERN_CACHE[key] = pat
    return pat.search(text) is not None


def _collect_hits(text: str, phrases: List[str], max_hits: Optional[int] = None) -> List[str]:
    hits: List[str] = []
    for phrase in phrases:
        p = _normalize_phrase(phrase)
        if p and _phrase_hit(text, p):
            hits.append(p)
            if max_hits is not None and len(hits) >= max_hits:
                break

    seen = set()
    out: List[str] = []
    for h in hits:
        if h not in seen:
            seen.add(h)
            out.append(h)
    return out


# Simple and broad F2-oriented keyword map.
KEYWORD_DOMAINS: Dict[str, List[str]] = {
    "EDMS": [
        "document management",
        "document management system",
        "records management",
        "records management system",
        "electronic records",
        "file registry",
        "archive management",
        "edms",
        "edrms",
    ],
    "Workflow": [
        "workflow",
        "workflow automation",
        "workflow management",
        "business process management",
        "process automation",
        "approval workflow",
        "bpm",
    ],
    "Case": [
        "case management",
        "case tracking",
        "complaint management",
        "grievance management",
        "service request management",
        "ticket management",
    ],
    "Gov": [
        "digital",
        "digital transformation",
        "digitalization",
        "digitalisation",
        "digitization",
        "digitisation",
        "digital system",
        "digital systems",
        "ict",
        "ict system",
        "ict systems",
        "information system",
        "information systems",
        "digital government",
        "e government",
        "e governance",
        "citizen portal",
        "public service platform",
        "government information system",
    ],
    "Records": [
        "records digitization",
        "records digitisation",
        "records archive",
        "records repository",
    ],
    "ECM": [
        "enterprise content management",
        "content management platform",
        "ecm",
    ],
    "Forms": [
        "forms automation",
        "electronic forms",
        "online forms",
    ],
    "ServiceDelivery": [
        "service delivery platform",
        "citizen services platform",
        "one stop portal",
    ],
    "Pipeline": [
        # F2-specific procurement intent phrases only.
        # Avoid broad standalone tender terms (rfp/rfq/rfi/eoi) that create noisy matches.
        "document management rfp",
        "records management rfp",
        "workflow automation rfp",
        "case management rfp",
        "enterprise content management rfp",
        "document management rfq",
        "records management rfq",
        "workflow automation rfq",
        "case management rfq",
        "document management system tender",
        "records management system tender",
        "workflow management tender",
        "case management system tender",
        "digital transformation platform tender",
        "citizen services platform tender",
    ],
}


ALL_KEYWORDS: List[str] = sorted({kw for kws in KEYWORD_DOMAINS.values() for kw in kws})

KEYWORD_TO_DOMAIN: Dict[str, List[str]] = {}
for domain, keywords in KEYWORD_DOMAINS.items():
    for kw in keywords:
        KEYWORD_TO_DOMAIN.setdefault(_normalize_phrase(kw), []).append(domain)


MICROSOFT_HARD_LOCK_SIGNALS: List[str] = [
    "must use sharepoint",
    "must use microsoft 365",
    "must use power platform",
    "built on sharepoint",
]
MICROSOFT_SOFT_LOCK_SIGNALS: List[str] = [
    "sharepoint environment",
    "microsoft 365",
    "office 365",
    "power platform",
]
MICROSOFT_COMMITMENT_SIGNALS: List[str] = sorted(
    set(MICROSOFT_HARD_LOCK_SIGNALS + MICROSOFT_SOFT_LOCK_SIGNALS)
)
PLATFORM_LOCKIN_SIGNALS: List[str] = MICROSOFT_COMMITMENT_SIGNALS.copy()

OPENNESS_SIGNALS: List[str] = [
    "or equivalent",
    "vendor neutral",
    "technology neutral",
    "platform agnostic",
]
PLATFORM_OPENNESS_SIGNALS: List[str] = OPENNESS_SIGNALS.copy()
OPEN_PROCUREMENT_SIGNALS: List[str] = [
    "open tender",
    "competitive bidding",
    "request for proposal",
]


CONSTRUCTION_SIGNALS: List[str] = [
    "construction of",
    "civil works",
    "building works",
    "road works",
    "rehabilitation of buildings",
]
HARDWARE_SIGNALS: List[str] = [
    "hardware supply",
    "supply of laptops",
    "supply and delivery of vehicles",
    "network infrastructure",
]
MEDICAL_SIGNALS: List[str] = [
    "electronic health record",
    "electronic medical record",
    "hospital information system",
]
NEGATIVE_SIGNALS: List[str] = [
    "website design only",
    "email security",
    "antivirus",
    "erp system",
]
IRRELEVANT_SIGNALS: List[str] = sorted(
    set(CONSTRUCTION_SIGNALS + HARDWARE_SIGNALS + MEDICAL_SIGNALS + NEGATIVE_SIGNALS)
)


GENERIC_STANDALONE_KEYWORDS: List[str] = ["system", "platform", "solution", "portal"]

PRIORITY_PHRASES: List[str] = [
    "document management",
    "records management",
    "workflow automation",
    "case management",
]

PRIORITY_COMBINATIONS = [
    (["EDMS", "Workflow"], 8, "HIGH"),
    (["EDMS", "Case"], 8, "HIGH"),
    (["Gov", "EDMS"], 5, "MEDIUM"),
    (["Gov", "Workflow"], 5, "MEDIUM"),
]

QUALIFICATION_QUESTIONS: List[str] = [
    "Is Microsoft platform mandatory or optional?",
    "Is buyer open to alternative platforms?",
]


def _domain_hits(text: str) -> Tuple[List[str], List[str], List[str]]:
    t = _normalize(text)
    matched_keywords: List[str] = []
    matched_domains: List[str] = []
    matched_phrases: List[str] = []

    for domain, phrases in KEYWORD_DOMAINS.items():
        hits = _collect_hits(t, phrases)
        if hits:
            matched_domains.append(domain)
            matched_phrases.extend(hits)
            matched_keywords.extend([f"{domain}:{h}" for h in hits])
    return matched_keywords, matched_domains, matched_phrases


def _days_between(a: date, b: date) -> int:
    return (b - a).days


def _new_output() -> Dict[str, Any]:
    return {
        "tender_id": "",
        "title": "",
        "source": "",
        "publication_date": "",
        "deadline": "",
        "matched_keywords": [],
        "matched_domains": [],
        "score": 0,
        "priority": "LOW",
        "platform_locked": False,
        "requires_qualification": False,
        "hard_no_go": False,
        "likely_fit_for_f2": "NO",
        "qualification_questions": [],
        "status": "ACTIVE",
        "f2_fit": 0.0,
        "fit_bucket": "IGNORE",
        "bucket": "IGNORE",
        "opportunity_type": "UNKNOWN",
        "is_pipeline": False,
        "is_urgent": False,
        "timing": {
            "days_to_deadline": None,
            "days_since_publication": None,
            "missing_deadline": False,
            "missing_publication_date": False,
            "excluded_by_timing": False,
            "timing_reason": "",
        },
        "subscores": {
            "core_platform": 0.0,
            "governance": 0.0,
            "enterprise": 0.0,
            "integration": 0.0,
            "implementation": 0.0,
            "penalties": 0.0,
        },
        "matched_phrases": [],
        "rationale": [],
    }


@dataclass
class TenderInput:
    tender_id: str
    title: str
    source: str
    text: str
    publication_date: Optional[date] = None
    deadline: Optional[date] = None


def classify_tender(
    t: TenderInput,
    today: Optional[date] = None,
    profile: ScanProfile = GLOBAL_PROFILE,
) -> Dict[str, Any]:
    today = today or date.today()
    text = _normalize(f"{t.title} {t.text}")
    out = _new_output()

    out["tender_id"] = t.tender_id
    out["title"] = t.title
    out["source"] = t.source
    out["publication_date"] = t.publication_date.isoformat() if t.publication_date else ""
    out["deadline"] = t.deadline.isoformat() if t.deadline else ""

    timing = out["timing"]
    timing["missing_deadline"] = t.deadline is None
    timing["missing_publication_date"] = t.publication_date is None
    if t.deadline:
        timing["days_to_deadline"] = _days_between(today, t.deadline)
    if t.publication_date:
        timing["days_since_publication"] = _days_between(t.publication_date, today)

    matched_keywords, matched_domains, matched_phrases = _domain_hits(text)
    out["matched_keywords"] = matched_keywords
    out["matched_domains"] = matched_domains
    out["matched_phrases"] = matched_phrases

    core_domains = [d for d in matched_domains if d in {"EDMS", "Workflow", "Case", "Gov"}]
    irrelevant_hits = _collect_hits(text, IRRELEVANT_SIGNALS)
    if irrelevant_hits and not core_domains:
        out["status"] = "HARD_EXCLUDED"
        out["hard_no_go"] = True
        out["opportunity_type"] = "IRRELEVANT"
        out["rationale"] = [f"Irrelevant signal: {irrelevant_hits[0]}."]
        return out

    hard_lock = _collect_hits(text, MICROSOFT_HARD_LOCK_SIGNALS, max_hits=2)
    soft_lock = _collect_hits(text, MICROSOFT_SOFT_LOCK_SIGNALS, max_hits=2)
    openness = _collect_hits(text, OPENNESS_SIGNALS, max_hits=2)

    core_score = min(1.0, (len(core_domains) * 0.2) + (min(len(matched_phrases), 8) * 0.05))
    penalty = 0.0
    if hard_lock and not openness:
        penalty += 0.15
    elif soft_lock and not openness:
        penalty += 0.08

    if timing["days_since_publication"] is not None and timing["days_since_publication"] > profile.max_days_since_publication:
        timing["excluded_by_timing"] = True
        timing["timing_reason"] = "Publication too old."
    if timing["days_to_deadline"] is not None and timing["days_to_deadline"] < profile.min_days_to_deadline:
        timing["excluded_by_timing"] = True
        timing["timing_reason"] = "Deadline too close."

    out["f2_fit"] = round(max(0.0, min(1.0, core_score - penalty)), 4)
    out["score"] = int(round(out["f2_fit"] * 100))

    if out["f2_fit"] >= 0.75:
        out["fit_bucket"] = "HIGH"
    elif out["f2_fit"] >= 0.6:
        out["fit_bucket"] = "GOOD"
    elif out["f2_fit"] >= 0.45:
        out["fit_bucket"] = "WATCHLIST"
    else:
        out["fit_bucket"] = "IGNORE"

    out["bucket"] = "IGNORE" if timing["excluded_by_timing"] else out["fit_bucket"]
    out["priority"] = (
        "HIGH" if out["bucket"] in {"HIGH", "GOOD"} else
        "MEDIUM" if out["bucket"] == "WATCHLIST" else
        "LOW"
    )
    out["platform_locked"] = bool(hard_lock or soft_lock)
    out["requires_qualification"] = out["platform_locked"]
    if out["requires_qualification"]:
        out["qualification_questions"] = QUALIFICATION_QUESTIONS.copy()

    out["is_pipeline"] = "Pipeline" in matched_domains and len(core_domains) <= 1
    out["is_urgent"] = bool(timing["days_to_deadline"] is not None and timing["days_to_deadline"] <= 3)

    if timing["excluded_by_timing"]:
        out["status"] = "TIMING_EXCLUDED"
        out["hard_no_go"] = True

    if out["hard_no_go"]:
        out["likely_fit_for_f2"] = "NO"
    elif out["bucket"] in {"HIGH", "GOOD"}:
        out["likely_fit_for_f2"] = "YES"
    elif out["bucket"] == "WATCHLIST":
        out["likely_fit_for_f2"] = "CONDITIONAL"
    else:
        out["likely_fit_for_f2"] = "NO"

    out["opportunity_type"] = (
        "PIPELINE" if out["is_pipeline"] else
        "PLATFORM PROCUREMENT" if len(core_domains) >= 2 else
        "GENERAL"
    )
    out["rationale"] = [
        f"Matched: {', '.join(matched_phrases[:5])}." if matched_phrases else "No strong keyword matches.",
        "Platform lock signal found." if out["platform_locked"] else "No platform lock signal.",
    ]
    if timing["excluded_by_timing"] and timing["timing_reason"]:
        out["rationale"].append("Timing filter: " + timing["timing_reason"])

    out["subscores"] = {
        "core_platform": round(core_score, 4),
        "governance": round(0.05 if "Gov" in matched_domains else 0.0, 4),
        "enterprise": round(0.04 if "EDMS" in matched_domains else 0.0, 4),
        "integration": round(0.03 if "Workflow" in matched_domains else 0.0, 4),
        "implementation": round(0.03 if "Case" in matched_domains else 0.0, 4),
        "penalties": round(penalty, 4),
    }
    return out
