"""
Negotiation & Commercial Rate Pricing Skill.
Computes market-rate commercial deliverables and rate cards for creators
based on follower tiers, niche CPM value, and Meta ad usage rights.
"""
import logging
from typing import Any, Dict, List, Optional
from src.models.creator import CreatorProfile

logger = logging.getLogger(__name__)

# Premium niches that command higher CPM rates in the ad market
HIGH_CPM_NICHES = {
    "tech": 1.35,
    "gadgets": 1.30,
    "luxury": 1.40,
    "travel": 1.25,
    "hospitality": 1.30,
    "finance": 1.50,
    "beauty": 1.15,
    "skincare": 1.20,
    "fitness": 1.15,
}


class NegotiationPricingSkill:
    """
    Computes commercial rate cards and deal structures for creators.
    """

    name: str = "negotiation_pricing"
    description: str = "Calculates market rates for UGC ad rights, sponsored reels, and brand bundle packages."

    def calculate_rate_card(self, profile: CreatorProfile, niche_hint: Optional[str] = None) -> Dict[str, Any]:
        followers = profile.followers_count or 10000
        
        # 1. Determine Creator Tier
        if followers < 10000:
            tier = "Nano Creator"
            base_ugc = (150, 300)
            base_reel = (200, 350)
            base_bundle = (320, 550)
        elif followers < 50000:
            tier = "Micro Influencer"
            base_ugc = (300, 550)
            base_reel = (450, 750)
            base_bundle = (650, 1100)
        elif followers < 250000:
            tier = "Mid-Tier Influencer"
            base_ugc = (550, 1100)
            base_reel = (850, 1800)
            base_bundle = (1250, 2600)
        else:
            tier = "Macro Influencer"
            base_ugc = (1200, 2800)
            base_reel = (2200, 5500)
            base_bundle = (3000, 7500)

        # 2. Check Niche Multiplier
        multiplier = 1.0
        niche_text = f"{niche_hint or ''} {' '.join(profile.niche_categories)} {profile.bio}".lower()
        for kw, mult in HIGH_CPM_NICHES.items():
            if kw in niche_text:
                multiplier = max(multiplier, mult)

        # 3. Apply Multiplier
        ugc_min = int(base_ugc[0] * multiplier)
        ugc_max = int(base_ugc[1] * multiplier)
        reel_min = int(base_reel[0] * multiplier)
        reel_max = int(base_reel[1] * multiplier)
        bundle_min = int(base_bundle[0] * multiplier)
        bundle_max = int(base_bundle[1] * multiplier)

        return {
            "creator_tier": tier,
            "followers_count": followers,
            "niche_multiplier": multiplier,
            "ugc_video_30d_ads": {
                "rate_range": f"${ugc_min:,} - ${ugc_max:,}",
                "deliverable": "1x 9:16 Vertical UGC Video (Hook + Problem + Demo + CTA) with 30-day Meta ad usage rights",
            },
            "organic_sponsored_reel": {
                "rate_range": f"${reel_min:,} - ${reel_max:,}",
                "deliverable": "1x Dedicated Instagram Reel post + 3x Story frames with direct swipe/sticker link",
            },
            "growth_bundle_package": {
                "rate_range": f"${bundle_min:,} - ${bundle_max:,}",
                "deliverable": "1x Dedicated Instagram Reel + 1x Raw UGC Cut for Brand Ads (30-day rights) - Best Value",
            },
            "suggested_initial_anchor_rate": f"${int((ugc_min + ugc_max) / 2):,}",
        }

    def execute(self, profile: CreatorProfile, niche_hint: Optional[str] = None) -> Dict[str, Any]:
        return self.calculate_rate_card(profile, niche_hint)


negotiation_pricing_skill = NegotiationPricingSkill()
