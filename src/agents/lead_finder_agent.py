"""
Lead Finder & Brand Contact Enrichment Agent.
Specialized in finding brands actively advertising on Instagram,
extracting verified company marketing emails, phone/mobile numbers,
and storing them in clean JSON format and SQLite database for deduplication.
"""
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from rich.console import Console
from rich.table import Table

from src.config import settings
from src.models.brand import BrandOpportunity
from src.models.creator import CreatorProfile
from src.search.brand_finder import brand_finder
from src.storage.db import db_manager

logger = logging.getLogger(__name__)
console = Console()


class LeadFinderAgent:
    """
    Identifies high-probability Instagram advertisers and builds
    structured company contact lists with emails and mobile numbers.
    Guarantees no redundant brands across multiple runs using SQLite memory.
    """

    def __init__(self, finder=None, db=None):
        self.finder = finder or brand_finder
        self.db = db or db_manager

    async def find_brand_leads(
        self,
        profile: CreatorProfile,
        location: str = "Global",
        interests: Optional[List[str]] = None,
        limit: int = 5,
    ) -> List[BrandOpportunity]:
        console.print(f"[cyan]Agent [bold]LeadFinderAgent[/bold] searching non-redundant brand leads for @{profile.username}...[/cyan]")

        # 1. Fetch previously contacted brands from SQLite database
        already_scouted: Set[str] = self.db.get_contacted_brand_names(profile.username)
        if already_scouted:
            console.print(f"[dim]Excluding {len(already_scouted)} previously scouted brands from memory to ensure 100% fresh leads.[/dim]")

        # 2. Search for fresh brand opportunities
        brands = await self.finder.search_brands(
            niche_tags=profile.niche_categories or profile.detected_hashtags,
            location=location,
            interests=interests,
            bio_text=profile.bio,
            exclude_brands=already_scouted,
            limit=limit,
        )

        # 3. Save new brands into SQLite database
        self.db.save_leads(profile.username, brands)

        # 4. Save and update cumulative leads JSON
        self.save_cumulative_leads_json(profile.username, brands)
        return brands

    def save_cumulative_leads_json(self, username: str, newly_scouted: List[BrandOpportunity]) -> Path:
        """
        Stores cumulative company names, verified marketing emails, mobile numbers,
        and ad probability into a dedicated JSON file.
        """
        all_db_rows = self.db.get_all_leads_for_creator(username)

        leads_data = []
        for idx, row in enumerate(all_db_rows, 1):
            leads_data.append({
                "id": idx,
                "company_name": row["company_name"],
                "marketing_email": row["marketing_email"],
                "mobile_number": row["mobile_number"],
                "phone_number": row["phone_number"],
                "instagram_handle": row["instagram_handle"],
                "website": row["website"],
                "industry": row["industry"],
                "location": row["location"],
                "ad_probability": row["ad_probability"],
                "fit_synergy_score": f"{row['fit_score']}%",
                "suggested_deal": row["collab_type"],
                "pitch_hook": row["pitch_hook"],
                "scouted_at": row["scouted_at"],
            })

        out_path = settings.data_dir / f"leads_{username}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(leads_data, f, indent=2)

        console.print(f"[green]✓ {len(newly_scouted)} NEW brand contacts added. Total cumulative leads in database: [bold]{len(leads_data)}[/bold][/green]")
        console.print(f"[dim]Updated: {out_path}[/dim]")
        return out_path

    def save_leads_json(self, username: str, newly_scouted: List[BrandOpportunity]) -> Path:
        """Alias for save_cumulative_leads_json."""
        self.db.save_leads(username, newly_scouted)
        return self.save_cumulative_leads_json(username, newly_scouted)

    def print_leads_table(self, username: str, brands: List[BrandOpportunity]):
        """
        Renders a dedicated, clear visual table of newly discovered Company Names,
        Emails, and Mobile numbers.
        """
        table = Table(
            title=f"Newly Discovered Brand Contacts for @{username} (Non-Redundant Leads)",
            show_lines=True,
            header_style="bold magenta",
        )
        table.add_column("#", style="dim", width=3)
        table.add_column("Company / Brand", style="bold cyan")
        table.add_column("Marketing Email", style="bold green")
        table.add_column("Mobile / Phone", style="yellow")
        table.add_column("Instagram Handle", style="magenta")
        table.add_column("Ad Probability & Fit", style="white")

        for idx, b in enumerate(brands, 1):
            email = b.contact.contact_email or "collab@" + b.website.replace("https://", "").split("/")[0]
            phone = b.contact.mobile_number or b.contact.phone_number or "Online Form"
            ig = b.contact.instagram_handle or "N/A"
            ad_info = f"{b.fit_score}% Fit\n[dim]{b.ad_probability}[/dim]"

            table.add_row(
                str(idx),
                f"{b.brand_name}\n[dim]{b.industry}[/dim]",
                email,
                phone,
                ig,
                ad_info,
            )

        console.print(table)


lead_finder_agent = LeadFinderAgent()
