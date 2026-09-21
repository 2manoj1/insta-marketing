"""
Deep Pitch Strategist Agent.
Calculates creator market rate cards via NegotiationPricingSkill,
generates 3-channel pitch sequences (Email + DM + WhatsApp) via PitchSequencingSkill,
and saves ready-to-send files into the Pitch Vault.
"""
import logging
from typing import Callable, Dict, List, Optional
from rich.console import Console

from src.agents.draft_manager import draft_manager
from src.models.brand import BrandOpportunity
from src.models.creator import CreatorProfile
from src.models.outreach import OutreachPitch
from src.skills.negotiation_pricing import negotiation_pricing_skill
from src.skills.pitch_sequencing import pitch_sequencing_skill

logger = logging.getLogger(__name__)
console = Console()


class DeepPitchStrategistAgent:
    """
    Deep agent that engineers commercially calibrated cold outreach sequences.
    """

    def __init__(
        self,
        pricing_skill=None,
        pitch_skill=None,
        draft_mgr=None,
    ):
        self.pricing = pricing_skill or negotiation_pricing_skill
        self.pitch_gen = pitch_skill or pitch_sequencing_skill
        self.draft_mgr = draft_mgr or draft_manager

    def craft_pitches(
        self,
        profile: CreatorProfile,
        opportunities: List[BrandOpportunity],
        log_callback: Optional[Callable[[str], None]] = None,
    ) -> List[OutreachPitch]:
        def log(msg: str):
            if log_callback:
                log_callback(msg)
            console.print(msg)

        log(f"[bold purple]✍️ DeepPitchStrategistAgent:[/bold purple] Structuring commercial pitch packages for @{profile.username}...")

        # Step 1: Calculate creator commercial rate card
        rate_card = self.pricing.calculate_rate_card(profile)
        log(f"  [cyan]• Creator Tier:[/cyan] [bold]{rate_card['creator_tier']}[/bold] (Anchor: {rate_card['suggested_initial_anchor_rate']})")
        log(f"  [dim]• UGC Ad Rights Benchmark: {rate_card['ugc_video_30d_ads']['rate_range']}[/dim]")

        pitches: List[OutreachPitch] = []
        for opp in opportunities:
            log(f"  [purple]➜ Formulating sequence for:[/purple] [bold]{opp.brand_name}[/bold]")
            seq = self.pitch_gen.generate_sequence(profile, opp, rate_card)

            pitch = OutreachPitch(
                brand_name=opp.brand_name,
                creator_username=profile.username,
                recipient_email=seq["recipient_email"],
                subject_line=seq["subject"],
                email_body=seq["email_body"],
                instagram_dm=seq["dm_body"],
            )
            pitches.append(pitch)

        # Step 2: Persist pitches to disk
        self.draft_mgr.save_individual_drafts(profile.username, pitches)
        log(f"[bold green]✓ Saved {len(pitches)} pitch packages into Pitch Vault (data/drafts/{profile.username}/).[/bold green]")
        return pitches


deep_pitch_strategist = DeepPitchStrategistAgent()
