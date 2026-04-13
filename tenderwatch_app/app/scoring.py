"""
TenderWatch Scoring — F2-Optimized (STRICT)
=============================================
Strict, high-precision scoring for actual cBrain F2 tender opportunities.

Scoring Logic:
- +3 per PRIMARY domain hit (EDMS, Case, Workflow, Records)
- +2 per SECONDARY domain hit (Gov, ECM, Forms, ServiceDelivery)
- MINIMUM 2 domain hits required for score > 0
- BONUS +5 for Pipeline phrases (explicit RFP + F2 keyword)
- BONUS +4 for multi-domain combinations in same section
- -3 each irrelevant signal (construction, hardware, etc.)
- HARD DISCARD if score < 10 (too generic)

Result: ACTUAL F2 opportunities only
- No random "digital government" without domain specificity
- No construction/hardware/medical tenders
- No authentication/security-only solutions
- Higher recall = better, but ONLY if relevant
"""

import json
import re
import app.keywords as kw
from app.geography import enrich_scoring_with_geography

# Compatibility bridge
ALL_KEYWORDS = getattr(kw, "ALL_KEYWORDS", [])
KEYWORD_DOMAINS = getattr(kw, "KEYWORD_DOMAINS", {})
KEYWORD_TO_DOMAIN = getattr(kw, "KEYWORD_TO_DOMAIN", {})
NEGATIVE_SIGNALS = getattr(kw, "NEGATIVE_SIGNALS", [])
GENERIC_STANDALONE_KEYWORDS = getattr(kw, "GENERIC_STANDALONE_KEYWORDS", [])

# Primary domains = core to F2
PRIMARY_DOMAINS = {"EDMS", "Case", "Workflow", "Records", "ECM"}
# Secondary domains = supporting/contextual
SECONDARY_DOMAINS = {"Gov", "Forms", "ServiceDelivery"}

IRRELEVANT_SIGNALS = getattr(
    kw,
    "IRRELEVANT_SIGNALS",
    list(
        dict.fromkeys(
            getattr(kw, "CONSTRUCTION_SIGNALS", [])
            + getattr(kw, "HARDWARE_SIGNALS", [])
            + getattr(kw, "MEDICAL_SIGNALS", [])
            + [
                "email security",
                "vpn",
                "network security",
                "firewall",
                "antivirus",
                "password manager",
                "authentication system",
                "two factor auth",
                "hotel booking",
                "travel booking",
                "airlines",
                "aviation",
                "construction materials",
                "civil works",
                "building materials",
            ]
        )
    ),
)

PIPELINE_PHRASES = getattr(
    kw,
    "PRIORITY_PHRASES",
    [
        "document management rfp",
        "records management rfp",
        "workflow automation rfp",
        "case management rfp",
        "enterprise content management rfp",
        "document management system tender",
        "records management system tender",
        "digital transformation platform",
        "citizen services platform",
    ],
)


def _normalize(text: str) -> str:
    """Normalize text for matching."""
    _norm = getattr(kw, "_normalize", None)
    if callable(_norm):
        result = _norm(text)
        return str(result) if result else ""
    return text.lower() if text else ""


def _phrase_in_text(phrase: str, text: str) -> bool:
    """Check if phrase appears in text (case-insensitive, word boundary)."""
    if not phrase or not text:
        return False
    norm_phrase = _normalize(phrase)
    norm_text = _normalize(text)
    pattern = r"\b" + re.escape(norm_phrase) + r"\b"
    return bool(re.search(pattern, norm_text))


def score_text(title: str, text: str = ""):
    """
    Score text with STRICT F2 relevance logic.
    
    Returns: (score, matched_keywords_str, breakdown_json)
    
    HARD FILTER: score < 10 = NOT relevant
    Score 10-40 = weak relevance
    Score 40-70 = moderate relevance  
    Score 70+ = strong relevance
    """
    combined = f"{title} {text}"
    combined_norm = _normalize(combined)
    
    breakdown = {
        "primary_hits": [],
        "secondary_hits": [],
        "pipeline_hits": [],
        "irrelevant_signals": [],
        "total_score": 0,
        "relevance_level": "LOW",
    }
    
    # Check irrelevant signals first
    for signal in IRRELEVANT_SIGNALS:
        if _phrase_in_text(signal, combined):
            breakdown["irrelevant_signals"].append(signal)
    
    # Hard discard if irrelevant signals found
    if breakdown["irrelevant_signals"]:
        return 0, "", json.dumps(breakdown)
    
    # Score primary domains
    primary_score = 0
    for domain in PRIMARY_DOMAINS:
        keywords = KEYWORD_DOMAINS.get(domain, [])
        for kw in keywords:
            if _phrase_in_text(kw, combined):
                primary_score += 3
                if kw not in breakdown["primary_hits"]:
                    breakdown["primary_hits"].append(kw)
    
    # Score secondary domains
    secondary_score = 0
    for domain in SECONDARY_DOMAINS:
        keywords = KEYWORD_DOMAINS.get(domain, [])
        for kw in keywords:
            if _phrase_in_text(kw, combined):
                secondary_score += 2
                if kw not in breakdown["secondary_hits"]:
                    breakdown["secondary_hits"].append(kw)
    
    # Check pipeline phrases (explicit procurement intent)
    pipeline_score = 0
    for phrase in PIPELINE_PHRASES:
        if _phrase_in_text(phrase, combined):
            pipeline_score += 5
            if phrase not in breakdown["pipeline_hits"]:
                breakdown["pipeline_hits"].append(phrase)
    
    # Multi-domain bonus
    domain_combo_bonus = 0
    num_primary = len(breakdown["primary_hits"])
    num_secondary = len(breakdown["secondary_hits"])
    if num_primary >= 2:
        domain_combo_bonus = 4
    elif num_primary >= 1 and num_secondary >= 1:
        domain_combo_bonus = 3
    
    # Calculate total
    total_score = primary_score + secondary_score + pipeline_score + domain_combo_bonus
    
    # HARD FILTER: require at least primary domain hit
    if num_primary == 0:
        return 0, "", json.dumps(breakdown)
    
    # Determine relevance level
    if total_score >= 70:
        relevance_level = "HIGH"
    elif total_score >= 40:
        relevance_level = "MEDIUM"
    else:
        relevance_level = "LOW"
    
    breakdown["total_score"] = total_score
    breakdown["relevance_level"] = relevance_level
    
    # Format matched keywords string
    all_matched = (
        breakdown["primary_hits"] + breakdown["secondary_hits"] + breakdown["pipeline_hits"]
    )
    matched_str = ", ".join(all_matched[:5])  # Top 5
    
    # Normalize to 0-100 range
    normalized = min(100, max(10, total_score * 1.5))
    
    return int(normalized), matched_str, json.dumps(breakdown)

    irrelevant_found = []
    for signal in IRRELEVANT_SIGNALS:
        sig = (signal or "").strip()
        if not sig:
            continue
        needle = sig.lower()
        if callable(_norm_phrase):
            try:
                needle = _norm_phrase(sig)
            except Exception:
                needle = sig.lower()
        if needle and needle in combined:
            irrelevant_found.append(signal)
    
    # If irrelevant signals found AND no core F2 keywords, return 0
    # Core F2 keywords that override irrelevant signals
    core_f2_terms = [
        # EDMS & Records
        "document management", "records management", "edms", "edrms", "ecm",
        "electronic document", "electronic records", "digital records",
        "document repository", "file registry", "archives management",
        # Case & Workflow
        "case management", "case handling", "case tracking",
        "workflow", "workflow automation", "process automation", "bpm",
        "complaint management", "grievance", "docket",
        # Digitalization & Government
        "paperless", "paperless office", "paperless government",
        "digital transformation", "digitalization", "digitalisation",
        "e-government", "egovernment", "e-governance", "digital government",
        "government modernization", "public sector reform",
        # Service Delivery
        "citizen portal", "e-services", "service delivery platform",
        "one-stop-shop", "citizen services",
    ]
    def _needle(s: str) -> str:
        s = (s or "").strip()
        if not s:
            return ""
        if callable(_norm_phrase):
            try:
                return _norm_phrase(s)
            except Exception:
                return s.lower()
        return s.lower()

    has_core_f2_term = any(_needle(term) in combined for term in core_f2_terms)
    
    # If irrelevant signals found AND no core F2 terms, hard-exclude.
    if irrelevant_found and not has_core_f2_term:
        return 0, "", json.dumps({
            "keywords_found": 0,
            "domains_matched": [],
            "irrelevant_signals": irrelevant_found,
            "excluded": True,
            "exclusion_reason": f"Irrelevant tender: {irrelevant_found[0]}",
            "priority": "EXCLUDED",
            "likely_fit_for_F2": "excluded",
            "procurement_status": "excluded",
        })
    
    # ==========================================================================
    # STEP 1: Find all keyword matches
    # ==========================================================================
    # ======================================================================
    # STEP 1: Find all keyword/domain matches
    # ======================================================================
    matched_keywords = []
    matched_domains = set()

    # Prefer the more robust matcher from app.keywords (handles boundaries + normalization).
    _domain_hits = getattr(kw, "_domain_hits", None)
    if callable(_domain_hits):
        try:
            matched_kw, domains, phrases = _domain_hits(combined)
            matched_domains.update(domains or [])
            # phrases are normalized; keep a short list for display
            matched_keywords = list(phrases or [])
        except Exception:
            matched_keywords = []
            matched_domains = set()
    else:
        # Fallback (legacy): simple substring matching.
        for k in ALL_KEYWORDS:
            if k and k in combined:
                matched_keywords.append(k)
                key = k
                # KEYWORD_TO_DOMAIN keys are typically normalized; try both.
                if hasattr(kw, "_normalize_phrase"):
                    try:
                        key = kw._normalize_phrase(k)
                    except Exception:
                        key = k
                for domain in (KEYWORD_TO_DOMAIN.get(key) or KEYWORD_TO_DOMAIN.get(k) or []):
                    matched_domains.add(domain)
    
    # No matches = still include but with minimal score (downstream gates may filter out)
    if not matched_keywords:
        return 5, "", json.dumps({
            "keywords_found": 0,
            "domains_matched": [],
            "base_score": 0,
            "domain_bonus": 0,
            "negative_penalty": 0,
            "final_score": 5,
            "priority": "LOW",
            "likely_fit_for_F2": "uncertain"
        })
    
    # ==========================================================================
    # STEP 2: Base score (+1 per keyword hit)
    # ==========================================================================
    # De-dupe while keeping order
    seen = set()
    unique_keywords = []
    for k in matched_keywords:
        if k not in seen:
            seen.add(k)
            unique_keywords.append(k)

    base_score = len(unique_keywords)
    
    # ==========================================================================
    # STEP 3: Domain combination bonuses
    # ==========================================================================
    domain_bonus = 0
    priority_level = "LOW"
    
    for combo in PRIORITY_COMBINATIONS:
        # Backward-compatible parsing:
        # - (domains, bonus, priority)
        # - (domains, priority)
        combo_domains = []
        bonus = 0
        priority = "LOW"
        if isinstance(combo, (list, tuple)):
            if len(combo) == 3:
                combo_domains, bonus, priority = combo
            elif len(combo) == 2:
                combo_domains, priority = combo
                bonus = 6 if priority == "HIGH" else 3 if priority == "MEDIUM" else 1
            else:
                continue
        else:
            continue

        if all(d in matched_domains for d in combo_domains):
            domain_bonus = max(domain_bonus, bonus)
            if priority == "HIGH":
                priority_level = "HIGH"
            elif priority == "MEDIUM" and priority_level != "HIGH":
                priority_level = "MEDIUM"
    
    # Additional +2 if multiple domains in same text
    if len(matched_domains) >= 2:
        domain_bonus += 2
    
    # Additional +2 for government/public-sector context
    if "Gov" in matched_domains:
        domain_bonus += 2
    
    # ==========================================================================
    # STEP 4: Priority phrase bonus
    # ==========================================================================
    priority_bonus = 0
    priority_phrases_found = []
    
    for phrase in PRIORITY_PHRASES:
        p = (phrase or "").strip()
        if not p:
            continue
        needle = p.lower()
        if callable(_norm_phrase):
            try:
                needle = _norm_phrase(p)
            except Exception:
                needle = p.lower()
        if needle and needle in combined:
            priority_phrases_found.append(phrase)
            word_count = len(phrase.split())
            if word_count >= 5:
                priority_bonus += 5
            elif word_count >= 4:
                priority_bonus += 3
            else:
                priority_bonus += 2
    
    # ==========================================================================
    # STEP 5: Negative signals (-2 if purely storage/hosting/website)
    # ==========================================================================
    negative_penalty = 0
    negative_signals_found = []
    
    for neg in NEGATIVE_SIGNALS:
        n = (neg or "").strip()
        if not n:
            continue
        needle = n.lower()
        if callable(_norm_phrase):
            try:
                needle = _norm_phrase(n)
            except Exception:
                needle = n.lower()
        if needle and needle in combined:
            negative_signals_found.append(neg)
    
    # Only penalize if ONLY negative signals (no positive workflow/case/records)
    core_domains = {"EDMS", "Records", "Workflow", "Case", "ECM", "Forms", "ServiceDelivery"}
    has_core_match = bool(matched_domains & core_domains)
    
    if negative_signals_found and not has_core_match:
        negative_penalty = -2 * len(negative_signals_found)
    
    # ==========================================================================
    # STEP 5b: Platform commitment detection (Microsoft-mandated = SI-only)
    # ==========================================================================
    # General platform lock-in signals
    platform_lockin_found = []
    for signal in PLATFORM_LOCKIN_SIGNALS:
        s = (signal or "").strip()
        if not s:
            continue
        needle = s.lower()
        if callable(_norm_phrase):
            try:
                needle = _norm_phrase(s)
            except Exception:
                needle = s.lower()
        if needle and needle in combined:
            platform_lockin_found.append(signal)
    
    # STRONGER: Microsoft platform commitment signals (SI-only engagement)
    microsoft_commitment_found = []
    for signal in MICROSOFT_COMMITMENT_SIGNALS:
        s = (signal or "").strip()
        if not s:
            continue
        needle = s.lower()
        if callable(_norm_phrase):
            try:
                needle = _norm_phrase(s)
            except Exception:
                needle = s.lower()
        if needle and needle in combined:
            microsoft_commitment_found.append(signal)
    
    # Open procurement signals
    open_procurement_found = []
    for signal in OPEN_PROCUREMENT_SIGNALS:
        s = (signal or "").strip()
        if not s:
            continue
        needle = s.lower()
        if callable(_norm_phrase):
            try:
                needle = _norm_phrase(s)
            except Exception:
                needle = s.lower()
        if needle and needle in combined:
            open_procurement_found.append(signal)
    
    # Platform openness signals (buyer may consider alternatives)
    platform_openness_found = []
    for signal in PLATFORM_OPENNESS_SIGNALS:
        s = (signal or "").strip()
        if not s:
            continue
        needle = s.lower()
        if callable(_norm_phrase):
            try:
                needle = _norm_phrase(s)
            except Exception:
                needle = s.lower()
        if needle and needle in combined:
            platform_openness_found.append(signal)
    
    # ==========================================================================
    # STEP 5c: Determine procurement status and classification
    # ==========================================================================
    procurement_status = "open"  # Default: assume open procurement
    requires_qualification = False
    qualification_reason = ""
    
    # Combined openness signals (either open procurement OR platform openness)
    has_openness_signals = bool(open_procurement_found or platform_openness_found)
    
    # Check for Microsoft platform commitment (STRONGEST lock-in)
    if microsoft_commitment_found:
        requires_qualification = True
        
        if platform_openness_found:
            # Microsoft mandated BUT buyer signals openness to alternatives
            # This is HIGH STRATEGIC VALUE - position F2 as alternative
            procurement_status = "conditional_strategic"
            qualification_reason = "Microsoft mandated but buyer may be open to alternatives - HIGH STRATEGIC VALUE"
            negative_penalty -= 5  # Moderate penalty, but worth pursuing
        elif open_procurement_found:
            # Microsoft mentioned but this is clearly an open tender (provision of, RFP, etc.)
            # Worth discussing - may just be integration requirement
            procurement_status = "conditional_discuss"
            qualification_reason = "Microsoft environment mentioned in open tender - clarify if platform is mandated"
            negative_penalty -= 3  # Slight penalty
            requires_qualification = False  # Don't require full qualification for open tenders
        else:
            # Microsoft mandated, no openness signals
            # CONDITIONAL / NO-GO - require qualification before pursuit
            procurement_status = "conditional_nogo"
            qualification_reason = "Microsoft platform mandated - SI-only engagement unless buyer is open to alternatives"
            negative_penalty -= 15  # Strong penalty
    
    # Check for general platform lock-in (weaker than Microsoft commitment)
    elif platform_lockin_found:
        if has_openness_signals:
            # Mixed signals - client may be open to alternatives
            procurement_status = "locked_but_open"
            qualification_reason = "Platform mentioned but procurement appears open"
            negative_penalty -= 3  # Slight penalty but still viable
        else:
            # Strong lock-in signal - F2 unlikely to compete
            procurement_status = "locked"
            qualification_reason = "Vendor/platform already chosen"
            negative_penalty -= 10  # Significant penalty
    
    # Check if explicitly open procurement
    elif has_openness_signals:
        procurement_status = "open"
        qualification_reason = ""
    
    # ==========================================================================
    # STEP 6: Calculate final score
    # ==========================================================================
    raw_score = base_score + domain_bonus + priority_bonus + negative_penalty
    raw_score = max(5, raw_score)  # Minimum score of 5 (never hard-reject)
    
    # Normalize to 5-100 scale (for UI display)
    # Expected range: 1-30 points → 5-100%
    normalized_score = ((raw_score - 1) / 29) * 95 + 5
    normalized_score = min(100, max(5, round(normalized_score, 1)))
    
    # ==========================================================================
    # STEP 7: Determine F2 fit likelihood and priority
    # ==========================================================================
    # Consider platform commitment when determining F2 fit
    
    if procurement_status == "conditional_nogo":
        # Microsoft mandated, no openness signals → CONDITIONAL / NO-GO
        likely_fit = "conditional"
        priority_level = "CONDITIONAL"
    elif procurement_status == "conditional_strategic":
        # Microsoft mandated BUT buyer may be open → HIGH STRATEGIC VALUE
        likely_fit = "strategic"
        priority_level = "STRATEGIC"
    elif procurement_status == "conditional_discuss":
        # Microsoft mentioned in open tender → clarify but proceed
        likely_fit = "discuss"
        # Keep original priority_level, don't override
    elif procurement_status == "locked":
        # Other vendor locked in → NO-GO
        likely_fit = "no-go"
        priority_level = "LOCKED"
    elif procurement_status == "locked_but_open":
        # Platform mentioned but open procurement → DISCUSS
        likely_fit = "discuss"
    elif priority_level == "HIGH" or normalized_score >= 60:
        likely_fit = "true"
    elif priority_level == "MEDIUM" or normalized_score >= 30:
        likely_fit = "uncertain"
    else:
        likely_fit = "uncertain"  # Never false - let humans decide
    
    # ==========================================================================
    # BUILD OUTPUT
    # ==========================================================================
    # Keep user-facing keywords stable: keep order from matching rather than alpha sort.
    unique_keywords = unique_keywords
    
    breakdown = {
        "keywords_found": len(unique_keywords),
        "total_keywords_in_system": len(ALL_KEYWORDS),
        "matched_keywords": unique_keywords[:20],  # Limit for display
        "domains_matched": sorted(matched_domains),
        "priority_phrases_matched": priority_phrases_found,
        "negative_signals_found": negative_signals_found,
        # Platform commitment analysis
        "platform_lockin_signals": platform_lockin_found,
        "microsoft_commitment_signals": microsoft_commitment_found,
        "open_procurement_signals": open_procurement_found,
        "platform_openness_signals": platform_openness_found,
        "procurement_status": procurement_status,
        "requires_qualification": requires_qualification,
        "qualification_reason": qualification_reason,
        # Qualification questions (only if requires_qualification)
        "qualification_questions": QUALIFICATION_QUESTIONS if requires_qualification else [],
        # Scoring
        "base_score": base_score,
        "domain_bonus": domain_bonus,
        "priority_bonus": priority_bonus,
        "negative_penalty": negative_penalty,
        "raw_score": raw_score,
        "normalized_score": normalized_score,
        "match_percentage": normalized_score,
        "final_score": normalized_score,
        "priority": priority_level,
        "likely_fit_for_F2": likely_fit,
    }
    
    # Format matched keywords for display
    keywords_display = ", ".join(unique_keywords[:15])
    if len(unique_keywords) > 15:
        keywords_display += f" (+{len(unique_keywords) - 15} more)"
    
    return normalized_score, keywords_display, json.dumps(breakdown)


def score_tender(
    title: str,
    text: str = "",
    *,
    buyer: str = "",
    country: str = "",
    source_name: str = "",
    source_url: str = "",
    source_group: str = "",
    source_tags=None,
    pipeline_mode: str = "africa_priority",
    settings=None,
):
    base_score, matched_str, breakdown_json = score_text(title, text)
    try:
        breakdown = json.loads(breakdown_json)
    except Exception:
        breakdown = {}

    ranking_score, breakdown = enrich_scoring_with_geography(
        base_score=base_score,
        breakdown=breakdown,
        title=title,
        text=text,
        buyer=buyer,
        country=country,
        source_name=source_name,
        source_url=source_url,
        source_group=source_group,
        source_tags=source_tags,
        pipeline_mode=pipeline_mode,
        settings=settings,
    )
    breakdown["final_score"] = ranking_score
    return base_score, matched_str, json.dumps(breakdown), ranking_score


def classify_tender(title: str, text: str = ""):
    """
    Classify a tender with full F2 alignment output.
    
    Returns dict with:
    - matched_keywords
    - relevance_score (loose)
    - inferred_domains (EDMS, Workflow, Case, Gov)
    - likely_fit_for_F2 = true/false/uncertain
    - priority = HIGH/MEDIUM/LOW
    """
    score, matched_str, breakdown_json = score_text(title, text)
    breakdown = json.loads(breakdown_json)
    
    return {
        "relevance_score": score,
        "matched_keywords": breakdown.get("matched_keywords", []),
        "inferred_domains": breakdown.get("domains_matched", []),
        "priority": breakdown.get("priority", "LOW"),
        "likely_fit_for_F2": breakdown.get("likely_fit_for_F2", "uncertain"),
        "breakdown": breakdown,
    }
