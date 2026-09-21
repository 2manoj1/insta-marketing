"""
Multi-agent Influencer Marketing Workflow Graph.
Orchestrates profile analysis, brand opportunity scouting, lead enrichment,
and pitch drafting.
"""
import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.agents.adk_system import adk_orchestrator
from src.agents.brand_scout_agent import brand_scout_agent
from src.agents.draft_manager import draft_manager
from src.agents.lead_finder_agent import lead_finder_agent
from src.agents.pitch_drafter_agent import pitch_drafter_agent
from src.agents.profiler_agent import profiler_agent
from src.browser.scraper import creator_scraper
from src.config import settings
from src.models.brand import BrandOpportunity
from src.models.creator import CreatorProfile
from src.models.outreach import CampaignSummary, OutreachPitch

logger = logging.getLogger(__name__)
console = Console()


class MarketingWorkflowState:
    def __init__(self, handle: str, location: str = "Global", interests: Optional[List[str]] = None, deal_preference: str = "All"):
        self.handle = handle
        self.location = location
        self.interests = interests or []
        self.deal_preference = deal_preference
        self.profile: Optional[CreatorProfile] = None
        self.brands: List[BrandOpportunity] = []
        self.pitches: List[OutreachPitch] = []
        self.summary: Optional[CampaignSummary] = None
        self.leads_file: Optional[Path] = None
        self.drafts_dir: Optional[Path] = None
        self.logs: List[str] = []

    def log(self, message: str):
        self.logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")


class MarketingWorkflowGraph:
    """
    Graph orchestrator for Influencer Marketing Manager multi-agent pipeline.
    Governed by Google ADK (Agent Development Kit) multi-agent architecture.
    """

    def __init__(self):
        self.adk = adk_orchestrator
        self.profiler = profiler_agent
        self.scout = brand_scout_agent
        self.lead_finder = lead_finder_agent
        self.drafter = pitch_drafter_agent
        self.draft_mgr = draft_manager
        self.scraper = creator_scraper

    async def execute(
        self,
        handle_or_url: str,
        location: str = "Global",
        interests: Optional[List[str]] = None,
        deal_preference: str = "All",
        use_sample_data: bool = False,
        enable_hitl: bool = False,
        status_callback: Optional[Callable[[str, int], None]] = None,
    ) -> MarketingWorkflowState:
        state = MarketingWorkflowState(handle_or_url, location, interests, deal_preference)

        def update_status(step_name: str, pct: int):
            state.log(f"Stage {pct}%: {step_name}")
            if status_callback:
                status_callback(step_name, pct)

        # ----------------------------------------------------
        # Node 1: Profile Acquisition (Playwright Scraper Node)
        # ----------------------------------------------------
        update_status("Acquiring Creator Profile via Playwright", 15)
        if use_sample_data or handle_or_url.lower() in ["sample", "demo", "mock", "test"]:
            console.print("[yellow]Using realistic sample creator profile for rapid analysis...[/yellow]")
            state.profile = self.scraper.create_sample_profile(self.scraper.clean_handle(handle_or_url))
        else:
            try:
                state.profile = await self.scraper.scrape(handle_or_url)
            except Exception as e:
                console.print(f"[red]Error scraping live profile: {e}[/red]")
                console.print("[yellow]Falling back to mock creator profile to complete pipeline demonstration...[/yellow]")
                state.profile = self.scraper.create_sample_profile(self.scraper.clean_handle(handle_or_url))

        # Target location resolution
        target_loc = location
        if target_loc in ["Global", ""] and state.profile.location_hint:
            target_loc = state.profile.location_hint

        # ----------------------------------------------------
        # Nodes 2-4: Google ADK Multi-Agent Orchestration
        # ----------------------------------------------------
        update_status("Google ADK Director: Dispatching Specialist Agents", 35)
        update_status("Google ADK Profiler: Synthesizing Media Kit & UGC Rates", 50)
        update_status(f"Google ADK Lead Scout: Discovering Genuine Advertisers in {target_loc}", 70)
        update_status("Google ADK Pitch Drafter: Generating Bespoke Proposals & WhatsApp Pitches", 85)

        state.profile, state.brands, state.pitches = await self.adk.execute_adk_pipeline(
            profile=state.profile,
            location=target_loc,
            interests=interests,
            deal_preference=deal_preference,
            limit=5,
        )

        # ----------------------------------------------------
        # Node 5: Human-in-the-Loop (HITL) Review Node
        # ----------------------------------------------------
        if enable_hitl:
            update_status("Human-in-the-Loop Review: Awaiting Marketing Team Approval", 90)
            state.pitches = self.draft_mgr.hitl_interactive_review(state.pitches)

        # ----------------------------------------------------
        # Node 6: Export & Persistence Node
        # ----------------------------------------------------
        update_status("Compiling Campaign Summary & Exporting Leads & Drafts", 100)
        state.summary = CampaignSummary(
            creator_username=state.profile.username,
            creator_niche=state.profile.niche_categories,
            total_brands_discovered=len(state.brands),
            pitches=state.pitches,
        )

        # Save cumulative unique leads JSON
        state.leads_file = self.lead_finder.save_cumulative_leads_json(state.profile.username, state.brands)

        # Save individual editable drafts for human use
        state.drafts_dir = self.draft_mgr.save_individual_drafts(state.profile.username, state.pitches)

        # Persist complete campaign summary
        out_file = settings.data_dir / f"campaign_{state.profile.username}.json"
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(state.summary.model_dump(mode="json"), f, indent=2)

        console.print(f"\n[bold green]✓ Marketing Manager Workflow Finished Successfully![/bold green]")
        console.print(f"[dim]• Company & Leads JSON: {state.leads_file}[/dim]")
        console.print(f"[dim]• Editable Email Drafts: {state.drafts_dir}[/dim]\n")

        self._print_terminal_summary(state)
        return state

    def _print_terminal_summary(self, state: MarketingWorkflowState):
        prof = state.profile
        if not prof:
            return

        ugc = prof.ugc_profile
        rate_info = f"UGC: {ugc.estimated_rate_per_ugc_video_usd} | Sponsored Reel: {ugc.estimated_rate_per_sponsored_reel_usd}" if ugc else "N/A"

        creator_panel = Panel(
            f"[bold cyan]Creator:[/bold cyan] @{prof.username} ({prof.full_name})\n"
            f"[bold]Followers:[/bold] {prof.followers_count:,} | [bold]Tier:[/bold] {ugc.tier if ugc else 'Creator'}\n"
            f"[bold]Niches:[/bold] {', '.join(prof.niche_categories)}\n"
            f"[bold]Target Rates:[/bold] {rate_info}\n"
            f"[bold]Bio Link:[/bold] {prof.external_url or 'None'} | [bold]Contact:[/bold] {prof.contact_email or 'None'}",
            title="[bold yellow]Influencer Media Kit Card[/bold yellow]",
            border_style="yellow",
        )
        console.print(creator_panel)

        # Print the dedicated Verified Leads Table (Company Name, Marketing Email, Mobile/Phone)
        self.lead_finder.print_leads_table(prof.username, state.brands)


marketing_graph = MarketingWorkflowGraph()
