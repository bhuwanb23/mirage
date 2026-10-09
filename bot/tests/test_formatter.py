"""Tests for utils/formatter — the Telegram HTML verdict rendering."""

from __future__ import annotations

import pytest

from utils.formatter import (
    authenticity_bar,
    esc,
    format_image_block,
    format_url_block,
    format_verdict,
    format_voice_block,
    percent,
    risk_bar,
    split_message,
)

SCAM = {
    "is_scam": True,
    "confidence": 0.92,
    "scam_type": "bank_kyc",
    "risk_level": "critical",
    "red_flags": [
        "Domain sbi-kyc-verify.xyz is only 4 days old",
        "Asks for ATM PIN",
        "Creates extreme urgency",
    ],
    "summary": "This is a Bank KYC scam & it says <click> now.",
    "recommended_action": "DELETE IMMEDIATELY",
    "evidence": [
        {"type": "url_analysis", "detail": "Domain registered 4 days ago via Namecheap"},
        {"type": "linguistic", "detail": "Message asks for ATM PIN"},
    ],
}

LEGIT = {
    "is_scam": False,
    "confidence": 0.1,
    "summary": "Looks like a normal bank alert.",
}

UNCERTAIN = {
    "is_scam": True,
    "confidence": 0.5,
    "scam_type": "romance",
    "risk_level": "medium",
    "red_flags": ["Moves conversation to WhatsApp"],
    "summary": "Could be genuine, pattern is suspicious.",
}


# ---------------------------------------------------------------------------
# Scam verdict
# ---------------------------------------------------------------------------

class TestScamBlock:
    def test_header_and_confidence(self):
        out = format_verdict(SCAM)
        assert "SCAM DETECTED" in out
        assert "92% confident" in out

    def test_type_and_risk(self):
        out = format_verdict(SCAM)
        assert "Bank KYC / Account Freeze" in out
        assert "🔴" in out and "CRITICAL" in out

    def test_red_flags_bulleted(self):
        out = format_verdict(SCAM)
        assert "⚠️ Red Flags:" in out
        assert "• Domain sbi-kyc-verify.xyz is only 4 days old" in out
        assert "• Asks for ATM PIN" in out

    def test_summary_and_action(self):
        out = format_verdict(SCAM)
        assert "📋 Summary:" in out
        assert "✅ What to do:" in out
        assert "DELETE IMMEDIATELY" in out

    def test_top_3_evidence(self):
        out = format_verdict(SCAM)
        assert "🔬 Evidence:" in out
        assert "Domain registered 4 days ago" in out

    def test_footer(self):
        out = format_verdict(SCAM)
        assert "1930" in out and "cybercrime.gov.in" in out

    def test_html_escaping_of_verdict_content(self):
        out = format_verdict(SCAM)
        assert "&lt;click&gt;" in out          # escaped
        assert "<click>" not in out             # raw never leaks
        assert "Bank KYC scam &amp; it says" in out

    def test_invalid_verdict_returns_error_text(self):
        out = format_verdict(None)  # type: ignore[arg-type]
        assert "server error" in out.lower()


# ---------------------------------------------------------------------------
# Legitimate + uncertain
# ---------------------------------------------------------------------------

class TestLegitBlock:
    def test_header(self):
        out = format_verdict(LEGIT)
        assert "LIKELY LEGITIMATE" in out
        assert "10% confident" in out

    def test_tips_present(self):
        out = format_verdict(LEGIT)
        assert "💡 Tips:" in out
        assert "Never share your OTP" in out

    def test_no_red_flag_section(self):
        out = format_verdict(LEGIT)
        assert "Red Flags" not in out


class TestUncertainBlock:
    def test_header_and_pct(self):
        out = format_verdict(UNCERTAIN)
        assert "UNCERTAIN" in out
        assert "50% confident" in out

    def test_recommendation(self):
        out = format_verdict(UNCERTAIN)
        assert "Proceed with caution" in out

    def test_low_confidence_scam_is_uncertain(self):
        v = dict(SCAM, confidence=0.45)
        assert "UNCERTAIN" in format_verdict(v)


# ---------------------------------------------------------------------------
# Bars
# ---------------------------------------------------------------------------

class TestBars:
    @pytest.mark.parametrize(
        "score,expected",
        [
            (0.10, "Likely Human"),
            (0.30, "Probably Human"),
            (0.50, "Uncertain"),
            (0.70, "Likely AI-Generated"),
            (0.95, "AI-Generated"),
        ],
    )
    def test_authenticity_buckets(self, score, expected):
        assert expected in authenticity_bar(score)

    def test_risk_bar_five_segments(self):
        bar = risk_bar(0.75)
        assert len(bar) == 5
        assert bar.count("🟥") == 4  # round(0.75*5)=4

    def test_risk_bar_clamped(self):
        assert risk_bar(1.5).count("🟥") == 5
        assert risk_bar(-1).count("🟥") == 0

    def test_percent_rounding(self):
        assert percent(0.92) == 92
        assert percent(None) == 0
        assert percent("0.5") == 50


# ---------------------------------------------------------------------------
# Voice preamble
# ---------------------------------------------------------------------------

class TestVoiceBlock:
    def test_contains_transcript_and_language(self):
        out = format_voice_block("Send ₹50,000 now", "hi", 0.72, "likely_ai_generated")
        assert "VOICE NOTE ANALYSIS" in out
        assert "Send ₹50,000 now" in out
        assert "Hindi" in out
        assert "72%" in out

    def test_empty_transcript_placeholder(self):
        out = format_voice_block("", "en", 0.0, "unknown")
        assert "(no speech detected)" in out

    def test_long_transcript_truncated(self):
        out = format_voice_block("x" * 2000, "en", 0.0, "unknown")
        assert "…" in out
        assert len(out) < 3000

    def test_transcript_escaped(self):
        out = format_voice_block("a <b> tag", "en", 0.0, "unknown")
        assert "&lt;b&gt;" in out and "<b> tag" not in out.replace("<b> tag", "", 0)


# ---------------------------------------------------------------------------
# Image preamble
# ---------------------------------------------------------------------------

class TestImageBlock:
    def test_app_and_ocr(self):
        out = format_image_block("Your OTP is 123456", "WhatsApp", [])
        assert "SCREENSHOT ANALYSIS" in out
        assert "WhatsApp" in out
        assert "<code>" in out

    def test_ocr_truncated_at_500(self):
        out = format_image_block("y" * 900, "SMS", [])
        assert "truncated. Full text analyzed." in out

    def test_visual_anomalies_listed(self):
        out = format_image_block("text", "Browser", ["blurred logo", "wrong font"])
        assert "Visual Anomalies:" in out
        assert "• blurred logo" in out

    def test_ocr_escaped(self):
        out = format_image_block("<script>alert(1)</script>", "Unknown", [])
        assert "<script>" not in out


# ---------------------------------------------------------------------------
# URL preamble
# ---------------------------------------------------------------------------

def _url_info(**over):
    base = {
        "url": "http://sbi-kyc-verify.xyz/update",
        "domain": "sbi-kyc-verify.xyz",
        "tld": ".xyz",
        "domain_age_days": 4,
        "registrar": "Namecheap",
        "https": False,
        "risk_score": 0.75,
        "is_lookalike": True,
        "lookalike_target": "sbi.co.in",
        "brand_keyword": "sbi",
        "is_suspicious": True,
        "red_flags": ["Domain is only 4 days old", "Uses suspicious TLD .xyz"],
    }
    base.update(over)
    return base


class TestUrlBlock:
    def test_suspicious_fields(self):
        out = format_url_block(_url_info())
        assert "DOMAIN ANALYSIS" in out
        assert "sbi-kyc-verify.xyz" in out
        assert ".xyz" in out
        assert "4 days" in out
        assert "Namecheap" in out
        assert "❌ No" in out
        assert "75%" in out

    def test_lookalike_callout(self):
        out = format_url_block(_url_info())
        assert "lookalike" in out.lower() or "NOT the official" in out
        assert "sbi.co.in" in out

    def test_legit_domain(self):
        out = format_url_block(
            _url_info(
                url="https://sbi.co.in",
                domain="sbi.co.in",
                tld=".co.in",
                domain_age_days=8765,
                registrar="NIC",
                https=True,
                risk_score=0.02,
                is_lookalike=False,
                lookalike_target=None,
                brand_keyword=None,
                is_suspicious=False,
                red_flags=[],
            )
        )
        assert "✅ Yes" in out
        assert "8,765 days" in out
        assert "2%" in out

    def test_unknown_age(self):
        out = format_url_block(_url_info(domain_age_days=None))
        assert "WHOIS unavailable" in out

    def test_red_flags_listed(self):
        out = format_url_block(_url_info())
        assert "Red Flags:" in out
        assert "• Domain is only 4 days old" in out


# ---------------------------------------------------------------------------
# Splitting
# ---------------------------------------------------------------------------

class TestSplit:
    def test_short_message_single_chunk(self):
        assert split_message("hello") == ["hello"]

    def test_long_message_all_chunks_within_limit(self):
        text = "\n".join(f"line {i} with padding content here" for i in range(600))
        chunks = split_message(text)
        assert len(chunks) > 1
        assert all(len(c) <= 4096 for c in chunks)

    def test_no_content_lost(self):
        text = "\n".join(f"line {i}" for i in range(2000))
        chunks = split_message(text)
        assert "\n".join(chunks) == text

    def test_single_oversized_line_hard_cut(self):
        text = "z" * 10000
        chunks = split_message(text)
        assert all(len(c) <= 4096 for c in chunks)
        assert "".join(chunks) == text


def test_esc():
    assert esc("<&>") == "&lt;&amp;&gt;"
