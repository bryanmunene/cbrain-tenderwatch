from app.keywords import ALL_KEYWORDS, KEYWORD_GROUPS
import json


def score_text(title: str, text: str = ""):
    """
    Score text based on keyword matching.
    Returns: (score, matched_keywords, breakdown_dict)
    Scoring: Based on match count and specificity, normalized to 5-100%
    """
    combined = f"{title} {text}".lower()
    matched = [kw for kw in ALL_KEYWORDS if kw in combined]

    if not matched:
        return 0, "", {"keywords_found": 0, "total_keywords": len(ALL_KEYWORDS), "match_percentage": 0}

    unique_matched = sorted(set(matched))
    
    # Score calculation: count-based with multi-word keyword boost
    score = len(unique_matched)  # Base score: number of unique keywords matched
    
    # Boost for multi-word keywords (more specific = better)
    for kw in unique_matched:
        word_count = len(kw.split())
        if word_count > 1:
            score += word_count  # Extra points for specificity
    
    # Normalize: Expect 3-8 matches for most tenders, scale to 5-100%
    # More aggressive scaling to show variation
    # min_expected = 2 matches = 5%
    # max_expected = 15 matches = 100%
    normalized_score = ((score - 2) / (15 - 2)) * 95 + 5
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
