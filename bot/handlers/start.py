""" /start — welcome + menu. """

from __future__ import annotations

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

WELCOME = """\
<b>Mirage — The Scam Vaccine</b>

I simulate a scam against you <i>before</i> a real scammer ever gets to you.

<b>Commands</b>
/check — forward a text/screenshot/voice and I'll analyse it
/elder — set up a senior's protection profile
/help — what I can do

<b>Quick start</b>
Forward a suspicious SMS or WhatsApp message straight to this chat.
"""

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(
        WELCOME, parse_mode=ParseMode.HTML, disable_web_page_preview=True
    )
