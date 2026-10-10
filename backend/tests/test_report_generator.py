"""Tests for the Phase 5.6 cybercrime report generator."""

from __future__ import annotations

from unittest.mock import patch

from app.models.schemas import IOCItem, ReportRequest, ThreatIOCs
from app.services.report_generator import generate_report


def _iocs() -> ThreatIOCs:
    return ThreatIOCs(
        phone_numbers=[IOCItem(value="9876543211", context="call me on this")],
        upi_ids=[IOCItem(value="sbi-safe@ybl")],
        urls=[IOCItem(value="https://sbi-kyc-verify.xyz/update")],
        domains=[IOCItem(value="sbi-kyc-verify.xyz")],
        bank_accounts=[IOCItem(value="1234567890123")],
        ifsc_codes=[IOCItem(value="SBIN0001234")],
        bank_names=["SBI"],
        scammer_names=["Officer Kumar"],
        reference_numbers=["KYC-2025-8834"],
        amounts=["₹50,000"],
        locations=["Delhi"],
    )


def _request(**kw) -> ReportRequest:
    base = dict(
        user_name="Priya Sharma",
        user_phone="9811122233",
        user_city="Mumbai",
        scam_type="bank_kyc",
        mode_of_contact="phone_call",
        incident_date="15 January 2025",
        incident_time="3:30 PM",
        amount_lost=0,
    )
    base.update(kw)
    return ReportRequest(**base)


class TestReportText:
    def test_all_iocs_present(self):
        out = generate_report(_request(), _iocs())
        text = out.report_text
        assert "9876543211" in text
        assert "sbi-safe@ybl" in text
        assert "sbi-kyc-verify.xyz" in text
        assert "1234567890123" in text
        assert "SBIN0001234" in text
        assert "KYC-2025-8834" in text
        assert "Officer Kumar" in text
        assert "Priya Sharma" in text

    def test_missing_fields_show_placeholder(self):
        out = generate_report(_request(user_name=None, user_city=None), ThreatIOCs())
        assert "[Not available]" in out.report_text
        assert "Anonymous" not in out.report_text  # anonymous flag not set

    def test_anonymous(self):
        out = generate_report(_request(anonymous=True), _iocs())
        assert "Name: Anonymous" in out.report_text
        assert "Priya" not in out.report_text

    def test_urgent_when_money_lost(self):
        out = generate_report(_request(amount_lost=50000), _iocs())
        assert out.urgent is True
        assert "1930" in out.report_text
        assert "IMMEDIATELY" in out.report_text
        assert "₹50,000" in out.report_text

    def test_not_urgent_without_loss(self):
        out = generate_report(_request(amount_lost=0), _iocs())
        assert out.urgent is False

    def test_honeypot_session_marked_intelligence(self):
        out = generate_report(_request(honeypot_session_id="hp-123"), _iocs())
        assert "INTELLIGENCE REPORT" in out.report_text

    def test_action_requested_lists_iocs(self):
        out = generate_report(_request(), _iocs())
        assert "Block the scammer's phone number" in out.report_text
        assert "Freeze the scammer's UPI ID" in out.report_text
        assert "Investigate the fraudulent domain" in out.report_text

    def test_report_id_format(self):
        out = generate_report(_request(), _iocs())
        assert out.report_id.startswith("RPT-2026-")


class TestNarrative:
    def test_fallback_narrative_is_deterministic_and_specific(self):
        out = generate_report(_request(), _iocs())
        assert "Bank KYC Fraud" in out.report_text
        assert "9876543211" in out.report_text.split("NARRATIVE:")[1]

    def test_llm_narrative_used_when_available(self):
        with patch(
            "app.clients.llm.chat_completion",
            return_value="The complainant received a fraudulent call and reported it.",
        ):
            out = generate_report(_request(), _iocs())
        assert "fraudulent call and reported it" in out.report_text

    def test_llm_failure_falls_back_to_template(self):
        with patch(
            "app.clients.llm.chat_completion", side_effect=RuntimeError("no key")
        ):
            out = generate_report(_request(), _iocs())
        assert "Bank KYC Fraud" in out.report_text  # template narrative used


class TestHelplineScript:
    def test_script_contains_all_fields(self):
        out = generate_report(_request(), _iocs())
        script = out.helpline_script
        assert "1930 HELPLINE SCRIPT" in script
        assert "Priya Sharma" in script
        assert "Mumbai" in script
        assert "9876543211" in script
        assert "sbi-safe@ybl" in script
        assert "SBI" in script

    def test_loss_line_flips_with_amount(self):
        lost = generate_report(_request(amount_lost=25000), _iocs())
        assert "Yes. The amount is ₹25,000." in lost.helpline_script
        safe = generate_report(_request(amount_lost=0), _iocs())
        assert "did not lose any money" in safe.helpline_script
