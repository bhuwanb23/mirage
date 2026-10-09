"""Smoke test: Supabase + Neo4j connectivity.

Run:  cd backend && uv run python scripts/smoke_db.py
Each database skips cleanly when its env vars are missing.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.clients import neo4j_client, supabase_client  # noqa: E402
from app.config import settings  # noqa: E402


def check_supabase() -> int:
    if not settings.supabase_url or not settings.supabase_anon_key:
        print("[SKIP] Supabase: SUPABASE_URL / SUPABASE_ANON_KEY not set")
        return 0
    client = supabase_client.init_supabase()
    if client is None:
        print("[FAIL] Supabase init failed (see logs above)")
        return 1
    try:
        client.table("users").select("id").limit(1).execute()
        print("[OK] Supabase connected + 'users' table readable")
        return 0
    except Exception as exc:
        print(f"[FAIL] Supabase query failed (did you run backend/db/001_init_tables.sql?): {exc}")
        return 1


def check_neo4j() -> int:
    if not settings.neo4j_uri:
        print("[SKIP] Neo4j: NEO4J_URI not set")
        return 0
    driver = neo4j_client.init_neo4j()
    if driver is None:
        print("[FAIL] Neo4j init failed (see logs above)")
        return 1
    try:
        records = neo4j_client.run_query("MATCH (n) RETURN count(n) AS c")
        print(f"[OK] Neo4j connected, node count = {records[0]['c'] if records else 0}")
        return 0
    except Exception as exc:
        print(
            "[FAIL] Neo4j query failed "
            f"(did you run backend/db/002_neo4j_constraints.cypher?): {exc}"
        )
        return 1
    finally:
        neo4j_client.close_neo4j()


def main() -> int:
    return max(check_supabase(), check_neo4j())


if __name__ == "__main__":
    raise SystemExit(main())
