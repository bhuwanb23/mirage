"""Audio / voice note analyzer (Phase 1.4).

Flow:
  1. Validate audio (format, size, duration)
  2. Transcribe via Groq Whisper (verbose_json for segments)
  3. Feed transcript to text scam classifier (Phase 1.1)
  4. Synthetic voice detection via Resemblyzer (voice embedding + variance heuristic)
  5. Merge into VoiceAnalysisVerdict

Run:  uv run pytest backend/tests/test_voice_analyzer.py -q
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Optional

from app.clients.groq_client import is_configured as groq_configured
from app.clients.groq_client import transcribe_audio_with_segments
from app.clients.resemblyzer_client import (
    embed_wav,
)
from app.clients.resemblyzer_client import (
    is_available as resemblyzer_available,
)
from app.models.schemas import Evidence, EvidenceType, RiskLevel, ScamVerdict
from app.services.scam_analyzer import analyze_text
from app.services.voice_validator import validate_and_read_audio


@dataclass
class VoiceAnalysisVerdict:
    """Unified verdict for audio/voice analysis."""

    verdict: ScamVerdict
    transcript: str = ""
    transcript_segments: list[dict[str, Any]] = field(default_factory=list)
    detected_language: str = ""
    synthetic_voice_score: float = 0.0
    voice_verdict: str = "unknown"  # unknown | likely_human | likely_ai_generated | no_reference
    audio_duration_seconds: float = 0.0
    confidence_boost: float = 0.0
    processing_time_ms: float = 0.0
    audio_metadata: dict[str, Any] = field(default_factory=dict)
    voice_model_available: bool = False
    whisper_available: bool = False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def analyze_voice(source, language: Optional[str] = None) -> VoiceAnalysisVerdict:
    """Analyze an audio file for scam content and synthetic voice.

    `source` can be:
      - A file path (str / Path)
      - A file-like object / UploadFile with .read()
      - Raw bytes

    Returns a VoiceAnalysisVerdict. When Whisper or Resemblyzer is unavailable,
    the verdict is built from whatever signals are present.
    """
    t0 = time.perf_counter()

    # Step 1: validate
    data, mime, duration = validate_and_read_audio(source)

    # Write to temp file for clients that need a file path
    temp_path = _write_temp(data, mime)

    try:
        # Step 2: transcribe
        whisper_ok = groq_configured()
        if whisper_ok:
            transcript, segments = transcribe_audio_with_segments(temp_path, language)
        else:
            transcript, segments = _no_transcription()

        # Step 3: classify transcript
        if transcript.strip():
            text_verdict = analyze_text(transcript, sender_info=None)
        else:
            text_verdict = _no_speech_verdict()

        # Step 4: synthetic voice detection
        voice_score, voice_verdict, voice_model_ok = _synthetic_voice_analysis(temp_path, duration)

        # Step 5: merge
        verdict, boost = _merge(text_verdict, voice_score, voice_verdict, transcript)

        processing_ms = (time.perf_counter() - t0) * 1000

        # Detect language from segments if available
        detected_lang = _detect_language(segments, transcript)

        return VoiceAnalysisVerdict(
            verdict=verdict,
            transcript=transcript,
            transcript_segments=segments,
            detected_language=detected_lang,
            synthetic_voice_score=voice_score,
            voice_verdict=voice_verdict,
            audio_duration_seconds=duration,
            confidence_boost=boost,
            processing_time_ms=round(processing_ms, 1),
            audio_metadata={
                "mime": mime,
                "size_bytes": len(data),
                "whisper_available": whisper_ok,
                "voice_model_available": voice_model_ok,
            },
            voice_model_available=voice_model_ok,
            whisper_available=whisper_ok,
        )
    finally:
        _cleanup_temp(temp_path)


# ---------------------------------------------------------------------------
# Synthetic voice analysis
# ---------------------------------------------------------------------------


def _synthetic_voice_analysis(file_path: str, duration: float) -> tuple[float, str, bool]:
    """Run Resemblyzer synthetic voice detection.

    Returns (score 0..1, verdict, model_available).
    """
    if not resemblyzer_available():
        return 0.0, "unknown", False

    if duration < 2.0:
        # Too short for meaningful voice analysis
        return 0.0, "unknown", True

    try:
        embedding = embed_wav(file_path)
        if embedding is None:
            return 0.0, "unknown", True

        # Heuristic: split into segments, compute variance
        # For a single embedding, we use a simplified approach:
        # - If we can't get multiple segments, use a default score based on
        #   the embedding's "smoothness" heuristic
        score = _voice_variance_score(embedding, duration)
        if score > 0.6:
            verdict = "likely_ai_generated"
        elif score < 0.3:
            verdict = "likely_human"
        else:
            verdict = "uncertain"
        return score, verdict, True
    except Exception:
        return 0.0, "unknown", True


def _voice_variance_score(embedding: list[float], duration: float) -> float:
    """Estimate synthetic voice probability from embedding variance.

    Resemblyzer embeddings of AI voices tend to be "too consistent" —
    lower variance across the embedding dimensions. This is a rough
    heuristic: compute the variance of the embedding values and map to
    a 0..1 score where higher = more likely AI.
    """
    import statistics

    if len(embedding) < 10:
        return 0.5

    values = embedding
    variance = statistics.variance(values) if len(values) > 1 else 0.0

    # Normalize: typical human voice embeddings have variance in a certain range.
    # This is a rough heuristic — real thresholds would need calibration data.
    # Lower variance → higher AI probability.
    # Map variance to 0..1 where 0 variance = 1.0 (definitely AI)
    # and high variance = 0.0 (definitely human).
    if variance <= 0.0:
        return 0.8  # no variance = suspicious

    # Rough mapping: variance around 1e-5 to 1e-4 is typical for human voices
    # We invert: low variance → high AI score
    normalized = max(0.0, min(1.0, 1.0 - (variance * 10_000)))
    return round(normalized, 3)


# ---------------------------------------------------------------------------
# Merge logic
# ---------------------------------------------------------------------------


def _merge(
    text_verdict: ScamVerdict,
    synthetic_score: float,
    voice_verdict: str,
    transcript: str,
) -> tuple[ScamVerdict, float]:
    """Merge text verdict with synthetic voice score.

    Rules (from spec):
      - text says scam AND voice synthetic → boost to 0.95+
      - text says scam BUT voice human → keep text confidence
      - text says legitimate BUT voice synthetic → flag suspicious
    """
    confidence = text_verdict.confidence
    is_scam = text_verdict.is_scam
    boost = 0.0
    new_red_flags = list(text_verdict.red_flags)
    new_evidence = list(text_verdict.evidence)

    if voice_verdict == "likely_ai_generated":
        # Add voice evidence
        new_evidence.append(
            Evidence(
                type=EvidenceType.VOICE_SYNTHETIC,
                detail=f"Voice analysis: {synthetic_score:.0%} probability of AI-generated voice",
                severity=RiskLevel.HIGH if synthetic_score >= 0.6 else RiskLevel.MEDIUM,
            )
        )

        if is_scam:
            # Double confirmation → boost
            new_confidence = max(confidence, 0.95)
            boost = new_confidence - confidence
            confidence = new_confidence
        else:
            # Legit text + synthetic voice → suspicious
            confidence = min(1.0, confidence + 0.20)
            is_scam = confidence >= 0.5
            flag = "AI-synthesized voice detected — be cautious even if message sounds legitimate"
            if flag not in new_red_flags:
                new_red_flags.append(flag)

    elif voice_verdict == "likely_human":
        # Human voice, no boost needed; add evidence
        new_evidence.append(
            Evidence(
                type=EvidenceType.VOICE_SYNTHETIC,
                detail="Voice analysis: voice appears to be human (not AI-synthesized)",
                severity=RiskLevel.LOW,
            )
        )

    # Clamp
    confidence = max(0.0, min(1.0, confidence))

    risk_level = _risk_from_confidence(confidence, is_scam)

    return ScamVerdict(
        is_scam=is_scam,
        confidence=round(confidence, 3),
        scam_type=text_verdict.scam_type,
        risk_level=risk_level,
        red_flags=new_red_flags[:10],
        evidence=new_evidence,
        stages_detected=text_verdict.stages_detected,
        summary=text_verdict.summary or _summary(text_verdict.is_scam, confidence, voice_verdict),
        recommended_action=text_verdict.recommended_action or _recommended_action(risk_level),
    ), boost


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _no_transcription() -> tuple[str, list[dict[str, Any]]]:
    return "No speech detected in audio", []


def _no_speech_verdict() -> ScamVerdict:
    return ScamVerdict(
        is_scam=False,
        confidence=0.0,
        summary="No speech detected in audio",
        recommended_action="This appears legitimate",
        risk_level=RiskLevel.LOW,
    )


def _detect_language(segments: list[dict[str, Any]], transcript: str) -> str:
    """Best-effort language detection from transcript content."""
    if not transcript:
        return ""

    # Check for Devanagari script (Hindi, Marathi, etc.)
    devanagari = any("\u0900" <= c <= "\u097F" for c in transcript)
    if devanagari:
        return "hi"

    # Check for Tamil script
    tamil = any("\u0B80" <= c <= "\u0BFF" for c in transcript)
    if tamil:
        return "ta"

    # Check for Cyrillic (Russian, etc.)
    cyrillic = any("\u0400" <= c <= "\u04FF" for c in transcript)
    if cyrillic:
        return "ru"

    return "en"


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


def _summary(is_scam: bool, confidence: float, voice_verdict: str) -> str:
    pct = round(confidence * 100)
    if is_scam:
        parts = [f"🚨 This is a scam ({pct}% confidence)."]
        if voice_verdict == "likely_ai_generated":
            parts.append("AI-synthesized voice detected.")
        elif voice_verdict == "likely_human":
            parts.append("Voice appears human — could be a real scammer.")
        return " ".join(parts)
    if voice_verdict == "likely_ai_generated":
        return (
            f"✅ Message sounds legitimate ({pct}% confidence), "
            f"but AI-synthesized voice detected — be cautious."
        )
    return f"✅ This appears legitimate ({pct}% confidence)."


def _recommended_action(risk_level: RiskLevel) -> str:
    mapping = {
        RiskLevel.LOW: "This appears legitimate",
        RiskLevel.MEDIUM: "Proceed with caution. Verify through official channels.",
        RiskLevel.HIGH: "Do NOT share any OTP or personal information. Block the sender.",
        RiskLevel.CRITICAL: (
            "🚨 HANG UP IMMEDIATELY. Do NOT share any OTP. Report to 1930 helpline."
        ),
    }
    return mapping.get(risk_level, "This appears legitimate")


def _write_temp(data: bytes, mime: str) -> str:
    """Write audio bytes to a temp file. Returns the path."""
    import tempfile

    suffix = ".wav"
    if mime.startswith("audio/ogg"):
        suffix = ".ogg"
    elif mime.startswith("audio/mpeg"):
        suffix = ".mp3"
    elif mime.startswith("audio/mp4"):
        suffix = ".m4a"
    elif mime.startswith("audio/webm"):
        suffix = ".webm"
    elif mime.startswith("audio/flac"):
        suffix = ".flac"

    fd = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    fd.write(data)
    fd.close()
    return fd.name


def _cleanup_temp(path: str) -> None:
    """Remove temp file."""
    import os
    try:
        os.unlink(path)
    except OSError:
        pass
