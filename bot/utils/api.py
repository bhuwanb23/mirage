"""Async HTTP client for the Mirage backend (Phase 2).

Wraps POST /analyze (multipart form) with per-input timeouts and a small
error taxonomy so handlers can map failures to friendly Telegram replies:

    ApiError            → backend replied with a non-2xx status (has .status)
    ApiTimeout          → request exceeded the per-input timeout
    ApiConnectionError  → backend unreachable
    ApiDecodeError      → backend replied with malformed JSON

Run:  uv run python -c "from utils.api import health; print(health())"
"""

from __future__ import annotations

import os
from typing import Any, Optional

import httpx

# Accept both env names used across the repo (.env.example vs bot/.env.example).
API_URL = (
    os.getenv("BACKEND_URL") or os.getenv("MIRAGE_API_URL") or "http://localhost:8000"
).rstrip("/")

# Per-input timeouts (seconds), from the Phase 2 spec.
TIMEOUTS = {
    "text": 15.0,
    "url": 10.0,
    "image": 15.0,
    "audio": 20.0,
}

_CONNECT_TIMEOUT = 5.0


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

class ApiError(Exception):
    """Backend returned a non-2xx HTTP status."""

    def __init__(self, status: int, detail: str = ""):
        self.status = status
        self.detail = detail or f"HTTP {status}"
        super().__init__(f"API error {status}: {self.detail}")


class ApiTimeout(Exception):
    """Request exceeded the timeout budget."""


class ApiConnectionError(Exception):
    """Could not reach the backend at all."""


class ApiDecodeError(Exception):
    """Backend replied with a body that is not valid JSON."""


def friendly_error(exc: Exception) -> str:
    """Map an api-layer exception to the user-facing message (spec error table)."""
    if isinstance(exc, ApiError):
        if exc.status == 400:
            return "Invalid input. Please try again."
        if exc.status in (413,):
            return exc.detail or "File too large."
        if exc.status == 422:
            return exc.detail or "That file could not be processed."
        if exc.status == 503:
            return "AI service is temporarily busy. Please try again in 30 seconds."
        if exc.status == 504:
            return "Analysis timed out. Try a shorter message."
        if exc.status >= 500:
            return "Something went wrong on the server. Please try again."
        return "Something went wrong. Please try again."
    if isinstance(exc, ApiTimeout):
        return "Analysis timed out. Try a shorter message."
    if isinstance(exc, ApiConnectionError):
        return "Cannot reach the analysis server. Please try again later."
    if isinstance(exc, ApiDecodeError):
        return "⚠️ Analysis failed due to a server error. Please try again in a moment."
    return "Something went wrong. Please try again."


# ---------------------------------------------------------------------------
# Core request helper
# ---------------------------------------------------------------------------

def _timeout_for(kind: str) -> httpx.Timeout:
    return httpx.Timeout(TIMEOUTS.get(kind, 15.0), connect=_CONNECT_TIMEOUT)


async def _post(
    path: str,
    *,
    text: Optional[str] = None,
    url: Optional[str] = None,
    input_type: Optional[str] = None,
    file: Optional[tuple[str, bytes, str]] = None,
    kind: str = "text",
    json_body: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """POST `path` as multipart/form-data (or JSON when `json_body` is given).

    `file` is a (filename, bytes, content_type) triple.
    Returns the parsed JSON body; raises the taxonomy errors above.
    """
    data: dict[str, str] = {}
    if text is not None:
        data["text"] = text
    if url is not None:
        data["url"] = url
    if input_type is not None:
        data["input_type"] = input_type

    files = None
    if file is not None:
        filename, payload, content_type = file
        files = {"file": (filename, payload, content_type)}

    try:
        async with httpx.AsyncClient(timeout=_timeout_for(kind)) as client:
            if json_body is not None:
                resp = await client.post(f"{API_URL}{path}", json=json_body)
            else:
                resp = await client.post(f"{API_URL}{path}", data=data, files=files)
    except httpx.TimeoutException as exc:
        raise ApiTimeout(str(exc)) from exc
    except httpx.TransportError as exc:
        raise ApiConnectionError(str(exc)) from exc

    if resp.status_code >= 400:
        detail = ""
        try:
            body = resp.json()
            detail = str(body.get("detail", ""))
        except Exception:
            detail = resp.text[:200]
        raise ApiError(resp.status_code, detail)

    try:
        return resp.json()
    except Exception as exc:
        raise ApiDecodeError(str(exc)) from exc


# ---------------------------------------------------------------------------
# Public API — one function per input kind
# ---------------------------------------------------------------------------

async def analyze_text(text: str) -> dict[str, Any]:
    """Analyze a text message. Returns {verdict, analysis_metadata}."""
    return await _post("/analyze", text=text, kind="text")


async def analyze_url(url: str) -> dict[str, Any]:
    """Analyze a URL/domain via POST /analyze/url.

    Returns URLAnalysisOutput (urls_analyzed with age/registrar/lookalike/risk,
    overall_risk_score, highest_risk_url) — the orchestrator does not carry
    these per-URL fields.
    """
    return await _post("/analyze/url", json_body={"text": url}, kind="url")


async def analyze_image(filename: str, payload: bytes, content_type: str) -> dict[str, Any]:
    """Analyze an uploaded image via POST /analyze/image.

    Returns the ImageAnalysisVerdict body (verdict + ocr_text + visual flags) —
    the plain /analyze orchestrator does not carry the OCR fields.
    """
    return await _post(
        "/analyze/image",
        file=(filename, payload, content_type),
        kind="image",
    )


async def analyze_audio(filename: str, payload: bytes, content_type: str) -> dict[str, Any]:
    """Analyze an uploaded audio file via POST /analyze/voice.

    Returns the VoiceAnalysisVerdict body (verdict + transcript + synthetic score).
    """
    return await _post(
        "/analyze/voice",
        file=(filename, payload, content_type),
        kind="audio",
    )


async def health() -> dict[str, Any] | None:
    """GET /health — returns None when unreachable (non-fatal)."""
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
            resp = await client.get(f"{API_URL}/health")
            resp.raise_for_status()
            return resp.json()
    except Exception:
        return None
