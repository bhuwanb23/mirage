"""Smoke test: Gemini vision (image analysis).

Run:  cd backend && uv run python scripts/smoke_vision.py
Skips cleanly when GEMINI_API_KEY is missing.
"""

from __future__ import annotations

import base64
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.clients import gemini_client  # noqa: E402

# 1x1 red PNG (no file needed)
PNG_RED = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGP4z8DwHwAFAAH/q842iQAAAABJRU5ErkJggg=="
)


def main() -> int:
    if not gemini_client.is_configured():
        print("[SKIP] GEMINI_API_KEY not set")
        return 0
    try:
        out = gemini_client.analyze_image(PNG_RED, "What color is this 1x1 image? One word.")
    except Exception as exc:
        print(f"[FAIL] Gemini vision failed: {exc}")
        return 1
    print(f"[OK] response: {out!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
