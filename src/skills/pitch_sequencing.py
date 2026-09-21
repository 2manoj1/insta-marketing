"""
Multi-Channel Pitch Sequencing Skill.
Generates a synchronized 3-touchpoint outreach sequence:
1. Personalized Cold Email (Optimal 45-80 words, high deliverability, soft CTA)
2. Casual, Direct Instagram DM
3. Short Professional WhatsApp Message (for brands with mobile support)
"""
import logging
from typing import Any, Dict, Optional
from src.models.brand import BrandOpportunity
from src.models.creator import CreatorProfile

logger = logging.getLogger(__name__)


class PitchSequencingSkill:
    """
    Skill for drafting multi-channel outreach pitches tailored for brands.
    """

    name: str = "pitch_sequencing"
    description: str = "Generates high-converting 3-channel pitch sequences (Email + Instagram DM + WhatsApp outreach)."

    def generate_sequence(
        self,
        profile: CreatorProfile,
        opportunity: BrandOpportunity,
        rate_card: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, str]:
        brand_name = opportunity.brand_name
        contact_name = opportunity.contact.contact_person or f"{brand_name} Marketing Team"
        creator_name = profile.full_name or f"@{profile.username}"
        handle = f"@{profile.username}"
        followers_k = f"{round(profile.followers_count / 1000, 1)}K" if profile.followers_count else "engaged"
        niche = profile.niche_categories[0] if profile.niche_categories else "lifestyle"
        hook = opportunity.suggested_angle or f"custom content showcasing {brand_name}"

        # 1. Subject line (crisp, optimal 35-55 chars)
        subject = f"Collab idea for {brand_name} x {handle}"

        # 2. Cold Email Body (Concise, punchy, value-first)
        email_body = f"""Hi {contact_name},

I've been following {brand_name}'s recent campaigns and love how you're presenting your products.

I create high-performing {niche} content for an active community of {followers_k} followers ({handle}). My audience is highly aligned with {brand_name}'s core customer base.

Concept for you:
"{hook}"

I'd love to produce a high-converting 9:16 vertical UGC video ad with 30-day paid usage rights, or feature {brand_name} in an organic Reel.

Would you be open to me sending over a 20-second storyboard or media kit this week?

Best regards,
{creator_name}
{handle} | Instagram
{profile.contact_email or ''}"""

        # 3. Instagram DM Body (Brief, mobile-optimized, no walls of text)
        dm_body = f"""Hey {brand_name} team! 👋

Love your recent posts. I'm {creator_name} ({handle}, {followers_k} followers in {niche}).

Had a high-energy video concept that would fit your paid Meta ads & Reels:
👉 "{hook}"

Who's the best person on your marketing team to send a quick 20-sec sample to? Cheers!"""

        # 4. WhatsApp / SMS Message (Friendly & professional)
        phone = opportunity.contact.mobile_number or opportunity.contact.phone_number or ""
        whatsapp_body = f"""Hi {brand_name} Marketing Team, this is {creator_name} ({handle}). 

Saw your active Instagram campaigns and wanted to share a quick creative collaboration idea for your UGC ad pipeline: "{hook}".

Sent a quick note to your partnerships email—would love to connect if you're exploring creator ad rights this quarter! 🙏"""

        return {
            "subject": subject,
            "email_body": email_body,
            "dm_body": dm_body,
            "whatsapp_body": whatsapp_body,
            "recipient_email": opportunity.contact.contact_email or f"collab@{opportunity.website.replace('https://', '').split('/')[0]}",
            "recipient_phone": phone,
            "brand_name": brand_name,
        }

    def execute(
        self,
        profile: CreatorProfile,
        opportunity: BrandOpportunity,
        rate_card: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, str]:
        return self.generate_sequence(profile, opportunity, rate_card)


pitch_sequencing_skill = PitchSequencingSkill()
