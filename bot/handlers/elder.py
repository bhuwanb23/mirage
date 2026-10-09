""" /elder — Elder Mode toggle + language selection (Phase 2.6).

State lives in utils.alert_dispatcher.ELDER_MODE (in-memory):
    {user_id: {"enabled": bool, "language": "hi"|"ta"|"en"}}

Flow:
  /elder (off → on)  → activation message + ask for language (1️⃣2️⃣3️⃣)
  language reply     → stored; default Hindi after 30 s via job queue
  /elder (on → off)  → deactivation message
"""

from __future__ import annotations

import logging

from telegram import KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from utils import alert_dispatcher as state
from utils.elder_formatter import language_name

logger = logging.getLogger("mirage.bot.elder")

AWAITING_LANGUAGE = "elder_awaiting_language"

ACTIVATED = """\
👴 <b>ELDER MODE ACTIVATED</b>

From now on:
✅ I will send voice replies (easier to listen)
✅ I will use simple language
✅ I will use bigger text
✅ I will alert your family if I detect a scam

Which language would you like voice replies in?
1️⃣ Hindi
2️⃣ Tamil
3️⃣ English

<i>Reply 1, 2 or 3 — I'll default to Hindi in 30 seconds.</i>
"""

DEACTIVATED = """\
👴 Elder Mode deactivated.
I'll go back to normal text replies.
Type /elder to re-enable.
"""

LANG_CONFIRM = "✅ Elder Mode language set to {name}. Voice replies will be in {name}."

DEFAULTED = "⏱️ No language chosen — defaulting to Hindi."

_LANGUAGE_CHOICES = {"1": "hi", "2": "ta", "3": "en"}


async def elder(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    user = update.effective_user
    if not msg or not user:
        return

    if state.elder_enabled(user.id):
        state.ELDER_MODE[user.id] = {"enabled": False, "language": state.elder_language(user.id)}
        await msg.reply_text(DEACTIVATED, parse_mode=ParseMode.HTML)
        return

    state.ELDER_MODE[user.id] = {"enabled": True, "language": "hi", "language_pending": True}
    keyboard = ReplyKeyboardMarkup(
        [[KeyboardButton("1️⃣ Hindi"), KeyboardButton("2️⃣ Tamil"), KeyboardButton("3️⃣ English")]],
        one_time_keyboard=True,
        resize_keyboard=True,
    )
    await msg.reply_text(
        ACTIVATED, parse_mode=ParseMode.HTML, reply_markup=keyboard
    )

    # Default to Hindi if no language picked within 30 seconds.
    try:
        context.job_queue.run_once(
            _default_language, when=30, data={"user_id": user.id},
            name=f"elder_lang_{user.id}",
        )
    except AttributeError:
        logger.warning("job_queue unavailable; language default skipped")


async def _default_language(context: ContextTypes.DEFAULT_TYPE) -> None:
    job = context.job
    user_id = job.data.get("user_id")
    current = state.ELDER_MODE.get(user_id)
    if not current or not current.get("enabled"):
        return
    if current.get("language_pending") is not True:
        return
    current["language"] = "hi"
    current["language_pending"] = False
    try:
        await context.bot.send_message(chat_id=user_id, text=DEFAULTED)
    except Exception as exc:  # user may have blocked the bot
        logger.info("default-language notice failed: %s", exc)


async def language_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Consume a 1/2/3 language reply while Elder Mode awaits one.

    Returns True when the message was handled here.
    """
    msg = update.effective_message
    user = update.effective_user
    if not msg or not user:
        return False
    current = state.ELDER_MODE.get(user.id)
    if not current or not current.get("enabled") or not current.get("language_pending"):
        return False

    choice = (msg.text or "").strip()[:1]
    language = _LANGUAGE_CHOICES.get(choice)
    if language is None:
        return False  # not a language pick; let normal handlers run

    current["language"] = language
    current["language_pending"] = False
    await msg.reply_text(
        LANG_CONFIRM.format(name=language_name(language)),
        parse_mode=ParseMode.HTML,
        reply_markup=ReplyKeyboardRemove(),
    )
    # Cancel the pending default job.
    try:
        for job in context.job_queue.get_jobs_by_name(f"elder_lang_{user.id}"):
            job.schedule_removal()
    except AttributeError:
        pass
    return True
