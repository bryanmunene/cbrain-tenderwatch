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


GLOBAL_PROFILE = ScanProfile("GLOBAL", max_days_since_publication=90, min_days_to_deadline=7)
AFRICA_STRICT_PROFILE = ScanProfile("AFRICA_STRICT", max_days_since_publication=90, min_days_to_deadline=7)


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


# Expanded prompt-driven F2 keyword map.
KEYWORD_DOMAINS: Dict[str, List[str]] = {
    "EDMS": [
        "document management system",
        "document management",
        "electronic document management system",
        "enterprise document management",
        "edms",
        "edrms",
        "dms",
        "document repository",
        "knowledge repository",
        "document tracking",
        "file tracking system",
        "electronic filing",
        "e filing system",
        "digital filing system",
        "document lifecycle",
        "document imaging",
        "e archiving",
    ],
    "Records": [
        "records management",
        "records management system",
        "records information system",
        "records information management",
        "electronic records management",
        "enterprise records system",
        "records digitization",
        "records digitisation",
        "digitization of records",
        "digitisation of records",
        "records lifecycle",
        "retention schedule",
        "records registry",
        "registry management",
        "file registry system",
        "records centre",
        "records center",
        "archives management",
        "archival system",
        "electronic archiving",
        "archives and records",
        "official correspondence",
        "incoming and outgoing correspondence",
        "mail registry",
        "information management system",
        "information management",
        "correspondence management system",
        "correspondence management",
        "correspondence and registry",
        "digital registry",
        "registry system",
        "enterprise information management",
        "file management system",
        "document control system",
        "document control",
        "office automation system",
        "office automation",
        "regulatory information management",
        "audit management system",
        "document storage system",
    ],
    "Workflow": [
        "workflow automation",
        "workflow management system",
        "workflow management",
        "workflow system",
        "workflow",
        "business process management",
        "bpm",
        "process automation system",
        "approval workflow",
        "approval system",
        "routing and approval",
        "task management",
        "government workflow",
        "administrative workflow",
        "back office automation",
        "document centric workflow",
        "business rules",
    ],
    "Case": [
        "case management",
        "case handling",
        "case tracking system",
        "case file management",
        "case workflow",
        "administrative casework",
        "matter management system",
        "matter management",
        "docket management",
        "complaint management system",
        "complaints handling",
        "complaints portal",
        "grievance redress system",
        "grievance management system",
        "grievance portal",
        "petition management",
        "appeals management",
        "inspection management",
        "compliance management",
        "service request system",
        "service request management",
        "incident management",
        "dispute management system",
    ],
    "ServiceDelivery": [
        "e services portal",
        "citizen services portal",
        "citizen services platform",
        "citizen portal",
        "service delivery portal",
        "service delivery system",
        "public service portal",
        "public administration platform",
        "public sector administrative platform",
        "submission portal",
        "internal workflow portal",
        "service desk software",
        "help desk software",
        "online application portal",
        "citizen engagement portal",
        "public sector platform",
    ],
    "Licensing": [
        "licensing system",
        "permit management system",
        "licensing and permits",
        "permit issuance",
        "application processing",
        "online licensing",
        "online permits",
    ],
    "ProcurementRecords": [
        "contract management system",
        "contract lifecycle management",
        "procurement records system",
        "procurement management system",
        "e procurement records",
        "tender management system",
        "contract and records management",
    ],
    "ECM": [
        "enterprise content management",
        "electronic content management",
        "content services platform",
        "ecm",
        "content management",
        "information repository",
    ],
    "Forms": [
        "digital forms",
        "forms automation",
        "form management",
        "structured data capture",
        "data extraction",
        "search and retrieval",
        "metadata management",
        "dashboard reporting",
        "audit trail",
        "role based access",
        "document versioning",
    ],
    "Gov": [
        "e government platform",
        "digital government platform",
        "digital government",
        "digital transformation",
        "public sector",
        "government",
        "ministry",
        "department",
        "agency",
        "authority",
        "commission",
        "secretariat",
        "county government",
        "national government",
        "local government",
        "municipality",
        "judiciary",
        "parliament",
        "public service",
        "service delivery",
        "national archives",
        "land registry",
        "revenue authority",
        "state department",
        "e office",
        "paperless office",
        "paperless workflow",
    ],
    "Integration": [
        "api integration",
        "system integration",
        "integration platform",
        "middleware",
        "data migration",
        "change management",
        "training",
        "support and maintenance",
        "platform implementation",
        "modernization",
        "modernisation",
        "legacy replacement",
        "business process reengineering",
        "bpr",
        "low code platform",
        "no code platform",
        "configurable process platform",
        "line of business platform",
        "ict consultancy",
        "ict consulting",
        "it consulting services",
        "technology consultancy",
        "business process improvement",
        "digital transformation consultancy",
        "information systems consultancy",
    ],
    "Pipeline": [
        "records management system tender",
        "document management system tender",
        "electronic records management tender",
        "workflow automation tender",
        "case management system tender",
        "citizen services portal tender",
        "grievance management system tender",
        "licensing system tender",
        "registry and correspondence tender",
        "digitization of records tender",
        "archives management tender",
        "business process management tender",
    ],
}


ALL_KEYWORDS: List[str] = sorted({kw for kws in KEYWORD_DOMAINS.values() for kw in kws})

KEYWORD_TO_DOMAIN: Dict[str, List[str]] = {}
for domain, keywords in KEYWORD_DOMAINS.items():
    for kw in keywords:
        KEYWORD_TO_DOMAIN.setdefault(_normalize_phrase(kw), []).append(domain)


MICROSOFT_HARD_LOCK_SIGNALS: List[str] = [
    "microsoft power platform",
    "power apps",
    "power automate",
    "sharepoint online as required platform",
    "sharepoint as mandatory platform",
    "must be implemented on microsoft stack",
    "bidder must use existing microsoft power platform",
    "solution shall be built on sharepoint",
    "solution must use microsoft 365 platform",
    "no alternative platform accepted",
    "must use sharepoint",
    "must use microsoft 365",
    "must use power platform",
    "built on sharepoint",
]
MICROSOFT_SOFT_LOCK_SIGNALS: List[str] = [
    "existing microsoft environment",
    "microsoft licenses provided",
    "enterprise agreement",
    "sharepoint environment exists",
    "integration with microsoft 365",
    "compatibility with microsoft tools",
    "leveraging existing microsoft investment",
    "current sharepoint deployment",
    "power platform environment available",
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
    "buyer open to alternatives",
    "open to alternatives",
    "consider alternative solutions",
    "vendor neutral",
    "technology neutral",
    "platform agnostic",
    "interoperable",
]
PLATFORM_OPENNESS_SIGNALS: List[str] = OPENNESS_SIGNALS.copy()
OPEN_PROCUREMENT_SIGNALS: List[str] = [
    "open tender",
    "open national tender",
    "international tender",
    "competitive bidding",
    "invitation to tender",
    "invitation for bids",
    "expression of interest",
    "call for proposals",
    "request for proposal",
    "request for quotation",
    "procurement notice",
    "tender notice",
]


CONSTRUCTION_SIGNALS: List[str] = [
    "construction",
    "civil works",
    "road works",
    "building works",
    "renovation",
    "drilling",
    "water works",
    "electrical installation",
    "contractor works",
    "rehabilitation of buildings",
]
HARDWARE_SIGNALS: List[str] = [
    "hardware",
    "laptops",
    "desktops",
    "printers",
    "servers",
    "network switches",
    "routers",
    "cabling",
    "ups",
    "generator",
    "vehicles",
    "motor vehicles",
    "motorcycles",
    "tractors",
    "furniture",
    "fuel",
    "consumables",
    "biometric hardware",
    "cctv",
    "access control hardware",
    "network infrastructure",
]
MEDICAL_SIGNALS: List[str] = [
    "medical equipment",
    "laboratory equipment",
    "electronic health record",
    "electronic medical record",
    "hospital information system",
]
NEGATIVE_SIGNALS: List[str] = [
    "website redesign only",
    "website development only",
    "branding only",
    "social media only",
    "seo only",
    "pure mobile app development",
    "hosting only",
    "cloud hosting only",
    "internet bandwidth only",
    "cybersecurity only",
    "siem",
    "firewall",
    "antivirus",
    "backup appliance only",
    "data center only",
    "isp services",
    "pure erp replacement",
    "core banking only",
    "hr payroll only",
    "geospatial only",
    "logistics only",
    "fleet management only",
    "commodity supply only",
]
IRRELEVANT_SIGNALS: List[str] = sorted(
    set(CONSTRUCTION_SIGNALS + HARDWARE_SIGNALS + MEDICAL_SIGNALS + NEGATIVE_SIGNALS)
)


GENERIC_STANDALONE_KEYWORDS: List[str] = ["system", "platform", "solution", "portal"]

PRIORITY_PHRASES: List[str] = [
    "document and records management",
    "electronic document and records management",
    "workflow automation",
    "case management",
    "grievance redress system",
    "citizen services portal",
    "service delivery portal",
    "licensing system",
    "permit management system",
    "digitization of records",
    "electronic archiving",
]

PRIORITY_COMBINATIONS = [
    (["Workflow", "Records", "Gov"], 18, "HIGH"),
    (["Case", "Records", "Gov"], 18, "HIGH"),
    (["EDMS", "Workflow", "Gov"], 16, "HIGH"),
    (["EDMS", "Records", "Gov"], 16, "HIGH"),
    (["ServiceDelivery", "Workflow", "Gov"], 14, "HIGH"),
    (["Licensing", "Workflow", "ServiceDelivery"], 14, "HIGH"),
    (["Case", "ServiceDelivery", "Gov"], 14, "HIGH"),
    (["Records", "ECM"], 10, "MEDIUM"),
    (["ProcurementRecords", "Records"], 10, "MEDIUM"),
    (["Gov", "Workflow"], 8, "MEDIUM"),
]

QUALIFICATION_QUESTIONS: List[str] = [
    "Total number of end-users?",
    "Tender budget?",
    "Annual cost of Microsoft Enterprise Agreement or licenses?",
    "Is the buyer open to considering cBrain F2 as an alternative platform?",
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

    core_domains = [d for d in matched_domains if d in {"EDMS", "Workflow", "Case", "Gov", "Records", "ECM", "ServiceDelivery", "Licensing", "ProcurementRecords"}]
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
