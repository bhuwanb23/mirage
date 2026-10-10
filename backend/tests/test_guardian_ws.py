"""Tests for the Guardian WebSocket (Phase 4.1 / 4.2 / 4.4).

Fully offline: simulation-mode text frames drive the stage tracker, the
LLM classifier is patched to raise (exercising rule-based fallback), and
audio frames exercise the degradation path (no GROQ key → skipped).
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import stage_tracker as st
from app.services.transcription_stream import whisper_available


@pytest.fixture(autouse=True)
def no_llm(monkeypatch):
    """Force rule-based classification — no network in tests."""
    def boom(*_args, **_kwargs):
        raise RuntimeError("LLM disabled in tests")

    monkeypatch.setattr(st, "classify_llm", boom)


@pytest.fixture
def ws_client():
    return TestClient(app).websocket_connect("/guardian/stream")


def recv(ws) -> dict:
    return json.loads(ws.receive_text())


def recv_until(ws, msg_type: str) -> dict:
    """Drain messages until the wanted type arrives (voice frames interleave)."""
    for _ in range(12):
        message = recv(ws)
        if message["type"] == msg_type:
            return message
    raise AssertionError(f"did not receive a {msg_type!r} message")


SCRIPTS = {
    "hook": "Hello, is this Priya Sharma? You've been selected for an exclusive offer.",
    "authority": "This is Officer Rajesh from the SBI fraud department, "
                 "part of an RBI circular investigation by the cyber cell.",
    "isolation": "Do not tell anyone about this call. This is confidential. "
                 "Don't disconnect and don't inform your family.",
    "urgency": "Your account will be blocked within 30 minutes. Act immediately, "
               "this is your last chance or legal action tonight.",
    "payment": "Share the OTP and ATM PIN. Transfer ₹50,000 to this UPI now. "
               "Scan this QR code immediately.",
    "none": "Hi mom, I'll be home around 7. Should I pick up bread on the way?",
}


# ---------------------------------------------------------------------------
# Protocol basics
# ---------------------------------------------------------------------------
class TestProtocol:
    def test_ready_handshake(self, ws_client):
        with ws_client as ws:
            ws.send_text(json.dumps({"type": "init", "mode": "sim", "language": "en"}))
            ready = recv(ws)
            assert ready["type"] == "ready"
            assert ready["mode"] == "sim"
            assert ready["session_id"]
            assert "whisper_available" in ready
            assert "voice_method" in ready
            assert ready["scam_keywords"]

    def test_first_message_must_be_init(self, ws_client):
        with ws_client as ws:
            ws.send_text(json.dumps({"type": "ping"}))
            message = recv(ws)
            assert message["type"] == "error"

    def test_invalid_json_first_message(self, ws_client):
        with ws_client as ws:
            ws.send_text("not json at all")
            message = recv(ws)
            assert message["type"] == "error"

    def test_ping_pong_heartbeat(self, ws_client):
        with ws_client as ws:
            ws.send_text(json.dumps({"type": "init", "mode": "sim"}))
            recv(ws)  # ready
            ws.send_text(json.dumps({"type": "ping"}))
            pong = recv(ws)
            assert pong["type"] == "pong"

    def test_unknown_frame_type_errors_but_stays_open(self, ws_client):
        with ws_client as ws:
            ws.send_text(json.dumps({"type": "init", "mode": "sim"}))
            recv(ws)
            ws.send_text(json.dumps({"type": "weird"}))
            assert recv(ws)["type"] == "error"
            # connection still usable
            ws.send_text(json.dumps({"type": "ping"}))
            assert recv(ws)["type"] == "pong"


# ---------------------------------------------------------------------------
# Simulation mode — stage pipeline
# ---------------------------------------------------------------------------
def init_sim(ws) -> dict:
    ws.send_text(json.dumps({"type": "init", "mode": "sim", "language": "en"}))
    return recv(ws)


class TestSimStagePipeline:
    def test_text_frame_produces_transcription_then_stage_update(self, ws_client):
        with ws_client as ws:
            init_sim(ws)
            ws.send_text(json.dumps({"type": "text", "text": SCRIPTS["hook"]}))
            transcription = recv_until(ws, "transcription")
            assert transcription["source"] == "sim"
            assert transcription["text"] == SCRIPTS["hook"]
            stage = recv_until(ws, "stage_update")
            assert stage["current_stage"] in (
                "hook", "authority", "isolation", "urgency", "payment",
            )
            assert "transcript_so_far" in stage

    def test_full_scam_script_reaches_payment_and_critical(self, ws_client):
        with ws_client as ws:
            init_sim(ws)
            stages_seen = []
            for key in ("hook", "authority", "isolation", "urgency", "payment"):
                ws.send_text(json.dumps({"type": "text", "text": SCRIPTS[key]}))
                transcription = recv_until(ws, "transcription")
                assert transcription["text"] == SCRIPTS[key]
                stage = recv_until(ws, "stage_update")
                stages_seen.append(stage["current_stage"])
            # forward-only: monotonic non-decreasing ranks
            order = ["none", "hook", "authority", "isolation", "urgency", "payment"]
            ranks = [order.index(s) for s in stages_seen]
            assert ranks == sorted(ranks)
            assert stages_seen[-1] == "payment"
            assert stage["alert_level"] == "critical"
            assert "HANG UP" in stage["alert_message"]

    def test_legitimate_script_stays_safe(self, ws_client):
        with ws_client as ws:
            init_sim(ws)
            ws.send_text(json.dumps({"type": "text", "text": SCRIPTS["none"]}))
            stage = recv_until(ws, "stage_update")
            assert stage["current_stage"] == "none"
            assert stage["alert_level"] == "safe"

    def test_sim_voice_injection_raises_voice_and_double_alert(self, ws_client):
        with ws_client as ws:
            init_sim(ws)
            ws.send_text(json.dumps({"type": "sim_voice", "score": 0.72}))
            voice = recv(ws)
            assert voice["type"] == "voice_update"
            assert voice["synthetic_score"] == 0.72
            assert voice["method"] == "simulated"
            # Drive to urgency → combined alert must be critical
            for key in ("authority", "isolation", "urgency"):
                ws.send_text(json.dumps({"type": "text", "text": SCRIPTS[key]}))
                stage = recv_until(ws, "stage_update")
            assert stage["current_stage"] == "urgency"
            assert stage["alert_level"] == "critical"
            assert "CONFIRMED SCAM" in stage["alert_message"]

    def test_end_sends_summary(self, ws_client):
        with ws_client as ws:
            init_sim(ws)
            for key in ("hook", "urgency"):
                ws.send_text(json.dumps({"type": "text", "text": SCRIPTS[key]}))
                recv_until(ws, "stage_update")
            ws.send_text(json.dumps({"type": "end"}))
            summary = recv_until(ws, "summary")
            assert summary["highest_stage"] == "urgency"
            assert "verdict" in summary
            assert summary["chunks"] == 2
            assert summary["mode"] == "sim"


# ---------------------------------------------------------------------------
# Audio mode degradation (no GROQ key in tests)
# ---------------------------------------------------------------------------
class TestAudioDegradation:
    def test_garbage_audio_skips_transcription_but_keeps_session(self, ws_client):
        with ws_client as ws:
            ws.send_text(json.dumps({"type": "init", "mode": "audio"}))
            ready = recv(ws)
            assert ready["type"] == "ready"
            ws.send_bytes(b"this-is-not-audio")
            # Without a GROQ key the chunk is skipped, voice still degrades
            # gracefully, and the session stays alive.
            if whisper_available():
                pytest.skip("GROQ key present")
            skipped = recv_until(ws, "transcription_skipped")
            assert skipped["reason"] == "whisper_unavailable"
            recv_until(ws, "voice_update")
            ws.send_text(json.dumps({"type": "ping"}))
            assert recv(ws)["type"] == "pong"

    @pytest.mark.skipif(
        whisper_available(),
        reason="GROQ key present — skip unavailable-path test",
    )
    def test_audio_without_key_reports_unavailable(self, ws_client):
        with ws_client as ws:
            ws.send_text(json.dumps({"type": "init", "mode": "audio"}))
            recv(ws)
            ws.send_bytes(b"\x00\x01\x02")
            skipped = recv_until(ws, "transcription_skipped")
            assert skipped["reason"] == "whisper_unavailable"
