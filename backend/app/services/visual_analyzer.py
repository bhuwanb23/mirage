"""Visual analysis via Gemini Vision (Phase 1.3, Step 2b).

Analyzes a screenshot for visual signs of a fake UI: blurred logos,
inconsistent fonts, suspicious URL bars, etc. Only runs when
GEMINI_API_KEY is configured; otherwise returns a neutral result.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger("mirage.visual")


@dataclass
class VisualAnalysis:
    app_identified: str = "Unknown"
    visual_red_flags: list[str] = ()
    looks_legitimate: bool = True
    confidence: float = 0.0
    engine: str = "none"


_VISUAL_PROMPT = """Analyze this screenshot for visual signs of a scam or fake interface:

1. Does this look like a real bank app/website or a fake one?
2. Are there any blurred or pixelated logos?
3. Are the fonts inconsistent (mixing different font families)?
4. Are the colors slightly off from the real brand?
5. Does the URL bar (if visible) show a suspicious domain?
6. Are there any grammatical errors in the UI text?
7. Does the layout look like a legitimate app or a web page pretending to be an app?

Return your visual analysis as JSON:
{
  "app_identified": "WhatsApp" | "SMS" | "Bank App" | "Browser" | "Unknown",
  "visual_red_flags": ["list of visual anomalies"],
  "looks_legitimate": true/false,
  "confidence": 0.0-1.0
}
"""


def analyze_visual(source, mime_hint: Optional[str] = None) -> VisualAnalysis:
    """Run visual analysis on `source` (file path or file-like).

    Returns a VisualAnalysis. When Gemini is unavailable, returns a neutral
    result so callers can proceed with text-based analysis only.
    """
    data, mime = _read_image(source, mime_hint)
    if not data:
        return VisualAnalysis()

    if not _gemini_configured():
        logger.info("Gemini not configured — visual analysis skipped")
        return VisualAnalysis()

    try:
        text = _gemini_vision(data, mime)
        return _parse_visual_json(text)
    except Exception as exc:
        logger.warning("visual analysis failed: %s", exc)
        return VisualAnalysis()


def _read_image(source, mime_hint: Optional[str]) -> tuple[bytes, str]:
    from app.services.image_validator import validate_and_read_image
    if isinstance(source, (str, bytes)):
        return validate_and_read_image(source)
    if hasattr(source, "read"):
        return validate_and_read_image(source)
    return b"", "image/png"


def _gemini_configured() -> bool:
    try:
        from app.config import settings
        return bool(settings.gemini_api_key)
    except Exception:
        return False


def _gemini_vision(image_bytes: bytes, mime: str) -> str:
    from google import genai
    from google.genai import types

    from app.config import settings

    client = genai.Client(api_key=settings.gemini_api_key)
    part = types.Part.from_bytes(data=image_bytes, mime_type=mime)

    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=[_VISUAL_PROMPT, part],
        config=types.GenerateContentConfig(
            temperature=0.2,
            max_output_tokens=1500,
        ),
    )
    return response.text or "{}"


# Simple JSON parsing — try to extract the visual JSON from Gemini's response


def _parse_visual_json(text: str) -> VisualAnalysis:
    # Try to find JSON object in the response
    match = re.search(r'\{[^}]*"app_identified"[^}]*\}', text, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group(0))
            return VisualAnalysis(
                app_identified=data.get("app_identified", "Unknown"),
                visual_red_flags=data.get("visual_red_flags", []),
                looks_legitimate=data.get("looks_legitimate", True),
                confidence=float(data.get("confidence", 0.0)),
                engine="gemini",
            )
        except (json.JSONDecodeError, ValueError):
            pass

    # Fallback: try full JSON parse
    try:
        data = json.loads(text)
        if isinstance(data, dict) and "app_identified" in data:
            return VisualAnalysis(
                app_identified=data.get("app_identified", "Unknown"),
                visual_red_flags=data.get("visual_red_flags", []),
                looks_legitimate=data.get("looks_legitimate", True),
                confidence=float(data.get("confidence", 0.0)),
                engine="gemini",
            )
    except (json.JSONDecodeError, ValueError):
        pass

    # Last resort: return empty visual analysis
    return VisualAnalysis(engine="gemini")
