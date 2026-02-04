"""
Auto-Discovery Module
=====================
Automatically discovers tender opportunities across the web using Google and Bing Search APIs.
Removes dependency on manually-added sources for discovery while maintaining priority source system.

API Requirements:
- Google Custom Search API: https://developers.google.com/custom-search
- Bing Search API v7: https://www.microsoft.com/en-us/bing/apis/bing-web-search-api

Free Tier Limits:
- Google: 100 queries/day
- Bing: 1,000 queries/month (~33/day)
- Combined: ~133 searches/day
"""

import requests
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional
import logging
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class SearchAPIManager:
    """Manages both Google and Bing search APIs with quota tracking and fallback."""
    
    def __init__(self, google_api_key: str = None, google_cx: str = None, 
                 bing_api_key: str = None):
        """
        Initialize search API manager.
        
        Args:
            google_api_key: Google Custom Search API key
            google_cx: Google Custom Search Engine ID
            bing_api_key: Bing Search API key (Ocp-Apim-Subscription-Key)
        """
        self.google_api_key = google_api_key
        self.google_cx = google_cx
        self.bing_api_key = bing_api_key
        
        # API endpoints
        self.google_url = "https://www.googleapis.com/customsearch/v1"
        self.bing_url = "https://api.bing.microsoft.com/v7.0/search"
        
        # Quota tracking (reset daily)
        self.google_quota_used = 0
        self.bing_quota_used = 0
        self.quota_reset_date = datetime.utcnow().date()
        
        # Limits
        self.GOOGLE_DAILY_LIMIT = 100
        self.BING_DAILY_LIMIT = 33  # ~1000/month
    
    def _reset_quota_if_needed(self):
        """Reset quota counters if new day."""
        today = datetime.utcnow().date()
        if today > self.quota_reset_date:
            self.google_quota_used = 0
            self.bing_quota_used = 0
            self.quota_reset_date = today
            logger.info(f"Search API quotas reset for {today}")
    
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
            
            response = requests.get(self.google_url, params=params, timeout=15)
            response.raise_for_status()
            
            self.google_quota_used += 1
            data = response.json()
            
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
            
            response = requests.get(self.bing_url, headers=headers, params=params, timeout=15)
            response.raise_for_status()
            
            self.bing_quota_used += 1
            data = response.json()
            
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
            logger.error(f"Bing search API error: {e}")
            return []
    
    def search_all(self, query: str, num_results: int = 10) -> List[Dict]:
        """
        Search using both Google and Bing, return combined results.
        
        Args:
            query: Search query string
            num_results: Results per API (total = num_results * 2)
        
        Returns:
            Combined list of search results, deduplicated by URL
        """
        results = []
        seen_urls = set()
        
        # Try Google first (usually better for specific queries)
        google_results = self.search_google(query, num_results)
        for result in google_results:
            url = result['link']
            if url not in seen_urls:
                results.append(result)
                seen_urls.add(url)
        
        # Then Bing (for broader coverage)
        bing_results = self.search_bing(query, num_results)
        for result in bing_results:
            url = result['link']
            if url not in seen_urls:
                results.append(result)
                seen_urls.add(url)
        
        logger.info(f"Combined search for '{query}': {len(results)} unique results from Google + Bing")
        return results
    
    def get_quota_status(self) -> Dict:
        """Get current API quota usage."""
        self._reset_quota_if_needed()
        return {
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
            'reset_date': self.quota_reset_date.isoformat()
        }


class TenderDiscovery:
    """Main auto-discovery engine that coordinates searches and processes results."""
    
    # Default search queries targeting tender opportunities
    DEFAULT_QUERIES = [
        # General tender keywords
        'government tender procurement',
        'RFP document management system',
        'RFQ case management software',
        'tender EDMS records management',
        'bid opportunity workflow automation',
        
        # Regional variations
        'tender Kenya government',
        'procurement opportunity Africa',
        'RFP international development',
        
        # Specific categories
        'tender electronic document management',
        'RFP complaint handling system',
        'procurement business process automation',
        'tender ICT infrastructure',
        
        # Source-specific
        'UNDP procurement notice',
        'World Bank tender',
        'African Development Bank RFP',
        'UN agencies procurement'
    ]
    
    def __init__(self, search_manager: SearchAPIManager):
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
        
        # Negative indicators (exclude these)
        negative_keywords = [
            'news', 'article', 'blog', 'tutorial', 'definition',
            'wikipedia', 'linkedin', 'facebook', 'twitter',
            'youtube', 'video', 'course', 'training'
        ]
        
        # Check positive indicators
        has_positive = any(keyword in text or keyword in url for keyword in positive_keywords)
        
        # Check negative indicators
        has_negative = any(keyword in text or keyword in url for keyword in negative_keywords)
        
        # Must have positive indicators and no negative indicators
        return has_positive and not has_negative
    
    def fetch_page_details(self, url: str) -> Optional[Dict]:
        """
        Fetch additional details from tender page (optional enhancement).
        
        Args:
            url: Tender page URL
        
        Returns:
            Dict with extracted details or None if fetch fails
        """
        try:
            response = requests.get(url, timeout=10, verify=False)
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


# Global instance (initialized with API keys from AppSettings)
_discovery_manager: Optional[SearchAPIManager] = None
_discovery_engine: Optional[TenderDiscovery] = None


def init_discovery(google_api_key: str = None, google_cx: str = None, 
                   bing_api_key: str = None):
    """
    Initialize global auto-discovery system.
    
    Args:
        google_api_key: Google Custom Search API key
        google_cx: Google Custom Search Engine ID
        bing_api_key: Bing Search API key
    """
    global _discovery_manager, _discovery_engine
    
    _discovery_manager = SearchAPIManager(
        google_api_key=google_api_key,
        google_cx=google_cx,
        bing_api_key=bing_api_key
    )
    _discovery_engine = TenderDiscovery(_discovery_manager)
    
    logger.info("Auto-discovery system initialized")


def get_discovery_engine() -> Optional[TenderDiscovery]:
    """Get global discovery engine instance."""
    return _discovery_engine


def get_search_manager() -> Optional[SearchAPIManager]:
    """Get global search API manager instance."""
    return _discovery_manager
