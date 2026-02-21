from __future__ import annotations

import logging
import os
import re
import threading
import warnings
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from io import BytesIO
from typing import Dict, Iterable, List, Optional
from urllib.parse import urljoin, urlparse

import requests
import urllib3
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
from flask import current_app
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


from app.deadlines import parse_deadline, is_deadline_valid, extract_dates
from app.source_bias import SOURCE_BIAS
from app.categorizer import categorize
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.auto_discovery import init_discovery, get_discovery_engine
from app.models import TenderSource, TenderResult
from app.scoring import score_text
from app.source_bias import COUNTRY_MAP
from app.keywords import ALL_KEYWORDS

logger = logging.getLogger(__name__)
logging.getLogger("pypdf").setLevel(logging.ERROR)
logging.getLogger("pypdf._reader").setLevel(logging.ERROR)
logging.getLogger("urllib3.connectionpool").setLevel(logging.ERROR)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)




# Networking
# Use a slightly more forgiving read timeout (many tender portals are slow) while
# keeping connect fast. This improves recall without materially hurting scan speed
# thanks to parallelism.
HTTP_CONNECT_TIMEOUT = int(3)
HTTP_READ_TIMEOUT = int(10)
HTTP_TIMEOUT = (HTTP_CONNECT_TIMEOUT, HTTP_READ_TIMEOUT)
AUTO_DISCOVERY_TIMEOUT_SECONDS = int(os.getenv("AUTO_DISCOVERY_TIMEOUT_SECONDS", "25"))
AUTO_DISCOVERY_MAX_QUERIES = int(os.getenv("AUTO_DISCOVERY_MAX_QUERIES", "4"))

# PDF limits (adaptive parsing uses up to PDF_MAX_PAGES pages)
PDF_MAX_BYTES = 2_000_000  # 2 MB
PDF_MAX_PAGES = 2
MAX_ANCHORS_PER_SOURCE = 180
MAX_NEW_TENDERS_PER_SOURCE = 12
DETAIL_FETCH_MAX_PER_SOURCE = 16
DETAIL_TEXT_MAX_CHARS = 8000
DETAIL_PDF_LINK_LIMIT = 2
STALE_NOTICE_MAX_AGE_DAYS = int(os.getenv("STALE_NOTICE_MAX_AGE_DAYS", "120"))

# Default scan parallelism (safe for SQLite because we avoid DB writes in threads)
DEFAULT_SCAN_WORKERS = 15

USER_AGENT = "TenderWatch/1.3 (+https://tenderwatch.local; contact: ops@tenderwatch.local)"
DEFAULT_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

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

EXPIRED_NOTICE_HINTS = [
    "deadline passed",
    "closing date passed",
    "submission closed",
    "bids are closed",
    "bid closed",
    "tender closed",
    "closed tender",
    "no longer accepting",
    "expired tender",
    "opportunity closed",
    "this tender is closed",
]

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

NON_OPPORTUNITY_TITLE_HINTS = [
    "procurement plans",
    "procurement plan",
    "procurement reports",
    "report",
    "reports",
    "guidance",
    "guideline",
    "guidelines",
    "manual",
    "policy",
    "procedure",
    "strategic plan",
    "master plan",
    "masterplan",
    "service charter",
    "tender board decisions",
    "board decisions",
    "available bidding opportunities",
    "public procurement information portal",
    "government procurement portal",
    "quantum etendering guidance",
    "view projects",
    "tenders and proposal",
]

OPPORTUNITY_TITLE_HINTS = [
    "request for",
    "invitation",
    "tender advert",
    "tender document",
    "expression of interest",
    "eoi",
    "rfp",
    "rfq",
    "tender no",
    "bid no",
    "lot ",
    "submission deadline",
]

LISTING_PATH_TERMS = {
    "home",
    "tender",
    "tenders",
    "procurement",
    "opportunity",
    "opportunities",
    "notice",
    "notices",
    "publications",
    "publication",
    "resources",
    "guidance",
    "guidelines",
    "procurementplans",
    "plans",
}

GENERIC_HOST_BLOCKLIST = {
    "youtube.com",
    "www.youtube.com",
    "youtu.be",
}

F2_INTENT_TERMS = [
    "document management", "records management", "edms", "edrms",
    "enterprise content management", "ecm", "workflow", "workflow automation",
    "business process management", "bpm", "case management", "complaint management",
    "grievance", "e-filing", "electronic filing", "registry management",
    "digital", "digital system", "digital systems",
    "digital transformation", "digitalization", "digitalisation", "digitization", "digitisation",
    "paperless", "digital government", "e-government", "ict", "information system",
    "citizen portal", "service delivery platform",
]

MIN_RELEVANCE_SCORE = 12

# Broader discovery terms for high-signal favorite sources.
# These are intentionally narrower than generic gov words to avoid noisy capture.
BROAD_DISCOVERY_TERMS = [
    "digital", "digitization", "digitisation", "digitalization", "digitalisation",
    "digital system", "digital systems", "ict", "information system", "information systems",
    "software", "application", "system implementation", "automation",
    "platform", "portal", "data management", "enterprise system",
]
# Very broad terms that can appear on unrelated public works notices.
# We only accept broad fallback when at least one stronger term is present,
# or when multiple broad indicators co-occur.
WEAK_BROAD_DISCOVERY_TERMS = {
    "digital",
    "digitization",
    "digitisation",
    "digitalization",
    "digitalisation",
    "ict",
    "software",
    "platform",
}


def _has_keyword_hint(text: str) -> bool:
    hay = (text or "").lower()
    if not hay:
        return False
    for kw in ALL_KEYWORDS:
        k = (kw or "").strip().lower()
        if len(k) < 4:
            continue
        if k in hay:
            return True
    return False


# -----------------------------------------------------------------------------
# Parsing heuristics (module-level to avoid re-allocating per-source)
# -----------------------------------------------------------------------------

NAV_PATTERNS = {
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
    "quarterly report", "financial report",
}

TENDER_TERMS = [
    "tender", "rfp", "rfq", "procurement", "bid", "invitation to bid",
    "request for proposal", "request for quotation", "expression of interest",
    "eoi", "notice of", "call for", "solicitation",
]

URL_TERMS = [
    "tender", "tenders", "procurement", "bid", "bids", "rfp", "rfq",
    "solicitation", "notice", "notices", "opportunity", "opportunities",
    "contract", "contracts", "purchase", "tender-detail", "bid-detail",
]

DETAIL_URL_TERMS = [
    "/tender/", "/tenders/", "/procurement/", "/opportunity/", "/opportunities/",
    "/notice/", "/notices/", "/bid/", "/bids/", "/solicitation/",
    "tender-detail", "bid-detail", "/detail", "/document/", "/docs/", "/download/",
    "rfp", "rfq",
]

REF_CODE_RE = re.compile(r"\b[A-Z]{2,}[-/ ]?\d{2,}\b", flags=re.IGNORECASE)

REF_TERMS = [
    "ref", "reference", "ref.", "tender no", "rfp no", "rfq no",
    "procurement ref", "bid no", "request no",
]

DATE_TERMS = [
    "deadline", "closing date", "submission deadline", "due date",
    "closing time", "submission date", "posted", "published",
]

GENERIC_TITLES = {
    "tenders", "tender", "global tenders", "govt tenders", "government tenders",
    "tenders country", "tender notices", "procurement notices", "opportunities",
}


@dataclass(frozen=True)
class SourceInfo:
    """A thread-safe snapshot of TenderSource fields used during scans."""

    id: int
    name: str
    url: str
    favorite: bool = False


def _utcnow():
    # Keep naive UTC to match DB columns while avoiding utcnow() deprecation.
    return datetime.now(timezone.utc).replace(tzinfo=None)

_COUNTRY_BY_CCTLD = {
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
    ".bw": "Botswana",
    ".mz": "Mozambique",
    ".mw": "Malawi",
    ".na": "Namibia",
    ".sn": "Senegal",
    ".ci": "Ivory Coast",
    ".cm": "Cameroon",
    ".ma": "Morocco",
    ".tn": "Tunisia",
    ".eg": "Egypt",
    ".dz": "Algeria",
    ".ao": "Angola",
    ".zw": "Zimbabwe",
    ".mu": "Mauritius",
}


def _country_from_url(url: str) -> str:
    host = (urlparse(url).netloc or "").lower().strip()
    if not host:
        return ""
    if host.startswith("www."):
        host = host[4:]

    for suffix, country in _COUNTRY_BY_CCTLD.items():
        if host.endswith(suffix):
            return country

    if "afdb.org" in host or "trademarkafrica.com" in host:
        return "Africa Regional"
    return ""


def _source_country(source_name: str, url: str):
    # 1) Prefer domain-based country detection to avoid keyword collisions
    # (example: "ppra" exists in Kenya and Tanzania contexts).
    from_url = _country_from_url(url)
    if from_url:
        return from_url

    # 2) Fallback to source/name keyword map.
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


def _looks_like_listing_or_home_link(link: str) -> bool:
    parsed = urlparse(link or "")
    host = (parsed.netloc or "").lower().strip()
    if host in GENERIC_HOST_BLOCKLIST:
        return True

    path = (parsed.path or "").strip("/").lower()
    if path.endswith(".pdf"):
        return False
    if not path:
        return True

    tokens = [tok for tok in path.split("/") if tok]
    if not tokens:
        return True
    if len(tokens) == 1 and tokens[0] in LISTING_PATH_TERMS:
        return True
    if len(tokens) == 2 and tokens[0] in {"home", "en"} and tokens[1] in LISTING_PATH_TERMS:
        return True
    if len(tokens) <= 2 and tokens[-1] in {"tenders", "procurement", "opportunities", "publications"}:
        return True
    return False


def _is_non_opportunity_title(title: str) -> bool:
    t = (title or "").lower().strip()
    if not t:
        return True
    has_non_opportunity_hint = any(h in t for h in NON_OPPORTUNITY_TITLE_HINTS)
    has_opportunity_hint = any(h in t for h in OPPORTUNITY_TITLE_HINTS)
    return has_non_opportunity_hint and not has_opportunity_hint


def _has_f2_intent(text: str) -> bool:
    t = (text or "").lower()
    return any(term in t for term in F2_INTENT_TERMS)


def _broad_discovery_hits(text: str) -> List[str]:
    t = (text or "").lower()
    hits = []
    for term in BROAD_DISCOVERY_TERMS:
        if term in t:
            hits.append(term)
    # de-dupe while preserving order
    seen = set()
    out = []
    for h in hits:
        if h not in seen:
            seen.add(h)
            out.append(h)
    return out


def _broad_hits_pass_quality(hits: List[str]) -> bool:
    if not hits:
        return False
    strong_hits = [h for h in hits if h not in WEAK_BROAD_DISCOVERY_TERMS]
    if strong_hits:
        return True
    weak_unique = list(dict.fromkeys(h for h in hits if h in WEAK_BROAD_DISCOVERY_TERMS))
    return len(weak_unique) >= 2


def _classify_lifecycle(text: str) -> str:
    t = (text or "").lower()
    for status, terms in LIFECYCLE_HINTS.items():
        if any(term in t for term in terms):
            return status
    return "open"


def _looks_expired_or_stale(text: str, deadline: str, lifecycle_status: str) -> bool:
    """Hard filter for stale/closed notices that slip past keyword checks."""
    today = _utcnow().date()
    t = (text or "").lower()

    if lifecycle_status in {"awarded", "cancelled"}:
        return True

    if any(h in t for h in EXPIRED_NOTICE_HINTS):
        return True

    if deadline:
        try:
            parsed_deadline = datetime.strptime(deadline, "%Y-%m-%d").date()
            if parsed_deadline < today:
                return True
        except Exception:
            pass

    # When deadline is missing, reject notices that only reference old dates.
    if not deadline:
        dates = extract_dates(t)
        if dates:
            latest_seen = max(dates)
            age_days = (today - latest_seen).days
            if age_days > STALE_NOTICE_MAX_AGE_DAYS:
                return True

    return False


def _make_http_session() -> requests.Session:
    """Create a resilient requests Session (connection pooling + small retries).

    Note: A Session is NOT thread-safe; each thread should build its own.
    """

    session = requests.Session()
    session.headers.update(DEFAULT_HEADERS)

    # Retry on transient errors + rate limiting.
    try:
        retry = Retry(
            total=2,
            connect=1,
            read=1,
            backoff_factor=0.3,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset(["GET", "HEAD"]),
        )
    except TypeError:
        # urllib3 < 1.26 uses method_whitelist
        retry = Retry(
            total=2,
            connect=1,
            read=1,
            backoff_factor=0.3,
            status_forcelist=(429, 500, 502, 503, 504),
            method_whitelist=frozenset(["GET", "HEAD"]),
        )

    adapter = HTTPAdapter(max_retries=retry, pool_connections=16, pool_maxsize=16)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


def _fetch_html(url: str, session: requests.Session) -> str:
    """Fetch HTML with a TLS-verify fallback for misconfigured portals."""

    try:
        resp = session.get(url, timeout=HTTP_TIMEOUT, verify=True)
    except requests.exceptions.SSLError:
        logger.warning("SSL error for %s, retrying without verification", url)
        resp = session.get(url, timeout=HTTP_TIMEOUT, verify=False)
    # Do not raise_for_status: some portals return HTML error pages that still
    # include links (useful for navigation to tenders).
    return resp.text or ""


_PDF_TEXT_CACHE: Dict[str, str] = {}
_PDF_CACHE_LOCK = threading.Lock()


def _pdf_text_from_url(url: str, session: Optional[requests.Session] = None) -> str:
    """Best-effort PDF text extraction (bounded by size + pages).

    Caches extracted text by URL for the duration of the process.
    """

    if not url:
        return ""

    with _PDF_CACHE_LOCK:
        cached = _PDF_TEXT_CACHE.get(url)
    if cached is not None:
        return cached

    s = session or _make_http_session()

    # HEAD is cheap when supported; use it to reject huge PDFs.
    try:
        try:
            head = s.head(url, timeout=HTTP_TIMEOUT, allow_redirects=True, verify=True)
        except requests.exceptions.SSLError:
            head = s.head(url, timeout=HTTP_TIMEOUT, allow_redirects=True, verify=False)
        content_length = head.headers.get("Content-Length")
        if content_length and int(content_length) > PDF_MAX_BYTES:
            with _PDF_CACHE_LOCK:
                _PDF_TEXT_CACHE[url] = ""
            return ""
    except Exception:
        # HEAD frequently fails; continue with a bounded GET.
        pass

    try:
        try:
            r = s.get(url, timeout=HTTP_TIMEOUT, stream=True, verify=True)
        except requests.exceptions.SSLError:
            r = s.get(url, timeout=HTTP_TIMEOUT, stream=True, verify=False)

        if not r.ok:
            with _PDF_CACHE_LOCK:
                _PDF_TEXT_CACHE[url] = ""
            return ""

        # Bounded read
        buf = bytearray()
        for chunk in r.iter_content(chunk_size=64 * 1024):
            if not chunk:
                continue
            buf.extend(chunk)
            if len(buf) > PDF_MAX_BYTES:
                with _PDF_CACHE_LOCK:
                    _PDF_TEXT_CACHE[url] = ""
                return ""

        try:
            from pypdf import PdfReader
        except Exception:
            with _PDF_CACHE_LOCK:
                _PDF_TEXT_CACHE[url] = ""
            return ""

        reader = PdfReader(BytesIO(bytes(buf)))
        text_chunks: List[str] = []

        # Extract a small number of pages for speed; many notices put the key
        # info (title + deadline) on the first 1–2 pages.
        for page in reader.pages[:PDF_MAX_PAGES]:
            try:
                page_text = page.extract_text() or ""
            except Exception:
                page_text = ""
            if page_text:
                text_chunks.append(page_text)

        out = " ".join(text_chunks).strip()
        with _PDF_CACHE_LOCK:
            _PDF_TEXT_CACHE[url] = out
        return out
    except Exception:
        with _PDF_CACHE_LOCK:
            _PDF_TEXT_CACHE[url] = ""
        return ""


def _extract_pdf_links(base_url: str, soup: BeautifulSoup) -> List[str]:
    links: List[str] = []
    seen: set[str] = set()
    for a in soup.find_all("a", href=True):
        href = (a.get("href") or "").strip()
        if not href:
            continue
        full = urljoin(base_url, href).split("#")[0].strip()
        if not full:
            continue
        low = full.lower()
        is_pdf_link = (
            low.endswith(".pdf")
            or ".pdf?" in low
            or ".pdf#" in low
            or "format=pdf" in low
            or "download=pdf" in low
        )
        if not is_pdf_link or full in seen:
            continue
        seen.add(full)
        links.append(full)
        if len(links) >= DETAIL_PDF_LINK_LIMIT:
            break
    return links


def _detail_context(link: str, session: requests.Session) -> Dict[str, str]:
    """Fetch detail page/PDF context to improve deadline extraction.

    Returns dict with keys:
      text: extracted detail text (possibly empty)
      deadline: parsed deadline from detail/PDF text (possibly empty)
      pdf_text: any extracted PDF text (possibly empty)
    """
    out = {"text": "", "deadline": "", "pdf_text": ""}
    if not link:
        return out

    low = link.lower()
    is_pdf = (
        low.endswith(".pdf")
        or ".pdf?" in low
        or ".pdf#" in low
        or "format=pdf" in low
        or "download=pdf" in low
    )

    # Direct PDF detail URL.
    if is_pdf:
        pdf_text = (_pdf_text_from_url(link, session=session) or "")[:DETAIL_TEXT_MAX_CHARS]
        out["pdf_text"] = pdf_text
        out["text"] = pdf_text
        out["deadline"] = parse_deadline(pdf_text) or ""
        return out

    # HTML detail page.
    html = _fetch_html(link, session=session)
    if not html:
        return out

    try:
        soup = BeautifulSoup(html, "lxml")
    except Exception:
        soup = BeautifulSoup(html, "html.parser")

    # Prefer semantically rich containers first.
    text_blocks: List[str] = []
    for selector in ("main", "article", "section"):
        for node in soup.select(selector):
            t = node.get_text(" ", strip=True)
            if t and len(t) >= 80:
                text_blocks.append(t)
                if len(" ".join(text_blocks)) >= DETAIL_TEXT_MAX_CHARS:
                    break
        if len(" ".join(text_blocks)) >= DETAIL_TEXT_MAX_CHARS:
            break

    if not text_blocks:
        body = soup.body.get_text(" ", strip=True) if soup.body else soup.get_text(" ", strip=True)
        if body:
            text_blocks = [body]

    detail_text = " ".join(text_blocks)
    detail_text = re.sub(r"\s+", " ", detail_text).strip()[:DETAIL_TEXT_MAX_CHARS]
    out["text"] = detail_text
    out["deadline"] = parse_deadline(detail_text) or ""

    # If deadline still missing, inspect linked PDFs on detail page.
    if not out["deadline"]:
        for pdf_link in _extract_pdf_links(link, soup):
            pdf_text = (_pdf_text_from_url(pdf_link, session=session) or "")[:DETAIL_TEXT_MAX_CHARS]
            if pdf_text:
                out["pdf_text"] = pdf_text
                out["deadline"] = parse_deadline(pdf_text) or ""
                if out["deadline"]:
                    break

    return out


def cleanup_irrelevant_tenders():
    """Remove tenders that are awards/results, expired, or stale."""
    one_month_ago = _utcnow() - timedelta(days=30)
    tenders = TenderResult.query.filter(TenderResult.created_at >= one_month_ago).all()
    removed = 0
    for tender in tenders:
        combined = f"{tender.title} {tender.description} {tender.link}".lower()
        lifecycle = (tender.timing_status or "open").strip().lower()
        deadline = (tender.deadline or "").strip()
        if _is_closed_award(combined) or _looks_expired_or_stale(combined, deadline, lifecycle):
            db.session.delete(tender)
            removed += 1
    if removed:
        db.session.commit()
        print(f" Removed {removed} non-F2 or closed tenders")


def scan_source(
    source: SourceInfo,
    existing_links: Optional[Iterable[str]] = None,
    max_new_per_source: int = MAX_NEW_TENDERS_PER_SOURCE,
    discovery_mode: str = "f2_ranked",
) -> List[Dict]:
    """Scan a single source URL and return candidate tender rows.

    Important: This function does **not** write to the database.
    We keep it thread-safe + SQLite-friendly by doing all DB writes in the main thread.
    """

    import json as json_lib
    import time

    t0 = time.time()
    session = _make_http_session()

    try:
        html = _fetch_html(source.url, session)
    except Exception as e:
        logger.warning("Failed to fetch %s: %s", source.name, str(e)[:120])
        logger.info("%s took %.1fs (failed)", source.name, time.time() - t0)
        return []

    # Parser choice: lxml is faster + more forgiving, but fall back safely.
    try:
        soup = BeautifulSoup(html, "lxml")
    except Exception:
        soup = BeautifulSoup(html, "html.parser")

    existing = existing_links if isinstance(existing_links, set) else set(existing_links or ())

    manual_like = (discovery_mode or "").strip().lower() == "manual_like"
    # PDF extraction is costly and can trigger repeated SSL retries on unstable hosts.
    # Keep it for known high-signal sources in strict mode; disable in manual-like mode for speed.
    allow_pdf = (source.name in PDF_SOURCE_ALLOW) and (not manual_like)
    seen_links: set[str] = set()
    seen_titles: set[str] = set()
    out: List[Dict] = []
    detail_fetch_count = 0

    for idx, a in enumerate(soup.find_all("a", href=True)):
        if idx >= MAX_ANCHORS_PER_SOURCE:
            break

        try:
            href = (a.get("href") or "").strip()
            if not href or href.startswith("#") or href.lower().startswith("javascript"):
                continue

            link = urljoin(source.url, href).split("#")[0].strip()
            if not link:
                continue

            link_lower = link.lower()
            if any(bad in link_lower for bad in ["/login", "/signin", "/register", "facebook.com", "twitter.com", "linkedin.com"]):
                continue
            if link_lower.endswith((".jpg", ".jpeg", ".png", ".gif", ".svg", ".css", ".js")):
                continue
            if _looks_like_listing_or_home_link(link):
                continue
            if link in existing or link in seen_links:
                continue

            raw_title = a.get_text(" ", strip=True) or ""
            aria_title = (a.get("title") or a.get("aria-label") or "").strip()
            if not raw_title and aria_title:
                raw_title = aria_title

            title = _clean_title(raw_title)
            if not title or len(title) < 8:
                continue

            lower_title = title.lower().strip()
            if lower_title in GENERIC_TITLES or _is_generic_title(title):
                continue
            if _is_non_opportunity_title(lower_title):
                continue
            if any(pat in lower_title for pat in NAV_PATTERNS):
                continue
            if lower_title in seen_titles:
                continue

            # Basic length gate (avoid "View", "Details", "Click here" fragments)
            title_key = re.sub(r"[^a-z0-9]+", " ", lower_title).strip()
            if len(title_key) < 12:
                continue

            # Contextual text (limit to avoid pulling whole-page boilerplate)
            parent_text = ""
            try:
                if a.parent:
                    parent_text = a.parent.get_text(" ", strip=True) or ""
            except Exception:
                parent_text = ""
            if len(parent_text) > 800:
                parent_text = parent_text[:800]

            description = ""
            if aria_title and aria_title.lower() != raw_title.lower():
                description = aria_title
            if len(description) < 20 and parent_text and parent_text.lower() != raw_title.lower():
                description = parent_text

            # Strip nav-like boilerplate from descriptions
            desc_lower = (description or "").lower()
            if any(pat in desc_lower for pat in NAV_PATTERNS):
                description = ""
                desc_lower = ""

            has_url_term = any(term in link_lower for term in URL_TERMS)
            has_detail_url = any(term in link_lower for term in DETAIL_URL_TERMS)
            is_pdf = (
                link_lower.endswith(".pdf")
                or ".pdf?" in link_lower
                or ".pdf#" in link_lower
                or "format=pdf" in link_lower
                or "download=pdf" in link_lower
            )

            base_combined = f"{title} {description} {aria_title} {parent_text}".strip()
            combined_for_deadline = base_combined
            combined_lower = base_combined.lower()

            # Signals for separating real tenders from nav/aggregator links
            has_tender_term = any(term in lower_title for term in TENDER_TERMS) or any(term in combined_lower for term in TENDER_TERMS)
            has_ref_hint = any(term in combined_lower for term in REF_TERMS) or any(ch.isdigit() for ch in lower_title)
            has_date_hint = any(term in combined_lower for term in DATE_TERMS)
            has_ref_code = bool(REF_CODE_RE.search(base_combined))

            deadline = parse_deadline(combined_for_deadline)

            pdf_text = ""
            if allow_pdf and is_pdf:
                pdf_text = _pdf_text_from_url(link, session=session)
                if pdf_text:
                    # Cap size to keep downstream scoring fast
                    pdf_text = pdf_text[:5000]
                    if not deadline:
                        deadline = parse_deadline(f"{combined_for_deadline} {pdf_text}")

            # Read-through pass for hidden deadlines:
            # if listing metadata lacks deadline, inspect detail page/PDF content.
            detail_text = ""
            if not deadline and detail_fetch_count < DETAIL_FETCH_MAX_PER_SOURCE and (has_detail_url or is_pdf):
                detail_fetch_count += 1
                detail = _detail_context(link, session=session)
                detail_text = (detail.get("text") or "")[:DETAIL_TEXT_MAX_CHARS]
                detail_pdf_text = (detail.get("pdf_text") or "")[:DETAIL_TEXT_MAX_CHARS]
                if detail_pdf_text and not pdf_text:
                    pdf_text = detail_pdf_text
                if detail_text:
                    combined_for_deadline = f"{combined_for_deadline} {detail_text}".strip()
                if not deadline:
                    deadline = (detail.get("deadline") or "").strip()

            lifecycle_status = _classify_lifecycle(f"{base_combined} {link}")

            # Extra short-title filter: require at least one strong signal
            if len(title_key) < 18 and not (has_detail_url or deadline or has_ref_code or is_pdf):
                continue

            keyword_hint = _has_keyword_hint(base_combined)

            # Must have at least one strong tender signal.
            # In manual-like mode, allow keyword-led discovery if strong link metadata is missing.
            if not (has_tender_term or has_detail_url or has_ref_code or deadline):
                if not (manual_like and keyword_hint):
                    continue
            if not deadline and not has_ref_code and not has_detail_url and not (has_ref_hint and has_date_hint):
                if not (manual_like and (has_tender_term or keyword_hint)):
                    continue

            full_context = f"{base_combined} {detail_text} {pdf_text} {link}".strip()
            if _is_closed_award(full_context) or lifecycle_status == "awarded":
                continue
            if lifecycle_status in {"clarification", "cancelled"}:
                continue
            if _looks_expired_or_stale(full_context, deadline, lifecycle_status):
                continue

            # Score using richer context (aria/row text + small PDF snippet if present)
            scoring_text = f"{description} {aria_title} {parent_text}".strip()
            if detail_text:
                scoring_text = f"{scoring_text} {detail_text}".strip()
            if pdf_text:
                scoring_text = f"{scoring_text} {pdf_text}".strip()
            score, matched, scoring_breakdown = score_text(title, scoring_text)

            try:
                breakdown = json_lib.loads(scoring_breakdown)
            except Exception:
                breakdown = {}

            keywords_found = int(breakdown.get("keywords_found", 0) or 0)
            domains_matched = breakdown.get("domains_matched", []) or []
            likely_fit = breakdown.get("likely_fit_for_F2", "uncertain")
            procurement_status = breakdown.get("procurement_status", "open")

            if score <= 0 or keywords_found == 0:
                # Do not resurrect tenders explicitly excluded by keyword scoring.
                # Example: construction/civil works notices with incidental "ict" text.
                if bool(breakdown.get("excluded", False)) or (breakdown.get("irrelevant_signals") or []):
                    continue
                # Controlled fallback: keep digital/ICT-adjacent leads from favorite sources.
                broad_hits = _broad_discovery_hits(base_combined)
                allow_broad_capture = has_tender_term or has_ref_code or has_detail_url
                broad_quality_ok = _broad_hits_pass_quality(broad_hits) or (has_tender_term and len(broad_hits) >= 1)
                if allow_broad_capture and broad_quality_ok:
                    score = max(float(score or 0), 18.0 if manual_like else 16.0)
                    keywords_found = len(broad_hits)
                    matched = ", ".join([f"broad:{h}" for h in broad_hits[:4]])
                    breakdown["keywords_found"] = keywords_found
                    breakdown["matched_phrases"] = broad_hits[:8]
                    breakdown["broad_capture"] = True
                    if breakdown.get("likely_fit_for_F2", "uncertain") == "uncertain":
                        breakdown["likely_fit_for_F2"] = "discuss"
                    scoring_breakdown = json_lib.dumps(breakdown)
                    likely_fit = breakdown.get("likely_fit_for_F2", "discuss")
                    procurement_status = breakdown.get("procurement_status", "open")
                else:
                    continue
            if likely_fit in {"excluded", "no-go"} and not manual_like:
                continue
            if procurement_status in {"locked", "conditional_nogo"} and (not source.favorite) and (not manual_like):
                continue
            # Keep more exploratory matches in F2-ranked mode; final quality is handled in UI filters.
            if likely_fit == "uncertain" and score < 14 and not manual_like:
                continue
            strict_no_deadline = (not bool(source.favorite)) and (not manual_like)
            if strict_no_deadline and not deadline and likely_fit in {"uncertain", "discuss"} and score < 24 and not has_tender_term:
                continue
            if strict_no_deadline and not deadline and keywords_found < 2 and score < 30 and not has_tender_term:
                continue
            if (not manual_like) and (not _has_f2_intent(base_combined)) and len(domains_matched) < 2 and score < MIN_RELEVANCE_SCORE:
                continue

            bonus = _source_bias_bonus(source.name, link)
            if bonus:
                score = min(100, score + bonus)
                breakdown["source_bias"] = bonus
                breakdown["final_score"] = score
                scoring_breakdown = json_lib.dumps(breakdown)

            category, _, confidence = categorize(title, scoring_text, source_name=source.name)

            country = _source_country(source.name, link)
            inferred_domains = json_lib.dumps(domains_matched)
            priority_level = breakdown.get("priority", "LOW")
            requires_qualification = bool(breakdown.get("requires_qualification", False))
            qualification_reason = breakdown.get("qualification_reason", "")
            platform_signals = json_lib.dumps(breakdown.get("microsoft_commitment_signals", []))

            out.append(
                {
                    "title": title,
                    "title_translated": title,
                    "link": link,
                    "description": description,
                    "description_translated": description if description else "",
                    "score": float(score),
                    "keywords_matched": matched,
                    "scoring_breakdown": scoring_breakdown,
                    "category": category,
                    "confidence": confidence,
                    "deadline": deadline or "",
                    "publication_date": "",
                    "buyer": source.name,
                    "country": country,
                    "inferred_domains": inferred_domains,
                    "priority_level": priority_level,
                    "likely_fit_for_f2": likely_fit,
                    "procurement_status": procurement_status,
                    "requires_qualification": requires_qualification,
                    "qualification_reason": qualification_reason,
                    "platform_commitment_signals": platform_signals,
                    "timing_status": lifecycle_status,
                    "discovery_method": "manual",
                    "search_query": "",
                    "search_source": source.name,
                    "source_id": source.id,
                }
            )

            seen_links.add(link)
            seen_titles.add(lower_title)
        except Exception as e:
            logger.debug("Skipping link from %s due to parsing error: %s", source.name, str(e)[:120])
            continue

    # Keep the strongest opportunities from each source instead of first-seen links.
    out.sort(
        key=lambda r: (
            float(r.get("score", 0) or 0),
            1 if (r.get("deadline") or "").strip() else 0,
        ),
        reverse=True,
    )
    try:
        per_source_cap = max(1, int(max_new_per_source or MAX_NEW_TENDERS_PER_SOURCE))
    except Exception:
        per_source_cap = MAX_NEW_TENDERS_PER_SOURCE
    out = out[:per_source_cap]

    logger.info("Source %s produced %d candidates in %.1fs", source.name, len(out), time.time() - t0)
    return out


def cleanup_old_tenders():
    """Remove tenders older than 1 month"""
    one_month_ago = _utcnow() - timedelta(days=30)
    try:
        # Single SQL DELETE (much faster than loading rows into Python)
        count = (
            TenderResult.query.filter(TenderResult.created_at < one_month_ago)
            .delete(synchronize_session=False)
        )
        if count:
            db.session.commit()
            print(f"  Removed {count} tender(s) older than 1 month")
    except Exception:
        # Fallback to safe row-by-row delete if the backend doesn't support this well
        db.session.rollback()
        old_tenders = TenderResult.query.filter(TenderResult.created_at < one_month_ago).all()
        if old_tenders:
            count = len(old_tenders)
            for tender in old_tenders:
                db.session.delete(tender)
            db.session.commit()
            print(f"  Removed {count} tender(s) older than 1 month")


def _discover_rows(
    flask_app,
    existing_links: set[str],
    max_candidates: int = 120,
) -> List[Dict]:
    """Discover web-wide opportunities via configured search providers.

    Uses AppSettings credentials when present, and falls back to environment vars.
    Returns candidate rows compatible with run_scan batch insertion.
    """
    with flask_app.app_context():
        from app.models import AppSettings
        import json as json_lib

        settings = AppSettings.query.first()
        if not settings:
            return []

        auto_enabled = bool(getattr(settings, "auto_discovery_enabled", False))
        google_api_key = (getattr(settings, "google_api_key", "") or "").strip()
        google_cx = (getattr(settings, "google_cx", "") or "").strip()
        # We store SerpAPI key in settings.bing_api_key for backward compatibility
        # with existing DB schema/settings forms.
        serpapi_api_key = (getattr(settings, "bing_api_key", "") or "").strip() or (os.getenv("SERPAPI_API_KEY", "") or "").strip()
        bing_api_key = (os.getenv("BING_API_KEY", "") or "").strip()

        # Require explicit enable. Credentials are optional (no-key crawling fallback is supported).
        if not auto_enabled:
            return []

        raw_queries = (getattr(settings, "discovery_queries", "") or "").strip()
        queries: Optional[List[str]] = None
        if raw_queries:
            # Support JSON list and line-based fallback.
            try:
                parsed = json_lib.loads(raw_queries)
                if isinstance(parsed, list):
                    queries = [str(x).strip() for x in parsed if str(x).strip()]
            except Exception:
                line_queries = [q.strip() for q in raw_queries.splitlines() if q.strip()]
                if line_queries:
                    queries = line_queries

        results_per_query = int(getattr(settings, "results_per_query", 10) or 10)
        results_per_query = max(3, min(30, results_per_query))

        # Google CSE is often partially configured and can slow discovery with repeated 4xx errors.
        # Keep it opt-in; SerpAPI/Bing remain primary API paths.
        google_cse_enabled = bool(
            (google_api_key and google_cx)
            and str(os.getenv("ENABLE_GOOGLE_CSE_DISCOVERY", "0")).strip() == "1"
        )
        has_api_credentials = bool(google_cse_enabled or serpapi_api_key or bing_api_key)

        init_discovery(
            google_api_key=(google_api_key if google_cse_enabled else None) or None,
            google_cx=(google_cx if google_cse_enabled else None) or None,
            serpapi_api_key=serpapi_api_key or None,
            bing_api_key=bing_api_key or None,
        )
        engine = get_discovery_engine()
        if not engine:
            return []

        effective_queries = queries
        effective_results_per_query = results_per_query
        if not has_api_credentials:
            # No-key crawler ignores query semantics; run a compact pass for speed.
            effective_queries = [queries[0]] if queries else ["tender procurement"]
            effective_results_per_query = min(results_per_query, 8)
        elif effective_queries:
            # Bound API discovery breadth to keep scan runtime predictable.
            effective_queries = effective_queries[:max(1, AUTO_DISCOVERY_MAX_QUERIES)]
            effective_results_per_query = min(effective_results_per_query, 8)

        discovered = engine.discover_tenders(
            queries=effective_queries,
            results_per_query=effective_results_per_query,
        )
        if not discovered and has_api_credentials:
            # API mode may fail (quota/config issues). Fall back to no-key crawl mode.
            init_discovery()
            engine = get_discovery_engine()
            if engine:
                fallback_queries = [queries[0]] if queries else ["tender procurement"]
                discovered = engine.discover_tenders(
                    queries=fallback_queries,
                    results_per_query=min(results_per_query, 8),
                )
        if not discovered:
            return []

        rows: List[Dict] = []
        seen_local: set[str] = set()
        discovery_keep_terms = (
            "tender",
            "rfp",
            "rfq",
            "procurement notice",
            "request for proposal",
            "request for quotation",
            "expression of interest",
            "eoi",
        )
        discovery_noise_terms = (
            "report",
            "reports",
            "forms",
            "charts",
            "manual",
            "guideline",
            "guidelines",
            "training",
            "capacity building",
            "audit",
            "policy",
            "procedure",
        )

        for item in discovered:
            link = (item.get("link") or "").strip()
            if not link or link in existing_links or link in seen_local:
                continue
            if _looks_like_listing_or_home_link(link):
                continue

            title = (item.get("title") or "").strip()
            description = (item.get("description") or "").strip()
            if not title:
                continue
            title_low = title.lower().strip()
            title_key = re.sub(r"[^a-z0-9]+", " ", title_low).strip()
            if len(title_key) < 12:
                continue
            if title_low in GENERIC_TITLES:
                continue
            if any(pat in title_low for pat in GENERIC_TITLE_PATTERNS):
                continue
            if _is_non_opportunity_title(title_low):
                continue
            if title_low in {"open tenders", "archived tenders", "procurement", "tender notice", "tender notices"}:
                continue
            title_or_link_has_tender_hint = any(term in title_low or term in link.lower() for term in discovery_keep_terms)
            if (not title_or_link_has_tender_hint) and any(term in title_low for term in discovery_noise_terms):
                continue

            score, matched, scoring_breakdown = score_text(title, description)
            try:
                breakdown = json_lib.loads(scoring_breakdown)
            except Exception:
                breakdown = {}

            keywords_found = int(breakdown.get("keywords_found", 0) or 0)
            if score <= 0 or keywords_found == 0:
                text_low = f"{title} {description} {link}".lower()
                broad_hits = _broad_discovery_hits(text_low)
                has_tender_hint = any(term in text_low for term in discovery_keep_terms)

                # Keep broad discovery opportunities only when there is at least one
                # concrete broad hit; title/link tender hints alone are too noisy.
                if len(broad_hits) >= 1:
                    score = max(float(score or 0), 24.0)
                    if broad_hits:
                        matched = ", ".join([f"broad:{h}" for h in broad_hits[:4]])
                        breakdown["matched_phrases"] = broad_hits[:8]
                        breakdown["keywords_found"] = max(1, len(broad_hits))
                    breakdown["broad_capture"] = True
                    if breakdown.get("likely_fit_for_F2", "uncertain") == "uncertain":
                        breakdown["likely_fit_for_F2"] = "discuss"
                    scoring_breakdown = json_lib.dumps(breakdown)
                else:
                    continue

            category, _, confidence = categorize(title, description, source_name="Auto Discovery")
            domains_matched = breakdown.get("domains_matched", []) or []
            likely_fit = breakdown.get("likely_fit_for_F2", "uncertain")
            procurement_status = breakdown.get("procurement_status", "open")
            context = f"{title} {description} {link}".strip()
            deadline = parse_deadline(context) or ""
            if deadline:
                try:
                    parsed_deadline = datetime.strptime(deadline, "%Y-%m-%d").date()
                    if parsed_deadline < _utcnow().date():
                        continue
                except Exception:
                    pass
            lifecycle_status = _classify_lifecycle(context)
            if _looks_expired_or_stale(context, deadline, lifecycle_status):
                continue

            rows.append(
                {
                    "title": title,
                    "title_translated": title,
                    "link": link,
                    "description": description,
                    "description_translated": description,
                    "score": float(score),
                    "keywords_matched": matched,
                    "scoring_breakdown": scoring_breakdown,
                    "category": category,
                    "confidence": confidence,
                    "deadline": deadline,
                    "publication_date": "",
                    "buyer": "Auto Discovery",
                    "country": _source_country(str(item.get("search_source", "")), link),
                    "inferred_domains": json_lib.dumps(domains_matched),
                    "priority_level": breakdown.get("priority", "LOW"),
                    "likely_fit_for_f2": likely_fit,
                    "procurement_status": procurement_status,
                    "requires_qualification": bool(breakdown.get("requires_qualification", False)),
                    "qualification_reason": breakdown.get("qualification_reason", ""),
                    "platform_commitment_signals": json_lib.dumps(breakdown.get("microsoft_commitment_signals", [])),
                    "timing_status": lifecycle_status,
                    "discovery_method": "auto",
                    "search_query": str(item.get("search_query", "") or ""),
                    "search_source": str(item.get("search_source", "") or ""),
                    "source_id": None,
                }
            )
            seen_local.add(link)

            if len(rows) >= max_candidates:
                break

        if rows:
            print(f" Auto-discovery added {len(rows)} web-discovered candidate(s).")
        return rows


def run_scan(
    flask_app=None,
    max_sources=15,
    scan_timeout_seconds=None,
    discovery_mode: str = "f2_ranked",
    max_new_per_source: int = MAX_NEW_TENDERS_PER_SOURCE,
):
    """Scan sources for tenders and return newly added TenderResult objects.

    Key properties:
    - Parallel HTTP parsing for speed
    - **Single-thread DB write** for SQLite safety (avoids "database is locked" + race duplicates)
    - Batch insert + best-effort salvage on uniqueness collisions
    """

    from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError, as_completed
    import time

    start_time = time.time()

    # Resolve Flask app (Streamlit / scheduler can pass it explicitly)
    if flask_app is None:
        flask_app = current_app._get_current_object()

    # --- Phase 1: DB housekeeping + snapshot sources/links (app context) ---
    with flask_app.app_context():
        cleanup_old_tenders()
        cleanup_irrelevant_tenders()

        sources = TenderSource.query.filter_by(active=True).all()
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

        sources_info: List[SourceInfo] = [
            SourceInfo(id=s.id, name=s.name or "", url=s.url or "", favorite=bool(s.favorite)) for s in sources
        ]

        # Snapshot existing links once (race-safe inserts will still enforce uniqueness).
        existing_links: set[str] = {link for (link,) in db.session.query(TenderResult.link).all()}

    # --- Phase 2: Parallel scan (no DB writes in threads) ---
    workers = max(1, min(DEFAULT_SCAN_WORKERS, len(sources_info)))

    if scan_timeout_seconds is None:
        # Keep old behavior but base on number of sources; allow enough time for slow portals.
        if max_sources is None:
            scan_timeout_seconds = 120
        else:
            try:
                scan_timeout_seconds = max(30, min(120, int(max_sources) * 5))
            except Exception:
                scan_timeout_seconds = 60

    print(f"\n FAST PARALLEL scan: {len(sources_info)} sources with {workers} workers...")

    candidate_rows: List[Dict] = []

    executor = ThreadPoolExecutor(max_workers=workers)
    try:
        future_to_source = {
            executor.submit(
                scan_source,
                src,
                existing_links,
                max_new_per_source,
                discovery_mode,
            ): src for src in sources_info
        }

        completed = 0
        try:
            for future in as_completed(future_to_source, timeout=scan_timeout_seconds):
                src = future_to_source[future]
                completed += 1
                try:
                    rows = future.result() or []
                    if rows:
                        candidate_rows.extend(rows)
                        print(f" [{completed}/{len(sources_info)}] {src.name}: {len(rows)} candidates")
                    else:
                        print(f" [{completed}/{len(sources_info)}] {src.name}: 0")
                except Exception as e:
                    print(f" [{completed}/{len(sources_info)}] {src.name}: {str(e)[:60]}")
        except Exception:
            # Timeout reached - return completed results immediately.
            for fut in future_to_source:
                if not fut.done():
                    fut.cancel()
            print(f" Scan timeout reached after {scan_timeout_seconds}s; committing partial results.")
    finally:
        # Critical: do not wait for hung workers after timeout.
        executor.shutdown(wait=False, cancel_futures=True)

    # --- Phase 2b: Optional auto-discovery (web-wide via APIs) ---
    # Run with a hard timeout so slow API/no-key crawling does not block scans.
    auto_discovery_timeout_s = max(
        8,
        min(AUTO_DISCOVERY_TIMEOUT_SECONDS, int((scan_timeout_seconds or 60) * 0.4)),
    )
    discovery_executor = ThreadPoolExecutor(max_workers=1)
    discovery_future = None
    try:
        discovery_future = discovery_executor.submit(
            _discover_rows,
            flask_app,
            existing_links=existing_links,
            max_candidates=120,
        )
        discovered_rows = discovery_future.result(timeout=auto_discovery_timeout_s)
        if discovered_rows:
            candidate_rows.extend(discovered_rows)
    except FuturesTimeoutError:
        if discovery_future:
            discovery_future.cancel()
        logger.warning(
            "Auto-discovery timed out after %ss; continuing scan with source results only.",
            auto_discovery_timeout_s,
        )
        print(f" Auto-discovery timed out after {auto_discovery_timeout_s}s; using source results only.")
    except Exception as e:
        logger.warning("Auto-discovery step failed: %s", str(e)[:160])
    finally:
        discovery_executor.shutdown(wait=False, cancel_futures=True)

    # --- Phase 3: Batch insert (app context) ---
    fresh_tenders: List[TenderResult] = []
    if not candidate_rows:
        elapsed = time.time() - start_time
        print(f" Scan complete in {elapsed:.1f}s! Found 0 new tenders.")
        return []

    # De-duplicate candidates by link and ignore links we already had.
    # (This also avoids uniqueness collisions between sources.)
    seen_links = set(existing_links)
    deduped: List[Dict] = []
    for row in candidate_rows:
        link = (row or {}).get("link")
        if not link or link in seen_links:
            continue
        seen_links.add(link)
        deduped.append(row)

    with flask_app.app_context():
        new_objects: List[TenderResult] = []
        for row in deduped:
            try:
                new_objects.append(
                    TenderResult(
                        title=row.get("title", ""),
                        title_translated=row.get("title_translated", ""),
                        link=row.get("link", ""),
                        description=row.get("description", ""),
                        description_translated=row.get("description_translated", ""),
                        score=float(row.get("score", 0) or 0),
                        keywords_matched=row.get("keywords_matched", ""),
                        scoring_breakdown=row.get("scoring_breakdown", ""),
                        category=row.get("category", ""),
                        confidence=float(row.get("confidence", 0) or 0),
                        deadline=row.get("deadline", ""),
                        publication_date=row.get("publication_date", ""),
                        buyer=row.get("buyer", ""),
                        country=row.get("country", ""),
                        inferred_domains=row.get("inferred_domains", "[]"),
                        priority_level=row.get("priority_level", "LOW"),
                        likely_fit_for_f2=row.get("likely_fit_for_f2", "uncertain"),
                        procurement_status=row.get("procurement_status", "open"),
                        requires_qualification=bool(row.get("requires_qualification", False)),
                        qualification_reason=row.get("qualification_reason", ""),
                        platform_commitment_signals=row.get("platform_commitment_signals", "[]"),
                        timing_status=row.get("timing_status", "open"),
                        discovery_method=row.get("discovery_method", "manual"),
                        search_query=row.get("search_query", ""),
                        search_source=row.get("search_source", ""),
                        source_id=row.get("source_id"),
                    )
                )
            except Exception:
                continue

        if not new_objects:
            elapsed = time.time() - start_time
            print(f" Scan complete in {elapsed:.1f}s! Found 0 new tenders.")
            return []

        db.session.add_all(new_objects)

        try:
            db.session.commit()
            fresh_tenders = new_objects
        except IntegrityError:
            # Rare: concurrent scan inserted some links. Salvage what we can.
            db.session.rollback()
            salvaged: List[TenderResult] = []
            for obj in new_objects:
                try:
                    db.session.add(obj)
                    db.session.commit()
                    salvaged.append(obj)
                except IntegrityError:
                    db.session.rollback()
                except Exception:
                    db.session.rollback()
            fresh_tenders = salvaged
        except Exception:
            db.session.rollback()
            fresh_tenders = []

    elapsed = time.time() - start_time
    print(f" Scan complete in {elapsed:.1f}s! Found {len(fresh_tenders)} new tenders.")

    # Send push notifications for new high-score tenders
    if fresh_tenders:
        try:
            from app.push_notifications import PushNotificationService

            push_service = PushNotificationService(flask_app)
            push_service.notify_new_tenders(fresh_tenders)
        except Exception as e:
            print(f" Push notification failed: {e}")

    return fresh_tenders
