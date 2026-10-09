"""Groq client — chat completions (Llama 3.3 70B) + Whisper transcription."""

from __future__ import annotations

import logging
import time
from typing import Any, Optional

import httpx

from app.config import settings

logger = logging.getLogger("mirage.groq")

DEFAULT_CHAT_MODEL = "llama-3.3-70b-versatile"
WHISPER_MODEL = "whisper-large-v3"
AUDIO_FORMATS = (".ogg", ".mp3", ".wav", ".m4a", ".webm", ".flac")


def _client():
    if not settings.groq_api_key:
        raise RuntimeError("GROQ_API_KEY not configured")
    from groq import Groq

    return Groq(api_key=settings.groq_api_key)


def chat_completion(
    messages: list[dict[str, str]],
    model: str = DEFAULT_CHAT_MODEL,
    json_mode: bool = False,
    temperature: float = 0.3,
    max_retries: int = 1,
    timeout: float | None = None,
) -> str:
    """Chat completion. Retries once after 2s on 429 rate limit."""
    client = _client()
    kwargs: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    _timeout = (
        httpx.Timeout(timeout, connect=5.0) if timeout else None
    )

    start = time.perf_counter()
    last_exc: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            resp = client.chat.completions.create(
                **kwargs, timeout=_timeout if _timeout else None
            )
            latency_ms = (time.perf_counter() - start) * 1000
            usage = getattr(resp, "usage", None)
            logger.info(
                "groq chat ok",
                extra={
                    "model": model,
                    "latency_ms": round(latency_ms, 1),
                    "tokens_in": getattr(usage, "prompt_tokens", None),
                    "tokens_out": getattr(usage, "completion_tokens", None),
                },
            )
            return resp.choices[0].message.content or ""
        except Exception as exc:  # groq.RateLimitError among others
            last_exc = exc
            if "429" in str(exc) or "rate" in str(exc).lower():
                if attempt < max_retries:
                    logger.warning("Groq 429 - retrying in 2s (attempt %s)", attempt + 1)
                    time.sleep(2)
                    continue
            raise
    raise last_exc  # pragma: no cover


def transcribe_audio(file_path: str, language: Optional[str] = None) -> str:
    """Transcribe audio via Groq Whisper. Supports ogg/mp3/wav/m4a/webm/flac."""
    client = _client()
    start = time.perf_counter()
    with open(file_path, "rb") as f:
        kwargs: dict[str, Any] = {"file": (file_path, f), "model": WHISPER_MODEL}
        if language:
            kwargs["language"] = language
        resp = client.audio.transcriptions.create(**kwargs)
    latency_ms = (time.perf_counter() - start) * 1000
    logger.info(
        "groq whisper ok",
        extra={"model": WHISPER_MODEL, "latency_ms": round(latency_ms, 1)},
    )
    return resp.text


def is_configured() -> bool:
    return bool(settings.groq_api_key)
