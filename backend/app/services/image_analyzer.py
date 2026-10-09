"""Image / screenshot analyzer (Phase 1.3).

Flow:
  1. Validate image (format + size)
  2. OCR (local engine first, Gemini Vision fallback)
  3. Pipeline OCR text → text classifier (1.1) + URL analyzer (1.2)
  4. Visual analysis (Gemini Vision, only if configured)
  5. Merge into ImageAnalysisVerdict

Run:  uv run pytest backend/tests/test_image_analyzer.py -q
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from app.models.schemas import Evidence, EvidenceType, RiskLevel, ScamVerdict
from app.services.ocr_engine import OCRResult, ocr_image
from app.services.scam_analyzer import analyze_text
from app.services.url_analyzer import analyze_text_for_urls
from app.services.visual_analyzer import VisualAnalysis, analyze_visual


@dataclass
class ImageAnalysisVerdict:
    """Unified verdict for image/screenshot analysis."""

    verdict: ScamVerdict
    ocr_text: str = ""
    ocr_engine: str = "none"
    visual_analysis: Optional[VisualAnalysis] = None
    visual_red_flags_added: list[str] = field(default_factory=list)
    confidence_boost: float = 0.0
    processing_time_ms: float = 0.0
    image_metadata: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def analyze_image(source, mime_hint: Optional[str] = None) -> ImageAnalysisVerdict:
    """Analyze a screenshot/image for scam indicators.

    `source` can be:
      - A file path (str / Path)
      - A file-like object / UploadFile with .read()
      - Raw bytes

    Returns an ImageAnalysisVerdict. When OCR or visual analysis is
    unavailable, the verdict is built from whatever signals are present.
    """
    t0 = time.perf_counter()

    # Step 1: OCR (handles validation internally)
    ocr_result: OCRResult = ocr_image(source, mime_hint)
    ocr_text = ocr_result.text

    # Re-read data for visual analysis if needed
    if isinstance(source, bytes):
        data = source
        mime = mime_hint or "image/png"
    elif isinstance(source, str):
        p = Path(source)
        data = p.read_bytes()
        mime = mime_hint or p.suffix.lower() or "image/png"
    elif hasattr(source, "read"):
        data = source.read()
        mime = mime_hint or "image/png"
    else:
        data = b""
        mime = mime_hint or "image/png"

    # Step 3: pipeline OCR text → text classifier + URL analyzer
    text_verdict = _pipeline_text(ocr_text) if ocr_text else _empty_text_verdict()
    url_output = analyze_text_for_urls(ocr_text) if ocr_text else None

    # Step 4: visual analysis (only if Gemini configured)
    visual = analyze_visual(data, mime) if _gemini_configured() else VisualAnalysis()

    # Step 5: merge
    verdict, boost, visual_flags = _merge(
        text_verdict=text_verdict,
        url_output=url_output,
        visual=visual,
        ocr_text=ocr_text,
    )

    processing_ms = (time.perf_counter() - t0) * 1000

    return ImageAnalysisVerdict(
        verdict=verdict,
        ocr_text=ocr_text,
        ocr_engine=ocr_result.engine,
        visual_analysis=visual if visual.engine != "none" else None,
        visual_red_flags_added=visual_flags,
        confidence_boost=boost,
        processing_time_ms=round(processing_ms, 1),
        image_metadata={
            "mime": mime,
            "size_bytes": len(data),
            "ocr_engine": ocr_result.engine,
            "visual_engine": visual.engine,
        },
    )


# ---------------------------------------------------------------------------
# Pipeline helpers
# ---------------------------------------------------------------------------


def _pipeline_text(text: str) -> ScamVerdict:
    """Feed OCR text to the text scam classifier."""
    return analyze_text(text)


def _empty_text_verdict() -> ScamVerdict:
    return ScamVerdict(
        is_scam=False,
        confidence=0.0,
        summary="No text content found in image",
        recommended_action="This appears legitimate",
        risk_level=RiskLevel.LOW,
    )


def _gemini_configured() -> bool:
    try:
        from app.config import settings
        return bool(settings.gemini_api_key)
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Merge logic
# ---------------------------------------------------------------------------


def _merge(
    text_verdict: ScamVerdict,
    url_output,
    visual: VisualAnalysis,
    ocr_text: str,
) -> tuple[ScamVerdict, float, list[str]]:
    """Merge text verdict + URL results + visual analysis into one verdict."""
    # Dedup incoming text red flags first
    seen: set[str] = set()
    red_flags: list[str] = []
    for f in text_verdict.red_flags:
        if f not in seen:
            seen.add(f)
            red_flags.append(f)
    evidence = list(text_verdict.evidence)
    confidence = text_verdict.confidence
    is_scam = text_verdict.is_scam
    boost = 0.0
    visual_flags: list[str] = []

    # --- URL signals ---
    if url_output and url_output.urls_analyzed:
        highest = max(url_output.urls_analyzed, key=lambda u: u.risk_score)
        if highest.risk_score > 0:
            red_flags.append(
                f"Domain {highest.domain} analyzed: "
                f"{'suspicious' if highest.is_suspicious else 'not flagged'} "
                f"(risk {highest.risk_score:.2f})"
            )
            if highest.is_suspicious:
                evidence.append(
                    Evidence(
                        type=EvidenceType.URL_ANALYSIS,
                        detail=f"URL {highest.url} → {highest.domain} "
                        f"(risk {highest.risk_score:.2f})",
                        severity=RiskLevel.HIGH if highest.risk_score >= 0.5 else RiskLevel.MEDIUM,
                    )
                )
                # Boost confidence when URL confirms text verdict
                if is_scam and highest.risk_score >= 0.5:
                    boost += 0.10

    # --- Visual analysis signals ---
    if visual.engine != "none" and visual.visual_red_flags:
        for flag in visual.visual_red_flags:
            if flag not in red_flags:
                red_flags.append(flag)
                visual_flags.append(flag)
        if not visual.looks_legitimate and is_scam:
            # Multiple modalities agree → boost
            boost += 0.10
        elif not visual.looks_legitimate and not is_scam:
            # Visual says fake but text says legit → raise suspicion
            confidence = min(1.0, confidence + 0.15)
            is_scam = confidence >= 0.5

    # QR code detection (heuristic from OCR text)
    if _contains_qr_indication(ocr_text):
        flag = "Image contains a QR code indication — never scan QR codes to RECEIVE money"
        if flag not in red_flags:
            red_flags.append(flag)
            visual_flags.append(flag)

    # Blurry / low quality heuristic
    if _looks_low_quality(ocr_text):
        flag = "Image quality too low for full analysis"
        if flag not in red_flags:
            red_flags.append(flag)

    # If no text was extracted at all
    if not ocr_text.strip():
        return _no_text_verdict(red_flags, evidence), boost, visual_flags

    # Rebuild verdict with merged signals
    new_confidence = max(0.0, min(1.0, confidence + boost))
    risk_level = _risk_from_confidence(new_confidence, is_scam)

    return ScamVerdict(
        is_scam=is_scam,
        confidence=round(new_confidence, 3),
        scam_type=text_verdict.scam_type,
        risk_level=risk_level,
        red_flags=red_flags[:10],
        evidence=evidence,
        stages_detected=text_verdict.stages_detected,
        summary=text_verdict.summary or _summary_from_parts(is_scam, new_confidence, visual),
        recommended_action=text_verdict.recommended_action or _recommended_action(risk_level),
    ), boost, visual_flags


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------


def _risk_from_confidence(confidence: float, is_scam: bool) -> RiskLevel:
    if not is_scam:
        if confidence <= 0.5:
            return RiskLevel.LOW
        if confidence <= 0.7:
            return RiskLevel.MEDIUM
        return RiskLevel.HIGH
    if confidence <= 0.5:
        return RiskLevel.MEDIUM
    if confidence <= 0.7:
        return RiskLevel.HIGH
    return RiskLevel.CRITICAL


def _summary_from_parts(is_scam: bool, confidence: float, visual: VisualAnalysis) -> str:
    pct = round(confidence * 100)
    if is_scam:
        parts = [f"🚨 This is a scam ({pct}% confidence)."]
        if visual.engine != "none":
            parts.append(f"Visual analysis: {visual.app_identified} app detected.")
        if visual.visual_red_flags:
            parts.append(f"Visual red flags: {'; '.join(visual.visual_red_flags[:3])}.")
        return " ".join(parts)
    return f"✅ This appears legitimate ({pct}% confidence)."


def _recommended_action(risk_level: RiskLevel) -> str:
    mapping = {
        RiskLevel.LOW: "This appears legitimate",
        RiskLevel.MEDIUM: "Proceed with caution. Verify through official channels.",
        RiskLevel.HIGH: "Do NOT click any links or share personal information. Block the sender.",
        RiskLevel.CRITICAL: "🚨 HANG UP / DELETE IMMEDIATELY. Report to 1930 helpline.",
    }
    return mapping.get(risk_level, "This appears legitimate")


def _no_text_verdict(red_flags: list[str], evidence: list[Evidence]) -> ScamVerdict:
    return ScamVerdict(
        is_scam=False,
        confidence=0.0,
        summary="No text content found in image",
        recommended_action="This appears legitimate",
        risk_level=RiskLevel.LOW,
        red_flags=red_flags,
        evidence=evidence,
    )


def _contains_qr_indication(text: str) -> bool:
    lower = text.lower()
    return any(kw in lower for kw in ["qr code", "qr code", "scan the qr", "scan this qr"])


def _looks_low_quality(text: str) -> bool:
    # Very short OCR output from a supposedly text-heavy screenshot may indicate
    # poor image quality or a non-text image.
    return len(text.strip()) < 10
