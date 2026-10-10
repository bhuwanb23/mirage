"""Chunked live transcription for the Guardian WebSocket (Phase 4.1).

Each browser chunk (4 s of `audio/webm;codecs=opus`) is written to a temp
file and transcribed via Groq Whisper. Degradation tiers:

  * `groq` configured      → whisper-large-v3-turbo per chunk
  * no key / provider fail → ChunkTranscription.available=False, text=""

The router treats an unavailable transcription as "text sim only": the
session keeps running, stage tracking continues from any text frames, and
the frontend shows a "transcription unavailable" note instead of dying.

Known Whisper-on-short-clip hallucinations ("Thank you.", "Thanks for
watching." …) are filtered so they never pollute the transcript buffer.

Run:  uv run pytest tests/test_transcription_stream.py -q
"""

from __future__ import annotations

import logging
import os
import tempfile
import time
from dataclasses import dataclass
from typing import Optional

from app.clients.groq_client import is_configured as groq_configured
from app.clients.groq_client import transcribe_audio

logger = logging.getLogger("mirage.transcription_stream")

# Whisper frequently "hallucinates" these on silence / noise-only clips
# (compared after lowercasing + stripping trailing punctuation).
_HALLUCINATIONS = {
    "thank you",
    "thanks for watching",
    "thanks for listening",
    "you",
    "bye",
    "subtitles by vitac.com",
    "the end",
}

# MediaRecorder blobs are headerless after the first chunk unless the
# recorder is restarted — we accept any of these extensions.
AUDIO_EXTENSIONS = (".webm", ".ogg", ".m4a", ".mp4", ".mp3", ".wav")


@dataclass
class ChunkTranscription:
    """Result of transcribing one binary chunk."""

    seq: int
    text: str = ""
    available: bool = False
    error: Optional[str] = None
    duration_ms: float = 0.0

    @property
    def is_usable(self) -> bool:
        """True when there is text worth feeding to the stage tracker."""
        return bool(self.text.strip())


def whisper_available() -> bool:
    return groq_configured()


def _write_temp(data: bytes, ext: str) -> str:
    fd, path = tempfile.mkstemp(suffix=ext, prefix="guardian_chunk_")
    with os.fdopen(fd, "wb") as f:
        f.write(data)
    return path


def _clean(text: str) -> str:
    """Strip Whisper hallucinations and whitespace."""
    cleaned = " ".join(text.split())
    normalized = cleaned.lower().strip().rstrip(".!? ").strip()
    if normalized in _HALLUCINATIONS:
        return ""
    return cleaned


def transcribe_chunk(
    data: bytes,
    seq: int,
    language: Optional[str] = None,
    ext: str = ".webm",
) -> ChunkTranscription:
    """Transcribe one binary audio chunk. Never raises.

    Returns ChunkTranscription with available=False and a short error
    reason when Whisper is unconfigured, the chunk is empty, or the API
    call fails (rate limit included).
    """
    if not data:
        return ChunkTranscription(seq=seq, error="empty_chunk")
    if ext not in AUDIO_EXTENSIONS:
        ext = ".webm"
    if not groq_configured():
        return ChunkTranscription(seq=seq, error="whisper_unavailable")

    path = _write_temp(data, ext)
    try:
        return transcribe_file(path, seq, language)
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def transcribe_file(
    path: str,
    seq: int,
    language: Optional[str] = None,
) -> ChunkTranscription:
    """Transcribe an audio file already on disk. Never raises.

    Used by the Guardian router, which owns the temp file (it also feeds
    the same file to voice authenticity analysis).
    """
    if not groq_configured():
        return ChunkTranscription(seq=seq, error="whisper_unavailable")

    start = time.perf_counter()
    try:
        raw = transcribe_chunk_sync(path, language)
        elapsed = (time.perf_counter() - start) * 1000
        text = _clean(raw or "")
        return ChunkTranscription(
            seq=seq,
            text=text,
            available=True,
            duration_ms=round(elapsed, 1),
        )
    except Exception as exc:  # noqa: BLE001 — a dropped chunk must not kill the call
        msg = str(exc).lower()
        rate_limited = "429" in str(exc) or "rate" in msg
        reason = "rate_limited" if rate_limited else "transcribe_failed"
        logger.warning("chunk %s transcription failed (%s): %s", seq, reason, exc)
        return ChunkTranscription(
            seq=seq,
            available=False,
            error=reason,
            duration_ms=round((time.perf_counter() - start) * 1000, 1),
        )


def transcribe_chunk_sync(path: str, language: Optional[str] = None) -> str:
    """Thin seam so tests can patch the actual Groq call."""
    return transcribe_audio(path, language=language)
