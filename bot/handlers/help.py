""" /help — command reference. """

from __future__ import annotations

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

HELP_TEXT = """\
<b>What I do</b>
I turn you into a hard target. Forward me a scam and I tear it apart; later I'll
fire drills at you so the real thing feels rehearsed.

<b>Commands</b>
/check — analyse a message (text, screenshot, voice)
/elder — senior protection profile
/help — this message

<b>Privacy</b>
Message text is sent to the Mirage backend for analysis only.
"""

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(
        HELP_TEXT, parse_mode=ParseMode.HTML, disable_web_page_preview=True
    )
