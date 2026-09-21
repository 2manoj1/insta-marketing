"""
Modular Agent Skills Framework for Instagram Influencer Marketing.
Provides reusable, free and open-source tool capabilities for deep agents.
"""
from src.skills.stealth_scraper import StealthScraperSkill, stealth_scraper_skill
from src.skills.deep_bio_link import DeepBioLinkSkill, deep_bio_link_skill
from src.skills.contact_verifier import ContactVerifierSkill, contact_verifier_skill
from src.skills.negotiation_pricing import NegotiationPricingSkill, negotiation_pricing_skill
from src.skills.pitch_sequencing import PitchSequencingSkill, pitch_sequencing_skill
from src.skills.okf_memory import OKFMemorySkill, okf_memory_skill
from src.skills.web_search import FreeWebSearchSkill, free_web_search_skill

__all__ = [
    "StealthScraperSkill",
    "stealth_scraper_skill",
    "DeepBioLinkSkill",
    "deep_bio_link_skill",
    "ContactVerifierSkill",
    "contact_verifier_skill",
    "NegotiationPricingSkill",
    "negotiation_pricing_skill",
    "PitchSequencingSkill",
    "pitch_sequencing_skill",
    "OKFMemorySkill",
    "okf_memory_skill",
    "FreeWebSearchSkill",
    "free_web_search_skill",
]
