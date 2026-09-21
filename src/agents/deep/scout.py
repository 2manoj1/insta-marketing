"""
Deep Brand Scout & Enrichment Agent.
Conducts multi-step deep discovery:
1. Deduplication query against SQLite history & OKF Knowledge Store
2. Niche & location alignment matching
3. Deep bio-link & website crawling for missing contacts via DeepBioLinkSkill
4. Contact deliverability verification via ContactVerifierSkill
5. Knowledge loop commit to Open Knowledge Framework (OKF)
"""
import asyncio
import logging
from typing import Any, Callable, Dict, List, Optional, Set
from rich.console import Console

from src.models.brand import BrandContact, BrandOpportunity
from src.models.creator import CreatorProfile
from src.search.brand_finder import brand_finder
from src.skills.contact_verifier import contact_verifier_skill
from src.skills.deep_bio_link import deep_bio_link_skill
from src.skills.okf_memory import okf_memory_skill
from src.storage.db import db_manager
from src.storage.okf import okf_manager

logger = logging.getLogger(__name__)
console = Console()


class DeepBrandScoutAgent:
    """
    Deep agent orchestrating multi-phase brand discovery, website crawling,
    contact verification, and OKF knowledge retention.
    """

    def __init__(
        self,
        finder=None,
        db=None,
        okf=None,
        bio_scraper=None,
        verifier=None,
    ):
        self.finder = finder or brand_finder
        self.db = db or db_manager
        self.okf = okf or okf_manager
        self.bio_scraper = bio_scraper or deep_bio_link_skill
        self.verifier = verifier or contact_verifier_skill

    async def scout_and_enrich(
        self,
        profile: CreatorProfile,
        location: str = "Global",
        interests: Optional[List[str]] = None,
        limit: int = 5,
        log_callback: Optional[Callable[[str], None]] = None,
    ) -> List[BrandOpportunity]:
        def log(msg: str):
            if log_callback:
                log_callback(msg)
            console.print(msg)

        log(f"[bold cyan]🔍 DeepBrandScoutAgent:[/bold cyan] Initiating intelligence scan for @{profile.username} in {location}...")

        # Step 1: Memory & Deduplication Query
        contacted: Set[str] = self.db.get_contacted_brand_names(profile.username)
        log(f"  [dim]• Memory Ledger: {len(contacted)} previously scouted brands loaded from database.[/dim]")

        # Step 2: Query OKF Knowledge Base for known high-probability advertisers
        niche_query = " ".join(profile.niche_categories or ["lifestyle"])
        okf_matches = self.okf.query_brands(
            niche=niche_query,
            location=location,
            exclude_names=contacted,
            limit=limit,
        )

        opportunities: List[BrandOpportunity] = []
        for b in okf_matches:
            email = b.get("marketing_emails", [None])[0] if b.get("marketing_emails") else None
            phone = b.get("phone_numbers", [None])[0] if b.get("phone_numbers") else None
            opportunities.append(
                BrandOpportunity(
                    brand_name=b["brand_name"],
                    website=b["website"],
                    industry=b["industry"],
                    location=b.get("location", location),
                    fit_score=b.get("fit_score", 95),
                    ad_probability=b.get("ad_probability", "High (Active Ad Buyer)"),
                    collab_type=b.get("collab_type", "UGC Video & Sponsored Reel"),
                    value_proposition=f"Audience overlap with @{profile.username} in {b.get('industry', 'lifestyle')}.",
                    contact=BrandContact(
                        contact_email=email,
                        mobile_number=phone,
                        phone_number=phone,
                        instagram_handle=b.get("instagram_handle"),
                        website=b["website"],
                        source="okf_knowledge_store",
                    ),
                    suggested_angle=b.get("suggested_angle", "Bespoke UGC product hook"),
                )
            )

        if opportunities:
            log(f"  [green]• OKF Knowledge Base matched {len(opportunities)} verified advertisers.[/green]")

        # Step 3: If more brands needed to reach target limit, discover via search/catalog engine
        needed = limit - len(opportunities)
        if needed > 0:
            log(f"  [cyan]• Discovering {needed} additional candidate brands matching {niche_query}...[/cyan]")
            all_excluded = contacted.union({o.brand_name.lower() for o in opportunities})
            fresh = await self.finder.search_brands(
                niche_tags=profile.niche_categories or profile.detected_hashtags,
                location=location,
                interests=interests,
                bio_text=profile.bio,
                exclude_brands=all_excluded,
                limit=needed,
            )
            opportunities.extend(fresh)

        # Step 4: Deep Website & Bio-Link Crawling & Contact Verification
        final_leads: List[BrandOpportunity] = []
        for opp in opportunities[:limit]:
            log(f"  [cyan]➜ Inspecting brand:[/cyan] [bold]{opp.brand_name}[/bold] ({opp.website})")

            # Check if email or phone is missing or needs deep enrichment
            has_email = bool(opp.contact.contact_email and "@" in opp.contact.contact_email)
            has_mobile = bool(opp.contact.mobile_number and opp.contact.mobile_number != "N/A")

            # Deep enrichment if contacts missing or generic
            if not has_email or not has_mobile:
                log(f"    [dim]Invoking DeepBioLinkSkill for {opp.brand_name}...[/dim]")
                crawl_res = await self.bio_scraper.crawl_brand_site(opp.website, max_subpages=2)
                if crawl_res.get("emails") and not has_email:
                    opp.contact.contact_email = crawl_res["emails"][0]
                    log(f"    [green]✓ Discovered email via deep crawl:[/green] {opp.contact.contact_email}")
                if crawl_res.get("phones") and not has_mobile:
                    opp.contact.mobile_number = crawl_res["phones"][0]
                    opp.contact.phone_number = crawl_res["phones"][0]
                    log(f"    [green]✓ Discovered phone via deep crawl:[/green] {opp.contact.mobile_number}")

            # Verify contacts with ContactVerifierSkill
            verification = self.verifier.execute(opp.contact.contact_email, opp.contact.mobile_number)
            if verification["phone_verification"]["is_valid"]:
                opp.contact.mobile_number = verification["phone_verification"]["phone"]
                opp.contact.phone_number = verification["phone_verification"]["phone"]

            # Step 5: Save to SQLite and OKF
            self.db.save_leads(profile.username, [opp])
            self.okf.save_brand_intelligence(opp, creator_username=profile.username)
            final_leads.append(opp)

        log(f"[bold green]✓ DeepBrandScoutAgent finalized {len(final_leads)} verified brand leads (committed to SQLite & OKF).[/bold green]")
        return final_leads


deep_brand_scout = DeepBrandScoutAgent()
