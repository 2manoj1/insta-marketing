"""
Test Suite for Measurable Evaluation & Investor Benchmark Engine.
"""
from pathlib import Path
from src.evals.metrics import EvaluationMetrics
from src.evals.benchmark_runner import BenchmarkRunner
from src.browser.stealth import HumanEmulator


def test_email_validity_scoring():
    # Valid deliverable emails
    ok, msg = EvaluationMetrics.evaluate_email_validity("partnerships@thetamara.com")
    assert ok is True

    ok, msg = EvaluationMetrics.evaluate_email_validity("collab@snitch.co.in")
    assert ok is True

    # Invalid emails
    ok, msg = EvaluationMetrics.evaluate_email_validity("noreply@brand.com")
    assert ok is False
    assert "Blacklisted" in msg

    ok, msg = EvaluationMetrics.evaluate_email_validity("invalid-email-address")
    assert ok is False

    ok, msg = EvaluationMetrics.evaluate_email_validity("")
    assert ok is False


def test_phone_validity_scoring():
    # Valid numbers
    ok, msg = EvaluationMetrics.evaluate_phone_validity("+91 95919 96919")
    assert ok is True

    ok, msg = EvaluationMetrics.evaluate_phone_validity("+1 888 539 2476")
    assert ok is True

    # Invalid numbers
    ok, msg = EvaluationMetrics.evaluate_phone_validity("123")
    assert ok is False
    assert "Invalid digit count" in msg

    ok, msg = EvaluationMetrics.evaluate_phone_validity("N/A")
    assert ok is False


def test_pitch_deliverability_and_spam_scoring():
    # Clean high-performing pitch
    subject = "Luxury Weekend Getaway UGC Collab with @iva_mana5"
    body = "Hi The Tamara Resorts Team,\n\nIva (@iva_mana5) is a Bangalore travel creator with 77k followers. Would it be alright if I sent over a 20-second sample storyboard concept for your review?\n\nBest,\nTalent Team"
    res = EvaluationMetrics.evaluate_pitch_deliverability_and_spam(subject, body, "marketing@thetamara.com")
    assert res["is_deliverable"] is True
    assert res["deliverability_score"] >= 90.0
    assert len(res["spam_hits"]) == 0

    # Spammy pitch with triggers
    spam_subject = "ACT NOW 100% FREE MONEY FOR YOUR BRAND!!!"
    spam_body = "CLICK HERE to earn cash and get guaranteed miracle sales right now order now!"
    res2 = EvaluationMetrics.evaluate_pitch_deliverability_and_spam(spam_subject, spam_body, "brand@example.com")
    assert res2["deliverability_score"] < 50.0
    assert len(res2["spam_hits"]) >= 2


def test_commercial_roi_calculations():
    roi = EvaluationMetrics.calculate_commercial_roi(leads_count=10, creator_followers=77_000, ugc_rate_usd=400.0)
    assert roi["leads_analyzed"] == 10
    assert roi["manual_hours_saved"] == 7.5
    assert roi["agency_labor_cost_saved_usd"] == 262.5
    assert roi["gross_pipeline_value_usd"] == 4000.0
    assert roi["projected_revenue_unlocked_usd"] == 800.0


def test_benchmark_runner_report_generation(tmp_path):
    report_file = tmp_path / "test_benchmark.json"
    runner = BenchmarkRunner(report_path=report_file)
    report = runner.run_benchmark()

    assert report_file.exists()
    assert report["composite_score"] > 80.0
    assert report["overall_grade"] in ["A+", "A", "B+"]
    assert "metrics" in report
    assert "commercial_roi" in report
    assert report["metrics"]["email_deliverability_accuracy_pct"] >= 90.0


def test_stealth_human_emulator_rate_limiter():
    emulator = HumanEmulator(min_delay=0.01, max_delay=0.02)
    # Check rate limiter accepts requests up to limit
    for _ in range(5):
        assert emulator.check_rate_limit() is True
