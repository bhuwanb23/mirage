"""Smoke test: Groq Whisper transcription.

Run:  cd backend && uv run python scripts/smoke_whisper.py
Skips cleanly when GROQ_API_KEY is missing or no sample audio is present.
Usage: uv run python scripts/smoke_whisper.py path/to/audio.ogg
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.clients import groq_client  # noqa: E402


def main() -> int:
    if not groq_client.is_configured():
        print("[SKIP] GROQ_API_KEY not set")
        return 0

    if len(sys.argv) < 2:
        print("[SKIP] No audio file provided. Usage: smoke_whisper.py path/to/audio.ogg")
        return 0

    path = sys.argv[1]
    if not Path(path).exists():
        print(f"[FAIL] file not found: {path}")
        return 1

    try:
        text = groq_client.transcribe_audio(path)
    except Exception as exc:
        print(f"[FAIL] Whisper failed: {exc}")
        return 1

    print(f"[OK] transcript: {text!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
