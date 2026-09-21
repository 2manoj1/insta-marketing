"""
Brand Scout Agent.
Matches creator profile with high-paying brand opportunities by location and niche,
and personalizes the strategic pitch angle for each brand.
"""
import logging
from typing import List, Optional
from rich.console import Console

from src.llm.client import llm_client
from src.models.brand import BrandOpportunity
from src.models.creator import CreatorProfile
from src.search.brand_finder import brand_finder

logger = logging.getLogger(__name__)
console = Console()


class BrandScoutAgent:
    def __init__(self, llm=None, searcher=None):
        self.llm = llm or llm_client
        self.searcher = searcher or brand_finder

    async def scout_brands(
        self,
        profile: CreatorProfile,
        location: str = "Global",
        interests: Optional[List[str]] = None,
        limit: int = 4,
    ) -> List[BrandOpportunity]:
        console.print(f"[cyan]Agent [bold]BrandScoutAgent[/bold] scouting brands in [bold]{location}[/bold] for @{profile.username}...[/cyan]")

        # 1. Retrieve candidates from finder
        niche_tags = profile.niche_categories or profile.detected_hashtags
        candidates = await self.searcher.search_brands(
            niche_tags=niche_tags,
            location=location,
            interests=interests,
            limit=limit,
        )

        # 2. Refine angles with LLM
        refined_brands = []
        for brand in candidates:
            refined = self._refine_brand_pitch_angle(profile, brand)
            refined_brands.append(refined)

        console.print(f"[green]✓ Scouted {len(refined_brands)} high-synergy brand opportunities.[/green]")
        for b in refined_brands:
            console.print(f"  • [bold]{b.brand_name}[/bold] ({b.industry}) - Fit: {b.fit_score}% | Contact: [cyan]{b.contact.contact_email}[/cyan]")

        return refined_brands

    def _refine_brand_pitch_angle(self, profile: CreatorProfile, brand: BrandOpportunity) -> BrandOpportunity:
        prompt = f"""
As an Influencer Marketing Manager representing @{profile.username} ({profile.followers_count:,} followers, niche: {', '.join(profile.niche_categories)}),
generate a creative collaboration hook and value proposition for pitching {brand.brand_name} ({brand.industry}).

Creator strengths: {', '.join(profile.ugc_profile.ugc_strengths if profile.ugc_profile else ['Authentic storytelling'])}

Provide JSON with:
1. "value_proposition": A concise sentence explaining why {brand.brand_name} will get strong ROI from partnering with @{profile.username}.
2. "suggested_angle": A specific high-converting video concept/hook idea (e.g., "Problem vs Solution reel showing...").
3. "collab_type": Best deal format (e.g. "Direct-Response UGC Video Ad" or "Sponsored Reel + Ad Whitelisting").
"""
        try:
            res = self.llm.generate_json([
                {"role": "system", "content": "You are a brand partnership director. Output valid JSON only."},
                {"role": "user", "content": prompt}
            ])
            if res.get("value_proposition"):
                brand.value_proposition = res["value_proposition"]
            if res.get("suggested_angle"):
                brand.suggested_angle = res["suggested_angle"]
            if res.get("collab_type"):
                brand.collab_type = res["collab_type"]
        except Exception as e:
            logger.debug(f"LLM pitch angle refinement fallback: {e}")

        return brand


brand_scout_agent = BrandScoutAgent()
