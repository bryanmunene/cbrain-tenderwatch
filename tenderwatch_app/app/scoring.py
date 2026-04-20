"""Prompt-driven scoring for cBrain F2 tender discovery."""

from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any, Dict, List, Optional

import app.keywords as kw
from app.geography import enrich_scoring_with_geography

ALL_KEYWORDS = getattr(kw, "ALL_KEYWORDS", [])
KEYWORD_DOMAINS = getattr(kw, "KEYWORD_DOMAINS", {})
NEGATIVE_SIGNALS = getattr(kw, "NEGATIVE_SIGNALS", [])
IRRELEVANT_SIGNALS = getattr(kw, "IRRELEVANT_SIGNALS", [])
PRIORITY_COMBINATIONS = getattr(kw, "PRIORITY_COMBINATIONS", [])
PRIORITY_PHRASES = getattr(kw, "PRIORITY_PHRASES", [])
MICROSOFT_HARD_LOCK_SIGNALS = getattr(kw, "MICROSOFT_HARD_LOCK_SIGNALS", [])
MICROSOFT_SOFT_LOCK_SIGNALS = getattr(kw, "MICROSOFT_SOFT_LOCK_SIGNALS", [])
OPENNESS_SIGNALS = getattr(kw, "OPENNESS_SIGNALS", [])
OPEN_PROCUREMENT_SIGNALS = getattr(kw, "OPEN_PROCUREMENT_SIGNALS", [])
QUALIFICATION_QUESTIONS = getattr(kw, "QUALIFICATION_QUESTIONS", [])

PRIMARY_DOMAINS = {
    "EDMS",
    "Records",
    "Workflow",
    "Case",
    "ECM",
    "ServiceDelivery",
    "Licensing",
    "ProcurementRecords",
}
SUPPORTING_DOMAINS = {"Gov", "Forms", "Integration", "Pipeline"}


def _normalize(text: str) -> str:
    fn = getattr(kw, "_normalize", None)
    if callable(fn):
        return str(fn(text) or "")
    return (text or "").lower().strip()


def _collect_hits(text: str, phrases: List[str], max_hits: Optional[int] = None) -> List[str]:
    fn = getattr(kw, "_collect_hits", None)
    if callable(fn):
        return list(fn(text, phrases, max_hits=max_hits) or [])

    hits: List[str] = []
    hay = _normalize(text)
    for phrase in phrases:
        p = _normalize(phrase)
        if p and p in hay and p not in hits:
            hits.append(p)
            if max_hits is not None and len(hits) >= max_hits:
                break
    return hits


def _parse_date(value: Any) -> Optional[date]:
    if not value:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    text = str(value).strip()[:10]
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except Exception:
            continue
    return None


def _timing_breakdown(publication_date: Any = None, deadline: Any = None) -> Dict[str, Any]:
    today = date.today()
    pub = _parse_date(publication_date)
    due = _parse_date(deadline)
    out = {
        "days_to_deadline": None,
        "days_since_publication": None,
        "missing_deadline": due is None,
        "missing_publication_date": pub is None,
        "excluded_by_timing": False,
        "timing_reason": "",
    }
    reasons: List[str] = []

    if due is not None:
        out["days_to_deadline"] = (due - today).days
        if out["days_to_deadline"] < 7:
            out["excluded_by_timing"] = True
            reasons.append("Submission deadline is under 7 days away")

    if pub is not None:
        out["days_since_publication"] = (today - pub).days
        if out["days_since_publication"] > 90:
            out["excluded_by_timing"] = True
            reasons.append("Notice is older than 3 months")

    if reasons:
        out["timing_reason"] = "; ".join(reasons)
    elif due is None or pub is None:
        out["timing_reason"] = "Date uncertainty"

    return out


def score_text(
    title: str,
    text: str = "",
    *,
    publication_date: Any = None,
    deadline: Any = None,
):
    """Return prompt-driven F2 fit score, matched keywords string, and JSON breakdown."""
    combined_raw = f"{title or ''} {text or ''}".strip()
    combined = _normalize(combined_raw)

    domain_hits: Dict[str, List[str]] = {}
    for domain, phrases in KEYWORD_DOMAINS.items():
        hits = _collect_hits(combined, phrases, max_hits=12)
        if hits:
            domain_hits[domain] = hits

    matched_domains = set(domain_hits.keys())
    primary_hits: List[str] = []
    secondary_hits: List[str] = []
    for domain, hits in domain_hits.items():
        if domain in PRIMARY_DOMAINS:
            primary_hits.extend(hits)
        else:
            secondary_hits.extend(hits)

    primary_hits = list(dict.fromkeys(primary_hits))
    secondary_hits = list(dict.fromkeys(secondary_hits))
    matched_keywords = primary_hits + secondary_hits

    negative_hits = _collect_hits(combined, list(dict.fromkeys(IRRELEVANT_SIGNALS + NEGATIVE_SIGNALS)), max_hits=10)
    hard_lock_hits = _collect_hits(combined, MICROSOFT_HARD_LOCK_SIGNALS, max_hits=6)
    soft_lock_hits = _collect_hits(combined, MICROSOFT_SOFT_LOCK_SIGNALS, max_hits=6)
    openness_hits = _collect_hits(combined, OPENNESS_SIGNALS, max_hits=4)
    procurement_hits = _collect_hits(combined, OPEN_PROCUREMENT_SIGNALS, max_hits=5)
    timing = _timing_breakdown(publication_date=publication_date, deadline=deadline)

    primary_domain_count = len(matched_domains & PRIMARY_DOMAINS)
    supporting_domain_count = len(matched_domains & SUPPORTING_DOMAINS)
    government_context = 1 if "Gov" in matched_domains else 0

    combo_bonus = 0
    strong_fit_combinations: List[str] = []
    combo_priority = "LOW"
    for combo in PRIORITY_COMBINATIONS:
        try:
            combo_domains, bonus, priority = combo
        except ValueError:
            continue
        if all(domain in matched_domains for domain in combo_domains):
            combo_bonus = max(combo_bonus, int(bonus))
            strong_fit_combinations.append(" + ".join(combo_domains))
            if priority == "HIGH":
                combo_priority = "HIGH"
            elif priority == "MEDIUM" and combo_priority != "HIGH":
                combo_priority = "MEDIUM"

    if primary_domain_count == 0:
        breakdown = {
            "keywords_found": 0,
            "matched_keywords": [],
            "domains_matched": sorted(matched_domains),
            "primary_hits": [],
            "secondary_hits": secondary_hits,
            "irrelevant_signals": negative_hits,
            "priority": "LOW",
            "fit_classification": "NO-GO",
            "likely_fit_for_F2": "no-go",
            "procurement_status": "open",
            "requires_qualification": False,
            "qualification_reason": "No core F2 workflow/records/case/platform signals found",
            "qualification_questions": [],
            "timing": timing,
            "recommendation": "NO-GO",
            "queue_bucket": "no_go",
            "final_score": 0,
            "excluded": True,
        }
        return 0, "", json.dumps(breakdown)

    if negative_hits and primary_domain_count < 2:
        breakdown = {
            "keywords_found": len(matched_keywords),
            "matched_keywords": matched_keywords[:20],
            "domains_matched": sorted(matched_domains),
            "primary_hits": primary_hits,
            "secondary_hits": secondary_hits,
            "irrelevant_signals": negative_hits,
            "priority": "LOW",
            "fit_classification": "NO-GO",
            "likely_fit_for_F2": "no-go",
            "procurement_status": "open",
            "requires_qualification": False,
            "qualification_reason": "Scope is dominated by excluded hardware/infrastructure/construction signals",
            "qualification_questions": [],
            "timing": timing,
            "recommendation": "NO-GO",
            "queue_bucket": "no_go",
            "final_score": 0,
            "excluded": True,
        }
        return 0, ", ".join(primary_hits[:5]), json.dumps(breakdown)

    raw_score = 0
    raw_score += min(42, len(primary_hits) * 6 + primary_domain_count * 8)
    raw_score += min(18, len(secondary_hits) * 2 + supporting_domain_count * 3)
    raw_score += combo_bonus
    raw_score += 6 if government_context else 0
    raw_score += 5 if procurement_hits else 0
    raw_score += 4 if len(domain_hits.get("Integration", [])) >= 2 else 0
    raw_score += 4 if primary_domain_count >= 3 else 0
    raw_score -= min(36, len(negative_hits) * 12)

    procurement_status = "open"
    requires_qualification = False
    qualification_reason = ""

    if hard_lock_hits and (
        "no alternative platform accepted" in hard_lock_hits or not openness_hits
    ):
        procurement_status = "conditional_nogo"
        requires_qualification = True
        qualification_reason = "Microsoft or SharePoint stack appears mandatory with no clear alternative platform allowance"
        raw_score -= 35
    elif hard_lock_hits:
        procurement_status = "conditional_discuss"
        requires_qualification = True
        qualification_reason = "Microsoft stack is referenced, but the notice may still allow an alternative approach"
        raw_score -= 15
    elif soft_lock_hits and not openness_hits:
        procurement_status = "locked_but_open"
        requires_qualification = True
        qualification_reason = "Existing Microsoft environment may constrain platform choice"
        raw_score -= 10
    elif soft_lock_hits:
        procurement_status = "conditional"
        requires_qualification = True
        qualification_reason = "Microsoft environment exists; clarify openness to F2 as an alternative"
        raw_score -= 5

    score = max(0, min(100, int(round(raw_score))))

    if timing.get("excluded_by_timing"):
        score = min(score, 25)

    fit_classification = "NO-GO"
    priority = combo_priority if combo_priority != "LOW" else "LOW"
    likely_fit = "no-go"
    recommendation = "NO-GO"
    queue_bucket = "no_go"

    if timing.get("excluded_by_timing"):
        fit_classification = "NO-GO"
        priority = "LOW"
        likely_fit = "no-go"
        recommendation = "NO-GO"
    elif procurement_status == "conditional_nogo":
        fit_classification = "NO-GO"
        priority = "LOCKED"
        likely_fit = "no-go"
        recommendation = "NO-GO"
    elif requires_qualification:
        fit_classification = "CONDITIONAL"
        priority = "CONDITIONAL"
        likely_fit = "conditional"
        recommendation = "REVIEW"
        queue_bucket = "conditional_watchlist"
    elif score >= 80 and primary_domain_count >= 2 and government_context:
        fit_classification = "HIGH PRIORITY"
        priority = "HIGH"
        likely_fit = "true"
        recommendation = "PURSUE"
        queue_bucket = "today_shortlist"
    elif score >= 70:
        fit_classification = "GOOD FIT"
        priority = "HIGH" if priority == "HIGH" else "MEDIUM"
        likely_fit = "true"
        recommendation = "PURSUE"
        queue_bucket = "main_shortlist"
    elif score >= 45:
        fit_classification = "CONDITIONAL"
        priority = "CONDITIONAL"
        likely_fit = "conditional"
        recommendation = "REVIEW"
        queue_bucket = "conditional_watchlist"

    breakdown = {
        "keywords_found": len(matched_keywords),
        "matched_keywords": matched_keywords[:20],
        "primary_hits": primary_hits,
        "secondary_hits": secondary_hits,
        "domains_matched": sorted(matched_domains),
        "strong_fit_combinations": strong_fit_combinations,
        "priority_phrases_matched": _collect_hits(combined, PRIORITY_PHRASES, max_hits=8),
        "negative_signals_found": negative_hits,
        "irrelevant_signals": negative_hits,
        "platform_lockin_signals": list(dict.fromkeys(hard_lock_hits + soft_lock_hits)),
        "microsoft_commitment_signals": list(dict.fromkeys(hard_lock_hits + soft_lock_hits)),
        "open_procurement_signals": procurement_hits,
        "platform_openness_signals": openness_hits,
        "procurement_status": procurement_status,
        "requires_qualification": requires_qualification,
        "qualification_reason": qualification_reason,
        "qualification_questions": QUALIFICATION_QUESTIONS if requires_qualification else [],
        "timing": timing,
        "base_score": raw_score,
        "domain_bonus": combo_bonus,
        "priority_bonus": 0,
        "negative_penalty": -min(36, len(negative_hits) * 12),
        "raw_score": raw_score,
        "normalized_score": score,
        "match_percentage": score,
        "final_score": score,
        "priority": priority,
        "fit_classification": fit_classification,
        "likely_fit_for_F2": likely_fit,
        "recommendation": recommendation,
        "queue_bucket": queue_bucket,
        "excluded": recommendation == "NO-GO",
    }

    matched_str = ", ".join((primary_hits + secondary_hits)[:8])
    return score, matched_str, json.dumps(breakdown)


def score_tender(
    title: str,
    text: str = "",
    *,
    buyer: str = "",
    country: str = "",
    source_name: str = "",
    source_url: str = "",
    source_group: str = "",
    source_tags=None,
    pipeline_mode: str = "africa_priority",
    settings=None,
    publication_date: Any = None,
    deadline: Any = None,
):
    base_score, matched_str, breakdown_json = score_text(
        title,
        text,
        publication_date=publication_date,
        deadline=deadline,
    )
    try:
        breakdown = json.loads(breakdown_json)
    except Exception:
        breakdown = {}

    ranking_score, breakdown = enrich_scoring_with_geography(
        base_score=base_score,
        breakdown=breakdown,
        title=title,
        text=text,
        buyer=buyer,
        country=country,
        source_name=source_name,
        source_url=source_url,
        source_group=source_group,
        source_tags=source_tags,
        pipeline_mode=pipeline_mode,
        settings=settings,
    )

    if breakdown.get("recommendation") == "NO-GO":
        ranking_score = min(float(ranking_score or 0), float(base_score or 0))

    breakdown["final_score"] = ranking_score
    return base_score, matched_str, json.dumps(breakdown), ranking_score


def classify_tender(title: str, text: str = "", **kwargs):
    score, _, breakdown_json = score_text(
        title,
        text,
        publication_date=kwargs.get("publication_date"),
        deadline=kwargs.get("deadline"),
    )
    breakdown = json.loads(breakdown_json)
    return {
        "relevance_score": score,
        "matched_keywords": breakdown.get("matched_keywords", []),
        "inferred_domains": breakdown.get("domains_matched", []),
        "priority": breakdown.get("priority", "LOW"),
        "likely_fit_for_F2": breakdown.get("likely_fit_for_F2", "uncertain"),
        "breakdown": breakdown,
    }
