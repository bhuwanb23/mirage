""" /elder — senior protection profile setup (Phase 3 onboarding). """

from __future__ import annotations

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

ELDER_TEXT = """\
<b>Elder protection</b>

I'll keep a lightweight profile so drills, alerts, and the Memory Handshake
are tuned for the person you're protecting.

<b>Not built yet</b> — this lands with Phase 3. For now:
1. Add this chat to your family group.
2. Set a Memory Handshake phrase only your family knows.
"""


async def elder(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(
        ELDER_TEXT, parse_mode=ParseMode.HTML, disable_web_page_preview=True
    )
