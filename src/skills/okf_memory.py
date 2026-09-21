"""
OKF Memory Skill.
Connects agents to the Open Knowledge Framework store for reading intelligence
and writing newly discovered advertiser data and campaign learnings.
"""
import logging
from typing import Any, Dict, List, Optional, Set
from src.models.brand import BrandOpportunity
from src.storage.okf import okf_manager

logger = logging.getLogger(__name__)


class OKFMemorySkill:
    """
    Skill for accessing and updating Open Knowledge Framework intelligence.
    """

    name: str = "okf_memory"
    description: str = "Queries and persists brand intelligence, verified contacts, and market benchmarks in the Open Knowledge Framework."

    def __init__(self, manager=None):
        self.okf = manager or okf_manager

    def query(
        self,
        niche: Optional[str] = None,
        location: Optional[str] = None,
        exclude_names: Optional[Set[str]] = None,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        return self.okf.query_brands(niche=niche, location=location, exclude_names=exclude_names, limit=limit)

    def learn(self, brand: BrandOpportunity, creator_username: Optional[str] = None) -> bool:
        return self.okf.save_brand_intelligence(brand, creator_username)

    def get_market_benchmarks(self) -> Dict[str, Any]:
        return self.okf.get_benchmarks()

    def get_knowledge_summary(self) -> Dict[str, Any]:
        return self.okf.get_summary()


okf_memory_skill = OKFMemorySkill()
