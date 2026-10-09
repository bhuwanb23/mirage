"""Smoke test: LLM router (Groq -> Gemini -> Ollama).

Run:  cd backend && uv run python scripts/smoke_llm.py
Exit 0 = pass (or graceful skip when no provider configured).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.clients import (
    llm,  # noqa: E402
    ollama_client,  # noqa: E402
)
from app.config import settings  # noqa: E402


def reachable_providers() -> list[str]:
    """Configured providers that we can actually talk to right now."""
    out = []
    for p in settings.available_llm_providers:
        if p == "ollama" and not ollama_client.is_available():
            continue
        out.append(p)
    return out


def main() -> int:
    providers = reachable_providers()
    if not providers:
        print(
            "[SKIP] No reachable LLM provider "
            "(set GROQ_API_KEY / GEMINI_API_KEY, or start Ollama with `ollama serve`)"
        )
        return 0

    try:
        out = llm.chat_completion(
            [{"role": "user", "content": "Reply with exactly: MIRAGE OK"}],
            provider=providers[0],
            fallback=False,
            temperature=0.0,
        )
    except Exception as exc:
        print(f"[FAIL] LLM call failed: {exc}")
        return 1

    print(f"[OK] provider: {providers[0]} (reachable chain: {providers})")
    print(f"[OK] response: {out[:200]!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
