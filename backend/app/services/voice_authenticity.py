"""Synthetic Voice Detector (Phase 4.4).

Runs once per audio chunk alongside transcription and produces a 0..1
"synthetic score" for the caller's voice (higher = more likely AI clone).

Three degradation tiers, chosen automatically:

  1. `resemblyzer` — embedding-consistency analysis (plan §4.4 primary):
     intra-chunk sub-segment similarity (weight 0.40), inter-chunk rolling
     similarity (0.30), plus spectral flatness (0.15) and breathing (0.15).
  2. `signal` — no resemblyzer: decode the chunk with ffmpeg and score
     spectral flatness in the 2–8 kHz band (0.50), pause/breathing gaps
     (0.30), and frame-energy variability (0.20).
  3. `unavailable` — no ffmpeg either: neutral score, `available=False`
     so the UI shows "analysis unavailable" instead of a fake number.

Silent chunks are skipped (return None) so they never skew the rolling
window. Fewer than 3 analyzed chunks → `ready=False` ("Analyzing...").

Run:  uv run pytest tests/test_voice_authenticity.py -q
"""

from __future__ import annotations

import array
import logging
import math
import os
import shutil
import statistics
import subprocess
import tempfile
import wave
from dataclasses import dataclass
from typing import Any, Optional

from app.clients.resemblyzer_client import embed_wav
from app.clients.resemblyzer_client import is_available as resemblyzer_available

logger = logging.getLogger("mirage.voice_auth")

SAMPLE_RATE = 16_000
FRAME_MS = 20
FRAME_SAMPLES = SAMPLE_RATE * FRAME_MS // 1000  # 320 @ 16 kHz
FFT_SIZE = 512
READY_AFTER_CHUNKS = 3
ROLLING_WINDOW = 10

# Label bands from plan §4.4 "Interpretation".
_LABEL_BANDS = [
    (0.30, "Likely Human"),
    (0.50, "Probably Human"),
    (0.70, "Uncertain"),
    (0.85, "Likely AI Clone"),
    (1.01, "AI Generated"),
]


def label_for(score: float) -> str:
    for ceiling, label in _LABEL_BANDS:
        if score <= ceiling:
            return label
    return "AI Generated"


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


# ---------------------------------------------------------------------------
# Data contract
# ---------------------------------------------------------------------------
@dataclass
class VoiceUpdate:
    """Payload sent to the frontend after each analyzed chunk."""

    synthetic_score: float = 0.0
    label: str = "Analyzing..."
    intra_chunk_similarity: Optional[float] = None
    inter_chunk_similarity: Optional[float] = None
    reference_match: Optional[float] = None
    chunks_analyzed: int = 0
    ready: bool = False
    available: bool = True
    method: str = "signal"  # resemblyzer | signal | unavailable
    quality_warning: Optional[str] = None

    def to_payload(self) -> dict[str, Any]:
        return {
            "type": "voice_update",
            "synthetic_score": round(self.synthetic_score, 3),
            "label": self.label,
            "intra_chunk_similarity": _round_opt(self.intra_chunk_similarity),
            "inter_chunk_similarity": _round_opt(self.inter_chunk_similarity),
            "reference_match": _round_opt(self.reference_match),
            "chunks_analyzed": self.chunks_analyzed,
            "ready": self.ready,
            "available": self.available,
            "method": self.method,
            "quality_warning": self.quality_warning,
        }


def _round_opt(v: Optional[float]) -> Optional[float]:
    return None if v is None else round(v, 3)


# ---------------------------------------------------------------------------
# Audio helpers
# ---------------------------------------------------------------------------
def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def decode_to_wav(src_path: str) -> Optional[str]:
    """Decode any container (webm/ogg/…) → 16 kHz mono PCM wav temp file.

    Returns the temp path or None when ffmpeg is missing/fails. Caller
    must delete it.
    """
    if not ffmpeg_available():
        return None
    fd, out_path = tempfile.mkstemp(suffix=".wav", prefix="guardian_")
    os.close(fd)
    try:
        subprocess.run(
            [
                "ffmpeg", "-v", "error", "-y",
                "-i", src_path,
                "-f", "wav",
                "-ac", "1",
                "-ar", str(SAMPLE_RATE),
                out_path,
            ],
            check=True,
            capture_output=True,
            timeout=15,
        )
        return out_path
    except Exception as exc:  # noqa: BLE001
        logger.warning("ffmpeg decode failed: %s", exc)
        try:
            os.unlink(out_path)
        except OSError:
            pass
        return None


def _read_frames(wav_path: str) -> list[int]:
    """Read a wav file → list of 16-bit int samples (mono, downmixed)."""
    with wave.open(wav_path, "rb") as wf:
        channels = wf.getnchannels()
        width = wf.getsampwidth()
        raw = wf.readframes(wf.getnframes())
    if width != 2:
        raise ValueError(f"expected 16-bit wav, got {width * 8}-bit")
    samples = array.array("h")
    samples.frombytes(raw)
    if channels > 1:
        samples = [
            sum(samples[i : i + channels]) // channels
            for i in range(0, len(samples) - channels + 1, channels)
        ]
    return list(samples)


def _frame_rms(samples: list[int]) -> list[float]:
    rms: list[float] = []
    for i in range(0, len(samples) - FRAME_SAMPLES + 1, FRAME_SAMPLES):
        frame = samples[i : i + FRAME_SAMPLES]
        energy = sum(s * s for s in frame) / FRAME_SAMPLES
        rms.append(math.sqrt(energy))
    return rms


def _voiced_mask(rms: list[float]) -> tuple[list[bool], float]:
    """Threshold: midway between noise floor (p10) and peak speech (p90)."""
    if not rms:
        return [], 0.0
    ordered = sorted(rms)
    floor = ordered[max(0, len(ordered) // 10)]
    peak = ordered[min(len(ordered) - 1, (len(ordered) * 9) // 10)]
    if peak <= floor:
        threshold = floor * 0.5 if floor > 0 else 1.0
    else:
        threshold = floor + 0.25 * (peak - floor)
    return [r > threshold for r in rms], threshold


# ---------------------------------------------------------------------------
# DSP (pure python — no numpy/scipy dependency)
# ---------------------------------------------------------------------------
def _fft(values: list[complex]) -> list[complex]:
    """Iterative radix-2 Cooley–Tukey FFT. len(values) must be a power of 2."""
    n = len(values)
    if n & (n - 1):
        raise ValueError("FFT size must be a power of 2")
    out = list(values)
    # bit-reversal permutation
    j = 0
    for i in range(1, n):
        bit = n >> 1
        while j & bit:
            j ^= bit
            bit >>= 1
        j |= bit
        if i < j:
            out[i], out[j] = out[j], out[i]
    length = 2
    while length <= n:
        ang = -2 * math.pi / length
        w_len = complex(math.cos(ang), math.sin(ang))
        for i in range(0, n, length):
            w = 1 + 0j
            half = length // 2
            for k in range(i, i + half):
                u = out[k]
                v = out[k + half] * w
                out[k] = u + v
                out[k + half] = u - v
                w *= w_len
        length <<= 1
    return out


def spectral_flatness_2_8k(
    samples: list[int], rms: list[float], mask: list[bool]
) -> Optional[float]:
    """Mean spectral flatness of voiced frames in the 2–8 kHz band.

    Flat spectrum in that band is a known (rough) AI-vocoder tell.
    Returns 0..1 or None when there is no voiced audio to analyze.
    """
    bin_lo = int(2000 * FFT_SIZE / SAMPLE_RATE)   # 64
    bin_hi = int(8000 * FFT_SIZE / SAMPLE_RATE)   # 256
    flatness_values: list[float] = []
    frame_index = 0
    for start in range(0, len(samples) - FFT_SIZE + 1, FRAME_SAMPLES):
        if frame_index >= len(mask) or not mask[frame_index]:
            frame_index += 1
            continue
        frame_index += 1
        windowed = []
        for i in range(FFT_SIZE):
            hamming = 0.54 - 0.46 * math.cos(2 * math.pi * i / (FFT_SIZE - 1))
            windowed.append(complex(samples[start + i] * hamming, 0))
        spectrum = _fft(windowed)
        powers = [(spectrum[b].real ** 2 + spectrum[b].imag ** 2) for b in range(bin_lo, bin_hi)]
        powers = [p + 1e-12 for p in powers]
        mean_p = sum(powers) / len(powers)
        log_mean = sum(math.log(p) for p in powers) / len(powers)
        geometric = math.exp(log_mean)
        flatness_values.append(geometric / mean_p)
        if len(flatness_values) >= 12:  # enough frames for a stable mean
            break
    if not flatness_values:
        return None
    return sum(flatness_values) / len(flatness_values)


def pause_ratio(mask: list[bool], min_run: int = 3) -> float:
    """Fraction of the voiced span taken by real pauses (breathing gaps).

    Only contiguous silent RUNS of `min_run` frames (60 ms @ 20 ms/frame)
    count — scattered single-frame dips (plosive closures, noise) are not
    pauses and must not make continuous noise look like breathing speech.
    """
    voiced = [i for i, v in enumerate(mask) if v]
    if len(voiced) < 2:
        return 0.0
    start, end = voiced[0], voiced[-1]
    span = end - start + 1
    if span <= 0:
        return 0.0
    gap_frames = 0
    run = 0
    for i in range(start, end + 1):
        silent = i >= len(mask) or not mask[i]
        if silent:
            run += 1
        else:
            if run >= min_run:
                gap_frames += run
            run = 0
    if run >= min_run:
        gap_frames += run
    return gap_frames / span


def energy_variability(rms: list[float], mask: list[bool]) -> Optional[float]:
    """Coefficient of variation of voiced-frame RMS (humans vary more)."""
    voiced = [r for r, v in zip(rms, mask) if v and r > 0]
    if len(voiced) < 4:
        return None
    mean = sum(voiced) / len(voiced)
    if mean <= 0:
        return None
    return statistics.pstdev(voiced) / mean


# ---------------------------------------------------------------------------
# Signal-method scoring
# ---------------------------------------------------------------------------
def _signal_method(wav_path: str) -> tuple[Optional[dict[str, float]], Optional[str]]:
    """Score a decoded wav without resemblyzer.

    Returns ({signal_name: 0..1}, quality_warning) or (None, warning).
    """
    try:
        samples = _read_frames(wav_path)
    except Exception as exc:  # noqa: BLE001
        logger.warning("wav read failed: %s", exc)
        return None, None
    if len(samples) < SAMPLE_RATE // 2:
        return None, None

    rms = _frame_rms(samples)
    mask, _threshold = _voiced_mask(rms)
    voiced_fraction = (sum(mask) / len(mask)) if mask else 0.0
    if voiced_fraction < 0.15:
        return None, None  # treat as silence / no speech

    warnings: list[str] = []
    if voiced_fraction < 0.35:
        warnings.append("Voice analysis unreliable due to poor call quality.")

    signals: dict[str, float] = {}

    flatness = spectral_flatness_2_8k(samples, rms, mask)
    if flatness is not None:
        # Human speech 2–8 kHz flatness ≈ 0.05–0.20; vocoder ≈ 0.3+.
        signals["flatness"] = _clamp((flatness - 0.10) / 0.30)

    pauses = pause_ratio(mask)
    # Real talkers take breaths / pause: gap fraction ≳ 0.05 in4 s speech.
    if pauses < 0.04:
        signals["breathing"] = 1.0
    elif pauses > 0.18:
        signals["breathing"] = 0.0
    else:
        signals["breathing"] = _clamp((0.18 - pauses) / 0.14)

    variability = energy_variability(rms, mask)
    if variability is not None:
        # cv < 0.15 → suspiciously flat; cv > 0.6 → naturally dynamic.
        signals["energy"] = _clamp((0.60 - variability) / 0.45)

    if not signals:
        return None, (warnings[0] if warnings else None)
    return signals, (warnings[0] if warnings else None)


_SIGNAL_WEIGHTS = {"flatness": 0.50, "breathing": 0.30, "energy": 0.20}


def _weighted(signals: dict[str, float], weights: dict[str, float]) -> float:
    applicable = {k: weights[k] for k in signals if k in weights}
    total = sum(applicable.values())
    if total <= 0:
        return 0.0
    return _clamp(sum(signals[k] * w for k, w in applicable.items()) / total)


# ---------------------------------------------------------------------------
# Resemblyzer-method scoring
# ---------------------------------------------------------------------------
def _split_wav(wav_path: str, parts: int = 4) -> list[str]:
    """Split a wav into `parts` equal temp wavs (for intra-chunk embeddings)."""
    with wave.open(wav_path, "rb") as wf:
        params = wf.getparams()
        frames = wf.readframes(wf.getnframes())
    frame_size = params.nchannels * params.sampwidth
    chunk_len = (len(frames) // parts // frame_size) * frame_size
    paths: list[str] = []
    for i in range(parts):
        fd, path = tempfile.mkstemp(suffix=".wav", prefix="guardian_seg_")
        os.close(fd)
        with wave.open(path, "wb") as out:
            out.setparams(params)
            out.writeframes(frames[i * chunk_len : (i + 1) * chunk_len])
        paths.append(path)
    return paths


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if not na or not nb:
        return 0.0
    return _clamp(dot / (na * nb))


def _mean_embedding(window: list[list[float]]) -> Optional[list[float]]:
    if not window:
        return None
    dim = len(window[0])
    return [sum(e[i] for e in window) / len(window) for i in range(dim)]


def _resemblyzer_signals(
    wav_path: str,
) -> tuple[Optional[dict[str, float]], Optional[float], Optional[float]]:
    """Returns (signals, intra_sim, inter_sim); signals None if embedding failed."""
    embedding = embed_wav(wav_path)
    if embedding is None:
        return None, None, None

    intra: Optional[float] = None
    seg_paths = _split_wav(wav_path, 4)
    try:
        seg_embeddings = [p for p in (embed_wav(sp) for sp in seg_paths) if p is not None]
        if len(seg_embeddings) >= 2:
            pairs = [
                _cosine(seg_embeddings[i], seg_embeddings[j])
                for i in range(len(seg_embeddings))
                for j in range(i + 1, len(seg_embeddings))
            ]
            intra = sum(pairs) / len(pairs)
    finally:
        for sp in seg_paths:
            try:
                os.unlink(sp)
            except OSError:
                pass

    signals: dict[str, float] = {}
    if intra is not None:
        # Human sub-segments: 0.75–0.90; AI: >0.95 (plan §4.4 step 2).
        signals["intra"] = _clamp((intra - 0.90) / 0.07)
    return signals, intra, embedding


# ---------------------------------------------------------------------------
# Analyzer (per-session)
# ---------------------------------------------------------------------------
class VoiceAuthenticityAnalyzer:
    """Rolling synthetic-voice analyzer for one Guardian session."""

    def __init__(self, reference_embedding: Optional[list[float]] = None) -> None:
        self._window: list[list[float]] = []
        self._embedding: Optional[list[float]] = None  # last chunk embedding
        self.chunks_analyzed: int = 0
        self.last_score: float = 0.0
        self.reference_embedding = reference_embedding

    @property
    def method(self) -> str:
        if resemblyzer_available():
            return "resemblyzer"
        if ffmpeg_available():
            return "signal"
        return "unavailable"

    def _update_from_score(
        self,
        score: float,
        intra: Optional[float],
        inter: Optional[float],
        quality_warning: Optional[str],
    ) -> VoiceUpdate:
        self.last_score = score
        reference_match: Optional[float] = None
        if self.reference_embedding is not None and self._embedding is not None:
            reference_match = _cosine(self.reference_embedding, self._embedding)
        ready = self.chunks_analyzed >= READY_AFTER_CHUNKS
        return VoiceUpdate(
            synthetic_score=score,
            label=label_for(score) if ready else "Analyzing...",
            intra_chunk_similarity=intra,
            inter_chunk_similarity=inter,
            reference_match=reference_match,
            chunks_analyzed=self.chunks_analyzed,
            ready=self.chunks_analyzed >= READY_AFTER_CHUNKS,
            available=True,
            method=self.method,
            quality_warning=quality_warning,
        )

    def analyze_chunk(self, chunk_path: str) -> Optional[VoiceUpdate]:
        """Analyze one audio chunk. Returns None for silent/undecodable chunks.

        `chunk_path` may be webm/ogg/wav — it is decoded to wav first.
        """
        wav_path = decode_to_wav(chunk_path)
        if wav_path is None:
            return VoiceUpdate(
                synthetic_score=0.0,
                label="Unavailable",
                chunks_analyzed=self.chunks_analyzed,
                ready=False,
                available=False,
                method="unavailable",
                quality_warning="Voice analysis unavailable (no audio decoder on server).",
            )
        try:
            # Silence gate before spending any compute.
            try:
                samples = _read_frames(wav_path)
                rms = _frame_rms(samples)
                mask, _ = _voiced_mask(rms)
                voiced = (sum(mask) / len(mask)) if mask else 0.0
            except Exception:  # noqa: BLE001
                return None
            if voiced < 0.15 or len(samples) < SAMPLE_RATE // 2:
                return None  # silent chunk — do not skew the window

            signals: dict[str, float] = {}
            intra: Optional[float] = None
            inter: Optional[float] = None
            quality_warning: Optional[str] = None

            if resemblyzer_available():
                rem_signals, intra, embedding = _resemblyzer_signals(wav_path)
                if rem_signals is not None and embedding is not None:
                    signals.update(rem_signals)
                    self._embedding = embedding
                    self._window.append(embedding)
                    self._window = self._window[-ROLLING_WINDOW:]
                    mean = _mean_embedding(self._window[:-1])
                    if mean is not None:
                        inter = _cosine(mean, embedding)
                        # AI: inter >0.95; human drift 0.80–0.92 (plan §4.4).
                        signals["inter"] = _clamp((inter - 0.92) / 0.06)

            # Signal-based contributions (flatness / breathing) supplement the
            # embedding path and carry the whole score when it is absent.
            sig, quality_warning = _signal_method(wav_path)
            if sig:
                signals.update(sig)

            if not signals:
                return None

            if resemblyzer_available() and "intra" in signals:
                weights = {"intra": 0.40, "inter": 0.30, "flatness": 0.15, "breathing": 0.15}
                if "energy" in signals:
                    weights["energy"] = 0.10  # extra evidence, renormalized below
            else:
                weights = _SIGNAL_WEIGHTS

            score = _weighted(signals, weights)
            self.chunks_analyzed += 1
            return self._update_from_score(score, intra, inter, quality_warning)
        finally:
            try:
                os.unlink(wav_path)
            except OSError:
                pass

    def unavailable_update(self) -> VoiceUpdate:
        return VoiceUpdate(
            synthetic_score=0.0,
            label="Unavailable",
            chunks_analyzed=self.chunks_analyzed,
            ready=False,
            available=False,
            method="unavailable",
            quality_warning="Voice analysis unavailable (no audio decoder on server).",
        )

