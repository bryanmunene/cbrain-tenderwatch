from collections import defaultdict
import re
from app.keywords import KEYWORD_GROUPS

# --------------------------------------------------
# MAIN CATEGORIZATION FUNCTION
# --------------------------------------------------

def categorize(title: str, text: str = "", source_name: str | None = None):
    """
    Categorize tenders based on keywords from KEYWORD_GROUPS.
    Uses multi-word keyword matching for better accuracy.
    Prioritizes category with most keyword matches + multi-word bonus.
    """
    combined = f"{title} {text}".lower()
    combined = re.sub(r"\s+", " ", combined)

    scores = defaultdict(float)
    matched_keywords = defaultdict(set)

    # Score each category based on keyword matches
    # Prioritize longer (more specific) keywords to avoid generic matches
    for category, keywords in KEYWORD_GROUPS.items():
        # Sort by length (longest first) for better multi-word matching
        sorted_keywords = sorted(keywords, key=len, reverse=True)
        
        for kw in sorted_keywords:
            if kw in combined:
                # Weight multi-word keywords higher for tie-breaking
                word_count = len(kw.split())
                # Score: multi-word gets more weight
                score_value = word_count * 2  # Multi-word: 4-6 pts, Single: 2 pts
                scores[category] += score_value
                matched_keywords[category].add(kw)

    if not scores:
        return "Unclassified", "", 0.0

    # Pick best category - if tied, prefer category with more specific keywords
    best_category = max(scores, key=lambda c: (scores[c], len([kw for kw in matched_keywords[c] if len(kw.split()) > 1])))
    
    total = sum(scores.values())
    confidence = scores[best_category] / total if total else 0.0

    keywords_used = ", ".join(sorted(matched_keywords[best_category]))

    return best_category, keywords_used, round(confidence, 3)
