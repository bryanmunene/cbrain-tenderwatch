"""Auto-discovery utilities.

Discovery supports no-key crawling by default. If API credentials are present,
API search is used (SerpAPI preferred, Google/Bing optional fallback).
Otherwise the engine falls back to crawling known public tender/source pages
and feed endpoints.
"""

import requests
from requests.adapters import HTTPAdapter
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional
import logging
import os
import time
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup
import urllib3
from urllib3.util.retry import Retry

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)
ALLOW_INSECURE_TLS = (os.getenv("ALLOW_INSECURE_TLS", "") or "").strip().lower() in {"1", "true", "yes", "on"}

NO_KEY_SEED_URLS = [
    # Kenya + Africa priority
    "https://tenders.go.ke/website/tenders/all",
    "https://icta.go.ke/tenders/",
    "https://www.kemsa.co.ke/tenders/",
    "https://www.etenders.gov.za/",
    "https://www.ppda.go.ug/",
    "https://www.ppra.go.tz/",
    "https://trademarkafrica.com/procurement/",
    # Global institutions
    "https://procurement-notices.undp.org/",
    "https://www.ungm.org/Public/Notice",
    "https://www.unops.org/business-opportunities",
]

TENDER_HINTS = (
    "tender", "procurement", "bid", "rfp", "rfq", "expression of interest", "eoi",
    "request for proposal", "request for quotation", "opportunity", "solicitation",
)


class NoKeyDiscoveryManager:
    """Discover opportunities from public pages/feeds without API keys."""

    def __init__(self, seed_urls: Optional[List[str]] = None):
        self.seed_urls = seed_urls or list(NO_KEY_SEED_URLS)

    def search_all(self, query: str, num_results: int = 10) -> List[Dict]:
        # Query is used only as a soft hint; this mode primarily crawls known sources.
        query_terms = [t.strip().lower() for t in (query or "").split() if len(t.strip()) >= 3]
        max_per_source = max(5, min(30, int(num_results) * 2))
        results: List[Dict] = []
        seen = set()

        for base_url in self.seed_urls:
            try:
                page_results = self._crawl_source(base_url, max_per_source=max_per_source)
            except Exception:
                continue
            for item in page_results:
                url = item.get("link", "")
                if not url or url in seen:
                    continue
                text = f"{item.get('title', '')} {item.get('snippet', '')}".lower()
                if query_terms and not any(term in text for term in query_terms):
                    # Keep generic tender results when query doesn't match, but score them lower.
                    if not any(h in text for h in TENDER_HINTS):
                        continue
                seen.add(url)
                results.append(item)

        return results

    def _crawl_source(self, url: str, max_per_source: int = 12) -> List[Dict]:
        out: List[Dict] = []
        seen = set()
        source_tag = (urlparse(url).netloc or url).lower().strip()
        html = self._fetch(url)
        if not html:
            return out
        soup = BeautifulSoup(html, "html.parser")

        # 1) Parse direct links from landing page.
        for a in soup.find_all("a", href=True):
            if len(out) >= max_per_source:
                break
            title = (a.get_text(" ", strip=True) or "").strip()
            href = a.get("href", "").strip()
            if not href:
                continue
            link = urljoin(url, href)
            if not link.startswith(("http://", "https://")):
                continue
            hay = f"{title} {link}".lower()
            if not any(h in hay for h in TENDER_HINTS):
                continue
            if link in seen:
                continue
            seen.add(link)
            out.append({
                "title": title or "Tender notice",
                "link": link,
                "snippet": title,
                "source": source_tag or "no_key_feed",
            })

        # 2) Try common feed endpoints.
        feed_paths = ("/feed", "/rss", "/atom", "/feeds", "/feed.xml", "/rss.xml", "/atom.xml")
        for path in feed_paths:
            if len(out) >= max_per_source:
                break
            feed_url = url.rstrip("/") + path
            feed_xml = self._fetch(feed_url)
            if not feed_xml or ("<rss" not in feed_xml.lower() and "<feed" not in feed_xml.lower()):
                continue
            try:
                fsoup = BeautifulSoup(feed_xml, "xml")
                items = fsoup.find_all(["item", "entry"])
                for item in items:
                    if len(out) >= max_per_source:
                        break
                    title = (item.find("title").get_text(" ", strip=True) if item.find("title") else "").strip()
                    link_tag = item.find("link")
                    link = ""
                    if link_tag:
                        link = link_tag.get("href") or link_tag.get_text(" ", strip=True)
                    link = (link or "").strip()
                    if not link:
                        continue
                    link = urljoin(feed_url, link)
                    hay = f"{title} {link}".lower()
                    if not any(h in hay for h in TENDER_HINTS):
                        continue
                    if link in seen:
                        continue
                    seen.add(link)
                    out.append({
                        "title": title or "Tender notice",
                        "link": link,
                        "snippet": title,
                        "source": source_tag or "no_key_feed",
                    })
            except Exception:
                continue

        return out

    @staticmethod
    def _fetch(url: str) -> str:
        try:
            r = requests.get(url, timeout=5, verify=True)
            r.raise_for_status()
            return r.text
        except Exception:
            if not ALLOW_INSECURE_TLS:
                return ""
            try:
                r = requests.get(url, timeout=5, verify=False)
                r.raise_for_status()
                return r.text
            except Exception:
                return ""


class SearchAPIManager:
    """Manages SerpAPI/Google/Bing search APIs with quota tracking and fallback."""
    
    def __init__(
        self,
        google_api_key: str = None,
        google_cx: str = None,
        bing_api_key: str = None,
        serpapi_api_key: str = None,
    ):
        """
        Initialize search API manager.
        
        Args:
            google_api_key: Google Custom Search API key
            google_cx: Google Custom Search Engine ID
            bing_api_key: Legacy Bing Search API key (deprecated by Microsoft)
            serpapi_api_key: SerpAPI key (web-wide search)
        """
        self.google_api_key = google_api_key
        self.google_cx = google_cx
        self.bing_api_key = bing_api_key
        self.serpapi_api_key = serpapi_api_key
        
        # API endpoints
        self.serpapi_url = "https://serpapi.com/search.json"
        self.google_url = "https://www.googleapis.com/customsearch/v1"
        self.bing_url = "https://api.bing.microsoft.com/v7.0/search"

        self.http_timeout = int(os.getenv("DISCOVERY_HTTP_TIMEOUT_SECONDS", "20") or 20)
        self.session = self._make_session()
        
        # Quota tracking (reset daily)
        self.serpapi_quota_used = 0
        self.google_quota_used = 0
        self.bing_quota_used = 0
        self.quota_reset_date = datetime.utcnow().date()
        
        # Limits
        self.SERPAPI_DAILY_LIMIT = 5000
        self.GOOGLE_DAILY_LIMIT = 100
        self.BING_DAILY_LIMIT = 33  # ~1000/month

        self.provider_health = {
            "serpapi": {
                "last_status": "unknown",
                "last_error": "",
                "last_http_status": None,
                "last_latency_ms": 0,
                "success_count": 0,
                "failure_count": 0,
            },
            "google": {
                "last_status": "unknown",
                "last_error": "",
                "last_http_status": None,
                "last_latency_ms": 0,
                "success_count": 0,
                "failure_count": 0,
            },
            "bing": {
                "last_status": "unknown",
                "last_error": "",
                "last_http_status": None,
                "last_latency_ms": 0,
                "success_count": 0,
                "failure_count": 0,
            },
        }

    def _make_session(self) -> requests.Session:
        session = requests.Session()
        try:
            retry = Retry(
                total=2,
                connect=2,
                read=1,
                backoff_factor=0.4,
                status_forcelist=(429, 500, 502, 503, 504),
                allowed_methods=frozenset(["GET", "HEAD"]),
            )
        except TypeError:
            retry = Retry(
                total=2,
                connect=2,
                read=1,
                backoff_factor=0.4,
                status_forcelist=(429, 500, 502, 503, 504),
                method_whitelist=frozenset(["GET", "HEAD"]),
            )

        adapter = HTTPAdapter(max_retries=retry, pool_connections=8, pool_maxsize=8)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        return session

    def _mark_provider_success(self, provider: str, latency_ms: int, http_status: int):
        state = self.provider_health.get(provider, {})
        state["last_status"] = "success"
        state["last_error"] = ""
        state["last_http_status"] = http_status
        state["last_latency_ms"] = latency_ms
        state["success_count"] = int(state.get("success_count", 0) or 0) + 1
        self.provider_health[provider] = state

    def _mark_provider_failure(self, provider: str, err: Exception, latency_ms: int, http_status: Optional[int] = None):
        state = self.provider_health.get(provider, {})
        state["last_status"] = "failed"
        state["last_error"] = str(err)[:260]
        state["last_http_status"] = http_status
        state["last_latency_ms"] = latency_ms
        state["failure_count"] = int(state.get("failure_count", 0) or 0) + 1
        self.provider_health[provider] = state
    
    def _reset_quota_if_needed(self):
        """Reset quota counters if new day."""
        today = datetime.utcnow().date()
        if today > self.quota_reset_date:
            self.serpapi_quota_used = 0
            self.google_quota_used = 0
            self.bing_quota_used = 0
            self.quota_reset_date = today
            logger.info(f"Search API quotas reset for {today}")

    def search_serpapi(self, query: str, num_results: int = 10) -> List[Dict]:
        """Search using SerpAPI (preferred global web search provider)."""
        if not self.serpapi_api_key:
            logger.info("SerpAPI key not configured")
            return []

        self._reset_quota_if_needed()
        if self.serpapi_quota_used >= self.SERPAPI_DAILY_LIMIT:
            logger.warning(f"SerpAPI daily quota soft-limit reached ({self.SERPAPI_DAILY_LIMIT})")
            return []

        try:
            params = {
                "engine": "google",
                "q": query,
                "num": max(1, min(num_results, 100)),
                "api_key": self.serpapi_api_key,
            }
            start = time.perf_counter()
            response = self.session.get(self.serpapi_url, params=params, timeout=self.http_timeout)
            response.raise_for_status()
            latency_ms = int((time.perf_counter() - start) * 1000)

            self.serpapi_quota_used += 1
            data = response.json()
            self._mark_provider_success("serpapi", latency_ms=latency_ms, http_status=response.status_code)

            results = []
            for item in data.get("organic_results", []):
                results.append(
                    {
                        "title": item.get("title", ""),
                        "link": item.get("link", ""),
                        "snippet": item.get("snippet", ""),
                        "source": "serpapi",
                    }
                )

            logger.info(
                "SerpAPI search '%s' returned %d results (quota: %d/%d)",
                query,
                len(results),
                self.serpapi_quota_used,
                self.SERPAPI_DAILY_LIMIT,
            )
            return results
        except requests.RequestException as e:
            latency_ms = int((time.perf_counter() - start) * 1000) if 'start' in locals() else 0
            status = getattr(getattr(e, "response", None), "status_code", None)
            self._mark_provider_failure("serpapi", e, latency_ms=latency_ms, http_status=status)
            logger.error(f"SerpAPI search error: {e}")
            return []
    
    def search_google(self, query: str, num_results: int = 10) -> List[Dict]:
        """
        Search using Google Custom Search API.
        
        Args:
            query: Search query string
            num_results: Number of results to return (max 10 per request)
        
        Returns:
            List of search results with 'title', 'link', 'snippet'
        """
        if not self.google_api_key or not self.google_cx:
            logger.warning("Google API credentials not configured")
            return []
        
        self._reset_quota_if_needed()
        
        if self.google_quota_used >= self.GOOGLE_DAILY_LIMIT:
            logger.warning(f"Google API daily quota exceeded ({self.GOOGLE_DAILY_LIMIT})")
            return []
        
        try:
            params = {
                'key': self.google_api_key,
                'cx': self.google_cx,
                'q': query,
                'num': min(num_results, 10)  # Google max 10/request
            }
            
            start = time.perf_counter()
            response = self.session.get(self.google_url, params=params, timeout=min(self.http_timeout, 15))
            response.raise_for_status()
            latency_ms = int((time.perf_counter() - start) * 1000)
            
            self.google_quota_used += 1
            data = response.json()
            self._mark_provider_success("google", latency_ms=latency_ms, http_status=response.status_code)
            
            results = []
            for item in data.get('items', []):
                results.append({
                    'title': item.get('title', ''),
                    'link': item.get('link', ''),
                    'snippet': item.get('snippet', ''),
                    'source': 'google'
                })
            
            logger.info(f"Google search '{query}' returned {len(results)} results (quota: {self.google_quota_used}/{self.GOOGLE_DAILY_LIMIT})")
            return results
            
        except requests.RequestException as e:
            latency_ms = int((time.perf_counter() - start) * 1000) if 'start' in locals() else 0
            status = getattr(getattr(e, "response", None), "status_code", None)
            self._mark_provider_failure("google", e, latency_ms=latency_ms, http_status=status)
            logger.error(f"Google search API error: {e}")
            return []
    
    def search_bing(self, query: str, num_results: int = 10) -> List[Dict]:
        """
        Search using Bing Search API v7.
        
        Args:
            query: Search query string
            num_results: Number of results to return (max 50 per request)
        
        Returns:
            List of search results with 'title', 'link', 'snippet'
        """
        if not self.bing_api_key:
            logger.warning("Bing API credentials not configured")
            return []
        
        self._reset_quota_if_needed()
        
        if self.bing_quota_used >= self.BING_DAILY_LIMIT:
            logger.warning(f"Bing API daily quota exceeded ({self.BING_DAILY_LIMIT})")
            return []
        
        try:
            headers = {'Ocp-Apim-Subscription-Key': self.bing_api_key}
            params = {
                'q': query,
                'count': min(num_results, 50),  # Bing max 50/request
                'textDecorations': False,
                'textFormat': 'HTML'
            }
            
            start = time.perf_counter()
            response = self.session.get(self.bing_url, headers=headers, params=params, timeout=min(self.http_timeout, 15))
            response.raise_for_status()
            latency_ms = int((time.perf_counter() - start) * 1000)
            
            self.bing_quota_used += 1
            data = response.json()
            self._mark_provider_success("bing", latency_ms=latency_ms, http_status=response.status_code)
            
            results = []
            for item in data.get('webPages', {}).get('value', []):
                results.append({
                    'title': item.get('name', ''),
                    'link': item.get('url', ''),
                    'snippet': item.get('snippet', ''),
                    'source': 'bing'
                })
            
            logger.info(f"Bing search '{query}' returned {len(results)} results (quota: {self.bing_quota_used}/{self.BING_DAILY_LIMIT})")
            return results
            
        except requests.RequestException as e:
            latency_ms = int((time.perf_counter() - start) * 1000) if 'start' in locals() else 0
            status = getattr(getattr(e, "response", None), "status_code", None)
            self._mark_provider_failure("bing", e, latency_ms=latency_ms, http_status=status)
            logger.error(f"Bing search API error: {e}")
            return []
    
    def search_all(self, query: str, num_results: int = 10) -> List[Dict]:
        """
        Search using SerpAPI/Google/Bing and return combined results.
        
        Args:
            query: Search query string
            num_results: Results per provider
        
        Returns:
            Combined list of search results, deduplicated by URL
        """
        results = []
        seen_urls = set()
        
        # Prefer SerpAPI for global web coverage.
        serp_results = self.search_serpapi(query, num_results)
        for result in serp_results:
            url = result['link']
            if url and url not in seen_urls:
                results.append(result)
                seen_urls.add(url)

        # Then Google CSE (if configured).
        google_results = self.search_google(query, num_results)
        for result in google_results:
            url = result['link']
            if url and url not in seen_urls:
                results.append(result)
                seen_urls.add(url)
        
        # Finally Bing (legacy fallback).
        bing_results = self.search_bing(query, num_results)
        for result in bing_results:
            url = result['link']
            if url and url not in seen_urls:
                results.append(result)
                seen_urls.add(url)
        
        logger.info(f"Combined search for '{query}': {len(results)} unique results across SerpAPI/Google/Bing")
        return results
    
    def get_quota_status(self) -> Dict:
        """Get current API quota usage."""
        self._reset_quota_if_needed()
        return {
            'serpapi': {
                'used': self.serpapi_quota_used,
                'limit': self.SERPAPI_DAILY_LIMIT,
                'remaining': self.SERPAPI_DAILY_LIMIT - self.serpapi_quota_used
            },
            'google': {
                'used': self.google_quota_used,
                'limit': self.GOOGLE_DAILY_LIMIT,
                'remaining': self.GOOGLE_DAILY_LIMIT - self.google_quota_used
            },
            'bing': {
                'used': self.bing_quota_used,
                'limit': self.BING_DAILY_LIMIT,
                'remaining': self.BING_DAILY_LIMIT - self.bing_quota_used
            },
            'provider_health': self.provider_health,
            'reset_date': self.quota_reset_date.isoformat()
        }


class TenderDiscovery:
    """Main auto-discovery engine that coordinates searches and processes results."""
    
    # Default search queries targeting official F2-fit public-sector opportunities
    DEFAULT_QUERIES = [
        'official procurement portal records management system tender',
        'official government document management system tender',
        'electronic records management public sector tender',
        'case management system ministry tender',
        'workflow automation government rfp',
        'business process management public administration tender',
        'citizen services portal workflow tender',
        'grievance complaints handling system tender',
        'licensing permit management system tender',
        'registry correspondence management tender',
        'digitization and archiving records tender',
        'procurement records management system tender',
        'configurable process platform public sector tender',
        'UNDP records workflow tender',
        'African Development Bank digital government tender',
        'EU funding records workflow platform tender'
    ]
    
    def __init__(self, search_manager):
        """
        Initialize discovery engine.
        
        Args:
            search_manager: Configured SearchAPIManager instance
        """
        self.search_manager = search_manager
    
    def discover_tenders(self, queries: List[str] = None, 
                        results_per_query: int = 10) -> List[Dict]:
        """
        Run auto-discovery across multiple search queries.
        
        Args:
            queries: List of search queries (uses DEFAULT_QUERIES if None)
            results_per_query: Results to fetch per query per API
        
        Returns:
            List of discovered tender opportunities with metadata
        """
        queries = queries or self.DEFAULT_QUERIES
        all_results = []
        seen_urls = set()
        
        logger.info(f"Starting auto-discovery with {len(queries)} queries")
        
        for query in queries:
            # Search both APIs
            search_results = self.search_manager.search_all(query, results_per_query)
            
            for result in search_results:
                url = result['link']
                
                # Skip duplicates
                if url in seen_urls:
                    continue
                
                # Basic relevance filtering
                if self._is_likely_tender(result):
                    all_results.append({
                        'title': result['title'],
                        'link': url,
                        'description': result['snippet'],
                        'search_query': query,
                        'search_source': result['source'],
                        'discovered_at': datetime.utcnow().isoformat(),
                        'discovery_method': 'auto'
                    })
                    seen_urls.add(url)
        
        logger.info(f"Discovery complete: {len(all_results)} unique tender opportunities found")
        return all_results
    
    def _is_likely_tender(self, result: Dict) -> bool:
        """
        Filter search results to likely tender opportunities.
        
        Args:
            result: Search result dict with 'title', 'link', 'snippet'
        
        Returns:
            True if result appears to be a tender/procurement opportunity
        """
        text = f"{result.get('title', '')} {result.get('snippet', '')}".lower()
        url = result.get('link', '').lower()
        
        # Positive indicators
        positive_keywords = [
            'tender', 'rfp', 'rfq', 'procurement', 'bid', 'proposal',
            'solicitation', 'notice', 'opportunity', 'contract',
            'expression of interest', 'eoi', 'request for'
        ]

        fit_keywords = [
            'records management', 'document management', 'edms', 'edrms', 'ecm',
            'workflow', 'case management', 'grievance', 'complaint',
            'citizen services', 'service delivery portal', 'licensing system',
            'permit management', 'digitization', 'archiving', 'registry',
            'public administration', 'digital government'
        ]
        
        # Negative indicators (exclude these)
        negative_keywords = [
            'news', 'article', 'blog', 'tutorial', 'definition',
            'wikipedia', 'linkedin', 'facebook', 'twitter',
            'youtube', 'video', 'course', 'training',
            'laptop', 'printer', 'server', 'router', 'switch', 'vehicle',
            'construction', 'civil works', 'road works', 'fuel', 'furniture',
            'hosting only', 'bandwidth only', 'website redesign only'
        ]
        
        has_positive = any(keyword in text or keyword in url for keyword in positive_keywords)
        has_fit = any(keyword in text for keyword in fit_keywords)
        has_negative = any(keyword in text or keyword in url for keyword in negative_keywords)
        
        return has_positive and has_fit and not has_negative
    
    def fetch_page_details(self, url: str) -> Optional[Dict]:
        """
        Fetch additional details from tender page (optional enhancement).
        
        Args:
            url: Tender page URL
        
        Returns:
            Dict with extracted details or None if fetch fails
        """
        try:
            verify_tls = not ALLOW_INSECURE_TLS
            response = requests.get(url, timeout=10, verify=verify_tls)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract meta description if available
            meta_desc = soup.find('meta', attrs={'name': 'description'})
            description = meta_desc.get('content', '') if meta_desc else ''
            
            # Get page title
            title_tag = soup.find('title')
            title = title_tag.get_text(strip=True) if title_tag else ''
            
            return {
                'title': title,
                'description': description,
                'content_length': len(response.text)
            }
            
        except Exception as e:
            logger.debug(f"Failed to fetch details for {url}: {e}")
            return None


# Global instance
_discovery_manager: Optional[SearchAPIManager] = None
_discovery_engine: Optional[TenderDiscovery] = None


def init_discovery(
    google_api_key: str = None,
    google_cx: str = None,
    bing_api_key: str = None,
    serpapi_api_key: str = None,
):
    """
    Initialize global auto-discovery system.
    
    Args:
        google_api_key: Google Custom Search API key
        google_cx: Google Custom Search Engine ID
        bing_api_key: Legacy Bing Search API key
        serpapi_api_key: SerpAPI key
    """
    global _discovery_manager, _discovery_engine
    
    has_api = bool((google_api_key and google_cx) or bing_api_key or serpapi_api_key)
    if has_api:
        _discovery_manager = SearchAPIManager(
            google_api_key=google_api_key,
            google_cx=google_cx,
            bing_api_key=bing_api_key,
            serpapi_api_key=serpapi_api_key,
        )
        logger.info("Auto-discovery initialized in API mode")
    else:
        _discovery_manager = NoKeyDiscoveryManager()
        logger.info("Auto-discovery initialized in no-key mode")
    _discovery_engine = TenderDiscovery(_discovery_manager)


def get_discovery_engine() -> Optional[TenderDiscovery]:
    """Get global discovery engine instance."""
    return _discovery_engine


def get_search_manager() -> Optional[SearchAPIManager]:
    """Get global search API manager instance."""
    return _discovery_manager
