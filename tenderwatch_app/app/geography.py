from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
from urllib.parse import urlparse


AFRICA_COUNTRY_TO_REGION: Dict[str, str] = {
    "algeria": "North Africa",
    "angola": "Southern Africa",
    "benin": "West Africa",
    "botswana": "Southern Africa",
    "burkina faso": "West Africa",
    "burundi": "East Africa",
    "cabo verde": "West Africa",
    "cape verde": "West Africa",
    "cameroon": "Central Africa",
    "central african republic": "Central Africa",
    "chad": "Central Africa",
    "comoros": "East Africa",
    "congo": "Central Africa",
    "democratic republic of the congo": "Central Africa",
    "dr congo": "Central Africa",
    "drc": "Central Africa",
    "djibouti": "East Africa",
    "egypt": "North Africa",
    "equatorial guinea": "Central Africa",
    "eritrea": "East Africa",
    "eswatini": "Southern Africa",
    "ethiopia": "East Africa",
    "gabon": "Central Africa",
    "gambia": "West Africa",
    "ghana": "West Africa",
    "guinea": "West Africa",
    "guinea bissau": "West Africa",
    "guinea-bissau": "West Africa",
    "ivory coast": "West Africa",
    "cote d ivoire": "West Africa",
    "cote d'ivoire": "West Africa",
    "kenya": "East Africa",
    "lesotho": "Southern Africa",
    "liberia": "West Africa",
    "libya": "North Africa",
    "madagascar": "Southern Africa",
    "malawi": "Southern Africa",
    "mali": "West Africa",
    "mauritania": "West Africa",
    "mauritius": "Southern Africa",
    "morocco": "North Africa",
    "mozambique": "Southern Africa",
    "namibia": "Southern Africa",
    "niger": "West Africa",
    "nigeria": "West Africa",
    "rwanda": "East Africa",
    "sao tome and principe": "Central Africa",
    "senegal": "West Africa",
    "seychelles": "East Africa",
    "sierra leone": "West Africa",
    "somalia": "East Africa",
    "south africa": "Southern Africa",
    "south sudan": "East Africa",
    "sudan": "North Africa",
    "tanzania": "East Africa",
    "togo": "West Africa",
    "tunisia": "North Africa",
    "uganda": "East Africa",
    "zambia": "Southern Africa",
    "zimbabwe": "Southern Africa",
    "africa regional": "Africa",
}

COUNTRY_ALIASES: Dict[str, str] = {
    "drc": "Democratic Republic of the Congo",
    "dr congo": "Democratic Republic of the Congo",
    "congo drc": "Democratic Republic of the Congo",
    "ivory coast": "Ivory Coast",
    "cote d ivoire": "Ivory Coast",
    "cote d'ivoire": "Ivory Coast",
    "uae": "United Arab Emirates",
    "uk": "United Kingdom",
    "us": "United States",
    "usa": "United States",
}

OTHER_COUNTRY_TO_REGION: Dict[str, str] = {
    "australia": "Oceania",
    "bangladesh": "Asia",
    "belgium": "Europe",
    "brazil": "Latin America",
    "canada": "North America",
    "china": "Asia",
    "denmark": "Europe",
    "france": "Europe",
    "germany": "Europe",
    "india": "Asia",
    "indonesia": "Asia",
    "ireland": "Europe",
    "italy": "Europe",
    "jordan": "Middle East",
    "netherlands": "Europe",
    "norway": "Europe",
    "pakistan": "Asia",
    "philippines": "Asia",
    "qatar": "Middle East",
    "saudi arabia": "Middle East",
    "singapore": "Asia",
    "spain": "Europe",
    "sweden": "Europe",
    "switzerland": "Europe",
    "united arab emirates": "Middle East",
    "united kingdom": "Europe",
    "united states": "North America",
}

AFRICA_REGION_TERMS: Dict[str, str] = {
    "east africa": "East Africa",
    "eastern africa": "East Africa",
    "west africa": "West Africa",
    "western africa": "West Africa",
    "southern africa": "Southern Africa",
    "central africa": "Central Africa",
    "north africa": "North Africa",
    "africa regional": "Africa",
    "sub saharan africa": "Africa",
    "sub-saharan africa": "Africa",
}

AFRICA_REGIONAL_PROGRAM_TERMS: Dict[str, str] = {
    "eac": "East Africa",
    "east african community": "East Africa",
    "ecowas": "West Africa",
    "sadc": "Southern Africa",
    "comesa": "Africa",
    "african union": "Africa",
    "au commission": "Africa",
    "trademark africa": "East Africa",
}

GLOBAL_SCOPE_TERMS = {
    "global",
    "international",
    "worldwide",
    "multi country",
    "multicountry",
    "multiple countries",
}

DONOR_TERMS = {
    "afdb",
    "african development bank",
    "adb",
    "world bank",
    "international development association",
    "ida",
    "ifc",
    "undp",
    "unops",
    "ungm",
    "united nations",
    "european union",
    "eu funded",
    "eib",
    "usaid",
    "giz",
    "fcdo",
    "dfid",
    "danida",
    "sida",
    "kfw",
    "trade and development fund",
    "donor funded",
    "grant funded",
}

PUBLIC_SECTOR_TERMS = {
    "government",
    "ministry",
    "department",
    "authority",
    "agency",
    "public sector",
    "municipality",
    "municipal",
    "county government",
    "state government",
    "regulator",
    "regulatory",
    "treasury",
    "judiciary",
    "court",
    "revenue authority",
    "commission",
    "public body",
    "procurement authority",
    "city council",
    "parastatal",
}

PRIVATE_SECTOR_TERMS = {
    "private company",
    "commercial software",
    "commercial enterprise",
    "private sector",
    "for profit",
    "retail chain",
    "bank plc",
    "telecom operator",
}

GLOBAL_DOWNGRADE_TERMS = {
    "construction",
    "civil works",
    "building works",
    "road works",
    "hardware supply",
    "supply and delivery",
    "vehicles",
    "laptops",
    "desktop computers",
    "staff augmentation",
    "recruitment",
    "staffing",
    "labour hire",
    "generic consultancy",
    "consulting services",
    "architectural services",
}

DOMAIN_PROMOTION_TERMS = {
    "records management",
    "document management",
    "edms",
    "edrms",
    "workflow",
    "workflow automation",
    "case management",
    "registry management",
    "citizen services",
    "citizen portal",
    "regulatory system",
    "revenue system",
    "public administration modernization",
    "public administration modernisation",
    "institutional modernization",
    "institutional modernisation",
}

LARGE_ENTERPRISE_TERMS = {
    "enterprise platform",
    "process automation",
    "business process management",
    "bpm",
    "workflow engine",
    "document repository",
    "content management platform",
}

SOURCE_GROUPS = {
    "africa_priority",
    "africa_regional",
    "global_public",
    "global_multilateral",
    "aggregator",
    "experimental",
}

AFRICA_SOURCE_HINTS = {
    "tenders.go.ke",
    "ppda",
    "ppra",
    "bpp",
    "ppa.gov.gh",
    "ghaneps",
    "rppa",
    "zppa",
    "ict authority",
    "kemsa",
    "kra",
    "kaa",
    "ketraco",
    "kpa",
    "cbk",
    "county government",
}

AFRICA_REGIONAL_SOURCE_HINTS = {
    "afdb",
    "african development bank",
    "trademark africa",
    "african union",
    "comesa",
    "ecowas",
    "sadc",
    "east african community",
}

GLOBAL_MULTILATERAL_SOURCE_HINTS = {
    "undp",
    "ungm",
    "unops",
    "world bank",
    "devbusiness",
    "eib",
    "who",
    "wfp",
    "fao",
    "ilo",
    "aiib",
    "idb",
    "commonwealth",
    "eib",
    "devbusiness",
}

AGGREGATOR_SOURCE_HINTS = {
    "globaltenders",
    "dgmarket",
    "tendersinfo",
    "tendersontime",
    "biddetail",
}

GLOBAL_PUBLIC_SOURCE_HINTS = {
    "find a tender",
    "ted europa",
    "udbud",
    "bund",
    "sam.gov",
    "austender",
    "cppp",
    "gebiz",
    "eu funding",
}


@dataclass(frozen=True)
class GeoSettings:
    africa_priority_weight: float = 12.0
    global_relevance_threshold: float = 28.0
    donor_multilateral_boost: float = 8.0
    africa_only_mode: bool = False
    include_global_sources: bool = True
    include_global_in_default_shortlist: bool = False
    secondary_review_queue_threshold: float = 16.0


def _text(value: Any) -> str:
    return (value or "").strip().lower()


def _compact_space(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip())


def _normalize_country(value: str) -> str:
    cleaned = _compact_space(value).lower()
    if not cleaned:
        return ""
    cleaned = cleaned.replace(".", "")
    canonical = COUNTRY_ALIASES.get(cleaned, cleaned)
    if canonical in AFRICA_COUNTRY_TO_REGION:
        return canonical.title() if canonical != "africa regional" else "Africa Regional"
    if canonical in OTHER_COUNTRY_TO_REGION:
        return canonical.title()
    return _compact_space(canonical.title())


def _contains_any(text: str, terms: Iterable[str]) -> List[str]:
    haystack = f" {text} "
    hits: List[str] = []
    for term in terms:
        needle = _text(term)
        if not needle:
            continue
        if f" {needle} " in haystack or needle in text:
            hits.append(term)
    return hits


def parse_source_tags(value: Any) -> List[str]:
    if not value:
        return []
    if isinstance(value, (list, tuple, set)):
        raw = [str(item).strip().lower() for item in value if str(item).strip()]
    else:
        text = str(value).strip()
        if not text:
            return []
        try:
            parsed = json.loads(text)
        except Exception:
            parsed = [part.strip().lower() for part in text.split(",") if part.strip()]
        if isinstance(parsed, (list, tuple, set)):
            raw = [str(item).strip().lower() for item in parsed if str(item).strip()]
        else:
            raw = [str(parsed).strip().lower()] if str(parsed).strip() else []

    deduped: List[str] = []
    seen = set()
    for item in raw:
        if item not in seen:
            deduped.append(item)
            seen.add(item)
    return deduped


def normalize_source_group(value: str) -> str:
    group = _text(value).replace("-", "_").replace(" ", "_")
    if group in SOURCE_GROUPS:
        return group
    return ""


def source_tags_for_group(group: str) -> List[str]:
    normalized = normalize_source_group(group)
    return [normalized] if normalized else []


def source_pipeline(group: str) -> str:
    normalized = normalize_source_group(group)
    if normalized in {"africa_priority", "africa_regional"}:
        return "africa_priority"
    return "global_discovery"


def infer_source_group(
    source_name: str = "",
    source_url: str = "",
    explicit_group: str = "",
    explicit_tags: Optional[Sequence[str]] = None,
) -> str:
    normalized = normalize_source_group(explicit_group)
    if normalized and normalized != "experimental":
        return normalized

    tags = [normalize_source_group(tag) for tag in parse_source_tags(explicit_tags or [])]
    for tag in tags:
        if tag and tag != "experimental":
            return tag

    haystack = _text(f"{source_name} {source_url}")
    if any(hint in haystack for hint in AGGREGATOR_SOURCE_HINTS):
        return "aggregator"
    if any(hint in haystack for hint in AFRICA_REGIONAL_SOURCE_HINTS):
        return "africa_regional"
    if any(hint in haystack for hint in GLOBAL_MULTILATERAL_SOURCE_HINTS):
        return "global_multilateral"
    if any(hint in haystack for hint in GLOBAL_PUBLIC_SOURCE_HINTS):
        return "global_public"
    if any(hint in haystack for hint in AFRICA_SOURCE_HINTS):
        return "africa_priority"

    host = (urlparse(source_url).netloc or "").lower().strip()
    if host.endswith((".ke", ".ug", ".tz", ".rw", ".za", ".gh", ".ng", ".zm", ".et", ".sz", ".bw", ".mz", ".mw", ".na", ".sn", ".ci", ".cm", ".ma", ".tn", ".eg", ".dz", ".ao", ".zw", ".mu")):
        return "africa_priority"
    if host.endswith((".gov", ".gov.uk", ".gov.au", ".eu")) or ".gov." in host:
        return "global_public"
    return normalized or "experimental"


def settings_from_model(settings: Any = None) -> GeoSettings:
    if settings is None:
        return GeoSettings()
    return GeoSettings(
        africa_priority_weight=float(getattr(settings, "africa_priority_weight", 12.0) or 12.0),
        global_relevance_threshold=float(getattr(settings, "global_relevance_threshold", 28.0) or 28.0),
        donor_multilateral_boost=float(getattr(settings, "donor_multilateral_boost", 8.0) or 8.0),
        africa_only_mode=bool(getattr(settings, "africa_only_mode", False)),
        include_global_sources=bool(getattr(settings, "include_global_sources", True)),
        include_global_in_default_shortlist=bool(getattr(settings, "include_global_in_default_shortlist", False)),
        secondary_review_queue_threshold=float(
            getattr(settings, "secondary_review_queue_threshold", 16.0) or 16.0
        ),
    )


def is_africa_country(country: str) -> bool:
    return _text(country) in AFRICA_COUNTRY_TO_REGION


def region_for_country(country: str) -> str:
    key = _text(country)
    if key in AFRICA_COUNTRY_TO_REGION:
        return AFRICA_COUNTRY_TO_REGION[key]
    if key in OTHER_COUNTRY_TO_REGION:
        return OTHER_COUNTRY_TO_REGION[key]
    return "Unknown"


def _detected_countries(text: str) -> List[str]:
    haystack = _text(text)
    hits: List[str] = []
    for country in list(AFRICA_COUNTRY_TO_REGION.keys()) + list(OTHER_COUNTRY_TO_REGION.keys()):
        if country and country in haystack:
            normalized = _normalize_country(country)
            if normalized and normalized not in hits:
                hits.append(normalized)
    return hits


def infer_country(
    explicit_country: str = "",
    title: str = "",
    text: str = "",
    buyer: str = "",
    source_name: str = "",
    source_url: str = "",
) -> str:
    if explicit_country and _text(explicit_country) not in {"global", "unknown"}:
        return _normalize_country(explicit_country)

    combined = _text(f"{title} {text} {buyer} {source_name} {source_url}")
    countries = _detected_countries(combined)
    if countries:
        return countries[0]

    host = (urlparse(source_url).netloc or "").lower().strip()
    cctld_map = {
        ".ke": "Kenya",
        ".ug": "Uganda",
        ".tz": "Tanzania",
        ".rw": "Rwanda",
        ".za": "South Africa",
        ".gh": "Ghana",
        ".ng": "Nigeria",
        ".zm": "Zambia",
        ".et": "Ethiopia",
        ".sz": "Eswatini",
        ".ma": "Morocco",
        ".eg": "Egypt",
    }
    for suffix, country in cctld_map.items():
        if host.endswith(suffix):
            return country
    return ""


def _target_region_from_text(text: str) -> str:
    haystack = _text(text)
    for term, region in AFRICA_REGION_TERMS.items():
        if term in haystack:
            return region
    for term, region in AFRICA_REGIONAL_PROGRAM_TERMS.items():
        if term in haystack:
            return region
    if any(term in haystack for term in {"african governments", "african institutions", "african public sector", "across africa"}):
        return "Africa"
    if any(term in haystack for term in GLOBAL_SCOPE_TERMS):
        return "Global"
    return ""


def classify_geography(
    *,
    title: str = "",
    text: str = "",
    buyer: str = "",
    country: str = "",
    source_name: str = "",
    source_url: str = "",
    source_group: str = "",
    source_tags: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    group = infer_source_group(source_name, source_url, source_group, source_tags)
    normalized_country = infer_country(
        explicit_country=country,
        title=title,
        text=text,
        buyer=buyer,
        source_name=source_name,
        source_url=source_url,
    )
    combined = _text(f"{title} {text} {buyer} {source_name}")
    source_country_region = region_for_country(normalized_country) if normalized_country else "Unknown"
    target_region = _target_region_from_text(f"{title} {text}")

    detected_countries = _detected_countries(f"{title} {text} {buyer}")
    african_countries = [c for c in detected_countries if is_africa_country(c)]
    multi_country_africa = len({c.lower() for c in african_countries}) >= 2 or target_region in {
        "Africa",
        "East Africa",
        "West Africa",
        "Southern Africa",
        "Central Africa",
        "North Africa",
    }

    public_sector_hits = _contains_any(combined, PUBLIC_SECTOR_TERMS)
    donor_hits = _contains_any(combined, DONOR_TERMS)
    private_hits = _contains_any(combined, PRIVATE_SECTOR_TERMS)
    downgrade_hits = _contains_any(combined, GLOBAL_DOWNGRADE_TERMS)
    domain_hits = _contains_any(combined, DOMAIN_PROMOTION_TERMS)
    enterprise_hits = _contains_any(combined, LARGE_ENTERPRISE_TERMS)

    buyer_region = source_country_region
    implementation_region = target_region or source_country_region
    target_beneficiary_region = target_region or ("Africa" if multi_country_africa else source_country_region)

    donor_or_multilateral_flag = bool(
        donor_hits
        or group in {"global_multilateral", "africa_regional"}
    )

    africa_priority_flag = bool(
        is_africa_country(normalized_country)
        or source_country_region in {"East Africa", "West Africa", "Southern Africa", "Central Africa", "North Africa", "Africa"}
        or implementation_region in {"East Africa", "West Africa", "Southern Africa", "Central Africa", "North Africa", "Africa"}
        or target_beneficiary_region in {"East Africa", "West Africa", "Southern Africa", "Central Africa", "North Africa", "Africa"}
        or group in {"africa_priority", "africa_regional"}
    )

    if group in {"global_multilateral", "global_public", "aggregator"} and africa_priority_flag:
        geographic_scope = "Global"
    elif africa_priority_flag:
        geographic_scope = "Africa"
    elif group in {"global_multilateral", "global_public", "aggregator"} or target_beneficiary_region == "Global":
        geographic_scope = "Global"
    elif normalized_country:
        geographic_scope = "Other Region"
    else:
        geographic_scope = "Unknown"

    geo_label = (
        "Africa-priority"
        if geographic_scope == "Africa"
        else "Africa-targeted global"
        if africa_priority_flag and geographic_scope == "Global"
        else "Non-African global"
        if geographic_scope == "Global"
        else "Other-region"
        if geographic_scope == "Other Region"
        else "Unknown geography"
    )

    return {
        "country": normalized_country or (country if country else "Unknown"),
        "region": source_country_region,
        "geographic_scope": geographic_scope,
        "africa_priority_flag": africa_priority_flag,
        "donor_or_multilateral_flag": donor_or_multilateral_flag,
        "target_beneficiary_region": target_beneficiary_region if target_beneficiary_region != "Unknown" else "",
        "buyer_region": buyer_region if buyer_region != "Unknown" else "",
        "implementation_region": implementation_region if implementation_region != "Unknown" else "",
        "multi_country_africa": multi_country_africa,
        "public_sector_signal": bool(public_sector_hits) or group in {"africa_priority", "africa_regional", "global_public", "global_multilateral"},
        "private_sector_signal": bool(private_hits),
        "downgrade_hits": downgrade_hits,
        "domain_hits": domain_hits,
        "enterprise_hits": enterprise_hits,
        "donor_hits": donor_hits,
        "source_group": group,
        "source_tags": source_tags_for_group(group) if not source_tags else parse_source_tags(source_tags),
        "geo_label": geo_label,
    }


def enrich_scoring_with_geography(
    *,
    base_score: float,
    breakdown: Dict[str, Any],
    title: str = "",
    text: str = "",
    buyer: str = "",
    country: str = "",
    source_name: str = "",
    source_url: str = "",
    source_group: str = "",
    source_tags: Optional[Sequence[str]] = None,
    pipeline_mode: str = "africa_priority",
    settings: Any = None,
) -> Tuple[float, Dict[str, Any]]:
    geo = classify_geography(
        title=title,
        text=text,
        buyer=buyer,
        country=country,
        source_name=source_name,
        source_url=source_url,
        source_group=source_group,
        source_tags=source_tags,
    )
    cfg = settings_from_model(settings)
    fit_score = float(base_score or 0)
    keywords_found = int(breakdown.get("keywords_found", 0) or 0)
    domains_matched = breakdown.get("domains_matched", []) or []
    strong_domain_fit = bool(
        geo["domain_hits"]
        or geo["enterprise_hits"]
        or keywords_found >= 3
        or len(domains_matched) >= 2
        or any(domain in {"EDMS", "Workflow", "Case", "Gov", "Records", "ECM"} for domain in domains_matched)
    )

    geo_adjustment = 0.0
    ranking_reason: List[str] = []

    if geo["geographic_scope"] == "Africa" and geo["africa_priority_flag"]:
        geo_adjustment += cfg.africa_priority_weight
        ranking_reason.append("African buyer or implementation context lifted ranking.")
    if geo["multi_country_africa"]:
        geo_adjustment += cfg.africa_priority_weight * 0.5
        ranking_reason.append("Multi-country African program received extra regional weight.")
    if geo["geographic_scope"] == "Global" and geo["africa_priority_flag"] and geo["donor_or_multilateral_flag"]:
        geo_adjustment += cfg.donor_multilateral_boost
        ranking_reason.append("Global donor or multilateral tender targets African institutions.")
    elif geo["donor_or_multilateral_flag"]:
        geo_adjustment += cfg.donor_multilateral_boost * 0.5
        ranking_reason.append("Donor or multilateral route adds strategic value.")

    if geo["geographic_scope"] == "Global" and geo["public_sector_signal"] and strong_domain_fit:
        geo_adjustment += min(4.0, cfg.africa_priority_weight * 0.25)
        ranking_reason.append("Strong global public-sector fit kept this tender competitive.")

    if geo["private_sector_signal"] and not geo["public_sector_signal"] and not strong_domain_fit:
        geo_adjustment -= max(6.0, cfg.africa_priority_weight * 0.5)
        ranking_reason.append("Private-sector notice without strong F2 signals was downgraded.")

    if geo["geographic_scope"] == "Other Region" and not geo["public_sector_signal"] and not strong_domain_fit:
        geo_adjustment -= max(8.0, cfg.africa_priority_weight * 0.65)
        ranking_reason.append("Non-African notice with weak public-sector or workflow fit was downgraded.")

    if geo["downgrade_hits"] and geo["geographic_scope"] != "Africa":
        geo_adjustment -= 8.0
        ranking_reason.append("Generic consultancy, staffing, hardware, or construction language reduced rank.")

    if geo["source_group"] == "aggregator":
        geo_adjustment -= 2.0
        ranking_reason.append("Aggregator source received a small confidence discount.")

    ranking_score = max(0.0, min(100.0, round(fit_score + geo_adjustment, 1)))

    procurement_status = _text(breakdown.get("procurement_status", "open"))
    likely_fit = _text(breakdown.get("likely_fit_for_F2", "uncertain"))
    geo_public_or_donor = geo["public_sector_signal"] or geo["donor_or_multilateral_flag"] or geo["africa_priority_flag"]
    promotion_signals = strong_domain_fit or geo_public_or_donor or bool(geo["enterprise_hits"])
    global_gate_threshold = max(cfg.global_relevance_threshold, cfg.secondary_review_queue_threshold + 8)

    if breakdown.get("excluded") or procurement_status in {"locked", "conditional_nogo"} or likely_fit in {"excluded", "no-go"}:
        recommendation = "NO-GO"
        queue_bucket = "archive"
        recommendation_reason = "Platform constraints or weak strategic fit block pursuit."
    elif pipeline_mode == "global_discovery" and geo["geographic_scope"] != "Africa":
        if not geo_public_or_donor and not strong_domain_fit:
            recommendation = "NO-GO"
            queue_bucket = "archive"
            recommendation_reason = "Global notice lacks the public-sector or F2-domain signals needed for promotion."
        elif fit_score >= global_gate_threshold and promotion_signals:
            recommendation = "GO"
            queue_bucket = "main_shortlist"
            recommendation_reason = "High-confidence global public-sector or donor fit cleared the stricter global gate."
        elif fit_score >= cfg.secondary_review_queue_threshold and promotion_signals:
            recommendation = "REVIEW"
            queue_bucket = "secondary_review"
            recommendation_reason = "Relevant global signal found, but confidence is not strong enough for the main shortlist."
        else:
            recommendation = "NO-GO"
            queue_bucket = "archive"
            recommendation_reason = "Global discovery notice did not clear the relevance threshold."
    else:
        if fit_score >= max(26.0, cfg.global_relevance_threshold - 2.0) and geo_public_or_donor and promotion_signals:
            recommendation = "GO"
            queue_bucket = "main_shortlist"
            recommendation_reason = "Strong F2 fit with clear strategic geography and buyer relevance."
        elif fit_score >= cfg.secondary_review_queue_threshold and promotion_signals:
            recommendation = "REVIEW"
            queue_bucket = "main_shortlist" if geo["africa_priority_flag"] else "secondary_review"
            recommendation_reason = "Potential fit exists, but more qualification is needed before pursuit."
        else:
            recommendation = "NO-GO"
            queue_bucket = "archive"
            recommendation_reason = "Weak fit remains weak even after geography and buyer context are considered."

    relevance_reason = "Relevant to F2 because it aligns with records, workflow, case, citizen-service, or public modernization needs."
    if domains_matched:
        relevance_reason = f"Relevant to F2 because it matched {', '.join(domains_matched[:4])} domains."

    geography_reason = (
        "Classified as Africa-priority because the buyer or implementation context is African."
        if geo["geographic_scope"] == "Africa"
        else "Classified as Africa-targeted from a global source because the opportunity targets African institutions."
        if geo["geographic_scope"] == "Global" and geo["africa_priority_flag"]
        else "Classified as a non-African global opportunity because the source or buyer is global but still institutionally comparable."
        if geo["geographic_scope"] == "Global"
        else "Classified outside the Africa-first default because no African implementation or beneficiary signal was found."
    )

    ranking_summary = " ".join(ranking_reason[:2]) if ranking_reason else "Ranking stayed close to fit score because geography was neutral."
    explainability = {
        "f2_relevance": relevance_reason,
        "geography_context": geography_reason,
        "ranking_reason": ranking_summary,
        "recommendation_reason": recommendation_reason,
    }

    breakdown.update(
        {
            "country": geo["country"],
            "fit_score": round(fit_score, 1),
            "ranking_score": ranking_score,
            "geo_adjustment": round(geo_adjustment, 1),
            "recommendation": recommendation,
            "queue_bucket": queue_bucket,
            "geographic_scope": geo["geographic_scope"],
            "region": geo["region"],
            "africa_priority_flag": geo["africa_priority_flag"],
            "donor_or_multilateral_flag": geo["donor_or_multilateral_flag"],
            "target_beneficiary_region": geo["target_beneficiary_region"],
            "buyer_region": geo["buyer_region"],
            "implementation_region": geo["implementation_region"],
            "source_group": geo["source_group"],
            "source_tags": geo["source_tags"],
            "geo_label": geo["geo_label"],
            "geo_public_sector_signal": geo["public_sector_signal"],
            "geo_private_sector_signal": geo["private_sector_signal"],
            "geo_domain_hits": geo["domain_hits"],
            "geo_donor_hits": geo["donor_hits"],
            "geo_downgrade_hits": geo["downgrade_hits"],
            "ranking_reason_points": ranking_reason,
            "explainability": explainability,
        }
    )
    return ranking_score, breakdown


def recommendation_priority(value: str) -> int:
    mapping = {"GO": 0, "REVIEW": 1, "NO-GO": 2}
    return mapping.get((value or "").strip().upper(), 3)


def shortlist_mode_match(tender: Any, mode: str = "africa") -> bool:
    shortlist_mode = _text(mode) or "africa"
    scope = _text(getattr(tender, "geographic_scope", ""))
    africa_flag = bool(getattr(tender, "africa_priority_flag", False))

    if shortlist_mode == "africa":
        return africa_flag or scope == "africa"
    if shortlist_mode == "global":
        return scope in {"global", "other region"} or (scope == "unknown" and not africa_flag)
    return True


def tender_sort_key(tender: Any) -> Tuple[Any, ...]:
    recommendation = getattr(tender, "recommendation", "") or "REVIEW"
    fit_score = float(getattr(tender, "score", 0) or 0)
    africa_flag = 1 if getattr(tender, "africa_priority_flag", False) else 0
    donor_flag = 1 if getattr(tender, "donor_or_multilateral_flag", False) else 0
    deadline = getattr(tender, "deadline", "") or "9999-12-31"
    created_at = getattr(tender, "created_at", None)
    created_ts = created_at.timestamp() if created_at else 0
    return (
        recommendation_priority(recommendation),
        -fit_score,
        -africa_flag,
        -donor_flag,
        deadline,
        -created_ts,
    )
