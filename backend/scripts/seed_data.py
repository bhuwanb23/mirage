"""Seed data script (plan §7.3) — populate the demo dataset before a demo.

What it seeds:
  * Scam graph: the full §7.3 dataset (15 phones, 8 UPI IDs, 6 domains,
    4 bank accounts, 30+ edges, 12 scam reports) — written directly to the
    graph store (SQLite file or Neo4j, whichever is configured).
  * In-process demo data (Priya profile, drill history 25 -> 42 -> 67,
    12 dashboard events, "Sharma Family" handshake) is seeded automatically
    by the backend at startup (MIRAGE_SEED_DEMO=1, the default). This script
    seeds it too when run with --in-process, which is only useful for tests.

After seeding it runs ring detection and prints stats — the plan's
"verify the graph is correct" step.

Run:
    cd backend && uv run python scripts/seed_data.py
    uv run python scripts/seed_data.py --verify   # also check a running API

Idempotent: re-running merges (MERGE semantics), never duplicates.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services import scam_graph  # noqa: E402
from app.services.graph_seed import seed_full  # noqa: E402


def _print_stats(stats) -> None:
    data = stats.model_dump() if hasattr(stats, "model_dump") else dict(stats)
    print("\nGraph stats after seeding:")
    for key in (
        "phone_numbers",
        "upi_ids",
        "domains",
        "bank_accounts",
        "scam_reports",
        "rings",
    ):
        print(f"  {key:15} {data.get(key)}")
    print(f"  {'backend':15} {data.get('backend')}")


def _verify_api(base_url: str) -> int:
    """Hit a running backend and confirm the demo data is visible."""
    checks = [
        ("/health", lambda b: b.get("status") in ("ok", "healthy")),
        ("/graph/stats", lambda b: (b.get("phone_numbers") or 0) >= 15),
        ("/graph/rings", lambda b: len(b.get("rings") or []) >= 1),
        ("/map/heatmap", lambda b: len(b.get("cities") or []) == 10),
        (
            "/drill/score/7f3a9c1e-5d2b-4f8a-9e6c-1b8d4a7f2c9e",
            lambda b: b.get("current_score") == 67 and b.get("drills_completed") == 3,
        ),
    ]
    failures = 0
    print(f"\nVerifying running API at {base_url} ...")
    for path, ok in checks:
        try:
            with urllib.request.urlopen(base_url.rstrip("/") + path, timeout=5) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            passed = bool(ok(body))
        except Exception as exc:  # noqa: BLE001
            print(f"  FAIL  {path}  ({exc})")
            failures += 1
            continue
        print(f"  {'PASS' if passed else 'FAIL'}  {path}")
        if not passed:
            failures += 1
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed the Mirage demo dataset (plan §7.3)")
    parser.add_argument(
        "--in-process",
        action="store_true",
        help="also seed drill/report/family stores in THIS process (tests only — "
        "a running server seeds them itself at startup)",
    )
    parser.add_argument(
        "--verify",
        metavar="URL",
        default=None,
        help="verify a running backend after seeding (e.g. http://localhost:8000)",
    )
    args = parser.parse_args()

    store = scam_graph.get_store()
    stats = seed_full(store)
    _print_stats(stats)

    rings = store.detect_rings(min_size=3)
    print(f"\nRing detection: {len(rings)} ring(s) found")
    shared = store.shared_infrastructure(min_phones=2)
    for s in shared.get("shared_upis", [])[:3]:
        print(f"  mule UPI {s['upi_id']} shared by {s['phone_count']} phones")
    if not rings:
        print("  ERROR: expected at least one ring — seeding failed")
        return 1

    if args.in_process:
        from app.services.demo_seed import seed_demo

        print("\nIn-process demo seed:", seed_demo())

    failures = 0
    if args.verify:
        failures = _verify_api(args.verify)
        if failures:
            print(f"\n{failures} verification check(s) failed")
            return 1
        print("\nAll API checks passed. Demo data is live.")

    print("\nNote: profile/drills/family seed in the SERVER process at startup")
    print("(MIRAGE_SEED_DEMO=1). Restart the backend to refresh them.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
