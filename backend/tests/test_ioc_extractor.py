"""Tests for the Phase 5.2 IOC extractor (regex + LLM layers, dedup, validation)."""

from __future__ import annotations

import json
from unittest.mock import patch

from app.models.schemas import IOCItem, ThreatIOCs
from app.services import ioc_extractor

MESSAGE = (
    "Good afternoon, this is Officer Rajesh from SBI. Your KYC is incomplete. "
    "Transfer ₹50,000 to sbi-safe@ybl immediately, or call me on 98765 43211. "
    "Also WhatsApp me on +91-87654-32109. Open https://sbi-kyc-verify.xyz/update "
    "and give account number 555666777888 with IFSC SBIN0001234. "
    "Your case reference is KYC-2025-8834. My colleague Ramesh will help."
)


class TestRegexExtraction:
    def test_phone_numbers(self):
        iocs = ioc_extractor.extract_iocs(MESSAGE)
        phones = [i.value for i in iocs.phone_numbers]
        assert "9876543211" in phones
        assert "8765432109" in phones  # +91-87654-32109 normalized

    def test_upi_ids(self):
        iocs = ioc_extractor.extract_iocs(MESSAGE)
        assert "sbi-safe@ybl" in [i.value for i in iocs.upi_ids]

    def test_urls(self):
        iocs = ioc_extractor.extract_iocs(MESSAGE)
        assert any("sbi-kyc-verify.xyz" in u.value for u in iocs.urls)

    def test_domain_extracted_from_url(self):
        iocs = ioc_extractor.extract_iocs(MESSAGE)
        assert "sbi-kyc-verify.xyz" in [d.value for d in iocs.domains]

    def test_bank_account_requires_keyword_context(self):
        iocs = ioc_extractor.extract_iocs(MESSAGE)
        assert "555666777888" in [a.value for a in iocs.bank_accounts]
        # A bare 12-digit number with no account keyword must NOT match.
        bare = ioc_extractor.extract_iocs("My pin is 998877665544 ok")
        assert bare.bank_accounts == []

    def test_ifsc(self):
        iocs = ioc_extractor.extract_iocs(MESSAGE)
        assert "SBIN0001234" in [i.value for i in iocs.ifsc_codes]

    def test_amounts_and_references(self):
        iocs = ioc_extractor.extract_iocs(MESSAGE)
        assert any("50,000" in a for a in iocs.amounts)
        assert "KYC-2025-8834" in iocs.reference_numbers

    def test_bank_names_and_locations(self):
        iocs = ioc_extractor.extract_iocs("SBI officer called from Delhi about HDFC account")
        assert "SBI" in iocs.bank_names
        assert "Delhi" in iocs.locations

    def test_email_is_not_a_upi_id(self):
        iocs = ioc_extractor.extract_iocs("write to support@sbi.co.in or admin@example.com")
        upis = [i.value for i in iocs.upi_ids]
        assert "admin@example.com" not in upis

    def test_deduplication(self):
        text = "call 9876543211 or 9876543211 again, pay to sbi-safe@ybl and sbi-safe@ybl"
        iocs = ioc_extractor.extract_iocs(text)
        assert len(iocs.phone_numbers) == 1
        assert len(iocs.upi_ids) == 1

    def test_empty_text(self):
        assert ioc_extractor.extract_iocs("").total() == 0


class TestValidation:
    def test_honeypot_fake_details_filtered(self):
        # The persona's own fabricated phone/account must never be stored.
        iocs = ioc_extractor.extract_iocs(
            "My account number is 1234567890 and my number is 9876543210"
        )
        assert "9876543210" not in [i.value for i in iocs.phone_numbers]
        assert "1234567890" not in [a.value for a in iocs.bank_accounts]

    def test_legit_helplines_filtered(self):
        iocs = ioc_extractor.extract_iocs("call 18004253800 or 1930 immediately")
        assert iocs.phone_numbers == []

    def test_llm_output_validated(self):
        raw = json.dumps(
            {
                "phone_numbers": ["+91 98111 22233", "12345"],  # 12345 invalid
                "upi_ids": ["Scam.Pay@YBL", "bad@com"],         # bad@com emailish
                "bank_accounts": ["1234567890"],                # honeypot fake
                "urls": ["http://evil.example/update"],
            }
        )
        with patch("app.clients.llm.chat_completion", return_value=raw):
            iocs = ioc_extractor.llm_extract_iocs("scam text")
        assert [i.value for i in iocs.phone_numbers] == ["9811122233"]
        assert [i.value for i in iocs.upi_ids] == ["scam.pay@ybl"]
        assert iocs.bank_accounts == []
        assert "evil.example" in [d.value for d in iocs.domains]


class TestLLMLayer:
    def test_llm_failure_returns_empty(self):
        with patch("app.clients.llm.chat_completion", side_effect=RuntimeError("down")):
            assert ioc_extractor.llm_extract_iocs("text").total() == 0

    def test_extract_all_without_llm(self):
        iocs = ioc_extractor.extract_all("pay 9988776655 via fraud@upi", use_llm=False)
        assert "9988776655" in [i.value for i in iocs.phone_numbers]

    def test_merge_iocs(self):
        a = ioc_extractor.extract_iocs("call 9876543211")
        b = ioc_extractor.extract_iocs("upi is kyc-verify@paytm")
        merged = ioc_extractor.merge_iocs(a, b)
        assert merged.total() == 2
        assert len(ioc_extractor.merge_iocs(merged, a).phone_numbers) == 1


def test_iocs_as_plain_dict():
    iocs = ThreatIOCs(
        phone_numbers=[IOCItem(value="9876543211")],
        upi_ids=[IOCItem(value="sbi-safe@ybl")],
    )
    plain = ioc_extractor.iocs_as_plain_dict(iocs)
    assert plain["phone_numbers"] == ["9876543211"]
    assert plain["upi_ids"] == ["sbi-safe@ybl"]
