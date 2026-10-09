"""OCR engine (Phase 1.3, Step 2 + free-OCR priority).

Priority chain:
  1. Local OCR engine (plugable — RapidOCR, PaddleOCR, etc.)
  2. Gemini Vision OCR (when GEMINI_API_KEY is configured)
  3. Empty string (graceful degradation — no OCR available)

All engines are loaded lazily so the module imports even when no engine
is installed.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from app.services.image_validator import validate_and_read_image

logger = logging.getLogger("mirage.ocr")

OCR_SYSTEM_PROMPT = (
    "Extract ALL text visible in this image exactly as it appears. "
    "Return ONLY the raw text, nothing else."
)

OCR_USER_PROMPT = (
    "Extract ALL text visible in this screenshot exactly as it appears. Include:\n"
    "- Sender name/number\n"
    "- Message content\n"
    "- Any URLs or links\n"
    "- Any phone numbers\n"
    "- Any UPI IDs\n"
    "- Any amounts (Rs/₹)\n"
    "- Timestamps\n"
    "- App name (WhatsApp, SMS, etc.) if visible\n\n"
    "Return the extracted text in a structured format.\n"
)


class OCRResult:
    def __init__(self, text: str = "", engine: str = "none", model: str = ""):
        self.text = text
        self.engine = engine
        self.model = model


# ---------------------------------------------------------------------------
# Local OCR engine registry — pluggable
# ---------------------------------------------------------------------------

_local_engine: Optional[object] = None
_local_engine_name = "none"


def _try_load_local_engine():
    """Try to load a local OCR engine. Returns (engine, name) or (None, "none")."""
    global _local_engine, _local_engine_name
    if _local_engine is not None:
        return _local_engine, _local_engine_name

    for engine_name, loader in _LOCAL_ENGINE_LOADERS:
        try:
            engine = loader()
            if engine is not None:
                _local_engine = engine
                _local_engine_name = engine_name
                logger.info("local OCR engine loaded: %s", engine_name)
                return engine, engine_name
        except Exception as exc:
            logger.debug("local OCR %s unavailable: %s", engine_name, exc)
    return None, "none"


def _run_local_ocr(image_bytes: bytes, mime: str) -> Optional[str]:
    engine, name = _try_load_local_engine()
    if engine is None:
        return None
    try:
        result = engine(image_bytes, mime)
        return result or ""
    except Exception as exc:
        logger.warning("local OCR %s failed: %s", name, exc)
        return None


# ---------------------------------------------------------------------------
# Gemini Vision OCR fallback
# ---------------------------------------------------------------------------

_got_got_gemini = False
_gemini_available = False


def _gemini_available_check():
    global _gemini_available
    if _gemini_available:
        return True
    try:
        from app.config import settings
        if not settings.gemini_api_key:
            return False
        from google import genai
        client = genai.Client(api_key=settings.gemini_api_key)
        # Quick check: list models
        models = client.models.list()
        if models:
            _gemini_available = True
            return True
    except Exception:
        pass
    return False


def _run_gemini_ocr(image_bytes: bytes, mime: str) -> Optional[str]:
    """Send image to Gemini Vision for OCR. Returns text or None."""
    try:
        from google import genai
        from google.genai import types

        from app.config import settings

        client = genai.Client(api_key=settings.gemini_api_key)
        part = types.Part.from_bytes(data=image_bytes, mime_type=mime)

        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[OCR_USER_PROMPT, part],
            config=types.GenerateContentConfig(
                temperature=0.2,
                max_output_tokens=1500,
            ),
        )
        return response.text or ""
    except Exception as exc:
        logger.warning("Gemini OCR failed: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def ocr_image(source, mime_hint: Optional[str] = None) -> OCRResult:
    """Run OCR on `source` (file path, UploadFile, or bytes).

    Returns OCRResult with extracted text and the engine used.
    """
    if isinstance(source, str):
        # File path — convert to Path for validate_and_read_image
        source = Path(source)
    if isinstance(source, Path):
        data, mime = validate_and_read_image(source)
    elif hasattr(source, "read"):
        # File-like / UploadFile
        suffix = getattr(source, "filename", "")
        if suffix:
            ext = Path(suffix).suffix.lower()
            mime = mime_hint or {"png": "image/png", "jpg": "image/jpeg",
                                  "jpeg": "image/jpeg", "webp": "image/webp"}.get(ext, "image/png")
        else:
            mime = mime_hint or "image/png"
        data = source.read()
        if not data:
            return OCRResult(engine="none")
    else:
        data = source
        mime = mime_hint or "image/png"

    if not data:
        return OCRResult(engine="none")

    # 1. Local OCR
    text = _run_local_ocr(data, mime)
    if text:
        return OCRResult(text=text, engine=_local_engine_name, model="local")

    # 2. Gemini Vision
    if _gemini_available_check():
        text = _run_gemini_ocr(data, mime)
        if text:
            return OCRResult(text=text, engine="gemini", model="gemini-2.0-flash")

    # 3. Nothing available
    logger.info("no OCR engine available")
    return OCRResult(engine="none")


# ---------------------------------------------------------------------------
# Pluggable local engine loaders — add new engines here
# ---------------------------------------------------------------------------

_LOCAL_ENGINE_LOADERS: list[tuple[str, callable]] = []


def register_local_engine(name: str, loader: callable):
    """Register a local OCR engine loader.

    `loader` is a callable that returns an OCR function (image_bytes, mime) -> str
    or None if it can't run. Called lazily on first OCR request.
    """
    _LOCAL_ENGINE_LOADERS.append((name, loader))


def _lazy_rapidocr():
    """RapidOCR (ONNX Runtime) — free, unlimited, no API key."""
    try:
        import rapidocr_onnxruntime
        recognizer = rapidocr_onnxruntime.RapidOCR()
        def _recognize(image_bytes: bytes, mime: str) -> Optional[str]:
            result, _ = recognizer(image_bytes)
            if result:
                return "\n".join(line[1] for line in result)
            return None
        return _recognize
    except Exception as e:
        logger.debug("RapidOCR load failed: %s", e)
        return None


def _lazy_paddleocr():
    """PaddleOCR — free, good multilingual support."""
    try:
        from paddleocr import PaddleOCR
        ocr = PaddleOCR(use_angle_cls=True, lang="en")
        def _recognize(image_bytes: bytes, mime: str) -> Optional[str]:
            result = ocr.ocr(image_bytes, cls=True)
            if result and result[0]:
                return "\n".join(line[1][0] for line in result[0])
            return None
        return _recognize
    except Exception as e:
        logger.debug("PaddleOCR load failed: %s", e)
        return None


# Register available engines
register_local_engine("rapidocr", _lazy_rapidocr)
register_local_engine("paddleocr", _lazy_paddleocr)
