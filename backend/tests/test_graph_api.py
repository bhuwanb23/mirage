"""API tests for the Phase 5.3-5.5 graph/map router."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import scam_graph

sys.path.insert(0, str(Path(__file__).resolve().parent))
from seed_graph import seed  # noqa: E402


@pytest.fixture
def client(tmp_path, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "graph_db_path", str(tmp_path / "graph.db"))
    monkeypatch.setattr(settings, "neo4j_uri", "")
    scam_graph.reset_store()
    with TestClient(app) as c:
        yield c
    scam_graph.reset_store()


@pytest.fixture
def seeded_client(client):
    seed(scam_graph.get_store())
    return client


def test_graph_data_shape(seeded_client):
    body = seeded_client.get("/graph/data").json()
    assert len(body["nodes"]) > 0
    node = body["nodes"][0]
    for key in ("id", "label", "type", "group", "report_count", "in_ring", "properties"):
        assert key in node
    edge = body["edges"][0]
    assert {"source", "target", "type"} <= set(edge)


def test_graph_data_limit(seeded_client):
    body = seeded_client.get("/graph/data?limit=5").json()
    assert len(body["nodes"]) <= 5


def test_graph_stats(seeded_client):
    body = seeded_client.get("/graph/stats").json()
    assert body["phone_numbers"] == 8
    assert body["upi_ids"] == 3
    assert body["domains"] == 2
    assert body["bank_accounts"] == 2
    assert body["rings"] >= 1
    assert body["backend"] == "sqlite"
    assert body["scam_type_counts"]["bank_kyc"] >= 1


def test_graph_stats_empty(client):
    body = client.get("/graph/stats").json()
    assert body["phone_numbers"] == 0
    assert body["rings"] == 0


def test_graph_rings(seeded_client):
    body = seeded_client.get("/graph/rings").json()
    assert len(body["rings"]) >= 1
    ring = body["rings"][0]
    assert ring["size"] >= 3
    assert len(ring["phones"]) >= 2
    shared = body["shared"]
    assert any(s["upi_id"] == "sbi-safe@ybl" and s["phone_count"] >= 3
               for s in shared["shared_upis"])


def test_map_heatmap_shape(client):
    body = client.get("/map/heatmap").json()
    assert len(body["cities"]) == 10
    delhi = next(c for c in body["cities"] if c["city"] == "Delhi")
    assert delhi["scam_count"] == 47
    assert delhi["top_type"] == "bank_kyc"
    assert delhi["intensity"] == 0.9
    assert body["national_stats"]["total_reports_this_week"] >= 202


def test_map_heatmap_enriched_by_live_reports(seeded_client):
    body = seeded_client.get("/map/heatmap").json()
    # live reports (8) < demo total, but graph ring count is surfaced
    assert body["national_stats"]["graph_rings_detected"] >= 1
