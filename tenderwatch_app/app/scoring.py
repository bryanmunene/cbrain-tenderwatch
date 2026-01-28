from app.keywords import ALL_KEYWORDS, KEYWORD_GROUPS
import json

# Generic keywords to exclude from scoring (too broad)
GENERIC_KEYWORDS = {
    "bid", "tender", "procurement", "rfp", "rfq", 
    "invitation to bid", "request for proposal", "request for quotation",
    "notice", "opportunity", "contract", "service", "services",
    "system", "software", "platform", "solution"
}

def score_text(title: str, text: str = ""):
    """
    Score text based on keyword matching with strict quality requirements.
    Returns: (score, matched_keywords, breakdown_dict)
    Scoring: Requires specific multi-word keywords, excludes generic terms
    """
    combined = f"{title} {text}".lower()
    matched = [kw for kw in ALL_KEYWORDS if kw in combined]

    if not matched:
        return 0, "", {"keywords_found": 0, "total_keywords": len(ALL_KEYWORDS), "match_percentage": 0}

    # Filter out generic keywords
    specific_matched = [kw for kw in matched if kw not in GENERIC_KEYWORDS]
    
    # STRICT REQUIREMENT: Must have at least one specific multi-word keyword (3+ words)
    multi_word_matches = [kw for kw in specific_matched if len(kw.split()) >= 3]
    
    if not multi_word_matches:
        # No specific multi-word keywords = not relevant
        return 0, "", {"keywords_found": 0, "reason": "No specific keywords matched", "match_percentage": 0}
    
    unique_matched = sorted(set(specific_matched))
    
    # Score calculation: heavily favor multi-word specific keywords
    score = 0
    
    for kw in unique_matched:
        word_count = len(kw.split())
        if word_count >= 3:
            score += word_count * 3  # 3+ words: 9+ points each
        elif word_count == 2:
            score += word_count * 2  # 2 words: 4 points each
        else:
            score += 1  # Single word: 1 point (minimal)
    
    # Normalize: Expect 10-30 points for relevant tenders, scale to 5-100%
    # min_expected = 10 points = 5%
    # max_expected = 40 points = 100%
    normalized_score = ((score - 10) / (40 - 10)) * 95 + 5
    normalized_score = min(100, max(5, round(normalized_score, 2)))
    
    # Determine which groups matched
    matched_groups = []
    for group_name, keywords in KEYWORD_GROUPS.items():
        group_keywords = [kw.lower() for kw in keywords]
        matched_in_group = [kw for kw in group_keywords if kw in combined]
        if matched_in_group:
            matched_groups.append({
                "group": group_name,
                "keywords": matched_in_group,
                "count": len(matched_in_group)
            })
    
    breakdown = {
        "total_keywords_in_system": len(ALL_KEYWORDS),
        "keywords_found": len(unique_matched),
        "unique_keywords": unique_matched,
        "match_percentage": score,
        "matched_groups": matched_groups,
        "score": score
    }
    
    return score, ", ".join(unique_matched), json.dumps(breakdown)
