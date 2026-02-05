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

Design Principles:
- Do NOT hard-reject based on score
- Use score only for ranking
- Favor recall over precision
- Let humans or downstream models decide final fit
"""

import json
from app.keywords import (
    ALL_KEYWORDS, 
    KEYWORD_DOMAINS, 
    KEYWORD_TO_DOMAIN,
    PRIORITY_COMBINATIONS,
    NEGATIVE_SIGNALS,
    PRIORITY_PHRASES,
    GENERIC_STANDALONE_KEYWORDS,
)


def score_text(title: str, text: str = ""):
    """
    Score text based on F2-aligned loose keyword matching.
    
    Returns: (score, matched_keywords_str, breakdown_json)
    
    Score is a relevance ranking (not a filter).
    Any keyword hit is a signal. Multiple hits increase relevance.
    """
    combined = f"{title} {text}".lower()
    
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
    # STEP 6: Calculate final score
    # ==========================================================================
    raw_score = base_score + domain_bonus + priority_bonus + negative_penalty
    raw_score = max(5, raw_score)  # Minimum score of 5 (never hard-reject)
    
    # Normalize to 5-100 scale (for UI display)
    # Expected range: 1-30 points → 5-100%
    normalized_score = ((raw_score - 1) / 29) * 95 + 5
    normalized_score = min(100, max(5, round(normalized_score, 1)))
    
    # ==========================================================================
    # STEP 7: Determine F2 fit likelihood
    # ==========================================================================
    if priority_level == "HIGH" or normalized_score >= 60:
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
