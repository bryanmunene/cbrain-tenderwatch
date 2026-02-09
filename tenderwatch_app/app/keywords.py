
from __future__ import annotations

# ...existing docstring and imports...

# ...existing TIMING_RULES, NORMALIZATION, _normalize, _phrase_hit...

# CORE KEYWORD DOMAINS (F2 RELEVANCE SIGNALS)
KEYWORD_DOMAINS: Dict[str, List[str]] = {
    # ...existing domain definitions...
}

# After KEYWORD_DOMAINS is defined, build ALL_KEYWORDS and DOMAIN_WEIGHTS if needed
# (If these are already defined, leave them in place)

# KEYWORD_TO_DOMAIN: Maps each keyword to the list of domains it appears in
KEYWORD_TO_DOMAIN: Dict[str, list[str]] = {}
for domain, keywords in KEYWORD_DOMAINS.items():
    for kw in keywords:
        KEYWORD_TO_DOMAIN.setdefault(kw, []).append(domain)

"""
TenderWatch — F2-Aligned Intelligence Logic (Authoritative, Revised)
===================================================================

Fixes applied
- Moved `from __future__ import annotations` to the very top (required).
- Removed duplicated pasted blocks (you had the whole module twice).
- Removed duplicate "ECM" key inside KEYWORD_DOMAINS (Python overwrites earlier key silently).
- Moved KEYWORD_TO_DOMAIN construction to AFTER KEYWORD_DOMAINS exists.
- Restored missing "Records" in DOMAIN_WEIGHTS (you were scoring it via combos but not weighting it).
"""

import re
from dataclasses import dataclass
from datetime import date
from typing import Any, Dict, List, Tuple, Optional


# =============================================================================
# TIMING LOGIC (HARD FILTERS + PENALTIES)
# =============================================================================

TIMING_RULES: Dict[str, Any] = {
    "min_days_to_deadline": 7,
    "max_days_since_float": 90,
    "missing_dates_behavior": "penalize_not_exclude",
    "missing_deadline_penalty": -3,
    "missing_publication_penalty": -2,
}

# =============================================================================
# TEXT NORMALIZATION
# =============================================================================

NORMALIZATION: Dict[str, Any] = {
    "lowercase": True,
    "collapse_whitespace": True,
    "max_text_chars": 250_000,
}

_WORD_BOUNDARY = r"(?:^|[\s\W])"
_WORD_BOUNDARY_END = r"(?:$|[\s\W])"


def _normalize(text: str) -> str:
    if not text:
        return ""
    t = text[: NORMALIZATION["max_text_chars"]]
    if NORMALIZATION["lowercase"]:
        t = t.lower()
    if NORMALIZATION["collapse_whitespace"]:
        t = re.sub(r"\s+", " ", t).strip()
    return t


def _phrase_hit(text: str, phrase: str) -> bool:
    p = re.escape(phrase.lower().strip())
    pattern = _WORD_BOUNDARY + p + _WORD_BOUNDARY_END
    return re.search(pattern, text) is not None


# =============================================================================
# CORE KEYWORD DOMAINS (F2 RELEVANCE SIGNALS)
# =============================================================================

KEYWORD_DOMAINS: Dict[str, List[str]] = {
    "EDMS": [
        "electronic document management",
        "document management system",
        "document management",
        "edms",
        "edrms",
        "electronic document and records management",
        "document repository",
        "document tracking",
        "document digitization",
        "scanning and archiving",
        "document imaging",
        "intelligent document processing",
        "idp",
        "ocr",
        "paperless",
        "capture solution",
    ],
    "ECM": [
        "enterprise content management",
        "ecm",
        "content services platform",
        "content services",
        "content management",
        "knowledge repository",
        "document repository",
    ],
    "Records": [
        "records management",
        "records lifecycle",
        "records retention",
        "retention schedule",
        "records disposal",
        "digital records",
        "archives",
        "archival system",
        "registry",
        "registry management",
        "file registry",
        "file tracking",
        "classification scheme",
        "classification plan",
        "file plan",
        "information governance",
        "audit trail",
        "audit logging",
        "legal hold",
        "iso 15489",
        "right to information",
        "freedom of information",
        "foia",
    ],
    "Workflow": [
        "workflow",
        "workflow automation",
        "workflow management",
        "approval workflow",
        "business process management",
        "bpm",
        "bpm system",
        "process automation",
        "digital process automation",
        "process orchestration",
        "task routing",
        "work item",
        "case workflow",
        "bpmn",
    ],
    "Case": [
        "case management",
        "case handling",
        "case tracking",
        "case processing",
        "docket",
        "matter management",
        "complaint management",
        "complaints management",
        "grievance",
        "grievance redress",
        "inspection management",
        "licensing system",
        "permit management",
        "enforcement case",
        "regulatory case",
    ],
    "Forms": [
        "electronic forms",
        "e-forms",
        "digital forms",
        "form automation",
        "electronic memos",
        "digital correspondence",
        "correspondence management",
        "e-filing",
        "electronic filing",
    ],
    "ServiceDelivery": [
        "service request",
        "service requests",
        "citizen services",
        "e-services",
        "service delivery",
        "citizen portal",
        "government portal",
        "one stop shop",
    ],
    "Gov": [
        "e-government",
        "digital government",
        "e-governance",
        "public sector",
        "public sector digitization",
        "government automation",
        "government agency",
        "public institution",
        "parastatal",
        "state corporation",
        "municipal",
        "local authority",
        "ministry",
        "department",
        "authority",
        "commission",
    ],
    "Digitalization": [
        "paperless government",
        "digital transformation",
        "digitization",
        "digital first",
        "government modernization",
        "administrative reform",
        "public administration reform",
        "knowledge management",
    ],
}

ALL_KEYWORDS: List[str] = sorted({kw for kws in KEYWORD_DOMAINS.values() for kw in kws})

KEYWORD_TO_DOMAIN: Dict[str, List[str]] = {}
for domain, keywords in KEYWORD_DOMAINS.items():
    for kw in keywords:
        KEYWORD_TO_DOMAIN.setdefault(kw, []).append(domain)

DOMAIN_WEIGHTS: Dict[str, int] = {
    "Records": 3,
    "Workflow": 3,
    "Case": 3,
    "EDMS": 2,
    "ECM": 2,
    "Forms": 2,
    "ServiceDelivery": 2,
    "Gov": 1,
    "Digitalization": 1,
}

# =============================================================================
# PLATFORM LOCK-IN & SI-ONLY SIGNALS (CONDITIONAL NO-GO)
# =============================================================================

MICROSOFT_HARD_LOCK_SIGNALS: List[str] = [
    "must use power platform",
    "must use microsoft power platform",
    "must use sharepoint",
    "deploy on sharepoint",
    "built on power platform",
    "built on sharepoint",
    "solution shall be built on power platform",
    "solution shall be built on sharepoint",
    "sharepoint online",
    "power apps",
    "power automate",
    "dataverse",
]

MICROSOFT_SOFT_LOCK_SIGNALS: List[str] = [
    "existing sharepoint",
    "already procured microsoft",
    "procured power platform",
    "microsoft enterprise agreement",
    "licenses will be provided",
    "excluding licenses",
    "implementation partner",
    "configuration services",
    "si partner",
    "sharepoint environment",
]

# =============================================================================
# GENERAL PLATFORM LOCK-IN SIGNALS
# =============================================================================
PLATFORM_LOCKIN_SIGNALS: List[str] = [
    "platform lock-in",
    "vendor lock-in",
    "proprietary platform",
    "proprietary solution",
    "single vendor",
    "restricted platform",
    "closed platform",
    "must use power platform",
    "must use microsoft power platform",
    "must use sharepoint",
    "deploy on sharepoint",
    "built on power platform",
    "built on sharepoint",
    "solution shall be built on power platform",
    "solution shall be built on sharepoint",
    "sharepoint online",
    "power apps",
    "power automate",
    "dataverse",
]

# =============================================================================
# OPEN PROCUREMENT SIGNALS (BUYER MAY CONSIDER ALTERNATIVES)
# =============================================================================
OPEN_PROCUREMENT_SIGNALS: List[str] = [
    "open procurement",
    "platform agnostic",
    "vendor neutral",
    "alternative solutions",
    "alternative platforms",
    "technology neutral",
    "best value",
    "total cost of ownership",
    "tco analysis",
    "fit for purpose",
    "or equivalent",
]

# =============================================================================
# MICROSOFT COMMITMENT SIGNALS (SI-ONLY ENGAGEMENT)
# =============================================================================
MICROSOFT_COMMITMENT_SIGNALS: List[str] = [
    "must use power platform",
    "must use microsoft power platform",
    "must use sharepoint",
    "deploy on sharepoint",
    "built on power platform",
    "built on sharepoint",
    "solution shall be built on power platform",
    "solution shall be built on sharepoint",
    "sharepoint online",
    "power apps",
    "power automate",
    "dataverse",
    "existing sharepoint",
    "already procured microsoft",
    "procured power platform",
    "microsoft enterprise agreement",
    "licenses will be provided",
    "excluding licenses",
    "implementation partner",
    "configuration services",
    "si partner",
    "sharepoint environment",
]

QUALIFICATION_QUESTIONS: List[str] = [
    "Total number of end-users?",
    "Total tender budget (implementation + support)?",
    "Annual Microsoft EA / license cost?",
    "Is the buyer open to alternative platforms?",
    "Is this a platform decision or SI-only delivery?",
]

PLATFORM_OPENNESS_SIGNALS: List[str] = [
    "platform agnostic",
    "vendor neutral",
    "alternative solutions",
    "alternative platforms",
    "technology neutral",
    "best value",
    "total cost of ownership",
    "tco analysis",
    "fit for purpose",
    "or equivalent",
]

# =============================================================================
# HARD NO-GO ELIMINATION SIGNALS (ARCHITECTURAL MISMATCH)
# =============================================================================

HARD_ELIMINATION_SIGNALS: List[str] = [
    "consultancy services",
    "advisory services",
    "strategy development",
    "roadmap development",
    "policy advisory",
    "assessment study",
    "feasibility study",
    "maturity assessment",
    "baseline assessment",
    "training only",
    "capacity building only",
    "hardware supply",
    "supply of laptops",
    "supply of computers",
    "network infrastructure",
    "cabling works",
    "data center",
    "data centre",
    "cloud hosting only",
    "internet connectivity",
    "construction of",
    "civil works",
    "building works",
    "renovation",
    "rehabilitation",
    "water works",
    "road works",
    "inventory management",
    "stock management",
    "logistics system",
    "supply chain system",
    "fleet management",
    "warehouse management",
]

# =============================================================================
# NEGATIVE SIGNALS (SCORE PENALTY, NOT ELIMINATION)
# =============================================================================

NEGATIVE_SIGNALS: List[str] = [
    "website design only",
    "hosting services",
    "storage infrastructure",
    "backup services",
    "email security",
    "antivirus",
    "erp system",
    "crm system",
    "mobile app development",
    "social media management",
]

# =============================================================================
# IRRELEVANT SIGNALS (STRICT EXCLUSION)
# =============================================================================
IRRELEVANT_SIGNALS: List[str] = [
    "construction",
    "building works",
    "civil works",
    "renovation",
    "rehabilitation",
    "water works",
    "road works",
    "inventory management",
    "stock management",
    "logistics system",
    "supply chain system",
    "fleet management",
    "warehouse management",
    "email security",
    "antivirus",
    "erp system",
    "crm system",
    "mobile app development",
    "social media management",
    "website design only",
    "cloud hosting only",
    "hardware supply",
    "supply of laptops",
    "supply of computers",
    "network infrastructure",
    "cabling works",
    "data center",
    "data centre",
]

# =============================================================================
# SCORING LOGIC
# =============================================================================

SCORING: Dict[str, int] = {
    "per_keyword_hit": 1,
    "unique_domain_bonus": 2,
    "domain_weight_multiplier": 1,
    "gov_context_bonus": 2,
    "workflow_records_combo": 4,
    "case_records_combo": 4,
    "workflow_case_combo": 3,
    "platform_open_bonus": 3,
    "microsoft_hard_lock_penalty": -8,
    "microsoft_soft_lock_penalty": -4,
    "negative_signal_penalty": -2,
}

PRIORITY_COMBINATIONS: List[Tuple[List[str], str]] = [
    (["Workflow", "Records", "Gov"], "HIGH"),
    (["Case", "Records", "Gov"], "HIGH"),
    (["Workflow", "Case", "Gov"], "HIGH"),
    (["Records", "Gov"], "MEDIUM"),
    (["Workflow", "Gov"], "MEDIUM"),
    (["Case", "Gov"], "MEDIUM"),
]

PRIORITY_THRESHOLDS: Dict[str, int] = {"HIGH": 14, "MEDIUM": 8, "LOW": 0}

# =============================================================================
# PRIORITY PHRASES (HIGH VALUE SIGNALS)
# =============================================================================
PRIORITY_PHRASES: List[str] = [
    "workflow automation",
    "case management",
    "records management",
    "document management",
    "digital government",
    "e-government",
    "public sector reform",
    "service delivery platform",
    "citizen portal",
    "platform agnostic",
    "vendor neutral",
    "alternative solutions",
    "open procurement",
    "fit for purpose",
    "knowledge management",
    "digital transformation",
    "government modernization",
    "business process management",
    "bpm",
    "approval workflow",
    "process automation",
    "records lifecycle",
    "retention schedule",
    "audit trail",
    "information governance",
]

# =============================================================================
# GENERIC STANDALONE KEYWORDS (BROAD SIGNALS)
# =============================================================================
GENERIC_STANDALONE_KEYWORDS: List[str] = [
    "records",
    "workflow",
    "case",
    "edms",
    "ecm",
    "forms",
    "service delivery",
    "government",
    "digitalization",
    "platform",
    "public sector",
    "document",
    "archive",
    "registry",
    "portal",
    "automation",
    "management",
    "system",
    "solution",
    "process",
]

# =============================================================================
# OUTPUT SCHEMA
# =============================================================================

OUTPUT_SCHEMA: Dict[str, Any] = {
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
}

# =============================================================================
# CLASSIFICATION ENGINE
# =============================================================================

@dataclass
class TenderInput:
    tender_id: str
    title: str
    source: str
    text: str
    publication_date: Optional[date] = None
    deadline: Optional[date] = None


def _days_between(a: date, b: date) -> int:
    return (b - a).days


def _collect_hits(text: str, phrases: List[str]) -> List[str]:
    hits: List[str] = []
    for p in phrases:
        if _phrase_hit(text, p):
            hits.append(p)
    seen = set()
    out: List[str] = []
    for h in hits:
        if h not in seen:
            seen.add(h)
            out.append(h)
    return out


def _domain_hits(text: str) -> Tuple[List[str], List[str]]:
    matched_keywords: List[str] = []
    matched_domains: List[str] = []
    for domain, phrases in KEYWORD_DOMAINS.items():
        hits = _collect_hits(text, phrases)
        if hits:
            matched_domains.append(domain)
            matched_keywords.extend([f"{domain}:{h}" for h in hits])
    return matched_keywords, matched_domains


def _has_combo(domains: List[str], combo: List[str]) -> bool:
    s = set(domains)
    return all(d in s for d in combo)


def _priority_from_combos(domains: List[str]) -> str:
    for combo, lvl in PRIORITY_COMBINATIONS:
        if _has_combo(domains, combo):
            return lvl
    return "LOW"


def classify_tender(t: TenderInput, today: Optional[date] = None) -> Dict[str, Any]:
    today = today or date.today()
    text = _normalize(f"{t.title} {t.text}")

    out = dict(OUTPUT_SCHEMA)
    out["tender_id"] = t.tender_id
    out["title"] = t.title
    out["source"] = t.source
    out["publication_date"] = t.publication_date.isoformat() if t.publication_date else ""
    out["deadline"] = t.deadline.isoformat() if t.deadline else ""

    score = 0
    hard_exclude = False

    if t.deadline:
        if _days_between(today, t.deadline) < TIMING_RULES["min_days_to_deadline"]:
            hard_exclude = True
    else:
        score += TIMING_RULES["missing_deadline_penalty"]

    if t.publication_date:
        if _days_between(t.publication_date, today) > TIMING_RULES["max_days_since_float"]:
            hard_exclude = True
    else:
        score += TIMING_RULES["missing_publication_penalty"]

    hard_elims = _collect_hits(text, HARD_ELIMINATION_SIGNALS)
    if hard_elims:
        out["hard_no_go"] = True
        out["likely_fit_for_f2"] = "NO"
        out["score"] = -999
        out["matched_keywords"] = [f"ELIM:{h}" for h in hard_elims]
        out["matched_domains"] = []
        out["priority"] = "LOW"
        return out

    if hard_exclude:
        out["hard_no_go"] = True
        out["likely_fit_for_f2"] = "NO"
        out["score"] = -100
        out["matched_keywords"] = []
        out["matched_domains"] = []
        out["priority"] = "LOW"
        return out

    matched_keywords, matched_domains = _domain_hits(text)
    out["matched_keywords"] = matched_keywords
    out["matched_domains"] = matched_domains

    domain_score = 0
    for d in matched_domains:
        domain_score += DOMAIN_WEIGHTS.get(d, 1) * SCORING["domain_weight_multiplier"]
    score += domain_score

    score += len(matched_keywords) * SCORING["per_keyword_hit"]
    score += len(matched_domains) * SCORING["unique_domain_bonus"]

    if "Gov" in matched_domains or _phrase_hit(text, "government") or _phrase_hit(text, "ministry"):
        score += SCORING["gov_context_bonus"]

    if _has_combo(matched_domains, ["Workflow", "Records"]):
        score += SCORING["workflow_records_combo"]
    if _has_combo(matched_domains, ["Case", "Records"]):
        score += SCORING["case_records_combo"]
    if _has_combo(matched_domains, ["Workflow", "Case"]):
        score += SCORING["workflow_case_combo"]

    openness_hits = _collect_hits(text, PLATFORM_OPENNESS_SIGNALS)
    if openness_hits:
        score += SCORING["platform_open_bonus"]

    hard_lock_hits = _collect_hits(text, MICROSOFT_HARD_LOCK_SIGNALS)
    soft_lock_hits = _collect_hits(text, MICROSOFT_SOFT_LOCK_SIGNALS)

    platform_locked = False
    requires_qualification = False

    if hard_lock_hits:
        platform_locked = True
        requires_qualification = True
        score += SCORING["microsoft_hard_lock_penalty"]
    elif soft_lock_hits:
        platform_locked = True
        requires_qualification = True
        score += SCORING["microsoft_soft_lock_penalty"]

    out["platform_locked"] = platform_locked
    out["requires_qualification"] = requires_qualification

    neg_hits = _collect_hits(text, NEGATIVE_SIGNALS)
    if neg_hits:
        score += len(neg_hits) * SCORING["negative_signal_penalty"]

    combo_priority = _priority_from_combos(matched_domains)
    if score >= PRIORITY_THRESHOLDS["HIGH"]:
        priority = "HIGH"
    elif score >= PRIORITY_THRESHOLDS["MEDIUM"]:
        priority = "MEDIUM"
    else:
        priority = combo_priority
    out["priority"] = priority

    if score >= PRIORITY_THRESHOLDS["HIGH"] and (not hard_lock_hits or openness_hits):
        out["likely_fit_for_f2"] = "YES"
    elif platform_locked:
        out["likely_fit_for_f2"] = "CONDITIONAL" if openness_hits else "NO"
    elif score >= PRIORITY_THRESHOLDS["MEDIUM"]:
        out["likely_fit_for_f2"] = "CONDITIONAL"
    else:
        out["likely_fit_for_f2"] = "NO"

    if out["requires_qualification"]:
        out["qualification_questions"] = QUALIFICATION_QUESTIONS.copy()

    if hard_lock_hits:
        out["matched_keywords"].extend([f"MS_HARD_LOCK:{h}" for h in hard_lock_hits])
    if soft_lock_hits:
        out["matched_keywords"].extend([f"MS_SOFT_LOCK:{h}" for h in soft_lock_hits])
    if openness_hits:
        out["matched_keywords"].extend([f"OPENNESS:{h}" for h in openness_hits])
    if neg_hits:
        out["matched_keywords"].extend([f"NEG:{h}" for h in neg_hits])

    out["score"] = int(score)
    return out
