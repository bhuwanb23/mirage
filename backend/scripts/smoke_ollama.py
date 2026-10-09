"""Smoke test: local Ollama availability + chat.

Run:  cd backend && uv run python scripts/smoke_ollama.py
Skips if no Ollama server is listening (ollama serve).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.clients import ollama_client  # noqa: E402
from app.config import settings  # noqa: E402


def main() -> int:
    if not ollama_client.is_available():
        print(f"[SKIP] No Ollama server at {settings.ollama_base_url} (run: ollama serve)")
        return 0

    models = ollama_client.list_models()
    print(f"[OK] models: {models}")

    if not models:
        print(f"[WARN] no models pulled - run: ollama pull {settings.ollama_model}")
        return 0

    try:
        out = ollama_client.chat_completion(
            [{"role": "user", "content": "Reply with exactly: MIRAGE OK"}],
            model=settings.ollama_model,
            temperature=0.0,
        )
    except Exception as exc:
        print(f"[FAIL] Ollama chat failed: {exc}")
        return 1

    print(f"[OK] response: {out[:200]!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
