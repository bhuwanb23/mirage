# Phase 0 — Foundation & Infrastructure (Complete Deep Dive)

---

## 0.1 · Repo & Monorepo Structure

### GitHub Repository

**Repo name:** `mirage-ai`
**Visibility:** Private during hackathon, public after submission
**Branch strategy:** `main` (always deployable) → each person works on `feature/<name>` branches → merge via pull request or direct push if solo

### Folder Structure

```
mirage-ai/
│
├── frontend/                  # Next.js web app
│   ├── app/                   # App router (Next.js 14)
│   │   ├── layout.tsx         # Root layout with nav, dark mode
│   │   ├── page.tsx           # Landing page
│   │   ├── dashboard/
│   │   │   └── page.tsx       # Main dashboard
│   │   ├── drill/
│   │   │   └── page.tsx       # Scam Fire Drill page
│   │   ├── guardian/
│   │   │   └── page.tsx       # Live Call Guardian page
│   │   └── graph/
│   │       └── page.tsx       # Scam Graph + Weather Map
│   ├── components/            # Reusable UI components
│   │   ├── ui/                # shadcn/ui components (button, card, etc.)
│   │   ├── Navbar.tsx
│   │   ├── ScoreCard.tsx
│   │   └── StageTracker.tsx
│   ├── lib/                   # Utility functions
│   │   ├── api.ts             # API client (fetch wrapper for backend)
│   │   └── constants.ts       # Backend URL, config
│   ├── public/                # Static assets (logo, icons)
│   ├── tailwind.config.ts
│   ├── next.config.js
│   ├── package.json
│   ├── tsconfig.json
│   └── .env.local             # NEXT_PUBLIC_API_URL=http://localhost:8000
│
├── backend/                   # FastAPI server
│   ├── app/
│   │   ├── main.py            # FastAPI app, CORS, startup
│   │   ├── config.py          # Env loading via pydantic-settings
│   │   ├── routers/
│   │   │   ├── analyze.py     # POST /analyze (Phase 1)
│   │   │   ├── drill.py       # Fire Drill endpoints (Phase 3)
│   │   │   ├── guardian.py    # Live Guardian endpoints (Phase 4)
│   │   │   ├── honeypot.py    # Scammer Hunter endpoints (Phase 5)
│   │   │   └── health.py     # GET /health
│   │   ├── services/          # Business logic
│   │   │   ├── scam_analyzer.py
│   │   │   ├── voice_analyzer.py
│   │   │   ├── url_analyzer.py
│   │   │   ├── image_analyzer.py
│   │   │   └── drill_engine.py
│   │   ├── models/            # Pydantic models (shared types)
│   │   │   ├── schemas.py     # ScamVerdict, DrillResult, etc.
│   │   │   └── database.py    # Supabase table models
│   │   ├── clients/           # AI service wrappers
│   │   │   ├── groq_client.py
│   │   │   ├── gemini_client.py
│   │   │   ├── neo4j_client.py
│   │   │   └── supabase_client.py
│   │   └── utils/
│   │       ├── logger.py
│   │       └── helpers.py
│   ├── requirements.txt
│   ├── .env                   # All API keys
│   └── Dockerfile             # For Render deploy (optional)
│
├── bot/                       # Telegram bot
│   ├── main.py                # Bot entry point
│   ├── handlers/
│   │   ├── text_handler.py    # Handle text messages
│   │   ├── voice_handler.py   # Handle voice notes
│   │   ├── image_handler.py   # Handle images
│   │   └── command_handler.py # /start, /check, /elder
│   ├── utils/
│   │   ├── api_client.py      # Calls backend /analyze
│   │   └── formatter.py       # Format verdict for Telegram
│   ├── requirements.txt
│   └── .env                   # BOT_TOKEN, BACKEND_URL
│
├── ml/                        # ML models & notebooks
│   ├── voice_cloning/
│   │   └── f5_tts_colab.ipynb # Colab notebook for voice cloning
│   ├── deepfake_detection/
│   │   └── resemblyzer_test.py
│   └── README.md              # How to run each model
│
├── docs/
│   ├── architecture.md        # System architecture diagram
│   ├── api_contracts.md       # All API endpoints documented
│   ├── demo_script.md         # 3-minute demo script
│   └── pitch_deck.md          # Pitch notes
│
├── .gitignore
├── README.md                  # Project overview, setup, run instructions
└── .env.example               # Template for all env vars
```

### .gitignore essentials

```
node_modules/
__pycache__/
.env
.env.local
*.pyc
.next/
venv/
.vercel/
```

### .env.example

```
# Backend
GROQ_API_KEY=
GEMINI_API_KEY=
SUPABASE_URL=
SUPABASE_ANON_KEY=
NEO4J_URI=
NEO4J_USERNAME=
NEO4J_PASSWORD=

# Bot
TELEGRAM_BOT_TOKEN=
BACKEND_URL=http://localhost:8000

# Frontend
NEXT_PUBLIC_API_URL=http://localhost:8000
```

---

## 0.2 · Backend Skeleton

### What main.py should do

1. **Create the FastAPI app** with a title ("Mirage API") and version
2. **Add CORS middleware** — allow all origins during development (restrict in production). This is critical because your Next.js frontend on `localhost:3000` will call the backend on `localhost:8000` — without CORS, every request will fail
3. **Register routers** — for now, only the health router. As you build phases 1–5, you'll add more routers
4. **Add startup/shutdown events** — initialize Supabase and Neo4j connections on startup, close them on shutdown
5. **Configure logging** — structured JSON logging so you can debug fast

### config.py behavior

Use `pydantic-settings` (formerly `pydantic[dotenv]`) to load env vars:
- It reads from `.env` automatically
- Every config value is typed and validated at startup
- If a required key is missing, the app crashes immediately with a clear error rather than failing silently later during a demo

**Config fields needed:**
| Field | Type | Required | Default |
|-------|------|----------|---------|
| `GROQ_API_KEY` | str | Yes | — |
| `GEMINI_API_KEY` | str | Yes | — |
| `SUPABASE_URL` | str | Yes | — |
| `SUPABASE_ANON_KEY` | str | Yes | — |
| `NEO4J_URI` | str | Yes | — |
| `NEO4J_USERNAME` | str | Yes | — |
| `NEO4J_PASSWORD` | str | Yes | — |
| `ENVIRONMENT` | str | No | `development` |
| `LOG_LEVEL` | str | No | `INFO` |

### health.py router

**Endpoint:** `GET /health`

**Response:**
```json
{
  "status": "healthy",
  "service": "mirage-api",
  "version": "0.1.0",
  "timestamp": "2025-01-15T10:30:00Z"
}
```

**Why include timestamp and version:** During the demo, if something breaks, you can quickly hit `/health` to confirm the backend is reachable and what version is deployed.

### Logger setup

Use Python's built-in `logging` module. Configure it to:
- Output to stdout (Render captures stdout as logs)
- Include timestamp, log level, module name
- Log every incoming request (method, path, response time)
- Log every AI API call (which model, latency, token count)

### requirements.txt for backend

```
fastapi
uvicorn[standard]
pydantic
pydantic-settings
python-dotenv
httpx
supabase
neo4j
groq
google-genai
edge-tts
python-whois
python-Levenshtein
resemblyzer
python-multipart
jinja2
pyotp
```

### How to run locally

```
cd backend
python -m venv venv
source venv/bin/activate      # or venv\Scripts\activate on Windows
pip install -r requirements.txt
cp .env.example .env           # fill in your keys
uvicorn app.main:app --reload --port 8000
```

Verify: open `http://localhost:8000/health` → should return the JSON above

---

## 0.3 · Database Setup

### Supabase (Postgres)

**Step-by-step setup:**
1. Go to supabase.com → sign up with GitHub
2. Click "New Project"
3. **Name:** `mirage`
4. **Database password:** generate a strong one, save it
5. **Region:** choose closest to your location (Mumbai for India)
6. Wait 2 minutes for provisioning
7. Go to Settings → API → copy the **Project URL** and **anon/public key**
8. These go into your `.env` as `SUPABASE_URL` and `SUPABASE_ANON_KEY`

### Database Tables

Go to Supabase → SQL Editor → run these table creation queries:

**Table: `users`**

| Column | Type | Constraints | Purpose |
|--------|------|-------------|---------|
| id | uuid | PRIMARY KEY, auto-generated | Unique user ID |
| name | text | NOT NULL | User's name |
| phone | text | UNIQUE | Phone number (optional) |
| telegram_chat_id | bigint | UNIQUE | Telegram chat ID for bot users |
| city | text | | User's city (for drill personalization) |
| bank | text | | User's bank (for drill personalization) |
| employer | text | | User's employer |
| resilience_score | integer | DEFAULT 0 | Current scam resilience score (0–100) |
| elder_mode | boolean | DEFAULT false | Elder mode enabled |
| created_at | timestamptz | DEFAULT now() | |
| updated_at | timestamptz | DEFAULT now() | |

**Table: `drills`**

| Column | Type | Constraints | Purpose |
|--------|------|-------------|---------|
| id | uuid | PRIMARY KEY | |
| user_id | uuid | FOREIGN KEY → users.id | Who took the drill |
| scam_type | text | NOT NULL | bank_kyc, fedex, relative_distress, etc. |
| script_text | text | | Generated scam script |
| audio_url | text | | URL to cloned voice audio |
| user_response | text | | identified_scam / fell_for_it |
| detection_time_seconds | integer | | How fast they caught it |
| stages_identified | text[] | | Which stages they spotted |
| stages_missed | text[] | | Which stages they missed |
| score_before | integer | | Resilience score before drill |
| score_after | integer | | Resilience score after drill |
| debrief_text | text | | LLM-generated debrief |
| created_at | timestamptz | DEFAULT now() | |

**Table: `scam_reports`**

| Column | Type | Constraints | Purpose |
|--------|------|-------------|---------|
| id | uuid | PRIMARY KEY | |
| user_id | uuid | FOREIGN KEY → users.id, NULLABLE | Anonymous reports allowed |
| input_type | text | NOT NULL | text, audio, image, url |
| input_content | text | | Original message/URL |
| input_file_url | text | | Uploaded file URL |
| verdict | jsonb | | Full ScamVerdict object |
| is_scam | boolean | | Quick lookup |
| confidence | float | | 0.0 – 1.0 |
| scam_type | text | | Classification |
| red_flags | text[] | | List of identified red flags |
| evidence | jsonb | | Detailed evidence object |
| source | text | | web, telegram, guardian |
| created_at | timestamptz | DEFAULT now() | |

**Table: `family_groups`**

| Column | Type | Constraints | Purpose |
|--------|------|-------------|---------|
| id | uuid | PRIMARY KEY | |
| name | text | NOT NULL | "Sharma Family" |
| created_by | uuid | FOREIGN KEY → users.id | |
| invite_code | text | UNIQUE | 6-char code to join |
| alert_telegram_group_id | bigint | | Telegram group for alerts |
| created_at | timestamptz | DEFAULT now() | |

**Table: `family_members`** (junction table)

| Column | Type | Constraints | Purpose |
|--------|------|-------------|---------|
| id | uuid | PRIMARY KEY | |
| family_group_id | uuid | FOREIGN KEY → family_groups.id | |
| user_id | uuid | FOREIGN KEY → users.id | |
| role | text | DEFAULT 'member' | admin / member |
| joined_at | timestamptz | DEFAULT now() | |

**Table: `memory_secrets`**

| Column | Type | Constraints | Purpose |
|--------|------|-------------|---------|
| id | uuid | PRIMARY KEY | |
| family_group_id | uuid | FOREIGN KEY → family_groups.id | |
| set_by_user_id | uuid | FOREIGN KEY → users.id | |
| question | text | NOT NULL | "What's our dog's name?" |
| answer_hash | text | NOT NULL | Hashed answer (don't store plain text) |
| totp_secret | text | | Base32 TOTP secret for rotating codes |
| is_active | boolean | DEFAULT true | |
| created_at | timestamptz | DEFAULT now() | |

### Row Level Security (RLS)

Enable RLS on all tables in Supabase. For the hackathon, set simple policies:
- Users can read/write their own data
- Family members can read other members' data within their group
- Scam reports are readable by all (for the graph/map)

For the hackathon demo, you can also just **disable RLS** temporarily to avoid debugging auth issues. Add a comment: "// TODO: Enable RLS before production."

### Neo4j AuraDB Setup

1. Go to neo4j.com/cloud/aura-free → sign up
2. Create a **Free instance**
3. **Name:** `mirage-scam-graph`
4. Copy the **connection URI** (looks like `neo4j+s://xxxx.databases.neo4j.io`), **username** (usually `neo4j`), and **password**
5. These go into your `.env`

**Initial graph schema** (run in Neo4j Browser):

Create constraint queries to ensure uniqueness:
- `PhoneNumber` nodes — unique on `number` property
- `UPI_ID` nodes — unique on `upi_id` property
- `Domain` nodes — unique on `domain` property
- `BankAccount` nodes — unique on `account_number` property
- `ScamCampaign` nodes — unique on `campaign_id` property
- `ScamReport` nodes — unique on `report_id` property

**Relationships to support:**
- `(PhoneNumber)-[:CALLS]->(PhoneNumber)`
- `(PhoneNumber)-[:USES]->(UPI_ID)`
- `(PhoneNumber)-[:LINKED_TO]->(Domain)`
- `(UPI_ID)-[:BELONGS_TO]->(BankAccount)`
- `(ScamReport)-[:INVOLVES]->(PhoneNumber)`
- `(ScamReport)-[:INVOLVES]->(UPI_ID)`
- `(ScamCampaign)-[:INCLUDES]->(PhoneNumber)`

For now, just create the constraints. The graph will be populated in Phase 5.

---

## 0.4 · AI API Keys & Wrappers

### Groq Setup

1. Go to console.groq.com → sign up
2. Go to API Keys → create a new key
3. Copy it into `.env` as `GROQ_API_KEY`
4. **Free tier limits:** 30 requests/minute, 14,400 requests/day for Llama 3.3 70B. Whisper is also free

**groq_client.py behavior:**

This wrapper should expose two main functions:

**Function 1: `chat_completion(messages, model, response_format)`**
- Takes a list of messages (system + user), model name (default: `llama-3.3-70b-versatile`), and optional JSON response format
- Calls Groq's chat completions API
- Returns the response content as a string
- Handles rate limiting: if you get a 429 error, wait 2 seconds and retry once
- Logs the model used, input token count, output token count, and latency

**Function 2: `transcribe_audio(file_path, language)`**
- Takes an audio file path and optional language hint
- Calls Groq's Whisper endpoint
- Returns the transcription text
- Supports `.ogg`, `.mp3`, `.wav`, `.m4a` formats

### Gemini Setup

1. Go to aistudio.google.com → sign in with Google
2. Click "Get API Key" → create key
3. Copy into `.env` as `GEMINI_API_KEY`
4. **Free tier:** Gemini 2.0 Flash — 15 requests/minute, 1 million tokens/day

**gemini_client.py behavior:**

**Function 1: `analyze_image(image_bytes, prompt)`**
- Takes raw image bytes and a text prompt
- Sends to Gemini 2.0 Flash with vision
- Returns text response
- Primary use: OCR on scam screenshots, detecting fake UI elements

**Function 2: `chat_completion(messages, model)`**
- Backup LLM when Groq hits rate limits
- Same interface as groq_client for easy swapping

### Edge-TTS Setup

No API key needed. It's a Python package that uses Microsoft Edge's free TTS service.

**How to test:**
```bash
pip install edge-tts
edge-tts --text "Mirage is online" --voice en-IN-NeerjaNeural --write-media test.mp3
```

**Supported voices for this project:**
| Language | Voice Name | Gender |
|----------|-----------|--------|
| English (India) | en-IN-NeerjaNeural | Female |
| English (India) | en-IN-PrabhatNeural | Male |
| Hindi | hi-IN-SwaraNeural | Female |
| Hindi | hi-IN-MadhurNeural | Male |
| Tamil | ta-IN-PallaviNeural | Female |
| Tamil | ta-IN-ValluvarNeural | Male |

**tts_client.py behavior:**
- Function `text_to_speech(text, language, gender)` → selects the right voice → returns audio bytes or saves to file

### F5-TTS / XTTS Voice Cloning

This runs on **Google Colab** (free GPU) because it needs a GPU and your local machine may not have one.

**Colab notebook structure:**
1. Install F5-TTS or XTTS v2
2. Upload a 10-second reference voice clip
3. Input the scam script text
4. Generate cloned audio
5. Download the output `.wav` file
6. Upload it to Supabase Storage (or just save locally for demo)

**For the demo:** Pre-clone 2–3 voices before the presentation. Don't rely on real-time cloning during the live demo — it takes 30–60 seconds on Colab and might fail.

**Integration with backend:** The backend doesn't call Colab directly. Instead:
- Pre-generated cloned audio files are stored in Supabase Storage or as static files
- The drill engine references them by URL
- As a stretch goal: set up a simple Flask server on Colab with ngrok that accepts clone requests via REST API

### Resemblyzer Setup

```bash
pip install resemblyzer
```

No API key needed. It's a local model.

**How it works for deepfake detection:**
- Resemblyzer creates voice embeddings (d-vectors)
- Compare the embedding of the incoming call voice against known real voice embeddings of the family member
- If cosine similarity is below a threshold (e.g., 0.75), flag as potentially synthetic
- This isn't a dedicated deepfake detector, but it catches cloned voices that don't perfectly match the real person's voiceprint

**resemblyzer_client.py behavior:**
- Function `get_voice_embedding(audio_path)` → returns a numpy array (256-dim vector)
- Function `compare_voices(embedding1, embedding2)` → returns cosine similarity (0.0–1.0)
- Function `is_likely_synthetic(audio_path, reference_embedding, threshold=0.75)` → returns boolean + confidence

---

## 0.5 · Frontend Skeleton

### Initial Setup Steps

1. Create the Next.js app with TypeScript, Tailwind, App Router (not Pages Router)
2. Install shadcn/ui — run the init command, then add components: button, card, badge, input, dialog, tabs, progress, separator
3. Install additional packages: `recharts` (charts), `framer-motion` (animations), `lucide-react` (icons)

### Layout Structure

**Root layout (`app/layout.tsx`):**
- Dark mode by default (add `dark` class to `<html>` tag)
- Background: very dark gray/black (`bg-gray-950` or `bg-black`)
- A persistent **Navbar** at the top with:
  - Mirage logo (left) — a shield icon from Lucide
  - Navigation links: Dashboard, Fire Drill, Guardian, Scam Graph
  - Resilience Score badge (right) — small colored badge showing the number
- Body content below the navbar
- A global font: Inter (default in Next.js) or JetBrains Mono for a techy feel

### Page-by-Page Skeleton

**`/` (Landing Page):**
- Hero section with tagline: "Your Personal AI Immune System Against Scams"
- Subtitle: "We attack you first, so real scammers can't."
- Two CTAs: "Start Fire Drill" (primary button) → links to `/drill`, "Try the Bot" (secondary) → links to Telegram bot
- Three feature cards below: Fire Drill, Live Guardian, Scam Graph — each with an icon, one-liner, and "Coming soon" or "Try now" badge
- This page is for judges. Make it look professional

**`/dashboard`:**
- Top row: 4 stat cards
  - Resilience Score (big number, color-coded: red < 40, yellow 40-70, green > 70)
  - Total Drills Completed
  - Scams Detected
  - Family Members Protected
- Middle row: Resilience Score trend line chart (Recharts `LineChart`, showing score over time)
- Bottom row: Recent Activity feed (list of recent drills, scam reports, alerts)
- Everything shows placeholder data for now: score = 0, drills = 0

**`/drill`:**
- Step 1: "Upload Your Voice" — a file upload area (drag and drop or click) for a 10-second audio clip
- Step 2: "Enter Your Profile" — form fields: name, city, bank, employer (pre-fill from user profile if logged in)
- Step 3: "Choose Scam Type" — radio buttons: Bank KYC Fraud, FedEx Package, Relative in Distress, Job Offer, OTP Scam
- A big "Start Fire Drill" button
- Results area (hidden until drill completes): audio player for the scam call, debrief text, red flags list, before/after resilience score
- For now: all static/non-functional, just the UI skeleton

**`/guardian`:**
- Left panel: Live Transcript area (scrolling text box)
- Center: Scam Stage Tracker — 5 horizontal segments (Hook → Authority → Isolation → Urgency → Payment), each lights up as detected. Use a progress-bar-like component with 5 colored segments
- Right panel: Voice Authenticity Meter (vertical gauge, 0–100%)
- Bottom: Memory Handshake panel — "Challenge Question: [What's our dog's name?]" with an answer field and verify button
- A big "Start Listening" button at the top
- For now: static mockup with placeholder stages

**`/graph`:**
- Left 60%: Force-directed graph canvas (placeholder `<div>` with text "Scam Graph loads here")
- Right 40%: Scam Weather Map (placeholder `<div>` with text "Weather Map loads here")
- Below: IOC table — columns: Type (phone/UPI/domain), Value, First Seen, Linked To, Risk Level
- For now: completely empty, just the layout structure

### API Client (`lib/api.ts`)

A simple fetch wrapper:
- Base URL from `NEXT_PUBLIC_API_URL` environment variable
- Function `apiGet(path)` → GET request, returns JSON
- Function `apiPost(path, body)` → POST request, returns JSON
- Function `apiPostFile(path, file)` → POST with FormData, returns JSON
- Handles errors: if response is not OK, throw with error message
- All functions are async

### Color Scheme

| Purpose | Color | Tailwind Class |
|---------|-------|---------------|
| Background | Near black | `bg-gray-950` |
| Card background | Dark gray | `bg-gray-900` |
| Card border | Subtle gray | `border-gray-800` |
| Primary accent | Electric blue | `text-blue-400` |
| Danger / Scam | Red | `text-red-500` |
| Safe / Verified | Green | `text-green-500` |
| Warning | Amber | `text-amber-500` |
| Text primary | White | `text-white` |
| Text secondary | Gray | `text-gray-400` |

---

## 0.6 · Telegram Bot Skeleton

### BotFather Setup

1. Open Telegram → search for `@BotFather`
2. Send `/newbot`
3. **Name:** `Mirage Scam Shield` (display name)
4. **Username:** `mirage_scam_bot` (must end in `bot`, must be unique — try variations)
5. Copy the **HTTP API token** → put in `.env` as `TELEGRAM_BOT_TOKEN`
6. Send `/setdescription` → "Forward any suspicious message, voice note, or screenshot. I'll tell you if it's a scam."
7. Send `/setabouttext` → "Your AI immune system against scams. By Team Mirage."
8. Send `/setcommands` → paste:
```
start - Start Mirage
check - Quick scam check
elder - Toggle Elder Mode
help - How to use Mirage
```

### Bot Architecture

**main.py:**
- Load the bot token from `.env`
- Create an `Application` (python-telegram-bot v20+)
- Register handlers in this order (order matters — first match wins):
  1. CommandHandler for `/start` → welcome message
  2. CommandHandler for `/check` → inline quick check
  3. CommandHandler for `/elder` → toggle elder mode
  4. CommandHandler for `/help` → usage guide
  5. MessageHandler for text → text analysis
  6. MessageHandler for voice → voice analysis
  7. MessageHandler for photo → image analysis
  8. MessageHandler for document → file analysis
- Start polling (`application.run_polling()`)

### Handler Behaviors (Phase 0 — skeleton only)

**`/start` handler:**
Reply with:
```
🛡️ Welcome to Mirage — Your AI Scam Shield

Forward me any:
📝 Text message
🎤 Voice note
📸 Screenshot
🔗 URL

I'll analyze it and tell you if it's a scam.

Commands:
/check <text> — Quick scam check
/elder — Toggle Elder Mode (big text, voice replies)
/help — How to use
```

**Text message handler (skeleton):**
- Receive the message text
- Reply: "🔍 Analyzing your message... (Engine not connected yet)"
- Later in Phase 2: call `POST /analyze` with the text

**Voice note handler (skeleton):**
- Receive the voice file
- Reply: "🎤 Received voice note. Analyzing... (Engine not connected yet)"
- Later: download the .ogg file, send to backend

**Photo handler (skeleton):**
- Receive the photo
- Reply: "📸 Received screenshot. Analyzing... (Engine not connected yet)"
- Later: download the image, send to backend

### Running the Bot Locally

```bash
cd bot
python -m venv venv
source venv/bin/activate
pip install python-telegram-bot python-dotenv httpx
cp .env.example .env    # add BOT_TOKEN and BACKEND_URL
python main.py
```

Test: open Telegram → find your bot → send `/start` → should get the welcome message. Send any text → should get the "Analyzing..." placeholder.

### Bot requirements.txt

```
python-telegram-bot
python-dotenv
httpx
```

---

## 0.7 · Deploy Pipelines

### Frontend → Vercel

1. Go to vercel.com → sign up with GitHub
2. Click "New Project" → import your `mirage-ai` repo
3. **Framework Preset:** Next.js (auto-detected)
4. **Root Directory:** `frontend` (important — tell Vercel the Next.js app is in the `frontend/` subfolder)
5. **Environment Variables:** add `NEXT_PUBLIC_API_URL` = your Render backend URL (you'll get this after deploying backend)
6. Click Deploy
7. Every push to `main` will auto-deploy

**Vercel gives you:** a free `.vercel.app` URL, HTTPS, CDN, serverless functions

### Backend → Render

1. Go to render.com → sign up with GitHub
2. Click "New Web Service" → connect your `mirage-ai` repo
3. **Name:** `mirage-api`
4. **Root Directory:** `backend`
5. **Runtime:** Python 3
6. **Build Command:** `pip install -r requirements.txt`
7. **Start Command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
8. **Instance Type:** Free (512 MB RAM, spins down after 15 min of inactivity)
9. **Environment Variables:** add all the keys from `.env.example`
10. Click Create

**Important free tier behavior:** Render free tier sleeps after 15 minutes of no traffic. First request after sleep takes 30–50 seconds to cold-start. During the demo, have someone hit `/health` every 10 minutes to keep it warm. Or hit it yourself right before presenting.

**Render gives you:** a free `.onrender.com` URL, HTTPS

### Bot → Render (or run locally)

**Option A (Render):** Create another Web Service for the bot
- Root Directory: `bot`
- Build Command: `pip install -r requirements.txt`
- Start Command: `python main.py`
- Problem: free tier only allows one web service. The bot is a long-running process, not a web server

**Option B (better for hackathon):** Run the bot on your laptop during the demo. It just needs internet access. This is simpler and more reliable

**Option C (free alternative):** Deploy the bot on **Railway** (free tier: 500 hours/month) or **Koyeb** (free tier available)

### Post-Deploy Checklist

| Check | How |
|-------|-----|
| Backend is live | Visit `https://mirage-api.onrender.com/health` → should return JSON |
| Frontend is live | Visit `https://mirage-ai.vercel.app` → should show landing page |
| Frontend calls backend | Open browser console on frontend → check for CORS errors → fix if needed |
| Bot is running | Send `/start` to the Telegram bot → should reply |
| Bot calls backend | Send a test text to bot → it should call backend (even if it gets a placeholder response) |

---

## 0.8 · Shared Types & Contracts

### Pydantic Models (backend/app/models/schemas.py)

These are the data structures that every part of the system uses. Define them once, use everywhere.

---

**`ScamVerdict`** — returned by the analysis engine

| Field | Type | Description |
|-------|------|-------------|
| is_scam | bool | Final verdict |
| confidence | float | 0.0 to 1.0 |
| scam_type | str or null | "bank_kyc", "fedex", "otp", "lottery", "job_offer", "relative_distress", "investment", "romance", "unknown" |
| risk_level | str | "low", "medium", "high", "critical" |
| red_flags | list[str] | Human-readable red flags: ["Creates false urgency", "Asks for OTP", "Domain registered 2 days ago"] |
| evidence | list[Evidence] | Detailed evidence items |
| stages_detected | list[str] | Which scam stages appear: ["hook", "authority", "urgency"] |
| summary | str | One-paragraph human-readable summary |
| recommended_action | str | "Ignore", "Block and report", "Call back on official number" |

**`Evidence`** — a single piece of evidence

| Field | Type | Description |
|-------|------|-------------|
| type | str | "url_analysis", "domain_age", "linguistic", "voice_synthetic", "visual" |
| detail | str | "Domain sbi-verify.xyz was registered 3 days ago" |
| severity | str | "low", "medium", "high" |

**`DrillResult`** — returned after a Fire Drill

| Field | Type | Description |
|-------|------|-------------|
| drill_id | str (uuid) | Unique drill ID |
| scam_type | str | Type of scam simulated |
| script_text | str | The scam script used |
| audio_url | str or null | URL to cloned voice audio |
| user_detected_scam | bool | Did user identify it? |
| detection_time_seconds | int | How fast |
| stages_identified | list[str] | Stages user caught |
| stages_missed | list[str] | Stages user missed |
| score_before | int | Resilience score before |
| score_after | int | Resilience score after |
| debrief | str | LLM-generated debrief text |

**`CallStage`** — real-time call analysis state

| Field | Type | Description |
|-------|------|-------------|
| current_stage | str | "none", "hook", "authority", "isolation", "urgency", "payment" |
| stage_confidence | float | 0.0 to 1.0 |
| alert_level | str | "safe", "suspicious", "warning", "critical" |
| alert_message | str or null | "Caller is creating urgency — this may be a scam" |
| transcript_so_far | str | Full transcript up to now |
| synthetic_voice_score | float | 0.0 (definitely human) to 1.0 (definitely AI) |
| timestamps | dict | {"hook": "0:05", "authority": "0:18", ...} |

**`ThreatIOCs`** — extracted indicators of compromise

| Field | Type | Description |
|-------|------|-------------|
| phone_numbers | list[str] | Extracted phone numbers |
| upi_ids | list[str] | Extracted UPI IDs |
| urls | list[str] | Extracted URLs |
| domains | list[DomainInfo] | Domain analysis results |
| bank_accounts | list[str] | Extracted bank account numbers |
| email_addresses | list[str] | Extracted emails |

**`DomainInfo`** — result of domain analysis

| Field | Type | Description |
|-------|------|-------------|
| domain | str | "sbi-verify.xyz" |
| age_days | int or null | Domain age in days |
| registrar | str or null | Registrar name |
| is_suspicious | bool | True if age < 30 days or is a lookalike |
| lookalike_target | str or null | "sbi.co.in" — the legitimate domain it's imitating |
| similarity_score | float | Levenshtein similarity to known brands |

**`AnalyzeRequest`** — input to the analysis endpoint

| Field | Type | Description |
|-------|------|-------------|
| text | str or null | Message text |
| url | str or null | URL to check |
| input_type | str | "text", "audio", "image", "url" |

For audio and image, the file is sent as multipart form data, not in the JSON body.

**`MemorySecret`** — for Memory Handshake

| Field | Type | Description |
|-------|------|-------------|
| question | str | "What did we name the dog in 2019?" |
| answer_hash | str | SHA-256 hash of the answer |
| totp_code | str or null | Current 6-digit TOTP code |

---

### API Endpoints Contract (what will exist by end of all phases)

| Method | Path | Input | Output | Phase |
|--------|------|-------|--------|-------|
| GET | `/health` | — | HealthCheck | 0 |
| POST | `/analyze` | AnalyzeRequest + optional file | ScamVerdict | 1 |
| POST | `/analyze/url` | `{url: str}` | DomainInfo | 1 |
| POST | `/drill/start` | `{user_id, scam_type, voice_clip}` | DrillResult (partial — script + audio) | 3 |
| POST | `/drill/respond` | `{drill_id, user_response, detection_time}` | DrillResult (complete — with debrief + score) | 3 |
| GET | `/drill/history/{user_id}` | — | list[DrillResult] | 3 |
| WS | `/guardian/stream` | audio chunks via WebSocket | CallStage updates | 4 |
| POST | `/guardian/analyze-clip` | audio file | CallStage | 4 |
| POST | `/memory/setup` | `{family_group_id, question, answer}` | MemorySecret | 4 |
| POST | `/memory/verify` | `{family_group_id, question, answer}` | `{verified: bool}` | 4 |
| GET | `/memory/totp/{family_group_id}` | — | `{code: str, expires_in: int}` | 4 |
| POST | `/honeypot/start` | `{scammer_message}` | `{response: str, extracted_iocs: ThreatIOCs}` | 5 |
| GET | `/graph/nodes` | — | list of graph nodes | 5 |
| GET | `/graph/edges` | — | list of graph edges | 5 |
| GET | `/graph/stats` | — | `{total_numbers, total_upis, total_domains, rings_detected}` | 5 |
| GET | `/map/heatmap` | — | `[{city, lat, lng, scam_count, top_scam_type}]` | 5 |

---

## Phase 0 Completion Checklist

```
□ GitHub repo created with full folder structure
□ .env.example committed with all required keys listed
□ .gitignore committed

□ Backend runs locally on port 8000
□ GET /health returns 200 with JSON
□ CORS allows localhost:3000
□ Config loads from .env and crashes on missing keys
□ Logger outputs structured logs

□ Supabase project created
□ All 6 tables created with correct columns and types
□ Supabase URL and key in .env

□ Neo4j AuraDB instance created
□ Uniqueness constraints created for all node types
□ Neo4j credentials in .env

□ Groq API key obtained and tested (one chat + one whisper call)
□ Gemini API key obtained and tested (one vision call)
□ Edge-TTS tested locally (generated one audio file)
□ Resemblyzer installed and tested (generated one embedding)
□ F5-TTS Colab notebook opens and runs

□ Frontend runs locally on port 3000
□ All 5 routes render placeholder pages
□ Navbar shows with working links
□ Dark mode applied globally
□ shadcn/ui components installed
□ API client can call backend /health

□ Telegram bot created via BotFather
□ Bot replies to /start with welcome message
□ Bot acknowledges text, voice, and photo messages
□ Bot runs locally

□ Frontend deployed to Vercel
□ Backend deployed to Render
□ Frontend can reach backend (no CORS errors)
□ Bot can reach backend

□ All Pydantic models defined in schemas.py
□ API contract documented
```

**When every box is checked, Phase 0 is done. Move to Phase 1.**

---

Ready for Phase 1 deep dive? Say the word.