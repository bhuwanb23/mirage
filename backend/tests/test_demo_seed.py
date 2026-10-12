"""Tests for the Phase 7.3 demo seeds (graph seed_full + in-process demo_seed)."""

from __future__ import annotations

import pytest

from app.services import demo_seed, recent_activity
from app.services.drill_store import get_history, get_score
from app.services.drill_store import reset as reset_drill_store
from app.services.memory_handshake import InMemoryStore, set_store
from app.services.scam_graph import SQLiteGraphStore, node_id


@pytest.fixture
def store(tmp_path):
    s = SQLiteGraphStore(str(tmp_path / "graph.db"))
    yield s
    s.close()


@pytest.fixture(autouse=True)
def _isolated_stores():
    """Keep the in-process stores clean around every demo-seed test."""
    reset_drill_store()
    recent_activity.clear()
    set_store(InMemoryStore())
    yield
    reset_drill_store()
    recent_activity.clear()
    set_store(None)


class TestSeedFull:
    def test_meets_plan_73_counts(self, store):
        """Plan §7.3: 15 phones, 8 UPIs, 6 domains, 4 accounts, 12 reports."""
        from app.services.graph_seed import seed_full

        stats = seed_full(store)
        assert stats.phone_numbers == 15
        assert stats.upi_ids == 8
        assert stats.domains == 6
        assert stats.bank_accounts == 4
        assert stats.scam_reports >= 12  # 8 (5.4) + 12 (7.3) = 20 total
        assert stats.rings >= 1

    def test_mule_upi_shared_by_four_phones(self, store):
        """The demo talking point: one UPI ID links 4 phones (mule account)."""
        from app.services.graph_seed import seed_full

        seed_full(store)
        shared = store.shared_infrastructure()
        mule = next(s for s in shared["shared_upis"] if s["upi_id"] == "sbi-safe@ybl")
        assert mule["phone_count"] >= 4

    def test_idempotent(self, store):
        from app.services.graph_seed import seed_full

        s1 = seed_full(store)
        s2 = seed_full(store)
        assert (s1.phone_numbers, s1.upi_ids, s1.domains) == (
            s2.phone_numbers,
            s2.upi_ids,
            s2.domains,
        )

    def test_sbi_safe_deposits_to_sbi_account(self, store):
        from app.services.graph_seed import seed_full

        seed_full(store)
        data = store.get_graph_data()
        edge_pairs = {(e.source, e.target) for e in data.edges}
        assert (
            node_id("UPI_ID", "sbi-safe@ybl"),
            node_id("BankAccount", "1234567890123"),
        ) in edge_pairs


class TestDemoSeed:
    def test_seeds_priya_profile_and_drills(self):
        results = demo_seed.seed_demo()
        assert results["profile_and_drills"] is True

        history = get_history(demo_seed.DEMO_USER_ID)
        assert len(history) == 3
        assert [r["score_after"] for r in history] == [25, 42, 67]
        assert get_score(demo_seed.DEMO_USER_ID) == 67

    def test_seeds_reports_and_family(self):
        results = demo_seed.seed_demo()
        assert results["reports"] is True
        assert results["family"] is True

        events = recent_activity.list_recent(limit=20)
        demo_events = [e for e in events if e["summary"].startswith("[demo]")]
        assert len(demo_events) == 12

        from app.services import memory_handshake as mem

        status = mem.family_status(demo_seed.DEMO_USER_ID)
        assert status["linked"] is True
        assert status["name"] == "Sharma Family"
        assert status["member_count"] >= 3
        assert status["handshake_ready"] is True
        assert status["has_totp"] is True

    def test_idempotent(self):
        first = demo_seed.seed_demo()
        second = demo_seed.seed_demo()
        assert any(first.values()) is True
        assert all(second.values()) is False
        assert len(get_history(demo_seed.DEMO_USER_ID)) == 3

    def test_score_endpoint_shape(self):
        """The seeded user flows through the real /drill/score endpoint."""
        from fastapi.testclient import TestClient

        from app.main import app

        demo_seed.seed_demo()
        with TestClient(app) as client:
            body = client.get(f"/drill/score/{demo_seed.DEMO_USER_ID}").json()
        assert body["current_score"] == 67
        assert body["drills_completed"] == 3
        assert [h["score"] for h in body["history"]] == [25, 42, 67]
        assert body["label"] == "Resilient"


class TestRecentActivityTimestamp:
    def test_created_at_override(self):
        recent_activity.record_analyze(
            is_scam=True,
            scam_type="bank_kyc",
            confidence=0.9,
            created_at="2026-10-01T10:00:00+00:00",
        )
        event = recent_activity.list_recent(limit=1)[0]
        assert event["created_at"] == "2026-10-01T10:00:00+00:00"

    def test_defaults_to_now(self):
        recent_activity.record_analyze(
            is_scam=False, scam_type=None, confidence=0.5
        )
        event = recent_activity.list_recent(limit=1)[0]
        assert event["created_at"]  # non-empty ISO timestamp
