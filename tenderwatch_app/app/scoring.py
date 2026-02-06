"""
TenderWatch Scoring — F2-Aligned (Non-Strict)
==============================================
Loose, non-blocking scoring for cBrain F2 relevance.

Scoring Logic:
- +1 per keyword hit
- +2 if multiple domains appear in same section/paragraph
- +2 if workflow OR case language appears near records language
- +2 if government/public-sector context appears
- -2 if tender is purely storage, hosting, or website-only

Platform Commitment Logic:
- Detect Microsoft-mandated tenders (SI-only engagements)
- Flag as CONDITIONAL / NO-GO but don't auto-discard
- Surface qualification questions for strategic review
- HIGH STRATEGIC VALUE if buyer is open to alternatives

Design Principles:
- Do NOT hard-reject based on score
- Use score only for ranking
- Favor recall over precision
- Let humans or downstream models decide final fit
- EXCEPT: Exclude clearly irrelevant tenders (construction, email security, etc.)
"""

import json
from app.keywords import (
    ALL_KEYWORDS, 
    KEYWORD_DOMAINS, 
    KEYWORD_TO_DOMAIN,
    PRIORITY_COMBINATIONS,
    NEGATIVE_SIGNALS,
    IRRELEVANT_SIGNALS,
    PRIORITY_PHRASES,
    GENERIC_STANDALONE_KEYWORDS,
    PLATFORM_LOCKIN_SIGNALS,
    OPEN_PROCUREMENT_SIGNALS,
    MICROSOFT_COMMITMENT_SIGNALS,
    PLATFORM_OPENNESS_SIGNALS,
    QUALIFICATION_QUESTIONS,
)


def score_text(title: str, text: str = ""):
    """
    Score text based on F2-aligned loose keyword matching.
    
    Returns: (score, matched_keywords_str, breakdown_json)
    
    Score is a relevance ranking (not a filter).
    Any keyword hit is a signal. Multiple hits increase relevance.
    Irrelevant tenders (construction, email security, etc.) return score=0.
    """
    combined = f"{title} {text}".lower()
    
    # ==========================================================================
    # STEP 0: Check for irrelevant signals (EXCLUDE these tenders)
    # ==========================================================================
    irrelevant_found = []
    for signal in IRRELEVANT_SIGNALS:
        if signal.lower() in combined:
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
    has_core_f2_term = any(term in combined for term in core_f2_terms)
    
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
    
        # STRICT F2-ONLY FILTER: Require at least one core F2 keyword, always exclude if not present
        if not has_core_f2_term:
            return 0, "", json.dumps({
                "keywords_found": 0,
                "domains_matched": [],
                "irrelevant_signals": irrelevant_found,
                "excluded": True,
                "exclusion_reason": "No F2 core keyword present",
                "priority": "EXCLUDED",
                "likely_fit_for_F2": "excluded",
                "procurement_status": "excluded",
            })
    
        # If irrelevant signals found, always exclude (even if F2 term present)
        if irrelevant_found:
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
    matched_keywords = []
    matched_domains = set()
    
    for kw in ALL_KEYWORDS:
        if kw in combined:
            matched_keywords.append(kw)
            # Track which domains matched
            if kw in KEYWORD_TO_DOMAIN:
                for domain in KEYWORD_TO_DOMAIN[kw]:
                    matched_domains.add(domain)
    
    # No matches = still include but with minimal score
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
    base_score = len(matched_keywords)
    
    # ==========================================================================
    # STEP 3: Domain combination bonuses
    # ==========================================================================
    domain_bonus = 0
    priority_level = "LOW"
    
    for combo_domains, bonus, priority in PRIORITY_COMBINATIONS:
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
        if phrase.lower() in combined:
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
        if neg.lower() in combined:
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
        if signal.lower() in combined:
            platform_lockin_found.append(signal)
    
    # STRONGER: Microsoft platform commitment signals (SI-only engagement)
    microsoft_commitment_found = []
    for signal in MICROSOFT_COMMITMENT_SIGNALS:
        if signal.lower() in combined:
            microsoft_commitment_found.append(signal)
    
    # Open procurement signals
    open_procurement_found = []
    for signal in OPEN_PROCUREMENT_SIGNALS:
        if signal.lower() in combined:
            open_procurement_found.append(signal)
    
    # Platform openness signals (buyer may consider alternatives)
    platform_openness_found = []
    for signal in PLATFORM_OPENNESS_SIGNALS:
        if signal.lower() in combined:
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
    unique_keywords = sorted(set(matched_keywords))
    
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
        "priority": priority_level,
        "likely_fit_for_F2": likely_fit,
    }
    
    # Format matched keywords for display
    keywords_display = ", ".join(unique_keywords[:15])
    if len(unique_keywords) > 15:
        keywords_display += f" (+{len(unique_keywords) - 15} more)"
    
    return normalized_score, keywords_display, json.dumps(breakdown)


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
