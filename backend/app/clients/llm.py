"""LLM provider router — Groq → Gemini → Ollama, selected by availability.

Set LLM_PROVIDER to pin a provider; leave it as `auto` to pick the first available.
Every provider is called through the same interface so Phase 1 prompts are
provider-identical.
"""

from __future__ import annotations

import logging

from app.config import settings

logger = logging.getLogger("mirage.llm")

Order = ["groq", "gemini", "ollama"]


def _provider_order(requested: str | None = None) -> list[str]:
    requested = (requested or settings.llm_provider).lower()
    if requested in Order:
        return [requested]
    return [p for p in settings.available_llm_providers if p in Order] or Order


def _call(provider: str, messages, model, json_mode, temperature, timeout=None) -> str:
    if provider == "groq":
        from app.clients import groq_client

        return groq_client.chat_completion(
            messages, model=model or groq_client.DEFAULT_CHAT_MODEL,
            json_mode=json_mode, temperature=temperature, timeout=timeout,
        )
    if provider == "gemini":
        from app.clients import gemini_client

        return gemini_client.chat_completion(
            messages, model=model or gemini_client.DEFAULT_MODEL,
            json_mode=json_mode, temperature=temperature, timeout=timeout,
        )
    if provider == "ollama":
        from app.clients import ollama_client

        return ollama_client.chat_completion(
            messages, model=model, json_mode=json_mode, temperature=temperature, timeout=timeout,
        )
    raise ValueError(f"unknown LLM provider: {provider}")


def chat_completion(
    messages: list[dict[str, str]],
    provider: str | None = None,
    model: str | None = None,
    json_mode: bool = False,
    temperature: float = 0.3,
    timeout: float | None = None,
    fallback: bool = True,
) -> str:
    """Chat completion with automatic provider fallback.

    Raises RuntimeError if every configured provider fails.
    """
    errors: list[str] = []
    for p in _provider_order(provider):
        try:
            return _call(p, messages, model, json_mode, temperature)
        except Exception as exc:
            errors.append(f"{p}: {exc}")
            logger.warning("LLM provider %s failed (%s)", p, exc)
            if not fallback:
                break
    raise RuntimeError("All LLM providers failed -> " + " | ".join(errors))


def available_providers() -> list[str]:
    return [p for p in _provider_order() if p in settings.available_llm_providers or p == "ollama"]
