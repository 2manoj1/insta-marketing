"""
Unit tests for the modular Skills framework:
- ContactVerifierSkill
- NegotiationPricingSkill
- PitchSequencingSkill
- DeepBioLinkSkill
"""
from src.models.brand import BrandContact, BrandOpportunity
from src.models.creator import CreatorProfile
from src.skills.contact_verifier import contact_verifier_skill
from src.skills.deep_bio_link import deep_bio_link_skill
from src.skills.negotiation_pricing import negotiation_pricing_skill
from src.skills.pitch_sequencing import pitch_sequencing_skill


def test_contact_verifier_email():
    # 1. Valid partnership email
    res1 = contact_verifier_skill.verify_email("collab@snitch.co.in")
    assert res1["is_valid"] is True
    assert res1["role"] == "partnership"
    assert res1["confidence_score"] >= 90

    # 2. Disposable / blacklisted domain
    res2 = contact_verifier_skill.verify_email("fake@tempmail.com")
    assert res2["is_valid"] is False
    assert res2["role"] == "disposable"

    # 3. Malformed syntax
    res3 = contact_verifier_skill.verify_email("not-an-email")
    assert res3["is_valid"] is False


def test_contact_verifier_phone():
    # 1. Valid 10-digit Indian phone
    p1 = contact_verifier_skill.verify_phone("9876543210")
    assert p1["is_valid"] is True
    assert p1["phone"] == "+91 98765 43210"

    # 2. International E.164 phone
    p2 = contact_verifier_skill.verify_phone("+14155552671")
    assert p2["is_valid"] is True
    assert p2["phone"] == "+14155552671"

    # 3. Invalid too short phone
    p3 = contact_verifier_skill.verify_phone("12345")
    assert p3["is_valid"] is False


def test_negotiation_pricing_tiers():
    # Nano
    nano = CreatorProfile(username="nano", followers_count=4500, niche_categories=["lifestyle"])
    r1 = negotiation_pricing_skill.calculate_rate_card(nano)
    assert r1["creator_tier"] == "Nano Creator"

    # Micro with Luxury Travel niche multiplier
    micro = CreatorProfile(username="micro", followers_count=35000, niche_categories=["Luxury Travel"])
    r2 = negotiation_pricing_skill.calculate_rate_card(micro)
    assert r2["creator_tier"] == "Micro Influencer"
    assert r2["niche_multiplier"] >= 1.25
    assert "ugc_video_30d_ads" in r2
    assert "organic_sponsored_reel" in r2


def test_pitch_sequencing_output():
    creator = CreatorProfile(
        username="iva_mana5",
        full_name="Iva Mana",
        followers_count=28500,
        niche_categories=["Luxury Hospitality", "Travel"],
        contact_email="iva@example.com",
    )
    opp = BrandOpportunity(
        brand_name="The Tamara Resorts",
        website="https://thetamara.com",
        industry="Luxury Eco-Resorts",
        suggested_angle="Luxury weekend staycation reel highlighting dining",
        contact=BrandContact(
            contact_email="marketing@thetamara.com",
            mobile_number="+91 95919 96919",
        ),
    )

    seq = pitch_sequencing_skill.generate_sequence(creator, opp)
    assert "subject" in seq
    assert "The Tamara Resorts" in seq["subject"]
    assert "email_body" in seq
    assert "dm_body" in seq
    assert "whatsapp_body" in seq
    assert "iva_mana5" in seq["dm_body"]
    assert "+91 95919 96919" in seq["recipient_phone"]


def test_deep_bio_link_html_extraction():
    html = """
    <html>
      <body>
        <div class="footer">
          <p>Need help? Contact support@brand.com or write to collab@brand.com</p>
          <a href="mailto:press@brand.com">Press Inquiries</a>
          <a href="https://wa.me/919900012345">WhatsApp Support</a>
          <a href="/about-us.png">Logo Image</a>
        </div>
      </body>
    </html>
    """
    res = deep_bio_link_skill.extract_contacts_from_html(html)
    assert "collab@brand.com" in res["emails"]
    assert "press@brand.com" in res["emails"]
    assert "+91 99000 12345" in res["phones"]
    # Image name should not be treated as email
    assert not any(".png" in e for e in res["emails"])


def test_free_web_search_skill_url_cleaning():
    from src.skills.web_search import free_web_search_skill
    # 1. Unwrapping DDG redirect URL
    ddg_redirect = "//duckduckgo.com/l/?uddg=https%3A%2F%2Fmokobara.com%2F&rut=123"
    cleaned = free_web_search_skill._clean_ddg_url(ddg_redirect)
    assert cleaned == "https://mokobara.com/"

    # 2. Scheme-relative URL
    cleaned2 = free_web_search_skill._clean_ddg_url("//example.com/page")
    assert cleaned2 == "https://example.com/page"

    # 3. Direct URL
    cleaned3 = free_web_search_skill._clean_ddg_url("https://snitch.co.in")
    assert cleaned3 == "https://snitch.co.in"


def test_live_search_endpoint():
    from fastapi.testclient import TestClient
    from src.server.app import app

    client = TestClient(app)
    # Test POST /api/search/live
    resp = client.post(
        "/api/search/live",
        json={"niche": "Tech EDC", "location": "India", "limit": 2},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert "brands" in data
    assert isinstance(data["brands"], list)
