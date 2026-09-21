"""
Authenticated Instagram Brand Business Profile Scraper.
Uses mobile emulation to scrape brand Instagram profiles and extract direct
business action buttons ("Email", "Contact", "Call", "WhatsApp") that are
only visible on mobile.
"""
import asyncio
import logging
import re
from typing import Any, Dict, Optional
from playwright.async_api import async_playwright

from src.browser.session import session_manager
from src.config import settings
from src.models.brand import BrandContact
from src.search.confidence import calculate_lead_confidence
from src.skills.contact_verifier import contact_verifier_skill

logger = logging.getLogger(__name__)


class InstagramBrandScraper:
    """
    Mobile-viewport browser scraper for Instagram brand profiles.
    Extracts high-confidence business action buttons.
    """

    def __init__(self):
        self.session_manager = session_manager

    def clean_handle(self, handle_or_url: str) -> str:
        """Extracts clean username without @ or URL prefix."""
        h = handle_or_url.strip()
        while "instagram.com/" in h.lower():
            h = h.split("instagram.com/")[-1]
        h = h.split("?")[0].split("#")[0].strip("/@")
        return h

    async def scrape_brand_profile(self, handle_or_url: str) -> Dict[str, Any]:
        """
        Navigates to Instagram profile using mobile user agent and viewport.
        Extracts:
        - Bio text and external website link
        - Direct "Email" or "Contact" action button
        - Direct "Call" or "WhatsApp" action button
        - Computes dynamic confidence score
        """
        handle = self.clean_handle(handle_or_url)
        if not handle:
            return {"success": False, "error": "Invalid Instagram handle."}

        profile_url = f"https://www.instagram.com/{handle}/"
        logger.info(f"Scraping mobile Instagram business profile: {profile_url}")

        contact = BrandContact(
            instagram_handle=f"@{handle}",
            source="instagram_profile"
        )

        extracted_email: Optional[str] = None
        extracted_phone: Optional[str] = None
        extracted_bio: Optional[str] = None
        extracted_link: Optional[str] = None
        has_business_button = False

        async with async_playwright() as p:
            try:
                browser, context = await self.session_manager.launch_authenticated_browser(
                    playwright=p,
                    headless=True,
                    mobile=True,
                )
            except Exception as e:
                logger.warning(f"Could not launch browser for Instagram scraping: {e}")
                return {
                    "success": False,
                    "handle": handle,
                    "error": f"Browser launch error: {e}",
                    "contact": contact.model_dump(),
                }

            try:
                page = await context.new_page()
                # 30s timeout
                await page.goto(profile_url, timeout=30000, wait_until="domcontentloaded")
                await asyncio.sleep(2)  # Wait for dynamic React hydration

                # 1. Extract Profile Bio & Link
                try:
                    bio_el = await page.query_selector("header section, div.-vDIg, div.x7a10gl")
                    if bio_el:
                        extracted_bio = await bio_el.inner_text()
                except Exception:
                    pass

                # 2. Extract External Website Link
                try:
                    links = await page.query_selector_all("header a[href^='http'], header a[href*='l.instagram.com']")
                    for l in links:
                        href = await l.get_attribute("href")
                        if href and "instagram.com" not in href:
                            extracted_link = href
                            break
                        elif href and "u=" in href:
                            # l.instagram.com/?u=https%3A%2F%2F...
                            m = re.search(r"u=([^&]+)", href)
                            if m:
                                import urllib.parse
                                extracted_link = urllib.parse.unquote(m.group(1))
                                break
                except Exception:
                    pass

                # 3. Check for Direct mailto / tel links in DOM
                try:
                    mail_links = await page.query_selector_all("a[href^='mailto:']")
                    for ml in mail_links:
                        href = await ml.get_attribute("href")
                        if href:
                            clean_mail = href.replace("mailto:", "").split("?")[0].strip()
                            if clean_mail and "@" in clean_mail:
                                extracted_email = clean_mail
                                has_business_button = True
                                break

                    tel_links = await page.query_selector_all("a[href^='tel:']")
                    for tl in tel_links:
                        href = await tl.get_attribute("href")
                        if href:
                            clean_tel = href.replace("tel:", "").split("?")[0].strip()
                            if clean_tel:
                                extracted_phone = clean_tel
                                has_business_button = True
                                break
                except Exception:
                    pass

                # 4. Check for Mobile Action Buttons ("Contact", "Email", "Call")
                if not extracted_email or not extracted_phone:
                    try:
                        contact_buttons = await page.query_selector_all("button, a[role='button']")
                        for btn in contact_buttons:
                            txt = (await btn.inner_text()).strip().lower()
                            if "contact" in txt or "email" in txt or "message" in txt:
                                await btn.click(timeout=2000)
                                await asyncio.sleep(1)
                                
                                # Check if bottom sheet appeared with mailto or tel links
                                sheet_links = await page.query_selector_all("div[role='dialog'] a, div[role='menu'] a")
                                for sl in sheet_links:
                                    s_href = await sl.get_attribute("href")
                                    if s_href and s_href.startswith("mailto:"):
                                        extracted_email = s_href.replace("mailto:", "").split("?")[0].strip()
                                        has_business_button = True
                                    elif s_href and s_href.startswith("tel:"):
                                        extracted_phone = s_href.replace("tel:", "").split("?")[0].strip()
                                        has_business_button = True
                                break
                    except Exception as e:
                        logger.debug(f"Action button click inspection bypassed: {e}")

                # 5. Regex Bio Fallback for Email & Phone if buttons didn't catch
                if extracted_bio:
                    if not extracted_email:
                        emails = re.findall(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", extracted_bio)
                        if emails:
                            extracted_email = emails[0]
                    if not extracted_phone:
                        phones = re.findall(r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{3,5}\)?[-.\s]?\d{3,5}[-.\s]?\d{4}", extracted_bio)
                        if phones:
                            extracted_phone = phones[0]

            except Exception as e:
                logger.warning(f"Error scraping Instagram handle {handle}: {e}")
            finally:
                try:
                    await context.close()
                except Exception:
                    pass

        # Update contact object
        if extracted_email:
            contact.contact_email = extracted_email
            # Verify and tier email
            if "pr@" in extracted_email.lower() or "collab" in extracted_email.lower() or "partner" in extracted_email.lower():
                contact.email_tier = "Tier 1 (Direct PR / Collab)"
            else:
                contact.email_tier = "Tier 2 (Marketing Desk)"

        if extracted_phone:
            norm_phone = contact_verifier_skill.normalize_phone(extracted_phone)
            contact.mobile_number = norm_phone
            contact.phone_number = norm_phone
            contact.whatsapp_ready = len(re.sub(r"\D", "", norm_phone)) >= 10

        if extracted_link:
            contact.website = extracted_link

        if has_business_button:
            contact.source = "instagram_business_button"
        elif extracted_email or extracted_phone:
            contact.source = "instagram_bio"

        # Calculate final confidence score
        contact.confidence_score = calculate_lead_confidence(contact)

        return {
            "success": True,
            "handle": f"@{handle}",
            "contact_email": contact.contact_email,
            "phone_number": contact.mobile_number,
            "website": contact.website,
            "email_tier": contact.email_tier,
            "whatsapp_ready": contact.whatsapp_ready,
            "confidence_score": contact.confidence_score,
            "source": contact.source,
            "has_business_button": has_business_button,
            "bio": extracted_bio,
            "contact": contact.model_dump(),
        }


instagram_brand_scraper = InstagramBrandScraper()
