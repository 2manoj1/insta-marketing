"""
Unit tests for the Open Knowledge Framework (OKF) storage and retrieval engine.
"""
from pathlib import Path
from src.models.brand import BrandContact, BrandOpportunity
from src.storage.okf import OKFManager


def test_okf_initialization_and_seeding(tmp_path: Path):
    mgr = OKFManager(okf_dir=tmp_path / "okf")
    summary = mgr.get_summary()

    # OKF starts clean with zero hardcoded brands, learning dynamically
    assert summary["total_brands_in_okf"] == 0
    assert summary["total_verified_emails"] == 0
    assert summary["total_verified_phones"] == 0

    benchmarks = mgr.get_benchmarks()
    assert "rates_by_tier" in benchmarks


def test_okf_save_and_query(tmp_path: Path):
    mgr = OKFManager(okf_dir=tmp_path / "okf")

    brand = BrandOpportunity(
        brand_name="Custom Brand Test",
        website="https://custombrand.io",
        industry="Custom Technology",
        location="India",
        fit_score=95,
        suggested_angle="Workspace tech setup",
        contact=BrandContact(
            contact_email="partnerships@custombrand.io",
            mobile_number="+91 99887 76655",
            source="live_web_verified",
        ),
    )

    saved = mgr.save_brand_intelligence(brand, creator_username="test_creator")
    assert saved is True

    # Query with niche filter
    matches = mgr.query_brands(niche="Technology", limit=5)
    match_names = [m["brand_name"] for m in matches]
    assert "Custom Brand Test" in match_names

    # Query with exclusion
    matches_ex = mgr.query_brands(niche="Technology", exclude_names={"custom brand test"}, limit=5)
    match_names_ex = [m["brand_name"] for m in matches_ex]
    assert "Custom Brand Test" not in match_names_ex
