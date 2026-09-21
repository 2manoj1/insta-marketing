"""
Deep Bio-Link & Website Scraper Skill.
Completely free, open-source tool using httpx & BeautifulSoup4.
Traverses brand websites, Linktree, and contact/collab pages to extract
verified marketing emails and mobile/WhatsApp numbers with safety delays and rate limits.
"""
import asyncio
import logging
import re
from typing import Dict, List, Optional, Set
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
    """

    name: str = "deep_bio_link_scraper"
    description: str = "Traverses brand websites, Linktree pages, and contact/collab sub-pages to extract marketing emails and mobile numbers."

    def __init__(self, request_delay: float = 0.8, timeout: float = 12.0):
        self.request_delay = request_delay
        self.timeout = timeout
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }

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

    def extract_contacts_from_html(self, html: str, base_url: str = "") -> Dict[str, Set[str]]:
        """
        Parses HTML with BeautifulSoup and regex to find emails, phones, and WhatsApp links.
        """
        emails: Set[str] = set()
        phones: Set[str] = set()
        soup = BeautifulSoup(html, "html.parser")

        # 1. Inspect mailto: links
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            if href.lower().startswith("mailto:"):
                raw_email = href[7:].split("?")[0]
                cleaned = self._clean_email(raw_email)
                if cleaned:
                    emails.add(cleaned)

            # Inspect tel: links
            elif href.lower().startswith("tel:"):
                raw_phone = href[4:].split("?")[0]
                cleaned_phone = self._clean_phone(raw_phone)
                if cleaned_phone:
                    phones.add(cleaned_phone)

            # Inspect WhatsApp links (wa.me, api.whatsapp.com)
            elif "wa.me/" in href or "api.whatsapp.com/send" in href:
                match = re.search(r"(?:wa\.me/|phone=)(\d+)", href)
                if match:
                    cleaned_phone = self._clean_phone("+" + match.group(1))
                    if cleaned_phone:
                        phones.add(cleaned_phone)

        # 2. Text regex extraction for emails
        text_content = soup.get_text(separator=" ", strip=True)
        raw_emails = re.findall(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", text_content)
        for r_email in raw_emails:
            cleaned = self._clean_email(r_email)
            if cleaned:
                emails.add(cleaned)

        # 3. Text regex extraction for phone/mobile numbers
        # Matches Indian (+91 98765 43210) and international numbers
        phone_matches = re.findall(
            r"(?:(?:\+|00)91[\s.-]?)?[6-9]\d{4}[\s.-]?\d{5}|\+?[1-9]\d{1,2}[\s.-]?\(?\d{2,4}\)?[\s.-]?\d{3,4}[\s.-]?\d{3,4}",
            text_content,
        )
        for r_phone in phone_matches:
            cleaned_p = self._clean_phone(r_phone)
            if cleaned_p:
                phones.add(cleaned_p)

        return {"emails": emails, "phones": phones}

    async def crawl_brand_site(self, website_url: str, max_subpages: int = 3) -> Dict[str, List[str]]:
        """
        Deep crawls the brand homepage and potential contact/collab pages
        with human-safe rate delays and timeout protections.
        """
        if not website_url.startswith("http"):
            website_url = f"https://{website_url}"

        discovered_emails: Set[str] = set()
        discovered_phones: Set[str] = set()
        visited_urls: Set[str] = set()

        effective_url = website_url
        async with httpx.AsyncClient(headers=self.headers, follow_redirects=True, timeout=self.timeout) as client:
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
                        if data["emails"] or data["phones"] or not homepage_found:
                            effective_url = str(resp.url)
                            homepage_found = True
                            discovered_emails.update(data["emails"])
                            discovered_phones.update(data["phones"])
                        if discovered_emails:
                            break
                except Exception as e:
                    logger.debug(f"Deep crawl failed for URL {cand_url}: {e}")

            # 2. If no direct marketing email found, check standard contact sub-paths on effective domain
            if not discovered_emails and len(visited_urls) <= max_subpages and homepage_found:
                base_domain = f"{urlparse(effective_url).scheme}://{urlparse(effective_url).netloc}"
                for path in CONTACT_PATHS[:max_subpages]:
                    target = f"{base_domain}{path}"
                    if target in visited_urls:
                        continue
                    visited_urls.add(target)

                    # Respectful safety delay
                    await asyncio.sleep(self.request_delay)
                    try:
                        resp = await client.get(target)
                        if resp.status_code == 200:
                            data = self.extract_contacts_from_html(resp.text, target)
                            discovered_emails.update(data["emails"])
                            discovered_phones.update(data["phones"])
                            if discovered_emails:
                                break  # We found contact info!
                    except Exception:
                        pass

        # Sort emails prioritizing partnerships / collabs / marketing / pr
        sorted_emails = sorted(
            list(discovered_emails),
            key=lambda e: (
                0 if any(p in e for p in ["collab", "partner", "marketing", "influencer", "creator", "pr"])
                else 1 if "hello" in e or "contact" in e
                else 2
            ),
        )

        return {
            "emails": sorted_emails,
            "phones": list(discovered_phones),
            "pages_crawled": list(visited_urls),
            "effective_url": effective_url,
        }

    async def execute(self, website_url: str) -> Dict[str, Any]:
        """Skill execution entrypoint."""
        return await self.crawl_brand_site(website_url)


deep_bio_link_skill = DeepBioLinkSkill()
