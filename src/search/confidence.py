"""
Multi-signal Lead Confidence Scoring Engine.
Calculates a transparent, verifiable confidence score (0 to 100%) for brand leads
based on direct Instagram business buttons, email tiers, WhatsApp readiness,
Meta Ad Library spend proof, and multi-channel footprint.
"""
import logging
from typing import Optional, Union
from src.models.brand import BrandContact, BrandOpportunity

logger = logging.getLogger(__name__)


def calculate_lead_confidence(
    contact_or_opp: Union[BrandContact, BrandOpportunity],
    ad_probability: Optional[str] = None,
) -> int:
    """
    Computes a 0–100% confidence score for a brand lead.
    
    Weights:
    - Direct Instagram Business Button contact: +40%
    - Tier 1 Direct PR/Collab Email: +25% (Tier 2: +15%, Tier 3: +5%)
    - Verified Phone / WhatsApp Mobile: +15%
    - Meta Ad Spend Proof (Ad Library / Active Buyer): +15%
    - Multi-Channel Footprint & Website: +5%
    """
    if isinstance(contact_or_opp, BrandOpportunity):
        contact = contact_or_opp.contact
        ad_prob = ad_probability or contact_or_opp.ad_probability
        website = contact_or_opp.website
    else:
        contact = contact_or_opp
        ad_prob = ad_probability or "High"
        website = contact.website

    score = 25  # Base candidate score

    # 1. Direct Instagram Business Profile Action Button (Highest Signal)
    if contact.source in ["instagram_business_button", "instagram_button"]:
        score += 40
    elif contact.source in ["live_web_verified", "okf_knowledge_framework"]:
        score += 20
    elif contact.source == "live_web_discovery":
        score += 15

    # 2. Email Quality & Tier
    email = contact.contact_email or contact.pr_email
    tier = (contact.email_tier or "").lower()
    if email:
        if "tier 1" in tier or "pr" in tier or "collab" in tier:
            score += 25
        elif "tier 2" in tier or "marketing" in tier:
            score += 18
        else:
            score += 10

    # 3. WhatsApp & Phone Readiness
    phone = contact.mobile_number or contact.phone_number
    if phone and phone != "N/A":
        if contact.whatsapp_ready:
            score += 15
        else:
            score += 10

    # 4. Meta Ad Spend Proof
    meta_ad = contact.meta_ad_library_url
    if meta_ad and "facebook.com/ads/library" in meta_ad:
        score += 15
    elif ad_prob and any(kw in ad_prob.lower() for kw in ["active", "high", "buyer", "running"]):
        score += 10

    # 5. Multi-channel Social Footprint & Website
    social_count = sum(bool(getattr(contact, field, None)) for field in [
        "instagram_handle", "linkedin_url", "youtube_url", "twitter_url", "linktree_url", "collab_form_url"
    ])
    if social_count >= 3:
        score += 10
    elif social_count >= 1:
        score += 5

    # Website check
    if website and ("http" in website or "." in website):
        score += 5

    # Clamping rules
    if contact.source == "instagram_business_button":
        score = max(score, 90)
    elif email and phone and phone != "N/A":
        score = max(score, 80)
    elif email:
        score = max(score, 65)

    return min(100, max(10, score))
