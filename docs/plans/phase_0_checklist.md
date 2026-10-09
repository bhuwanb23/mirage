# Phase 0 Checklist — Living Tracker

Status: 🟡 in progress · Updated as each item is verified.

Legend: `[ ]` not done · `[x]` done & verified · `[~]` blocked on external account

## Repo & structure

- [x] Monorepo folder structure (frontend, backend, bot, ml, docs, scripts)
- [x] `.gitignore` committed
- [x] `.env.example` with all required keys
- [x] Root `README.md` with setup instructions

## Backend (0.2)

- [x] `app/main.py` — FastAPI + CORS (localhost:3000) + lifespan + request logging
- [x] `app/config.py` — pydantic-settings, warns in dev / crashes in prod on missing keys
- [x] `routers/health.py` — `GET /health` returns 200 JSON
- [x] `utils/logger.py` — structured logs to stdout
- [x] Backend runs locally on port 8000 → verified: `curl http://localhost:8000/health`
- [x] Logs show incoming requests

## Shared contracts (0.8)

- [x] All Pydantic models in `app/models/schemas.py` (ScamVerdict, Evidence, DrillResult, CallStage, ThreatIOCs, DomainInfo, AnalyzeRequest, MemorySecret, HealthCheck)
- [x] `docs/api_contracts.md` documents every endpoint

## Databases (0.3)

- [x] `backend/db/001_init_tables.sql` — 6 tables (users, drills, scam_reports, family_groups, family_members, memory_secrets)
- [x] `backend/db/002_neo4j_constraints.cypher` — uniqueness constraints for all node types
- [~] Supabase project `mirage` created — **manual: user**
- [~] SQL executed in Supabase SQL Editor — **manual: user**
- [~] `SUPABASE_URL` / `SUPABASE_ANON_KEY` in `backend/.env` — **manual: user**
- [~] Neo4j AuraDB free instance created — **manual: user**
- [~] Cypher constraints executed in Neo4j Browser — **manual: user**
- [~] Neo4j creds in `backend/.env` — **manual: user**

## AI keys & wrappers (0.4)

- [x] `clients/llm.py` — provider router (Groq → Gemini → Ollama, `LLM_PROVIDER=auto`)
- [x] `clients/groq_client.py` — chat_completion + transcribe_audio (429 retry)
- [x] `clients/gemini_client.py` — analyze_image + chat_completion
- [x] `clients/ollama_client.py` — chat_completion against local Ollama
- [x] `clients/tts_client.py` — edge-tts (en/hi/ta voices)
- [x] `clients/resemblyzer_client.py` — lazy/optional import, graceful skip on py3.13
- [x] `clients/supabase_client.py` / `clients/neo4j_client.py` — soft-fail in dev
- [x] Smoke tests in `backend/scripts/` (llm, vision, whisper, tts, ollama, resemblyzer) — each skips cleanly when key missing
- [~] Groq key obtained + smoke passed — **manual: user** (free at console.groq.com)
- [~] Gemini key obtained + smoke passed — **manual: user**
- [~] Ollama smoke passed (needs `ollama serve` + model pulled) — **manual: user**
- [~] Edge-TTS smoke passed (generates one mp3)
- [~] Resemblyzer smoke passed — **may skip: py3.13 wheels** (revisit in Phase 1.4)
- [ ] F5-TTS Colab notebook runs

## Frontend (0.5)

- [x] Next.js (latest, App Router, TS, Tailwind) in `frontend/`
- [x] shadcn/ui installed (button, card, badge, input, dialog, tabs, progress, separator)
- [x] recharts + framer-motion + lucide-react installed
- [x] 5 routes render: `/`, `/dashboard`, `/drill`, `/guardian`, `/graph`
- [x] Navbar with links + Resilience Score badge
- [x] Dark mode global (`bg-gray-950`)
- [x] `lib/api.ts` fetch wrapper + `lib/constants.ts`
- [x] Dashboard backend-status card calls `GET /health`
- [x] `npm run lint` passes
- [x] `npm run build` passes

## Telegram bot (0.6)

- [x] BotFather setup doc'd (token already held by user)
- [x] `main.py` + handlers registered in correct order
- [x] `/start` welcome message
- [x] `/check`, `/elder`, `/help` commands
- [x] Text / voice / photo handlers acknowledge input (engine wired later)
- [x] `bot/requirements.txt` + pyproject
- [~] Bot replies live to `/start` — **needs TELEGRAM_BOT_TOKEN in bot/.env**

## ML scaffold

- [x] `ml/voice_cloning/f5_tts_colab.ipynb`
- [x] `ml/deepfake_detection/resemblyzer_test.py`
- [x] `ml/README.md`

## Deploy (0.7)

- [x] `render.yaml` (backend web service)
- [x] `docs/deploy.md` (Vercel + Render + cold-start notes + post-deploy checklist)
- [~] Frontend deployed to Vercel — **manual: user**
- [~] Backend deployed to Render — **manual: user**
- [~] Frontend ↔ backend reachable (no CORS errors)
- [~] Bot ↔ backend reachable
