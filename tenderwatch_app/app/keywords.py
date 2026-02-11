from __future__ import annotations

"""
TenderWatch — F2-Aligned Tender Intelligence Logic (v2, practical + high-precision)
=================================================================================

Goal
----
Score tenders for suitability to cBrain F2-style opportunities:
- Integrated *case + document/records + workflow* for public sector / regulated bodies
- With governance/compliance signals (retention, audit trail, archiving, file plans)
- Allow "pipeline shaping" items (Solution Architect / RFI / PIN / APP) to surface as WATCHLIST
- Avoid false positives: hardware-only, construction, digitization-only, pure renewals, etc.

Key design choices (to match “results like above”)
--------------------------------------------------
1) NOT hard-excluding “consulting/solution architect” tenders.
   They become opportunity_type="CONSULTING/ARCHITECTURE" and typically bucket WATCHLIST/GOOD.
2) Hard excludes are reserved for obvious non-software categories (construction/roads/waterworks)
   or hardware-only tenders *when core platform signals are absent*.
3) Uses an F2-style rubric (0–1):
   A) Core platform need (0–0.55)
   B) Compliance/records governance (0–0.20)
   C) Enterprise rollout (0–0.10)
   D) Integration & identity (0–0.10)
   E) Implementation services (0–0.05)
   Penalties up to -0.30 for renewals-only/hardware-only/digitization-only/platform lock-in/etc.
4) Timing logic is profile-based (GLOBAL vs AFRICA_STRICT).

Usage
-----
- Call classify_tender(TenderInput(...), profile=GLOBAL_PROFILE) or AFRICA_STRICT_PROFILE.
- Output includes:
  - f2_fit (0–1), score (0–100), bucket (HIGH/GOOD/WATCHLIST/IGNORE)
  - likely_fit_for_f2 (YES/CONDITIONAL/NO)
  - platform lock flags (MICROSOFT hard/soft)
  - matched_phrases, matched_domains, rationale
"""

import re
from dataclasses import dataclass
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

# =============================================================================
# PROFILES (timing rules + strictness)
# =============================================================================

@dataclass(frozen=True)
class ScanProfile:
    name: str
    max_days_since_publication: int
    min_days_to_deadline: int
    allow_urgent_override: bool = True
    urgent_override_min_fit: float = 0.85  # if deadline is too soon but fit is very high, keep as URGENT
    missing_deadline_behavior: str = "penalize"  # "penalize" | "pipeline" | "exclude"
    missing_publication_behavior: str = "penalize"  # "penalize" | "exclude"
    missing_deadline_penalty: float = 0.06
    missing_publication_penalty: float = 0.04


GLOBAL_PROFILE = ScanProfile(
    name="GLOBAL",
    max_days_since_publication=90,
    min_days_to_deadline=7,
    allow_urgent_override=True,
    urgent_override_min_fit=0.85,
    missing_deadline_behavior="pipeline",
    missing_publication_behavior="penalize",
    missing_deadline_penalty=0.06,
    missing_publication_penalty=0.04,
)

AFRICA_STRICT_PROFILE = ScanProfile(
    name="AFRICA_STRICT",
    max_days_since_publication=30,
    min_days_to_deadline=0,  # Africa scan usually just needs deadline >= today; set 0 and enforce "open"
    allow_urgent_override=True,
    urgent_override_min_fit=0.85,
    missing_deadline_behavior="pipeline",
    missing_publication_behavior="penalize",
    missing_deadline_penalty=0.06,
    missing_publication_penalty=0.04,
)

# =============================================================================
# NORMALIZATION + PHRASE MATCHING
# =============================================================================

NORMALIZATION: Dict[str, Any] = {
    "lowercase": True,
    "collapse_whitespace": True,
    "max_text_chars": 250_000,
}

_PATTERN_CACHE: Dict[str, re.Pattern] = {}


def _normalize(text: str) -> str:
    if not text:
        return ""
    t = text[: NORMALIZATION["max_text_chars"]]
    if NORMALIZATION["lowercase"]:
        t = t.lower()

    # Make common separators behave consistently for phrase matching
    # (helps match "e-government", "e/filing", "edms/edrms", etc.)
    t = re.sub(r"[\-/\\_|]+", " ", t)
    t = re.sub(r"[“”\"'`´]", " ", t)
    t = re.sub(r"[\(\)\[\]\{\}]", " ", t)
    t = re.sub(r"[,:;]+", " ", t)

    if NORMALIZATION["collapse_whitespace"]:
        t = re.sub(r"\s+", " ", t).strip()
    return t


def _normalize_phrase(phrase: str) -> str:
    p = (phrase or "").strip().lower()
    p = re.sub(r"[\-/\\_|]+", " ", p)
    p = re.sub(r"\s+", " ", p).strip()
    return p


def _compile_phrase(phrase: str) -> re.Pattern:
    """
    Compile a phrase matcher:
    - Normalize separators in phrase the same way as text.
    - Allow variable whitespace between tokens.
    - Use unicode-aware word boundaries via (?<!\\w) ... (?!\\w)
    """
    p = _normalize_phrase(phrase)
    if not p:
        return re.compile(r"(?!x)x")

    escaped = re.escape(p).replace(r"\ ", r"\s+")
    pattern = rf"(?<!\w){escaped}(?!\w)"
    return re.compile(pattern, flags=re.UNICODE)


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
    for p in phrases:
        if _phrase_hit(text, p):
            hits.append(_normalize_phrase(p))
            if max_hits is not None and len(hits) >= max_hits:
                break
    # De-dupe while preserving order
    seen = set()
    out: List[str] = []
    for h in hits:
        if h not in seen:
            seen.add(h)
            out.append(h)
    return out


# =============================================================================
# KEYWORD DOMAINS (expanded + multilingual)
# =============================================================================

KEYWORD_DOMAINS: Dict[str, List[str]] = {
    # Core platform signals
    "EDMS": [
        "electronic document management",
        "document management system",
        "document management",
        "edms",
        "edrms",
        "electronic document and records management",
        "document repository",
        "document tracking",
        "correspondence management",
        "mailroom",
        "digital registry",
        "registry modernization",
        # FR / PT / ES / AR
        "gestion electronique des documents",
        "ged",
        "gestion documentaire",
        "gestao documental",
        "gestao de documentos",
        "gestion documental",
        "archivo electronico",
        "نظام إدارة الوثائق",
    ],
    "ECM": [
        "enterprise content management",
        "ecm",
        "content services platform",
        "content services",
        "content management",
        "enterprise content services",
        # FR/ES
        "services de contenu",
        "plateforme de services de contenu",
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
        "archiving",
        "electronic archiving",
        "e archiving",
        "e archive",
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
        # FR / PT / ES / AR
        "archivage electronique",
        "sae",
        "gestion des archives",
        "gestao de arquivos",
        "gestion de archivos",
        "الأرشفة الإلكترونية",
        "نظام إدارة السجلات",
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
        # FR / ES / PT / AR
        "automatisation des processus",
        "gestion des processus",
        "tramitacion",
        "tramitación",
        "سير العمل",
    ],
    "Case": [
        "case management",
        "case management system",
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
        "permit management",
        "licensing system",
        "enforcement case",
        "regulatory case",
        # FR / ES / PT / AR
        "gestion des dossiers",
        "gestion de dossiers",
        "gestion des cas",
        "gestion de cas",
        "gestion de expedientes",
        "gestao de processos",
        "gestao de casos",
        "إدارة القضايا",
    ],
    # Helpful but non-core
    "Forms": [
        "electronic forms",
        "e forms",
        "digital forms",
        "form automation",
        "electronic memos",
        "digital correspondence",
        "e filing",
        "electronic filing",
    ],
    "ServiceDelivery": [
        "service request",
        "service requests",
        "citizen services",
        "e services",
        "service delivery",
        "citizen portal",
        "government portal",
        "one stop shop",
        "one-stop shop",
        "single window",
    ],
    "Gov": [
        "e government",
        "digital government",
        "e governance",
        # FR / ES / PT
        "administration publique",
        "sector publico",
        "setor publico",
    ],
    "Digitalization": [
        "digital transformation",
        "digitization",
        "digital first",
        "government modernization",
        "administrative reform",
        "public administration reform",
        "paperless government",
        "knowledge management",
        "dematerialisation",
        "dématérialisation",
        "desmaterializacao",
        "desmaterialização",
    ],
    # Integration & identity (F2-friendly)
    "Integration": [
        "single sign on",
        "sso",
        "identity and access management",
        "iam",
        "active directory",
        "azure ad",
        "ldap",
        "api integration",
        "rest api",
        "web service",
        "email integration",
        "outlook integration",
        "e signature",
        "e-signature",
        "digital signature",
        "electronic signature",
    ],
    # Implementation services (F2-friendly)
    "Implementation": [
        "implementation",
        "configuration",
        "rollout",
        "deployment",
        "migration",
        "data migration",
        "content migration",
        "change management",
        "training",
        "support and maintenance",
        "commissioning",
    ],
    # Pipeline/procurement stages
    "Pipeline": [
        "expression of interest",
        "eoi",
        "request for information",
        "rfi",
        "prior information notice",
        "pin",
        "procurement plan",
        "annual procurement plan",
        "app",
        "prequalification",
        "pre qualification",
    ],
}

ALL_KEYWORDS: List[str] = sorted({kw for kws in KEYWORD_DOMAINS.values() for kw in kws})

# keyword -> [domains]
KEYWORD_TO_DOMAIN: Dict[str, List[str]] = {}
for domain, keywords in KEYWORD_DOMAINS.items():
    for kw in keywords:
        KEYWORD_TO_DOMAIN.setdefault(_normalize_phrase(kw), []).append(domain)

# =============================================================================
# LOCK-IN & PROCUREMENT OPENNESS
# =============================================================================

MICROSOFT_HARD_LOCK_SIGNALS: List[str] = [
    "must use power platform",
    "must use microsoft power platform",
    "solution shall be built on power platform",
    "built on power platform",
    "power apps",
    "power automate",
    "dataverse",
    "must use sharepoint",
    "solution shall be built on sharepoint",
    "built on sharepoint",
    "deploy on sharepoint",
    "sharepoint online",
]

MICROSOFT_SOFT_LOCK_SIGNALS: List[str] = [
    "existing sharepoint",
    "sharepoint environment",
    "already procured microsoft",
    "procured power platform",
    "microsoft enterprise agreement",
    "licenses will be provided",
    "excluding licenses",
    "implementation partner",
    "configuration services",
    "si partner",
]

OPENNESS_SIGNALS: List[str] = [
    "platform agnostic",
    "vendor neutral",
    "technology neutral",
    "or equivalent",
    "alternative solutions",
    "alternative platforms",
    "open procurement",
    "best value",
    "total cost of ownership",
    "tco analysis",
    "fit for purpose",
]

QUALIFICATION_QUESTIONS: List[str] = [
    "Total number of end-users?",
    "Total tender budget (implementation + support)?",
    "Is the buyer open to alternative platforms (e.g., not Microsoft-only)?",
    "Is this a platform decision or SI-only delivery?",
    "Any mandatory hosting / data residency requirements?",
]

# =============================================================================
# NEGATIVE / EXCLUSION SIGNALS (carefully tuned)
# =============================================================================

# Hard-exclude only when core platform signals are absent (prevents false negatives)
CONSTRUCTION_SIGNALS: List[str] = [
    "construction of",
    "civil works",
    "building works",
    "renovation",
    "rehabilitation",
    "road works",
    "water works",
    "sewer",
    "bridge",
]

HARDWARE_SIGNALS: List[str] = [
    "supply of laptops",
    "supply of computers",
    "hardware supply",
    "supply and delivery of",
    "network infrastructure",
    "cabling works",
    "data center",
    "data centre",
    "servers",
    "storage infrastructure",
    "backup appliance",
    "printer",
    "photocopier",
]

MEDICAL_SIGNALS: List[str] = [
    "ehr",
    "emr",
    "electronic medical record",
    "electronic health record",
    "hospital information system",
    "patient records",
]

# “Consulting-only” should NOT be hard-excluded (pipeline shaping), but does reduce platform-likelihood
CONSULTING_SIGNALS: List[str] = [
    "solution architect",
    "enterprise architect",
    "consultant",
    "consultancy",
    "advisory services",
    "strategy development",
    "roadmap",
    "assessment study",
    "feasibility study",
    "maturity assessment",
    "baseline assessment",
]

RENEWAL_SIGNALS: List[str] = [
    "license renewal",
    "licence renewal",
    "renewal of license",
    "renewal of licence",
    "annual support",
    "software assurance",
    "subscription renewal",
    "support renewal",
]

DIGITIZATION_SIGNALS: List[str] = [
    "digitization",
    "digitalization",
    "scanning",
    "scan and archive",
    "scanning and archiving",
    "ocr",
    "imaging",
    "document imaging",
    "intelligent document processing",
    "idp",
]

NEGATIVE_SIGNALS: List[str] = [
    "website design only",
    "social media management",
    "antivirus",
    "email security",
    "mobile app development",
    "hosting services",
    "cloud hosting only",
    "erp system",
    "fleet management",
    "warehouse management",
    "inventory management",
]

# =============================================================================
# OUTPUT SCHEMA (superset of your original; keeps compatibility)
# =============================================================================

OUTPUT_SCHEMA: Dict[str, Any] = {
    "tender_id": "",
    "title": "",
    "source": "",
    "publication_date": "",
    "deadline": "",
    # Compatibility fields:
    "matched_keywords": [],
    "matched_domains": [],
    "score": 0,  # int 0-100
    "priority": "LOW",  # LOW/MEDIUM/HIGH (compat)
    "platform_locked": False,
    "requires_qualification": False,
    "hard_no_go": False,
    "likely_fit_for_f2": "NO",  # NO/CONDITIONAL/YES
    "qualification_questions": [],
    # New, more useful fields:
    "f2_fit": 0.0,  # float 0-1
    "bucket": "IGNORE",  # IGNORE/WATCHLIST/GOOD/HIGH
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
        "core_platform": 0.0,   # 0-0.55
        "governance": 0.0,      # 0-0.20
        "enterprise": 0.0,      # 0-0.10
        "integration": 0.0,     # 0-0.10
        "implementation": 0.0,  # 0-0.05
        "penalties": 0.0,       # 0-0.30 (reported as positive; subtracted from total)
    },
    "matched_phrases": [],     # list[str] (normalized phrases)
    "rationale": [],           # list[str] short explanations
}

# =============================================================================
# INTERNAL SCORING MODEL (F2 rubric)
# =============================================================================

# Governance phrases are a focused subset to avoid overweighting generic "records"
GOVERNANCE_PHRASES: List[str] = [
    "retention schedule",
    "records retention",
    "classification scheme",
    "classification plan",
    "file plan",
    "records disposal",
    "audit trail",
    "audit logging",
    "legal hold",
    "iso 15489",
    "freedom of information",
    "right to information",
    "foia",
    "electronic archiving",
    "archivage electronique",
    "sae",
]

ENTERPRISE_PHRASES: List[str] = [
    "enterprise wide",
    "enterprise-wide",
    "organization wide",
    "organisation wide",
    "ministry wide",
    "ministry-wide",
    "agency wide",
    "agency-wide",
    "shared services",
    "whole of government",
    "whole-of-government",
    "national rollout",
]

INTEGRATION_PHRASES: List[str] = KEYWORD_DOMAINS["Integration"]

IMPLEMENTATION_PHRASES: List[str] = KEYWORD_DOMAINS["Implementation"]

# Core platform components
DOC_PLATFORM_PHRASES: List[str] = KEYWORD_DOMAINS["EDMS"] + KEYWORD_DOMAINS["ECM"]
RECORDS_PLATFORM_PHRASES: List[str] = KEYWORD_DOMAINS["Records"]
WORKFLOW_PHRASES: List[str] = KEYWORD_DOMAINS["Workflow"]
CASE_PHRASES: List[str] = KEYWORD_DOMAINS["Case"]

GOV_CONTEXT_PHRASES: List[str] = KEYWORD_DOMAINS["Gov"]


def _days_between(a: date, b: date) -> int:
    return (b - a).days


def _saturating_score(hit_count: int, max_points: float, k: int = 3) -> float:
    """
    Convert hit_count to [0, max_points] with a smooth saturation curve.
    k ~ how many hits to reach near-max.
    """
    if hit_count <= 0:
        return 0.0
    # Simple saturation: 1 - exp(-n/k)
    # Use a small approximation without importing math.exp for speed + simplicity:
    # exp(-x) approx via pow(2.71828, -x) would require math anyway.
    # We'll use a rational saturation: n/(n+k)
    return max_points * (hit_count / (hit_count + k))


def _domain_hits(text: str) -> Tuple[List[str], List[str], List[str]]:
    """
    Returns:
      matched_keywords: ["DOMAIN:phrase", ...]
      matched_domains: ["EDMS", "Workflow", ...]
      matched_phrases: ["phrase", ...] (flattened)
    """
    matched_keywords: List[str] = []
    matched_domains: List[str] = []
    matched_phrases: List[str] = []

    for domain, phrases in KEYWORD_DOMAINS.items():
        hits = _collect_hits(text, phrases)
        if hits:
            matched_domains.append(domain)
            matched_phrases.extend(hits)
            matched_keywords.extend([f"{domain}:{h}" for h in hits])

    # de-dupe phrases/keywords while keeping order
    def _dedupe_keep_order(items: List[str]) -> List[str]:
        seen = set()
        out: List[str] = []
        for x in items:
            if x not in seen:
                seen.add(x)
                out.append(x)
        return out

    return (
        _dedupe_keep_order(matched_keywords),
        matched_domains,
        _dedupe_keep_order(matched_phrases),
    )


def _detect_platform_lock(text: str) -> Tuple[str, List[str], List[str], List[str]]:
    hard = _collect_hits(text, MICROSOFT_HARD_LOCK_SIGNALS)
    soft = _collect_hits(text, MICROSOFT_SOFT_LOCK_SIGNALS)
    open_ = _collect_hits(text, OPENNESS_SIGNALS)

    if hard:
        return "MICROSOFT_HARD", hard, soft, open_
    if soft:
        return "MICROSOFT_SOFT", hard, soft, open_
    return "NONE", hard, soft, open_


def _detect_opportunity_type(text: str, core_platform_score: float) -> str:
    """
    Classify the nature of the opportunity for business handling.
    """
    renewal_hits = _collect_hits(text, RENEWAL_SIGNALS)
    consulting_hits = _collect_hits(text, CONSULTING_SIGNALS)
    pipeline_hits = _collect_hits(text, KEYWORD_DOMAINS["Pipeline"])

    # Renewal-only (usually not F2-friendly unless it's replacement/upgrade, which should have core signals)
    if renewal_hits and core_platform_score < 0.25 and not _phrase_hit(text, "replacement") and not _phrase_hit(text, "upgrade"):
        return "RENEWAL/SUPPORT_ONLY"

    # Pipeline / planning
    if pipeline_hits and core_platform_score < 0.35:
        return "PIPELINE (RFI/PIN/APP/EOI)"

    # Consulting / architecture (keep, don’t exclude)
    if consulting_hits and core_platform_score < 0.40:
        return "CONSULTING/ARCHITECTURE"

    # If core is strong, it’s typically a platform procurement
    if core_platform_score >= 0.40:
        return "PLATFORM PROCUREMENT (SOFTWARE+IMPLEMENTATION)"

    return "GENERAL / UNCLEAR"


def _obvious_hard_exclude(text: str, core_platform_score: float) -> Tuple[bool, str]:
    """
    Hard exclude ONLY if obviously not a software/platform procurement AND core is weak.
    """
    construction_hits = _collect_hits(text, CONSTRUCTION_SIGNALS, max_hits=3)
    medical_hits = _collect_hits(text, MEDICAL_SIGNALS, max_hits=3)

    if construction_hits and core_platform_score < 0.20:
        return True, f"Construction/civil works focus ({', '.join(construction_hits[:2])})"

    if medical_hits and core_platform_score < 0.25:
        return True, f"Clinical EHR/EMR focus ({', '.join(medical_hits[:2])})"

    return False, ""


def _penalty_model(text: str, core_platform_score: float, platform_lock: str, openness_hits: List[str]) -> Tuple[float, List[str], bool]:
    """
    Returns:
      penalties (0..0.30) as positive number to subtract
      rationale list
      is_pipeline flag suggestion
    """
    penalties = 0.0
    rationale: List[str] = []
    is_pipeline = False

    renewal_hits = _collect_hits(text, RENEWAL_SIGNALS, max_hits=4)
    hardware_hits = _collect_hits(text, HARDWARE_SIGNALS, max_hits=4)
    digit_hits = _collect_hits(text, DIGITIZATION_SIGNALS, max_hits=4)
    consulting_hits = _collect_hits(text, CONSULTING_SIGNALS, max_hits=4)
    negative_hits = _collect_hits(text, NEGATIVE_SIGNALS, max_hits=4)
    pipeline_hits = _collect_hits(text, KEYWORD_DOMAINS["Pipeline"], max_hits=4)

    # Platform lock-in: strong penalty for cBrain F2 if Microsoft-hard and no openness
    if platform_lock == "MICROSOFT_HARD" and not openness_hits:
        penalties += 0.18
        rationale.append("Hard Microsoft platform lock-in signals (Power Platform/SharePoint).")

    elif platform_lock == "MICROSOFT_SOFT" and not openness_hits:
        penalties += 0.08
        rationale.append("Soft Microsoft commitment signals (existing SharePoint/licensing).")

    # Renewal-only: heavy penalty if core weak
    if renewal_hits and core_platform_score < 0.30:
        penalties += 0.22
        rationale.append("Looks like renewal/support-only rather than a new platform procurement.")

    # Hardware: if core weak, treat as very low relevance; otherwise minor penalty (mixed tender)
    if hardware_hits:
        if core_platform_score < 0.25:
            penalties += 0.25
            rationale.append("Hardware-heavy tender and weak platform signals.")
        else:
            penalties += 0.06
            rationale.append("Contains hardware/procurement language; ensure platform scope is primary.")

    # Digitization-only: penalize if no strong platform signals (digitization can still be part of EDMS rollout)
    if digit_hits and core_platform_score < 0.30 and not _phrase_hit(text, "document management"):
        penalties += 0.18
        rationale.append("Digitization/scanning appears without clear EDMS/records platform component.")

    # Consulting: not excluded, but usually pipeline shaping
    if consulting_hits and core_platform_score < 0.40:
        penalties += 0.06
        is_pipeline = True
        rationale.append("Consulting/architecture scope; likely pipeline shaping rather than a platform award.")

    # Pipeline terms: label pipeline if core isn’t strong yet
    if pipeline_hits and core_platform_score < 0.40:
        is_pipeline = True

    # Generic negatives
    if negative_hits:
        penalties += min(0.08, 0.02 * len(negative_hits))
        rationale.append("Contains generic negative signals (may be adjacent/non-core).")

    penalties = min(0.30, penalties)
    return penalties, rationale, is_pipeline


# =============================================================================
# PUBLIC API
# =============================================================================

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
    """
    Main classifier. Returns OUTPUT_SCHEMA-compatible dict + extended fields.

    NOTE: This function does not "fetch" or "scrape" anything.
    It assumes you already have t.title and t.text (notice + doc text where possible).
    """
    today = today or date.today()
    text = _normalize(f"{t.title} {t.text}")

    out = dict(OUTPUT_SCHEMA)
    out["tender_id"] = t.tender_id
    out["title"] = t.title
    out["source"] = t.source
    out["publication_date"] = t.publication_date.isoformat() if t.publication_date else ""
    out["deadline"] = t.deadline.isoformat() if t.deadline else ""

    # --- Timing evaluation (profile-based) ---
    timing = dict(out["timing"])
    timing["missing_deadline"] = t.deadline is None
    timing["missing_publication_date"] = t.publication_date is None

    days_to_deadline: Optional[int] = None
    days_since_pub: Optional[int] = None

    if t.deadline:
        days_to_deadline = _days_between(today, t.deadline)
        timing["days_to_deadline"] = days_to_deadline
    if t.publication_date:
        days_since_pub = _days_between(t.publication_date, today)
        timing["days_since_publication"] = days_since_pub

    # compute domain hits early because timing may allow urgent override based on fit
    matched_keywords, matched_domains, matched_phrases = _domain_hits(text)
    out["matched_keywords"] = matched_keywords
    out["matched_domains"] = matched_domains
    out["matched_phrases"] = matched_phrases

    # --- Core scoring (0..0.55) ---
    doc_hits = _collect_hits(text, DOC_PLATFORM_PHRASES)
    records_hits = _collect_hits(text, RECORDS_PLATFORM_PHRASES)
    workflow_hits = _collect_hits(text, WORKFLOW_PHRASES)
    case_hits = _collect_hits(text, CASE_PHRASES)

    core_doc = _saturating_score(len(doc_hits), 0.20, k=3)
    core_records = _saturating_score(len(records_hits), 0.15, k=3)
    core_workflow = _saturating_score(len(workflow_hits), 0.10, k=3)
    core_case = _saturating_score(len(case_hits), 0.10, k=3)
    core_platform = core_doc + core_records + core_workflow + core_case  # 0..0.55

    # --- Governance (0..0.20) ---
    gov_hits = _collect_hits(text, GOVERNANCE_PHRASES)
    governance = _saturating_score(len(gov_hits), 0.20, k=3)

    # --- Enterprise rollout (0..0.10) ---
    ent_hits = _collect_hits(text, ENTERPRISE_PHRASES)
    enterprise = _saturating_score(len(ent_hits), 0.10, k=2)

    # --- Integration (0..0.10) ---
    integ_hits = _collect_hits(text, INTEGRATION_PHRASES)
    integration = _saturating_score(len(integ_hits), 0.10, k=3)

    # --- Implementation services (0..0.05) ---
    impl_hits = _collect_hits(text, IMPLEMENTATION_PHRASES)
    implementation = _saturating_score(len(impl_hits), 0.05, k=4)

    # --- Public sector context boost (soft) ---
    gov_context_hits = _collect_hits(text, GOV_CONTEXT_PHRASES, max_hits=5)
    has_gov_context = bool(gov_context_hits) or _phrase_hit(text, "government") or _phrase_hit(text, "ministry")

    # Base fit
    base_fit = core_platform + governance + enterprise + integration + implementation  # 0..1.0

    # Apply mild down-weight if not public sector (F2 is strongest there)
    if not has_gov_context:
        base_fit *= 0.85

    # Platform lock & openness
    platform_lock, hard_lock_hits, soft_lock_hits, openness_hits = _detect_platform_lock(text)
    out["platform_locked"] = platform_lock in ("MICROSOFT_HARD", "MICROSOFT_SOFT")
    out["requires_qualification"] = out["platform_locked"]
    if out["requires_qualification"]:
        out["qualification_questions"] = QUALIFICATION_QUESTIONS.copy()

    # Opportunity type + penalties
    opportunity_type = _detect_opportunity_type(text, core_platform)
    penalties, penalty_rationale, is_pipeline_hint = _penalty_model(text, core_platform, platform_lock, openness_hits)

    # Hard exclude only in obvious cases
    hard_exclude, hard_exclude_reason = _obvious_hard_exclude(text, core_platform)
    if hard_exclude:
        out["hard_no_go"] = True
        out["likely_fit_for_f2"] = "NO"
        out["bucket"] = "IGNORE"
        out["priority"] = "LOW"
        out["f2_fit"] = 0.0
        out["score"] = -999
        out["opportunity_type"] = "HARD_EXCLUDED"
        out["rationale"] = [hard_exclude_reason]
        out["timing"] = timing
        return out

    # Final fit (0..1) after penalties
    f2_fit = max(0.0, min(1.0, base_fit - penalties))

    # --- Timing filters (post-fit so urgent override can apply) ---
    excluded_by_timing = False
    timing_reason = ""

    # Publication age
    if t.publication_date:
        if days_since_pub is not None and days_since_pub > profile.max_days_since_publication:
            excluded_by_timing = True
            timing_reason = f"Published {days_since_pub} days ago (> {profile.max_days_since_publication})."
    else:
        if profile.missing_publication_behavior == "exclude":
            excluded_by_timing = True
            timing_reason = "Missing publication date (profile excludes)."
        else:
            f2_fit = max(0.0, f2_fit - profile.missing_publication_penalty)

    # Deadline logic
    is_urgent = False
    if t.deadline:
        # For Africa strict scanning, open-only is typically "deadline >= today"
        if profile.min_days_to_deadline <= 0:
            if days_to_deadline is not None and days_to_deadline < 0:
                excluded_by_timing = True
                timing_reason = "Deadline has passed."
        else:
            if days_to_deadline is not None and days_to_deadline < profile.min_days_to_deadline:
                if profile.allow_urgent_override and f2_fit >= profile.urgent_override_min_fit:
                    is_urgent = True
                else:
                    excluded_by_timing = True
                    timing_reason = f"Deadline too soon ({days_to_deadline} days < {profile.min_days_to_deadline})."
    else:
        if profile.missing_deadline_behavior == "exclude":
            excluded_by_timing = True
            timing_reason = "Missing deadline (profile excludes)."
        elif profile.missing_deadline_behavior == "pipeline":
            is_pipeline_hint = True
            f2_fit = max(0.0, f2_fit - profile.missing_deadline_penalty)
        else:
            f2_fit = max(0.0, f2_fit - profile.missing_deadline_penalty)

    timing["excluded_by_timing"] = excluded_by_timing
    timing["timing_reason"] = timing_reason
    out["timing"] = timing
    out["is_urgent"] = is_urgent

    # If excluded by timing, mark hard_no_go (for inclusion filters) but still return scored object.
    if excluded_by_timing:
        out["hard_no_go"] = True

    # Bucket thresholds (aligned to the “refined prompt” logic)
    if f2_fit >= 0.80:
        bucket = "HIGH"
    elif f2_fit >= 0.75:
        bucket = "GOOD"
    elif f2_fit >= 0.70:
        bucket = "WATCHLIST"
    else:
        bucket = "IGNORE"
    out["bucket"] = bucket

    # Compatibility "priority"
    if bucket in ("HIGH", "GOOD"):
        out["priority"] = "HIGH"
    elif bucket == "WATCHLIST":
        out["priority"] = "MEDIUM"
    else:
        out["priority"] = "LOW"

    # Gate: require meaningful core platform need (prevents governance-only false positives)
    core_gate_ok = core_platform >= 0.35

    # likely_fit_for_f2 logic (platform lock aware)
    if out["hard_no_go"]:
        likely = "NO"
    elif platform_lock == "MICROSOFT_HARD" and not openness_hits:
        likely = "NO"
    elif bucket == "HIGH" and core_gate_ok:
        likely = "YES"
    elif bucket in ("GOOD", "WATCHLIST") and core_gate_ok:
        likely = "CONDITIONAL"
    else:
        likely = "NO"
    out["likely_fit_for_f2"] = likely

    # Pipeline flag:
    # - if profile says pipeline for missing deadline
    # - or we saw pipeline terms / consulting shaping and core not strong
    out["is_pipeline"] = bool(is_pipeline_hint)

    # Populate rationale (short, actionable)
    rationale: List[str] = []

    # Why it matches
    if core_gate_ok:
        # Pick 2-4 strongest phrases as "matched highlights"
        highlights: List[str] = []
        for grp in (doc_hits, records_hits, workflow_hits, case_hits, gov_hits):
            for h in grp:
                if h not in highlights:
                    highlights.append(h)
                if len(highlights) >= 4:
                    break
            if len(highlights) >= 4:
                break
        if highlights:
            rationale.append("Core platform signals: " + "; ".join(highlights[:4]) + ".")

    if gov_hits:
        rationale.append("Governance/compliance signals detected (retention/audit/archiving).")
    if enterprise > 0:
        rationale.append("Enterprise rollout signals present.")
    if integration > 0:
        rationale.append("Integration/identity signals present (SSO/IAM/APIs/email/e-sign).")

    # Platform lock explanation
    if platform_lock == "MICROSOFT_HARD":
        rationale.append("Hard Microsoft lock-in indicators detected.")
    elif platform_lock == "MICROSOFT_SOFT":
        rationale.append("Soft Microsoft commitment indicators detected.")
    if openness_hits:
        rationale.append("Openness signals present (technology neutral / or equivalent).")

    # Penalty rationale
    rationale.extend(penalty_rationale)

    # Timing notes
    if is_urgent:
        rationale.append("URGENT: deadline is soon but fit is very high (kept by override).")
    if out["is_pipeline"]:
        rationale.append("PIPELINE: likely early-stage (RFI/PIN/APP/architecture).")

    out["rationale"] = rationale

    # Matched keywords enrichment (lock/open/neg tags)
    # (keeps a similar shape to your original module’s extra tags)
    if hard_lock_hits:
        out["matched_keywords"].extend([f"MS_HARD_LOCK:{h}" for h in hard_lock_hits])
    if soft_lock_hits:
        out["matched_keywords"].extend([f"MS_SOFT_LOCK:{h}" for h in soft_lock_hits])
    if openness_hits:
        out["matched_keywords"].extend([f"OPENNESS:{h}" for h in openness_hits])

    # Negative tags
    neg_hits = _collect_hits(text, NEGATIVE_SIGNALS, max_hits=6)
    if neg_hits:
        out["matched_keywords"].extend([f"NEG:{h}" for h in neg_hits])

    # Final score fields
    out["f2_fit"] = float(round(f2_fit, 4))
    out["score"] = int(round(f2_fit * 100))
    out["opportunity_type"] = opportunity_type

    # Subscores
    out["subscores"] = {
        "core_platform": float(round(core_platform, 4)),
        "governance": float(round(governance, 4)),
        "enterprise": float(round(enterprise, 4)),
        "integration": float(round(integration, 4)),
        "implementation": float(round(implementation, 4)),
        "penalties": float(round(penalties, 4)),
    }

    return out
