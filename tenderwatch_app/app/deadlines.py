import re
from datetime import datetime, timedelta

MONTHS = {
    "jan":1,"feb":2,"mar":3,"apr":4,"may":5,"jun":6,
    "jul":7,"aug":8,"sep":9,"oct":10,"nov":11,"dec":12
}


def _utcnow():
    # Keep naive UTC for compatibility with existing DB datetime usage.
    return datetime.now(datetime.UTC).replace(tzinfo=None)

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
    try:
        return datetime(y, mth, d).strftime("%Y-%m-%d")
    except ValueError:
        return None


def check_timing_constraints(deadline_str: str, publication_date: datetime = None):
    """
    F2-Aligned Timing Constraints (HARD FILTERS):
    - Submission deadline >= 7 days from scan date
    - Publication/float date <= 3 months from scan date
    
    If dates are missing, do NOT auto-exclude - downgrade confidence instead.
    
    Returns:
        tuple: (is_valid, confidence_modifier, reason)
        - is_valid: True if passes timing constraints OR dates missing
        - confidence_modifier: 0 (pass), -0.1 to -0.3 (warning), or -0.5 (fail but include)
        - reason: Human-readable explanation
    """
    now = _utcnow()
    min_deadline = now + timedelta(days=7)
    max_publication_age = now - timedelta(days=90)  # 3 months ago
    
    # Case 1: Both dates missing - include with slight confidence penalty
    if not deadline_str and not publication_date:
        return (True, -0.1, "No dates available - included with lower confidence")
    
    # Case 2: Parse deadline if provided
    if deadline_str:
        try:
            deadline = datetime.strptime(deadline_str, "%Y-%m-%d")
            
            # Hard filter: deadline must be >= 7 days from now
            if deadline < min_deadline:
                days_until = (deadline - now).days
                if days_until < 0:
                    return (False, -0.5, f"Deadline passed ({deadline_str})")
                else:
                    return (False, -0.3, f"Deadline too soon ({days_until} days)")
        except ValueError:
            # Invalid date format - include with warning
            pass
    
    # Case 3: Check publication date if provided
    if publication_date:
        if publication_date < max_publication_age:
            days_old = (now - publication_date).days
            return (True, -0.2, f"Publication is {days_old} days old - may be stale")
    
    # All checks passed
    return (True, 0, "Timing OK")


def is_deadline_valid(deadline_str: str):
    """
    Simple check: is deadline >= 7 days from now?
    Returns True if valid OR if deadline is missing (don't exclude).
    """
    if not deadline_str:
        return True  # Don't exclude if missing
    
    try:
        deadline = datetime.strptime(deadline_str, "%Y-%m-%d")
        min_deadline = _utcnow() + timedelta(days=7)
        return deadline >= min_deadline
    except ValueError:
        return True  # Don't exclude on parse error

