""" /family — family alert group registration (Phase 2.7 Step 1).

In a group:  links this chat to the sender's account for scam alerts.
In private:  shows setup instructions (or current status).
"""

from __future__ import annotations

import logging

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from utils import alert_dispatcher as state

logger = logging.getLogger("mirage.bot.family")

PRIVATE_HELP = """\
👨‍👩‍👧‍👦 <b>Family Alert Setup</b>

When I detect a high-risk scam, I can automatically alert your family members.

To set up:
1️⃣ Create a Telegram group with your family
2️⃣ Add me (@{bot}) to the group
3️⃣ Send /family in the group to link it

I'll alert the group whenever a family member receives a critical scam.
"""

LINKED_STATUS = (
    "✅ You're linked to a family group. High-risk scam alerts will be sent there."
)
NOT_LINKED = "❌ You're not linked to a family group yet. See /family for setup steps."


async def family(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    chat = update.effective_chat
    user = update.effective_user
    if not msg or not chat or not user:
        return

    if chat.type in ("group", "supergroup"):
        # Link the sender → this group (spec 2.7 Step 1).
        state.link_family_group(user.id, chat.id)
        await msg.reply_text(state.group_linked_message())
        logger.info("family group linked: user=%s chat=%s", user.id, chat.id)
        return

    # Private chat — instructions or status.
    bot_username = (await context.bot.get_me()).username
    text = PRIVATE_HELP.format(bot=bot_username)
    if state.family_group_for(user.id):
        text = f"{LINKED_STATUS}\n\n{text}"
    else:
        text = f"{NOT_LINKED}\n\n{text}"
    await msg.reply_text(text, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
