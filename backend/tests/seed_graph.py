"""Seed the scam graph with the plan §5.4 demo ring (Delhi-NCR KYC scam).

Run:   cd backend && uv run python tests/seed_graph.py
Idempotent: re-running merges (does not duplicate) thanks to MERGE semantics.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services import scam_graph  # noqa: E402
from app.services.graph_seed import seed  # noqa: E402

if __name__ == "__main__":
    store = scam_graph.get_store()
    stats = seed(store)
    print(f"Seeded demo ring. Stats: {stats.model_dump()}")
    print(f"Rings detected: {len(store.detect_rings(min_size=3))}")
