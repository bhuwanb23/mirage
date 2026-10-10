"""Tests for chunked live transcription (Phase 4.1). Offline — Groq patched."""

from __future__ import annotations

import pytest

from app.services import transcription_stream as ts


class TestClean:
    @pytest.mark.parametrize(
        "raw",
        ["Thank you.", "thank you", "Thanks for watching!", "Thanks for listening."],
    )
    def test_hallucinations_filtered(self, raw: str):
        assert ts._clean(raw) == ""

    def test_real_text_kept_and_whitespace_collapsed(self):
        assert ts._clean("  your account   will be blocked ") == "your account will be blocked"

    def test_empty_stays_empty(self):
        assert ts._clean("") == ""


class TestTranscribeChunk:
    def test_empty_chunk_reports_error(self):
        result = ts.transcribe_chunk(b"", 0)
        assert result.error == "empty_chunk"
        assert result.is_usable is False

    @pytest.mark.skipif(ts.whisper_available(), reason="GROQ key present")
    def test_unavailable_without_key(self):
        result = ts.transcribe_chunk(b"\x00\x01", 1)
        assert result.error == "whisper_unavailable"
        assert result.available is False

    def test_unknown_extension_normalized(self, monkeypatch):
        """Anything the browser sends is routed through whisper with .webm."""
        seen = {}

        def fake_sync(path, language=None):
            seen["path"] = path
            return "hello there"

        monkeypatch.setattr(ts, "transcribe_chunk_sync", fake_sync)
        monkeypatch.setattr(ts, "groq_configured", lambda: True)
        result = ts.transcribe_chunk(b"audio-bytes", 5, ext=".xyz")
        assert result.text == "hello there"
        assert seen["path"].endswith(".webm")

    def test_api_failure_degrades_with_reason(self, monkeypatch):
        def fake_sync(path, language=None):
            raise RuntimeError("429 rate limit reached")

        monkeypatch.setattr(ts, "transcribe_chunk_sync", fake_sync)
        monkeypatch.setattr(ts, "groq_configured", lambda: True)
        result = ts.transcribe_chunk(b"audio", 7)
        assert result.available is False
        assert result.error == "rate_limited"


class TestTranscribeFile:
    def test_success_path(self, tmp_path, monkeypatch):
        audio = tmp_path / "chunk.webm"
        audio.write_bytes(b"bytes")
        monkeypatch.setattr(
            ts, "transcribe_chunk_sync", lambda p, lang=None: "transcribed text"
        )
        monkeypatch.setattr(ts, "groq_configured", lambda: True)
        result = ts.transcribe_file(str(audio), 3)
        assert result.is_usable is True
        assert result.text == "transcribed text"
        assert result.duration_ms >= 0

    def test_hallucination_result_is_not_usable(self, tmp_path, monkeypatch):
        audio = tmp_path / "chunk.webm"
        audio.write_bytes(b"bytes")
        monkeypatch.setattr(ts, "transcribe_chunk_sync", lambda p, lang=None: "Thank you.")
        monkeypatch.setattr(ts, "groq_configured", lambda: True)
        result = ts.transcribe_file(str(audio), 4)
        assert result.available is True
        assert result.is_usable is False  # cleaned away
