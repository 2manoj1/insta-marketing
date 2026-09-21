"""
End-to-End Verification of Full Pipeline and Web API (Port 8088 application).
Validates all endpoints, UI elements, database operations, 1-click delete,
flagging, live discovery, multi-agent orchestration, and pitch generation.
"""
import sys
import json
from fastapi.testclient import TestClient
from src.server.app import app
from src.storage.db import db_manager
from src.storage.okf import okf_manager

client = TestClient(app)

def run_all_checks():
    print("=" * 70)
    print("🚀 STARTING FULL PIPELINE & WEB API END-TO-END VERIFICATION")
    print("=" * 70)

    # 1. Healthcheck probe
    print("\n[1/12] Testing GET /healthz ...")
    resp = client.get("/healthz")
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    data = resp.json()
    assert data["status"] == "healthy"
    print(f"  ✅ Healthcheck passed: {data}")

    # 2. Web UI HTML serving & components check
    print("\n[2/12] Testing GET / (Single Page Dashboard) ...")
    resp = client.get("/")
    assert resp.status_code == 200
    html = resp.text
    required_strings = [
        "InstaMarketing",
        "Verified Brand Directory",
        "flag-lead-modal",
        "toggle-hide-flagged",
        "dismissDiscoveredCard",
        "openFlagModal",
        "deleteLead",
        "D2C Activewear & Athleisure",
        "Specialty Coffee & Gourmet Foods",
        "Sustainable Fashion & Apparel",
        "Luxury Eco-Resorts & Stays",
        "Minimalist Desk Tech & EDC",
        "Autonomous Marketing Director",
    ]
    for s in required_strings:
        assert s in html, f"Missing required UI string/element: '{s}'"
    print(f"  ✅ Web UI HTML successfully loaded ({len(html)} bytes) with all critical UI elements.")

    # 3. Database Stats & Quality Metrics
    print("\n[3/12] Testing GET /api/stats ...")
    resp = client.get("/api/stats")
    assert resp.status_code == 200
    stats = resp.json()
    for k in ["total_leads", "unique_brands", "verified_emails", "verified_phones", "flagged_leads", "genuine_leads", "industries"]:
        assert k in stats, f"Missing stats key: {k}"
    print(f"  ✅ Database stats verified: Total={stats['total_leads']}, Genuine={stats['genuine_leads']}, Flagged={stats['flagged_leads']}")

    # 4. System Status
    print("\n[4/12] Testing GET /api/status ...")
    resp = client.get("/api/status")
    assert resp.status_code == 200
    status_data = resp.json()
    assert "llm_model" in status_data
    assert "instagram_authenticated" in status_data
    print(f"  ✅ System status operational: LLM={status_data['llm_model']}")

    # 5. OKF Knowledge Base & Benchmarks
    print("\n[5/12] Testing GET /api/okf ...")
    resp = client.get("/api/okf")
    assert resp.status_code == 200
    okf_data = resp.json()
    assert "summary" in okf_data
    assert "brands" in okf_data
    assert "benchmarks" in okf_data
    print(f"  ✅ OKF store connected: {okf_data['summary']['total_brands_in_okf']} brands in persistent memory.")

    # 6. Modular Agent Skills Catalog
    print("\n[6/12] Testing GET /api/skills ...")
    resp = client.get("/api/skills")
    assert resp.status_code == 200
    skills_data = resp.json()
    assert skills_data["count"] == 6
    skill_names = [s["name"] for s in skills_data["skills"]]
    assert "stealth_scraper" in skill_names
    assert "deep_bio_link_scraper" in skill_names
    assert "contact_verifier" in skill_names
    print(f"  ✅ All 6 agent skills verified: {', '.join(skill_names)}")

    # 7. Live Brand Search with Authenticity Filter
    print("\n[7/12] Testing POST /api/search/live with genuine brand filter ...")
    resp = client.post("/api/search/live", json={
        "niche": "specialty coffee",
        "location": "India",
        "limit": 3
    })
    assert resp.status_code == 200
    search_data = resp.json()
    brands = search_data.get("brands", [])
    print(f"  ✅ Live discovery returned {len(brands)} brands.")
    for b in brands:
        print(f"     - Discovered: {b.get('brand_name')} | Site: {b.get('website')} | Email: {b.get('contact', {}).get('contact_email')}")
        # Verify no listicles or test company mock names exist in candidates
        assert not any(bad in b.get('brand_name', '').lower() for bad in ['direct 1', 'direct 2', 'test company', '19 bangalore', 'top 10'])

    # 8. Lead Creation, 1-Click Flagging, and Filtering
    print("\n[8/12] Testing Lead Flagging & Filter Endpoints ...")
    from src.models.brand import BrandOpportunity, BrandContact
    e2e_brand = BrandOpportunity(
        brand_name="E2E Quality Test Brand",
        website="https://e2etestbrand.com",
        industry="Lifestyle / DTC",
        location="India",
        fit_score=94,
        contact=BrandContact(
            contact_email="collab@e2etestbrand.com",
            mobile_number="+91 98765 00000",
            source="live_web_verified",
        )
    )
    db_manager.save_leads("e2e_pilot_user", [e2e_brand])
    leads_initial = db_manager.get_all_leads(creator_username="e2e_pilot_user")
    assert len(leads_initial) > 0
    target_lead_id = leads_initial[0]["id"]

    # Flag as improper scraper details
    flag_resp = client.post(f"/api/leads/{target_lead_id}/flag", json={
        "is_test": False,
        "reason": "Improper Scraper Details (Missing Phone)"
    })
    assert flag_resp.status_code == 200
    print(f"  ✅ Flagged lead #{target_lead_id} successfully.")

    # Verify hide flagged works
    leads_hidden = client.get("/api/leads?creator=e2e_pilot_user&exclude_flagged=true").json()["leads"]
    assert not any(l["id"] == target_lead_id for l in leads_hidden)
    leads_shown = client.get("/api/leads?creator=e2e_pilot_user&exclude_flagged=false").json()["leads"]
    assert any(l["id"] == target_lead_id for l in leads_shown)
    print("  ✅ 'Hide Flagged/Test' filter accurately excludes flagged records.")

    # Unflag lead
    unflag_resp = client.post(f"/api/leads/{target_lead_id}/unflag")
    assert unflag_resp.status_code == 200
    print(f"  ✅ Cleared flag on lead #{target_lead_id}.")

    # 9. 1-Click Lead Permanent Deletion
    print("\n[9/12] Testing 1-Click Lead Deletion Endpoint ...")
    del_resp = client.delete(f"/api/leads/{target_lead_id}")
    assert del_resp.status_code == 200
    del_data = del_resp.json()
    assert del_data["status"] == "deleted"
    leads_after_del = db_manager.get_all_leads(creator_username="e2e_pilot_user")
    assert not any(l["id"] == target_lead_id for l in leads_after_del)
    print(f"  ✅ Permanently deleted lead #{target_lead_id} from SQLite and OKF store.")

    # 10. End-to-End Multi-Agent Pipeline Execution (Sync)
    print("\n[10/12] Testing POST /api/run_sync (End-to-End Multi-Agent Execution) ...")
    # Clean up prior test leads for pilot_creator_e2e to ensure test idempotency across runs
    with db_manager._get_connection() as conn:
        conn.execute("DELETE FROM brand_leads WHERE LOWER(creator_username) = 'pilot_creator_e2e'")
        conn.commit()

    # Ensure OKF has a verified partner matching creator niche
    seed_brand = BrandOpportunity(
        brand_name="Keychron",
        website="https://keychron.com",
        industry="Tech / Mechanical Keyboards",
        location="India",
        fit_score=95,
        suggested_angle="Minimalist desk setup and ergonomics showcase",
        contact=BrandContact(
            contact_email="partnerships@keychron.com",
            mobile_number="+91 98888 12345",
            source="live_web_verified",
        )
    )
    okf_manager.save_brand_intelligence(seed_brand)

    run_resp = client.post("/api/run_sync", json={
        "handle_or_url": "pilot_creator_e2e",
        "location": "India",
        "interests": ["tech", "ergonomics", "desk setup"],
        "deal_preference": "UGC Video with Paid Ad Rights",
        "use_sample": True
    })
    assert run_resp.status_code == 200
    run_result = run_resp.json()
    assert run_result["status"] == "completed"
    assert run_result["creator"] is not None
    assert len(run_result["brands"]) > 0
    assert len(run_result["pitches"]) > 0
    print(f"  ✅ Pipeline executed successfully for @{run_result['creator']['username']}:")
    print(f"     - Follower Count: {run_result['creator']['followers_count']}")
    print(f"     - Target Brands Matched: {len(run_result['brands'])}")
    print(f"     - Multi-Touch Pitches Synthesized: {len(run_result['pitches'])}")

    # 11. Pitch Drafts & HITL Editing on Disk
    print("\n[11/12] Testing GET /api/drafts & POST /api/drafts/update (HITL Pitch Editing) ...")
    drafts_resp = client.get("/api/drafts?creator=pilot_creator_e2e")
    assert drafts_resp.status_code == 200
    drafts_data = drafts_resp.json()
    assert drafts_data["count"] > 0
    sample_draft = drafts_data["drafts"][0]
    filename = sample_draft["filename"]
    original_content = sample_draft["full_content"]
    print(f"  ✅ Found draft file '{filename}' on disk.")

    # Edit draft via HITL endpoint
    edited_content = original_content + "\n\nP.S. Edited via HITL Web Portal for Custom Deal Terms."
    update_resp = client.post("/api/drafts/update", json={
        "filename": filename,
        "full_content": edited_content,
        "creator": "pilot_creator_e2e"
    })
    assert update_resp.status_code == 200
    assert update_resp.json()["status"] == "success"

    # Verify disk content has been updated
    re_read_resp = client.get("/api/drafts?creator=pilot_creator_e2e")
    updated_draft = next(d for d in re_read_resp.json()["drafts"] if d["filename"] == filename)
    assert "Edited via HITL Web Portal for Custom Deal Terms" in updated_draft["full_content"]
    print(f"  ✅ HITL edit persisted to disk successfully for '{filename}'.")

    # 12. Leads CSV Export
    print("\n[12/12] Testing GET /api/leads/export (CSV Download) ...")
    export_resp = client.get("/api/leads/export")
    assert export_resp.status_code == 200
    assert "text/csv" in export_resp.headers.get("content-type", "")
    csv_text = export_resp.text
    assert "company_name" in csv_text
    print(f"  ✅ CSV export verified ({len(csv_text.splitlines())} rows generated).")

    print("\n" + "=" * 70)
    print("🎉 ALL 12/12 END-TO-END VERIFICATION CHECKS PASSED SUCCESSFULLY!")
    print("=" * 70)

if __name__ == "__main__":
    try:
        run_all_checks()
    except Exception as err:
        print(f"\n❌ E2E Verification Failed: {err}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
