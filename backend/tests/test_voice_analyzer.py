"""Tests for the voice / audio analyzer (Phase 1.4).

Offline tests: audio validation, transcription stub, synthetic voice
heuristic, merge logic, schema. Groq Whisper and Resemblyzer tests are
skipped when the respective services are unavailable.
"""

from __future__ import annotations

import pytest

from app.models.schemas import ScamVerdict, TranscriptSegment, VoiceAnalysisVerdict
from app.services.voice_analyzer import (
    VoiceAnalysisVerdict as _VoiceVerdict,
)
from app.services.voice_analyzer import (
    analyze_voice,
)
from app.services.voice_validator import (
    MAX_AUDIO_BYTES,
    MIME_BY_EXT,
    _guess_suffix_from_bytes,
    validate_and_read_audio,
)

# ---------------------------------------------------------------------------
# Audio validation
# ---------------------------------------------------------------------------

class TestAudioValidation:
    def test_accept_wav(self, tmp_path):
        # Minimal valid WAV (44-byte header + silence)
        wav = (
            b"RIFF"
            + (44 + 100).to_bytes(4, "little")
            + b"WAVE"
            + b"fmt "
            + (16).to_bytes(4, "little")
            + (1).to_bytes(2, "little")  # PCM
            + (1).to_bytes(2, "little")  # mono
            + (16000).to_bytes(4, "little")  # 16kHz
            + (32000).to_bytes(4, "little")  # byte rate
            + (2).to_bytes(2, "little")  # block align
            + (16).to_bytes(2, "little")  # bits per sample
            + b"data"
            + (100).to_bytes(4, "little")
            + b"\x00" * 100
        )
        data, mime, duration = validate_and_read_audio(wav)
        assert mime == "audio/wav"
        assert len(data) > 0
        assert duration > 0

    def test_accept_ogg(self, tmp_path):
        # Minimal OGG header
        ogg = b"OggS" + b"\x00" * 28 + b"\x00" * 100
        data, mime, duration = validate_and_read_audio(ogg)
        assert mime == "audio/ogg"
        assert len(data) > 0

    def test_accept_mp3(self, tmp_path):
        mp3 = b"ID3" + b"\x00" * 10 + b"\xff\xd8\xff\xe0" + b"\x00" * 100
        data, mime, duration = validate_and_read_audio(mp3)
        assert mime == "audio/mpeg"
        assert len(data) > 0

    def test_accept_webm(self, tmp_path):
        webm = b"\x1a\x45\xdf\xa3" + b"\x00" * 50
        data, mime, duration = validate_and_read_audio(webm)
        assert mime == "audio/webm"
        assert len(data) > 0

    def test_accept_flac(self, tmp_path):
        flac = b"fLaC" + b"\x00" * 50
        data, mime, duration = validate_and_read_audio(flac)
        assert mime == "audio/flac"
        assert len(data) > 0

    def test_reject_unsupported_format(self, tmp_path):
        path = tmp_path / "test.xyz"
        path.write_bytes(b"not audio")
        with pytest.raises(ValueError, match="Unsupported audio format"):
            validate_and_read_audio(path)

    def test_reject_empty(self):
        with pytest.raises(ValueError, match="Audio is empty"):
            validate_and_read_audio(b"")

    def test_reject_too_large(self, tmp_path):
        path = tmp_path / "large.ogg"
        path.write_bytes(b"\x00" * (MAX_AUDIO_BYTES + 1))
        with pytest.raises(ValueError, match="too large"):
            validate_and_read_audio(path)

    def test_mime_by_extension(self):
        assert MIME_BY_EXT[".ogg"] == "audio/ogg"
        assert MIME_BY_EXT[".mp3"] == "audio/mpeg"
        assert MIME_BY_EXT[".wav"] == "audio/wav"
        assert MIME_BY_EXT[".m4a"] == "audio/mp4"

    def test_suffix_detection_from_bytes(self):
        assert _guess_suffix_from_bytes(b"OggS" + b"\x00" * 100) == ".ogg"
        # Real WAV: RIFF(0-4) + size(4-8) + WAVE(8-12)
        wav_bytes = b"RIFF" + (44).to_bytes(4, "little") + b"WAVE" + b"\x00" * 100
        assert _guess_suffix_from_bytes(wav_bytes) == ".wav"
        assert _guess_suffix_from_bytes(b"ID3" + b"\x00" * 100) == ".mp3"
        assert _guess_suffix_from_bytes(b"fLaC" + b"\x00" * 100) == ".flac"


# ---------------------------------------------------------------------------
# Voice analysis verdict schema
# ---------------------------------------------------------------------------

class TestVoiceAnalysisVerdictSchema:
    def test_defaults(self):
        v = VoiceAnalysisVerdict(
            verdict=ScamVerdict(is_scam=False, confidence=0.0),
        )
        assert v.verdict.is_scam is False
        assert v.transcript == ""
        assert v.transcript_segments == []
        assert v.detected_language == ""
        assert v.synthetic_voice_score == 0.0
        assert v.voice_verdict == "unknown"
        assert v.audio_duration_seconds == 0.0
        assert v.confidence_boost == 0.0
        assert v.processing_time_ms == 0.0
        assert v.audio_metadata == {}
        assert v.voice_model_available is False
        assert v.whisper_available is False

    def test_transcript_segment_schema(self):
        seg = TranscriptSegment(start=0.0, end=3.2, text="Hello world")
        assert seg.start == 0.0
        assert seg.end == 3.2
        assert seg.text == "Hello world"


# ---------------------------------------------------------------------------
# Full analyzer offline
# ---------------------------------------------------------------------------

class TestFullAnalyzerOffline:
    def test_analyzer_returns_valid_verdict(self):
        # Minimal WAV bytes
        wav = (
            b"RIFF"
            + (44 + 100).to_bytes(4, "little")
            + b"WAVE"
            + b"fmt "
            + (16).to_bytes(4, "little")
            + (1).to_bytes(2, "little")
            + (1).to_bytes(2, "little")
            + (16000).to_bytes(4, "little")
            + (32000).to_bytes(4, "little")
            + (2).to_bytes(2, "little")
            + (16).to_bytes(2, "little")
            + b"data"
            + (100).to_bytes(4, "little")
            + b"\x00" * 100
        )
        result = analyze_voice(wav)
        assert isinstance(result, _VoiceVerdict)
        assert isinstance(result.verdict, ScamVerdict)
        assert 0.0 <= result.verdict.confidence <= 1.0
        assert result.processing_time_ms >= 0
        assert result.audio_duration_seconds > 0
        assert result.voice_model_available is False  # resemblyzer not installed
        assert result.whisper_available is False  # no groq key

    def test_analyzer_empty_transcript(self):
        # Silence-only audio
        wav = (
            b"RIFF"
            + (44 + 100).to_bytes(4, "little")
            + b"WAVE"
            + b"fmt "
            + (16).to_bytes(4, "little")
            + (1).to_bytes(2, "little")
            + (1).to_bytes(2, "little")
            + (16000).to_bytes(4, "little")
            + (32000).to_bytes(4, "little")
            + (2).to_bytes(2, "little")
            + (16).to_bytes(2, "little")
            + b"data"
            + (100).to_bytes(4, "little")
            + b"\x00" * 100
        )
        result = analyze_voice(wav)
        assert "No speech detected" in result.verdict.summary or result.verdict.confidence == 0.0

    def test_analyzer_no_whisper_returns_no_speech(self):
        wav = (
            b"RIFF"
            + (44 + 100).to_bytes(4, "little")
            + b"WAVE"
            + b"fmt "
            + (16).to_bytes(4, "little")
            + (1).to_bytes(2, "little")
            + (1).to_bytes(2, "little")
            + (16000).to_bytes(4, "little")
            + (32000).to_bytes(4, "little")
            + (2).to_bytes(2, "little")
            + (16).to_bytes(2, "little")
            + b"data"
            + (100).to_bytes(4, "little")
            + b"\x00" * 100
        )
        result = analyze_voice(wav)
        assert result.whisper_available is False
        assert result.transcript == "No speech detected in audio"
