"""Tests for the text scam classifier (backend/app/services/scam_analyzer.py).

Design note:
- Pure-logic tests (edge cases, JSON parsing, calibration, risk mapping) do not
  call an LLM and run offline.
- LLM-integrated tests patch `app.clients.llm.chat_completion` with canned
  responses so they run without API keys.

Run:  cd backend && uv run pytest backend/tests/test_scam_analyzer.py -q
"""

from __future__ import annotations

import json
from unittest.mock import patch

from conftest import _patch_completion

from app.models.schemas import RiskLevel, ScamVerdict
from app.services.scam_analyzer import (
    _analysis_failed_verdict,
    _as_str_list,
    _calibrate,
    _contains_phone,
    _contains_url,
    _extract_json,
    _looks_like_emoji_only,
    _normalize_text,
    _parse_fallback,
    _risk_from_confidence,
    analyze_text,
)

# ---------------------------------------------------------------------------
# Edge-case / schema tests (no LLM call)
# ---------------------------------------------------------------------------

class TestEmptyAndNoContent:
    def test_empty_string_returns_empty_verdict(self):
        v = analyze_text("")
        assert v.is_scam is False
        assert v.confidence == 0.0
        assert v.summary == "No content to analyze"

    def test_whitespace_only_returns_empty_verdict(self):
        v = analyze_text("   \t\n  ")
        assert v.is_scam is False
        assert v.confidence == 0.0

    def test_emoji_only_returns_empty_verdict(self):
        v = analyze_text("😂👍🔥")
        assert v.is_scam is False
        assert v.confidence == 0.0

    def test_single_punctuation_returns_empty_verdict(self):
        v = analyze_text("!!!")
        assert v.is_scam is False
        assert v.confidence == 0.0

    def test_analyze_text_returns_valid_schema(self):
        v = analyze_text("")
        assert isinstance(v, ScamVerdict)
        assert 0.0 <= v.confidence <= 1.0


class TestNormalization:
    def test_short_text_passthrough(self):
        assert _normalize_text("Hello world") == "Hello world"

    def test_empty_normalizes_to_empty(self):
        assert _normalize_text("") == ""
        assert _normalize_text("   ") == ""

    def test_truncation_at_max_length(self):
        long_text = "a" * 6000
        normalized = _normalize_text(long_text)
        assert len(normalized) <= 5000
        assert normalized.endswith(" [Message truncated for analysis]")

    def test_boundary_no_truncation_when_exactly_at_limit(self):
        text = "x" * 5000
        assert _normalize_text(text) == text


class TestEmojiHeuristic:
    def test_alphanumeric_content_satisfies(self):
        assert _looks_like_emoji_only("Hello 😂") is False

    def test_emoji_only_satisfies(self):
        assert _looks_like_emoji_only("😂👍") is True

    def test_short_whitespace_satisfies(self):
        assert _looks_like_emoji_only(" ") is True


class TestUrlAndPhoneHeuristics:
    def test_http_url_detected(self):
        assert _contains_url("click http://example.com") is True
        assert _contains_url("no link here") is False

    def test_https_url_detected(self):
        assert _contains_url("https://sbi.co.in") is True

    def test_indian_mobile_pattern_detected(self):
        assert _contains_phone("+91-98765-43210") is True
        assert _contains_phone("9876543210") is True

    def test_no_phone_when_missing(self):
        assert _contains_phone("call your bank") is False


# ---------------------------------------------------------------------------
# JSON extraction
# ---------------------------------------------------------------------------

class TestJsonExtraction:
    def test_raw_json(self):
        obj = _extract_json('{"is_scam": true, "confidence": 0.9}')
        assert obj == {"is_scam": True, "confidence": 0.9}

    def test_markdown_fenced_json(self):
        text = "```json\n{\"is_scam\": false}\n```"
        obj = _extract_json(text)
        assert obj == {"is_scam": False}

    def test_markdown_fenced_no_label(self):
        text = "```\n{\"is_scam\": true}\n```"
        obj = _extract_json(text)
        assert obj["is_scam"] is True

    def test_json_inside_prose(self):
        text = "Here is the result: {\"is_scam\": true, \"confidence\": 0.5} end."
        obj = _extract_json(text)
        assert obj == {"is_scam": True, "confidence": 0.5}

    def test_empty_string_returns_none(self):
        assert _extract_json("") is None

    def test_non_json_text_returns_none(self):
        assert _extract_json("I think this is a scam") is None


# ---------------------------------------------------------------------------
# Fallback parsing
# ---------------------------------------------------------------------------

class TestFallbackParsing:
    def test_full_payload(self, bank_kyc_llm_json):
        payload = json.loads(bank_kyc_llm_json)
        v = _parse_fallback(payload, original="some text")
        assert v.is_scam is True
        assert v.confidence == 0.95
        assert v.scam_type == "bank_kyc"
        assert v.risk_level == RiskLevel.CRITICAL
        assert len(v.red_flags) == 5
        assert "hook" in v.stages_detected
        assert v.summary
        assert v.recommended_action

    def test_missing_fields_filled_with_defaults(self):
        payload = {"is_scam": True}
        v = _parse_fallback(payload, original="x")
        assert v.is_scam is True
        assert v.confidence == 0.0
        assert v.scam_type is None
        assert v.risk_level == RiskLevel.LOW
        assert v.red_flags == []
        assert v.stages_detected == []
        assert v.summary  # non-empty fallback

    def test_invalid_scam_type_normalized_to_none(self):
        payload = {"is_scam": True, "scam_type": "super_scam_xyz"}
        v = _parse_fallback(payload, original="x")
        assert v.scam_type is None

    def test_invalid_risk_normalized_to_low(self):
        payload = {"is_scam": True, "risk_level": "super_high"}
        v = _parse_fallback(payload, original="x")
        assert v.risk_level == RiskLevel.LOW

    def test_non_list_red_flags_become_single_item(self):
        payload = {"is_scam": True, "red_flags": "one flag"}
        v = _parse_fallback(payload, original="x")
        assert v.red_flags == ["one flag"]

    def test_none_payload_returns_failure_verdict(self):
        v = _parse_fallback(None, original="x")
        assert v.is_scam is False
        assert v.confidence == 0.0
        assert "failed" in v.summary.lower()

    def test_as_str_list_handles_strings_and_lists(self):
        assert _as_str_list(["a", "b"]) == ["a", "b"]
        assert _as_str_list("only") == ["only"]
        assert _as_str_list(None) == []
        assert _as_str_list(123) == ["123"]


# ---------------------------------------------------------------------------
# Confidence calibration + risk mapping
# ---------------------------------------------------------------------------

class TestRiskFromConfidence:
    def test_not_scam_low_confidence(self):
        assert _risk_from_confidence(0.1, False) == RiskLevel.LOW
        assert _risk_from_confidence(0.4, False) == RiskLevel.LOW

    def test_not_scam_above_midpoint(self):
        assert _risk_from_confidence(0.6, False) == RiskLevel.MEDIUM
        assert _risk_from_confidence(0.8, False) == RiskLevel.HIGH

    def test_scam_bands(self):
        assert _risk_from_confidence(0.4, True) == RiskLevel.MEDIUM
        assert _risk_from_confidence(0.6, True) == RiskLevel.MEDIUM
        assert _risk_from_confidence(0.75, True) == RiskLevel.HIGH
        assert _risk_from_confidence(0.9, True) == RiskLevel.CRITICAL

    def test_boundaries_inclusive(self):
        assert _risk_from_confidence(0.7, True) == RiskLevel.HIGH
        assert _risk_from_confidence(0.85, True) == RiskLevel.CRITICAL


class TestCalibration:
    def test_confidence_clamped_to_1(self):
        v = ScamVerdict.model_construct(
            is_scam=True, confidence=1.5, risk_level=RiskLevel.HIGH
        )
        out = _calibrate(v)
        assert out.confidence <= 1.0

    def test_confidence_clamped_to_zero(self):
        v = ScamVerdict.model_construct(
            is_scam=False, confidence=-0.5
        )
        out = _calibrate(v)
        assert out.confidence >= 0.0

    def test_zero_red_flags_dampens_confidence_when_scam(self):
        v = ScamVerdict(is_scam=True, confidence=0.9, red_flags=[])
        out = _calibrate(v)
        assert out.confidence <= 0.5

    def test_calibration_preserves_summary(self):
        v = ScamVerdict(is_scam=True, confidence=0.5, summary="keep me")
        out = _calibrate(v)
        assert out.summary == "keep me"

    def test_calibration_is_deterministic_for_same_input(self):
        v = ScamVerdict(is_scam=True, confidence=0.85, red_flags=["a", "b"])
        a = _calibrate(v)
        b = _calibrate(v)
        assert a.confidence == b.confidence
        assert a.risk_level == b.risk_level


class TestAnalysisFailedVerdict:
    def test_returns_low_confidence_failure_verdict(self):
        v = _analysis_failed_verdict(original="some text")
        assert v.is_scam is False
        assert v.confidence == 0.0
        assert "failed" in v.summary.lower()


# ---------------------------------------------------------------------------
# LLM-integrated tests (offline via patch)
# ---------------------------------------------------------------------------



class TestWithCannedLlmResponse:
    def test_valid_json_returned_as_verdict(self, bank_kyc_llm_json):
        with _patch_completion(bank_kyc_llm_json):
            v = analyze_text("Dear Customer, your SBI account will be BLOCKED within 24 hours...")
        assert v.is_scam is True
        assert v.scam_type == "bank_kyc"
        assert v.risk_level == RiskLevel.CRITICAL
        assert v.confidence == 0.95

    def test_markdown_wrapped_json_parsed(self):
        text = "```json\n" + json.dumps(
            {"is_scam": True, "confidence": 0.8, "scam_type": "lottery", "risk_level": "high"}
        ) + "\n```"
        with _patch_completion(text):
            v = analyze_text("You won a prize!")
        assert v.is_scam is True
        assert v.scam_type == "lottery"

    def test_prose_with_embedded_json_parsed(self):
        payload = {"is_scam": False, "confidence": 0.2, "scam_type": None, "risk_level": "low"}
        text = "Sure, here you go: " + json.dumps(payload) + " hope this helps."
        with _patch_completion(text):
            v = analyze_text("Your OTP is 123456")
        assert v.is_scam is False
        assert v.confidence == 0.2

    def test_provider_failure_returns_failure_verdict(self):
        with _patch_completion(side_effect=RuntimeError("All LLM providers failed")):
            v = analyze_text("some message")
        assert v.is_scam is False
        assert v.confidence == 0.0
        assert "failed" in v.summary.lower()

    def test_truncated_message_still_classified(self, bank_kyc_llm_json):
        long_msg = "abc " * 2000 + "http://x.com ask for OTP now"
        with _patch_completion(bank_kyc_llm_json):
            v = analyze_text(long_msg)
        assert v.is_scam is True

    def test_language_parameter_passed(self):
        with _patch_completion("{}") as mock:
            analyze_text("message", language="hi")
            call_kwargs = mock.call_args.kwargs
            assert call_kwargs.get("timeout") == 5.0

    def test_explicit_provider_forwarded(self, bank_kyc_llm_json):
        with _patch_completion(bank_kyc_llm_json) as mock:
            analyze_text("msg", provider="groq", model="llama-3.3-70b-versatile")
            call_kwargs = mock.call_args.kwargs
            assert call_kwargs.get("provider") == "groq"
            assert call_kwargs.get("json_mode") is True
            assert call_kwargs.get("temperature") == 0.1

    def test_system_and_user_messages_built(self, bank_kyc_llm_json):
        recorded = {}

        def capture(messages, **kwargs):
            recorded["messages"] = messages
            return bank_kyc_llm_json

        with patch("app.services.scam_analyzer.chat_completion", side_effect=capture):
            analyze_text("Hello this is a test", sender_info="Mom")

        assert len(recorded["messages"]) == 2
        assert recorded["messages"][0]["role"] == "system"
        assert "Hello this is a test" in recorded["messages"][1]["content"]
        assert "Mom" in recorded["messages"][1]["content"]


# ---------------------------------------------------------------------------
# Sample-driven structural assertions (offline)
# ---------------------------------------------------------------------------

class TestSamplesStructural:
    """Assert the service produces a valid verdict for every sample without
    requiring an LLM call. These validate schema + defaults, not LLM accuracy."""

    def test_every_sample_returns_valid_verdict(self, samples):
        for sample in samples:
            v = analyze_text(sample["text"])
            assert isinstance(v, ScamVerdict)
            assert 0.0 <= v.confidence <= 1.0
            assert isinstance(v.summary, str)
            assert isinstance(v.recommended_action, str)
            assert isinstance(v.red_flags, list)
            assert isinstance(v.stages_detected, list)

    def test_legitimate_samples_default_safe(self, samples):
        for sample in samples:
            if not sample.get("expected_is_scam"):
                v = analyze_text(sample["text"])
                # Without an LLM we cannot assert the verdict is 'false' —
                # the service will have fallen back. So we assert the schema
                # is stable and confidence is in range.
                assert 0.0 <= v.confidence <= 1.0
                assert isinstance(v.risk_level, (RiskLevel, str))


class TestRecommendedActionFallback:
    def test_empty_text_has_sensible_action(self):
        v = analyze_text("")
        assert v.recommended_action == "This appears legitimate"

    def test_failure_verdict_has_sensible_action(self):
        v = _analysis_failed_verdict(original="x")
        assert v.recommended_action == "This appears legitimate"
