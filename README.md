# Mirage — The Scam Vaccine

> **Don't detect scams. Vaccinate people against them.**

Mirage simulates a personalized attack against you *before* a real scammer ever reaches you — then debriefs you, scores your resilience, and shields you live when a real one calls.

## Layers

| Layer | What it is | Phase |
|-------|-----------|-------|
| Scam Fire Drill | Personalized simulated scam + debrief + Resilience Score | 3 |
| Live Call Guardian | Real-time 5-stage scam pipeline detection + Memory Handshake | 4 |
| Scammer Hunter | AI honeypot → IOC extraction → Neo4j Scam Graph → weather map | 5 |
| Zero-install bot | Telegram bot: forward text/voice/screenshot → verdict | 2 |

## Monorepo layout

```
mirage/
├── frontend/   # Next.js (App Router) — landing, dashboard, drill, guardian, graph
├── backend/    # FastAPI — analysis engine, drill, guardian, honeypot + DB scripts
├── bot/        # Telegram bot
├── ml/         # Voice cloning notebook + deepfake detection experiments
├── docs/       # Idea, plans, API contracts, deploy guide
└── scripts/    # Repo-level utilities
```

## Quick start (local)

### Backend

```bash
cd backend
uv sync
cp ../.env.example .env    # fill in keys (empty values are fine in development)
uv run uvicorn app.main:app --reload --port 8000
# verify: http://localhost:8000/health
```

### Frontend

```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev
# verify: http://localhost:3000
```

### Bot

```bash
cd bot
uv sync
cp ../.env.example .env    # set TELEGRAM_BOT_TOKEN
uv run python main.py
```

## Environment

All keys are documented in [`.env.example`](.env.example). Nothing is required in `development` — missing providers are skipped with a warning. See [docs/deploy.md](docs/deploy.md) for production deploys.

## Docs

- [Idea](docs/idea/idea.md) · [Tech stack](docs/idea/tech_stack.md)
- [Master plan](docs/plans/master_plan.md) · [Phase 0](docs/plans/phase_0.md) · [Phase 0 checklist](docs/plans/phase_0_checklist.md)
- [API contracts](docs/api_contracts.md) · [Deploy guide](docs/deploy.md)
