"""
Free & Open-Source Live Web Search Skill.
Uses DuckDuckGo (HTML / Lite / Instant API) to autonomously search the open internet
for active Instagram brands, direct-to-consumer advertisers, Linktrees, and contact pages.
Zero paid API keys, zero subscription dependencies, with human-like delays.
"""
import asyncio
import logging
import random
import re
from typing import Any, Dict, List, Optional, Set
from urllib.parse import parse_qs, unquote, urlparse
from bs4 import BeautifulSoup
import httpx

logger = logging.getLogger(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
]

# Domains to ignore from search results (search engines, directories, social aggregators)
SEARCH_BLACKLIST_DOMAINS = {
    "google.com", "duckduckgo.com", "bing.com", "yahoo.com", "wikipedia.org",
    "facebook.com", "twitter.com", "x.com", "linkedin.com", "youtube.com",
    "reddit.com", "pinterest.com", "quora.com", "medium.com"
}


class FreeWebSearchSkill:
    """
    Open-source web search skill querying the live internet without paid third-party APIs.
    """

    name: str = "free_web_search"
    description: str = "Searches the live open internet (DuckDuckGo HTML/Lite) for active brands, Instagram accounts, and official websites."

    def __init__(self, request_delay: float = 0.5, timeout: float = 3.5):
        self.request_delay = request_delay
        self.timeout = timeout
        self._ddg_blocked: bool = False

    def _get_headers(self) -> Dict[str, str]:
        return {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://html.duckduckgo.com/",
        }

    def _clean_ddg_url(self, raw_url: str) -> Optional[str]:
        """Unwraps DuckDuckGo redirect URLs like //duckduckgo.com/l/?uddg=https%3A%2F%2Fbrand.com."""
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

    async def search(
        self,
        query: str,
        limit: int = 5,
        exclude_domains: Optional[Set[str]] = None,
    ) -> List[Dict[str, str]]:
        """
        Executes a free live web search on DuckDuckGo HTML endpoint.
        Returns a list of dicts with title, url, snippet, domain.
        """
        if self._ddg_blocked:
            return []

        excluded = set(exclude_domains or set()).union(SEARCH_BLACKLIST_DOMAINS)
        results: List[Dict[str, str]] = []

        # Polite human-like delay jitter to safeguard IP
        jitter = random.uniform(self.request_delay * 0.8, self.request_delay * 1.3)
        await asyncio.sleep(jitter)

        endpoints = [
            ("https://html.duckduckgo.com/html/", {"q": query}),
            ("https://lite.duckduckgo.com/lite/", {"q": query}),
        ]

        for url, data in endpoints:
            try:
                async with httpx.AsyncClient(headers=self._get_headers(), follow_redirects=True, timeout=self.timeout) as client:
                    resp = await client.post(url, data=data)
                    if resp.status_code == 202:
                        logger.debug("DuckDuckGo presented anomaly challenge. Skipping further DDG endpoints.")
                        self._ddg_blocked = True
                        break
                    if resp.status_code == 200 and len(resp.text) > 500:
                        soup = BeautifulSoup(resp.text, "html.parser")

                        # DuckDuckGo HTML parser
                        elements = soup.find_all("div", class_=re.compile(r"result|result__body"))
                        if not elements:
                            # Fallback to general link scraping
                            elements = soup.find_all("a", class_=re.compile(r"result__url|result__snippet"))

                        for el in elements:
                            a_tag = el.find("a", class_=re.compile(r"result__url|result__title")) or el.find("a", href=True)
                            if not a_tag:
                                continue

                            raw_link = a_tag.get("href")
                            clean_link = self._clean_ddg_url(raw_link)
                            if not clean_link:
                                continue

                            parsed_domain = urlparse(clean_link).netloc.lower().replace("www.", "")
                            if not parsed_domain or any(bad in parsed_domain for bad in excluded):
                                continue

                            title = a_tag.get_text(strip=True) or parsed_domain
                            snippet_el = el.find(class_=re.compile(r"result__snippet|snippet"))
                            snippet = snippet_el.get_text(strip=True) if snippet_el else ""

                            # Deduplicate by domain
                            if not any(r["domain"] == parsed_domain for r in results):
                                results.append({
                                    "title": title,
                                    "url": clean_link,
                                    "domain": parsed_domain,
                                    "snippet": snippet,
                                })
                                if len(results) >= limit:
                                    break

                        if results:
                            break
            except Exception as e:
                logger.debug(f"DuckDuckGo search error on {url}: {e}")

        return results[:limit]

    async def search_brands_for_niche(
        self,
        niche: str,
        location: str = "India",
        limit: int = 5,
        exclude_domains: Optional[Set[str]] = None,
    ) -> List[Dict[str, str]]:
        """
        Formulates smart discovery search queries to find real active brands and Instagram pages.
        """
        queries = [
            f'"{niche}" direct to consumer brands {location} "collaborate" OR "contact"',
            f'site:instagram.com "{niche}" brand {location}',
            f'top "{niche}" startup brands {location} instagram',
        ]

        all_results: List[Dict[str, str]] = []
        seen_domains: Set[str] = set()

        for q in queries:
            if self._ddg_blocked or len(all_results) >= limit:
                break
            res = await self.search(q, limit=limit, exclude_domains=exclude_domains)
            for r in res:
                if r["domain"] not in seen_domains:
                    seen_domains.add(r["domain"])
                    all_results.append(r)
                    if len(all_results) >= limit:
                        break

        return all_results[:limit]


free_web_search_skill = FreeWebSearchSkill()
