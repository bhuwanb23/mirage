"""TTS via Microsoft Edge (edge-tts) — free, no API key, en/hi/ta voices."""

from __future__ import annotations

import asyncio
import logging
import tempfile
from pathlib import Path

logger = logging.getLogger("mirage.tts")

# voice_id -> edge-tts voice
VOICES = {
    ("en", "female"): "en-US-JennyNeural",
    ("en", "male"): "en-US-GuyNeural",
    ("hi", "female"): "hi-IN-SwaraNeural",
    ("hi", "male"): "hi-IN-MadhurNeural",
    ("ta", "female"): "ta-IN-PallaviNeural",
    ("ta", "male"): "ta-IN-ValluvarNeural",
}


def pick_voice(language: str = "en", gender: str = "female") -> str:
    return VOICES.get((language.lower(), gender.lower()), VOICES[("en", "female")])


async def _synthesize(text: str, voice: str, rate: str = "+0%") -> bytes:
    import edge_tts

    communicate = edge_tts.Communicate(text, voice, rate=rate)
    chunks: list[bytes] = []
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            chunks.append(chunk["data"])
    return b"".join(chunks)


def synthesize_to_bytes(text: str, language: str = "en", gender: str = "female") -> bytes:
    """Generate speech and return raw mp3 bytes (blocking wrapper)."""
    return asyncio.run(_synthesize(text, pick_voice(language, gender)))


def synthesize_to_file(
    text: str,
    output_path: str | Path,
    language: str = "en",
    gender: str = "female",
) -> Path:
    """Generate speech and write an mp3 file. Returns the path."""
    data = synthesize_to_bytes(text, language=language, gender=gender)
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    logger.info("tts wrote %s (%d bytes)", path, len(data))
    return path


def synthesize_temp(text: str, language: str = "en", gender: str = "female") -> Path:
    """Generate speech into a temp file (caller deletes when done)."""
    suffix = ".mp3"
    fd = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    fd.close()
    return synthesize_to_file(text, fd.name, language=language, gender=gender)
