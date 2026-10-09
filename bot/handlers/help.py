""" /help — detailed usage guide (Phase 2.5 spec text). """

from __future__ import annotations

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

HELP_TEXT = """\
<b>🛡️ Mirage Help</b>

<b>Forwarding messages:</b>
• Long-press any message in WhatsApp/Telegram
• Select "Forward"
• Choose "Mirage Scam Shield"
• I'll analyze it instantly

<b>Voice notes:</b>
• Forward any suspicious voice note
• I'll transcribe it and check for AI-generated voices

<b>Screenshots:</b>
• Take a screenshot of any suspicious page
• Send it to me
• I'll read the text and check for fake UI

<b>URLs:</b>
• Paste any suspicious link
• I'll check the domain age and legitimacy

<b>Commands:</b>
/check &lt;text&gt; — Quick analysis
/elder — Elder Mode (voice replies, big text)
/family — Family alert setup
/help — This message

<b>Privacy:</b>
• I don't store your messages
• Analysis happens in real-time
• Your data is never shared

Report scams: 📞 1930 | 🌐 cybercrime.gov.in
"""


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(
        HELP_TEXT, parse_mode=ParseMode.HTML, disable_web_page_preview=True
    )
