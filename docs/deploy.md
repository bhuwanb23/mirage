# Deployment

Everything here is manual on purpose — no deploys run on commit.

## Order of operations

Provision the data layer **first**. The backend boots without it (soft-init), but
nothing downstream will work.

### 1. Supabase

1. Create a project at <https://supabase.com>.
2. SQL Editor → paste `backend/db/001_init_tables.sql` → **Run**.
   Verifies: 6 tables, 4 enums, RLS policies, `updated_at` trigger.
3. Project Settings → API → copy:
   - `Project URL` → `SUPABASE_URL`
   - `anon public` key → `SUPABASE_ANON_KEY`
   - `service_role` key → `SUPABASE_SERVICE_ROLE_KEY` (server-side only, never in the frontend)

### 2. Neo4j

1. Create a free Aura instance at <https://neo4j.com/cloud/aura-free>.
2. In Browser, paste `backend/db/002_neo4j_constraints.cypher` → Run.
   Verifies: 8 constraints + 1 fulltext index.
3. Copy the bolt URI + password → `NEO4J_URI`, `NEO4J_PASSWORD`.

### 3. LLM keys

| Provider | Get it | Env var | Needed for |
| --- | --- | --- | --- |
| Groq | <https://console.groq.com> | `GROQ_API_KEY` | chat + Whisper transcription |
| Gemini | <https://aistudio.google.com> | `GEMINI_API_KEY` | image/screenshot analysis |
| Ollama | local (`ollama serve`) | none | free fallback, runs on your machine |

Order of preference is **Groq → Gemini → Ollama** (`LLM_PROVIDER=auto`).
Groq's free tier is fast; set one key and most of Phase 2 works.

### 4. Local backend

```powershell
cd backend
Copy-Item .env.example .env   # then edit values
uv sync
uv run uvicorn app.main:app --port 8000
```

Verify: `Invoke-WebRequest http://localhost:8000/health` → `200`.

### 5. Local frontend

```powershell
cd frontend
npm install
Copy-Item .env.example .env.local
npm run dev
```

Verify: <http://localhost:3000> — the Dashboard card shows a green `GET /health` probe.

### 6. Bot

```powershell
cd bot
Copy-Item .env.example .env   # add TELEGRAM_BOT_TOKEN from @BotFather
uv sync
uv run python main.py
```

Verify: message the bot `/start` → welcome text.

### 7. Render

`render.yaml` at the repo root is a blueprint with three services:

| Service | Type | Notes |
| --- | --- | --- |
| `mirage-api` | web (python) | `rootDir: backend`, health check `/health` |
| `mirage-web` | static | `rootDir: frontend` — see caveat below |
| `mirage-bot` | worker (python) | `rootDir: bot`, long-running polling |

In Render → New → Blueprint → point at the repo. Fill every `sync: false` env var
in the dashboard. **Environment is `production`**, which makes the backend
hard-fail on missing required keys — that is intended.

> **Static-site caveat:** `mirage-web` assumes an export step. Next.js 16 App
> Router needs `output: "export"` in `frontend/next.config.ts` plus asset
> rewrites for a true static build. If you'd rather keep server rendering,
> switch that service to `runtime: node` with `npm run build && npm start`.
> Both paths are untested — pick one and confirm before relying on it.

## Never deploy

- `SUPABASE_SERVICE_ROLE_KEY` to the frontend — it bypasses RLS.
- `.env` files — they're gitignored; Render stores secrets in its dashboard.
- `TELEGRAM_BOT_TOKEN` anywhere except the bot worker.

## Post-deploy smoke test

```powershell
Invoke-WebRequest https://<your-api>/health
```

Expect `200` with `providers.supabase: true` and `providers.neo4j: true`.
Any `false` means step 1 or 2 above is incomplete.
