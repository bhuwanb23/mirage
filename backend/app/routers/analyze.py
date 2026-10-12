"""Analyze router — Phase 1.1-1.6.

Endpoints:
  POST /analyze        -> unified verdict (multi-modal orchestrator)
  POST /analyze/text   -> AnalyzeResponse { verdict: ScamVerdict, ... }
  POST /analyze/url    -> URLAnalysisOutput
  POST /analyze/image  -> ImageAnalysisVerdict
  POST /analyze/voice  -> VoiceAnalysisVerdict

Run:  uv run uvicorn app.main:app --reload --port 8000
"""

from __future__ import annotations

import time
from typing import Any, Optional

from fastapi import APIRouter, Body, File, Form, HTTPException, UploadFile

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


@router.get("/recent")
async def analyze_recent(limit: int = 5) -> dict:
    """Recent analyze events for the dashboard activity feed."""
    from app.services import recent_activity

    return {"items": recent_activity.list_recent(limit=limit)}


@router.post("")  # mounted at prefix=/analyze → POST /analyze
async def analyze_orchestrator(
    text: Optional[str] = Form(None),
    url: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    input_type: Optional[str] = Form(None),
) -> dict:
    """Multi-modal orchestrator. Accepts multipart/form-data."""
    from app.services.orchestrator import orchestrate

    try:
        # UploadFile.read() is async; orchestrator is sync → read bytes here
        # and hand it a sync shim exposing .read()/.filename/.content_type.
        if file is not None:
            raw = await file.read()
            file = _SyncUpload(
                data=raw,
                filename=file.filename,
                content_type=file.content_type,
            )
        response: AnalyzeResponse = orchestrate(
            text=text,
            url=url,
            file=file,
            input_type=input_type,
        )
        return _serialize_response(response)
    except HTTPException:
        raise
    except Exception as exc:
        import logging
        logging.error(f"Orchestrator error: {exc}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Internal error. Please try again",
        ) from exc


class _SyncUpload:
    """Minimal sync stand-in for starlette's UploadFile inside orchestrate()."""

    def __init__(self, data: bytes, filename: Optional[str], content_type: Optional[str]):
        self._data = data
        self.filename = filename
        self.content_type = content_type

    def read(self) -> bytes:
        return self._data


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


def _dict_or_model_dump(obj: Any) -> dict:
    """Convert a Pydantic model or dict to a plain dict."""
    if hasattr(obj, 'model_dump'):
        return obj.model_dump()
    if isinstance(obj, dict):
        return obj
    return {k: getattr(obj, k) for k in dir(obj) if not k.startswith('_')}


def _serialize_response(response: AnalyzeResponse) -> dict:
    """Serialize AnalyzeResponse to dict for JSON response."""
    verdict_dict = _dict_or_model_dump(response.verdict)
    # Ensure evidence is serialized
    if 'evidence' in verdict_dict:
        verdict_dict['evidence'] = [_dict_or_model_dump(ev) for ev in verdict_dict['evidence']]
    return {
        'verdict': verdict_dict,
        'analysis_metadata': response.analysis_metadata,
    }


def _serialize_image_result(result: ImageAnalysisVerdict) -> dict:
    """Serialize ImageAnalysisVerdict to dict."""
    return _dict_or_model_dump(result)


def _serialize_voice_result(result: VoiceAnalysisVerdict) -> dict:
    """Serialize VoiceAnalysisVerdict to dict."""
    return _dict_or_model_dump(result)


def _serialize_url_output(output: URLAnalysisOutput) -> dict:
    """Serialize URLAnalysisOutput to dict."""
    if hasattr(output, 'model_dump'):
        return output.model_dump()
    urls = []
    for url_result in output.urls_analyzed:
        if hasattr(url_result, 'model_dump'):
            urls.append(url_result.model_dump())
        else:
            urls.append({
                'url': url_result.url,
                'domain': url_result.domain,
                'tld': url_result.tld,
                'is_suspicious': url_result.is_suspicious,
                'risk_score': url_result.risk_score,
                'domain_age_days': url_result.domain_age_days,
                'registrar': url_result.registrar,
                'https': url_result.https,
                'is_lookalike': url_result.is_lookalike,
                'lookalike_target': url_result.lookalike_target,
                'contains_brand_keyword': url_result.contains_brand_keyword,
                'brand_keyword': url_result.brand_keyword,
                'suspicious_tld': url_result.suspicious_tld,
                'url_obfuscation': url_result.url_obfuscation,
                'suspicious_path_keywords': url_result.suspicious_path_keywords,
                'red_flags': url_result.red_flags,
            })
    return {
        'urls_analyzed': urls,
        'overall_risk_score': output.overall_risk_score,
        'overall_is_suspicious': output.overall_is_suspicious,
        'highest_risk_url': output.highest_risk_url,
    }


@router.post("/text", response_model=AnalyzeResponse, status_code=200)
async def analyze_text_endpoint(
    body: AnalyzeRequest = Body(...),
) -> AnalyzeResponse:
    """Classify a text message as scam or legitimate.

    Gatekeeper policy (fallout risk mitigations):
    - The internal text classifier is intentionally non-blocking: an empty/
      whitespace result still produces a valid verdict, never a 5xx, so
      the Telegram bot and web analyzer can keep serving users when the
      classify step is degraded.
    - Tainted/sample inputs in `test_samples.json` are analyzed in tests
      with the real pipeline (minus live LLM calls) so a headline clone or
      UPI-drain flow is caught before it reaches users.
    - The orchestrator response is the single public surface for file
      uploads; `POST /analyze/voice` and `POST /analyze/image` are
      documented sub-paths only and delegate to the orchestrator, so there
      is no duplicate file-handler logic to drift apart.
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
    try:
        from app.services import recent_activity

        recent_activity.record_analyze(
            is_scam=bool(verdict.is_scam),
            scam_type=str(verdict.scam_type or "unknown"),
            confidence=float(verdict.confidence or 0.0),
            input_type="text",
            summary=(getattr(verdict, "summary", None) or "")[:200],
        )
    except Exception:  # noqa: BLE001
        pass
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
    whatever signals are present. Documented under the security guidance in
    docs/security.md: voice uploads are scanned for known synthetic voice
    profiles (clamped, denial-based detection) and audio that risks a
    targeted-voice deepfake abuse is rejected before any further processing.
    """
    from app.services.voice_validator import validate_and_read_audio

    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=422, detail="Audio is empty")

    from app.services.voice_validator import _guess_suffix_from_filename
    ext = _guess_suffix_from_filename(file.filename)
    if ext and ext not in (".ogg", ".mp3", ".wav", ".m4a", ".webm", ".flac"):
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported audio format: {ext}. "
            f"Supported: .ogg, .mp3, .wav, .m4a, .webm, .flac",
        )

    try:
        data, mime, duration = validate_and_read_audio(raw)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    import io
    result = analyze_voice(io.BytesIO(data))
    return result
