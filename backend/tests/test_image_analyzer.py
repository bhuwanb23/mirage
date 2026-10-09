"""Tests for the image / screenshot analyzer (Phase 1.3).

Offline tests: image validation, OCR engine interface, merge logic,
schema, edge cases. Gemini-dependent tests are skipped when
GEMINI_API_KEY is not set.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.models.schemas import RiskLevel, ScamVerdict
from app.services.image_analyzer import (
    ImageAnalysisVerdict,
    _contains_qr_indication,
    _looks_low_quality,
    _merge,
    _recommended_action,
    _risk_from_confidence,
    _summary_from_parts,
    analyze_image,
)
from app.services.image_validator import validate_and_read_image
from app.services.ocr_engine import OCRResult, ocr_image
from app.services.visual_analyzer import VisualAnalysis, analyze_visual

# Minimal valid image bytes for offline tests
PNG_1X1 = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
    b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00"
    b"\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05"
    b"\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
)
JPEG_MAGIC = (
    b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
    b"\xff\xdb\x00C\x00\x08\x00\x01\x00\x01\x01\x01\x11\x00"
)
WEBP_MAGIC = b"RIFF\x00\x00\x00\x00WEBP\x00\x00\x00\x00\x10\x00\x00\x00\x85VP8\x00\x00\x00\x00"

# ---------------------------------------------------------------------------
# Image validation
# ---------------------------------------------------------------------------

class TestImageValidation:
    def test_valid_png_bytes(self, tmp_path):
        # Create a minimal valid PNG (1x1 red pixel)
        data, mime = validate_and_read_image(PNG_1X1)
        assert len(data) > 0
        assert mime == "image/png"

    def test_jpeg_magic_bytes(self):
        data, mime = validate_and_read_image(JPEG_MAGIC)
        assert mime == "image/jpeg"

    def test_webp_magic_bytes(self):
        data, mime = validate_and_read_image(WEBP_MAGIC)
        assert mime == "image/webp"

    def test_unsupported_suffix(self, tmp_path):
        path = tmp_path / "test.xyz"
        path.write_bytes(b"not an image")
        with pytest.raises(ValueError, match="Unsupported image format"):
            validate_and_read_image(path)

    def test_empty_data(self):
        with pytest.raises(ValueError, match="Image is empty"):
            validate_and_read_image(b"")

    def test_file_too_large(self, tmp_path):
        path = tmp_path / "large.png"
        path.write_bytes(b"x" * (5 * 1024 * 1024 + 1))
        with pytest.raises(ValueError, match="too large"):
            validate_and_read_image(path)


# ---------------------------------------------------------------------------
# OCR engine interface
# ---------------------------------------------------------------------------

class TestOCREngineInterface:
    def test_no_engine_returns_empty(self):
        result = ocr_image(PNG_1X1)
        assert isinstance(result, OCRResult)
        assert result.engine == "none"
        assert result.text == ""

    def test_ocr_result_schema(self):
        r = OCRResult(text="Hello world", engine="rapidocr", model="local")
        assert r.text == "Hello world"
        assert r.engine == "rapidocr"
        assert r.model == "local"


# ---------------------------------------------------------------------------
# Visual analysis
# ---------------------------------------------------------------------------

class TestVisualAnalysis:
    def test_neutral_result_when_no_gemini(self):
        # Should return neutral result without Gemini
        visual = analyze_visual(PNG_1X1)
        assert isinstance(visual, VisualAnalysis)
        assert visual.app_identified == "Unknown"
        assert visual.looks_legitimate is True


# ---------------------------------------------------------------------------
# Merge logic
# ---------------------------------------------------------------------------

class TestMergeLogic:
    def test_merge_text_only(self):
        verdict = ScamVerdict(
            is_scam=True,
            confidence=0.85,
            scam_type="bank_kyc",
            risk_level=RiskLevel.CRITICAL,
            red_flags=["asks for OTP", "suspicious domain"],
            summary="This is a scam",
            recommended_action="Do NOT click any links",
        )
        merged, boost, visual_flags = _merge(
            text_verdict=verdict,
            url_output=None,
            visual=VisualAnalysis(),
            ocr_text="Some text",
        )
        assert merged.is_scam is True
        assert boost == 0.0
        assert visual_flags == []

    def test_merge_url_confirms_scam(self):
        from app.models.schemas import URLAnalysisOutput, URLAnalysisResult
        url_out = URLAnalysisOutput(
            urls_analyzed=[
                URLAnalysisResult(
                    url="http://sbi-kyc-verify.xyz",
                    domain="sbi-kyc-verify.xyz",
                    tld=".xyz",
                    is_suspicious=True,
                    risk_score=0.75,
                )
            ]
        )
        verdict = ScamVerdict(is_scam=True, confidence=0.8, summary="Scam")
        merged, boost, _ = _merge(
            text_verdict=verdict,
            url_output=url_out,
            visual=VisualAnalysis(),
            ocr_text="text",
        )
        assert boost >= 0.10
        assert merged.confidence >= 0.90

    def test_merge_visual_says_fake_scam(self):
        visual = VisualAnalysis(
            app_identified="WhatsApp",
            visual_red_flags=["blurred logo"],
            looks_legitimate=False,
            confidence=0.9,
            engine="gemini",
        )
        verdict = ScamVerdict(is_scam=True, confidence=0.85, summary="Scam")
        merged, boost, visual_flags = _merge(
            text_verdict=verdict,
            url_output=None,
            visual=visual,
            ocr_text="scam message",
        )
        assert boost >= 0.10
        assert "blurred logo" in visual_flags

    def test_merge_visual_fake_but_text_legit(self):
        visual = VisualAnalysis(
            app_identified="Unknown",
            visual_red_flags=["inconsistent fonts"],
            looks_legitimate=False,
            confidence=0.8,
            engine="gemini",
        )
        verdict = ScamVerdict(is_scam=False, confidence=0.2, summary="legit")
        merged, _, _ = _merge(
            text_verdict=verdict,
            url_output=None,
            visual=visual,
            ocr_text="something",
        )
        # Visual says fake, text says legit → raise suspicion
        assert merged.confidence > 0.2

    def test_merge_no_text_returns_no_text_verdict(self):
        merged, _, _ = _merge(
            text_verdict=ScamVerdict(is_scam=False, confidence=0.0),
            url_output=None,
            visual=VisualAnalysis(),
            ocr_text="",
        )
        assert merged.summary == "No text content found in image"
        assert merged.confidence == 0.0

    def test_merge_deduplicates_red_flags(self):
        verdict = ScamVerdict(
            is_scam=True,
            confidence=0.8,
            red_flags=["duplicate", "duplicate", "other"],
        )
        merged, _, _ = _merge(
            text_verdict=verdict,
            url_output=None,
            visual=VisualAnalysis(visual_red_flags=["duplicate"], engine="gemini"),
            ocr_text="text",
        )
        assert merged.red_flags.count("duplicate") == 1

    def test_merge_caps_red_flags_at_10(self):
        verdict = ScamVerdict(
            is_scam=True,
            confidence=0.8,
            red_flags=[f"flag-{i}" for i in range(15)],
        )
        merged, _, _ = _merge(
            text_verdict=verdict,
            url_output=None,
            visual=VisualAnalysis(visual_red_flags=[f"v-{i}" for i in range(5)]),
            ocr_text="text",
        )
        assert len(merged.red_flags) <= 10


# ---------------------------------------------------------------------------
# Risk mapping
# ---------------------------------------------------------------------------

class TestRiskMapping:
    def test_low_confidence_legit(self):
        assert _risk_from_confidence(0.1, False) == RiskLevel.LOW
        assert _risk_from_confidence(0.4, False) == RiskLevel.LOW

    def test_medium_confidence_legit(self):
        assert _risk_from_confidence(0.6, False) == RiskLevel.MEDIUM

    def test_scam_bands(self):
        assert _risk_from_confidence(0.4, True) == RiskLevel.MEDIUM
        assert _risk_from_confidence(0.6, True) == RiskLevel.HIGH
        assert _risk_from_confidence(0.9, True) == RiskLevel.CRITICAL


# ---------------------------------------------------------------------------
# Summary + recommended action
# ---------------------------------------------------------------------------

class TestSummaryAndAction:
    def test_summary_scam_with_visual(self):
        visual = VisualAnalysis(app_identified="WhatsApp", looks_legitimate=False, engine="gemini")
        s = _summary_from_parts(True, 0.92, visual)
        assert "92%" in s
        assert "scam" in s.lower()
        assert "WhatsApp" in s

    def test_summary_legit(self):
        s = _summary_from_parts(False, 0.15, VisualAnalysis())
        assert "15%" in s
        assert "legitimate" in s.lower()

    def test_recommended_action_mapping(self):
        assert _recommended_action(RiskLevel.LOW) == "This appears legitimate"
        assert _recommended_action(RiskLevel.MEDIUM) == (
            "Proceed with caution. Verify through official channels."
        )
        assert "block" in _recommended_action(RiskLevel.HIGH).lower()
        assert "1930" in _recommended_action(RiskLevel.CRITICAL)


# ---------------------------------------------------------------------------
# QR + quality heuristics
# ---------------------------------------------------------------------------

class TestHeuristics:
    def test_qr_indication(self):
        assert _contains_qr_indication("scan the qr code") is True
        assert _contains_qr_indication("normal message") is False

    def test_low_quality_short_text(self):
        assert _looks_low_quality("") is True
        assert _looks_low_quality("hi") is True
        assert _looks_low_quality("a" * 100) is False


# ---------------------------------------------------------------------------
# Full analyzer integration (offline)
# ---------------------------------------------------------------------------

class TestFullAnalyzerOffline:
    def test_analyzer_returns_valid_verdict(self):
        result = analyze_image(PNG_1X1)
        assert isinstance(result, ImageAnalysisVerdict)
        assert isinstance(result.verdict, ScamVerdict)
        assert 0.0 <= result.verdict.confidence <= 1.0
        assert result.ocr_engine == "none"  # no OCR installed
        assert result.processing_time_ms >= 0

    def test_analyzer_with_ocr_mocked(self):
        with patch("app.services.image_analyzer.ocr_image", return_value=OCRResult(
            text="Your SBI account will be blocked within 24 hours",
            engine="rapidocr",
            model="local",
        )):
            result = analyze_image(PNG_1X1)
            assert result.ocr_engine == "rapidocr"
            assert "blocked" in result.ocr_text
            assert result.verdict.summary  # non-empty

    def test_analyzer_schema_valid(self):
        result = analyze_image(PNG_1X1)
        assert isinstance(result.verdict, ScamVerdict)
        assert isinstance(result.ocr_text, str)
        assert isinstance(result.processing_time_ms, float)
        assert isinstance(result.image_metadata, dict)
