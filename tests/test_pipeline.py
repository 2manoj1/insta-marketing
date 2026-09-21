"""
Tests for Instagram Influencer Marketing Manager system.
"""
import asyncio
import json
import uuid
from pathlib import Path
import pytest

from src.agents.brand_scout_agent import BrandScoutAgent
from src.agents.draft_manager import DraftManager, draft_manager
from src.agents.lead_finder_agent import LeadFinderAgent, lead_finder_agent
from src.agents.pitch_drafter_agent import PitchDrafterAgent
from src.agents.profiler_agent import ProfilerAgent
from src.agents.workflow_graph import MarketingWorkflowGraph
from src.browser.scraper import CreatorScraper, parse_count, extract_email_from_text
from src.browser.session import InstagramSessionManager
from src.models.brand import BrandOpportunity, BrandContact
from src.models.creator import CreatorProfile, UGCReadiness
from src.models.outreach import OutreachPitch
from src.search.brand_finder import BrandFinder


def test_count_parsing():
    assert parse_count("125K") == 125_000
    assert parse_count("1.2M") == 1_200_000
    assert parse_count("450") == 450
    assert parse_count("10,400") == 10_400
    assert parse_count("") == 0


def test_email_extraction():
    text = "Fitness enthusiast. Contact: collab@creator.io or DM for partnerships"
    assert extract_email_from_text(text) == "collab@creator.io"
    assert extract_email_from_text("No email here") is None


def test_sample_creator_profile():
    profile = CreatorScraper.create_sample_profile("test_creator")
    assert profile.username == "test_creator"
    assert profile.followers_count == 48500
    assert len(profile.recent_posts) > 0
    assert profile.contact_email is not None


def test_brand_finder_matching():
    from unittest.mock import AsyncMock, patch
    from src.models.brand import BrandContact

    mock_brands = [
        BrandOpportunity(
            brand_name=f"TestBrand_{i}",
            website=f"https://testbrand{i}.com",
            industry="Tech",
            location="India",
            fit_score=90,
            suggested_angle=f"Test angle {i}",
            contact=BrandContact(
                contact_email=f"collab@testbrand{i}.com",
                mobile_number=f"+91 98765 4321{i}",
                source="live_web_verified",
            ),
        ) for i in range(3)
    ]

    async def _test():
        finder = BrandFinder()
        with patch.object(finder, "search_brands", new_callable=AsyncMock, return_value=mock_brands):
            brands = await finder.search_brands(
                niche_tags=["Tech", "Keyboard", "Desk Setup"],
                location="India / Bangalore",
                limit=3,
            )
            assert len(brands) == 3
            assert brands[0].brand_name != ""
            assert brands[0].contact.contact_email is not None
            assert "@" in brands[0].contact.contact_email

    asyncio.run(_test())


def test_profiler_agent_fallback():
    profiler = ProfilerAgent()
    profile = CreatorScraper.create_sample_profile("alex_test")
    ugc = profiler._fallback_profile(profile)
    assert "Micro-influencer" in ugc.tier
    assert "$200" in ugc.estimated_rate_per_ugc_video_usd
    assert len(ugc.ugc_strengths) > 0


def test_pitch_drafter_output(monkeypatch):
    drafter = PitchDrafterAgent()
    monkeypatch.setattr(drafter.llm, "generate_json", lambda *a, **kw: None)
    profile = CreatorScraper.create_sample_profile("alex_test")
    brand = BrandOpportunity(
        brand_name="Keychron",
        website="https://www.keychron.com",
        industry="Mechanical Keyboards",
        location="Global",
        fit_score=95,
        value_proposition="High audience overlap with desk setup enthusiasts",
        contact=BrandContact(contact_email="influencer@keychron.com"),
        suggested_angle="Typing sound test and productivity breakdown",
    )
    pitches = drafter.draft_pitches(profile, [brand])
    assert len(pitches) == 1
    p = pitches[0]
    assert p.brand_name == "Keychron"
    assert p.recipient_email == "influencer@keychron.com"
    assert "alex_test" in p.email_body
    assert len(p.instagram_dm) > 0
    assert len(p.deliverables) > 0


def test_lead_finder_saves_json(tmp_path):
    finder = LeadFinderAgent()
    brand = BrandOpportunity(
        brand_name="The Tamara Resorts",
        website="https://www.thetamara.com",
        industry="Luxury Hospitality",
        location="Bangalore",
        fit_score=98,
        contact=BrandContact(
            contact_email="marketing@thetamara.com",
            mobile_number="+91 95919 96919",
            instagram_handle="@thetamararesorts"
        ),
    )
    out_file = finder.save_leads_json("test_isolated_json_creator", [brand])
    assert out_file.exists()

    with open(out_file, "r") as f:
        data = json.load(f)
    assert len(data) >= 1
    assert data[0]["company_name"] == "The Tamara Resorts"
    assert data[0]["marketing_email"] == "marketing@thetamara.com"
    assert data[0]["mobile_number"] == "+91 95919 96919"


def test_draft_manager_saves_individual_files():
    mgr = DraftManager()
    pitch = OutreachPitch(
        brand_name="Snitch",
        recipient_email="collab@snitch.co.in",
        creator_username="iva_test",
        subject_line="Collab Proposal: Snitch x @iva_test",
        email_body="Hi Snitch team, let's collaborate on fashion UGC.",
        instagram_dm="Hey Snitch team!",
    )
    draft_dir = mgr.save_individual_drafts("iva_test", [pitch])
    assert draft_dir.exists()
    draft_file = draft_dir / "Snitch_pitch.txt"
    assert draft_file.exists()
    content = draft_file.read_text()
    assert "collab@snitch.co.in" in content
    assert "Collab Proposal: Snitch x @iva_test" in content


def test_hitl_interactive_review_actions(monkeypatch):
    mgr = DraftManager()
    pitches = [
        OutreachPitch(
            brand_name="Brand A",
            recipient_email="a@example.com",
            creator_username="test_user",
            subject_line="Subject A",
            email_body="Body A",
            instagram_dm="DM A",
        ),
        OutreachPitch(
            brand_name="Brand B",
            recipient_email="b@example.com",
            creator_username="test_user",
            subject_line="Subject B",
            email_body="Body B",
            instagram_dm="DM B",
        ),
    ]

    # 1. Test auto_approve
    res = mgr.hitl_interactive_review(pitches, auto_approve=True)
    assert len(res) == 2
    assert all(p.status == "approved" for p in res)

    # 2. Test Skip / Approve All via input simulation
    from rich.prompt import Prompt
    monkeypatch.setattr(Prompt, "ask", lambda *a, **kw: "A")
    res2 = mgr.hitl_interactive_review(pitches)
    assert len(res2) == 2

    # 3. Test Reject Action
    inputs = iter(["R", "1", "A"])  # Reject draft 1 ("Brand A"), then Approve remaining
    monkeypatch.setattr(Prompt, "ask", lambda *a, **kw: next(inputs))
    res3 = mgr.hitl_interactive_review(pitches)
    assert len(res3) == 1
    assert res3[0].brand_name == "Brand B"


def test_marketing_workflow_graph_end_to_end(monkeypatch):
    async def _test():
        graph = MarketingWorkflowGraph()

        # Mock LLM calls directly on the agent instances
        fake_ugc = {
            "tier": "Micro-influencer (10K-50K)",
            "ugc_strengths": ["Authentic storytelling", "High quality camera work"],
            "content_pillars": ["Tech", "Desk Setups"],
            "estimated_rate_per_ugc_video_usd": "$250 - $450",
            "estimated_rate_per_sponsored_reel_usd": "$400 - $800",
            "suggested_ad_formats": ["Problem-Solution"],
        }
        monkeypatch.setattr(graph.profiler.llm, "generate_json", lambda *a, **kw: fake_ugc)
        monkeypatch.setattr(graph.scout.llm, "generate_json", lambda *a, **kw: {
            "value_proposition": "Great audience alignment",
            "suggested_angle": "Productivity transformation",
            "collab_type": "UGC Ad",
        })
        from unittest.mock import AsyncMock
        mock_brand_opp = BrandOpportunity(
            brand_name=f"Fresh Brand {uuid.uuid4().hex[:4]}",
            website="https://freshbrand.com",
            industry="Tech Accessories",
            location="India / Bangalore",
            contact=BrandContact(
                contact_email="collab@freshbrand.com",
                mobile_number="+91 98888 77777",
                source="live_web_verified",
            ),
        )
        monkeypatch.setattr(graph.lead_finder.finder, "search_brands", AsyncMock(return_value=[mock_brand_opp]))
        monkeypatch.setattr(graph.drafter.llm, "generate_json", lambda *a, **kw: {
            "subject_line": "Collab with @alex_tech_creator",
            "email_body": "Hi team, let's collab.",
            "instagram_dm": "Hey team!",
            "deliverables": [{"title": "1x UGC Video", "description": "High quality video", "usage_rights": "30 days"}],
            "call_to_action": "Can we talk?",
        })
        unique_handle = f"pilot_{uuid.uuid4().hex[:6]}"
        state = await graph.execute(
            handle_or_url=unique_handle,
            location="India / Bangalore",
            interests=["Desk Setup", "Tech Gadgets"],
            use_sample_data=True,
            enable_hitl=False,
        )
        assert state.profile is not None
        assert state.profile.ugc_profile is not None
        assert len(state.brands) > 0
        assert len(state.pitches) > 0
        assert state.summary is not None
        assert state.summary.total_brands_discovered == len(state.brands)
        assert state.leads_file is not None and state.leads_file.exists()
        assert state.drafts_dir is not None and state.drafts_dir.exists()

    asyncio.run(_test())


def test_server_db_endpoints_without_running_agents():
    """
    Verifies that the FastAPI server can serve leads, drafts, stats, and creators
    directly from the database and disk without invoking any agent workflow.
    """
    from fastapi.testclient import TestClient
    from src.server.app import app

    client = TestClient(app)

    # 1. Test /api/stats
    stats_resp = client.get("/api/stats")
    assert stats_resp.status_code == 200
    stats = stats_resp.json()
    assert "total_leads" in stats
    assert "unique_brands" in stats
    assert "leads_with_email" in stats

    # 2. Test /api/leads
    leads_resp = client.get("/api/leads?limit=10")
    assert leads_resp.status_code == 200
    leads_data = leads_resp.json()
    assert "count" in leads_data
    assert "leads" in leads_data
    assert isinstance(leads_data["leads"], list)

    # 3. Test /api/creators
    creators_resp = client.get("/api/creators")
    assert creators_resp.status_code == 200
    creators_data = creators_resp.json()
    assert isinstance(creators_data, list)

    # 4. Test /api/drafts
    drafts_resp = client.get("/api/drafts")
    assert drafts_resp.status_code == 200
    drafts_data = drafts_resp.json()
    assert "count" in drafts_data
    assert "drafts" in drafts_data

    # 5. Test web UI root serving HTML
    html_resp = client.get("/")
    assert html_resp.status_code == 200
    assert "InstaMarketing" in html_resp.text
    assert "Verified Brand Directory" in html_resp.text


def test_server_run_and_stop_job_flow(monkeypatch):
    """
    Verifies that a user can start a workflow job via API, poll its status,
    and stop/cancel the flow immediately via the stop endpoint.
    """
    import asyncio
    from fastapi.testclient import TestClient
    from src.server.app import app
    from src.agents.workflow_graph import marketing_graph

    async def mock_execute(*args, **kwargs):
        # Simulate long-running agent flow
        await asyncio.sleep(10)
        return None

    monkeypatch.setattr(marketing_graph, "execute", mock_execute)

    client = TestClient(app)

    # 1. Start a workflow job
    run_resp = client.post("/api/run", json={
        "handle_or_url": "test_creator",
        "location": "Global",
        "use_sample": True,
    })
    assert run_resp.status_code == 200
    data = run_resp.json()
    assert "job_id" in data
    job_id = data["job_id"]
    assert data["status"] == "running"

    # 2. Poll job status
    status_resp = client.get(f"/api/job/{job_id}")
    assert status_resp.status_code == 200
    status_data = status_resp.json()
    assert status_data["job_id"] == job_id
    assert status_data["status"] in ["running", "completed", "stopped"]

    # 3. Stop/Cancel the flow
    stop_resp = client.post(f"/api/stop/{job_id}")
    assert stop_resp.status_code == 200
    stop_data = stop_resp.json()
    assert stop_data["status"] == "stopped"

    # 4. Verify job is marked as stopped
    check_resp = client.get(f"/api/job/{job_id}")
    assert check_resp.status_code == 200
    assert check_resp.json()["status"] == "stopped"


def test_brand_authenticity_filter():
    """
    Verifies that brand_finder._is_authentic_brand accurately rejects
    SEO listicles, aggregators, test placeholders, and bad domains.
    """
    from src.search.brand_finder import brand_finder

    # Authentic brands must pass
    assert brand_finder._is_authentic_brand("Nykaa", domain="nykaa.com") is True
    assert brand_finder._is_authentic_brand("Snitch", domain="snitch.co.in") is True
    assert brand_finder._is_authentic_brand("boAt Lifestyle", domain="boat-lifestyle.com") is True
    assert brand_finder._is_authentic_brand("Keychron", domain="keychron.com") is True

    # SEO listicles & aggregators must be rejected
    assert brand_finder._is_authentic_brand("19 Bangalore Based Jewelry Companies", domain="beststartup.asia") is False
    assert brand_finder._is_authentic_brand("Top 10 D2C Brands in India", domain="topcompanies.in") is False
    assert brand_finder._is_authentic_brand("Best 25 Sustainable Brands", domain="clutch.co") is False
    assert brand_finder._is_authentic_brand("Directory of Bangalore Companies", domain="justdial.com") is False

    # Test & mock placeholders must be rejected
    assert brand_finder._is_authentic_brand("Luxury eco-resorts & hospitality Direct 1", domain="direct1.com") is False
    assert brand_finder._is_authentic_brand("Direct 2", domain="example.com") is False
    assert brand_finder._is_authentic_brand("Test Company", domain="testbrand.com") is False
    assert brand_finder._is_authentic_brand("Sample Brand", domain="sample.com") is False

    # Aggregator domains must be rejected
    assert brand_finder._is_authentic_brand("Some Company", domain="clutch.co") is False
    assert brand_finder._is_authentic_brand("Tech Corp", domain="goodfirms.co") is False
    assert brand_finder._is_authentic_brand("Startups", domain="beststartup.asia") is False


def test_lead_flagging_and_deletion_api():
    """
    Verifies 1-click delete, flagging, and exclude_flagged filters via API.
    """
    from fastapi.testclient import TestClient
    from src.server.app import app
    from src.storage.db import db_manager
    from src.storage.okf import okf_manager
    from src.models.brand import BrandOpportunity, BrandContact

    client = TestClient(app)

    # Insert a test lead directly
    test_brand = BrandOpportunity(
        brand_name="Test Deletable Brand",
        website="https://testdeletable.com",
        industry="Tech",
        location="India",
        fit_score=90,
        contact=BrandContact(
            contact_email="partnerships@testdeletable.com",
            mobile_number="+91 99999 88888",
            source="live_web_verified",
        )
    )
    db_manager.save_leads("test_creator_flag", [test_brand])
    okf_manager.save_brand_intelligence(test_brand, creator_username="test_creator_flag")

    # Verify lead exists in db
    leads = db_manager.get_all_leads(creator_username="test_creator_flag")
    assert len(leads) >= 1
    lead_id = leads[0]["id"]

    # 1. Flag lead with improper details
    flag_resp = client.post(f"/api/leads/{lead_id}/flag", json={
        "is_test": False,
        "reason": "Improper Scraper Details"
    })
    assert flag_resp.status_code == 200
    flag_data = flag_resp.json()
    assert flag_data["status"] == "flagged"

    # Verify exclude_flagged hides it
    filtered_resp = client.get("/api/leads?creator=test_creator_flag&exclude_flagged=true")
    assert filtered_resp.status_code == 200
    assert len(filtered_resp.json()["leads"]) == 0

    all_resp = client.get("/api/leads?creator=test_creator_flag&exclude_flagged=false")
    assert all_resp.status_code == 200
    assert len(all_resp.json()["leads"]) >= 1

    # 2. Unflag lead
    unflag_resp = client.post(f"/api/leads/{lead_id}/unflag")
    assert unflag_resp.status_code == 200
    assert unflag_resp.json()["status"] == "unflagged"

    # 3. Delete lead permanently (1-click delete)
    del_resp = client.delete(f"/api/leads/{lead_id}")
    assert del_resp.status_code == 200
    assert del_resp.json()["status"] == "deleted"

    # Verify lead is gone from SQLite
    leads_after = db_manager.get_all_leads(creator_username="test_creator_flag")
    assert not any(l["id"] == lead_id for l in leads_after)

    # Verify brand is gone from OKF
    okf_brands = okf_manager.load_brands()
    assert not any(b.get("brand_name") == "Test Deletable Brand" for b in okf_brands)



