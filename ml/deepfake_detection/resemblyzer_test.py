"""Resemblyzer sanity check for Mirage voice work.

Two jobs:
  1. voice-clone similarity  -> drill audio authenticity (F5-TTS output vs reference)
  2. deepfake detection      -> Phase 6: is this caller really the person claimed?

Run from backend/ so `app.*` imports resolve:
    cd backend && uv run python ../ml/deepfake_detection/resemblyzer_test.py

Requires the optional voice group (Python 3.11/3.12 only):
    cd backend && uv sync --group voice
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from app.clients import resemblyzer_client as rc  # noqa: E402


def main() -> int:
    report = rc.availability_report()
    print("availability:", report)

    if not rc.is_available():
        print("[SKIP] resemblyzer not installed (voice group is optional)")
        print("       uv sync --group voice   # needs Python 3.11 or 3.12")
        return 0

    # Both samples must exist for a real similarity check.
    ref = Path(__file__).parent / "sample_reference.wav"
    probe = Path(__file__).parent / "sample_probe.wav"

    if not (ref.exists() and probe.exists()):
        print("[SKIP] no samples found. Place sample_reference.wav + sample_probe.wav here.")
        return 0

    a = rc.embed_wav(str(ref))
    b = rc.embed_wav(str(probe))
    score = rc.similarity(a, b)

    verdict = "MATCH" if score > 0.75 else "MISMATCH"
    print(f"[OK] similarity={score:.3f} -> {verdict}")
    print("     threshold 0.75 is a starting point; tune on your own corpus.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
