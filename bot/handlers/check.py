""" /check + free-text / voice / photo intake — Phase 2 analysis flow. """

from __future__ import annotations

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from utils import api

PENDING = "Awaiting backend /analyze routes (Phase 2). Meanwhile, I log the intake."


async def check_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if context.args:
        await analyse_text(" ".join(context.args), update)
        return
    await update.effective_message.reply_text(
        "Send me the suspicious message as text, a screenshot, or a voice note.\n"
        "You can also use <code>/check your message here</code>.",
        parse_mode=ParseMode.HTML,
    )


async def analyse_text(text: str, update: Update) -> None:
    msg = update.effective_message
    if not msg:
        return

    result = api.analyze_text(text)
    if result is None:
        await msg.reply_text(
            "📩 <b>Got it.</b>\n" + PENDING,
            parse_mode=ParseMode.HTML,
        )
        return

    verdict = result.get("verdict", "?")
    risk = result.get("risk_level", "?")
    await msg.reply_text(
        f"<b>Verdict:</b> {verdict}\n<b>Risk:</b> {risk}",
        parse_mode=ParseMode.HTML,
    )


async def text_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_message or not update.effective_message.text:
        return
    if update.effective_message.text.startswith("/"):
        return
    await analyse_text(update.effective_message.text, update)


async def voice_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    if not msg or not msg.voice:
        return
    await msg.reply_text(
        "🎙️ <b>Voice note received.</b>\nTranscription arrives with the Whisper "
        "route in Phase 2.",
        parse_mode=ParseMode.HTML,
    )


async def photo_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    if not msg or not msg.photo:
        return
    await msg.reply_text(
        "🖼️ <b>Screenshot received.</b>\nOCR + vision analysis arrives in Phase 2.",
        parse_mode=ParseMode.HTML,
    )
