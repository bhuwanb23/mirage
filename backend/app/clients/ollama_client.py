"""Ollama client — local LLM fallback (no API key required)."""

from __future__ import annotations

import logging
import time

import httpx

from app.config import settings

logger = logging.getLogger("mirage.ollama")

TIMEOUT = httpx.Timeout(60.0, connect=5.0)


def is_available() -> bool:
    """True if an Ollama server is reachable."""
    try:
        resp = httpx.get(f"{settings.ollama_base_url}/api/tags", timeout=3.0)
        return resp.status_code == 200
    except Exception:
        return False


def list_models() -> list[str]:
    try:
        resp = httpx.get(f"{settings.ollama_base_url}/api/tags", timeout=3.0)
        resp.raise_for_status()
        return [m["name"] for m in resp.json().get("models", [])]
    except Exception:
        return []


def resolve_model(requested: str) -> str:
    """Return `requested` if installed, else the first installed model.

    Ollama answers 404 with an empty body when the model is missing, which is
    useless to a caller — so we check `/api/tags` first.
    """
    installed = list_models()
    if not installed:
        raise RuntimeError(
            "Ollama is running but has no models. Pull one: `ollama pull llama3.2:1b`"
        )
    if requested in installed:
        return requested
    # allow "llama3.2:1b" matching "llama3.2:1b" or bare-name matches
    for m in installed:
        if m.split(":")[0] == requested.split(":")[0]:
            logger.warning("ollama model %r not installed, using %r", requested, m)
            return m
    logger.warning(
        "ollama model %r not installed, using first available %r", requested, installed[0]
    )
    return installed[0]


def chat_completion(
    messages: list[dict[str, str]],
    model: str | None = None,
    json_mode: bool = False,
    temperature: float = 0.3,
    timeout: float | None = None,
) -> str:
    """Chat completion against local Ollama. Same interface as groq_client."""
    payload = {
        "model": resolve_model(model or settings.ollama_model),
        "messages": messages,
        "stream": False,
        "options": {"temperature": temperature},
    }
    _timeout = httpx.Timeout(timeout, connect=5.0) if timeout else None
    if json_mode:
        payload["format"] = "json"

    start = time.perf_counter()
    resp = httpx.post(
        f"{settings.ollama_base_url}/api/chat", json=payload,
        timeout=_timeout if _timeout else TIMEOUT,
    )
    resp.raise_for_status()
    latency_ms = (time.perf_counter() - start) * 1000
    data = resp.json()
    logger.info(
        "ollama chat ok",
        extra={"model": payload["model"], "latency_ms": round(latency_ms, 1)},
    )
    return data.get("message", {}).get("content", "")
