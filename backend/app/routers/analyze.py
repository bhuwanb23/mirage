"""Analyze router — Phase 1.1 text endpoint.

Endpoints:
  POST /analyze/text  -> AnalyzeResponse { verdict: ScamVerdict, ... }

Run:  uv run uvicorn app.main:app --reload --port 8000
Test: curl -X POST http://localhost:8000/analyze/text \
       -H 'Content-Type: application/json' \
       -d '{"text": "Your SBI account will be blocked in 24 hours..."}'
"""

from __future__ import annotations

import time

from fastapi import APIRouter, Body, File, HTTPException, UploadFile

from app.models.schemas import (
    AnalyzeRequest,
    AnalyzeResponse,
    ImageAnalysisVerdict,
    URLAnalysisOutput,
    VoiceAnalysisVerdict,
)
from app.services.image_analyzer import analyze_image
from app.services.scam_analyzer import analyze_text
from app.services.url_analyzer import analyze_text_for_urls
from app.services.voice_analyzer import analyze_voice

router = APIRouter(tags=["analyze"])


def _metadata(
    input_type: str,
    processing_ms: float,
    language: str,
    provider_used: str | None,
    analyzers: list[str],
) -> dict:
    return {
        "input_type": input_type,
        "analyzers_used": analyzers,
        "processing_time_ms": round(processing_ms, 1),
        "language_detected": language,
        "provider_used": provider_used,
    }


@router.post("/text", response_model=AnalyzeResponse, status_code=200)
async def analyze_text_endpoint(
    body: AnalyzeRequest = Body(...),
) -> AnalyzeResponse:
    """Classify a text message as scam or legitimate.

    At least one of `text` or `url` should be provided; if both are empty the
    endpoint returns a low-confidence "no content" verdict rather than 400,
    because the bot forwards messages that may only become available later.
    """
    t0 = time.perf_counter()

    text = body.text
    if not text or not text.strip():
        verdict = analyze_text("")
        processing_ms = (time.perf_counter() - t0) * 1000
        return AnalyzeResponse(
            verdict=verdict,
            analysis_metadata=_metadata(
                "text", processing_ms, body.input_type or "en", None,
                ["text_classifier"],
            ),
        )

    provider_used: str | None = None
    try:
        verdict = analyze_text(
            message_text=text,
            sender_info=None,
            language=body.input_type or "en",
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Analysis unavailable: {exc}") from exc

    processing_ms = (time.perf_counter() - t0) * 1000
    return AnalyzeResponse(
        verdict=verdict,
        analysis_metadata=_metadata(
            "text", processing_ms, body.input_type or "en",
            provider_used, ["text_classifier"],
        ),
    )


@router.post("/url", response_model=URLAnalysisOutput, status_code=200)
async def analyze_url_endpoint(
    body: AnalyzeRequest = Body(...),
) -> URLAnalysisOutput:
    """Extract URLs from text and analyze each domain.

    Accepts plain text / a single URL in the `text` field. When `url` is set,
    it is analyzed directly. Returns per-URL results plus an overall risk
    summary.
    """
    text = body.url or body.text or ""
    output = analyze_text_for_urls(text)
    return output


@router.post("/image", response_model=ImageAnalysisVerdict, status_code=200)
async def analyze_image_endpoint(
    file: UploadFile = File(...),
) -> ImageAnalysisVerdict:
    """Analyze an uploaded screenshot/image for scam indicators.

    Accepts multipart form-data with a `file` field (png/jpg/jpeg/webp).
    Runs OCR (local engine first, Gemini Vision fallback) then pipelines
    the extracted text to the text classifier and URL analyzer.

    When no OCR engine is available, returns a verdict based on image
    metadata only.
    """
    result = analyze_image(file.file)
    return result


@router.post("/voice", response_model=VoiceAnalysisVerdict, status_code=200)
async def analyze_voice_endpoint(
    file: UploadFile = File(...),
) -> VoiceAnalysisVerdict:
    """Analyze an uploaded audio file for scam content and synthetic voice.

    Accepts multipart form-data with a `file` field (ogg/mp3/wav/m4a/webm).
    Transcribes via Groq Whisper, classifies the transcript, and checks
    for AI-synthesized voice using Resemblyzer.

    When Whisper or Resemblyzer is unavailable, returns a verdict based on
    whatever signals are present.
    """
    result = analyze_voice(file.file)
    return result
