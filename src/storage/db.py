"""
SQLite database manager for tracking and deduplicating brand leads across runs.
Ensures that every execution discovers fresh, unique brand opportunities and contacts.
"""
import sqlite3
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from contextlib import contextmanager

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

    @contextmanager
    def _get_connection(self):
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

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
                    source TEXT DEFAULT 'unverified',
                    is_test INTEGER DEFAULT 0,
                    flag_reason TEXT DEFAULT '',
                    linkedin_url TEXT DEFAULT '',
                    youtube_url TEXT DEFAULT '',
                    twitter_url TEXT DEFAULT '',
                    linktree_url TEXT DEFAULT '',
                    collab_form_url TEXT DEFAULT '',
                    meta_ad_library_url TEXT DEFAULT '',
                    email_tier TEXT DEFAULT 'Tier 2 (Marketing Desk)',
                    whatsapp_ready INTEGER DEFAULT 0,
                    UNIQUE(creator_username, company_name)
                );
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_creator_company 
                ON brand_leads(creator_username, company_name);
            """)
            # Safe schema upgrades for existing databases
            for col_name, col_type in [
                ("is_test", "INTEGER DEFAULT 0"),
                ("flag_reason", "TEXT DEFAULT ''"),
                ("linkedin_url", "TEXT DEFAULT ''"),
                ("youtube_url", "TEXT DEFAULT ''"),
                ("twitter_url", "TEXT DEFAULT ''"),
                ("linktree_url", "TEXT DEFAULT ''"),
                ("collab_form_url", "TEXT DEFAULT ''"),
                ("meta_ad_library_url", "TEXT DEFAULT ''"),
                ("email_tier", "TEXT DEFAULT 'Tier 2 (Marketing Desk)'"),
                ("whatsapp_ready", "INTEGER DEFAULT 0"),
            ]:
                try:
                    conn.execute(f"ALTER TABLE brand_leads ADD COLUMN {col_name} {col_type}")
                except sqlite3.OperationalError:
                    pass
            conn.commit()

    def reset_all(self):
        """Drops and recreates the brand_leads table."""
        with self._get_connection() as conn:
            conn.execute('DROP TABLE IF EXISTS brand_leads')
            conn.commit()
        self._init_db()

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
                            ad_probability, fit_score, collab_type, pitch_hook, scouted_at, source,
                            linkedin_url, youtube_url, twitter_url, linktree_url,
                            collab_form_url, meta_ad_library_url, email_tier, whatsapp_ready
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                        datetime.now(timezone.utc).isoformat(),
                        b.contact.source,
                        b.contact.linkedin_url or "",
                        b.contact.youtube_url or "",
                        b.contact.twitter_url or "",
                        b.contact.linktree_url or "",
                        b.contact.collab_form_url or "",
                        b.contact.meta_ad_library_url or "",
                        b.contact.email_tier or "Tier 2 (Marketing Desk)",
                        1 if b.contact.whatsapp_ready else 0,
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

    def delete_lead(self, lead_id: int) -> Optional[str]:
        """
        Permanently removes a lead by ID from SQLite.
        Returns the company_name of the deleted lead if found, else None.
        """
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT company_name FROM brand_leads WHERE id = ?", (lead_id,))
            row = cursor.fetchone()
            if not row:
                return None
            company_name = row["company_name"]
            conn.execute("DELETE FROM brand_leads WHERE id = ?", (lead_id,))
            conn.commit()
            return company_name

    def flag_lead(self, lead_id: int, reason: str = "", is_test: bool = True) -> bool:
        """
        Flags a lead as a test company, mock, or improper details.
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                "UPDATE brand_leads SET is_test = ?, flag_reason = ? WHERE id = ?",
                (1 if is_test else 0, reason, lead_id)
            )
            conn.commit()
            return cursor.rowcount > 0

    def unflag_lead(self, lead_id: int) -> bool:
        """Removes flag from a lead."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "UPDATE brand_leads SET is_test = 0, flag_reason = '' WHERE id = ?",
                (lead_id,)
            )
            conn.commit()
            return cursor.rowcount > 0

    def get_all_leads(
        self,
        creator_username: Optional[str] = None,
        search: Optional[str] = None,
        limit: int = 200,
        verified_only: bool = False,
        exclude_flagged: bool = False,
    ) -> List[Dict]:
        """
        Retrieves leads across all creators or filtered by creator/keyword without running agents.
        """
        query = "SELECT * FROM brand_leads WHERE 1=1"
        params: List[Any] = []

        if verified_only:
            query += " AND source = 'live_web_verified'"

        if exclude_flagged:
            query += " AND (is_test = 0 AND (flag_reason IS NULL OR flag_reason = ''))"

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
            
            flagged_leads = conn.execute("SELECT COUNT(*) FROM brand_leads WHERE is_test = 1 OR (flag_reason IS NOT NULL AND flag_reason != '')").fetchone()[0]
            genuine_leads = total_leads - flagged_leads

            # Group by industry for dashboard breakdown
            industry_rows = conn.execute("""
                SELECT COALESCE(NULLIF(TRIM(industry), ''), 'Lifestyle') as ind, COUNT(*) as cnt
                FROM brand_leads
                GROUP BY ind
                ORDER BY cnt DESC
                LIMIT 6
            """).fetchall()
            industries = {row["ind"]: row["cnt"] for row in industry_rows}

            return {
                "total_leads": total_leads,
                "unique_brands": unique_brands,
                "total_creators": total_creators,
                "leads_with_mobile": with_mobile,
                "leads_with_email": with_email,
                "verified_emails": with_email,
                "verified_phones": with_mobile,
                "flagged_leads": flagged_leads,
                "genuine_leads": genuine_leads,
                "industries": industries,
            }


db_manager = DatabaseManager()

