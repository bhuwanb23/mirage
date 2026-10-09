"""Elder Mode: simplified text + TTS voice scripts (Phase 2.6).

Two responsibilities:
  1. simplify a verdict into plain, jargon-free text (verdict FIRST)
  2. produce a short spoken script (stripped of emojis/markup) for Edge-TTS,
     in English / Hindi / Tamil

Text replies stay English (per project scope); voice scripts are available in
all three languages because TTS reads a fixed short script, not the verdict.
"""

from __future__ import annotations

from typing import Optional

from utils.constants import FOOTER, SCAM_TYPE_READABLE

# ---------------------------------------------------------------------------
# Simplified on-screen text (no jargon, verdict first)
# ---------------------------------------------------------------------------

def simplify(verdict: dict) -> str:
    """Plain-language Elder Mode reply. Verdict is the very first line."""
    if not isinstance(verdict, dict):
        return "⚠️ I could not check this message. Please try again."

    is_scam = bool(verdict.get("is_scam"))
    confidence = float(verdict.get("confidence") or 0.0)
    scam_type = SCAM_TYPE_READABLE.get(
        str(verdict.get("scam_type") or ""), "Unknown Scam Type"
    )

    if is_scam and confidence >= 0.6:
        return _scam_text(scam_type)
    if is_scam or 0.4 <= confidence < 0.6:
        return (
            "\U0001f7e1 <b>Possible dhoka (scam).</b>\n\n"
            "Do not click any link and do not share OTP or PIN.\n"
            "Check with your son or daughter first.\n"
            "Call your bank on the number printed on your card.\n\n"
            f"<i>{FOOTER}</i>"
        )
    return (
        "\U0001f7e2 <b>This message looks OK.</b>\n\n"
        "But always be careful:\n"
        "❌ Never share OTP or PIN with anyone\n"
        "❌ Never send money to unknown people\n"
        "✅ If unsure, ask your family first\n\n"
        "<i>Stay safe!</i>"
    )


def _scam_text(scam_type: str) -> str:
    return (
        "\U0001f6a8\U0001f6a8\U0001f6a8 <b>यह SCAM है! धोखा है!</b> \U0001f6a8\U0001f6a8\U0001f6a8\n"
        "\n"
        "<b>What to do:</b>\n"
        "❌ Do NOT click any link\n"
        "❌ Do NOT share OTP or PIN\n"
        "❌ Do NOT send money\n"
        "✅ Tell your son / daughter\n"
        "✅ Call 1930\n"
        "\n"
        f"<b>Why:</b> This is a {scam_type} trick. Your bank will never ask like this.\n"
        "\n"
        "\U0001f4de Helpline: 1930"
    )


# ---------------------------------------------------------------------------
# Spoken scripts for Edge-TTS (emojis/formatting stripped by caller)
# ---------------------------------------------------------------------------

def voice_script(verdict: dict, language: str = "en") -> str:
    """Short spoken script describing the verdict, in en/hi/ta."""
    if not isinstance(verdict, dict):
        return "Sorry, I could not check this message. Please try again."

    is_scam = bool(verdict.get("is_scam"))
    confidence = float(verdict.get("confidence") or 0.0)
    scam = is_scam and confidence >= 0.6
    uncertain = is_scam or 0.4 <= confidence < 0.6
    lang = (language or "en").lower()

    if lang == "hi":
        return _SCRIPTS["hi"]["scam" if scam else "uncertain" if uncertain else "ok"]
    if lang == "ta":
        return _SCRIPTS["ta"]["scam" if scam else "uncertain" if uncertain else "ok"]
    # English — include the readable scam type when we have one.
    bucket = "scam" if scam else "uncertain" if uncertain else "ok"
    text = _SCRIPTS["en"][bucket]
    if bucket == "scam":
        scam_type = SCAM_TYPE_READABLE.get(str(verdict.get("scam_type") or ""))
        if scam_type:
            text = f"This looks like a {scam_type} scam. " + text
    return text


_SCRIPTS: dict[str, dict[str, str]] = {
    "en": {
        "scam": (
            "Warning from Mirage Scam Shield. This message is a scam. "
            "Do not click any link. Do not share your OTP. Do not send money. "
            "Tell your family and call one nine three zero. Stay safe."
        ),
        "uncertain": (
            "Caution from Mirage Scam Shield. This message may be a scam. "
            "Do not click any link and do not share your OTP. "
            "Check with your family before you act."
        ),
        "ok": (
            "This message looks legitimate. "
            "But never share your OTP with anyone, and always check with your family "
            "if something feels wrong. Stay safe."
        ),
    },
    "hi": {
        "scam": (
            "Namaste. Mirage scam shield ki taraf se chetavni. "
            "Yeh message ek scam hai. Dhokha hai. "
            "Is link par click mat kijiye. Koi OTP mat dijiye. Paise mat bhejiye. "
            "Apne parivaar ko bataiye. One nine three zero par call kijiye. "
            "Surakshit rahiye."
        ),
        "uncertain": (
            "Namaste. Yeh message theek nahi lag raha. Sambhal ke rahein. "
            "Link par click mat kijiye. OTP kisi ko mat dijiye. "
            "Pehle apne parivaar se poochhiye."
        ),
        "ok": (
            "Yeh message theek lagta hai. "
            "Phir bhi OTP kisi ko mat dijiye. "
            "Kuch bhi adbhut lage toh pehle apne parivaar se poochhiye. Surakshit rahiye."
        ),
    },
    "ta": {
        "scam": (
            "Vanakkam. Mirage scam shield ilirundhu echcharikkai. "
            "Idhu oru scam. Mosam. "
            "Indha link-ai click seyyadheenga. OTP kudukkadheenga. Panam anuppadheenga. "
            "Ungal kudumbaththinai theriyapaduthunga. One nine three zero-ku call pannunga. "
            "Paathukonga."
        ),
        "uncertain": (
            "Vanakkam. Idhu scam-a irukkalaam. Maridhaana irunga. "
            "Link-ai click seyyadheenga. OTP yaarukkum kudukkadheenga. "
            "Muthal aaga ungala udanpaalukku kelunga."
        ),
        "ok": (
            "Idhu sariyana message-a theriyum. "
            "Aanaalum OTP yaarukkum kudukkadheenga. "
            "Ethachum samayamma irundha mudhal aaga udanpaalukku kelunga. Paathukonga."
        ),
    },
}

# Voice codes for Edge-TTS per language
TTS_VOICES = {
    "hi": "hi-IN-SwaraNeural",
    "ta": "ta-IN-PallaviNeural",
    "en": "en-IN-NeerjaNeural",
}


def strip_for_tts(text: str) -> str:
    """Remove emojis, HTML tags and markdown so TTS reads only words."""
    import re

    text = re.sub(r"<[^>]+>", "", text)
    # Remove non-BMP chars (emoji) but keep Indic scripts (BMP).
    text = re.sub(r"[\U00010000-\U0010ffff]", "", text)
    text = re.sub(r"[❌✅⚠️🚨📞📊]", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def language_name(code: Optional[str]) -> str:
    return {"hi": "Hindi", "ta": "Tamil", "en": "English"}.get(
        (code or "en").lower(), "English"
    )
