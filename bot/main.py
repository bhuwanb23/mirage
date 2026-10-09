"""Mirage Telegram bot entrypoint (Phase 2).

Registration order matters — first matching handler wins (spec):

  1. /start  /help  /check  /elder  /family      commands
  2. photo / image-document                       image handler
  3. voice / audio                                voice handler
  4. text & ~command & URL-only                   URL handler
  5. text & ~command                              text catch-all

Run:  cd bot && uv run python main.py
"""

from __future__ import annotations

import logging
import os
import sys

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from handlers import check, elder, family, start
from handlers import help as help_mod

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=logging.INFO,
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger("mirage.bot")


def load_token() -> str:
    # .env support without a dependency: tiny parser.
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(env_path):
        for line in open(env_path, encoding="utf-8"):
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())

    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        print("TELEGRAM_BOT_TOKEN missing. Copy bot/.env.example to bot/.env and fill it.")
        sys.exit(1)
    return token


def build_app(token: str):
    return (
        ApplicationBuilder()
        .token(token)
        .build()
    )


def _guarded(handler):
    """Wrap an async handler so a crash never kills the polling loop."""
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        try:
            await handler(update, context)
        except Exception:
            logger.exception("handler %s crashed", getattr(handler, "__name__", handler))
    wrapper.__name__ = getattr(handler, "__name__", "handler")
    return wrapper


async def text_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Intercept Elder Mode language picks before normal text analysis."""
    if await elder.language_choice(update, context):
        return
    await check.text_message(update, context)


def register(app) -> None:
    # 1. Commands (explicit, first)
    app.add_handler(CommandHandler("start", _guarded(start.start)))
    app.add_handler(CommandHandler("help", _guarded(help_mod.help_command)))
    app.add_handler(CommandHandler("check", _guarded(check.check_command)))
    app.add_handler(CommandHandler("elder", _guarded(elder.elder)))
    app.add_handler(CommandHandler("family", _guarded(family.family)))

    # 2. Media before text (a photo message can carry a caption)
    app.add_handler(
        MessageHandler(
            filters.PHOTO | filters.Document.IMAGE, _guarded(check.photo_message)
        )
    )
    app.add_handler(
        MessageHandler(filters.VOICE | filters.AUDIO, _guarded(check.voice_message))
    )

    # 3. URL-bearing text before the catch-all text handler (spec order).
    #    Only messages Telegram parsed as containing a URL land here; inside,
    #    url_message() falls through to normal text analysis when the message
    #    has other content besides the URL (spec 2.4 Step 1).
    url_text = filters.TEXT & ~filters.COMMAND & filters.Entity("url")
    app.add_handler(MessageHandler(url_text, _guarded(check.url_message)))

    # 4. General text catch-all — Elder Mode language picks are consumed
    #    first, then normal text analysis (which also short-circuits
    #    URL-only input the entity filter may have missed, e.g. bare
    #    domains like sbi-kyc-verify.xyz).
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, _guarded(text_router)))


def main() -> None:
    token = load_token()
    app = build_app(token)
    register(app)
    logger.info("Mirage bot starting (polling)")
    app.run_polling(allowed_updates=["message"])


if __name__ == "__main__":
    main()
