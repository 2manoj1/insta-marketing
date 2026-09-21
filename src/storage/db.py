"""
SQLite database manager for tracking and deduplicating brand leads across runs.
Ensures that every execution discovers fresh, unique brand opportunities and contacts.
"""
import sqlite3
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from src.config import settings
from src.models.brand import BrandOpportunity, BrandContact

logger = logging.getLogger(__name__)


class DatabaseManager:
    """
    Manages SQLite database for persistent lead storage and deduplication.
    """

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or (settings.data_dir / "leads.db")
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """Creates tables with unique constraints to prevent duplicate pitches."""
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS brand_leads (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    creator_username TEXT NOT NULL,
                    company_name TEXT NOT NULL,
                    marketing_email TEXT NOT NULL,
                    mobile_number TEXT,
                    phone_number TEXT,
                    instagram_handle TEXT,
                    website TEXT,
                    industry TEXT,
                    location TEXT,
                    ad_probability TEXT,
                    fit_score INTEGER,
                    collab_type TEXT,
                    pitch_hook TEXT,
                    scouted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    status TEXT DEFAULT 'scouted',
                    UNIQUE(creator_username, company_name)
                );
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_creator_company 
                ON brand_leads(creator_username, company_name);
            """)
            conn.commit()

    def get_contacted_brand_names(self, creator_username: str) -> Set[str]:
        """
        Returns a set of lowercase company names that have already been scouted
        for this creator.
        """
        username = creator_username.lower().lstrip("@")
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT LOWER(company_name) as name FROM brand_leads WHERE LOWER(creator_username) = ?",
                (username,)
            )
            return {row["name"] for row in cursor.fetchall()}

    def save_leads(self, creator_username: str, brands: List[BrandOpportunity]) -> int:
        """
        Inserts new brands into SQLite, skipping any that were previously saved.
        Returns the count of newly inserted records.
        """
        username = creator_username.lower().lstrip("@")
        inserted = 0

        with self._get_connection() as conn:
            for b in brands:
                email = b.contact.contact_email or "collab@" + b.website.replace("https://", "").replace("http://", "").split("/")[0]
                mobile = b.contact.mobile_number or b.contact.phone_number or "N/A"
                phone = b.contact.phone_number or "N/A"
                ig = b.contact.instagram_handle or "@" + b.brand_name.lower().replace(" ", "")

                try:
                    conn.execute("""
                        INSERT INTO brand_leads (
                            creator_username, company_name, marketing_email, mobile_number,
                            phone_number, instagram_handle, website, industry, location,
                            ad_probability, fit_score, collab_type, pitch_hook, scouted_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        username,
                        b.brand_name,
                        email,
                        mobile,
                        phone,
                        ig,
                        b.website,
                        b.industry,
                        b.location,
                        b.ad_probability,
                        b.fit_score,
                        b.collab_type,
                        b.suggested_angle,
                        datetime.now(timezone.utc).isoformat()
                    ))
                    inserted += 1
                except sqlite3.IntegrityError:
                    # Already exists for this creator
                    pass

            conn.commit()

        return inserted

    def get_all_leads_for_creator(self, creator_username: str) -> List[Dict]:
        """Returns all cumulative unique leads stored for a creator."""
        username = creator_username.lower().lstrip("@")
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM brand_leads WHERE LOWER(creator_username) = ? ORDER BY id DESC",
                (username,)
            )
            return [dict(row) for row in cursor.fetchall()]

    def count_leads(self, creator_username: str) -> int:
        """Counts total unique leads discovered so far for a creator."""
        username = creator_username.lower().lstrip("@")
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT COUNT(*) as cnt FROM brand_leads WHERE LOWER(creator_username) = ?",
                (username,)
            )
            row = cursor.fetchone()
            return row["cnt"] if row else 0

    def get_all_leads(self, creator_username: Optional[str] = None, search: Optional[str] = None, limit: int = 200) -> List[Dict]:
        """
        Retrieves leads across all creators or filtered by creator/keyword without running agents.
        """
        query = "SELECT * FROM brand_leads WHERE 1=1"
        params: List[Any] = []

        if creator_username:
            query += " AND LOWER(creator_username) = ?"
            params.append(creator_username.lower().lstrip("@"))

        if search:
            query += " AND (LOWER(company_name) LIKE ? OR LOWER(marketing_email) LIKE ? OR LOWER(industry) LIKE ? OR LOWER(pitch_hook) LIKE ?)"
            s = f"%{search.lower().strip()}%"
            params.extend([s, s, s, s])

        query += " ORDER BY id DESC LIMIT ?"
        params.append(limit)

        with self._get_connection() as conn:
            cursor = conn.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def get_creators(self) -> List[Dict]:
        """Returns a list of all distinct creators in the DB and their lead counts."""
        with self._get_connection() as conn:
            cursor = conn.execute("""
                SELECT creator_username, COUNT(*) as lead_count, MAX(scouted_at) as last_scouted
                FROM brand_leads
                GROUP BY creator_username
                ORDER BY lead_count DESC
            """)
            return [dict(row) for row in cursor.fetchall()]

    def get_stats(self) -> Dict[str, Any]:
        """Returns overall database statistics."""
        with self._get_connection() as conn:
            total_leads = conn.execute("SELECT COUNT(*) FROM brand_leads").fetchone()[0]
            unique_brands = conn.execute("SELECT COUNT(DISTINCT LOWER(company_name)) FROM brand_leads").fetchone()[0]
            total_creators = conn.execute("SELECT COUNT(DISTINCT LOWER(creator_username)) FROM brand_leads").fetchone()[0]
            with_mobile = conn.execute("SELECT COUNT(*) FROM brand_leads WHERE mobile_number IS NOT NULL AND mobile_number != 'N/A'").fetchone()[0]
            with_email = conn.execute("SELECT COUNT(*) FROM brand_leads WHERE marketing_email IS NOT NULL AND marketing_email != ''").fetchone()[0]

            return {
                "total_leads": total_leads,
                "unique_brands": unique_brands,
                "total_creators": total_creators,
                "leads_with_mobile": with_mobile,
                "leads_with_email": with_email,
            }


db_manager = DatabaseManager()

