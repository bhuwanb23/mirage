"""API tests for the Phase 5.1-5.3 honeypot router (simulate mode, no live LLM)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import scam_graph


@pytest.fixture
def client(tmp_path, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "graph_db_path", str(tmp_path / "graph.db"))
    monkeypatch.setattr(settings, "neo4j_uri", "")
    scam_graph.reset_store()
    # Isolate the in-process session store per test.
    from app.routers import honeypot

    honeypot.SESSIONS.clear()
    with TestClient(app) as c:
        yield c
    honeypot.SESSIONS.clear()
    scam_graph.reset_store()


def _turn(client, message, session_id=None, mode="simulate"):
    if session_id is None:
        payload = {"scammer_message": message, "persona": "ramesh", "mode": mode}
        return client.post("/honeypot/start", json=payload)
    payload = {"session_id": session_id, "scammer_message": message, "mode": mode}
    return client.post("/honeypot/continue", json=payload)


class TestStartAndContinue:
    def test_start_returns_in_character_reply(self, client):
        resp = _turn(
            client, "Hello, this is from SBI fraud department. Your account is compromised."
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["session_id"].startswith("hp-")
        assert body["conversation_health"] == "engaged"
        assert body["messages_in_session"] == 2
        assert len(body["reply"]) > 20
        assert "ai" not in body["reply"].lower().split()

    def test_continue_uses_same_session(self, client):
        first = _turn(client, "Your KYC is incomplete.").json()
        sid = first["session_id"]
        resp = _turn(client, "Transfer ₹50,000 to sbi-safe@ybl now!", session_id=sid)
        assert resp.status_code == 200
        assert resp.json()["session_id"] == sid
        assert resp.json()["messages_in_session"] == 4

    def test_continue_unknown_session_404(self, client):
        resp = _turn(client, "hello", session_id="hp-doesnotexist")
        assert resp.status_code == 404

    def test_empty_message_422(self, client):
        resp = client.post("/honeypot/start", json={"scammer_message": "   "})
        assert resp.status_code == 422


class TestIOCExtractionAcrossTurns:
    def test_upi_and_phone_extracted(self, client):
        resp = _turn(
            client,
            "Transfer to sbi-safe@ybl and call me on 9876543211",
        )
        body = resp.json()
        assert "sbi-safe@ybl" in body["iocs_extracted_this_turn"]["upi_ids"]
        assert "9876543211" in body["iocs_extracted_this_turn"]["phone_numbers"]
        assert body["total_iocs_extracted"] >= 2

    def test_iocs_accumulate_and_deduplicate(self, client):
        sid = _turn(client, "my upi is sbi-safe@ybl").json()["session_id"]
        body = _turn(client, "again, sbi-safe@ybl only", session_id=sid).json()
        # deduped: still exactly one UPI
        assert body["total_iocs_extracted"] == 1

    def test_fraudulent_url_becomes_domain_ioc(self, client):
        body = _turn(client, "open https://sbi-kyc-verify.xyz/update now").json()
        assert any("sbi-kyc-verify.xyz" in u for u in body["iocs_extracted_this_turn"]["urls"])


class TestConversationHealth:
    def test_frustrated_scammer(self, client):
        body = _turn(client, "JUST DO IT!!! are you stupid?").json()
        assert body["conversation_health"] == "frustrated"

    def test_hangup_threat(self, client):
        body = _turn(client, "I am disconnecting, useless").json()
        assert body["conversation_health"] == "about_to_hang_up"


class TestGraphIngestion:
    def test_turn_ingests_iocs_into_graph(self, client):
        _turn(client, "pay 9876543211 via sbi-safe@ybl")
        stats = client.get("/graph/stats").json()
        assert stats["phone_numbers"] >= 1
        assert stats["upi_ids"] >= 1
        assert stats["scam_reports"] >= 1

    def test_repeated_iocs_bump_report_count(self, client):
        sid = _turn(client, "call 9876543211").json()["session_id"]
        _turn(client, "again 9876543211", session_id=sid)
        _turn(client, "still 9876543211", session_id=sid)
        data = client.get("/graph/data").json()
        node = next(n for n in data["nodes"] if n["id"] == "phone:9876543211")
        assert node["report_count"] >= 3
        assert node["properties"]["is_verified_scammer"] is True


class TestSessionEndpoint:
    def test_full_log(self, client):
        sid = _turn(client, "send money to sbi-safe@ybl").json()["session_id"]
        _turn(client, "okay done", session_id=sid)
        body = client.get(f"/honeypot/session/{sid}").json()
        assert body["session_id"] == sid
        assert [m["role"] for m in body["messages"]] == ["scammer", "ramesh", "scammer", "ramesh"]
        assert body["iocs"]["upi_ids"][0]["value"] == "sbi-safe@ybl"
        assert body["total_time_wasted_seconds"] > 0

    def test_missing_session_404(self, client):
        assert client.get("/honeypot/session/hp-nope").status_code == 404


def test_scripted_demo_endpoint(client):
    body = client.get("/honeypot/scripted").json()
    assert len(body["messages"]) >= 8
    roles = {m["role"] for m in body["messages"]}
    assert roles == {"scammer", "ramesh"}
    assert "sbi-safe@ybl" in body["ioc_highlights"]
