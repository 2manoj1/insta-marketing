"""
Unit tests for the Deep Multi-Agent System (Scout, Strategist, Director).
Tests use mocked brand finder results since live discovery requires network + LLM.
"""
import pytest
from unittest.mock import AsyncMock, patch
from src.agents.deep.director import DeepDirectorOrchestrator
from src.agents.deep.scout import DeepBrandScoutAgent
from src.agents.deep.strategist import DeepPitchStrategistAgent
from src.browser.scraper import CreatorScraper
from src.models.brand import BrandContact, BrandOpportunity
from src.models.creator import CreatorProfile
from src.storage.db import DatabaseManager
from src.storage.okf import OKFManager


def _make_test_brands(n: int = 3) -> list[BrandOpportunity]:
    """Creates test brand opportunities with verified source for testing."""
    brands = []
    for i in range(n):
        brands.append(BrandOpportunity(
            brand_name=f"TestBrand_{i}",
            website=f"https://testbrand{i}.com",
            industry="Test Industry",
            location="India",
            fit_score=90,
            suggested_angle=f"Test angle for brand {i}",
            contact=BrandContact(
                contact_email=f"collab@testbrand{i}.com",
                mobile_number=f"+91 98765 4321{i}",
                phone_number=f"+91 98765 4321{i}",
                instagram_handle=f"@testbrand{i}",
                website=f"https://testbrand{i}.com",
                source="live_web_verified",
            ),
        ))
    return brands


@pytest.mark.anyio
async def test_deep_brand_scout_agent(tmp_path):
    """Tests scout agent with mocked brand discovery (no network needed)."""
    db = DatabaseManager(db_path=tmp_path / "test_leads.db")
    okf = OKFManager(okf_dir=tmp_path / "okf")
    agent = DeepBrandScoutAgent(db=db, okf=okf)
    profile = CreatorScraper.create_sample_profile("iva_mana5")

    mock_brands = _make_test_brands(3)
    with patch.object(agent.finder, "search_brands", new_callable=AsyncMock, return_value=mock_brands):
        brands = await agent.scout_and_enrich(
            profile=profile,
            location="Bangalore / India",
            interests=["Luxury Hospitality"],
            limit=3,
        )

    assert len(brands) == 3
    assert all(b.contact.contact_email for b in brands)
    # Verified brands should be committed to DB and OKF
    assert db.count_leads("iva_mana5") == 3


def test_deep_pitch_strategist_agent():
    agent = DeepPitchStrategistAgent()
    profile = CreatorScraper.create_sample_profile("iva_mana5")
    opps = _make_test_brands(1)
    opps[0].brand_name = "The Tamara Resorts"
    opps[0].suggested_angle = "Luxury staycation video hook"

    pitches = agent.craft_pitches(profile, opps)
    assert len(pitches) == 1
    p = pitches[0]
    assert p.brand_name == "The Tamara Resorts"
    assert "The Tamara Resorts" in p.subject_line
    assert "iva_mana5" in p.instagram_dm
    assert p.email_body != ""


@pytest.mark.anyio
async def test_deep_director_workflow_orchestration(tmp_path):
    """Tests director orchestration with mocked scout results."""
    db = DatabaseManager(db_path=tmp_path / "test_leads.db")
    okf = OKFManager(okf_dir=tmp_path / "okf")
    scout = DeepBrandScoutAgent(db=db, okf=okf)

    mock_brands = _make_test_brands(2)
    with patch.object(scout.finder, "search_brands", new_callable=AsyncMock, return_value=mock_brands):
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
