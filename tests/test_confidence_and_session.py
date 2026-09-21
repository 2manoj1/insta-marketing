"""
Tests for Chrome Instagram Session Importer, Multi-Signal Confidence Scoring,
and Instagram Brand Mobile Action Scraper Endpoints.
"""
import json
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from src.browser.session import InstagramSessionManager
from src.models.brand import BrandContact, BrandOpportunity
from src.search.confidence import calculate_lead_confidence
from src.server.app import app
from src.storage.db import DatabaseManager

client = TestClient(app)


def test_import_session_raw_string(tmp_path):
    sess_file = tmp_path / "test_session.json"
    mgr = InstagramSessionManager(session_path=str(sess_file))

    # Raw Instagram session ID (with embedded user ID 99887766)
    raw_token = "99887766%3Ajkhsdf876234:28%3AAYdfkjh23"
    res = mgr.import_session_token(raw_token)

    assert res["success"] is True
    assert res["has_sessionid"] is True
    assert sess_file.exists()

    with open(sess_file, "r", encoding="utf-8") as f:
        data = json.load(f)
        cookie_names = [c["name"] for c in data["cookies"]]
        assert "sessionid" in cookie_names
        assert "ds_user_id" in cookie_names
        # User id derived accurately from sessionid prefix
        user_id_cookie = next(c for c in data["cookies"] if c["name"] == "ds_user_id")
        assert user_id_cookie["value"] == "99887766"

    assert mgr.has_saved_session() is True


def test_import_session_cookie_header(tmp_path):
    sess_file = tmp_path / "test_session.json"
    mgr = InstagramSessionManager(session_path=str(sess_file))

    header = "sessionid=test_sess_123; csrftoken=csrftoken456; ds_user_id=12345"
    res = mgr.import_session_token(header)

    assert res["success"] is True
    assert res["cookies_count"] >= 3
    assert mgr.has_saved_session() is True


def test_import_session_json_array(tmp_path):
    sess_file = tmp_path / "test_session.json"
    mgr = InstagramSessionManager(session_path=str(sess_file))

    cookie_list = [
        {"name": "sessionid", "value": "abc123session", "domain": ".instagram.com"},
        {"name": "ds_user_id", "value": "11223344", "domain": ".instagram.com"},
        {"name": "csrftoken", "value": "tok_xyz", "domain": ".instagram.com"},
    ]
    res = mgr.import_session_token(cookie_list)

    assert res["success"] is True
    assert res["has_sessionid"] is True
    assert mgr.has_saved_session() is True


def test_confidence_scoring_weights():
    # 1. Direct Instagram Business Button contact -> must score >= 90%
    contact_ig_button = BrandContact(
        contact_email="partnerships@brand.com",
        mobile_number="+91 98765 43210",
        whatsapp_ready=True,
        source="instagram_business_button",
        email_tier="Tier 1 (Direct PR / Collab)",
        meta_ad_library_url="https://www.facebook.com/ads/library/?q=brand",
        website="https://brand.com",
    )
    score_ig = calculate_lead_confidence(contact_ig_button)
    assert score_ig >= 90, f"Expected >= 90, got {score_ig}"

    # 2. Tier 1 Email + WhatsApp + Meta Ads from website crawl
    contact_tier1 = BrandContact(
        contact_email="pr@brand.com",
        mobile_number="+91 98765 43210",
        whatsapp_ready=True,
        source="live_web_verified",
        email_tier="Tier 1 (Direct PR / Collab)",
        meta_ad_library_url="https://www.facebook.com/ads/library/?q=brand",
        website="https://brand.com",
    )
    score_t1 = calculate_lead_confidence(contact_tier1)
    assert score_t1 >= 80, f"Expected >= 80, got {score_t1}"

    # 3. Tier 2 Support/Corporate email only -> lower confidence
    contact_t3 = BrandContact(
        contact_email="info@brand.com",
        source="dynamic_ai_discovery",
        email_tier="Tier 3 (Corporate / Support)",
        website="https://brand.com",
    )
    score_t3 = calculate_lead_confidence(contact_t3)
    assert score_t3 < score_t1
    assert score_t3 >= 50


def test_api_session_import_endpoint():
    resp = client.post("/api/session/import", json={
        "session_token": "55443322%3Asecret_token:99"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["details"]["has_sessionid"] is True

    # Verify status endpoint reflects active session
    st_resp = client.get("/api/status")
    assert st_resp.status_code == 200
    assert st_resp.json()["instagram_authenticated"] is True


def test_sqlite_confidence_score_persistence(tmp_path):
    db = DatabaseManager(db_path=tmp_path / "test_conf.db")
    contact = BrandContact(
        contact_email="collabs@brand.com",
        mobile_number="+91 99999 88888",
        instagram_handle="@brand",
        website="https://brand.com",
        confidence_score=95,
        source="instagram_business_button",
    )
    opp = BrandOpportunity(
        brand_name="Super Brand",
        website="https://brand.com",
        industry="DTC",
        fit_score=92,
        contact=contact,
    )
    db.save_leads("test_creator", [opp])

    leads = db.get_all_leads(creator_username="test_creator")
    assert len(leads) == 1
    assert leads[0]["confidence_score"] == 95

    # Update lead contact
    lead_id = leads[0]["id"]
    updated = db.update_lead_contact(
        lead_id=lead_id,
        email="new_pr@brand.com",
        phone="+91 91111 22222",
        confidence_score=98,
        source="instagram_business_button"
    )
    assert updated is True

    leads_after = db.get_all_leads(creator_username="test_creator")
    assert leads_after[0]["marketing_email"] == "new_pr@brand.com"
    assert leads_after[0]["confidence_score"] == 98
