"""
Unit tests for the Deep Multi-Agent System (Scout, Strategist, Director).
"""
import pytest
from src.agents.deep.director import DeepDirectorOrchestrator
from src.agents.deep.scout import DeepBrandScoutAgent
from src.agents.deep.strategist import DeepPitchStrategistAgent
from src.browser.scraper import CreatorScraper
from src.models.brand import BrandContact, BrandOpportunity
from src.models.creator import CreatorProfile
from src.storage.db import DatabaseManager
from src.storage.okf import OKFManager


@pytest.mark.anyio
async def test_deep_brand_scout_agent(tmp_path):
    db = DatabaseManager(db_path=tmp_path / "test_leads.db")
    okf = OKFManager(okf_dir=tmp_path / "okf")

    agent = DeepBrandScoutAgent(db=db, okf=okf)
    profile = CreatorScraper.create_sample_profile("iva_mana5")

    brands = await agent.scout_and_enrich(
        profile=profile,
        location="Bangalore / India",
        interests=["Luxury Hospitality"],
        limit=3,
    )

    assert len(brands) == 3
    assert all(b.contact.contact_email for b in brands)
    # Check that leads were committed to DB and OKF
    assert db.count_leads("iva_mana5") == 3
    assert okf.get_summary()["total_brands_in_okf"] >= 3


def test_deep_pitch_strategist_agent():
    agent = DeepPitchStrategistAgent()
    profile = CreatorScraper.create_sample_profile("iva_mana5")
    opps = [
        BrandOpportunity(
            brand_name="The Tamara Resorts",
            website="https://thetamara.com",
            industry="Luxury Eco-Resorts",
            suggested_angle="Luxury staycation video hook",
            contact=BrandContact(
                contact_email="marketing@thetamara.com",
                mobile_number="+91 95919 96919",
            ),
        )
    ]

    pitches = agent.craft_pitches(profile, opps)
    assert len(pitches) == 1
    p = pitches[0]
    assert p.brand_name == "The Tamara Resorts"
    assert "The Tamara Resorts" in p.subject_line
    assert "iva_mana5" in p.instagram_dm
    assert p.email_body != ""


@pytest.mark.anyio
async def test_deep_director_workflow_orchestration(tmp_path):
    db = DatabaseManager(db_path=tmp_path / "test_leads.db")
    okf = OKFManager(okf_dir=tmp_path / "okf")
    scout = DeepBrandScoutAgent(db=db, okf=okf)
    director = DeepDirectorOrchestrator(scout_agent=scout)

    logs = []
    res = await director.execute_workflow(
        username="iva_mana5",
        location="Bangalore / India",
        limit=2,
        log_callback=lambda m: logs.append(m),
    )

    assert "creator_profile" in res
    assert "rate_card" in res
    assert len(res["brands"]) == 2
    assert len(res["pitches"]) == 2
    assert len(logs) > 0
