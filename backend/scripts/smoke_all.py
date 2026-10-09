"""Run every backend smoke test in order. Prints a PASS/FAIL/SKIP summary.

Run:  cd backend && uv run python scripts/smoke_all.py
Exit code 0 = no failures (skips are allowed).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SCRIPTS = [
    "smoke_llm.py",
    "smoke_vision.py",
    "smoke_whisper.py",
    "smoke_tts.py",
    "smoke_ollama.py",
    "smoke_resemblyzer.py",
    "smoke_db.py",
]


def main() -> int:
    here = Path(__file__).parent
    results: list[tuple[str, int]] = []

    for name in SCRIPTS:
        print(f"\n=== {name} ===")
        proc = subprocess.run([sys.executable, str(here / name)], cwd=here.parent)
        results.append((name, proc.returncode))

    print("\n=== SUMMARY ===")
    failed = 0
    for name, code in results:
        status = "PASS" if code == 0 else f"FAIL({code})"
        if code != 0:
            failed += 1
        print(f"  {status:10} {name}")

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
