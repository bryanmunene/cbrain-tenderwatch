from __future__ import annotations

import logging
import os
import json
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
from app.models import AppSettings, TenderSource, TenderResult, SourceHealth
from app.scoring import score_tender
from app.source_bias import COUNTRY_MAP
from app.keywords import ALL_KEYWORDS
from app.geography import (
    infer_source_group,
    parse_source_tags,
    settings_from_model,
    source_pipeline,
    source_tags_for_group,
)

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
HTTP_READ_TIMEOUT = int(7)
HTTP_TIMEOUT = (HTTP_CONNECT_TIMEOUT, HTTP_READ_TIMEOUT)
AUTO_DISCOVERY_TIMEOUT_SECONDS = int(os.getenv("AUTO_DISCOVERY_TIMEOUT_SECONDS", "12"))
AUTO_DISCOVERY_MAX_QUERIES = int(os.getenv("AUTO_DISCOVERY_MAX_QUERIES", "2"))
ALLOW_INSECURE_TLS = (os.getenv("ALLOW_INSECURE_TLS", "") or "").strip().lower() in {"1", "true", "yes", "on"}

# PDF limits (adaptive parsing uses up to PDF_MAX_PAGES pages)
PDF_MAX_BYTES = 2_000_000  # 2 MB
PDF_MAX_PAGES = 2
MAX_ANCHORS_PER_SOURCE = 120
MAX_NEW_TENDERS_PER_SOURCE = 12
DETAIL_FETCH_MAX_PER_SOURCE = 8
DETAIL_TEXT_MAX_CHARS = 4500
DETAIL_PDF_LINK_LIMIT = 2
STALE_NOTICE_MAX_AGE_DAYS = int(os.getenv("STALE_NOTICE_MAX_AGE_DAYS", "90"))

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

MIN_RELEVANCE_SCORE = 8

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
    source_group: str = "experimental"
    source_tags: str = "[]"
    health_success: int = 0
    health_failure: int = 0


SOURCE_SCAN_TUNING: Dict[str, Dict[str, int | bool]] = {
    "ICT Authority": {"max_anchors": 90, "detail_fetch_max": 4, "per_source_cap": 8},
    "Kenya Railways": {"max_anchors": 100, "detail_fetch_max": 4, "per_source_cap": 8},
    "CAK Tenders": {"max_anchors": 80, "detail_fetch_max": 4, "per_source_cap": 7},
    "South Africa eTender": {"max_anchors": 160, "detail_fetch_max": 8, "per_source_cap": 14},
    "Kenya PPIP": {"max_anchors": 150, "detail_fetch_max": 7, "per_source_cap": 12},
    "Kenya Public Procurement Portal": {"max_anchors": 150, "detail_fetch_max": 7, "per_source_cap": 12},
    "UNDP Procurement Notices": {"max_anchors": 180, "detail_fetch_max": 8, "per_source_cap": 14},
    "UN Global Marketplace": {"max_anchors": 0, "detail_fetch_max": 10, "per_source_cap": 18},
}


UNGM_BASE_URL = "https://www.ungm.org"
UNGM_SEARCH_URL = f"{UNGM_BASE_URL}/Public/Notice/Search"
UNGM_NOTICE_URL = f"{UNGM_BASE_URL}/Public/Notice"
UNGM_PAGE_SIZE = 15
UNGM_MAX_SEARCH_REQUESTS = int(os.getenv("UNGM_MAX_SEARCH_REQUESTS", "13") or 13)
UNGM_QUERY_TERMS = [
    "document management",
    "records management",
    "workflow",
    "case management",
    "digital government",
    "digital transformation",
    "registry management",
    "information management",
    "service delivery portal",
    "licensing system",
    "enterprise content management",
    "automation",
]


def _source_scan_tuning(source: SourceInfo) -> Dict[str, int | bool]:
    tuning: Dict[str, int | bool] = {
        "max_anchors": MAX_ANCHORS_PER_SOURCE,
        "detail_fetch_max": DETAIL_FETCH_MAX_PER_SOURCE,
        "per_source_cap": MAX_NEW_TENDERS_PER_SOURCE,
        "allow_pdf": source.name in PDF_SOURCE_ALLOW,
    }
    tuning.update(SOURCE_SCAN_TUNING.get(source.name, {}))

    # Reliability-aware dynamic tuning.
    failures = int(source.health_failure or 0)
    successes = int(source.health_success or 0)
    if failures >= 8 and successes <= 1:
        tuning["max_anchors"] = max(60, int(tuning["max_anchors"]) - 70)
        tuning["detail_fetch_max"] = max(3, int(tuning["detail_fetch_max"]) - 5)
        tuning["per_source_cap"] = max(4, int(tuning["per_source_cap"]) - 4)
    elif successes >= 8 and failures <= 2:
        tuning["max_anchors"] = min(320, int(tuning["max_anchors"]) + 40)
        tuning["detail_fetch_max"] = min(20, int(tuning["detail_fetch_max"]) + 3)
        tuning["per_source_cap"] = min(20, int(tuning["per_source_cap"]) + 2)

    return tuning


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

    if "afdb.org" in host or "trademarkafrica.com" in host or "eadb.org" in host:
        return "Kenya"
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
    return "Kenya"


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
    # Strip common table-column artefacts that get prepended on listing cards.
    title = re.sub(r"^(?:title|subject|description|tender\s+title|lot\s+title)\s*[:\-]?\s+", "", title, flags=re.IGNORECASE)
    # Strip common table-column artefacts that get prepended on listing cards.
    title = re.sub(r"^(?:title|subject|description|tender\s+title|lot\s+title)\s*[:\-]?\s+", "", title, flags=re.IGNORECASE)
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
        if not ALLOW_INSECURE_TLS:
            logger.warning("SSL error for %s; skipping insecure retry because ALLOW_INSECURE_TLS is disabled", url)
            raise
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
            if not ALLOW_INSECURE_TLS:
                raise
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
            if not ALLOW_INSECURE_TLS:
                raise
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


def _is_ungm_source(source: SourceInfo) -> bool:
    parsed = urlparse(source.url or "")
    host = (parsed.netloc or "").lower()
    path = (parsed.path or "").lower()
    haystack = f"{source.name} {source.url}".lower()
    return (
        "ungm.org" in host
        and "/public/notice" in path
    ) or "un global marketplace" in haystack


def _clean_ungm_text(value: str) -> str:
    text = (value or "").replace("\xa0", " ")
    text = re.sub(r"\b\d+\.\d{6,}\b", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _ungm_date(value: str) -> str:
    text = _clean_ungm_text(value)
    return parse_deadline(text) or ""


def _parse_ungm_notice_rows(html: str) -> List[Dict[str, str]]:
    """Parse UNGM /Public/Notice/Search HTML rows into structured notices."""

    if not html:
        return []

    try:
        soup = BeautifulSoup(html, "lxml")
    except Exception:
        soup = BeautifulSoup(html, "html.parser")

    notices: List[Dict[str, str]] = []
    for row in soup.select(".dataRow"):
        cells = row.select(".tableCell")
        if len(cells) < 8:
            continue

        notice_id = (row.get("data-noticeid") or row.get("data-notice-id") or "").strip()
        title_cell = row.select_one(".resultTitle") or cells[1]
        title = _clean_ungm_text(title_cell.get_text(" ", strip=True))
        title = re.sub(r"\bOpen in a new window\b", " ", title, flags=re.IGNORECASE)
        title = _clean_title(_clean_ungm_text(title))
        if not title:
            continue

        link = ""
        for a in title_cell.find_all("a", href=True):
            href = (a.get("href") or "").strip()
            if "/Public/Notice/" in href:
                link = urljoin(UNGM_BASE_URL, href)
                if not notice_id:
                    m = re.search(r"/Public/Notice/(\d+)", link)
                    notice_id = m.group(1) if m else ""
                break
        if not link and notice_id:
            link = f"{UNGM_NOTICE_URL}/{notice_id}"
        if not link:
            continue

        deadline_text = _clean_ungm_text(cells[2].get_text(" ", strip=True))
        published_text = _clean_ungm_text(cells[3].get_text(" ", strip=True))
        agency = _clean_ungm_text(cells[4].get_text(" ", strip=True))
        notice_type = _clean_ungm_text(cells[5].get_text(" ", strip=True))
        reference = _clean_ungm_text(cells[6].get_text(" ", strip=True))
        country = _clean_ungm_text(cells[7].get_text(" ", strip=True))

        meta_parts = [
            notice_type,
            f"Reference: {reference}" if reference else "",
            f"Beneficiary country or territory: {country}" if country else "",
            f"Published on: {published_text}" if published_text else "",
            f"Deadline on: {deadline_text}" if deadline_text else "",
        ]
        description = _clean_ungm_text(" ".join(part for part in meta_parts if part))

        notices.append(
            {
                "notice_id": notice_id,
                "title": title,
                "link": link,
                "description": description,
                "deadline": _ungm_date(deadline_text),
                "publication_date": _ungm_date(published_text),
                "buyer": agency,
                "country": country,
                "notice_type": notice_type,
                "reference": reference,
            }
        )

    return notices


def _ungm_search_payload(title: str = "", description: str = "", page_index: int = 0) -> Dict:
    return {
        "PageIndex": int(page_index or 0),
        "PageSize": UNGM_PAGE_SIZE,
        "Title": title or "",
        "Description": description or "",
        "Reference": "",
        "PublishedFrom": "",
        "PublishedTo": "",
        "DeadlineFrom": "",
        "DeadlineTo": "",
        "Countries": [],
        "Agencies": [],
        "UNSPSCs": [],
        "NoticeTypes": [],
        "SortField": "DatePublished",
        "SortAscending": False,
        "isPicker": False,
        "IsSustainable": False,
        "IsActive": True,
        "NoticeDisplayType": "",
        "NoticeSearchTotalLabelId": "noticeSearchTotal",
        "TypeOfCompetitions": [],
    }


def _ungm_search_specs(max_requests: int) -> List[Dict[str, str]]:
    specs: List[Dict[str, str]] = []
    for term in UNGM_QUERY_TERMS:
        specs.append({"title": term, "description": "", "label": f"title:{term}"})
        specs.append({"title": "", "description": term, "label": f"description:{term}"})

    # A final recent pass catches newly posted UN opportunities whose title/short
    # description uses unusual language. Scoring still decides whether to keep it.
    specs.append({"title": "", "description": "", "label": "recent-active"})
    return specs[: max(1, int(max_requests or 1))]


def _post_ungm_search(session: requests.Session, payload: Dict) -> str:
    headers = {
        "Accept": "text/html, */*; q=0.01",
        "Content-Type": "application/json",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": UNGM_NOTICE_URL,
    }
    response = session.post(UNGM_SEARCH_URL, json=payload, headers=headers, timeout=HTTP_TIMEOUT)
    response.raise_for_status()
    return response.text or ""


def _ungm_notice_to_row(
    notice: Dict[str, str],
    source: SourceInfo,
    pipeline_mode: str,
    geo_settings,
) -> Optional[Dict]:
    import json as json_lib

    title = _clean_title(notice.get("title", ""))
    if not title or len(title) < 8:
        return None

    link = (notice.get("link") or "").strip()
    if not link:
        return None

    base_description = _clean_ungm_text(notice.get("description", ""))
    detail_text = _clean_ungm_text(notice.get("detail_text", ""))
    description = _clean_ungm_text(f"{base_description} {detail_text}")[:DETAIL_TEXT_MAX_CHARS]
    deadline = (notice.get("deadline") or "").strip() or (parse_deadline(description) or "")
    publication_date = (notice.get("publication_date") or "").strip()
    buyer = (notice.get("buyer") or "").strip() or "UNGM"
    country = (notice.get("country") or "").strip()

    context = f"{title} {description} {link}".strip()
    lifecycle_status = _classify_lifecycle(context)
    if _is_closed_award(context) or _looks_expired_or_stale(context, deadline, lifecycle_status):
        return None

    fit_score, matched, scoring_breakdown, ranking_score = score_tender(
        title,
        description,
        buyer=buyer,
        country=country or _source_country(source.name, link),
        source_name=source.name,
        source_url=source.url,
        source_group=source.source_group,
        source_tags=parse_source_tags(source.source_tags),
        pipeline_mode=pipeline_mode,
        settings=geo_settings,
        publication_date=publication_date,
        deadline=deadline,
    )

    try:
        breakdown = json_lib.loads(scoring_breakdown)
    except Exception:
        breakdown = {}

    keywords_found = int(breakdown.get("keywords_found", 0) or 0)
    if fit_score <= 0 or keywords_found == 0:
        broad_hits = _broad_discovery_hits(context)
        has_tender_hint = any(term in context.lower() for term in TENDER_TERMS)
        if broad_hits and has_tender_hint and not bool(breakdown.get("excluded", False)):
            fit_score = max(float(fit_score or 0), 22.0)
            matched = ", ".join([f"broad:{h}" for h in broad_hits[:4]])
            breakdown["keywords_found"] = max(1, len(broad_hits))
            breakdown["matched_phrases"] = broad_hits[:8]
            breakdown["broad_capture"] = True
            if breakdown.get("likely_fit_for_F2", "uncertain") == "uncertain":
                breakdown["likely_fit_for_F2"] = "discuss"
            scoring_breakdown = json_lib.dumps(breakdown)
            ranking_score = float(breakdown.get("ranking_score", fit_score) or fit_score)
        else:
            return None

    likely_fit = breakdown.get("likely_fit_for_F2", "uncertain")
    procurement_status = breakdown.get("procurement_status", "open")
    recommendation = breakdown.get("recommendation", "REVIEW")
    queue_bucket = breakdown.get("queue_bucket", "secondary_review")
    if likely_fit in {"excluded", "no-go"}:
        return None
    if recommendation == "NO-GO":
        return None
    if procurement_status in {"locked", "conditional_nogo"}:
        return None
    if geo_settings and getattr(geo_settings, "africa_only_mode", False) and not bool(breakdown.get("africa_priority_flag", False)):
        return None

    domains_matched = breakdown.get("domains_matched", []) or []
    category, _, confidence = categorize(title, description, source_name=source.name)
    inferred_country = breakdown.get("country") or country or _source_country(source.name, link)

    return {
        "title": title,
        "title_translated": title,
        "link": link,
        "description": description,
        "description_translated": description,
        "score": float(fit_score),
        "ranking_score": float(ranking_score),
        "keywords_matched": matched,
        "scoring_breakdown": scoring_breakdown,
        "category": category,
        "confidence": confidence,
        "deadline": deadline,
        "publication_date": publication_date,
        "buyer": buyer,
        "country": inferred_country,
        "inferred_domains": json_lib.dumps(domains_matched),
        "priority_level": breakdown.get("priority", "LOW"),
        "likely_fit_for_f2": likely_fit,
        "procurement_status": procurement_status,
        "source_group": breakdown.get("source_group", source.source_group),
        "scan_pipeline": pipeline_mode,
        "geographic_scope": breakdown.get("geographic_scope", "Unknown"),
        "region": breakdown.get("region", ""),
        "africa_priority_flag": bool(breakdown.get("africa_priority_flag", False)),
        "donor_or_multilateral_flag": bool(breakdown.get("donor_or_multilateral_flag", False)),
        "target_beneficiary_region": breakdown.get("target_beneficiary_region", ""),
        "buyer_region": breakdown.get("buyer_region", ""),
        "implementation_region": breakdown.get("implementation_region", ""),
        "recommendation": recommendation,
        "queue_bucket": queue_bucket,
        "requires_qualification": bool(breakdown.get("requires_qualification", False)),
        "qualification_reason": breakdown.get("qualification_reason", ""),
        "platform_commitment_signals": json_lib.dumps(breakdown.get("microsoft_commitment_signals", [])),
        "timing_status": lifecycle_status,
        "discovery_method": "manual",
        "search_query": notice.get("search_query", ""),
        "search_source": source.name,
        "source_id": source.id,
    }


def _scan_ungm_source(
    source: SourceInfo,
    existing_links: Optional[Iterable[str]] = None,
    max_new_per_source: int = MAX_NEW_TENDERS_PER_SOURCE,
    pipeline_mode: str = "global_discovery",
    geo_settings=None,
) -> List[Dict]:
    """Scan UNGM's public procurement search across all agencies."""

    import time

    t0 = time.time()
    session = _make_http_session()
    session.headers.update(
        {
            "User-Agent": "Mozilla/5.0",
            "Accept": "text/html, */*; q=0.01",
            "Accept-Language": "en-US,en;q=0.9",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": UNGM_NOTICE_URL,
        }
    )
    existing = existing_links if isinstance(existing_links, set) else set(existing_links or ())
    tuning = _source_scan_tuning(source)
    detail_fetch_limit = int(tuning.get("detail_fetch_max", DETAIL_FETCH_MAX_PER_SOURCE) or DETAIL_FETCH_MAX_PER_SOURCE)
    per_source_cap = max(1, int(tuning.get("per_source_cap", max_new_per_source) or max_new_per_source))
    max_requests = max(1, min(30, UNGM_MAX_SEARCH_REQUESTS))
    candidate_limit = max(20, min(60, per_source_cap * 4))

    try:
        session.get(UNGM_NOTICE_URL, timeout=HTTP_TIMEOUT)
    except Exception as e:
        logger.debug("UNGM initial page fetch failed; continuing with search endpoint: %s", str(e)[:120])

    notices: List[Dict[str, str]] = []
    seen_links: set[str] = set()
    for spec in _ungm_search_specs(max_requests):
        payload = _ungm_search_payload(title=spec.get("title", ""), description=spec.get("description", ""))
        try:
            html = _post_ungm_search(session, payload)
        except Exception as e:
            logger.debug("UNGM search failed for %s: %s", spec.get("label", ""), str(e)[:160])
            continue

        for notice in _parse_ungm_notice_rows(html):
            link = notice.get("link", "")
            if not link or link in existing or link in seen_links:
                continue
            notice["search_query"] = spec.get("label", "")
            notices.append(notice)
            seen_links.add(link)
            if len(notices) >= candidate_limit:
                break
        if len(notices) >= candidate_limit:
            break

    rows: List[Dict] = []
    detail_fetch_count = 0
    for notice in notices:
        if detail_fetch_count < detail_fetch_limit:
            try:
                detail = _detail_context(notice.get("link", ""), session=session)
                detail_text = detail.get("text", "") or ""
                if detail_text:
                    notice["detail_text"] = detail_text
                if not notice.get("deadline") and detail.get("deadline"):
                    notice["deadline"] = detail.get("deadline", "")
                detail_fetch_count += 1
            except Exception:
                detail_fetch_count += 1

        row = _ungm_notice_to_row(
            notice,
            source=source,
            pipeline_mode=pipeline_mode,
            geo_settings=geo_settings,
        )
        if row:
            rows.append(row)
            if len(rows) >= per_source_cap:
                break

    rows.sort(
        key=lambda r: (
            float(r.get("score", 0) or 0),
            1 if (r.get("deadline") or "").strip() else 0,
        ),
        reverse=True,
    )
    logger.info("Source %s produced %d UNGM candidates in %.1fs", source.name, len(rows), time.time() - t0)
    return rows[:per_source_cap]


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
    pipeline_mode: str = "africa_priority",
    geo_settings=None,
) -> List[Dict]:
    """Scan a single source URL and return candidate tender rows.

    Important: This function does **not** write to the database.
    We keep it thread-safe + SQLite-friendly by doing all DB writes in the main thread.
    """

    import json as json_lib
    import time

    t0 = time.time()
    session = _make_http_session()

    if _is_ungm_source(source):
        return _scan_ungm_source(
            source,
            existing_links=existing_links,
            max_new_per_source=max_new_per_source,
            pipeline_mode=pipeline_mode,
            geo_settings=geo_settings,
        )

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
    tuning = _source_scan_tuning(source)
    max_anchors = int(tuning.get("max_anchors", MAX_ANCHORS_PER_SOURCE) or MAX_ANCHORS_PER_SOURCE)
    detail_fetch_limit = int(tuning.get("detail_fetch_max", DETAIL_FETCH_MAX_PER_SOURCE) or DETAIL_FETCH_MAX_PER_SOURCE)
    tuned_cap = int(tuning.get("per_source_cap", max_new_per_source) or max_new_per_source)
    allow_pdf = bool(tuning.get("allow_pdf", source.name in PDF_SOURCE_ALLOW)) and (not manual_like)
    seen_links: set[str] = set()
    seen_titles: set[str] = set()
    out: List[Dict] = []
    detail_fetch_count = 0

    for idx, a in enumerate(soup.find_all("a", href=True)):
        if idx >= max_anchors:
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
            if not deadline and detail_fetch_count < detail_fetch_limit and (has_detail_url or is_pdf):
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
                if not (has_tender_term or (manual_like and keyword_hint)):
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
            fit_score, matched, scoring_breakdown, ranking_score = score_tender(
                title,
                scoring_text,
                buyer=source.name,
                country=_source_country(source.name, link),
                source_name=source.name,
                source_url=source.url,
                source_group=source.source_group,
                source_tags=parse_source_tags(source.source_tags),
                pipeline_mode=pipeline_mode,
                settings=geo_settings,
                publication_date="",
                deadline=deadline or "",
            )

            try:
                breakdown = json_lib.loads(scoring_breakdown)
            except Exception:
                breakdown = {}

            keywords_found = int(breakdown.get("keywords_found", 0) or 0)
            domains_matched = breakdown.get("domains_matched", []) or []
            likely_fit = breakdown.get("likely_fit_for_F2", "uncertain")
            procurement_status = breakdown.get("procurement_status", "open")
            recommendation = breakdown.get("recommendation", "REVIEW")
            queue_bucket = breakdown.get("queue_bucket", "main_shortlist")

            if fit_score <= 0 or keywords_found == 0:
                # Do not resurrect tenders explicitly excluded by keyword scoring.
                # Example: construction/civil works notices with incidental "ict" text.
                if bool(breakdown.get("excluded", False)) and not (has_tender_term or has_ref_code or has_detail_url or (manual_like and keyword_hint)):
                    continue
                # Controlled fallback: keep digital/ICT-adjacent leads from favorite sources.
                broad_hits = _broad_discovery_hits(base_combined)
                allow_broad_capture = has_tender_term or has_ref_code or has_detail_url or (manual_like and keyword_hint)
                broad_quality_ok = _broad_hits_pass_quality(broad_hits) or (has_tender_term and len(broad_hits) >= 1) or (manual_like and keyword_hint and len(broad_hits) >= 1)
                if allow_broad_capture and broad_quality_ok and not bool(breakdown.get("excluded", False)):
                    fit_score = max(float(fit_score or 0), 18.0 if manual_like else 16.0)
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
                    recommendation = breakdown.get("recommendation", "REVIEW")
                    queue_bucket = breakdown.get("queue_bucket", "secondary_review")
                    ranking_score = float(breakdown.get("ranking_score", fit_score) or fit_score)
                else:
                    continue
            if likely_fit in {"excluded", "no-go"}:
                continue
            if recommendation == "NO-GO":
                continue
            if procurement_status in {"locked", "conditional_nogo"}:
                continue
            # Keep more exploratory matches in F2-ranked mode; final quality is handled in UI filters.
            if likely_fit == "uncertain" and fit_score < 10 and not manual_like:
                continue
            strict_no_deadline = (not bool(source.favorite)) and (not manual_like)
            if strict_no_deadline and not deadline and likely_fit in {"uncertain", "discuss"} and fit_score < 12 and not has_tender_term:
                continue
            if strict_no_deadline and not deadline and keywords_found < 2 and fit_score < 18 and not has_tender_term:
                continue
            if (
                (not manual_like)
                and (not _has_f2_intent(base_combined))
                and len(domains_matched) < 2
                and fit_score < MIN_RELEVANCE_SCORE
                and not (has_tender_term and (has_ref_code or has_detail_url or has_url_term))
            ):
                continue

            bonus = _source_bias_bonus(source.name, link)
            if bonus:
                ranking_score = min(100, ranking_score + bonus)
                breakdown["source_bias"] = bonus
                breakdown["ranking_score"] = ranking_score
                breakdown["final_score"] = ranking_score
                scoring_breakdown = json_lib.dumps(breakdown)

            category, _, confidence = categorize(title, scoring_text, source_name=source.name)

            country = breakdown.get("country") or _source_country(source.name, link)
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
                    "score": float(fit_score),
                    "ranking_score": float(ranking_score),
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
                    "source_group": breakdown.get("source_group", source.source_group),
                    "scan_pipeline": pipeline_mode,
                    "geographic_scope": breakdown.get("geographic_scope", "Unknown"),
                    "region": breakdown.get("region", ""),
                    "africa_priority_flag": bool(breakdown.get("africa_priority_flag", False)),
                    "donor_or_multilateral_flag": bool(breakdown.get("donor_or_multilateral_flag", False)),
                    "target_beneficiary_region": breakdown.get("target_beneficiary_region", ""),
                    "buyer_region": breakdown.get("buyer_region", ""),
                    "implementation_region": breakdown.get("implementation_region", ""),
                    "recommendation": recommendation,
                    "queue_bucket": queue_bucket,
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
        per_source_cap = max(1, int(tuned_cap or max_new_per_source or MAX_NEW_TENDERS_PER_SOURCE))
    except Exception:
        per_source_cap = max(1, int(max_new_per_source or MAX_NEW_TENDERS_PER_SOURCE))
    out = out[:per_source_cap]

    logger.info("Source %s produced %d candidates in %.1fs", source.name, len(out), time.time() - t0)
    return out


def cleanup_old_tenders(retention_days: int = 90):
    """Remove tenders older than the configured retention window."""
    try:
        retention_days = max(7, int(retention_days or 90))
    except Exception:
        retention_days = 90
    cutoff = _utcnow() - timedelta(days=retention_days)
    try:
        # Single SQL DELETE (much faster than loading rows into Python)
        count = (
            TenderResult.query.filter(TenderResult.created_at < cutoff)
            .delete(synchronize_session=False)
        )
        if count:
            db.session.commit()
            print(f"  Removed {count} tender(s) older than {retention_days} days")
    except Exception:
        # Fallback to safe row-by-row delete if the backend doesn't support this well
        db.session.rollback()
        old_tenders = TenderResult.query.filter(TenderResult.created_at < cutoff).all()
        if old_tenders:
            count = len(old_tenders)
            for tender in old_tenders:
                db.session.delete(tender)
            db.session.commit()
            print(f"  Removed {count} tender(s) older than {retention_days} days")


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
        import json as json_lib

        settings = AppSettings.query.first()
        if not settings:
            return []
        geo_settings = settings_from_model(settings)

        auto_enabled = bool(getattr(settings, "auto_discovery_enabled", False))
        google_api_key = (getattr(settings, "google_api_key", "") or "").strip() or (os.getenv("GOOGLE_API_KEY", "") or "").strip()
        google_cx = (getattr(settings, "google_cx", "") or "").strip() or (os.getenv("GOOGLE_CX", "") or "").strip()
        bing_api_key = (getattr(settings, "bing_api_key", "") or "").strip() or (os.getenv("BING_API_KEY", "") or "").strip()

        # SerpAPI is optional and can cause repeated 401 delays when stale keys linger in env.
        serpapi_enabled = str(os.getenv("ENABLE_SERPAPI_DISCOVERY", "0")).strip().lower() in {"1", "true", "yes", "on"}
        serpapi_api_key = ((os.getenv("SERPAPI_API_KEY", "") or "").strip() if serpapi_enabled else "")

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
        else:
            # Always keep API discovery bounded, even when default query sets are used.
            if not effective_queries:
                effective_queries = [
                    "government procurement records management tender",
                    "public sector workflow automation tender",
                ]
            effective_queries = effective_queries[:max(1, AUTO_DISCOVERY_MAX_QUERIES)]
            effective_results_per_query = min(effective_results_per_query, 8)

        discovered = engine.discover_tenders(
            queries=effective_queries,
            results_per_query=effective_results_per_query,
        )
        if not discovered and has_api_credentials:
            # API mode may fail due to invalid credentials or quota. No-key fallback can
            # be very slow, so keep it opt-in for interactive scans.
            allow_no_key_fallback = str(os.getenv("ALLOW_NO_KEY_DISCOVERY_FALLBACK", "0")).strip().lower() in {"1", "true", "yes", "on"}
            if allow_no_key_fallback:
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

            source_group = infer_source_group(
                source_name=str(item.get("search_source", "") or ""),
                source_url=link,
            )
            pipeline_mode = source_pipeline(source_group)
            fit_score, matched, scoring_breakdown, ranking_score = score_tender(
                title,
                description,
                buyer="Auto Discovery",
                country=_source_country(str(item.get("search_source", "")), link),
                source_name=str(item.get("search_source", "") or ""),
                source_url=link,
                source_group=source_group,
                source_tags=[source_group],
                pipeline_mode=pipeline_mode,
                settings=geo_settings,
                publication_date=item.get("publication_date", ""),
                deadline=item.get("deadline", ""),
            )
            try:
                breakdown = json_lib.loads(scoring_breakdown)
            except Exception:
                breakdown = {}

            keywords_found = int(breakdown.get("keywords_found", 0) or 0)
            recommendation = breakdown.get("recommendation", "REVIEW")
            queue_bucket = breakdown.get("queue_bucket", "secondary_review")
            if fit_score <= 0 or keywords_found == 0:
                text_low = f"{title} {description} {link}".lower()
                broad_hits = _broad_discovery_hits(text_low)
                has_tender_hint = any(term in text_low for term in discovery_keep_terms)

                # Keep broad discovery opportunities only when there is at least one
                # concrete broad hit; title/link tender hints alone are too noisy.
                if len(broad_hits) >= 1 and not bool(breakdown.get("excluded", False)):
                    fit_score = max(float(fit_score or 0), 24.0)
                    if broad_hits:
                        matched = ", ".join([f"broad:{h}" for h in broad_hits[:4]])
                        breakdown["matched_phrases"] = broad_hits[:8]
                        breakdown["keywords_found"] = max(1, len(broad_hits))
                    breakdown["broad_capture"] = True
                    if breakdown.get("likely_fit_for_F2", "uncertain") == "uncertain":
                        breakdown["likely_fit_for_F2"] = "discuss"
                    scoring_breakdown = json_lib.dumps(breakdown)
                    recommendation = breakdown.get("recommendation", "REVIEW")
                    queue_bucket = breakdown.get("queue_bucket", "secondary_review")
                    ranking_score = float(breakdown.get("ranking_score", fit_score) or fit_score)
                else:
                    continue

            category, _, confidence = categorize(title, description, source_name="Auto Discovery")
            domains_matched = breakdown.get("domains_matched", []) or []
            likely_fit = breakdown.get("likely_fit_for_F2", "uncertain")
            procurement_status = breakdown.get("procurement_status", "open")
            if geo_settings.africa_only_mode and not bool(breakdown.get("africa_priority_flag", False)):
                continue
            if (not geo_settings.include_global_sources) and pipeline_mode == "global_discovery" and not bool(breakdown.get("africa_priority_flag", False)):
                continue
            if recommendation == "NO-GO":
                continue
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
                    "score": float(fit_score),
                    "ranking_score": float(ranking_score),
                    "keywords_matched": matched,
                    "scoring_breakdown": scoring_breakdown,
                    "category": category,
                    "confidence": confidence,
                    "deadline": deadline,
                    "publication_date": "",
                    "buyer": "Auto Discovery",
                    "country": breakdown.get("country") or _source_country(str(item.get("search_source", "")), link),
                    "inferred_domains": json_lib.dumps(domains_matched),
                    "priority_level": breakdown.get("priority", "LOW"),
                    "likely_fit_for_f2": likely_fit,
                    "procurement_status": procurement_status,
                    "source_group": breakdown.get("source_group", source_group),
                    "scan_pipeline": pipeline_mode,
                    "geographic_scope": breakdown.get("geographic_scope", "Unknown"),
                    "region": breakdown.get("region", ""),
                    "africa_priority_flag": bool(breakdown.get("africa_priority_flag", False)),
                    "donor_or_multilateral_flag": bool(breakdown.get("donor_or_multilateral_flag", False)),
                    "target_beneficiary_region": breakdown.get("target_beneficiary_region", ""),
                    "buyer_region": breakdown.get("buyer_region", ""),
                    "implementation_region": breakdown.get("implementation_region", ""),
                    "recommendation": recommendation,
                    "queue_bucket": queue_bucket,
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
    max_sources=35,
    scan_timeout_seconds=None,
    discovery_mode: str = "manual_like",
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
        app_settings = AppSettings.query.first()
        retention_days = int(getattr(app_settings, "retention_days", 90) or 90) if app_settings else 90
        cleanup_old_tenders(retention_days=retention_days)
        # Optional expensive cleanup pass; disabled by default for faster interactive scans.
        run_cleanup = str(os.getenv("RUN_IRRELEVANT_CLEANUP_ON_SCAN", "0")).strip().lower() in {"1", "true", "yes", "on"}
        if run_cleanup:
            cleanup_irrelevant_tenders()

        sources = TenderSource.query.filter_by(active=True).all()
        geo_settings = settings_from_model(app_settings)

        for source in sources:
            inferred_group = infer_source_group(
                source_name=source.name,
                source_url=source.url,
                explicit_group=getattr(source, "source_group", "") or "",
                explicit_tags=getattr(source, "source_tags", "") or "",
            )
            if getattr(source, "source_group", "") != inferred_group:
                source.source_group = inferred_group
            expected_tags = json.dumps(source_tags_for_group(inferred_group))
            if getattr(source, "source_tags", "") != expected_tags:
                source.source_tags = expected_tags
        db.session.commit()

        health_map: Dict[int, SourceHealth] = {
            int(h.source_id): h
            for h in SourceHealth.query.filter(SourceHealth.source_id.isnot(None)).all()
            if h.source_id is not None
        }

        if geo_settings.africa_only_mode or not geo_settings.include_global_sources:
            allowed_groups = {"africa_priority", "africa_regional"}
            sources = [
                s for s in sources
                if infer_source_group(
                    source_name=s.name,
                    source_url=s.url,
                    explicit_group=getattr(s, "source_group", "") or "",
                    explicit_tags=getattr(s, "source_tags", "") or "",
                ) in allowed_groups
            ]

        def _source_rank(s):
            health = health_map.get(s.id)
            success = int((health.total_success if health else 0) or 0)
            failure = int((health.total_failure if health else 0) or 0)
            recent_good = 0 if (success > 0 and success >= failure) else 1
            return (
                source_pipeline(
                    infer_source_group(
                        source_name=s.name,
                        source_url=s.url,
                        explicit_group=getattr(s, "source_group", "") or "",
                        explicit_tags=getattr(s, "source_tags", "") or "",
                    )
                ) != "africa_priority",
                not bool(s.favorite),
                recent_good,
                -success,
                failure,
                (s.name or "").lower(),
            )

        sources = sorted(sources, key=_source_rank)

        if max_sources is not None:
            try:
                max_sources_int = int(max_sources)
            except Exception:
                max_sources_int = 10
            if max_sources_int > 0:
                sources = sources[:max_sources_int]

        if not sources:
            print("  No active sources found. Add sources and mark them as active to start scanning.")
            return []

        sources_info: List[SourceInfo] = [
            SourceInfo(
                id=s.id,
                name=s.name or "",
                url=s.url or "",
                favorite=bool(s.favorite),
                source_group=infer_source_group(
                    source_name=s.name,
                    source_url=s.url,
                    explicit_group=getattr(s, "source_group", "") or "",
                    explicit_tags=getattr(s, "source_tags", "") or "",
                ),
                source_tags=getattr(s, "source_tags", "") or "[]",
                health_success=int((health_map.get(s.id).total_success if health_map.get(s.id) else 0) or 0),
                health_failure=int((health_map.get(s.id).total_failure if health_map.get(s.id) else 0) or 0),
            )
            for s in sources
        ]

        # Snapshot existing links once (race-safe inserts will still enforce uniqueness).
        existing_links: set[str] = {link for (link,) in db.session.query(TenderResult.link).all()}

    # --- Phase 2: Parallel scan (no DB writes in threads) ---
    workers = max(1, min(DEFAULT_SCAN_WORKERS, len(sources_info)))

    if scan_timeout_seconds is None:
        # Keep old behavior but base on number of sources; allow enough time for slow portals.
        if max_sources is None:
            scan_timeout_seconds = 90
        else:
            try:
                scan_timeout_seconds = max(25, min(90, int(max_sources) * 3))
            except Exception:
                scan_timeout_seconds = 45

    print(f"\n FAST PARALLEL scan: {len(sources_info)} sources with {workers} workers...")

    candidate_rows: List[Dict] = []
    source_health_updates: List[Dict] = []

    executor = ThreadPoolExecutor(max_workers=workers)
    try:
        submitted_at: Dict[int, float] = {}
        future_to_source = {
            executor.submit(
                scan_source,
                src,
                existing_links,
                max_new_per_source,
                discovery_mode,
                source_pipeline(src.source_group),
                geo_settings,
            ): src for src in sources_info
        }
        for src in sources_info:
            submitted_at[src.id] = time.time()

        completed = 0
        try:
            for future in as_completed(future_to_source, timeout=scan_timeout_seconds):
                src = future_to_source[future]
                completed += 1
                try:
                    rows = future.result() or []
                    duration = max(0.0, time.time() - submitted_at.get(src.id, time.time()))
                    status = "success" if rows else "success_empty"
                    source_health_updates.append(
                        {
                            "source_id": src.id,
                            "source_name": src.name,
                            "source_url": src.url,
                            "status": status,
                            "error": "",
                            "candidates": len(rows),
                            "duration": duration,
                        }
                    )
                    if rows:
                        candidate_rows.extend(rows)
                        print(f" [{completed}/{len(sources_info)}] {src.name}: {len(rows)} candidates")
                    else:
                        print(f" [{completed}/{len(sources_info)}] {src.name}: 0")
                except Exception as e:
                    duration = max(0.0, time.time() - submitted_at.get(src.id, time.time()))
                    source_health_updates.append(
                        {
                            "source_id": src.id,
                            "source_name": src.name,
                            "source_url": src.url,
                            "status": "failed",
                            "error": str(e)[:300],
                            "candidates": 0,
                            "duration": duration,
                        }
                    )
                    print(f" [{completed}/{len(sources_info)}] {src.name}: {str(e)[:60]}")
        except BaseException:
            # Catches TimeoutError AND KeyboardInterrupt — commit whatever was collected.
            for fut in future_to_source:
                if not fut.done():
                    fut.cancel()
            # Collect results from any futures that finished before the interrupt.
            for fut, src in future_to_source.items():
                if fut.done() and fut not in {future_to_source.keys()} and not fut.cancelled():
                    try:
                        extra = fut.result() or []
                        if extra:
                            existing_extra = {r.get("link") for r in candidate_rows if isinstance(r, dict)}
                            for row in extra:
                                if isinstance(row, dict) and row.get("link") not in existing_extra:
                                    candidate_rows.append(row)
                    except Exception:
                        pass
            print(f" Scan timeout reached after {scan_timeout_seconds}s; committing partial results.")
    finally:
        # Critical: do not wait for hung workers after timeout.
        executor.shutdown(wait=False, cancel_futures=True)

    if source_health_updates:
        with flask_app.app_context():
            now = _utcnow().replace(tzinfo=None)
            for row in source_health_updates:
                health = SourceHealth.query.filter_by(source_id=row["source_id"]).first()
                if not health:
                    health = SourceHealth(source_id=row["source_id"])  # type: ignore[call-arg]
                    db.session.add(health)
                health.source_name = row["source_name"]
                health.source_url = row["source_url"]
                health.last_status = row["status"]
                health.last_error = row["error"]
                health.last_candidates = int(row["candidates"])
                health.last_duration_seconds = float(row["duration"])
                health.last_scan_at = now
                if row["status"] == "failed":
                    health.total_failure = int(health.total_failure or 0) + 1
                else:
                    health.total_success = int(health.total_success or 0) + 1
            db.session.commit()

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
                        ranking_score=float(row.get("ranking_score", 0) or 0),
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
                        source_group=row.get("source_group", "experimental"),
                        scan_pipeline=row.get("scan_pipeline", "africa_priority"),
                        geographic_scope=row.get("geographic_scope", "Unknown"),
                        region=row.get("region", ""),
                        africa_priority_flag=bool(row.get("africa_priority_flag", False)),
                        donor_or_multilateral_flag=bool(row.get("donor_or_multilateral_flag", False)),
                        target_beneficiary_region=row.get("target_beneficiary_region", ""),
                        buyer_region=row.get("buyer_region", ""),
                        implementation_region=row.get("implementation_region", ""),
                        recommendation=row.get("recommendation", "REVIEW"),
                        queue_bucket=row.get("queue_bucket", "main_shortlist"),
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

        if fresh_tenders:
            try:
                from app.push_notifications import PushNotificationService

                push_service = PushNotificationService(flask_app)
                push_service.notify_new_tenders(fresh_tenders)
            except Exception as e:
                print(f" Push notification failed: {e}")

    elapsed = time.time() - start_time
    print(f" Scan complete in {elapsed:.1f}s! Found {len(fresh_tenders)} new tenders.")

    return fresh_tenders
