"""Audio validation for Phase 1.4 (voice analyzer).

Accepts ogg/mp3/wav/m4a/webm up to 10 MB. Returns raw bytes + MIME type.
Duration is estimated from file size when no proper decoder is available
(rough heuristic), or parsed properly when ffprobe/pydub is present.
"""

from __future__ import annotations

from pathlib import Path

from app.clients.groq_client import AUDIO_FORMATS

MAX_AUDIO_BYTES = 10 * 1024 * 1024  # 10 MB
MAX_AUDIO_DURATION = 60  # seconds
MIN_AUDIO_DURATION = 1  # seconds — below this, skip synthetic voice detection

MIME_BY_EXT = {
    ".ogg": "audio/ogg",
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".m4a": "audio/mp4",
    ".webm": "audio/webm",
    ".flac": "audio/flac",
}

# Rough bytes-per-second estimates for duration estimation when no decoder.
# These are order-of-magnitude; real duration should come from ffprobe.
_BYTES_PER_SECOND_ESTIMATE = {
    ".ogg": 16_000,   # 16 kbps voice note
    ".mp3": 64_000,   # 64 kbps
    ".wav": 160_000,  # 16-bit 16kHz mono
    ".m4a": 64_000,
    ".webm": 32_000,
    ".flac": 160_000,
}


def validate_and_read_audio(source, strict_extension: bool = False) -> tuple[bytes, str, float]:
    """Read `source` and validate format + size.

    Returns (bytes, mime_type, estimated_duration_seconds).
    Raises ValueError on validation failure.

    When `strict_extension=True` and a filename/extension is available, rejects
    formats not in AUDIO_FORMATS. Otherwise uses byte-signature detection and
    defaults to .ogg for unrecognized data (Telegram voice notes).
    """
    if isinstance(source, bytes):
        data = source
        suffix = _guess_suffix_from_bytes(data)
        provided_ext = None
    elif isinstance(source, (str, Path)):
        path = Path(source)
        suffix = path.suffix.lower()
        provided_ext = suffix
        if suffix not in AUDIO_FORMATS:
            raise ValueError(
                f"Unsupported audio format: {suffix or 'no extension'}. "
                f"Supported: {', '.join(sorted(AUDIO_FORMATS))}"
            )
        data = path.read_bytes()
    elif hasattr(source, "read"):
        # File-like object / raw file handle — read synchronously.
        data = source.read()
        # When the source itself carries a filename (e.g. a path-like or a
        # custom wrapper), use it; otherwise fall back to byte-signature detection.
        provided_ext = _guess_suffix_from_filename(getattr(source, "filename", None))
        # Always reject an unsupported extension, regardless of byte content.
        if provided_ext and provided_ext not in AUDIO_FORMATS:
            raise ValueError(
                f"Unsupported audio format: {provided_ext or 'no extension'}. "
                f"Supported: {', '.join(sorted(AUDIO_FORMATS))}"
            )
        # If an extension was provided (and is valid), trust it.
        # If no extension was provided, fall back to byte-signature detection.
        suffix = provided_ext if provided_ext else _guess_suffix_from_bytes(data)
    else:
        raise ValueError("Unsupported audio source type")

    if not data:
        raise ValueError("Audio is empty")

    if len(data) > MAX_AUDIO_BYTES:
        raise ValueError(
            f"Audio too large: {len(data)} bytes. Max is {MAX_AUDIO_BYTES} bytes (10 MB)"
        )

    mime = MIME_BY_EXT.get(suffix, "audio/ogg")
    duration = _estimate_duration(data, suffix)

    if duration < MIN_AUDIO_DURATION:
        # Still accept it, but flag for no synthetic voice analysis
        pass

    return data, mime, duration


def _guess_suffix_from_bytes(data: bytes) -> str:
    if data[:4] == b"OggS":
        return ".ogg"
    if data[:3] == b"ID3" or data[:2] == b"\xff\xd8":
        return ".mp3"
    if data[:4] == b"RIFF" and data[8:12] == b"WAVE":
        return ".wav"
    if data[:4] == b"\x00\x00\x00\x1cftypM4A":
        return ".m4a"
    if data[:4] == b"\x1a\x45\xdf\xa3":
        return ".webm"
    if data[:4] == b"fLaC":
        return ".flac"
    # Fallback: try to detect from common markers
    if b"JFIF" in data[:128] or b"Exif" in data[:128]:
        return ".mp3"
    return ".ogg"


def _guess_suffix_from_filename(filename: str | None) -> str:
    """Return the extension from a filename, or the detected suffix from bytes.

    When the filename has a known audio extension, return it. When it has an
    unknown extension, return it anyway so the caller can reject it. When there
    is no filename, return empty string so the caller falls back to byte detection.
    """
    if not filename:
        return ""
    ext = Path(filename).suffix.lower()
    return ext if ext else ""


def _estimate_duration(data: bytes, suffix: str) -> float:
    """Estimate audio duration from file size.

    When a proper decoder (ffprobe / pydub) is available, use that instead.
    This fallback uses a rough bytes-per-second estimate.
    """
    try:
        return _duration_from_ffprobe(data, suffix)
    except Exception:
        pass

    try:
        import io

        from pydub import AudioSegment
        seg = AudioSegment.from_file(io.BytesIO(data), format=suffix.lstrip("."))
        return len(seg) / 1000.0
    except Exception:
        pass

    # Fallback: file size / bytes-per-second estimate
    bps = _BYTES_PER_SECOND_ESTIMATE.get(suffix, 16_000)
    return max(0.0, len(data) / bps)


def _duration_from_ffprobe(data: bytes, suffix: str) -> float:
    """Use ffprobe to get exact duration. Returns duration in seconds."""
    import subprocess
    import tempfile

    suffix_clean = suffix.lstrip(".")
    with tempfile.NamedTemporaryFile(suffix=f".{suffix_clean}", delete=False) as tmp:
        tmp.write(data)
        tmp_path = tmp.name

    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                tmp_path,
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            return float(result.stdout.strip())
    finally:
        import os
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

    raise RuntimeError("ffprobe failed to parse duration")
