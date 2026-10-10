"""Generate pre-demo drill audios (edge-tts) into frontend/public/audio/drill/.

Run from backend/:  uv run python scripts/generate_demo_audio.py

These are the static fallback files the frontend plays when live synthesis is
unavailable, so a demo never depends on the network or an LLM.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.voice_synthesizer import pre_generate_demo_audio  # noqa: E402

BACKEND_DIR = Path(__file__).resolve().parent.parent
FRONTEND_AUDIO_DIR = (
    BACKEND_DIR.parent / "frontend" / "public" / "audio" / "drill"
)

SCAM_TYPES = ["bank_kyc", "fedex", "job_offer", "relative_distress", "rbi_police"]


def main() -> int:
    print(f"Generating demo audios for: {', '.join(SCAM_TYPES)}")
    results = pre_generate_demo_audio(SCAM_TYPES, language="en")

    FRONTEND_AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    failures = 0
    for scam_type, res in results.items():
        if res.get("status") != "ready" or not res.get("audio_url"):
            print(f"  [FAIL] {scam_type}: {res.get('message', 'unknown error')}")
            failures += 1
            continue
        src = BACKEND_DIR / res["audio_url"].lstrip("/")
        if not src.exists():
            print(f"  [FAIL] {scam_type}: expected file missing at {src}")
            failures += 1
            continue
        dst = FRONTEND_AUDIO_DIR / f"{scam_type}.mp3"
        shutil.copyfile(src, dst)
        size_kb = dst.stat().st_size / 1024
        print(
            f"  [OK]   {scam_type}: {dst} "
            f"({res['duration_seconds']}s, {size_kb:.0f} KB, {res['method_used']})"
        )

    if failures:
        print(f"\n{failures} generation(s) failed — check network access to edge-tts.")
        return 1
    print(f"\nAll demo audios written to {FRONTEND_AUDIO_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
