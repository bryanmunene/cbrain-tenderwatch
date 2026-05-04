import json
from datetime import date, timedelta

from app.scoring import classify_tender as classify_prompt_fit, score_text


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


def test_score_text_strongly_rewards_public_sector_f2_combo():
    title = "RFP for electronic records management and workflow automation platform"
    text = (
        "The Ministry seeks a configurable public-sector platform for records management, "
        "case handling, approval workflow, e-services portal, audit trail and digitization."
    )

    score, matched, breakdown_json = score_text(title, text)
    breakdown = json.loads(breakdown_json)

    assert score >= 70
    assert breakdown.get("priority") in {"HIGH", "MEDIUM", "HIGH PRIORITY", "GOOD FIT"}
    assert breakdown.get("likely_fit_for_F2") in {"true", "YES", "good-fit", "high-priority"}


def test_score_text_flags_microsoft_platform_lock():
    title = "RFP for complaints portal built on Microsoft Power Platform"
    text = "The solution shall be built on SharePoint Online and Microsoft 365 with no alternative platform accepted."

    score, _, breakdown_json = score_text(title, text)
    breakdown = json.loads(breakdown_json)

    assert breakdown.get("requires_qualification") is True
    assert breakdown.get("procurement_status") in {"conditional_nogo", "locked", "NO-GO"}
    assert len(breakdown.get("qualification_questions", [])) >= 4
    assert score < 70


def test_score_text_rejects_generic_ict_and_digital_portal_noise():
    examples = [
        (
            "UN City Copenhagen ICT Incident Response Agreement",
            "Information technology response, support and maintenance services.",
        ),
        (
            "Campaign for Digital Financial Literacy and E-Wallet Onboarding",
            "Public awareness campaign and mobile wallet adoption support.",
        ),
        (
            "E-procurement portal",
            "Supplier registration and general procurement website access.",
        ),
    ]

    for title, text in examples:
        score, _, breakdown_json = score_text(title, text)
        breakdown = json.loads(breakdown_json)

        assert score == 0
        assert breakdown.get("recommendation") == "NO-GO"
        assert breakdown.get("likely_fit_for_F2") == "no-go"


def test_score_text_requires_core_f2_signal_for_service_portal():
    score, _, breakdown_json = score_text(
        "Citizen engagement portal",
        "The buyer wants a public-facing portal and campaign website.",
    )
    breakdown = json.loads(breakdown_json)

    assert score == 0
    assert breakdown.get("recommendation") == "NO-GO"


def test_classify_tender_excludes_close_deadline_and_old_notice():
    result = classify_prompt_fit(
        "Records management and workflow automation for ministry",
        "Electronic document management, case workflow and registry modernization.",
        publication_date=date.today() - timedelta(days=100),
        deadline=date.today() + timedelta(days=3),
    )

    assert result["breakdown"]["timing"]["excluded_by_timing"] is True
    assert result["breakdown"]["recommendation"] == "NO-GO"
