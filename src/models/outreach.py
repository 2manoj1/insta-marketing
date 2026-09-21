"""
Outreach pitch and campaign models.
"""
from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime, timezone


class CollaborationDeliverable(BaseModel):
    title: str = Field(description="e.g. 1 High-Converting 9:16 UGC Ad Video")
    description: str = Field(description="Details including hook, product demonstration, and call to action")
    usage_rights: str = Field(default="30 days paid ad usage rights + raw footage", description="Licensing terms")


class OutreachPitch(BaseModel):
    brand_name: str
    recipient_email: str
    creator_username: str
    subject_line: str
    email_body: str
    instagram_dm: str
    deliverables: List[CollaborationDeliverable] = Field(default_factory=list)
    call_to_action: str = Field(default="Can I send over a 20-second sample concept video for your team to review?")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: str = Field(default="draft", description="draft, approved, sent")


class CampaignSummary(BaseModel):
    creator_username: str
    creator_niche: List[str]
    total_brands_discovered: int
    pitches: List[OutreachPitch]
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
