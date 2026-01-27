import re
from datetime import datetime

MONTHS = {
    "jan":1,"feb":2,"mar":3,"apr":4,"may":5,"jun":6,
    "jul":7,"aug":8,"sep":9,"oct":10,"nov":11,"dec":12
}

def parse_deadline(text: str):
    if not text:
        return None
    t = text.lower()

    m = re.search(r"(\d{1,2})[\/\-\s]([a-z]{3,9}|\d{1,2})[\/\-\s](\d{2,4})", t)
    if not m:
        return None

    d, mth, y = m.groups()
    d = int(d)
    y = int(y) + (2000 if int(y) < 100 else 0)

    if mth.isdigit():
        mth = int(mth)
    else:
        mth = MONTHS.get(mth[:3])
        if not mth:
            return None

    return datetime(y, mth, d).strftime("%Y-%m-%d")
