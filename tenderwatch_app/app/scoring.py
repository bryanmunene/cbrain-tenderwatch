from app.keywords import ALL_KEYWORDS, KEYWORD_GROUPS, GENERIC_STANDALONE_KEYWORDS, PRIORITY_PHRASES
import json

def score_text(title: str, text: str = ""):
    """
    Score text based on keyword matching with quality requirements.
    Returns: (score, matched_keywords, breakdown_dict)
    
    Philosophy:
    - Treat any occurrence as a signal, not a filter
    - Prioritize multi-term matches, especially around workflow, case, records, government
    - Let scoring, not exclusion, decide relevance
    - Noise is cheaper to discard than missed signal
    """
    combined = f"{title} {text}".lower()
    matched = [kw for kw in ALL_KEYWORDS if kw in combined]

    if not matched:
        return 0, "", {"keywords_found": 0, "total_keywords": len(ALL_KEYWORDS), "match_percentage": 0}

    # Check for priority phrases (high-value multi-word matches)
    priority_matched = [phrase for phrase in PRIORITY_PHRASES if phrase.lower() in combined]
    
    # Filter out standalone generic keywords (but keep phrases containing them)
    specific_matched = [kw for kw in matched if kw not in GENERIC_STANDALONE_KEYWORDS]
    
    # If only generic keywords but no specific ones, still allow with lower score
    if not specific_matched and not priority_matched:
        return 5, ", ".join(matched[:5]), {"keywords_found": len(matched), "reason": "Generic keywords only", "match_percentage": 5}
    
    unique_matched = sorted(set(specific_matched))
    
    # Score calculation: favor multi-word specific keywords
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
    
    # BONUS: Priority phrases (multi-term matches close together)
    priority_bonus = 0
    for phrase in priority_matched:
        word_count = len(phrase.split())
        if word_count >= 5:
            priority_bonus += 15  # Very specific phrase
        elif word_count >= 4:
            priority_bonus += 10  # Specific phrase
        else:
            priority_bonus += 5   # Moderately specific
    
    score += priority_bonus
    
    # Normalize: Expect 8-50 points for relevant tenders, scale to 10-100%
    normalized_score = ((score - 8) / (50 - 8)) * 90 + 10
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
        "priority_phrases_matched": priority_matched,
        "priority_bonus": priority_bonus,
        "unique_keywords": unique_matched,
        "raw_score": score,
        "normalized_score": normalized_score,
        "matched_groups": matched_groups
    }
    
    # Return normalized_score (percentage), not raw score
    return normalized_score, ", ".join(unique_matched), json.dumps(breakdown)
