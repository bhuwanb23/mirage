"""Smoke test: resemblyzer voice embedding (OPTIONAL dependency).

Run:  cd backend && uv run python scripts/smoke_resemblyzer.py
Likely SKIPS on Python 3.13/Windows (webrtcvad has no wheels) — that is expected.
Revisit when Phase 1.4 (voice clone) lands.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.clients import resemblyzer_client as rc  # noqa: E402


def main() -> int:
    report = rc.availability_report()
    if not report["available"]:
        print(f"[SKIP] resemblyzer unavailable: {report['detail']}")
        print("       install with: uv sync --group voice (Python 3.11/3.12)")
        return 0

    print("[OK] resemblyzer imported")
    if len(sys.argv) < 2:
        print("[SKIP] no wav provided. Usage: smoke_resemblyzer.py path/to/audio.wav")
        return 0

    emb = rc.embed_wav(sys.argv[1])
    if emb is None:
        print("[FAIL] embed_wav returned None")
        return 1
    print(f"[OK] embedding dim={len(emb)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
