"""Shared Telegram send/edit/notify helpers used by every handler (Phase 2).

Responsibilities:
  - typing indicator + temporary "Analyzing…" message
  - replace the temporary message with the verdict (edit, not new message)
  - split >4096-char verdicts across messages
  - Elder Mode voice replies via Edge-TTS (graceful text-only fallback)
  - Family alert dispatch after any analysis (throttled, no content leak)
"""

from __future__ import annotations

import logging
import re
from typing import Any, Optional

from telegram import Message
from telegram.constants import ChatAction, ParseMode
from telegram.error import BadRequest, TelegramError
from telegram.ext import ContextTypes

from utils import alert_dispatcher as state
from utils import api
from utils.elder_formatter import strip_for_tts, voice_script
from utils.formatter import split_message

logger = logging.getLogger("mirage.bot.notify")

EMOJI_RE = re.compile(
    "["
    "\U0001F600-\U0001F64F"
    "\U0001F300-\U0001F5FF"
    "\U0001F680-\U0001F6FF"
    "\U0001F1E0-\U0001F1FF"
    "\U0001F900-\U0001F9FF"
    "\U0001FA70-\U0001FAFF"
    "\U00002702-\U000027B0"
    "\U0000FE00-\U0000FE0F"
    "]",
    flags=re.UNICODE,
)


# ---------------------------------------------------------------------------
# Progress feedback
# ---------------------------------------------------------------------------

async def typing(context: ContextTypes.DEFAULT_TYPE, chat_id: int) -> None:
    try:
        await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
    except TelegramError:
        pass


async def send_progress(
    context: ContextTypes.DEFAULT_TYPE, chat_id: int, text: str
) -> Optional[Message]:
    """Send the temporary 'Analyzing…' message; returns it for later editing."""
    try:
        return await context.bot.send_message(chat_id=chat_id, text=text)
    except TelegramError as exc:
        logger.warning("progress message failed: %s", exc)
        return None


async def deliver(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    text: str,
    progress: Optional[Message] = None,
    reply_to_message_id: Optional[int] = None,
) -> None:
    """Replace `progress` with `text` (edit), sending any overflow as new messages."""
    chunks = split_message(text)
    first, rest = chunks[0], chunks[1:]

    if progress is not None:
        try:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=progress.message_id,
                text=first,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
            )
            progress = None
        except BadRequest as exc:
            # "message is not modified" or too old — fall through to a new message.
            if "not modified" not in str(exc).lower():
                logger.warning("edit failed: %s", exc)
                progress = None
        except TelegramError as exc:
            logger.warning("edit failed: %s", exc)
            progress = None

    if progress is None and first:
        # No usable progress message → send fresh.
        try:
            await context.bot.send_message(
                chat_id=chat_id,
                text=first,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
                reply_to_message_id=reply_to_message_id,
            )
        except TelegramError as exc:
            logger.error("send failed: %s", exc)
            # Last resort: plain text so the user still gets an answer.
            try:
                await context.bot.send_message(chat_id=chat_id, text=strip_for_tts(first))
            except TelegramError:
                pass

    for chunk in rest:
        try:
            await context.bot.send_message(
                chat_id=chat_id,
                text=chunk,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
            )
        except TelegramError as exc:
            logger.warning("overflow send failed: %s", exc)


async def reply_error(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    exc: Exception,
    progress: Optional[Message] = None,
) -> None:
    await deliver(context, chat_id, api.friendly_error(exc), progress=progress)


# ---------------------------------------------------------------------------
# Elder Mode voice reply (Edge-TTS)
# ---------------------------------------------------------------------------

async def send_elder_voice(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    verdict: dict[str, Any],
    user_id: Optional[int] = None,
) -> bool:
    """Generate + send a voice reply. Returns False when TTS is unavailable.

    Elder Mode state is keyed by user_id; fall back to chat_id for private
    chats where they are identical.
    """
    key = user_id if user_id is not None else chat_id
    if not state.elder_enabled(key):
        return False
    language = state.elder_language(key)
    script = strip_for_tts(voice_script(verdict, language))

    temp_path = None
    try:
        import edge_tts

        from utils.elder_formatter import TTS_VOICES

        voice = TTS_VOICES.get(language, TTS_VOICES["en"])
        temp_path = _tts_temp_path()
        communicate = edge_tts.Communicate(script, voice)
        await communicate.save(temp_path)
        with open(temp_path, "rb") as fh:
            await context.bot.send_voice(chat_id=chat_id, voice=fh.read())
        return True
    except Exception as exc:  # edge-tts needs network; any failure → text-only
        logger.warning("elder TTS failed (%s); text-only fallback", exc)
        return False
    finally:
        if temp_path:
            try:
                import os

                os.unlink(temp_path)
            except OSError:
                pass


def _tts_temp_path() -> str:
    import tempfile

    fd = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    fd.close()
    return fd.name


# ---------------------------------------------------------------------------
# Family alert dispatch (post-analysis)
# ---------------------------------------------------------------------------

async def maybe_family_alert(
    context: ContextTypes.DEFAULT_TYPE,
    user_id: Optional[int],
    chat_id: int,
    first_name: str,
    verdict: dict[str, Any],
) -> None:
    """Fire the family alert when rules pass; never leaks message content."""
    if user_id is None:
        return

    ok, _reason = state.should_alert(user_id, verdict)
    if not ok:
        # Not linked but serious → prompt the user privately (spec 2.7 Step 2).
        if (
            verdict.get("is_scam")
            and float(verdict.get("confidence") or 0) > 0.85
            and state.family_group_for(user_id) is None
            and chat_id == user_id  # private chat only
        ):
            try:
                await context.bot.send_message(
                    chat_id=chat_id, text=state.setup_prompt()
                )
            except TelegramError:
                pass
        return

    group_chat_id = state.family_group_for(user_id)
    scam_type = str(verdict.get("scam_type") or "unknown")
    state.record_alert(user_id, scam_type)

    text = state.format_alert(first_name, verdict)
    try:
        await context.bot.send_message(
            chat_id=group_chat_id,
            text=text,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
        )
    except TelegramError as exc:
        logger.warning("family alert to %s failed: %s", group_chat_id, exc)
        # Bot was probably removed from the group → tell the user privately.
        if chat_id != user_id:
            return
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=(
                    "I can no longer send alerts to your family group. "
                    "Please add me back to the group and send /family again."
                ),
            )
        except TelegramError:
            pass
