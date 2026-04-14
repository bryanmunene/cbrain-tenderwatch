import json

from app.scoring import score_text


def test_score_text_rewards_core_f2_terms():
    title = "Case management and records workflow platform for ministry"
    score, matched, breakdown_json = score_text(title, "")
    breakdown = json.loads(breakdown_json)

    assert score > 0
    assert isinstance(matched, str)
    assert len(breakdown.get("primary_hits", [])) >= 1


def test_score_text_excludes_irrelevant_scope():
    title = "Supply and delivery of laptops, printers and network switches"
    score, _, _ = score_text(title, "")
    assert score == 0
