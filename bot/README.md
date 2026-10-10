# Mirage Telegram Bot

Zero-install surface for Mirage. Forward a text, a voice note, or a screenshot to the bot and get a scam verdict with red flags in seconds — no app to install. Families share one bot; elders just forward.

Part of the [Mirage monorepo](../README.md). All analysis runs on the [backend](../backend/README.md) — the bot is a thin Telegram client over `httpx`.

## Run it

```bash
uv sync
cp .env.example .env
# set TELEGRAM_BOT_TOKEN (from @BotFather)
# MIRAGE_API_URL or BACKEND_URL → backend base URL (default http://localhost:8000)
uv run python main.py
```

## Layout

```
main.py          # entrypoint — polling loop, command registration
handlers/        # per-feature Telegram handlers (text, voice, photo, commands)
utils/           # API client (BACKEND_URL / MIRAGE_API_URL), message formatting
tests/           # pytest (handlers, formatter, family flow, API client)
```

## Tests & lint

```bash
uv run pytest          # no Telegram token needed — network is mocked
uv run ruff check .
```

## Environment

| Var | Required | Default | Notes |
|-----|----------|---------|-------|
| `TELEGRAM_BOT_TOKEN` | yes | — | from [@BotFather](https://t.me/BotFather) |
| `MIRAGE_API_URL` | no | `http://localhost:8000` | backend base URL (matches `render.yaml`) |
| `BACKEND_URL` | no | — | alias; takes precedence over `MIRAGE_API_URL` if both set |
