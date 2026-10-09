"""Image validation (Phase 1.3, Step 1).

Accepts png/jpg/jpeg/webp up to 5 MB. Returns raw bytes for downstream
OCR/vision. Raises ValueError on invalid input so callers can map to 400/413.
"""

from __future__ import annotations

from pathlib import Path
from typing import BinaryIO

ALLOWED_MIME_SUFFIX = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}

MAX_IMAGE_BYTES = 5 * 1024 * 1024  # 5 MB


def validate_and_read_image(source: str | Path | BinaryIO) -> tuple[bytes, str]:
    """Read `source` and validate format + size.

    Returns (bytes, mime_type). Raises ValueError with a user-facing message
    on validation failure.
    """
    if isinstance(source, bytes):
        data = source
        suffix = _guess_suffix_from_bytes(data)
    elif isinstance(source, (str, Path)):
        path = Path(source)
        suffix = path.suffix.lower()
        if suffix not in ALLOWED_MIME_SUFFIX:
            raise ValueError(
                f"Unsupported image format: {suffix or 'no extension'}. "
                f"Supported: {', '.join(ALLOWED_MIME_SUFFIX.keys())}"
            )
        data = path.read_bytes()
    elif hasattr(source, "read"):
        # File-like object (e.g. FastAPI UploadFile)
        data = source.read()
        suffix = _guess_suffix_from_bytes(data)

    if not data:
        raise ValueError("Image is empty")

    if len(data) > MAX_IMAGE_BYTES:
        raise ValueError(
            f"Image too large: {len(data)} bytes. Max is {MAX_IMAGE_BYTES} bytes (5 MB)"
        )

    mime = ALLOWED_MIME_SUFFIX.get(suffix, "image/png")
    return data, mime


def _guess_suffix_from_bytes(data: bytes) -> str:
    """Best-effort suffix detection from magic bytes when no filename is available."""
    if data[:4] == b"\x89PNG":
        return ".png"
    if data[:2] == b"\xff\xd8":
        return ".jpg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return ".webp"
    # Fallback to jpg for anything that looks like a JPEG
    if b"JFIF" in data[:128] or b"Exif" in data[:128]:
        return ".jpg"
    return ".png"
