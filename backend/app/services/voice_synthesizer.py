"""Voice synthesizer (Phase 3.3) — Edge-TTS primary, F5-TTS optional.

Turns a generated script into one playable MP3 with exact per-stage timing:

- Each of the 5 stages is synthesized separately (edge-tts, Indian voices,
  rate -5%, pitch -10% per plan) so stage start/end seconds come from the
  CBR byte length (48 kbps mono 24 kHz => 6000 bytes/second — exact).
- Segments are concatenated (ID3 headers stripped after the first) into
  `media/drill/<script_id>.mp3`, served as `/media/drill/<script_id>.mp3`.
- `[STAGE: X]` tags are removed; `[pause Ns]` markers become `…` so the TTS
  takes a natural prosodic pause.
- Optional F5-TTS: if `F5TTS_API_URL` is set, POST the script there first
  (see ml/voice_cloning notebook); on any failure fall back to edge-tts.

SSL note: edge-tts hardcodes certifi's CA bundle. Machines that validate TLS
through the system store (TLS-intercepting proxies) fail verification, so on
a certificate error we repoint `edge_tts.communicate._SSL_CTX` at the default
system context and retry once.
"""

from __future__ import annotations

import logging
import re
import ssl
from pathlib import Path
from typing import Any, Optional

from app.config import settings

logger = logging.getLogger("mirage.voice_synth")

STAGES = ["hook", "authority", "isolation", "urgency", "payment"]

# edge-tts output: audio-24khz-48kbitrate-mono-mp3 => 6000 bytes per second
_BYTES_PER_SECOND = 48_000 / 8

# scam type -> edge-tts voice (male authoritative scammer; job offer = female HR)
_VOICE_BY_SCAM = {
    "job_offer": {"en": "en-IN-NeerjaNeural", "hi": "hi-IN-SwaraNeural"},
    "_default": {
        "en": "en-IN-PrabhatNeural",
        "hi": "hi-IN-MadhurNeural",
        "ta": "ta-IN-MuthuNeural",
    },
}

_STAGE_TAG_RE = re.compile(r"\[STAGE:\s*[A-Za-z]+\]", re.I)
_PAUSE_RE = re.compile(r"\[pause\s+(\d+(?:\.\d+)?)s?\]", re.I)

_SSL_FIXED = False


def pick_voice(scam_type: str, language: str = "en") -> str:
    table = _VOICE_BY_SCAM.get(scam_type, _VOICE_BY_SCAM["_default"])
    return table.get((language or "en").lower(), table["en"])


def prepare_tts_text(text: str) -> str:
    """Strip stage tags, turn [pause Ns] into a spoken pause (ellipsis)."""
    text = _STAGE_TAG_RE.sub("", text or "")
    text = _PAUSE_RE.sub(lambda m: " … ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _ensure_ssl_fix() -> bool:
    """Repoint edge-tts at the system trust store. Returns True if patched."""
    global _SSL_FIXED
    if _SSL_FIXED:
        return True
    try:
        import edge_tts.communicate as comm

        comm._SSL_CTX = ssl.create_default_context()  # system store, no certifi pin
        _SSL_FIXED = True
        logger.info("edge-tts SSL context repointed to system trust store")
        return True
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Could not patch edge-tts SSL context: %s", exc)
        return False


def _is_cert_error(exc: BaseException) -> bool:
    if isinstance(exc, (ssl.SSLError, ssl.CertificateError)):
        return True
    text = str(exc).lower()
    return "certificate" in text or "ssl" in text or "cert verify" in text


async def _stream_segment(text: str, voice: str) -> bytes:
    """One edge-tts call -> mp3 bytes, with SSL patch + single retry."""
    import edge_tts

    async def _run() -> bytes:
        communicate = edge_tts.Communicate(
            text, voice, rate="-5%", pitch="-10Hz", boundary="WordBoundary"
        )
        chunks: list[bytes] = []
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                chunks.append(chunk["data"])
        return b"".join(chunks)

    try:
        return await _run()
    except Exception as exc:
        if not _is_cert_error(exc):
            raise
        logger.warning("edge-tts certificate error (%s) — applying SSL fix", exc)
        _ensure_ssl_fix()
        return await _run()


def _strip_id3(data: bytes) -> bytes:
    """Drop an ID3v2 header if the segment starts with one (gapless join)."""
    while data.startswith(b"ID3") and len(data) > 10:
        # syncsafe 28-bit size at bytes 6..9 (footer flag adds 10 more)
        size = (
            ((data[6] & 0x7F) << 21)
            | ((data[7] & 0x7F) << 14)
            | ((data[8] & 0x7F) << 7)
            | (data[9] & 0x7F)
        )
        header = 10 + (10 if data[5] & 0x10 else 0)
        data = data[header + size :]
    return data


def _bytes_to_seconds(n: int) -> float:
    return round(n / _BYTES_PER_SECOND, 2)


# ---------------------------------------------------------------------------
# Optional F5-TTS (real voice cloning) — best effort, falls back to edge-tts
# ---------------------------------------------------------------------------

def _try_f5tts(text: str, profile: dict[str, Any]) -> Optional[bytes]:
    if not settings.f5tts_api_url:
        return None
    try:
        import httpx

        resp = httpx.post(
            f"{settings.f5tts_api_url.rstrip('/')}/synthesize",
            json={
                "text": text,
                "reference_audio": profile.get("voice_clip_url")
                or profile.get("voice_clip_path"),
            },
            timeout=60.0,
        )
        resp.raise_for_status()
        if resp.headers.get("content-type", "").startswith("audio") or len(resp.content) > 2000:
            return resp.content
    except Exception as exc:
        logger.warning("F5-TTS failed, falling back to edge-tts: %s", exc)
    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def synthesize_script(
    script: dict[str, Any],
    profile: Optional[dict[str, Any]] = None,
    method: str = "auto",
) -> dict[str, Any]:
    """Synthesize a generated script into an MP3 with per-stage timings.

    Returns {audio_url, duration_seconds, method_used, stage_timings,
    status, message}. On total failure: status="failed" with audio_url=None —
    the frontend then runs a text-only drill.
    """
    import asyncio

    profile = profile or {}
    language = script.get("language") or profile.get("language") or "en"
    stages: dict[str, dict[str, str]] = script.get("stages") or {}
    media_root = Path(settings.drill_media_dir)
    media_root.mkdir(parents=True, exist_ok=True)
    out_path = media_root / f"{script['script_id']}.mp3"

    # --- full-script path: F5-TTS if configured ---------------------------
    method = (method or "auto").lower()
    if method in ("auto", "f5tts") and settings.f5tts_api_url:
        blob = _try_f5tts(script.get("full_script", ""), profile)
        if blob:
            out_path.write_bytes(blob)
            return {
                "audio_url": f"/media/drill/{out_path.name}",
                "duration_seconds": float(script.get("estimated_duration_seconds") or 60.0),
                "method_used": "f5tts",
                "stage_timings": _fallback_stage_timings(stages, script),
                "status": "ready",
                "message": "Cloned voice generated via F5-TTS.",
            }

    # --- edge-tts: per-stage synthesis ------------------------------------
    voice = pick_voice(script.get("scam_type", "bank_kyc"), language)
    joined = bytearray()
    stage_timings: dict[str, dict[str, float]] = {}
    cursor = 0.0
    try:
        loop = asyncio.new_event_loop()
        try:
            for stage in STAGES:
                entry = stages.get(stage)
                text = prepare_tts_text((entry or {}).get("script") or "")
                if not text:
                    stage_timings[stage] = {"start": round(cursor, 2), "end": round(cursor, 2)}
                    continue
                audio = loop.run_until_complete(_stream_segment(text, voice))
                if joined:
                    audio = _strip_id3(audio)
                if not audio:
                    raise RuntimeError(f"edge-tts returned empty audio for stage {stage}")
                joined.extend(audio)
                dur = _bytes_to_seconds(len(audio))
                stage_timings[stage] = {"start": round(cursor, 2), "end": round(cursor + dur, 2)}
                cursor += dur
        finally:
            loop.close()
    except Exception as exc:
        logger.error("edge-tts synthesis failed: %s", exc)
        return {
            "audio_url": None,
            "duration_seconds": 0.0,
            "method_used": "none",
            "stage_timings": _fallback_stage_timings(stages, script),
            "status": "failed",
            "message": "Could not synthesize audio. Continuing with the text script.",
        }

    out_path.write_bytes(bytes(joined))
    duration = round(cursor, 2) or float(script.get("estimated_duration_seconds") or 60.0)
    return {
        "audio_url": f"/media/drill/{out_path.name}",
        "duration_seconds": duration,
        "method_used": "edge-tts",
        "stage_timings": stage_timings,
        "status": "ready",
        "message": f"Voice: {voice}.",
    }


def _fallback_stage_timings(
    stages: dict[str, dict[str, str]], script: dict[str, Any]
) -> dict[str, dict[str, float]]:
    """Word-proportional timings when audio synthesis is unavailable."""
    texts = {s: (stages.get(s) or {}).get("script", "") for s in STAGES}
    weights = {s: max(len(t.split()), 1) for s, t in texts.items()}
    total = sum(weights.values()) or 1
    duration = float(script.get("estimated_duration_seconds") or 60.0)
    cursor = 0.0
    out: dict[str, dict[str, float]] = {}
    for stage in STAGES:
        span = duration * weights[stage] / total
        out[stage] = {"start": round(cursor, 2), "end": round(cursor + span, 2)}
        cursor += span
    return out


def pre_generate_demo_audio(
    scam_types: list[str] | None = None,
    language: str = "en",
) -> dict[str, dict[str, Any]]:
    """Generate demo audios ahead of a presentation (static fallback files)."""
    from app.services.fallback_scripts import render_fallback
    from app.services.script_generator import estimate_duration_seconds

    scam_types = scam_types or ["bank_kyc", "fedex", "job_offer"]
    profile = {
        "name": "Priya Sharma",
        "first_name": "Priya",
        "city": "Mumbai",
        "bank_full_name": "State Bank of India",
        "employer": "TCS",
        "language": language,
    }
    results: dict[str, dict[str, Any]] = {}
    for scam_type in scam_types:
        # templates only — demo files must never depend on an LLM being up
        script = render_fallback(scam_type, profile)
        script["script_id"] = f"demo_{scam_type}"
        script["language"] = language
        script["estimated_duration_seconds"] = estimate_duration_seconds(script["full_script"])
        results[scam_type] = synthesize_script(script, profile)
    return results
