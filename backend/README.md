# Mirage Backend

FastAPI service powering every Mirage layer: the analysis engine (`text · url · image · voice`), fire drills, the live-call guardian WebSocket, the scammer honeypot, memory handshake, and the Neo4j scam-graph APIs.

Part of the [Mirage monorepo](../README.md).

## Run it

```bash
uv sync
cp ../.env.example .env    # empty values are fine in development
uv run uvicorn app.main:app --reload --port 8000
# verify: http://localhost:8000/health
```

## Layout

```
app/
├── main.py            # FastAPI app, CORS, router mounting
├── config.py          # pydantic-settings (reads .env)
├── routers/           # HTTP + WS endpoints
│   ├── analyze.py     # POST /analyze/{text,url,image,voice}
│   ├── guardian.py    # WS /ws/guardian — 5-stage live pipeline
│   ├── honeypot.py    # Honeypot conversation + IOC extraction
│   ├── memory.py      # Memory Handshake questions + verify
│   ├── graph.py       # Neo4j scam-graph read APIs
│   └── health.py      # GET /health
├── services/          # One module per capability
│   ├── *_analyzer.py  # text/url/image/voice analysis (pluggable LLM)
│   ├── stage_tracker.py    # Hook → Authority → Isolation → Urgency → Payment
│   ├── ioc_extractor.py    # phones, UPI IDs, domains, WhatsApp
│   ├── honeypot_engine.py  # AI persona that eats scam bait
│   ├── scam_graph.py       # Neo4j node/edge writes + weather-map queries
│   ├── memory_handshake.py # family-only verification questions
│   └── voice_authenticity.py
└── db/                # Supabase + Neo4j clients, schema SQL
```

## Tests & lint

```bash
uv run pytest          # no API keys needed — LLM is mocked in tests/conftest.py
uv run ruff check .
```

## Environment

All keys live in the root [`.env.example`](../.env.example). `LLM_PROVIDER=auto` picks the first available provider (Groq → Gemini → Ollama) and degrades with a warning when none is set.

For production, see [`docs/deploy.md`](../docs/deploy.md).
