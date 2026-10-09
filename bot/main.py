"""Mirage Telegram bot entrypoint.

Run:  cd bot && uv run python main.py
"""

from __future__ import annotations

import logging
import os
import sys

from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters

from handlers import check, elder, start
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


def register(app) -> None:
    app.add_handler(CommandHandler("start", start.start))
    app.add_handler(CommandHandler("help", help_mod.help_command))
    app.add_handler(CommandHandler("check", check.check_command))
    app.add_handler(CommandHandler("elder", elder.elder))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, check.text_message))
    app.add_handler(MessageHandler(filters.VOICE, check.voice_message))
    app.add_handler(MessageHandler(filters.PHOTO, check.photo_message))


def main() -> None:
    token = load_token()
    app = build_app(token)
    register(app)
    logger.info("Mirage bot starting (polling)")
    app.run_polling(allowed_updates=["message"])


if __name__ == "__main__":
    main()
