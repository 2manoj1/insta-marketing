"""
Pitch Drafter Agent.
Acts as an experienced Influencer Marketing Manager pitching creators to brands.
Drafts high-converting cold emails and Instagram DMs for UGC videos and sponsored ads.
"""
import logging
from typing import List, Optional
from rich.console import Console

from src.llm.client import llm_client
from src.models.brand import BrandOpportunity
from src.models.creator import CreatorProfile
from src.models.outreach import CollaborationDeliverable, OutreachPitch

logger = logging.getLogger(__name__)
console = Console()


class PitchDrafterAgent:
    def __init__(self, llm=None):
        self.llm = llm or llm_client

    def draft_pitches(
        self,
        profile: CreatorProfile,
        opportunities: List[BrandOpportunity],
    ) -> List[OutreachPitch]:
        console.print(f"[cyan]Agent [bold]PitchDrafterAgent[/bold] drafting customized pitches for {len(opportunities)} brands...[/cyan]")
        pitches: List[OutreachPitch] = []

        for brand in opportunities:
            pitch = self._draft_single_pitch(profile, brand)
            pitches.append(pitch)
            console.print(f"[green]✓ Pitch crafted for [bold]{brand.brand_name}[/bold] (Subject: \"{pitch.subject_line}\")[/green]")

        return pitches

    def _draft_single_pitch(self, profile: CreatorProfile, brand: BrandOpportunity) -> OutreachPitch:
        recipient = brand.contact.contact_email or f"partnerships@{brand.website.replace('https://', '').replace('http://', '').split('/')[0]}"
        recipient_phone = brand.contact.mobile_number or brand.contact.phone_number
        niche_str = ", ".join(profile.niche_categories or ["Tech & Lifestyle"])
        tier_str = profile.ugc_profile.tier if profile.ugc_profile else "Content Creator"
        suggested_rate = profile.ugc_profile.estimated_rate_per_ugc_video_usd if profile.ugc_profile else "$250 - $450"

        prompt = f"""
You are an expert Influencer Marketing Talent Manager representing the creator @{profile.username}.
You are reaching out to the marketing / influencer partnerships team at {brand.brand_name} ({brand.website}).

Creator Info:
- Handle: @{profile.username}
- Name: {profile.full_name}
- Followers: {profile.followers_count:,}
- Niche: {niche_str}
- Creator Tier: {tier_str}
- Suggested Pitch Angle / Video Hook: {brand.suggested_angle or "Authentic product integration"}
- Brand Industry: {brand.industry}
- Collaboration Format: {brand.collab_type}

Draft a high-converting, polite, and modern pitch package in JSON format:
{{
  "subject_line": "Catchy, professional subject line (e.g. Quick question re: {brand.brand_name} UGC / Collab Idea with @{profile.username})",
  "email_body": "Complete cold email (greeting, authentic brand appreciation, creator intro & metrics, proposed collaboration concept with hooks, deliverable proposal, and clear frictionless call-to-action). Sign off as 'Talent Management for @{profile.username}'.",
  "instagram_dm": "Short, punchy 3-4 sentence message suitable for Instagram direct message to {brand.brand_name}'s social team.",
  "whatsapp_pitch": "Short, professional 2-3 sentence WhatsApp outreach message introducing @{profile.username} ({profile.followers_count:,} followers) and proposing a 20-second UGC sample concept for {brand.brand_name}.",
  "deliverables": [
    {{
      "title": "1x High-Converting 9:16 UGC Video (Organic & Paid Ad Ready)",
      "description": "Engaging vertical video formatted for TikTok/Reels with 2 alternate opening hooks.",
      "usage_rights": "30-day paid social media advertising usage rights + raw B-roll"
    }},
    {{
      "title": "1x Dedicated Instagram Reel & Story Amplification",
      "description": "Posted organically to @{profile.username}'s feed tagging @{brand.brand_name} with link sticker.",
      "usage_rights": "Organic feed post + story highlight"
    }}
  ],
  "call_to_action": "Frictionless low-pressure CTA sentence (e.g., 'Would it be alright if I sent over a 20-second sample storyboard concept for your team to review?')"
}}
"""

        try:
            data = self.llm.generate_json([
                {"role": "system", "content": "You are a top-tier influencer talent manager who secures 5-figure UGC and brand sponsorships for creators. Return strict JSON."},
                {"role": "user", "content": prompt}
            ])

            deliverables = []
            for d in data.get("deliverables", []):
                deliverables.append(
                    CollaborationDeliverable(
                        title=d.get("title", "1x UGC Ad Video"),
                        description=d.get("description", "High quality vertical video"),
                        usage_rights=d.get("usage_rights", "30-day ad usage rights"),
                    )
                )

            return OutreachPitch(
                brand_name=brand.brand_name,
                recipient_email=recipient,
                recipient_phone=recipient_phone,
                creator_username=profile.username,
                subject_line=data.get("subject_line", f"Collab proposal: {brand.brand_name} x @{profile.username} (UGC Ad Concept)"),
                email_body=data.get("email_body", self._fallback_email(profile, brand)),
                instagram_dm=data.get("instagram_dm", self._fallback_dm(profile, brand)),
                whatsapp_pitch=data.get("whatsapp_pitch", self._fallback_whatsapp(profile, brand)),
                deliverables=deliverables or self._default_deliverables(),
                call_to_action=data.get("call_to_action", "Can I send over a quick 20-second storyboard for your team to inspect?"),
            )
        except Exception as e:
            logger.warning(f"LLM pitch generation fallback: {e}")
            return OutreachPitch(
                brand_name=brand.brand_name,
                recipient_email=recipient,
                recipient_phone=recipient_phone,
                creator_username=profile.username,
                subject_line=f"Quick Collab Idea for {brand.brand_name} + @{profile.username}",
                email_body=self._fallback_email(profile, brand),
                instagram_dm=self._fallback_dm(profile, brand),
                whatsapp_pitch=self._fallback_whatsapp(profile, brand),
                deliverables=self._default_deliverables(),
                call_to_action="Can I send over a brief 20-second video concept for your team to review?",
            )

    def _fallback_email(self, profile: CreatorProfile, brand: BrandOpportunity) -> str:
        return f"""Hi {brand.brand_name} Partnerships Team,

I'm reaching out from the talent management team for @{profile.username} ({profile.followers_count:,} engaged followers in {', '.join(profile.niche_categories or ['Lifestyle & Tech'])}).

We've been genuinely following {brand.brand_name}'s recent work, and we noticed your focus on {brand.industry}. @{profile.username}'s audience consists heavily of creators and young professionals who actively purchase products like yours.

We would love to produce a high-converting UGC video or dedicated Instagram Reel showcasing {brand.brand_name}.

Proposed Creative Concept:
- Concept Angle: {brand.suggested_angle or 'Everyday carry & problem-solution demonstration'}
- Deliverable: 1x 9:16 vertical video asset (with 2 distinct opening hooks) + 30 days paid ad whitelisting rights.

Can I send over a quick 20-second storyboard concept for your team to review this week?

Best regards,
Talent Partnerships & Management for @{profile.username}
{profile.instagram_url}"""

    def _fallback_dm(self, profile: CreatorProfile, brand: BrandOpportunity) -> str:
        return f"Hey {brand.brand_name} team! 👋 Reaching out from @{profile.username}'s management ({profile.followers_count:,} followers). We love your products and have a high-converting UGC video concept tailored for your paid ads. Who is the best person on your influencer marketing team to send a quick 20-second concept to?"

    def _fallback_whatsapp(self, profile: CreatorProfile, brand: BrandOpportunity) -> str:
        return f"Hi {brand.brand_name} Team! 👋 Reaching out on behalf of @{profile.username} ({profile.followers_count:,} followers in {', '.join(profile.niche_categories[:2] if profile.niche_categories else ['Lifestyle'])}). We have an aesthetic UGC video concept prepared for {brand.brand_name} ready for your paid social ads. Would you like me to share a 20-second storyboard preview here?"

    def _default_deliverables(self) -> List[CollaborationDeliverable]:
        return [
            CollaborationDeliverable(
                title="1x Direct-Response 9:16 UGC Video",
                description="Engineered for high-performing Meta/TikTok ads, complete with hook variations and captions.",
                usage_rights="30 days paid advertising usage rights + raw footage",
            ),
            CollaborationDeliverable(
                title="1x Organic Sponsored Reel + Link in Bio",
                description="Shared natively to @creator's feed with partner tag and interactive story swipe-up.",
                usage_rights="Organic feed permanence",
            ),
        ]


pitch_drafter_agent = PitchDrafterAgent()
