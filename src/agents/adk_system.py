"""
Official Google ADK (Agent Development Kit) Multi-Agent Architecture.
Defines Agent hierarchies, instructions, and orchestration for the
Instagram Influencer Marketing Manager system.
"""
import logging
from typing import List, Optional
from google.adk import Agent, Workflow
from rich.console import Console

from src.agents.draft_manager import draft_manager
from src.agents.lead_finder_agent import lead_finder_agent
from src.agents.pitch_drafter_agent import pitch_drafter_agent
from src.agents.profiler_agent import profiler_agent
from src.models.brand import BrandOpportunity
from src.models.creator import CreatorProfile
from src.models.outreach import OutreachPitch

logger = logging.getLogger(__name__)
console = Console()

# ---------------------------------------------------------------------------
# Google ADK Sub-Agents Definitions
# ---------------------------------------------------------------------------

adk_creator_profiler = Agent(
    name="creator_profiler_specialist",
    description="Analyzes creator's Instagram metrics, content themes, and calculates UGC video & sponsored reel rate cards.",
    instruction=(
        "You are an expert talent scout. Given a creator's bio, follower counts, and recent reels, "
        "synthesize their content tier (Nano, Micro, Mid, Macro), identify core audience appeal, "
        "and calculate accurate market rates for UGC video ad rights and organic sponsored posts."
    ),
)

adk_brand_lead_scout = Agent(
    name="brand_lead_enrichment_specialist",
    description="Discovers active Instagram and Meta advertisers, extracts verified marketing emails, phone/mobile numbers, and ad angles.",
    instruction=(
        "You are an influencer brand partnership director. Search for companies with high probability "
        "of running paid Instagram ads in the creator's niche and location. Extract verified marketing/PR emails "
        "and mobile/phone numbers for outreach."
    ),
)

adk_pitch_drafter = Agent(
    name="outreach_pitch_specialist",
    description="Drafts personalized cold outreach emails and Instagram DMs tailored for UGC ad rights and sponsored placements.",
    instruction=(
        "You are a top-tier influencer talent manager. Draft high-converting cold email pitches and punchy "
        "Instagram DMs proposing concrete deliverables (1x 9:16 UGC video with 30-day paid usage rights + "
        "dedicated Reel) with compelling value hooks that make brand marketing managers eager to reply."
    ),
)

# ---------------------------------------------------------------------------
# Google ADK Master Marketing Director Agent
# ---------------------------------------------------------------------------

adk_marketing_director = Agent(
    name="influencer_marketing_director",
    description="Supervises the end-to-end creator monetization workflow: profiling, brand matching, contact extraction, and pitch generation.",
    instruction=(
        "Orchestrate the multi-agent workflow: direct creator_profiler_specialist to analyze the creator, "
        "task brand_lead_enrichment_specialist to discover verified brand contacts, and direct outreach_pitch_specialist "
        "to draft high-converting proposals."
    ),
    sub_agents=[adk_creator_profiler, adk_brand_lead_scout, adk_pitch_drafter],
)


class GoogleADKOrchestrator:
    """
    Executes the multi-agent workflow using Google ADK agent definitions
    and domain specialists.
    """

    def __init__(self):
        self.director = adk_marketing_director
        self.profiler = profiler_agent
        self.lead_finder = lead_finder_agent
        self.pitch_drafter = pitch_drafter_agent
        self.draft_mgr = draft_manager

    def get_agent_manifest(self) -> List[dict]:
        """Returns details about the active Google ADK agents."""
        return [
            {
                "name": self.director.name,
                "role": "Master Supervisory Agent",
                "description": self.director.description,
                "sub_agents": [s.name for s in self.director.sub_agents],
            },
            {
                "name": adk_creator_profiler.name,
                "role": "Creator Profiler Specialist",
                "description": adk_creator_profiler.description,
            },
            {
                "name": adk_brand_lead_scout.name,
                "role": "Lead Enrichment Specialist",
                "description": adk_brand_lead_scout.description,
            },
            {
                "name": adk_pitch_drafter.name,
                "role": "Pitch Drafter Specialist",
                "description": adk_pitch_drafter.description,
            },
        ]

    async def execute_adk_pipeline(
        self,
        profile: CreatorProfile,
        location: str,
        interests: Optional[List[str]] = None,
        deal_preference: str = "All",
        limit: int = 5,
    ) -> tuple[CreatorProfile, List[BrandOpportunity], List[OutreachPitch]]:
        """
        Executes the multi-agent pipeline governed by the Google ADK director.
        """
        console.print(f"[bold purple]Google ADK Director:[/bold purple] Orchestrating multi-agent tasks for @{profile.username}...")

        # 1. Dispatch Profiler Specialist
        console.print(f"  [cyan]➜ Dispatching {adk_creator_profiler.name}...[/cyan]")
        profile = self.profiler.profile_creator(profile)

        # 2. Dispatch Lead Enrichment Specialist
        console.print(f"  [cyan]➜ Dispatching {adk_brand_lead_scout.name}...[/cyan]")
        combined_interests = list(interests or [])
        if deal_preference and deal_preference != "All":
            combined_interests.append(deal_preference)

        brands = await self.lead_finder.find_brand_leads(
            profile=profile,
            location=location,
            interests=combined_interests,
            limit=limit,
        )

        # 3. Dispatch Pitch Drafter Specialist
        console.print(f"  [cyan]➜ Dispatching {adk_pitch_drafter.name}...[/cyan]")
        pitches = self.pitch_drafter.draft_pitches(
            profile=profile,
            opportunities=brands,
        )

        return profile, brands, pitches


adk_orchestrator = GoogleADKOrchestrator()
