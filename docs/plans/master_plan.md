# Mirage — Master Build Plan

---

## Phase 0 · Foundation & Infrastructure
**Goal:** Every teammate can run the project locally and deploy to staging. No one wastes time on setup later.

| # | Task | Detail | Tech |
|---|------|--------|------|
| 0.1 | **Repo & monorepo structure** | `/frontend` (Next.js), `/backend` (FastAPI), `/bot` (Telegram), `/ml` (voice models), `/docs` | GitHub, Turborepo or plain folders |
| 0.2 | **Backend skeleton** | FastAPI app with health check, CORS, env config, logging | FastAPI, Uvicorn, Pydantic |
| 0.3 | **Database setup** | Supabase project → Postgres tables: `users`, `drills`, `scam_reports`, `family_groups`, `memory_secrets`. Neo4j AuraDB instance → empty graph | Supabase, Neo4j AuraDB |
| 0.4 | **AI API keys & wrappers** | Groq client (Llama + Whisper), Gemini client (backup + vision), Edge-TTS installed, F5-TTS Colab notebook tested | Groq SDK, `google-genai`, `edge-tts` |
| 0.5 | **Frontend skeleton** | Next.js app with Tailwind, basic layout shell, routing (`/`, `/dashboard`, `/drill`, `/guardian`, `/graph`) | Next.js 14, Tailwind, shadcn/ui |
| 0.6 | **Telegram bot skeleton** | BotFather → token, `python-telegram-bot` handler that echoes messages back | python-telegram-bot |
| 0.7 | **Deploy pipelines** | Vercel auto-deploy on push for frontend, Render auto-deploy for backend | Vercel, Render |
| 0.8 | **Shared types & contracts** | Define Pydantic models that both backend and bot use: `ScamVerdict`, `DrillResult`, `CallStage`, `ThreatIOCs` | Pydantic |

**Deliverable:** A running empty app end-to-end. `GET /health` returns 200. Telegram bot replies "Mirage online." Frontend shows a placeholder dashboard.

**Estimated time:** 3–5 hours

---

## Phase 1 · Scam Analysis Engine *(the brain)*
**Goal:** Given any input (text, image, audio, URL), return a structured scam verdict with evidence.

| # | Task | Detail | Tech |
|---|------|--------|------|
| 1.1 | **Text scam classifier** | Prompt-engineered Llama 3.3 via Groq. Input: message text. Output: `{is_scam, confidence, scam_type, red_flags[], stage, evidence[]}`. Test against 20 real scam samples (bank KYC, OTP, lottery, FedEx, job offer) | Groq Llama 3.3, structured JSON output |
| 1.2 | **URL & domain analyzer** | Extract URLs from text → WHOIS lookup (domain age, registrar) → Levenshtein distance against top 100 bank/gov domains → check for HTTPS, suspicious TLDs (.xyz, .top) | `python-whois`, `python-Levenshtein` |
| 1.3 | **Image / screenshot analyzer** | OCR via Gemini Vision → extract text + URLs → feed to 1.1 and 1.2. Also detect fake UI elements (blurred logos, mismatched fonts) | Gemini 2.0 Flash Vision |
| 1.4 | **Audio / voice note analyzer** | Transcribe via Groq Whisper → feed transcript to 1.1. Parallel: run Resemblyzer to get synthetic voice probability score | Groq Whisper, Resemblyzer |
| 1.5 | **Evidence trail builder** | Aggregate all signals into a human-readable report: "This message is 94% likely a bank KYC scam. Red flags: (1) domain sbi-verify.xyz is 4 days old, (2) asks for OTP, (3) creates urgency with '24hr deadline'." | Python, Jinja2 templates |
| 1.6 | **Multi-modal orchestrator** | Single endpoint `POST /analyze` that auto-detects input type (text/audio/image/URL) and routes to the right pipeline, then merges results | FastAPI, file type detection |

**Deliverable:** `POST /analyze` accepts any file or text and returns a full scam report with confidence score, scam type, red flags, and evidence.

**Estimated time:** 6–8 hours

**Dependencies:** Phase 0 complete

---

## Phase 2 · Telegram Bot *(the front door)*
**Goal:** A working bot that anyone can forward a suspicious message to and get an instant verdict.

| # | Task | Detail | Tech |
|---|------|--------|------|
| 2.1 | **Text message handler** | User forwards a text message → bot calls `/analyze` → replies with verdict + evidence in formatted Telegram message (bold red flags, emoji severity) | python-telegram-bot |
| 2.2 | **Voice note handler** | User forwards a voice note → bot downloads `.ogg` → sends to `/analyze` audio pipeline → replies with transcript + verdict + synthetic voice score | Telegram API, Groq Whisper |
| 2.3 | **Image / screenshot handler** | User forwards a screenshot → bot downloads → sends to `/analyze` image pipeline → replies with OCR'd text + verdict | Telegram API |
| 2.4 | **URL handler** | User sends a bare URL → bot runs domain analysis → replies with domain age, lookalike check, risk score | python-whois |
| 2.5 | **Inline quick-check** | `/check <paste text>` command for quick inline analysis without forwarding | python-telegram-bot CommandHandler |
| 2.6 | **Elder Mode toggle** | `/elder` command → switches bot to voice-only responses (Edge-TTS generates Hindi/Tamil audio reply), bigger text, simpler language, auto-alerts family group | Edge-TTS, Telegram groups |
| 2.7 | **Family alert webhook** | If scam confidence > 85%, bot auto-sends alert to a pre-registered family Telegram group: "⚠️ Dad just received a high-risk bank scam call" | Telegram Bot API |

**Deliverable:** A live Telegram bot that handles text, voice, image, and URL inputs with full scam analysis and family alerts.

**Estimated time:** 4–6 hours

**Dependencies:** Phase 1 complete

---

## Phase 3 · Scam Fire Drill Simulator *(the signature feature)*
**Goal:** Simulate a personalized scam attack against the user, then debrief them. This is the demo centerpiece.

| # | Task | Detail | Tech |
|---|------|--------|------|
| 3.1 | **Public footprint scraper** | User provides Instagram handle or LinkedIn URL or uploads a voice clip. Backend extracts: name, city, employer, bank (from posts/bio), voice sample. For demo: manually input a profile JSON to skip scraping complexity | Manual input for demo, BeautifulSoup as stretch |
| 3.2 | **Scam script generator** | LLM generates a personalized scam script using the footprint. Prompt: "You are a scammer targeting [name] in [city] who banks at [bank]. Generate a realistic KYC fraud call script." Include all 5 stages (hook → authority → isolation → urgency → payment) | Groq Llama 3.3 |
| 3.3 | **Voice cloning pipeline** | Take the user's uploaded voice clip (or a relative's) → clone with F5-TTS/XTTS on Colab → synthesize the scam script as audio. For demo: pre-clone one voice, generate 2–3 scam audios | F5-TTS on Colab, Edge-TTS as fallback |
| 3.4 | **Drill delivery UI** | Web page: "Your Scam Fire Drill is ready." Plays the cloned audio. User clicks "This is a scam" or "This seems real" at any point. Timer tracks how long they took to identify it | Next.js, HTML5 Audio |
| 3.5 | **Debrief engine** | After drill ends, LLM generates a personalized debrief: "You correctly flagged the urgency at 0:32 but missed the isolation tactic at 0:18 where the caller said 'don't tell your family.' Here's why that's a red flag…" | Groq Llama 3.3 |
| 3.6 | **Scam Resilience Score** | Algorithm: base score 0–100. Factors: detection speed, stages correctly identified, stages missed, improvement over previous drills. Store in DB. Display as a fitness-tracker-style chart | Supabase, Recharts |

**Deliverable:** A user can upload a voice clip, receive a personalized cloned-voice scam call, attempt to identify it, and get a scored debrief with a Resilience Score.

**Estimated time:** 8–10 hours

**Dependencies:** Phase 1 complete (analysis engine for debrief), Phase 0 (DB for scores)

---

## Phase 4 · Live Call Guardian + Memory Handshake *(the real-time shield)*
**Goal:** Real-time call monitoring with stage tracking and identity verification.

| # | Task | Detail | Tech |
|---|------|--------|------|
| 4.1 | **Live mic transcription** | Browser captures mic audio via `MediaRecorder` API → streams chunks to backend → Groq Whisper transcribes in near-real-time (3–5 sec chunks) | Web Audio API, WebSocket, Groq Whisper |
| 4.2 | **Scam stage tracker** | Each transcript chunk is classified into the 5-stage pipeline. Backend maintains state: `{current_stage, confidence, timestamps[]}`. When stage transitions to "urgency" (stage 4), trigger a warning. When "payment" (stage 5), trigger a critical alert | Groq Llama 3.3, WebSocket |
| 4.3 | **Real-time alert UI** | Web dashboard shows a live progress bar of the 5 stages. Green → yellow → red. At stage 4: "⚠️ SCAM LIKELY — caller is creating false urgency." At stage 5: "🚨 HANG UP NOW — payment demand detected." Pulsing animations | Next.js, Framer Motion |
| 4.4 | **Synthetic voice detector** | Parallel to transcription, run Resemblyzer on audio chunks. Display a "Voice Authenticity" meter: 95% = likely human, 40% = likely AI clone | Resemblyzer, WebSocket |
| 4.5 | **Memory Handshake setup** | User registers shared secrets with family members in the app: 3 challenge questions + answers ("What's our dog's name?", "What street did we grow up on?") + a rotating 6-digit TOTP code that refreshes every 5 min | Supabase, `pyotp` |
| 4.6 | **Memory Handshake trigger** | During a flagged call, Guardian prompts: "Ask the caller: What did we name the dog in 2019?" If the caller (or clone) can't answer, confirm scam. For demo: simulate the clone failing the challenge | Next.js UI, TOTP logic |

**Deliverable:** A live web page that listens to mic input, shows real-time scam stage progression, flags synthetic voices, and triggers a Memory Handshake challenge.

**Estimated time:** 8–10 hours

**Dependencies:** Phase 1 (analysis engine), Phase 0 (WebSocket infra)

---

## Phase 5 · Scammer Hunter *(the offensive layer)*
**Goal:** AI honeypot that wastes scammer time, extracts IOCs, and builds a scam graph.

| # | Task | Detail | Tech |
|---|------|--------|------|
| 5.1 | **Honeypot persona engine** | LLM-powered agent with a persona: "Ramesh, 62, retired, confused but talkative." Prompt instructs it to never hang up, ask repetitive questions, and slowly extract the scammer's UPI ID, phone number, and bank details | Groq Llama 3.3, agent loop |
| 5.2 | **IOC extractor** | NER (named entity recognition) on honeypot conversation logs → extract phone numbers, UPI IDs, URLs, bank account numbers, names. Regex + LLM fallback | Groq Llama 3.3, regex |
| 5.3 | **Scam Graph ingestion** | Push extracted IOCs into Neo4j. Nodes: `PhoneNumber`, `UPI_ID`, `Domain`, `BankAccount`, `ScammerName`. Edges: `CALLS`, `USES_UPI`, `LINKED_TO_DOMAIN`. Cypher queries to detect rings | Neo4j AuraDB, `neo4j` Python driver |
| 5.4 | **Scam Graph visualization** | Frontend: interactive force-directed graph using `react-force-graph` or D3. Click a node → see all linked entities. Highlight rings in red | Next.js, react-force-graph-2d |
| 5.5 | **Scam Weather Map** | Aggregate scam reports by city (from user submissions + honeypot data). Plot on a Leaflet map with heat layers. "Delhi: 47 active scams this week" | Leaflet.js, react-leaflet |
| 5.6 | **Cybercrime report generator** | Auto-fill a structured report: victim details, scammer IOCs, timeline, evidence attachments. One-click copy for pasting into cybercrime.gov.in or 1930 helpline script | Jinja2, PDF export |

**Deliverable:** A honeypot agent that extracts scammer details, a Neo4j graph showing scam rings, and a heatmap of active campaigns.

**Estimated time:** 6–8 hours

**Dependencies:** Phase 1 (analysis), Phase 0 (Neo4j setup)

---

## Phase 6 · Frontend Dashboard & Integration
**Goal:** Tie everything into a polished, cohesive web app.

| # | Task | Detail | Tech |
|---|------|--------|------|
| 6.1 | **Landing page** | Hero section: "Your Personal AI Immune System Against Scams." Animated immune system metaphor. CTA: "Start Your First Fire Drill" | Next.js, Framer Motion |
| 6.2 | **Dashboard** | Overview: Resilience Score (big number + trend chart), recent drills, active threats, family status, scam weather widget | Recharts, shadcn/ui |
| 6.3 | **Drill page** | Full Fire Drill flow: upload → wait → simulate → debrief → score | Next.js |
| 6.4 | **Guardian page** | Live call monitoring UI with stage tracker, voice authenticity meter, Memory Handshake panel | Next.js, Web Audio API |
| 6.5 | **Graph page** | Scam Graph + Weather Map side by side | Neo4j vis, Leaflet |
| 6.6 | **Family network page** | Add family members, set up Memory Handshake secrets, view their alert history | Supabase, Next.js |
| 6.7 | **Responsive + dark mode** | Mobile-first, dark theme by default (looks more "cybersecurity") | Tailwind |

**Deliverable:** A polished, navigable web app with all features accessible from a clean dashboard.

**Estimated time:** 6–8 hours

**Dependencies:** All previous phases

---

## Phase 7 · Demo Polish & Pitch
**Goal:** A flawless 3-minute demo and a pitch that makes judges remember you.

| # | Task | Detail | Tech |
|---|------|--------|------|
| 7.1 | **Demo script rehearsal** | Word-for-word script for the 3-minute demo. Assign a speaker. Rehearse 5x minimum | Humans |
| 7.2 | **Pre-record fallback videos** | Record screen captures of every feature working. If live demo breaks, switch to video seamlessly | OBS, Loom |
| 7.3 | **Seed data** | Pre-populate the scam graph with 50+ realistic nodes. Pre-run 3 fire drills so the Resilience Score has a trend. Pre-fill the weather map | Python scripts |
| 7.4 | **Pitch deck** | 5 slides max: Problem (₹7,000 Cr lost to scams in India in 2024), Hook ("What if we vaccinated you?"), Demo, Architecture, Ask | Figma / Canva |
| 7.5 | **One-liner & tagline** | "Mirage: The scam vaccine." / "We attack you first, so scammers can't." | — |
| 7.6 | **Bug bash** | 1 hour of trying to break everything. Fix only critical bugs. Cosmetic issues → hide the feature | — |
| 7.7 | **README & submission** | Clean README with screenshots, architecture diagram, setup instructions, and the "why" story | Markdown |

**Deliverable:** A rehearsed demo, a backup plan, a pitch deck, and a submission-ready repo.

**Estimated time:** 4–6 hours

**Dependencies:** All previous phases

---

## Priority Cuts (if you run out of time)

| Cut This | Keep This | Why |
|----------|-----------|-----|
| Scam Weather Map (5.5) | Scam Graph (5.3–5.4) | Graph is more impressive; map is nice-to-have |
| Honeypot agent (5.1) | IOC extractor (5.2) | Fake the honeypot with pre-recorded logs |
| Elder Mode (2.6) | Core bot (2.1–2.4) | Elder Mode is a pitch point, not a demo point |
| Live mic streaming (4.1) | Pre-recorded audio demo (4.3) | WebSocket audio is fragile live; pre-record is safe |
| PDF report (5.6) | On-screen report | Judges won't download a PDF |

---

## Phase Dependency Map

```
Phase 0 (Foundation)
  │
  ├──→ Phase 1 (Analysis Engine)
  │      │
  │      ├──→ Phase 2 (Telegram Bot)
  │      │
  │      ├──→ Phase 3 (Fire Drill) ← SIGNATURE
  │      │
  │      ├──→ Phase 4 (Live Guardian) ← SIGNATURE
  │      │
  │      └──→ Phase 5 (Scammer Hunter) ← BONUS
  │
  └──→ Phase 6 (Dashboard) ← needs 1–5
         │
         └──→ Phase 7 (Demo & Pitch) ← FINAL
```

---

**This is the full map.** Pick a phase and say "let's deep dive into Phase X" — I'll break it into exact code files, API endpoints, prompts, and step-by-step implementation. Or tell me your team size and hours and I'll assign phases to people with an hour-by-hour schedule.