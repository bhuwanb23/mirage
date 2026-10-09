"""Gemini client — vision (OCR/screenshots) + backup chat completion."""

from __future__ import annotations

import logging
import time
from typing import Optional

from app.config import settings

logger = logging.getLogger("mirage.gemini")

DEFAULT_MODEL = "gemini-2.0-flash"
IMAGE_MIME_TYPES = {"image/png", "image/jpeg", "image/webp", "image/gif"}


def _client():
    if not settings.gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY not configured")
    from google import genai

    return genai.Client(api_key=settings.gemini_api_key)


def analyze_image(image_bytes: bytes, prompt: str, mime_type: str = "image/png") -> str:
    """Send raw image bytes + prompt to Gemini vision. Returns text response."""
    from google.genai import types

    client = _client()
    part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
    start = time.perf_counter()
    resp = client.models.generate_content(
        model=DEFAULT_MODEL,
        contents=[prompt, part],
    )
    latency_ms = (time.perf_counter() - start) * 1000
    logger.info("gemini vision ok", extra={"model": DEFAULT_MODEL, "latency_ms": round(latency_ms, 1)})
    return resp.text or ""


def chat_completion(
    messages: list[dict[str, str]],
    model: str = DEFAULT_MODEL,
    json_mode: bool = False,
    temperature: float = 0.3,
) -> str:
    """Chat completion with the same interface as groq_client.chat_completion."""
    client = _client()
    # Convert chat messages into a single Gemini prompt with role markers.
    prompt = "\n\n".join(f"[{m['role'].upper()}]\n{m['content']}" for m in messages)
    config: dict = {"temperature": temperature}
    if json_mode:
        config["response_mime_type"] = "application/json"

    start = time.perf_counter()
    resp = client.models.generate_content(
        model=model,
        contents=prompt,
        config=types_config(config),
    )
    latency_ms = (time.perf_counter() - start) * 1000
    logger.info("gemini chat ok", extra={"model": model, "latency_ms": round(latency_ms, 1)})
    return resp.text or ""


def types_config(config: dict):
    from google.genai import types

    return types.GenerateContentConfig(**config)


def is_configured() -> bool:
    return bool(settings.gemini_api_key)
