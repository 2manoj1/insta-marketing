"""
Creator Profiler Agent.
Synthesizes creator profile, recent posts, and niche cues to build an Influencer Media Kit
and UGC monetization strategy.
"""
import logging
from typing import Optional
from rich.console import Console

from src.llm.client import llm_client
from src.models.creator import CreatorProfile, UGCReadiness

logger = logging.getLogger(__name__)
console = Console()


class ProfilerAgent:
    """
    Evaluates creator profile to determine UGC strengths, pricing rates,
    and brand value propositions.
    """

    def __init__(self, llm=None):
        self.llm = llm or llm_client

    def profile_creator(self, profile: CreatorProfile) -> CreatorProfile:
        console.print(f"[cyan]Agent [bold]ProfilerAgent[/bold] analyzing @{profile.username}...[/cyan]")

        # Prepare summary prompt
        post_captions = "\n".join([f"- {p.caption}" for p in profile.recent_posts[:6] if p.caption])
        hashtags = ", ".join(profile.detected_hashtags[:15])

        prompt = f"""
Analyze this Instagram creator for brand sponsorship and UGC (User-Generated Content) video opportunities:

Handle: @{profile.username}
Name: {profile.full_name}
Bio: {profile.bio}
Followers: {profile.followers_count:,}
Following: {profile.following_count:,}
Posts: {profile.posts_count:,}
Recent Captions:
{post_captions or "N/A"}
Hashtags: {hashtags or "N/A"}

Please synthesize:
1. tier: One of "Nano-creator (<10K)", "Micro-influencer (10K-50K)", "Mid-tier (50K-250K)", "Macro (250K+)"
2. ugc_strengths: Array of 3-4 top creator strengths (e.g. authentic review, aesthetic desk visuals, voiceover clarity)
3. content_pillars: Array of 3 main topics/niches
4. estimated_rate_per_ugc_video_usd: Recommended price range for 1 UGC video asset with 30-day ad usage rights (e.g. "$200 - $400")
5. estimated_rate_per_sponsored_reel_usd: Recommended price range for 1 posted sponsored reel (e.g. "$350 - $700")
6. suggested_ad_formats: Array of 3 high-converting ad styles (e.g. "Problem vs Solution", "3 Reasons Why", "Aesthetic Day in Life")

Respond strictly in JSON matching the above keys.
"""

        try:
            data = self.llm.generate_json([
                {"role": "system", "content": "You are a senior Influencer Marketing Talent Manager who helps creators monetize via UGC and brand deals. Return valid JSON only."},
                {"role": "user", "content": prompt}
            ])

            ugc = UGCReadiness(
                tier=data.get("tier", self._estimate_tier(profile.followers_count)),
                ugc_strengths=data.get("ugc_strengths", ["Authentic product demonstration", "Engaged organic community", "Clean aesthetic"]),
                content_pillars=data.get("content_pillars", profile.niche_categories or ["Lifestyle", "Tech & Gadgets"]),
                estimated_rate_per_ugc_video_usd=data.get("estimated_rate_per_ugc_video_usd", self._estimate_ugc_rate(profile.followers_count)),
                estimated_rate_per_sponsored_reel_usd=data.get("estimated_rate_per_sponsored_reel_usd", self._estimate_reel_rate(profile.followers_count)),
                suggested_ad_formats=data.get("suggested_ad_formats", ["Problem-Solution Hook", "Product Breakdown", "Desk Integration"]),
            )
            profile.ugc_profile = ugc
            if data.get("content_pillars"):
                profile.niche_categories = data["content_pillars"]

            console.print(f"[green]✓ Creator Profile Synthesized: {ugc.tier} | UGC Rate: {ugc.estimated_rate_per_ugc_video_usd}[/green]")
            return profile

        except Exception as e:
            logger.warning(f"LLM profiling failed ({e}). Using algorithmic marketing manager heuristics.")
            profile.ugc_profile = self._fallback_profile(profile)
            return profile

    def _estimate_tier(self, followers: int) -> str:
        if followers < 10_000:
            return "Nano-creator (<10K)"
        elif followers < 50_000:
            return "Micro-influencer (10K-50K)"
        elif followers < 250_000:
            return "Mid-tier Influencer (50K-250K)"
        else:
            return "Macro-influencer (250K+)"

    def _estimate_ugc_rate(self, followers: int) -> str:
        if followers < 10_000:
            return "$120 - $250"
        elif followers < 50_000:
            return "$200 - $450"
        elif followers < 250_000:
            return "$400 - $900"
        else:
            return "$800 - $2,000+"

    def _estimate_reel_rate(self, followers: int) -> str:
        if followers < 10_000:
            return "$150 - $350"
        elif followers < 50_000:
            return "$300 - $750"
        elif followers < 250_000:
            return "$650 - $1,800"
        else:
            return "$1,500 - $4,500+"

    def _fallback_profile(self, profile: CreatorProfile) -> UGCReadiness:
        return UGCReadiness(
            tier=self._estimate_tier(profile.followers_count),
            ugc_strengths=["High-converting authentic reviews", "Engaging vertical video format", "Product integration into daily routine"],
            content_pillars=profile.niche_categories or ["Consumer Tech", "Desk Setup", "Productivity"],
            estimated_rate_per_ugc_video_usd=self._estimate_ugc_rate(profile.followers_count),
            estimated_rate_per_sponsored_reel_usd=self._estimate_reel_rate(profile.followers_count),
            suggested_ad_formats=["Problem-Solution Hook", "Honest 30-day Experience", "Visual Aesthetic Showcase"],
        )


profiler_agent = ProfilerAgent()
