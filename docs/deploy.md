# Deployment

Everything here is manual on purpose — no deploys run on commit.

## Order of operations

Provision the data layer **first**. The backend soft-inits: missing keys log
warnings and the app still boots (`GET /health` works). Features that need a
provider degrade until you fill the secret.

### 1. Supabase

1. Create a project at <https://supabase.com>.
2. SQL Editor → paste `backend/db/001_init_tables.sql` → **Run**.
   Verifies: 6 tables, 4 enums, RLS policies, `updated_at` trigger.
3. Project Settings → API → copy:
   - `Project URL` → `SUPABASE_URL`
   - `anon public` / publishable key → `SUPABASE_ANON_KEY` (or `SUPABASE_PUBLISHABLE_KEY` — both work)

### 2. Neo4j

1. Create a free Aura instance at <https://neo4j.com/cloud/aura-free>.
2. In Browser, paste `backend/db/002_neo4j_constraints.cypher` → Run.
   Verifies: 8 constraints + 1 fulltext index.
3. Copy the bolt URI + password → `NEO4J_URI`, `NEO4J_PASSWORD`, `NEO4J_USERNAME`.

Without Neo4j the scam graph uses an embedded SQLite store and auto-seeds a demo ring on boot.

### 3. LLM keys

| Provider | Get it | Env var | Needed for |
| --- | --- | --- | --- |
| Groq | <https://console.groq.com> | `GROQ_API_KEY` | chat + Whisper transcription |
| Gemini | <https://aistudio.google.com> | `GEMINI_API_KEY` | image/screenshot analysis + chat fallback |
| Ollama | local (`ollama serve`) | none | free local fallback (not available on Render) |

Order of preference is **Groq → Gemini → Ollama** (`LLM_PROVIDER=auto`).

### 4. Local backend

```powershell
cd backend
Copy-Item .env.example .env   # then edit values
uv sync
uv run uvicorn app.main:app --port 8000
```

Verify: `Invoke-WebRequest http://localhost:8000/health` → `200`.
`providers.supabase` / `providers.neo4j` reflect **live client init**, not just env presence.
`providers.graph_backend` is `neo4j` or `sqlite`.

### 5. Local frontend

```powershell
cd frontend
npm install
Copy-Item .env.example .env.local
npm run dev
```

Verify: <http://localhost:3000> — Dashboard loads live score / weather / activity.

Optional demo audio fallbacks:

```powershell
cd backend
uv run python scripts/generate_demo_audio.py
```

### 6. Bot (local — free tier)

Workers are paid on Render. Run the bot locally against the local or Render API:

```powershell
cd bot
Copy-Item .env.example .env   # TELEGRAM_BOT_TOKEN + MIRAGE_API_URL (or BACKEND_URL)
uv sync
uv run python main.py
```

Verify: message the bot `/start` → welcome text.

### 7. Render

`render.yaml` provisions **two free web services**:

| Service | Type | Notes |
| --- | --- | --- |
| `mirage-api` | web (python) | `rootDir: backend`, health check `/health` |
| `mirage-web` | web (node) | Next.js `npm run build && npm start` |

In Render → New → Blueprint → point at the repo. Fill every `sync: false` env var.
Minimum useful set: `GEMINI_API_KEY` or `GROQ_API_KEY`, plus Supabase/Neo4j if you want persistence.

**Hostname suffixes:** Render often appends a random suffix
(`mirage-api-nj77`, `mirage-web-pvgo`). After first deploy, set these in the
dashboard (Environment) so the browser can talk to the API:

| Service | Key | Example |
| --- | --- | --- |
| `mirage-api` | `CORS_ORIGINS` | `http://localhost:3000,https://mirage-web-pvgo.onrender.com` |
| `mirage-web` | `NEXT_PUBLIC_API_URL` | `https://mirage-api-nj77.onrender.com` |
| `mirage-web` | `NEXT_PUBLIC_SITE_URL` | `https://mirage-web-pvgo.onrender.com` |

Then **Manual Deploy → Clear build cache & deploy** the web service so
`NEXT_PUBLIC_*` is baked into the Next.js bundle.

`ENVIRONMENT` defaults to `development` so missing secrets do not crash boot.
Set it to `production` in the dashboard once keys are filled (still soft-init — logs ERROR, does not exit).

Backend also allows any `https://mirage-web-*.onrender.com` origin via CORS regex.

## Never deploy

- Service-role Supabase keys to the frontend — they bypass RLS.
- `.env` files — they're gitignored; Render stores secrets in its dashboard.
- `TELEGRAM_BOT_TOKEN` anywhere except the local bot process.

## Post-deploy smoke test

```powershell
Invoke-WebRequest https://mirage-api.onrender.com/health
Invoke-WebRequest https://mirage-api.onrender.com/drill/scam-types
Invoke-WebRequest https://mirage-api.onrender.com/graph/stats
```

Then open `https://mirage-web.onrender.com` and walk Dashboard → Drill → Guardian (sim) → Graph → Family.
