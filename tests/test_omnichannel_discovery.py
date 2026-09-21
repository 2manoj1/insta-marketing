"""
Tests for Omni-Channel Brand Discovery, Social Matrix, Email Tiering, and Collab Form Extraction.
"""
import pytest
from src.models.brand import BrandContact, BrandOpportunity
from src.skills.deep_bio_link import deep_bio_link_skill
from src.storage.db import DatabaseManager
from src.storage.okf import OKFManager


def test_classify_email_tier():
    # Tier 1 keywords: collab, pr, creator, influencer, partner
    assert deep_bio_link_skill.classify_email_tier("collabs@brand.com") == "Tier 1 (Direct PR / Collab)"
    assert deep_bio_link_skill.classify_email_tier("pr@brand.com") == "Tier 1 (Direct PR / Collab)"
    assert deep_bio_link_skill.classify_email_tier("influencers@brand.com") == "Tier 1 (Direct PR / Collab)"
    assert deep_bio_link_skill.classify_email_tier("creators@brand.com") == "Tier 1 (Direct PR / Collab)"
    assert deep_bio_link_skill.classify_email_tier("partnerships@brand.com") == "Tier 1 (Direct PR / Collab)"

    # Tier 2 keywords: marketing, press, media
    assert deep_bio_link_skill.classify_email_tier("marketing@brand.com") == "Tier 2 (Marketing Desk)"
    assert deep_bio_link_skill.classify_email_tier("press@brand.com") == "Tier 2 (Marketing Desk)"

    # Tier 3 keywords: info, support, hello, contact
    assert deep_bio_link_skill.classify_email_tier("info@brand.com") == "Tier 3 (Corporate / Support)"
    assert deep_bio_link_skill.classify_email_tier("support@brand.com") == "Tier 3 (Corporate / Support)"
    assert deep_bio_link_skill.classify_email_tier("customercare@brand.com") == "Tier 3 (Corporate / Support)"


def test_generate_meta_ad_library_url():
    url = deep_bio_link_skill.generate_meta_ad_library_url("Blue Tokai Coffee")
    assert "facebook.com/ads/library" in url
    assert "Blue+Tokai+Coffee" in url or "Blue%20Tokai%20Coffee" in url


def test_extract_contacts_from_html():
    sample_html = """
    <html>
      <head><title>Aesthetic D2C Brand</title></head>
      <body>
        <a href="mailto:creators@aestheticbrand.com">Collaborate with Us</a>
        <a href="mailto:info@aestheticbrand.com">Help</a>
        <a href="https://instagram.com/aestheticbrand">Instagram</a>
        <a href="https://linkedin.com/company/aesthetic-brand">LinkedIn</a>
        <a href="https://youtube.com/@aestheticbrand">YouTube</a>
        <a href="https://x.com/aestheticbrand">Twitter</a>
        <a href="https://linktr.ee/aestheticbrand">Bio Link</a>
        <a href="https://aestheticbrand.com/pages/collab">Creator Application Form</a>
        <p>Call or WhatsApp us at +91 98765 43210</p>
      </body>
    </html>
    """
    res = deep_bio_link_skill.extract_contacts_from_html(sample_html, base_url="https://aestheticbrand.com")

    # Email extraction and tiering
    assert "creators@aestheticbrand.com" in res["emails"]
    assert res["primary_email_tier"] == "Tier 1 (Direct PR / Collab)"

    # Social matrix
    assert "instagram.com/aestheticbrand" in res["socials"]["instagram"]
    assert "linkedin.com/company/aesthetic-brand" in res["socials"]["linkedin"]
    assert "youtube.com/@aestheticbrand" in res["socials"]["youtube"]
    assert "x.com/aestheticbrand" in res["socials"]["twitter"]
    assert "linktr.ee/aestheticbrand" in res["socials"]["linktree"]

    # Collab form
    assert res["collab_form_url"] == "https://aestheticbrand.com/pages/collab"

    # Phone / WhatsApp
    assert len(res["phones"]) > 0
    assert res["whatsapp_ready"] is True


def test_sqlite_omnichannel_persistence(tmp_path):
    db = DatabaseManager(db_path=tmp_path / "test_leads.db")
    contact = BrandContact(
        contact_email="pr@d2cbrand.com",
        mobile_number="+91 91234 56789",
        phone_number="+91 91234 56789",
        instagram_handle="@d2cbrand",
        website="https://d2cbrand.com",
        linkedin_url="https://linkedin.com/company/d2cbrand",
        youtube_url="https://youtube.com/@d2cbrand",
        twitter_url="https://twitter.com/d2cbrand",
        linktree_url="https://linktr.ee/d2cbrand",
        collab_form_url="https://d2cbrand.com/pages/collab",
        meta_ad_library_url="https://www.facebook.com/ads/library/?q=d2cbrand",
        email_tier="Tier 1 (Direct PR / Collab)",
        whatsapp_ready=True,
        source="live_web_verified",
    )
    opp = BrandOpportunity(
        brand_name="D2C Brand",
        website="https://d2cbrand.com",
        industry="Lifestyle / Apparel",
        location="India",
        fit_score=94,
        suggested_angle="Aesthetic UGC try-on reel",
        contact=contact,
    )

    inserted = db.save_leads("test_creator", [opp])
    assert inserted == 1

    leads = db.get_all_leads(creator_username="test_creator")
    assert len(leads) == 1
    lead = leads[0]

    assert lead["company_name"] == "D2C Brand"
    assert lead["marketing_email"] == "pr@d2cbrand.com"
    assert lead["linkedin_url"] == "https://linkedin.com/company/d2cbrand"
    assert lead["collab_form_url"] == "https://d2cbrand.com/pages/collab"
    assert lead["meta_ad_library_url"] == "https://www.facebook.com/ads/library/?q=d2cbrand"
    assert lead["email_tier"] == "Tier 1 (Direct PR / Collab)"
    assert lead["whatsapp_ready"] == 1


def test_instagram_handle_and_url_sanitization():
    # 1. Doubled URL reported by user: https://instagram.com/https://instagram.com/travelosei
    c1 = BrandContact(instagram_handle="https://instagram.com/https://instagram.com/travelosei")
    assert c1.instagram_handle == "@travelosei"
    assert c1.instagram_url == "https://instagram.com/travelosei"

    # 2. Single full URL with trailing slashes / queries
    c2 = BrandContact(instagram_handle="https://instagram.com/travelosei/?hl=en")
    assert c2.instagram_handle == "@travelosei"
    assert c2.instagram_url == "https://instagram.com/travelosei"

    # 3. Already clean @handle
    c3 = BrandContact(instagram_handle="@travelosei")
    assert c3.instagram_handle == "@travelosei"
    assert c3.instagram_url == "https://instagram.com/travelosei"

    # 4. Raw handle without @
    c4 = BrandContact(instagram_handle="travelosei")
    assert c4.instagram_handle == "@travelosei"
    assert c4.instagram_url == "https://instagram.com/travelosei"

    # 5. Doubled protocols in website or general URLs
    c5 = BrandContact(
        website="https://https://brand.com",
        collab_form_url="https://brand.com/https://brand.com/pages/collab",
    )
    assert c5.website == "https://brand.com"
    assert c5.collab_form_url == "https://brand.com/pages/collab"

