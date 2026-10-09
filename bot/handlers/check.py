""" /check + free-text / voice / photo / URL intake — Phase 2 analysis flow.

Handler entry points (registered by main.py in spec order):
  check_command   /check <text>          — quick analysis of pasted text
  url_message     bare URL               — focused domain analysis (2.4)
  text_message    any other text         — scam verdict (2.1)
  voice_message   voice/audio notes      — transcript + voice score (2.2)
  photo_message   photos/image documents — OCR + visual analysis (2.3)

Shared flow: validate → typing indicator + temporary "Analyzing…" message →
call the backend → edit the temporary message with the formatted verdict →
fire the family alert when rules pass → Elder Mode voice reply.
"""

from __future__ import annotations

import logging
import re
import time
from typing import Optional

from telegram import Update
from telegram.constants import ParseMode
from telegram.error import TelegramError
from telegram.ext import ContextTypes

from utils import alert_dispatcher as state
from utils import api, notify
from utils.elder_formatter import simplify
from utils.formatter import (
    esc,
    format_image_block,
    format_url_block,
    format_verdict,
    format_voice_block,
    percent,
    risk_emoji,
)

logger = logging.getLogger("mirage.bot.check")

MAX_TEXT = 4000
GREETINGS = {
    "hi", "hello", "hey", "yo", "hola", "namaste", "namaskar", "salam",
    "good morning", "good evening", "good afternoon", "ok", "okay", "test",
}

GREETING_REPLY = (
    "\U0001f44b <b>Hi!</b> Forward me any suspicious message, voice note, or "
    "screenshot and I'll check if it's a scam. Type /help for more info."
)

URL_ONLY_RE = re.compile(
    r"^(https?://)?(www\.)?[a-zA-Z0-9-]+(\.[a-zA-Z0-9-]+)+(:\d+)?(/\S*)?$"
)
PHONE_ONLY_RE = re.compile(r"^\+?[\d\s()-]{10,18}$")
PHONE_TIP = (
    "\n\n<i>Tip: If you received a call from this number, forward the call "
    "recording for better analysis.</i>"
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def looks_like_url(text: str) -> bool:
    """True when the message is ONLY a URL (spec 2.4 Step 1)."""
    return bool(URL_ONLY_RE.match((text or "").strip()))


def normalize_url(text: str) -> str:
    """Add https:// and strip trailing punctuation (spec 2.4 Step 2)."""
    url = (text or "").strip().rstrip(".,;:!?)")
    if not re.match(r"^https?://", url, re.IGNORECASE):
        url = "https://" + url
    return url


def is_greeting(text: str) -> bool:
    return (text or "").strip().lower().rstrip("!.") in GREETINGS


def is_emoji_only(text: str) -> bool:
    stripped = (text or "").strip()
    return bool(stripped) and not any(c.isalnum() for c in stripped)


def _user_ctx(update: Update) -> tuple[Optional[int], int, str]:
    user = update.effective_user
    chat = update.effective_chat
    return (
        (user.id if user else None),
        chat.id if chat else 0,
        (user.first_name if user and user.first_name else "A user"),
    )


async def _finish(
    context: ContextTypes.DEFAULT_TYPE,
    update: Update,
    progress,
    body: dict,
    preamble: Optional[str] = None,
) -> None:
    """Format the verdict (Elder-aware), deliver it, then fire family alert."""
    _user_id, chat_id, first_name = _user_ctx(update)
    verdict = body.get("verdict") or {}

    if state.elder_enabled(_user_id):
        text = simplify(verdict)
        if preamble:
            text = f"{preamble}\n\n{text}"
    else:
        text = format_verdict(verdict)
        if preamble:
            text = f"{preamble}\n\n{text}"

    await notify.deliver(context, chat_id, text, progress=progress)
    await notify.send_elder_voice(context, chat_id, verdict, user_id=_user_id)
    await notify.maybe_family_alert(context, _user_id, chat_id, first_name, verdict)

    logger.info(
        "analysed user=%s type=text is_scam=%s conf=%s",
        _user_id, verdict.get("is_scam"), verdict.get("confidence"),
    )


# ---------------------------------------------------------------------------
# 2.5 — /check command
# ---------------------------------------------------------------------------

async def check_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    if not msg:
        return
    if not context.args:
        await msg.reply_text(
            "Usage: <code>/check &lt;paste suspicious message here&gt;</code>\n\n"
            "Example: <code>/check Dear Customer, your SBI account will be blocked…</code>\n\n"
            "You can also just forward the message directly, or paste a link.",
            parse_mode=ParseMode.HTML,
        )
        return

    text = " ".join(context.args).strip()
    if len(text) < 10:
        await msg.reply_text("Please provide more text for accurate analysis.")
        return

    if looks_like_url(text):
        await _run_url_analysis(update, context, normalize_url(text))
        return
    await _run_text_analysis(update, context, text)


# ---------------------------------------------------------------------------
# 2.1 — Text message handler
# ---------------------------------------------------------------------------

async def text_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    if not msg or not msg.text or msg.text.startswith("/"):
        return
    await _run_text_analysis(update, context, msg.text)


async def _run_text_analysis(
    update: Update, context: ContextTypes.DEFAULT_TYPE, raw_text: str
) -> None:
    msg = update.effective_message
    _user_id, chat_id, _name = _user_ctx(update)

    # -- validation --------------------------------------------------------
    text = (raw_text or "").strip()
    if not text:
        await msg.reply_text("Please send a message with actual content.")
        return
    if is_greeting(text):
        await msg.reply_text(GREETING_REPLY, parse_mode=ParseMode.HTML)
        return
    if is_emoji_only(text):
        await msg.reply_text(
            "I need text to analyze. Please forward the full suspicious message."
        )
        return
    if len(text) < 5:
        await msg.reply_text(
            "Message too short to analyze. Please forward the full scam message."
        )
        return
    if len(text) > MAX_TEXT:
        text = text[:MAX_TEXT] + "\n(Message truncated for analysis)"

    # -- URL-only short-circuit (registered earlier, but /check can land here)
    if looks_like_url(text):
        await _run_url_analysis(update, context, normalize_url(text))
        return

    # -- progress + analysis ----------------------------------------------
    await notify.typing(context, chat_id)
    progress = await notify.send_progress(context, chat_id, "\U0001f50d Analyzing your message…")
    t0 = time.perf_counter()

    try:
        body = await api.analyze_text(text)
    except Exception as exc:
        await notify.reply_error(context, chat_id, exc, progress=progress)
        return

    if not isinstance(body, dict) or not isinstance(body.get("verdict"), dict):
        await notify.deliver(
            context,
            chat_id,
            "⚠️ Analysis failed due to a server error. Please try again in a moment.",
            progress=progress,
        )
        return

    preamble = PHONE_TIP if PHONE_ONLY_RE.match(text) else None
    await _finish(context, update, progress, body, preamble=preamble)
    logger.info("text analysis took %.0f ms", (time.perf_counter() - t0) * 1000)


# ---------------------------------------------------------------------------
# 2.4 — URL handler
# ---------------------------------------------------------------------------

async def url_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Registered BEFORE the catch-all text handler (spec order)."""
    msg = update.effective_message
    if not msg or not msg.text or msg.text.startswith("/"):
        return
    if not looks_like_url(msg.text):
        # Not URL-only → behave exactly like the text handler.
        await _run_text_analysis(update, context, msg.text)
        return
    await _run_url_analysis(update, context, normalize_url(msg.text))


async def _run_url_analysis(
    update: Update, context: ContextTypes.DEFAULT_TYPE, url: str
) -> None:
    _user_id, chat_id, _name = _user_ctx(update)

    domain = re.sub(r"^https?://", "", url).split("/")[0]

    await notify.typing(context, chat_id)
    progress = await notify.send_progress(
        context, chat_id, f"\U0001f517 Checking domain: {esc(domain)}…"
    )

    try:
        body = await api.analyze_url(url)
    except Exception as exc:
        await notify.reply_error(context, chat_id, exc, progress=progress)
        return

    urls = (body or {}).get("urls_analyzed") or []
    if not urls:
        await notify.deliver(
            context,
            chat_id,
            "\U0001f517 <b>DOMAIN ANALYSIS</b>\n\nNo URL could be extracted from that input.",
            progress=progress,
        )
        return

    # Highest-risk URL first (spec 2.4 edge case).
    info = max(urls, key=lambda u: float(u.get("risk_score") or 0.0))
    text = format_url_block(info)
    text += _url_action(info)

    # Shortener / IP-address special cases (spec edge cases).
    shortener_note = _url_special_notes(info, url)
    if shortener_note:
        text = f"{text}\n\n{shortener_note}"

    await notify.deliver(context, chat_id, text, progress=progress)

    # Feed the risk into family alerts as a lightweight pseudo-verdict.
    risk = float(info.get("risk_score") or 0.0)
    if info.get("is_suspicious") and risk >= 0.6:
        await notify.maybe_family_alert(
            context,
            _user_id,
            chat_id,
            "A user",
            {
                "is_scam": True,
                "confidence": risk,
                "scam_type": "unknown",
                "risk_level": "high" if risk >= 0.7 else "medium",
                "summary": f"A suspicious link ({domain}) was shared with this person.",
            },
        )


def _url_action(info: dict) -> str:
    if info.get("is_suspicious"):
        target = info.get("lookalike_target")
        tail = f" The real site is {esc(target)}." if target else ""
        return f"\n\n\U0001f6a8 <b>DO NOT visit this link.</b>{tail}"
    if float(info.get("risk_score") or 0.0) >= 0.3:
        return "\n\n⚠️ <b>Be careful with this link.</b> Verify the sender before opening it."
    return "\n\n✅ This domain appears legitimate."


def _url_special_notes(info: dict, url: str) -> str:
    from utils.constants import URL_SHORTENER_DOMAINS

    domain = (info.get("domain") or "").lower()
    notes = []
    if domain in URL_SHORTENER_DOMAINS or any(
        domain.endswith("." + s) for s in URL_SHORTENER_DOMAINS
    ):
        notes.append(
            "⚠️ This is a shortened URL. The real destination is hidden. "
            "Shortened URLs are commonly used by scammers. Do NOT click unless "
            "you trust the sender."
        )
    if re.fullmatch(r"\d{1,3}(\.\d{1,3}){3}", domain):
        notes.append(
            "\U0001f6a8 This link uses an IP address instead of a domain name. "
            "This is a strong scam indicator. Legitimate services always use "
            "domain names."
        )
    if "docs.google.com" in domain or "forms.gle" in domain or "forms.google" in domain:
        notes.append(
            "⚠️ Scammers sometimes use Google Forms to collect personal "
            "information. Verify who created this form before entering any data."
        )
    return "\n\n".join(notes)


# ---------------------------------------------------------------------------
# 2.2 — Voice note handler
# ---------------------------------------------------------------------------

async def voice_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    if not msg:
        return
    _user_id, chat_id, _name = _user_ctx(update)

    voice = msg.voice or msg.audio
    if voice is None:
        return

    duration = getattr(voice, "duration", None) or 0
    file_size = getattr(voice, "file_size", None) or 0

    if duration and duration < 1:
        await msg.reply_text("Audio too short to analyze. Please send a longer recording.")
        return
    if duration and duration > 120:
        await msg.reply_text(
            "Audio too long (max 2 minutes). Please send a shorter clip or the "
            "most suspicious part."
        )
        return
    if file_size and file_size > 10 * 1024 * 1024:
        await msg.reply_text("Audio file too large (max 10 MB). Please compress or trim it.")
        return

    await notify.typing(context, chat_id)
    progress = await notify.send_progress(
        context,
        chat_id,
        "\U0001f3a4 Analyzing voice note… This may take a few seconds.",
    )

    try:
        tg_file = await context.bot.get_file(voice.file_id)
        payload = bytes(await tg_file.download_as_bytearray())
    except TelegramError as exc:
        await notify.deliver(
            context,
            chat_id,
            "Could not process this audio file. Please try re-recording or "
            "re-forwarding.",
            progress=progress,
        )
        logger.warning("voice download failed: %s", exc)
        return

    filename = getattr(voice, "file_name", None) or "voice.ogg"
    content_type = getattr(voice, "mime_type", None) or "audio/ogg"

    try:
        body = await api.analyze_audio(filename, payload, content_type)
    except Exception as exc:
        await notify.reply_error(context, chat_id, exc, progress=progress)
        return

    if not isinstance(body, dict) or not isinstance(body.get("verdict"), dict):
        await notify.deliver(
            context,
            chat_id,
            "⚠️ Analysis failed due to a server error. Please try again in a moment.",
            progress=progress,
        )
        return

    transcript = str(body.get("transcript") or "")
    if not transcript.strip() or transcript == "No speech detected in audio":
        await notify.deliver(
            context,
            chat_id,
            "No clear speech detected in this audio. Please send a recording "
            "with clear voice.",
            progress=progress,
        )
        return

    if state.elder_enabled(_user_id):
        text = simplify(body["verdict"])
    else:
        preamble = format_voice_block(
            transcript,
            str(body.get("detected_language") or "en"),
            float(body.get("synthetic_voice_score") or 0.0),
            str(body.get("voice_verdict") or "unknown"),
        )
        text = f"{preamble}\n\n{format_verdict(body['verdict'])}"

    await notify.deliver(context, chat_id, text, progress=progress)
    await notify.send_elder_voice(context, chat_id, body["verdict"], user_id=_user_id)
    await notify.maybe_family_alert(
        context, _user_id, chat_id, _name_for(update), body["verdict"]
    )


# ---------------------------------------------------------------------------
# 2.3 — Image / screenshot handler
# ---------------------------------------------------------------------------

async def photo_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    if not msg:
        return
    _user_id, chat_id, _name = _user_ctx(update)

    # Highest resolution for photos; documents when sent as files.
    if msg.photo:
        target = msg.photo[-1]
        filename, content_type = "photo.jpg", "image/jpeg"
    elif msg.document:
        target = msg.document
        mime = (getattr(msg.document, "mime_type", "") or "").lower()
        if not mime.startswith("image/"):
            await msg.reply_text(
                "Unsupported file type. Please send an image (jpg, png, or webp)."
            )
            return
        filename = getattr(msg.document, "file_name", None) or "image.png"
        content_type = mime
    else:
        return

    file_size = getattr(target, "file_size", None) or 0
    if file_size > 5 * 1024 * 1024:
        await msg.reply_text("Image too large (max 5 MB). Please compress or crop it.")
        return

    await notify.typing(context, chat_id)
    progress = await notify.send_progress(
        context,
        chat_id,
        "\U0001f4f8 Analyzing screenshot… Reading text and checking for fake UI elements.",
    )

    try:
        tg_file = await context.bot.get_file(target.file_id)
        payload = bytes(await tg_file.download_as_bytearray())
    except TelegramError as exc:
        await notify.deliver(
            context,
            chat_id,
            "Could not process this image. Please try again with a different screenshot.",
            progress=progress,
        )
        logger.warning("image download failed: %s", exc)
        return

    try:
        body = await api.analyze_image(filename, payload, content_type)
    except Exception as exc:
        await notify.reply_error(context, chat_id, exc, progress=progress)
        return

    if not isinstance(body, dict) or not isinstance(body.get("verdict"), dict):
        await notify.deliver(
            context,
            chat_id,
            "⚠️ Analysis failed due to a server error. Please try again in a moment.",
            progress=progress,
        )
        return

    ocr_text = str(body.get("ocr_text") or "")
    verdict = body["verdict"]

    if not ocr_text.strip():
        await notify.deliver(
            context,
            chat_id,
            "No text found in this image. This appears to be a photo, not a "
            "screenshot. Please forward the actual scam message or screenshot.",
            progress=progress,
        )
        return

    if state.elder_enabled(_user_id):
        text = simplify(verdict)
    else:
        preamble = format_image_block(
            ocr_text,
            str(body.get("visual_analysis_app") or "Unknown"),
            body.get("visual_red_flags") or [],
        )
        text = f"{preamble}\n\n{format_verdict(verdict)}"

    # QR-code warning (spec edge case).
    if "qr code" in ocr_text.lower() or "qr code" in " ".join(
        verdict.get("red_flags") or []
    ).lower():
        text += (
            "\n\n⚠️ <b>This image contains a QR code.</b> NEVER scan a QR code to "
            "<b>RECEIVE</b> money. QR codes are only for SENDING payments."
        )

    await notify.deliver(context, chat_id, text, progress=progress)
    await notify.send_elder_voice(context, chat_id, verdict, user_id=_user_id)
    await notify.maybe_family_alert(context, _user_id, chat_id, _name_for(update), verdict)


# ---------------------------------------------------------------------------
# Misc
# ---------------------------------------------------------------------------

def _name_for(update: Update) -> str:
    user = update.effective_user
    return (user.first_name if user and user.first_name else "A user")


__all__ = [
    "check_command",
    "text_message",
    "voice_message",
    "photo_message",
    "url_message",
    "looks_like_url",
    "normalize_url",
    "risk_emoji",
    "percent",
]
