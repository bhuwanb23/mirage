""" /start — welcome + menu (Phase 2.5 spec text). """

from __future__ import annotations

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

WELCOME = """\
<b>🛡️ Welcome to Mirage — Your AI Scam Shield</b>

I protect you from scams by analyzing messages, voice notes, screenshots, and URLs.

<b>How to use:</b>
1️⃣ Forward me any suspicious message
2️⃣ I'll tell you if it's a scam
3️⃣ I'll explain exactly WHY it's a scam

<b>What I can check:</b>
📝 Text messages (WhatsApp, SMS, email)
🎤 Voice notes and call recordings
📸 Screenshots of fake websites
🔗 Suspicious URLs and links

<b>Commands:</b>
/check &lt;text&gt; — Quick scam check
/elder — Toggle Elder Mode
/family — Set up family alerts
/help — Detailed help

<b>Try it now!</b> Forward me a suspicious message 👇
"""


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(
        WELCOME, parse_mode=ParseMode.HTML, disable_web_page_preview=True
    )
