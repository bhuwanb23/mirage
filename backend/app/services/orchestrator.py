"""Multi-Modal Orchestrator (Phase 1.6).

Single entry point that accepts any input type, detects what it is, routes to
the right analyzers, and returns a unified verdict via the Evidence Builder.

Flow:
  1. Validate input (at least one of text/url/file)
  2. Detect input type (auto-detect if not provided)
  3. Route to appropriate analyzers
  4. Collect results from all analyzers
  5. Pass to Evidence Builder for unified verdict
  6. Return AnalyzeResponse with verdict + metadata
"""

from __future__ import annotations

import os
import re
import time
from typing import Any, Optional

from fastapi import HTTPException, UploadFile

from app.models.schemas import (
    AnalyzeResponse,
)
from app.services.evidence_builder import build_evidence_trail
from app.services.image_analyzer import analyze_image
from app.services.scam_analyzer import analyze_text
from app.services.url_analyzer import analyze_text_for_urls
from app.services.voice_analyzer import analyze_voice

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
MAX_AUDIO_BYTES = 10 * 1024 * 1024  # 10 MB
MAX_IMAGE_BYTES = 5 * 1024 * 1024   # 5 MB
MAX_TEXT_LENGTH = 10000              # truncate beyond this

ANALYZE_TIMEOUT_SECONDS = 30

# MIME → input type mapping
AUDIO_MIME_PREFIXES = ("audio/ogg", "audio/mpeg", "audio/wav", "audio/mp4",
                        "audio/webm", "audio/flac")
IMAGE_MIME_PREFIXES = ("image/png", "image/jpeg", "image/webp", "image/gif")

# URL detection regex
_URL_RE = re.compile(
    r"https?://[^\s<>\"|{}|\\^`\[\]]+"
)

_SUPPORTED_AUDIO_EXTS = {".ogg", ".mp3", ".wav", ".m4a", ".webm", ".flac"}
_SUPPORTED_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def orchestrate(
    text: Optional[str] = None,
    url: Optional[str] = None,
    file: Optional[UploadFile] = None,
    input_type: Optional[str] = None,
) -> AnalyzeResponse:
    """Analyze any input and return a unified scam verdict.

    At least one of `text`, `url`, or `file` must be provided.

    Args:
        text: Message text (if no file).
        url: URL to check (if no file).
        file: Audio, image, or document file.
        input_type: Explicit type hint (text/audio/image/url). Auto-detected
            if not provided.

    Returns:
        AnalyzeResponse with merged verdict and analysis metadata.
    """
    t0 = time.perf_counter()

    # Step 1: validate at least one input
    if not text and not url and not file:
        raise HTTPException(
            status_code=400,
            detail="Provide text, url, or file",
        )

    # Step 2: detect input type
    detected_type = _detect_input_type(text, url, file, input_type)

    # Validate file if present
    if file is not None:
        _validate_file(file, detected_type)

    # Step 3: route to analyzers and collect results
    results: dict[str, Any] = {}
    analyzers_used: list[str] = []
    language = "en"

    if detected_type == "text":
        results, analyzers_used, language = _route_text(text, url)
    elif detected_type == "url":
        results, analyzers_used, language = _route_url(text, url)
    elif detected_type == "image":
        results, analyzers_used, language = _route_image(file)
    elif detected_type == "audio":
        results, analyzers_used, language = _route_audio(file)
    else:
        # Fallback — shouldn't happen
        results, analyzers_used = _route_text(text or "", url)

    # Step 4: pass to evidence builder
    verdict = build_evidence_trail(results)

    processing_ms = (time.perf_counter() - t0) * 1000

    return AnalyzeResponse(
        verdict=verdict,
        analysis_metadata={
            "input_type": detected_type,
            "analyzers_used": analyzers_used,
            "processing_time_ms": round(processing_ms, 1),
            "language_detected": language,
        },
    )


# ---------------------------------------------------------------------------
# Input type detection
# ---------------------------------------------------------------------------


def _detect_input_type(
    text: Optional[str],
    url: Optional[str],
    file: Optional[UploadFile],
    input_type: Optional[str],
) -> str:
    """Auto-detect input type when not explicitly provided."""
    if input_type is not None:
        return input_type.lower()

    # If file is present, detect from MIME or extension
    if file is not None:
        return _detect_from_file(file)

    # If url is present and text is empty → url
    if url and not text:
        return "url"

    # If text is present
    if text:
        text_clean = (text or "").strip()
        # If text is ONLY a URL → url
        if _is_only_url(text_clean):
            return "url"
        # If text contains a URL AND other content → text
        if _URL_RE.search(text_clean):
            return "text"
        return "text"

    # Fallback
    return "text"


def _detect_from_file(file: UploadFile) -> str:
    """Detect input type from uploaded file's MIME type or extension."""
    filename = file.filename or ""
    ext = _get_extension(filename)

    if ext in _SUPPORTED_IMAGE_EXTS:
        return "image"

    if ext in _SUPPORTED_AUDIO_EXTS:
        return "audio"

    # Check MIME type
    content_type = file.content_type or ""
    if content_type.startswith("image/"):
        return "image"
    if content_type.startswith("audio/"):
        return "audio"
    if content_type == "application/pdf":
        return "image"  # treat PDF as image (OCR first page — stretch goal)

    # Unsupported
    raise HTTPException(
        status_code=400,
        detail=f"Unsupported file type: {ext or content_type or 'unknown'}",
    )


def _get_extension(filename: str) -> str:
    """Get lowercase file extension, or empty string."""
    if not filename:
        return ""
    _, ext = os.path.splitext(filename)
    return ext.lower()


def _is_only_url(text: str) -> bool:
    """Check if text is ONLY a URL (no other content)."""
    text_clean = text.strip()
    if not text_clean:
        return False
    # Remove the URL, check if anything remains
    match = _URL_RE.search(text_clean)
    if not match:
        return False
    remaining = text_clean[:match.start()] + text_clean[match.end():]
    return not remaining.strip()


# ---------------------------------------------------------------------------
# File validation
# ---------------------------------------------------------------------------


def _validate_file(file: UploadFile, input_type: str) -> None:
    """Validate uploaded file size and type."""
    # Read file to check size (we need the bytes anyway for routing)
    # Actually, we read in the route functions. Here just check headers.
    # Size validation is done in the specific route functions.

    ext = _get_extension(file.filename or "")
    content_type = file.content_type or ""

    if input_type == "audio":
        if ext not in _SUPPORTED_AUDIO_EXTS and not content_type.startswith("audio/"):
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type: {ext or content_type}",
            )
    elif input_type == "image":
        if ext not in _SUPPORTED_IMAGE_EXTS and not content_type.startswith("image/"):
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type: {ext or content_type}",
            )


# ---------------------------------------------------------------------------
# Routing functions
# ---------------------------------------------------------------------------


def _route_text(text: Optional[str], url: Optional[str]) -> tuple[dict[str, Any], list[str], str]:
    """Route TEXT input to text classifier + URL analyzer."""
    text_clean = _normalize_text(text)
    analyzers_used: list[str] = ["text_classifier"]

    # Call text classifier
    text_verdict = analyze_text(
        message_text=text_clean,
        sender_info=None,
    )

    results: dict[str, Any] = {
        "text_verdict": text_verdict,
    }

    # Extract URLs from text and analyze if found
    if text_clean:
        url_output = analyze_text_for_urls(text_clean)
        if url_output.urls_analyzed:
            analyzers_used.append("url_analyzer")
            results["url_results"] = url_output.urls_analyzed

    return results, analyzers_used, "en"


def _route_url(text: Optional[str], url: Optional[str]) -> tuple[dict[str, Any], list[str], str]:
    """Route URL input to URL analyzer + text classifier."""
    analyzers_used: list[str] = ["url_analyzer", "text_classifier"]

    # Use provided url or extract from text
    target_url = url or ""
    if not target_url:
        # Try to extract from text
        text_clean = _normalize_text(text)
        match = _URL_RE.search(text_clean)
        if match:
            target_url = match.group(0)

    if target_url:
        url_output = analyze_text_for_urls(target_url)
        results: dict[str, Any] = {
            "url_results": url_output.urls_analyzed,
        }
    else:
        results = {"url_results": []}

    # Also classify the URL as text (for pattern matching)
    text_for_classification = target_url or (text or "")
    text_verdict = analyze_text(
        message_text=text_for_classification,
        sender_info=None,
    )
    results["text_verdict"] = text_verdict

    return results, analyzers_used, "en"


def _route_image(file: UploadFile) -> tuple[dict[str, Any], list[str], str]:
    """Route IMAGE input to image analyzer (which internally calls text + URL)."""
    import io

    raw = file.read()
    if not raw:
        raise HTTPException(status_code=422, detail="Image file is empty")

    if len(raw) > MAX_IMAGE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Max {MAX_IMAGE_BYTES // (1024*1024)}MB for images",
        )

    result = analyze_image(io.BytesIO(raw))

    analyzers_used = ["image_analyzer", "text_classifier"]
    if result.verdict.evidence:
        for ev in result.verdict.evidence:
            if ev.source == "url_analyzer" and "url_analyzer" not in analyzers_used:
                analyzers_used.append("url_analyzer")

    # Image analyzer internally calls text classifier + URL analyzer
    # We need to pass results to evidence builder
    # Extract URL results from image analysis if available
    # The image analyzer's verdict contains evidence with url_analyzer source

    # For the orchestrator, we pass the image verdict's verdict as text_verdict
    # and extract any URL results from evidence
    results: dict[str, Any] = {
        "text_verdict": result.verdict,
    }



    return results, analyzers_used, result.detected_language or "en"


def _route_audio(file: UploadFile) -> tuple[dict[str, Any], list[str], str]:
    """Route AUDIO input to voice analyzer (which internally calls text classifier)."""
    import io

    from app.services.voice_validator import validate_and_read_audio

    raw = file.read()
    if not raw:
        raise HTTPException(status_code=422, detail="Audio file is empty")

    if len(raw) > MAX_AUDIO_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Max {MAX_AUDIO_BYTES // (1024*1024)}MB for audio",
        )

    # Validate and get mime/duration
    try:
        data, mime, duration = validate_and_read_audio(raw)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    result = analyze_voice(io.BytesIO(data))

    analyzers_used = ["audio_analyzer", "text_classifier"]
    if result.verdict.evidence:
        for ev in result.verdict.evidence:
            if ev.source == "url_analyzer" and "url_analyzer" not in analyzers_used:
                analyzers_used.append("url_analyzer")

    results: dict[str, Any] = {
        "text_verdict": result.verdict,
    }

    return results, analyzers_used, result.detected_language or "en"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _normalize_text(text: Optional[str]) -> str:
    """Normalize text input."""
    if not text:
        return ""
    text = text.strip()
    if len(text) > MAX_TEXT_LENGTH:
        text = text[:MAX_TEXT_LENGTH]
    return text
