"""
Brand and partnership opportunity data models.
"""
import re
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator


class BrandContact(BaseModel):
    contact_email: Optional[str] = None
    pr_email: Optional[str] = None
    phone_number: Optional[str] = None
    mobile_number: Optional[str] = None
    instagram_handle: Optional[str] = None
    website: Optional[str] = None
    contact_person: Optional[str] = None
    linkedin_url: Optional[str] = None
    youtube_url: Optional[str] = None
    twitter_url: Optional[str] = None
    linktree_url: Optional[str] = None
    collab_form_url: Optional[str] = None
    meta_ad_library_url: Optional[str] = None
    email_tier: str = "Tier 2 (Marketing)"
    whatsapp_ready: bool = False
    confidence_score: int = 80
    source: str = "direct"

    @field_validator("instagram_handle", mode="before")
    @classmethod
    def clean_instagram_handle(cls, v: Optional[str]) -> Optional[str]:
        """Normalizes any handle or URL into standard @handle format, preventing doubled URLs."""
        if not v or not isinstance(v, str):
            return None
        v = v.strip()
        # Handle doubled or nested URLs, e.g. https://instagram.com/https://instagram.com/travelosei
        while "instagram.com/" in v.lower():
            v = v.split("instagram.com/")[-1]
        v = v.split("?")[0].split("#")[0].strip("/@")
        if not v or v.lower() in ["p", "reel", "stories", "explore", "about", "developer", "legal", "accounts"]:
            return None
        return f"@{v}"

    @field_validator(
        "website", "linkedin_url", "youtube_url", "twitter_url",
        "linktree_url", "collab_form_url", "meta_ad_library_url",
        mode="before"
    )
    @classmethod
    def sanitize_url(cls, v: Optional[str]) -> Optional[str]:
        """Sanitizes web URLs, fixing duplicated protocols and nested paths."""
        if not v or not isinstance(v, str):
            return None
        v = v.strip()
        if not v:
            return None
        # Fix duplicated protocols like https://https:// or http://https://
        v = re.sub(r'^(https?://)+', 'https://', v, flags=re.IGNORECASE)
        # Fix nested URLs like https://domain.com/https://domain.com/path
        match = re.search(r'https?://[^\s/]+/+(https?://.+)$', v, flags=re.IGNORECASE)
        if match:
            v = match.group(1)
        if not v.startswith("http://") and not v.startswith("https://"):
            v = f"https://{v}"
        return v

    @property
    def instagram_url(self) -> Optional[str]:
        """Returns clean canonical Instagram profile URL."""
        if self.instagram_handle:
            h = self.instagram_handle.lstrip("@")
            return f"https://instagram.com/{h}"
        return None


class BrandOpportunity(BaseModel):
    brand_name: str
    website: str
    industry: str = Field(description="e.g. DTC Skincare, Fitness Apparel, Tech Gadgets, Beverage")
    location: str = Field(default="Global", description="Target region or headquarters")
    fit_score: int = Field(default=85, description="Synergy rating from 1 to 100")
    ad_probability: str = Field(default="High (Active Instagram & Meta Ad Buyer)", description="Likelihood brand runs paid creator ads")
    collab_type: str = Field(default="UGC Video & Sponsored Reel", description="UGC, Sponsored Reel, Ambassador, Affiliate")
    value_proposition: str = Field(default="High-affinity brand partnership opportunity with verified audience overlap.", description="Why this brand would benefit from partnering with this creator")
    contact: BrandContact = Field(default_factory=BrandContact)
    suggested_angle: str = Field(default="", description="e.g. '3 reasons why I swapped X for Y' hook for ads")

    @property
    def company_name(self) -> str:
        return self.brand_name

    @property
    def confidence_score(self) -> int:
        return self.contact.confidence_score

