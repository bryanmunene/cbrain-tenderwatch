from app.deadlines import parse_deadline


def test_parse_deadline_iso_date():
    text = "Submission deadline: 2026-08-15"
    assert parse_deadline(text) == "2026-08-15"


def test_parse_deadline_month_name_date():
    text = "Bids must be submitted by 15 February 2026"
    parsed = parse_deadline(text)
    assert parsed.startswith("2026-02-")
