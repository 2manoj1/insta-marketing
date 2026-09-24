"""
Deep Bio-Link & Website Scraper Skill.
Completely free, open-source tool using httpx & BeautifulSoup4.
Traverses brand websites, Linktree, and contact/collab pages to extract
verified marketing emails and mobile/WhatsApp numbers with safety delays and rate limits.
"""
import asyncio
import logging
import re
from typing import Any, Dict, List, Optional, Set
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
import httpx

logger = logging.getLogger(__name__)

# Common contact & collaboration sub-paths for DTC brands & agencies
CONTACT_PATHS = [
    "/contact",
    "/contact-us",
    "/pages/contact",
    "/pages/contact-us",
    "/collaborate",
    "/pages/collaborate",
    "/pages/influencers",
    "/pages/creators",
    "/pages/brand-ambassador",
    "/pages/pr",
    "/press",
    "/about",
    "/pages/about-us",
]

# Patterns to filter out unwanted fake/asset emails
IGNORED_EMAIL_PATTERNS = {
    "example.com",
    "domain.com",
    "email.com",
    "sentry.io",
    "wixpress.com",
    "shopify.com",
    "schema.org",
    "w3.org",
    "github.com",
    ".png",
    ".jpg",
    ".jpeg",
    ".svg",
    ".webp",
    ".gif",
}


class DeepBioLinkSkill:
    """
    Open-source deep crawler skill for extracting emails and WhatsApp/phone numbers
    from brand websites and bio link landing pages (Linktree, Beacons, Shopify, etc.).
    Enhanced anti-block safety: rotating user agents, Gaussian jitter, per-domain rate limiting.
    """

    name: str = "deep_bio_link_scraper"
    description: str = "Traverses brand websites, Linktree pages, and contact/collab sub-pages to extract marketing emails and mobile numbers."

    USER_AGENTS = [
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0",
    ]

    def __init__(self, request_delay: float = 1.5, timeout: float = 12.0):
        self.request_delay = request_delay
        self.timeout = timeout
        self._domain_last_request: Dict[str, float] = {}
        self._min_domain_interval = 3.0  # Min seconds between requests to same domain

    def _get_headers(self) -> Dict[str, str]:
        """Returns request headers with a randomly rotated User-Agent."""
        import random
        return {
            "User-Agent": random.choice(self.USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }

    async def _safe_delay(self, domain: str = "") -> None:
        """Applies Gaussian jitter delay and per-domain rate limiting."""
        import random, time
        # Gaussian jitter: mean=request_delay, stddev=0.5
        jitter = max(0.5, random.gauss(self.request_delay, 0.5))
        # Per-domain rate limit
        if domain and domain in self._domain_last_request:
            elapsed = time.time() - self._domain_last_request[domain]
            if elapsed < self._min_domain_interval:
                jitter = max(jitter, self._min_domain_interval - elapsed)
        await asyncio.sleep(jitter)
        if domain:
            self._domain_last_request[domain] = time.time()

    def _clean_email(self, email_str: str) -> Optional[str]:
        """Cleans and validates candidate email string."""
        email = email_str.lower().strip().strip(".,;:()\"'<>")
        if not email or "@" not in email:
            return None

        # Ignore asset filenames or common junk domains
        if any(bad in email for bad in IGNORED_EMAIL_PATTERNS):
            return None

        parts = email.split("@")
        if len(parts) != 2:
            return None
        local, domain = parts
        if len(local) < 2 or len(domain) < 4 or "." not in domain:
            return None

        return email

    def _clean_phone(self, phone_str: str) -> Optional[str]:
        """Cleans candidate phone/mobile number and checks length."""
        clean = re.sub(r"[^\d+]", "", phone_str.strip())
        digits_only = re.sub(r"\D", "", clean)

        # Standard mobile / telephone length check (between 10 and 15 digits)
        if 10 <= len(digits_only) <= 15:
            # Format nicely
            if len(digits_only) == 10 and clean.startswith(("6", "7", "8", "9")):
                return f"+91 {digits_only[:5]} {digits_only[5:]}"
            elif len(digits_only) == 12 and digits_only.startswith("91"):
                return f"+91 {digits_only[2:7]} {digits_only[7:]}"
            elif clean.startswith("+"):
                return clean
            return f"+{clean}"
        return None

    def classify_email_tier(self, email: str) -> str:
        """Classifies marketing deliverability tier of an email address."""
        if not email:
            return "Tier 3 (Corporate / Support)"
        e_lower = email.lower()
        local_part = e_lower.split("@")[0] if "@" in e_lower else e_lower
        is_pr = (
            local_part == "pr" or
            re.search(r"(^|[._\-])pr([._\-]|$)", local_part) is not None
        )
        t1_keywords = ["collab", "creator", "influencer", "partnership", "partner", "sponsor", "ambassador", "talent"]
        if is_pr or any(kw in local_part for kw in t1_keywords):
            return "Tier 1 (Direct PR / Collab)"
        elif any(kw in local_part for kw in ["marketing", "brand", "media", "press", "advertising"]):
            return "Tier 2 (Marketing Desk)"
        else:
            return "Tier 3 (Corporate / Support)"

    def generate_meta_ad_library_url(self, brand_name: str) -> str:
        """Generates direct verification deep-link to Meta Ad Library."""
        import urllib.parse
        encoded = urllib.parse.quote_plus(brand_name)
        return f"https://www.facebook.com/ads/library/?active_status=all&ad_type=all&country=ALL&q={encoded}&search_type=keyword_unordered"

    def extract_contacts_from_html(self, html: str, base_url: str = "") -> Dict[str, Any]:
        """
        Parses HTML with BeautifulSoup and regex to find emails, phones, WhatsApp links,
        social media matrix profiles (Instagram, LinkedIn, Linktree, YouTube, Twitter),
        and creator collaboration portal / application form URLs.
        """
        emails: Set[str] = set()
        phones: Set[str] = set()
        socials: Dict[str, str] = {}
        collab_forms: Set[str] = set()
        whatsapp_ready: bool = False

        soup = BeautifulSoup(html, "html.parser")

        # 1. Inspect all <a> links
        for a in soup.find_all("a", href=True):
            raw_href = a["href"].strip()
            href = urljoin(base_url, raw_href) if base_url else raw_href
            href_lower = href.lower()

            # Inspect mailto: links
            if href_lower.startswith("mailto:"):
                raw_email = raw_href[7:].split("?")[0]
                cleaned = self._clean_email(raw_email)
                if cleaned:
                    emails.add(cleaned)

            # Inspect tel: links
            elif href_lower.startswith("tel:"):
                raw_phone = raw_href[4:].split("?")[0]
                cleaned_phone = self._clean_phone(raw_phone)
                if cleaned_phone:
                    phones.add(cleaned_phone)

            # Inspect WhatsApp links (wa.me, api.whatsapp.com)
            elif "wa.me/" in href_lower or "api.whatsapp.com/send" in href_lower:
                whatsapp_ready = True
                match = re.search(r"(?:wa\.me/|phone=)(\d+)", href)
                if match:
                    cleaned_phone = self._clean_phone("+" + match.group(1))
                    if cleaned_phone:
                        phones.add(cleaned_phone)

            # Inspect Instagram profile links
            elif "instagram.com/" in href_lower:
                ig_match = re.search(r"instagram\.com/([a-zA-Z0-9_.]+)", href)
                if ig_match:
                    slug = ig_match.group(1).strip("/?")
                    if slug not in ["p", "reel", "stories", "explore", "about", "developer", "legal", "accounts"]:
                        socials.setdefault("instagram", f"https://instagram.com/{slug}")
                        socials.setdefault("instagram_handle", f"@{slug}")

            # Inspect LinkedIn company links
            elif "linkedin.com/company/" in href_lower:
                li_match = re.search(r"linkedin\.com/company/([a-zA-Z0-9_-]+)", href)
                if li_match:
                    socials.setdefault("linkedin", f"https://www.linkedin.com/company/{li_match.group(1).strip('/?')}")

            # Inspect YouTube channel / handle links
            elif "youtube.com/" in href_lower:
                yt_match = re.search(r"youtube\.com/(@[a-zA-Z0-9_.-]+|channel/[a-zA-Z0-9_-]+|c/[a-zA-Z0-9_-]+)", href)
                if yt_match:
                    socials.setdefault("youtube", f"https://www.youtube.com/{yt_match.group(1)}")

            # Inspect Twitter / X profile links
            elif "twitter.com/" in href_lower or "x.com/" in href_lower:
                tw_match = re.search(r"(?:twitter\.com|x\.com)/([a-zA-Z0-9_]+)", href)
                if tw_match:
                    tw_handle = tw_match.group(1)
                    if tw_handle not in ["intent", "share", "home", "search"]:
                        socials.setdefault("twitter", f"https://x.com/{tw_handle}")

            # Inspect Linktree / Bio-link hubs
            elif any(hub in href_lower for hub in ["linktr.ee/", "beacons.ai/", "bio.link/", "shorby.com/"]):
                socials.setdefault("linktree", href.split("?")[0])

            # Inspect Dedicated Collaboration Pages & Application Forms
            if any(form_site in href_lower for form_site in ["forms.gle", "docs.google.com/forms", "typeform.com", "airtable.com"]):
                collab_forms.add(href)
            elif any(cp in href_lower for cp in ["/pages/collab", "/collab", "/collaborate", "/pages/influencers", "/pages/creators", "/pages/brand-ambassador"]):
                collab_forms.add(href)

        # 2. Text regex extraction for emails
        text_content = soup.get_text(separator=" ", strip=True)
        raw_emails = re.findall(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", text_content)
        for r_email in raw_emails:
            cleaned = self._clean_email(r_email)
            if cleaned:
                emails.add(cleaned)

        # 3. Text regex extraction for phone/mobile numbers
        phone_matches = re.findall(
            r"(?:(?:\+|00)91[\s.-]?)?[6-9]\d{4}[\s.-]?\d{5}|\+?[1-9]\d{1,2}[\s.-]?\(?\d{2,4}\)?[\s.-]?\d{3,4}[\s.-]?\d{3,4}",
            text_content,
        )
        for r_phone in phone_matches:
            cleaned_p = self._clean_phone(r_phone)
            if cleaned_p:
                phones.add(cleaned_p)

        # Sort discovered emails by tier priority (Tier 1 > Tier 2 > Tier 3)
        sorted_emails = sorted(
            list(emails),
            key=lambda e: (0 if "Tier 1" in self.classify_email_tier(e) else (1 if "Tier 2" in self.classify_email_tier(e) else 2))
        )
        collab_list = list(collab_forms)
        return {
            "emails": sorted_emails,
            "phones": list(phones),
            "socials": socials,
            "collab_forms": collab_forms,
            "collab_form_url": collab_list[0] if collab_list else None,
            "primary_email_tier": self.classify_email_tier(sorted_emails[0]) if sorted_emails else "Tier 2 (Marketing Desk)",
            "whatsapp_ready": whatsapp_ready or any(p.startswith("+91") for p in phones),
        }

    async def crawl_brand_site(self, website_url: str, max_subpages: int = 3) -> Dict[str, Any]:
        """
        Deep crawls the brand homepage and potential contact/collab pages
        with human-safe rate delays and timeout protections.
        Extracts verified emails, phones, social footprint, and creator application forms.
        """
        if not website_url.startswith("http"):
            website_url = f"https://{website_url}"

        discovered_emails: Set[str] = set()
        discovered_phones: Set[str] = set()
        discovered_socials: Dict[str, str] = {}
        discovered_collab_forms: Set[str] = set()
        visited_urls: Set[str] = set()
        is_whatsapp_ready = False

        effective_url = website_url
        async with httpx.AsyncClient(headers=self._get_headers(), follow_redirects=True, timeout=self.timeout) as client:
            # 1. Fetch Homepage / Landing Page with domain fallback if unreachable
            candidate_urls = [website_url]
            parsed_initial = urlparse(website_url)
            netloc = parsed_initial.netloc
            if netloc.endswith(".in") and not netloc.endswith(".co.in"):
                candidate_urls.append(f"{parsed_initial.scheme}://{netloc[:-3]}.com")
            elif netloc.endswith(".com"):
                candidate_urls.append(f"{parsed_initial.scheme}://{netloc[:-4]}.in")
                candidate_urls.append(f"{parsed_initial.scheme}://{netloc[:-4]}.co.in")

            homepage_found = False
            for cand_url in candidate_urls:
                try:
                    visited_urls.add(cand_url)
                    resp = await client.get(cand_url)
                    if resp.status_code == 200:
                        data = self.extract_contacts_from_html(resp.text, str(resp.url))
                        effective_url = str(resp.url)
                        homepage_found = True
                        discovered_emails.update(data["emails"])
                        discovered_phones.update(data["phones"])
                        discovered_socials.update(data.get("socials", {}))
                        discovered_collab_forms.update(data.get("collab_forms", []))
                        if data.get("whatsapp_ready"):
                            is_whatsapp_ready = True
                        if discovered_emails:
                            break
                except Exception as e:
                    logger.debug(f"Deep crawl failed for URL {cand_url}: {e}")

            # 2. If no direct marketing email or collab page found, check standard contact sub-paths
            if len(visited_urls) <= max_subpages and homepage_found:
                base_domain = f"{urlparse(effective_url).scheme}://{urlparse(effective_url).netloc}"
                for path in CONTACT_PATHS[:max_subpages]:
                    target = f"{base_domain}{path}"
                    if target in visited_urls:
                        continue
                    visited_urls.add(target)

                    # Gaussian jitter delay with per-domain rate limiting
                    crawl_domain = urlparse(effective_url).netloc
                    await self._safe_delay(domain=crawl_domain)
                    try:
                        resp = await client.get(target)
                        if resp.status_code == 200:
                            data = self.extract_contacts_from_html(resp.text, target)
                            discovered_emails.update(data["emails"])
                            discovered_phones.update(data["phones"])
                            discovered_socials.update(data.get("socials", {}))
                            discovered_collab_forms.update(data.get("collab_forms", []))
                            if data.get("whatsapp_ready"):
                                is_whatsapp_ready = True
                            if any(p in str(data["emails"]) for p in ["collab", "pr", "creator", "partner"]):
                                break  # Found high-tier direct collaboration email
                    except Exception:
                        pass

        # Sort emails prioritizing Tier 1 (collab, creator, pr, influencer) > Tier 2 (marketing, brand, media) > Tier 3 (info, support)
        sorted_emails = sorted(
            list(discovered_emails),
            key=lambda e: (0 if "Tier 1" in self.classify_email_tier(e) else (1 if "Tier 2" in self.classify_email_tier(e) else 2))
        )

        primary_email = sorted_emails[0] if sorted_emails else None
        email_tier = self.classify_email_tier(primary_email) if primary_email else "Tier 2 (Marketing Desk)"
        collab_form_url = list(discovered_collab_forms)[0] if discovered_collab_forms else None

        return {
            "emails": sorted_emails,
            "phones": list(discovered_phones),
            "pages_crawled": list(visited_urls),
            "effective_url": effective_url,
            "socials": discovered_socials,
            "collab_form_url": collab_form_url,
            "primary_email_tier": email_tier,
            "whatsapp_ready": is_whatsapp_ready or any(p.startswith("+91") for p in discovered_phones),
        }

    async def execute(self, website_url: str) -> Dict[str, Any]:
        """Skill execution entrypoint."""
        return await self.crawl_brand_site(website_url)
        """Skill execution entrypoint."""
        return await self.crawl_brand_site(website_url)


deep_bio_link_skill = DeepBioLinkSkill()
