"""
Free & Open-Source Live Web Search Skill.
Uses the duckduckgo-search Python library for reliable, CAPTCHA-free web searching.
Discovers active Instagram brands, direct-to-consumer advertisers, and official websites.
Zero paid API keys, with human-like delays and rate limiting.
"""
import asyncio
import logging
import random
import time
from typing import Any, Dict, List, Optional, Set
from urllib.parse import urlparse

try:
    from ddgs import DDGS
except ImportError:
    from duckduckgo_search import DDGS

logger = logging.getLogger(__name__)

# Domains to ignore from search results (search engines, directories, social aggregators)
SEARCH_BLACKLIST_DOMAINS = {
    "google.com", "duckduckgo.com", "bing.com", "yahoo.com", "wikipedia.org",
    "facebook.com", "twitter.com", "x.com", "linkedin.com", "youtube.com",
    "reddit.com", "pinterest.com", "quora.com", "medium.com",
    "instagram.com", "tiktok.com", "amazon.com", "ebay.com", "etsy.com",
    "walmart.com", "yelp.com", "tripadvisor.com", "yellowpages.com",
    "trustpilot.com", "glassdoor.com", "indeed.com", "booking.com",
    "expedia.com",
}


class FreeWebSearchSkill:
    """
    Open-source web search skill using the duckduckgo-search library.
    Provides reliable search without CAPTCHA issues, with built-in rate limiting.
    """

    name: str = "free_web_search"
    description: str = "Searches the live open internet via DuckDuckGo for active brands and official websites."

    def __init__(self, max_searches_per_minute: int = 5):
        self._search_attempts: int = 0
        self._last_reset_time: float = time.time()
        self._max_per_minute = max_searches_per_minute

    def _clean_ddg_url(self, raw_url: str) -> Optional[str]:
        """Unwraps DuckDuckGo redirect URLs like //duckduckgo.com/l/?uddg=https%3A%2F%2Fbrand.com."""
        from urllib.parse import parse_qs, unquote
        if not raw_url:
            return None
        if "duckduckgo.com/l/?" in raw_url:
            parsed = urlparse(raw_url)
            params = parse_qs(parsed.query)
            if "uddg" in params:
                return unquote(params["uddg"][0])
        elif raw_url.startswith("//"):
            return f"https:{raw_url}"
        elif raw_url.startswith("http"):
            return raw_url
        return None

    def _rate_limit_sync(self) -> None:
        """Synchronous rate limiter — max N searches per minute with jitter."""
        now = time.time()
        if now - self._last_reset_time >= 60:
            self._search_attempts = 0
            self._last_reset_time = now

        if self._search_attempts >= self._max_per_minute:
            wait = 60 - (now - self._last_reset_time)
            if wait > 0:
                time.sleep(wait)
            self._search_attempts = 0
            self._last_reset_time = time.time()

        self._search_attempts += 1

    def _search_sync(
        self,
        query: str,
        limit: int = 5,
        exclude_domains: Optional[Set[str]] = None,
    ) -> List[Dict[str, str]]:
        """
        Synchronous DuckDuckGo search with deduplication and domain filtering.
        Returns list of dicts with keys: title, url, domain, snippet.
        """
        self._rate_limit_sync()

        excluded = set(exclude_domains or set()).union(SEARCH_BLACKLIST_DOMAINS)
        results: List[Dict[str, str]] = []
        seen_domains: Set[str] = set()

        try:
            with DDGS() as ddgs:
                raw_results = list(ddgs.text(query, max_results=limit * 3))

            for res in raw_results:
                if len(results) >= limit:
                    break

                url = res.get("href", "")
                if not url:
                    continue

                parsed = urlparse(url)
                domain = parsed.netloc.lower().replace("www.", "")
                if not domain:
                    continue

                # Skip blacklisted and excluded domains
                if domain in seen_domains:
                    continue
                if any(domain == ex or domain.endswith(f".{ex}") for ex in excluded):
                    continue

                seen_domains.add(domain)
                results.append({
                    "title": res.get("title", domain),
                    "url": url,
                    "domain": domain,
                    "snippet": res.get("body", ""),
                })

        except Exception as e:
            logger.debug(f"DuckDuckGo search error: {e}")
            return []

        return results

    async def search(
        self,
        query: str,
        limit: int = 5,
        exclude_domains: Optional[Set[str]] = None,
    ) -> List[Dict[str, str]]:
        """
        Async wrapper for DuckDuckGo search. Runs the sync search in a thread
        to avoid blocking the event loop.
        """
        # Human-like jitter delay before search
        await asyncio.sleep(random.uniform(2.0, 4.0))
        return await asyncio.to_thread(
            self._search_sync, query, limit, exclude_domains
        )

    async def search_brands_for_niche(
        self,
        niche: str,
        location: str = "India",
        limit: int = 5,
        exclude_domains: Optional[Set[str]] = None,
    ) -> List[Dict[str, str]]:
        """
        Formulates smart discovery queries to find real active brands matching a niche.
        Runs multiple search queries and deduplicates results.
        """
        queries = [
            f'"{niche}" direct to consumer brands {location} "collaborate" OR "contact"',
            f'top "{niche}" startup brands {location} instagram',
            f'"{niche}" brand {location} influencer collaboration',
        ]

        all_results: List[Dict[str, str]] = []
        seen_domains: Set[str] = set()

        for q in queries:
            if len(all_results) >= limit:
                break
            results = await self.search(q, limit=limit, exclude_domains=exclude_domains)
            for r in results:
                if r["domain"] not in seen_domains:
                    seen_domains.add(r["domain"])
                    all_results.append(r)
                    if len(all_results) >= limit:
                        break

        return all_results[:limit]


free_web_search_skill = FreeWebSearchSkill()
