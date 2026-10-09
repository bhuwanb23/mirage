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

from fastapi import APIRouter, Body, HTTPException

from app.models.schemas import AnalyzeRequest, AnalyzeResponse
from app.services.scam_analyzer import analyze_text

router = APIRouter(tags=["analyze"])


def _metadata(
    input_type: str,
    processing_ms: float,
    language: str,
    provider_used: str | None,
) -> dict:
    return {
        "input_type": input_type,
        "analyzers_used": ["text_classifier"],
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
        # Defer to the service's empty-text handling for a consistent schema.
        verdict = analyze_text("")
        processing_ms = (time.perf_counter() - t0) * 1000
        return AnalyzeResponse(
            verdict=verdict,
            analysis_metadata=_metadata("text", processing_ms, body.input_type or "en", None),
        )

    provider_used: str | None = None
    try:
        verdict = analyze_text(
            message_text=text,
            sender_info=None,
            language=body.input_type or "en",
        )
        provider_used = None  # populated below if we can detect it
    except Exception as exc:
        # The service already returns a failure verdict for unreachable providers,
        # but if it raises we convert to a stable response.
        raise HTTPException(status_code=503, detail=f"Analysis unavailable: {exc}") from exc

    processing_ms = (time.perf_counter() - t0) * 1000
    return AnalyzeResponse(
        verdict=verdict,
        analysis_metadata=_metadata("text", processing_ms, body.input_type or "en", provider_used),
    )
