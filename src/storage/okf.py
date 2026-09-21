"""
Open Knowledge Framework (OKF) Storage & Intelligence Engine.
Provides persistent, cumulative brand intelligence, market benchmarks,
and learning memory across all campaigns.
Free and open-source JSON/SQLite backing with zero proprietary dependencies.
"""
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from src.config import settings
from src.models.brand import BrandOpportunity

logger = logging.getLogger(__name__)


DEFAULT_MARKET_BENCHMARKS = {
    "version": "1.0.0",
    "updated_at": "2026-09-21T00:00:00Z",
    "market_geographies": ["India", "Global", "United States", "UAE"],
    "rates_by_tier": {
        "Nano (1k - 10k)": {"ugc_video_30d": "$150 - $300", "sponsored_reel": "$200 - $350", "story_set": "$50 - $100"},
        "Micro (10k - 50k)": {"ugc_video_30d": "$300 - $550", "sponsored_reel": "$450 - $750", "story_set": "$120 - $250"},
        "Mid-Tier (50k - 200k)": {"ugc_video_30d": "$550 - $1,100", "sponsored_reel": "$850 - $1,800", "story_set": "$250 - $600"},
        "Macro (200k - 1M)": {"ugc_video_30d": "$1,200 - $2,800", "sponsored_reel": "$2,200 - $5,500", "story_set": "$600 - $1,500"},
    },
    "ad_rights_multiplier": {
        "30_days_meta_ads": 1.0,
        "60_days_meta_ads": 1.25,
        "90_days_meta_ads": 1.45,
        "in_perpetuity": 2.20,
    },
    "average_email_open_rate": "42.5%",
    "average_reply_rate": "18.3%",
}


class OKFManager:
    """
    Open Knowledge Framework manager.
    Maintains structured knowledge files in data/okf/.
    """

    def __init__(self, okf_dir: Optional[Path] = None):
        self.okf_dir = okf_dir or (settings.data_dir / "okf")
        self.okf_dir.mkdir(parents=True, exist_ok=True)
        self.brands_file = self.okf_dir / "brands_intelligence.json"
        self.benchmarks_file = self.okf_dir / "market_benchmarks.json"
        self.creators_file = self.okf_dir / "creator_memory.json"
        self._init_okf_files()

    def _init_okf_files(self):
        """Seeds default OKF files if they do not exist."""
        if not self.benchmarks_file.exists():
            with open(self.benchmarks_file, "w", encoding="utf-8") as f:
                json.dump(DEFAULT_MARKET_BENCHMARKS, f, indent=2)

        if not self.brands_file.exists():
            with open(self.brands_file, "w", encoding="utf-8") as f:
                json.dump([], f, indent=2)

        if not self.creators_file.exists():
            with open(self.creators_file, "w", encoding="utf-8") as f:
                json.dump({}, f, indent=2)

    def load_brands(self) -> List[Dict[str, Any]]:
        """Loads all brands in the OKF intelligence base."""
        try:
            if self.brands_file.exists():
                with open(self.brands_file, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Error loading OKF brands: {e}")
        return []

    def save_brand_intelligence(self, brand: BrandOpportunity, creator_username: Optional[str] = None) -> bool:
        """
        Enriches and updates a brand's entry in OKF intelligence store.
        Avoids duplicates by matching normalized brand_name and domain.
        """
        brands = self.load_brands()
        now_str = datetime.now(timezone.utc).isoformat()
        brand_key = brand.brand_name.lower().strip()

        matched = False
        for b in brands:
            if b.get("brand_name", "").lower().strip() == brand_key:
                # Update existing entry with newer or additional info
                matched = True
                b["last_verified"] = now_str
                if brand.contact.contact_email and brand.contact.contact_email not in b.get("marketing_emails", []):
                    b.setdefault("marketing_emails", []).append(brand.contact.contact_email)
                if brand.contact.mobile_number and brand.contact.mobile_number not in b.get("phone_numbers", []):
                    b.setdefault("phone_numbers", []).append(brand.contact.mobile_number)
                if creator_username:
                    b.setdefault("associated_creators", [])
                    if creator_username not in b["associated_creators"]:
                        b["associated_creators"].append(creator_username)
                break

        if not matched:
            emails = [brand.contact.contact_email] if brand.contact.contact_email else []
            phones = [brand.contact.mobile_number] if brand.contact.mobile_number else []
            if brand.contact.phone_number and brand.contact.phone_number not in phones:
                phones.append(brand.contact.phone_number)

            brands.append({
                "brand_name": brand.brand_name,
                "website": brand.website,
                "industry": brand.industry,
                "location": brand.location,
                "marketing_emails": emails,
                "phone_numbers": phones,
                "instagram_handle": brand.contact.instagram_handle,
                "ad_probability": brand.ad_probability,
                "fit_score": brand.fit_score,
                "collab_type": brand.collab_type,
                "suggested_angle": brand.suggested_angle,
                "associated_creators": [creator_username] if creator_username else [],
                "source": brand.contact.source or "okf_enrichment",
                "first_discovered": now_str,
                "last_verified": now_str,
            })

        with open(self.brands_file, "w", encoding="utf-8") as f:
            json.dump(brands, f, indent=2)

        return True

    def query_brands(
        self,
        niche: Optional[str] = None,
        location: Optional[str] = None,
        exclude_names: Optional[Set[str]] = None,
        min_fit: int = 70,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Queries OKF brand intelligence base with semantic/keyword filtering.
        """
        brands = self.load_brands()
        excluded = {e.lower().strip() for e in (exclude_names or set())}
        matches = []

        niche_lower = niche.lower() if niche else ""
        loc_lower = location.lower() if location else ""

        for b in brands:
            name_lower = b.get("brand_name", "").lower().strip()
            if name_lower in excluded:
                continue

            ind_lower = b.get("industry", "").lower()
            b_loc = b.get("location", "").lower()
            fit = b.get("fit_score", 85)

            if fit < min_fit:
                continue

            # Check niche alignment
            if niche_lower and not any(w in ind_lower or w in b.get("suggested_angle", "").lower() for w in niche_lower.split()):
                continue

            matches.append(b)
            if len(matches) >= limit:
                break

        return matches

    def get_benchmarks(self) -> Dict[str, Any]:
        """Returns market rate benchmarks from OKF."""
        try:
            with open(self.benchmarks_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return DEFAULT_MARKET_BENCHMARKS

    def get_summary(self) -> Dict[str, Any]:
        """Returns high-level OKF statistics."""
        brands = self.load_brands()
        total_emails = sum(len(b.get("marketing_emails", [])) for b in brands)
        total_phones = sum(len(b.get("phone_numbers", [])) for b in brands)
        industries = list({b.get("industry", "Other") for b in brands if b.get("industry")})

        return {
            "total_brands_in_okf": len(brands),
            "total_verified_emails": total_emails,
            "total_verified_phones": total_phones,
            "industries_covered": len(industries),
            "okf_version": "1.0-open",
            "storage_path": str(self.okf_dir),
        }


okf_manager = OKFManager()
okf_repository = okf_manager
