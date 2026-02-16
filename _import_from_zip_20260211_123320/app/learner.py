import re
from collections import Counter
from app.extensions import db
from app.models import LearnedKeyword

STOPWORDS = {
    "the","and","for","with","from","this","that",
    "tender","procurement","services","supply"
}

def learn_keywords(title: str, category: str):
    words = re.findall(r"[a-z]{4,}", title.lower())
    counts = Counter(w for w in words if w not in STOPWORDS)

    for kw, freq in counts.items():
        row = LearnedKeyword.query.filter_by(keyword=kw).first()
        if row:
            if row.category == category:
                row.weight += 0.2
        else:
            db.session.add(
                LearnedKeyword(keyword=kw, category=category, weight=1.0)
            )
