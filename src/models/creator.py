"""
Creator data models for profile scraping and UGC profiling.
"""
from typing import List, Optional
from pydantic import BaseModel, Field


class PostDetail(BaseModel):
    id: Optional[str] = None
    caption: str = ""
    hashtags: List[str] = Field(default_factory=list)
    is_reel: bool = False
    likes_count: Optional[int] = None
    comments_count: Optional[int] = None
    url: Optional[str] = None


class UGCReadiness(BaseModel):
    tier: str = Field(default="Micro-influencer", description="Nano (<10k), Micro (10k-50k), Mid-tier (50k-500k), Macro (500k+)")
    ugc_strengths: List[str] = Field(default_factory=list, description="Top creator strengths e.g. aesthetic visuals, authentic product tests, unboxing")
    content_pillars: List[str] = Field(default_factory=list, description="Primary content topics e.g. Tech accessories, lifestyle, wellness")
    estimated_rate_per_ugc_video_usd: str = Field(default="$150 - $350", description="Recommended pricing for 1 UGC video asset")
    estimated_rate_per_sponsored_reel_usd: str = Field(default="$250 - $600", description="Recommended pricing for 1 sponsored reel")
    suggested_ad_formats: List[str] = Field(default_factory=lambda: ["Direct-response UGC Video", "Instagram Reel + Story Amplification", "Product Review"])


class CreatorProfile(BaseModel):
    username: str
    full_name: str = ""
    bio: str = ""
    external_url: Optional[str] = None
    followers_count: int = 0
    following_count: int = 0
    posts_count: int = 0
    is_verified: bool = False
    location_hint: Optional[str] = None
    recent_posts: List[PostDetail] = Field(default_factory=list)
    detected_hashtags: List[str] = Field(default_factory=list)
    niche_categories: List[str] = Field(default_factory=list)
    contact_email: Optional[str] = None
    ugc_profile: Optional[UGCReadiness] = None

    @property
    def instagram_url(self) -> str:
        return f"https://www.instagram.com/{self.username}/"
