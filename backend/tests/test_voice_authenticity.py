"""Tests for the Synthetic Voice Detector (Phase 4.4).

Offline: synthetic wavs are generated in-process. The ffmpeg decode path
is exercised when ffmpeg is installed (skipped otherwise). Resemblyzer is
monkeypatched everywhere — it never needs to be installed.
"""

from __future__ import annotations

import math
import os
import random
import shutil
import struct
import tempfile
import wave

import pytest

from app.services import voice_authenticity as va

SAMPLE_RATE = 16_000


# ---------------------------------------------------------------------------
# Fixtures — generated audio
# ---------------------------------------------------------------------------
def _write_wav(samples: list[int]) -> str:
    fd, path = tempfile.mkstemp(suffix=".wav", prefix="voice_test_")
    os.close(fd)
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(b"".join(struct.pack("<h", s) for s in samples))
    return path


def human_like_samples(duration_s: float = 4.0) -> list[int]:
    """Voiced bursts with pauses and dynamic amplitude (human speech-ish)."""
    samples: list[int] = []
    total = int(SAMPLE_RATE * duration_s)
    for i in range(total):
        t = i / SAMPLE_RATE
        in_speech = (t % 0.75) < 0.5  # 0.5 s speech / 0.25 s pause
        if in_speech:
            amp = 3000 * (0.6 + 0.4 * math.sin(2 * math.pi * 0.5 * t))
            s = amp * math.sin(2 * math.pi * 180 * t)
            s += 700 * math.sin(2 * math.pi * 3200 * t) * math.sin(2 * math.pi * 5 * t)
        else:
            s = 30 * math.sin(2 * math.pi * 90 * t)  # noise floor
        samples.append(int(max(-32767, min(32767, s))))
    return samples


def noise_samples(duration_s: float = 4.0) -> list[int]:
    """White noise — flat spectrum, constant energy (AI-vocoder-ish).

    Seeded Gaussian so the test is deterministic across runs.
    """
    rng = random.Random(42)
    total = int(SAMPLE_RATE * duration_s)
    return [int(max(-32767, min(32767, rng.gauss(0, 900)))) for _ in range(total)]


def silence_samples(duration_s: float = 2.0) -> list[int]:
    return [0] * int(SAMPLE_RATE * duration_s)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _copy(path: str) -> str:
    fd, out = tempfile.mkstemp(suffix=".wav", prefix="voice_copy_")
    os.close(fd)
    shutil.copyfile(path, out)
    return out


@pytest.fixture
def human_wav() -> str:
    path = _write_wav(human_like_samples())
    yield path
    os.unlink(path)


@pytest.fixture
def noise_wav() -> str:
    path = _write_wav(noise_samples())
    yield path
    os.unlink(path)


@pytest.fixture
def silence_wav() -> str:
    path = _write_wav(silence_samples())
    yield path
    os.unlink(path)


# ---------------------------------------------------------------------------
# Labels
# ---------------------------------------------------------------------------
class TestLabels:
    @pytest.mark.parametrize(
        ("score", "expected"),
        [
            (0.10, "Likely Human"),
            (0.40, "Probably Human"),
            (0.60, "Uncertain"),
            (0.75, "Likely AI Clone"),
            (0.95, "AI Generated"),
        ],
    )
    def test_label_bands(self, score: float, expected: str):
        assert va.label_for(score) == expected


# ---------------------------------------------------------------------------
# Signal method (no resemblyzer) — decode via ffmpeg
# ---------------------------------------------------------------------------
@pytest.mark.skipif(not va.ffmpeg_available(), reason="ffmpeg not installed")
class TestSignalMethod:
    def test_human_like_audio_scores_low(self, human_wav, monkeypatch):
        monkeypatch.setattr(va, "resemblyzer_available", lambda: False)
        analyzer = va.VoiceAuthenticityAnalyzer()
        update = analyzer.analyze_chunk(human_wav)
        assert update is not None
        assert update.method == "signal"
        assert update.available is True
        assert update.synthetic_score < 0.45, update.synthetic_score

    def test_noise_scores_high(self, noise_wav, monkeypatch):
        monkeypatch.setattr(va, "resemblyzer_available", lambda: False)
        analyzer = va.VoiceAuthenticityAnalyzer()
        update = analyzer.analyze_chunk(noise_wav)
        assert update is not None
        assert update.synthetic_score > 0.7, update.synthetic_score

    def test_silence_is_skipped(self, silence_wav, monkeypatch):
        monkeypatch.setattr(va, "resemblyzer_available", lambda: False)
        analyzer = va.VoiceAuthenticityAnalyzer()
        assert analyzer.analyze_chunk(silence_wav) is None
        assert analyzer.chunks_analyzed == 0

    def test_ready_only_after_three_chunks(self, human_wav, monkeypatch):
        monkeypatch.setattr(va, "resemblyzer_available", lambda: False)
        analyzer = va.VoiceAuthenticityAnalyzer()
        first = analyzer.analyze_chunk(human_wav)
        assert first.ready is False
        assert first.label == "Analyzing..."
        for _ in range(2):
            analyzer.analyze_chunk(human_wav)
        third = analyzer.analyze_chunk(human_wav)
        assert third.ready is True
        assert third.label != "Analyzing..."
        assert third.chunks_analyzed == 4

    def test_webm_input_decodes(self, human_wav, monkeypatch):
        """Browser sends webm/opus — the analyzer must handle any container."""
        webm = tempfile.mktemp(suffix=".webm")
        import subprocess

        subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-i", human_wav,
             "-c:a", "libopus", "-b:a", "32k", webm],
            check=True,
        )
        try:
            monkeypatch.setattr(va, "resemblyzer_available", lambda: False)
            analyzer = va.VoiceAuthenticityAnalyzer()
            update = analyzer.analyze_chunk(webm)
            assert update is not None and update.available is True
        finally:
            os.unlink(webm)


# ---------------------------------------------------------------------------
# Unavailable tier
# ---------------------------------------------------------------------------
class TestUnavailable:
    def test_no_ffmpeg_no_resemblyzer_degrades(self, human_wav, monkeypatch):
        monkeypatch.setattr(va, "resemblyzer_available", lambda: False)
        monkeypatch.setattr(va, "ffmpeg_available", lambda: False)
        analyzer = va.VoiceAuthenticityAnalyzer()
        assert analyzer.method == "unavailable"
        update = analyzer.analyze_chunk(human_wav)
        assert update.available is False
        assert update.method == "unavailable"
        assert update.quality_warning


# ---------------------------------------------------------------------------
# Resemblyzer tier (mocked embeddings — never installed)
# ---------------------------------------------------------------------------
@pytest.mark.skipif(not va.ffmpeg_available(), reason="ffmpeg needed to decode chunk")
class TestResemblyzerTier:
    def _patch(self, monkeypatch, embedding_fn):
        monkeypatch.setattr(va, "resemblyzer_available", lambda: True)
        monkeypatch.setattr(va, "embed_wav", embedding_fn)

    def test_too_consistent_embeddings_score_high(self, noise_wav, monkeypatch):
        """AI voices produce near-identical embeddings → high synthetic."""
        self._patch(monkeypatch, lambda path: [1.0] + [0.0] * 63)
        analyzer = va.VoiceAuthenticityAnalyzer()
        updates = [analyzer.analyze_chunk(noise_wav) for _ in range(3)]
        last = updates[-1]
        assert last is not None
        assert last.method == "resemblyzer"
        assert last.intra_chunk_similarity == pytest.approx(1.0)
        assert last.inter_chunk_similarity == pytest.approx(1.0)
        assert last.synthetic_score > 0.7, last.synthetic_score

    def test_variable_embeddings_score_low(self, human_wav, monkeypatch):
        """Human voices drift between segments → lower score."""
        counter = {"n": 0}

        def drifting(_path):
            counter["n"] += 1
            seed = counter["n"] % 7
            return [1.0 if i == seed else 0.01 for i in range(64)]

        self._patch(monkeypatch, drifting)
        analyzer = va.VoiceAuthenticityAnalyzer()
        updates = [analyzer.analyze_chunk(human_wav) for _ in range(3)]
        last = updates[-1]
        assert last is not None
        assert last.intra_chunk_similarity is not None
        assert last.intra_chunk_similarity < 0.9
        assert last.synthetic_score < 0.5, last.synthetic_score

    def test_reference_match_reported(self, human_wav, monkeypatch):
        reference = [1.0] + [0.0] * 63
        self._patch(monkeypatch, lambda path: reference)
        analyzer = va.VoiceAuthenticityAnalyzer(reference_embedding=reference)
        update = analyzer.analyze_chunk(human_wav)
        assert update is not None
        assert update.reference_match == pytest.approx(1.0)

    def test_reference_mismatch_low(self, human_wav, monkeypatch):
        reference = [1.0] + [0.0] * 63
        self._patch(monkeypatch, lambda path: [0.0, 1.0] + [0.0] * 62)
        analyzer = va.VoiceAuthenticityAnalyzer(reference_embedding=reference)
        update = analyzer.analyze_chunk(human_wav)
        assert update is not None
        assert update.reference_match is not None
        assert update.reference_match < 0.3


# ---------------------------------------------------------------------------
# DSP units
# ---------------------------------------------------------------------------
class TestDspUnits:
    def test_fft_runs_and_has_expected_dc(self):
        signal = [complex(1.0, 0.0)] * 64  # constant → energy at bin 0
        spectrum = va._fft(signal)
        assert abs(spectrum[0]) == pytest.approx(64, abs=0.01)
        assert abs(spectrum[1]) < 1e-6

    def test_pause_ratio_all_voiced(self):
        assert va.pause_ratio([True] * 10) == 0.0

    def test_pause_ratio_ignores_single_frame_dips(self):
        # Scattered 1-frame dips (plosives / noise) are NOT pauses.
        mask = [True, False, True, False, True, False, True, False]
        assert va.pause_ratio(mask) == 0.0

    def test_pause_ratio_counts_contiguous_runs(self):
        # Three 3-frame gaps across an 9-frame span → 6/9.
        mask = [True, False, False, False, True, False, False, False, True]
        assert va.pause_ratio(mask) == pytest.approx(6 / 9)

    def test_weighted_renormalizes_over_available_signals(self):
        # Only breathing available → it alone drives the score.
        assert va._weighted({"breathing": 1.0}, va._SIGNAL_WEIGHTS) == 1.0
        assert va._weighted({"breathing": 0.0}, va._SIGNAL_WEIGHTS) == 0.0
        mixed = va._weighted({"flatness": 1.0, "breathing": 0.0}, va._SIGNAL_WEIGHTS)
        assert 0.3 < mixed < 0.75

    def test_payload_shape(self):
        update = va.VoiceUpdate(synthetic_score=0.5, chunks_analyzed=3, ready=True)
        payload = update.to_payload()
        assert payload["type"] == "voice_update"
        for key in ("synthetic_score", "label", "intra_chunk_similarity",
                    "inter_chunk_similarity", "reference_match",
                    "chunks_analyzed", "ready", "available", "method"):
            assert key in payload
