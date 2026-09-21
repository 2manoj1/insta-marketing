"""
Brand and partnership opportunity data models.
"""
from typing import List, Optional
from pydantic import BaseModel, Field


class BrandContact(BaseModel):
    contact_email: Optional[str] = None
    pr_email: Optional[str] = None
    phone_number: Optional[str] = None
    mobile_number: Optional[str] = None
    instagram_handle: Optional[str] = None
    website: Optional[str] = None
    contact_person: Optional[str] = None
    source: str = "direct"


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
