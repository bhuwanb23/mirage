"""Guardian WebSocket router — Phase 4.1 / 4.2 / 4.4 live pipeline.

Endpoint:  WS /guardian/stream

Protocol
--------
Client → server:
  {"type":"init", "session_id"?, "language"?, "mode"?, "user_id"?"}   first msg
  <binary bytes>                    audio chunk (4 s webm/opus)
  {"type":"text", "text": "..."}    simulation-mode transcript chunk
  {"type":"sim_voice", "score":0.7} simulation-mode voice score injection
  {"type":"ping"}                   heartbeat (Render kills idle sockets)
  {"type":"end"}                    graceful stop → server sends summary

Server → client:
  {"type":"ready", ...}                session initialized
  {"type":"transcription", ...}        new transcript text (whisper or sim)
  {"type":"transcription_skipped",...} chunk dropped (rate limit / no key)
  {"type":"stage_update", ...}         stage machine + alert decision
  {"type":"voice_update", ...}         synthetic-voice score
  {"type":"summary", ...}              call summary after "end"
  {"type":"pong"}                      heartbeat reply
  {"type":"error", ...}                protocol violation (non-fatal)

Degradation: Whisper unconfigured → audio chunks produce
`transcription_skipped` and the session keeps running (sim text still
classifies). Voice analysis degrades to signal-based / unavailable.
LLM classifier falls back to rules per chunk.

Run:  uv run uvicorn app.main:app --reload --port 8000
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import tempfile
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.config import settings
from app.services.stage_tracker import SCAM_HIGHLIGHT_WORDS, StageTracker, new_tracker
from app.services.transcription_stream import transcribe_file, whisper_available
from app.services.voice_authenticity import VoiceAuthenticityAnalyzer

logger = logging.getLogger("mirage.guardian")

router = APIRouter(tags=["guardian"])

CHUNK_SECONDS = 4.0  # browser records 4 s slices (plan §4.1)

# Active sessions — lives for the process; the frontend never sees it.
ACTIVE_SESSIONS: dict[str, "GuardianSession"] = {}


@dataclass
class GuardianSession:
    """All per-call state (plan §4.1 step 2)."""

    session_id: str
    mode: str = "audio"  # audio | sim
    language: str = "auto"
    user_id: Optional[str] = None
    started_at: float = field(default_factory=time.monotonic)
    transcript: str = ""
    chunk_count: int = 0
    tracker: StageTracker = field(default_factory=new_tracker)
    voice: VoiceAuthenticityAnalyzer = field(default_factory=VoiceAuthenticityAnalyzer)
    sim_voice_score: Optional[float] = None  # injected in sim mode
    transcription_unavailable_notified: bool = False

    @property
    def elapsed(self) -> float:
        return time.monotonic() - self.started_at

    @property
    def voice_score(self) -> float:
        if self.sim_voice_score is not None:
            return self.sim_voice_score
        if self.voice.chunks_analyzed >= 3:
            return self.voice.last_score
        return 0.0


async def _send(ws: WebSocket, payload: dict[str, Any]) -> None:
    try:
        await ws.send_text(json.dumps(payload, ensure_ascii=False))
    except Exception:  # noqa: BLE001 — client vanished mid-send
        logger.debug("send failed (client gone)", exc_info=True)


def _timestamp_range(elapsed: float, span: float = CHUNK_SECONDS) -> str:
    def mmss(seconds: float) -> str:
        seconds = max(0, int(seconds))
        return f"{seconds // 60}:{seconds % 60:02d}"

    return f"{mmss(elapsed - span)}-{mmss(elapsed)}"


def _write_chunk_temp(data: bytes, ext: str = ".webm") -> str:
    fd, path = tempfile.mkstemp(suffix=ext, prefix="guardian_ws_")
    with os.fdopen(fd, "wb") as f:
        f.write(data)
    return path


# ---------------------------------------------------------------------------
# Message handlers
# ---------------------------------------------------------------------------
async def _handle_init(ws: WebSocket, raw: str) -> GuardianSession:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        await _send(ws, {"type": "error", "error": "first message must be init JSON"})
        raise WebSocketDisconnect(code=1008)
    if data.get("type") != "init":
        await _send(ws, {"type": "error", "error": "first message must be type=init"})
        raise WebSocketDisconnect(code=1008)

    mode = data.get("mode", "audio")
    if mode not in ("audio", "sim"):
        mode = "audio"
    language = str(data.get("language") or "auto")

    session = GuardianSession(
        session_id=str(data.get("session_id") or uuid.uuid4()),
        mode=mode,
        language=language,
        user_id=str(data["user_id"]) if data.get("user_id") else None,
    )
    ACTIVE_SESSIONS[session.session_id] = session

    await _send(
        ws,
        {
            "type": "ready",
            "session_id": session.session_id,
            "mode": session.mode,
            "language": session.language,
            "whisper_available": whisper_available(),
            "voice_method": session.voice.method,
            "llm_providers": settings.available_llm_providers,
            "scam_keywords": SCAM_HIGHLIGHT_WORDS,
            "server_time": int(time.time()),
        },
    )
    logger.info(
        "guardian session started",
        extra={"session_id": session.session_id, "mode": mode, "language": language},
    )
    return session


async def _handle_audio_chunk(ws: WebSocket, session: GuardianSession, data: bytes) -> None:
    seq = session.chunk_count
    session.chunk_count += 1

    if not data:
        return

    path = _write_chunk_temp(data)
    language = None if session.language == "auto" else session.language
    try:
        # Both stages run in threads — they are blocking (ffmpeg / Groq).
        transcription, voice_update = await asyncio.gather(
            asyncio.to_thread(transcribe_file, path, seq, language),
            asyncio.to_thread(session.voice.analyze_chunk, path),
        )
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass

    # -- transcription ---------------------------------------------------
    if transcription.available and transcription.is_usable:
        session.transcript = f"{session.transcript} {transcription.text}".strip()
        await _send(
            ws,
            {
                "type": "transcription",
                "chunk_id": seq,
                "text": transcription.text,
                "timestamp": _timestamp_range(session.elapsed),
                "language": session.language,
                "source": "whisper",
                "transcript_so_far": session.transcript,
            },
        )
    elif transcription.error and transcription.error != "empty_chunk":
        reason = transcription.error
        if not session.transcription_unavailable_notified or reason == "rate_limited":
            session.transcription_unavailable_notified = True
            await _send(
                ws,
                {
                    "type": "transcription_skipped",
                    "chunk_id": seq,
                    "reason": reason,
                    "message": (
                        "Transcription rate-limited — chunk skipped."
                        if reason == "rate_limited"
                        else "Transcription unavailable — use Simulation mode text input."
                    ),
                },
            )

    # -- voice authenticity ------------------------------------------------
    if voice_update is not None:
        await _send(ws, voice_update.to_payload())

    # -- stage classification --------------------------------------------
    # Classify only when this chunk produced text; otherwise re-evaluate the
    # last known state against the current voice score (cheap, no LLM).
    chunk_text = transcription.text if transcription.is_usable else ""
    update = session.tracker.process(
        chunk_text=chunk_text,
        transcript=session.transcript,
        elapsed_seconds=session.elapsed,
        voice_synthetic=session.voice_score,
        skip_classification=not chunk_text,
    )
    if chunk_text or update.alert_level != "safe":
        await _send(ws, update.to_payload())


async def _handle_text_frame(ws: WebSocket, session: GuardianSession, data: dict) -> None:
    """Simulation mode: text frames stand in for transcribed audio."""
    text = str(data.get("text") or "").strip()
    if not text:
        return
    session.chunk_count += 1
    session.transcript = f"{session.transcript} {text}".strip()

    await _send(
        ws,
        {
            "type": "transcription",
            "chunk_id": session.chunk_count - 1,
            "text": text,
            "timestamp": _timestamp_range(session.elapsed),
            "language": session.language,
            "source": "sim",
            "transcript_so_far": session.transcript,
        },
    )

    update = session.tracker.process(
        chunk_text=text,
        transcript=session.transcript,
        elapsed_seconds=session.elapsed,
        voice_synthetic=session.voice_score,
    )
    await _send(ws, update.to_payload())

    # Keep the voice meter live in sim mode as well.
    if session.sim_voice_score is not None:
        await _send(
            ws,
            {
                "type": "voice_update",
                "synthetic_score": round(session.sim_voice_score, 3),
                "label": _sim_voice_label(session.sim_voice_score),
                "chunks_analyzed": session.chunk_count,
                "ready": session.chunk_count >= 3,
                "available": True,
                "method": "simulated",
            },
        )


def _sim_voice_label(score: float) -> str:
    from app.services.voice_authenticity import label_for

    return label_for(score)


async def _handle_control(ws: WebSocket, session: GuardianSession, data: dict) -> None:
    kind = data.get("type")

    if kind == "ping":
        await _send(ws, {"type": "pong", "server_time": int(time.time())})
        return

    if kind == "sim_voice":
        try:
            score = float(data.get("score", 0.0))
        except (TypeError, ValueError):
            score = 0.0
        session.sim_voice_score = max(0.0, min(1.0, score))
        await _send(
            ws,
            {
                "type": "voice_update",
                "synthetic_score": round(session.sim_voice_score, 3),
                "label": _sim_voice_label(session.sim_voice_score),
                "chunks_analyzed": session.chunk_count,
                "ready": session.chunk_count >= 3,
                "available": True,
                "method": "simulated",
            },
        )
        return

    if kind == "end":
        summary = session.tracker.summary(session.transcript, session.elapsed)
        summary.update(
            {
                "chunks": session.chunk_count,
                "voice_score": round(session.voice_score, 3),
                "mode": session.mode,
            }
        )
        await _send(ws, summary)
        ACTIVE_SESSIONS.pop(session.session_id, None)
        logger.info(
            "guardian session ended",
            extra={
                "session_id": session.session_id,
                "duration_s": round(session.elapsed, 1),
                "highest_stage": summary["highest_stage"],
            },
        )
        return

    await _send(ws, {"type": "error", "error": f"unknown message type: {kind}"})


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------
@router.websocket("/guardian/stream")
async def guardian_stream(ws: WebSocket) -> None:
    """Live Guardian pipeline — audio chunks or simulation text frames."""
    await ws.accept()
    session: Optional[GuardianSession] = None
    try:
        first = await ws.receive()
        if first.get("type") == "websocket.disconnect":
            return
        session = await _handle_init(ws, first.get("text") or "")

        while True:
            message = await ws.receive()
            msg_type = message.get("type")
            if msg_type == "websocket.disconnect":
                break

            payload_bytes = message.get("bytes")
            if payload_bytes is not None:
                await _handle_audio_chunk(ws, session, payload_bytes)
                continue

            raw_text = message.get("text")
            if not raw_text:
                continue
            try:
                data = json.loads(raw_text)
            except json.JSONDecodeError:
                await _send(ws, {"type": "error", "error": "invalid JSON frame"})
                continue

            frame_type = data.get("type")
            if frame_type == "text":
                await _handle_text_frame(ws, session, data)
            elif frame_type in ("ping", "sim_voice", "end"):
                await _handle_control(ws, session, data)
            elif frame_type == "init":
                await _send(ws, {"type": "error", "error": "init already received"})
            else:
                await _send(ws, {"type": "error", "error": f"unknown type: {frame_type}"})

    except WebSocketDisconnect:
        logger.debug("guardian client disconnected")
    except Exception:  # noqa: BLE001 — never take the whole app down
        logger.exception("guardian stream crashed")
        try:
            await ws.close(code=1011)
        except Exception:  # noqa: BLE001
            pass
    finally:
        if session is not None:
            ACTIVE_SESSIONS.pop(session.session_id, None)
            logger.info(
                "guardian session cleaned up",
                extra={"session_id": session.session_id},
            )
