"""
Deep Director Multi-Agent Orchestrator.
Supervises end-to-end multi-agent execution combining Google ADK principles,
modular skills, deep web crawling, and OKF knowledge retention.
"""
import asyncio
import logging
from typing import Any, Callable, Dict, List, Optional, Tuple
from rich.console import Console

from src.agents.deep.scout import deep_brand_scout
from src.agents.deep.strategist import deep_pitch_strategist
from src.models.brand import BrandOpportunity
from src.models.creator import CreatorProfile
from src.models.outreach import OutreachPitch
from src.skills.negotiation_pricing import negotiation_pricing_skill
from src.skills.okf_memory import okf_memory_skill
from src.skills.stealth_scraper import stealth_scraper_skill

logger = logging.getLogger(__name__)
console = Console()


class DeepDirectorOrchestrator:
    """
    Supervises the collaborative deep multi-agent workflow:
    - StealthScraperSkill
    - DeepBrandScoutAgent (with DeepBioLinkSkill & ContactVerifierSkill)
    - DeepPitchStrategistAgent (with NegotiationPricingSkill & PitchSequencingSkill)
    - OKFMemorySkill
    """

    def __init__(
        self,
        scraper_skill=None,
        scout_agent=None,
        strategist_agent=None,
        pricing_skill=None,
        okf_skill=None,
    ):
        self.scraper = scraper_skill or stealth_scraper_skill
        self.scout = scout_agent or deep_brand_scout
        self.strategist = strategist_agent or deep_pitch_strategist
        self.pricing = pricing_skill or negotiation_pricing_skill
        self.okf = okf_skill or okf_memory_skill

    async def execute_workflow(
        self,
        username: str,
        location: str = "Bangalore / India",
        interests: Optional[List[str]] = None,
        deal_preference: str = "All",
        limit: int = 5,
        log_callback: Optional[Callable[[str], None]] = None,
        step_callback: Optional[Callable[[str, int], None]] = None,
        should_stop: Optional[Callable[[], bool]] = None,
    ) -> Dict[str, Any]:
        """
        Executes deep multi-agent workflow with step callbacks and cancellation checkpoints.
        """
        def log(msg: str):
            if log_callback:
                log_callback(msg)
            console.print(msg)

        def set_step(title: str, pct: int):
            if step_callback:
                step_callback(title, pct)

        def check_stop():
            if should_stop and should_stop():
                log("[bold red]🛑 Stop signal detected. Halting Deep Director Orchestrator.[/bold red]")
                raise asyncio.CancelledError("Campaign interrupted by user.")

        log(f"[bold blue]════════════════════════════════════════════════════════════════[/bold blue]")
        log(f"[bold blue]🚀 DEEP MULTI-AGENT CAMPAIGN ORCHESTRATOR INITIATING[/bold blue]")
        log(f"[dim]Creator: @{username} | Location: {location} | Target Leads: {limit}[/dim]")
        log(f"[bold blue]════════════════════════════════════════════════════════════════[/bold blue]")

        # Phase 1: Creator Profiling & Stealth Scraping
        check_stop()
        set_step("Phase 1: Stealth Creator Profiling", 15)
        log(f"[cyan]➜ [Phase 1/4] Executing StealthScraperSkill for @{username}...[/cyan]")
        profile: CreatorProfile = await self.scraper.execute(username, use_sample_fallback=True)
        log(f"  • Creator: [bold]{profile.full_name}[/bold] ({profile.followers_count:,} followers)")
        log(f"  • Bio Niches: {', '.join(profile.niche_categories)}")

        # Phase 2: Rate Card & Deal Benchmarking
        check_stop()
        set_step("Phase 2: Commercial Rate Card Synthesis", 35)
        log(f"[cyan]➜ [Phase 2/4] Synthesizing Commercial Rate Card via NegotiationPricingSkill...[/cyan]")
        rate_card = self.pricing.calculate_rate_card(profile)
        log(f"  • Commercial Tier: [bold]{rate_card['creator_tier']}[/bold]")
        log(f"  • UGC 30-Day Ad Rights: [green]{rate_card['ugc_video_30d_ads']['rate_range']}[/green]")

        # Phase 3: Deep Brand Discovery & Bio-Link Crawling
        check_stop()
        set_step("Phase 3: Deep Brand Scouting & Web Crawling", 65)
        log(f"[cyan]➜ [Phase 3/4] Dispatching DeepBrandScoutAgent (OKF + Bio-Link Scraper + Contact Verifier)...[/cyan]")
        combined_interests = list(interests or [])
        if deal_preference and deal_preference != "All":
            combined_interests.append(deal_preference)

        brands: List[BrandOpportunity] = await self.scout.scout_and_enrich(
            profile=profile,
            location=location,
            interests=combined_interests,
            limit=limit,
            log_callback=log_callback,
        )

        # Phase 4: Pitch Strategist & Vault Packaging
        check_stop()
        set_step("Phase 4: Multi-Channel Pitch Formulation", 90)
        log(f"[cyan]➜ [Phase 4/4] Dispatching DeepPitchStrategistAgent (Email + DM + WhatsApp)...[/cyan]")
        pitches: List[OutreachPitch] = self.strategist.craft_pitches(
            profile=profile,
            opportunities=brands,
            log_callback=log_callback,
        )

        # Summary & OKF Knowledge Loop
        set_step("Complete: Intelligence Committed to OKF", 100)
        okf_summary = self.okf.get_knowledge_summary()
        log(f"[bold green]✓ DEEP CAMPAIGN SUCCESSFULLY EXECUTED[/bold green]")
        log(f"  • Brands Scouted: [bold]{len(brands)}[/bold]")
        log(f"  • Pitches Generated: [bold]{len(pitches)}[/bold]")
        log(f"  • OKF Total Brands: [bold]{okf_summary['total_brands_in_okf']}[/bold] (Verified Emails: {okf_summary['total_verified_emails']})")

        return {
            "creator_profile": profile.model_dump(),
            "rate_card": rate_card,
            "brands": [b.model_dump() for b in brands],
            "pitches": [p.model_dump() for p in pitches],
            "okf_summary": okf_summary,
        }


deep_director = DeepDirectorOrchestrator()
