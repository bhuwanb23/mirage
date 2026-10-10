"""Tests for the Phase 5.3 scam graph (SQLite store, ring detection, stats)."""

from __future__ import annotations

import pytest

from app.models.schemas import IOCItem, ThreatIOCs
from app.services import scam_graph
from app.services.scam_graph import SQLiteGraphStore, node_id


@pytest.fixture
def store(tmp_path):
    s = SQLiteGraphStore(str(tmp_path / "graph.db"))
    yield s
    s.close()


def _iocs(*, phones=(), upis=(), domains=(), accounts=(), names=()) -> ThreatIOCs:
    return ThreatIOCs(
        phone_numbers=[IOCItem(value=p) for p in phones],
        upi_ids=[IOCItem(value=u) for u in upis],
        domains=[IOCItem(value=d) for d in domains],
        bank_accounts=[IOCItem(value=a) for a in accounts],
        scammer_names=list(names),
    )


class TestIngestion:
    def test_merge_is_idempotent(self, store):
        iocs = _iocs(phones=["9876543211"], upis=["sbi-safe@ybl"])
        store.ingest_iocs("RPT-1", iocs, scam_type="bank_kyc")
        stats1 = store.get_stats()
        store.ingest_iocs("RPT-1", iocs, scam_type="bank_kyc")
        stats2 = store.get_stats()
        assert stats1.phone_numbers == stats2.phone_numbers == 1
        assert stats1.upi_ids == stats2.upi_ids == 1

    def test_report_count_increments(self, store):
        for n in range(3):
            store.ingest_iocs(f"RPT-{n}", _iocs(phones=["9876543211"]))
        data = store.get_graph_data()
        node = next(n for n in data.nodes if n.type == "PhoneNumber")
        assert node.report_count == 3
        assert node.properties["is_verified_scammer"] is True  # 3+ reports

    def test_co_occurrence_linking(self, store):
        store.ingest_iocs(
            "RPT-1",
            _iocs(
                phones=["9876543211", "8765432109"],
                upis=["sbi-safe@ybl"],
                domains=["sbi-kyc-verify.xyz"],
                accounts=["1234567890123"],
            ),
        )
        data = store.get_graph_data()
        rels = {e.type for e in data.edges}
        assert "USES_UPI" in rels
        assert "LINKED_TO_DOMAIN" in rels
        assert "DEPOSITS_TO" in rels
        # both phones link to the same UPI -> shared infrastructure
        shared = store.shared_infrastructure()
        assert shared["shared_upis"][0]["upi_id"] == "sbi-safe@ybl"
        assert shared["shared_upis"][0]["phone_count"] == 2

    def test_scammer_name_owns_phone(self, store):
        store.ingest_iocs(
            "RPT-1", _iocs(phones=["9876543211"], names=["Officer Kumar"])
        )
        data = store.get_graph_data()
        types = {n.type for n in data.nodes}
        assert "ScammerName" in types
        assert "OWNS" in {e.type for e in data.edges}

    def test_report_node_created_with_type(self, store):
        store.ingest_iocs("RPT-9", _iocs(phones=["9876543211"]), scam_type="fedex")
        stats = store.get_stats()
        assert stats.scam_reports == 1
        assert stats.scam_type_counts == {"fedex": 1}


class TestRingDetection:
    def test_no_rings_on_empty_store(self, store):
        assert store.detect_rings() == []

    def test_no_ring_below_min_size(self, store):
        store.ingest_iocs("RPT-1", _iocs(phones=["9876543211"], upis=["sbi-safe@ybl"]))
        assert store.detect_rings(min_size=3) == []

    def test_ring_found_for_connected_cluster(self, store):
        # 3 phones + 1 UPI + 1 domain = 5-entity ring via co-occurrence.
        store.ingest_iocs(
            "RPT-1",
            _iocs(
                phones=["9876543211", "8765432109", "7654321098"],
                upis=["sbi-safe@ybl"],
                domains=["sbi-kyc-verify.xyz"],
            ),
        )
        rings = store.detect_rings(min_size=3)
        assert len(rings) == 1
        assert rings[0]["size"] == 5
        assert "sbi-safe@ybl" in rings[0]["upi_ids"]

    def test_report_nodes_excluded_from_rings(self, store):
        # Two separate 2-entity clusters linked only via report nodes: no ring.
        store.ingest_iocs("RPT-1", _iocs(phones=["9876543211"], upis=["a@ybl"]))
        store.ingest_iocs("RPT-2", _iocs(phones=["8765432109"], upis=["b@ybl"]))
        assert store.detect_rings(min_size=3) == []

    def test_ring_marks_nodes_in_graph_data(self, store):
        store.ingest_iocs(
            "RPT-1",
            _iocs(phones=["9876543211", "8765432109", "7654321098"], upis=["sbi-safe@ybl"]),
        )
        data = store.get_graph_data()
        assert all(n.in_ring for n in data.nodes)
        assert len({n.group for n in data.nodes}) == 1  # same ring group


class TestGraphData:
    def test_node_shape(self, store):
        store.ingest_iocs("RPT-1", _iocs(phones=["9876543211"]))
        data = store.get_graph_data()
        node = data.nodes[0]
        assert node.id == "phone:9876543211"
        assert node.label == "98765-43211"  # formatted for display
        assert node.type == "PhoneNumber"

    def test_limit_truncates(self, store):
        for n in range(10):
            store.ingest_iocs(f"RPT-{n}", _iocs(phones=[f"987654321{n}"]))
        data = store.get_graph_data(limit=3)
        assert len(data.nodes) == 3
        assert data.truncated is True

    def test_edges_reference_existing_nodes(self, store):
        store.ingest_iocs(
            "RPT-1", _iocs(phones=["9876543211"], upis=["sbi-safe@ybl"])
        )
        data = store.get_graph_data()
        ids = {n.id for n in data.nodes}
        for edge in data.edges:
            assert edge.source in ids and edge.target in ids

    def test_clear(self, store):
        store.ingest_iocs("RPT-1", _iocs(phones=["9876543211"]))
        store.clear()
        assert store.get_stats().phone_numbers == 0


class TestStatsAndFactory:
    def test_stats_counts(self, store):
        store.ingest_iocs(
            "RPT-1",
            _iocs(phones=["9876543211", "8765432109"], upis=["sbi-safe@ybl"]),
            scam_type="bank_kyc",
        )
        stats = store.get_stats()
        assert stats.phone_numbers == 2
        assert stats.upi_ids == 1
        assert stats.scam_reports == 1
        assert stats.backend == "sqlite"

    def test_factory_defaults_to_sqlite_without_neo4j(self, monkeypatch):
        from app.config import settings

        monkeypatch.setattr(settings, "neo4j_uri", "")
        monkeypatch.setattr(settings, "graph_db_path", ":memory:")
        scam_graph.reset_store()
        try:
            store = scam_graph.get_store()
            assert isinstance(store, SQLiteGraphStore)
        finally:
            scam_graph.reset_store()

    def test_new_report_id_format(self):
        rid = scam_graph.new_report_id()
        assert rid.startswith("RPT-") and len(rid) == 14


def test_seed_script_builds_demo_ring(tmp_path):
    """The §5.4 demo seed produces a visible ring + verified scammer flags."""
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from seed_graph import seed

    store = SQLiteGraphStore(str(tmp_path / "seed.db"))
    try:
        stats = seed(store)
        assert stats.phone_numbers == 8
        assert stats.upi_ids == 3
        assert stats.domains == 2
        assert stats.bank_accounts == 2
        assert stats.scam_reports == 8
        assert stats.rings >= 1

        shared = store.shared_infrastructure()
        assert any(s["upi_id"] == "sbi-safe@ybl" and s["phone_count"] >= 3
                   for s in shared["shared_upis"])

        data = store.get_graph_data()
        primary = next(n for n in data.nodes if n.id == node_id("PhoneNumber", "9876543210"))
        assert primary.properties["is_verified_scammer"] is True
    finally:
        store.close()
