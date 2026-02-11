import requests
import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from datetime import datetime, timedelta, timezone
import logging
from io import BytesIO
from flask import current_app
from sqlalchemy.exc import IntegrityError
import urllib3


from app.deadlines import parse_deadline, check_timing_constraints, is_deadline_valid
from app.source_bias import SOURCE_BIAS
from app.categorizer import categorize
from app.learner import learn_keywords
from app.translator import translate_to_english

from app.extensions import db
from app.models import TenderSource, TenderResult
from app.scoring import score_text
from app.source_bias import COUNTRY_MAP
from app.keywords import ALL_KEYWORDS

logger = logging.getLogger(__name__)
logging.getLogger("pypdf").setLevel(logging.ERROR)
logging.getLogger("pypdf._reader").setLevel(logging.ERROR)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)




# Reduced timeout for faster scans
HTTP_TIMEOUT = 4  # seconds
PDF_MAX_BYTES = 1_200_000  # 1.2 MB
PDF_MAX_PAGES = 1
MAX_ANCHORS_PER_SOURCE = 180
MAX_NEW_TENDERS_PER_SOURCE = 12

# Prefer PDF parsing for these high-signal sources (plus any favorites).
PDF_SOURCE_ALLOW = {
    "KAA Procurement",
    "KEMSA Tenders",
    "KENHA Tenders",
    "KRA Tenders",
    "Kenya Power Tenders",
    "KEBS Tenders",
    "ICT Authority",
    "CBK Tenders",
    "Kenya Railways",
    "KPA Tenders",
}

CLOSED_HINTS = [
    "awarded", "award", "awarding", "award notice", "contract award",
    "winner", "winners", "successful bidder", "successful bidders",
    "evaluation", "evaluated", "results", "result", "list of awardees",
    "notice of award", "award of tender", "tender results",
]

LIFECYCLE_HINTS = {
    "awarded": [
        "awarded", "award notice", "contract award", "successful bidder",
        "winners", "winner", "award of tender", "tender results",
    ],
    "clarification": [
        "clarification", "corrigendum", "addendum", "q&a", "questions and answers",
        "extension notice", "deadline extension",
    ],
    "cancelled": [
        "cancelled", "canceled", "withdrawn", "terminated", "annulled",
    ],
    "pre_notice": [
        "prior information notice", "forecast", "pipeline", "upcoming procurement",
    ],
}

GENERIC_TITLE_PATTERNS = [
    "global tenders",
    "govt tenders",
    "government tenders",
    "tenders country",
    "tender notices",
    "procurement notices",
    "view tender",
    "view details",
]

F2_INTENT_TERMS = [
    "document management", "records management", "edms", "edrms",
    "enterprise content management", "ecm", "workflow", "workflow automation",
    "business process management", "bpm", "case management", "complaint management",
    "grievance", "e-filing", "electronic filing", "registry management",
    "digital transformation", "paperless", "digital government", "e-government",
    "citizen portal", "service delivery platform",
]

MIN_RELEVANCE_SCORE = 22


def _utcnow():
    # Keep naive UTC to match DB columns while avoiding utcnow() deprecation.
    return datetime.now(timezone.utc).replace(tzinfo=None)

def _source_country(source_name: str, url: str):
    haystack = f"{source_name} {url}".lower()
    for key, country in COUNTRY_MAP.items():
        if key in haystack:
            return country
    return "Global"


def _source_bias_bonus(source_name: str, url: str):
    haystack = f"{source_name} {url}".lower()
    for key, bonus in SOURCE_BIAS.items():
        if key in haystack:
            return bonus
    return 0


def _has_f2_keywords(text: str) -> bool:
    if not text:
        return False
    t = text.lower()
    return any(kw in t for kw in ALL_KEYWORDS)


def _is_closed_award(text: str) -> bool:
    if not text:
        return False
    t = text.lower()
    return any(hint in t for hint in CLOSED_HINTS)


def _clean_title(raw: str) -> str:
    title = (raw or "").strip()
    if not title:
        return ""
    # Remove metadata tails commonly concatenated on listing cards.
    title = re.split(
        r"\b(?:ref(?:erence)?(?:\s*no\.?)?|deadline|posted|country|office|process)\b",
        title,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0].strip(" -:|")
    title = re.sub(r"\s+", " ", title).strip()
    return title


def _is_generic_title(title: str) -> bool:
    t = (title or "").lower().strip()
    if not t:
        return True
    return any(pat in t for pat in GENERIC_TITLE_PATTERNS)


def _has_f2_intent(text: str) -> bool:
    t = (text or "").lower()
    return any(term in t for term in F2_INTENT_TERMS)


def _classify_lifecycle(text: str) -> str:
    t = (text or "").lower()
    for status, terms in LIFECYCLE_HINTS.items():
        if any(term in t for term in terms):
            return status
    return "open"


def _pdf_text_from_url(url: str) -> str:
    try:
        head = requests.head(url, timeout=HTTP_TIMEOUT, allow_redirects=True)
        if "pdf" not in (head.headers.get("Content-Type", "") or "").lower():
            # Not a PDF (or server doesn't say) - still try cautiously.
            pass
        content_length = head.headers.get("Content-Length")
        if content_length and int(content_length) > PDF_MAX_BYTES:
            return ""
    except Exception:
        # HEAD often fails on some servers; fall back to GET.
        pass

    try:
        r = requests.get(url, timeout=HTTP_TIMEOUT, stream=True)
        r.raise_for_status()
        data = r.raw.read(PDF_MAX_BYTES + 1)
        if len(data) > PDF_MAX_BYTES:
            return ""
        try:
            from pypdf import PdfReader
        except Exception:
            return ""
        reader = PdfReader(BytesIO(data))
        text_chunks = []
        for page in reader.pages[:PDF_MAX_PAGES]:
            try:
                page_text = page.extract_text() or ""
            except Exception:
                page_text = ""
            if page_text:
                text_chunks.append(page_text)
        return " ".join(text_chunks)
    except Exception:
        return ""


def cleanup_irrelevant_tenders():
    """Remove tenders that are awards/results (closed)."""
    one_month_ago = _utcnow() - timedelta(days=30)
    tenders = TenderResult.query.filter(TenderResult.created_at >= one_month_ago).all()
    removed = 0
    for tender in tenders:
        combined = f"{tender.title} {tender.description} {tender.link}".lower()
        if _is_closed_award(combined):
            db.session.delete(tender)
            removed += 1
    if removed:
        db.session.commit()
        print(f" Removed {removed} non-F2 or closed tenders")


def scan_source(source: TenderSource, app, existing_links=None):
    import time
    import json as json_lib

    new_tenders = []
    t0 = time.time()

    with app.app_context():
        try:
            try:
                html = requests.get(source.url, timeout=HTTP_TIMEOUT, verify=True).text
            except requests.exceptions.SSLError:
                logger.warning("SSL error for %s, retrying without verification", source.name)
                html = requests.get(source.url, timeout=HTTP_TIMEOUT, verify=False).text
        except requests.exceptions.RequestException as e:
            logger.warning("Failed to fetch %s: %s", source.name, str(e)[:50])
            logger.info("%s took %.1fs (failed)", source.name, time.time() - t0)
            return new_tenders

        elapsed = time.time() - t0
        if elapsed > 5:
            logger.info("SLOW source %s took %.1fs", source.name, elapsed)
        else:
            logger.info("Source %s took %.1fs", source.name, elapsed)

        soup = BeautifulSoup(html, "html.parser")
        existing = set(existing_links or ())
        seen = set()
        seen_titles = set()

        nav_patterns = {
            "about us", "about", "contact us", "contact", "home", "login", "sign in", "register",
            "search", "help", "faq", "privacy", "terms", "cookie", "accessibility",
            "menu", "navigation", "sitemap", "site map", "back to top", "read more", "learn more",
            "click here", "view all", "see all", "show more", "load more",
            "who we are", "what we do", "how we work", "our work", "our team", "our partners",
            "our office", "our history", "our mission", "our vision", "our values",
            "careers", "jobs", "employment", "vacancies", "work with us", "join us",
            "how we buy", "what we buy", "how to apply", "how to register", "how to submit",
            "qualifications", "eligibility", "supplier", "vendor", "guidance", "guidelines",
            "resources", "training", "certification", "statistics", "reports", "annual report",
            "code of conduct", "protest", "sanctions", "policies", "procedures",
            "guiding principles", "strategy", "sustainable", "framework",
            "facebook", "twitter", "linkedin", "instagram", "youtube", "share", "follow us",
            "subscribe", "newsletter", "email us", "call us",
            "press release", "news", "blog", "article", "publication", "brochure",
            "annual report", "quarterly report", "financial report",
        }

        tender_terms = [
            "tender", "rfp", "rfq", "procurement", "bid", "invitation to bid",
            "request for proposal", "request for quotation", "expression of interest",
            "eoi", "notice of", "call for", "solicitation",
        ]
        url_terms = [
            "tender", "tenders", "procurement", "bid", "bids", "rfp", "rfq",
            "solicitation", "notice", "notices", "opportunity", "opportunities",
            "contract", "contracts", "purchase", "tender-detail", "bid-detail",
        ]
        detail_url_terms = [
            "/tender/", "/tenders/", "/procurement/", "/opportunity/", "/opportunities/",
            "/notice/", "/notices/", "/bid/", "/bids/", "/solicitation/",
            "tender-detail", "bid-detail", "/detail", "/document/", "/docs/", "/download/",
            "rfp", "rfq",
        ]
        ref_code = re.compile(r"\b[A-Z]{2,}[-/ ]?\d{2,}\b")
        ref_terms = [
            "ref", "reference", "ref.", "tender no", "rfp no", "rfq no",
            "procurement ref", "bid no", "request no",
        ]
        date_terms = [
            "deadline", "closing date", "submission deadline", "due date",
            "closing time", "submission date", "posted", "published",
        ]
        generic_titles = {
            "tenders", "tender", "global tenders", "govt tenders", "government tenders",
            "tenders country", "tender notices", "procurement notices", "opportunities",
        }
        closed_hints = CLOSED_HINTS

        for idx, a in enumerate(soup.find_all("a", href=True)):
            if idx >= MAX_ANCHORS_PER_SOURCE:
                break
            if len(new_tenders) >= MAX_NEW_TENDERS_PER_SOURCE:
                break
            try:
                href = a.get("href", "").strip()
                if not href or href.startswith("#") or href.startswith("javascript"):
                    continue

                link = urljoin(source.url, href)
                if not link.startswith(("http://", "https://")):
                    continue

                if link in existing or link in seen:
                    continue

                raw_title = a.get_text(" ", strip=True)
                parent_text = a.parent.get_text(" ", strip=True) if a.parent else ""
                aria_title = a.get("title", "") or a.get("aria-label", "")
                context_text = " ".join([raw_title, aria_title, parent_text]).strip()

                if not context_text:
                    continue

                # If the anchor text is too short (e.g., "View", "Details"), fall back to row text.
                title = _clean_title(raw_title)
                if not title or len(title) < 8:
                    title = _clean_title(parent_text if len(parent_text) >= 20 else raw_title)
                if not title or len(title) < 8:
                    continue

                lower_title = title.lower()
                title_key = re.sub(r"[^a-z0-9]+", " ", lower_title).strip()
                if lower_title.strip() in generic_titles or _is_generic_title(lower_title):
                    continue
                if any(pat in lower_title for pat in nav_patterns):
                    continue
                if not title_key or len(title_key) < 18:
                    continue
                if title_key in seen_titles:
                    continue

                description = parent_text if parent_text and parent_text != title else ""
                base_combined = f"{title} {description} {aria_title}".strip()
                combined = base_combined

                combined_lower = combined.lower()
                link_lower = link.lower()
                is_pdf = link_lower.endswith(".pdf")
                allow_pdf = source.favorite or source.name in PDF_SOURCE_ALLOW
                if is_pdf and allow_pdf:
                    pdf_text = _pdf_text_from_url(link)
                    if pdf_text:
                        combined = f"{combined} {pdf_text}".strip()
                        combined_lower = combined.lower()
                        # If title is generic, try to pull a better title from PDF text.
                        if len(title) < 20:
                            title = pdf_text.strip().split("\n")[0][:200] or title
                            lower_title = title.lower()

                has_tender_term = any(term in combined_lower for term in tender_terms)
                has_url_term = any(term in link_lower for term in url_terms)
                has_detail_url = any(term in link_lower for term in detail_url_terms)
                has_closed_hint = any(term in combined_lower for term in closed_hints) or any(
                    term in link_lower for term in closed_hints
                )
                lifecycle_status = _classify_lifecycle(f"{combined} {link}")

                deadline = parse_deadline(combined)
                has_ref = any(term in combined_lower for term in ref_terms) or any(ch.isdigit() for ch in lower_title)
                has_date_hint = any(term in combined_lower for term in date_terms)
                has_ref_code = bool(ref_code.search(combined))

                if not (has_tender_term or has_detail_url or has_ref_code or deadline):
                    continue
                if not deadline and not has_ref_code and not has_detail_url and not (has_ref and has_date_hint):
                    # Skip generic listings without concrete tender signals.
                    continue
                if has_closed_hint:
                    # Skip award/results and already-closed material.
                    continue
                if lifecycle_status in {"awarded", "clarification", "cancelled"}:
                    # Focus on active opportunities, not post-award or admin updates.
                    continue
                if is_pdf and not deadline and not has_ref_code and not has_detail_url:
                    # Avoid dumping generic PDFs without tender-specific signals.
                    continue
                if deadline and not is_deadline_valid(deadline):
                    continue

                score, matched, scoring_breakdown = score_text(title, description)
                try:
                    breakdown = json_lib.loads(scoring_breakdown)
                except Exception:
                    breakdown = {}
                keywords_found = int(breakdown.get("keywords_found", 0) or 0)
                domains_matched = breakdown.get("domains_matched", []) or []
                likely_fit = breakdown.get("likely_fit_for_F2", "uncertain")
                procurement_status = breakdown.get("procurement_status", "open")

                # Hard relevance gates to avoid generic/non-F2 results flooding UI.
                if score <= 0 or keywords_found == 0:
                    continue
                if likely_fit in {"excluded", "no-go"}:
                    continue
                if procurement_status in {"locked", "conditional_nogo"} and not source.favorite:
                    continue
                if likely_fit == "uncertain" and score < 45:
                    continue
                if not deadline and likely_fit in {"uncertain", "discuss"} and score < 60:
                    continue
                if not deadline and keywords_found < 3 and score < 65:
                    continue
                if not _has_f2_intent(base_combined) and len(domains_matched) < 2 and score < MIN_RELEVANCE_SCORE:
                    continue

                bonus = _source_bias_bonus(source.name, link)
                if bonus:
                    score = min(100, score + bonus)
                    breakdown["source_bias"] = bonus
                    breakdown["final_score"] = score
                    scoring_breakdown = json_lib.dumps(breakdown)

                category, _, confidence = categorize(title, description)
                # Keep scans fast; translation is handled in throttled post-scan pass.
                title_translated = title
                description_translated = description if description else ""

                country = _source_country(source.name, link)
                inferred_domains = json_lib.dumps(breakdown.get("domains_matched", []))
                priority_level = breakdown.get("priority", "LOW")
                likely_fit = breakdown.get("likely_fit_for_F2", "uncertain")
                procurement_status = breakdown.get("procurement_status", "open")
                requires_qualification = bool(breakdown.get("requires_qualification", False))
                qualification_reason = breakdown.get("qualification_reason", "")
                platform_signals = json_lib.dumps(breakdown.get("microsoft_commitment_signals", []))

                tender = TenderResult(
                    title=title,
                    title_translated=title_translated,
                    link=link,
                    description=description,
                    description_translated=description_translated,
                    score=score,
                    keywords_matched=matched,
                    scoring_breakdown=scoring_breakdown,
                    category=category,
                    confidence=confidence,
                    deadline=deadline or "",
                    buyer=source.name,
                    country=country,
                    inferred_domains=inferred_domains,
                    priority_level=priority_level,
                    likely_fit_for_f2=likely_fit,
                    procurement_status=procurement_status,
                    requires_qualification=requires_qualification,
                    qualification_reason=qualification_reason,
                    platform_commitment_signals=platform_signals,
                    timing_status=lifecycle_status,
                    source_id=source.id,
                )
                db.session.add(tender)
                new_tenders.append(tender)
                seen.add(link)
                seen_titles.add(title_key)
            except Exception:
                logger.exception("Skipping link from %s due to parsing error", source.name)
                continue

        if new_tenders:
            try:
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                logger.debug("Integrity error while saving %s results; duplicates were skipped", source.name)
                return []
            except Exception as e:
                db.session.rollback()
                logger.debug("Unexpected DB error while saving %s results: %s", source.name, str(e)[:120])
                return []

        return [t.id for t in new_tenders if getattr(t, "id", None)]

    return []


def cleanup_old_tenders():
    """Remove tenders older than 1 month"""
    one_month_ago = _utcnow() - timedelta(days=30)
    old_tenders = TenderResult.query.filter(TenderResult.created_at < one_month_ago).all()
    
    if old_tenders:
        count = len(old_tenders)
        for tender in old_tenders:
            db.session.delete(tender)
        db.session.commit()
        print(f"  Removed {count} tender(s) older than 1 month")
    else:
        print(" No old tenders to remove")


def run_scan(flask_app=None, max_sources=15, scan_timeout_seconds=None):
    """
    Scan sources for tenders and return newly added tenders.
    OPTIMIZED: Uses parallel scanning with 15 workers for faster scans.
    
    Returns:
        List of newly added TenderResult objects
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed
    import time
    
    start_time = time.time()
    
    # First, clean up old and irrelevant tenders
    cleanup_old_tenders()
    cleanup_irrelevant_tenders()
    
    sources = TenderSource.query.filter_by(active=True).all()
    # Prioritize favorite/high-value sources first for faster actionable scans.
    sources = sorted(sources, key=lambda s: (not bool(s.favorite), (s.name or "").lower()))
    if max_sources is not None:
        try:
            max_sources_int = int(max_sources)
        except Exception:
            max_sources_int = 15
        if max_sources_int > 0:
            sources = sources[:max_sources_int]
    
    if not sources:
        print("  No active sources found. Add sources and mark them as active to start scanning.")
        return []
    
    all_new_ids = []
    
    # Resolve Flask app (Streamlit passes it explicitly).
    if flask_app is None:
        flask_app = current_app._get_current_object()

    # Snapshot existing links once to avoid re-querying for every source.
    existing_links = {link for (link,) in db.session.query(TenderResult.link).all()}

    # Scan sources in parallel.
    if sources:
        print(f"\n FAST PARALLEL scan: {len(sources)} sources with 15 workers...")
        if scan_timeout_seconds is None:
            if max_sources is None:
                scan_timeout_seconds = 120
            else:
                scan_timeout_seconds = max(30, min(90, int(max_sources) * 4))
        
        executor = ThreadPoolExecutor(max_workers=15)
        try:
            future_to_source = {executor.submit(scan_source, src, flask_app, existing_links): src for src in sources}

            completed = 0
            try:
                for future in as_completed(future_to_source, timeout=scan_timeout_seconds):
                    source = future_to_source[future]
                    completed += 1
                    try:
                        new_ids = future.result()
                        if new_ids:
                            all_new_ids.extend(new_ids)
                            print(f" [{completed}/{len(sources)}] {source.name}: {len(new_ids)} new")
                    except Exception as e:
                        print(f" [{completed}/{len(sources)}] {source.name}: {str(e)[:30]}")
            except Exception:
                # Timeout reached - return completed results immediately.
                for future in future_to_source:
                    if not future.done():
                        future.cancel()
                print(f" Scan timeout reached after {scan_timeout_seconds}s; returning partial results.")
        finally:
            # Critical: do not wait for hung workers after timeout.
            executor.shutdown(wait=False, cancel_futures=True)

        print("\n--- SLOW SOURCES REPORT ---")
        # Print slow sources summary
        # (Already printed per-source above)
        print("(Any source above marked  SLOW is a bottleneck)")
    
    elapsed = time.time() - start_time
    print(f" Scan complete in {elapsed:.1f}s! Found {len(all_new_ids)} new tenders.")

    fresh_tenders = []
    if all_new_ids:
        # Re-query in the main app context to avoid detached-session issues.
        with flask_app.app_context():
            fresh_tenders = TenderResult.query.filter(TenderResult.id.in_(all_new_ids)).all()
    
    # Send push notifications for new high-score tenders
    if fresh_tenders:
        try:
            from app.push_notifications import PushNotificationService
            
            push_service = PushNotificationService(flask_app)
            push_service.notify_new_tenders(fresh_tenders)
        except Exception as e:
            print(f" Push notification failed: {e}")
    
    return fresh_tenders




