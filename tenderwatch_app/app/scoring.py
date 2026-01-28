from app.keywords import ALL_KEYWORDS, KEYWORD_GROUPS
import json

# Standalone generic keywords to exclude (only if they appear alone, not as part of longer phrases)
GENERIC_STANDALONE_KEYWORDS = {
    "bid", "tender", "procurement", "rfp", "rfq", 
    "invitation to bid", "request for proposal", "request for quotation",
    "notice", "opportunity", "contract", "service", "services"
}

def score_text(title: str, text: str = ""):
    """
    Score text based on keyword matching with quality requirements.
    Returns: (score, matched_keywords, breakdown_dict)
    Scoring: Allows all relevant keywords (1+ words), excludes generic standalone terms
    """
    combined = f"{title} {text}".lower()
    matched = [kw for kw in ALL_KEYWORDS if kw in combined]

    if not matched:
        return 0, "", {"keywords_found": 0, "total_keywords": len(ALL_KEYWORDS), "match_percentage": 0}

    # Filter out standalone generic keywords (but keep phrases containing them)
    specific_matched = [kw for kw in matched if kw not in GENERIC_STANDALONE_KEYWORDS]
    
    if not specific_matched:
        # Only generic keywords matched = not relevant
        return 0, "", {"keywords_found": 0, "reason": "Only generic keywords matched", "match_percentage": 0}
    
    unique_matched = sorted(set(specific_matched))
    
    # Score calculation: favor multi-word specific keywords but allow relevant 1-2 word terms
    score = 0
    
    for kw in unique_matched:
        word_count = len(kw.split())
        if word_count >= 4:
            score += word_count * 4  # 4+ words: 16+ points (very specific)
        elif word_count == 3:
            score += word_count * 3  # 3 words: 9 points (specific)
        elif word_count == 2:
            score += word_count * 2  # 2 words: 4 points (somewhat specific)
        else:
            score += 2  # Single word (like "edms", "dms", "ecm"): 2 points
    
    # Normalize: Expect 8-40 points for relevant tenders, scale to 10-100%
    # min_expected = 8 points = 10%
    # max_expected = 40 points = 100%
    normalized_score = ((score - 8) / (40 - 8)) * 90 + 10
    normalized_score = min(100, max(10, round(normalized_score, 2)))
    
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
