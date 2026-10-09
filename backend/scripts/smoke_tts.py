"""Smoke test: edge-tts speech synthesis (no API key needed).

Run:  cd backend && uv run python scripts/smoke_tts.py
Writes a short mp3 next to the script and reports its size.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.clients import tts_client  # noqa: E402

OUT = Path(__file__).parent / "smoke_tts_out.mp3"


def main() -> int:
    try:
        tts_client.synthesize_to_file(
            "Mirage online. Your scam drill is ready.", OUT, "en", "female"
        )
    except Exception as exc:
        print(f"[FAIL] TTS failed: {exc}")
        return 1

    size = OUT.stat().st_size
    if size < 1000:
        print(f"[FAIL] audio too small ({size} bytes)")
        return 1

    print(f"[OK] wrote {OUT.name} ({size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
