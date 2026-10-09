# Mirage — 100% Free Tech Stack

## Core

| Layer | Tool | Why Free |
|-------|------|----------|
| **Frontend** | Next.js + Tailwind on **Vercel** | Hobby tier = free forever |
| **Backend** | FastAPI on **Render** | Free tier (spins down after 15min, fine for demo) |
| **Database** | **Supabase** (Postgres) | 500MB, 50K rows — more than enough |
| **Scam Graph** | **Neo4j AuraDB** | 1M nodes free forever |

## AI (all free tier)

| Task | Tool | Free Limit |
|------|------|-----------|
| **Reasoning / Scam Analysis / Honeypot** | **Groq** (Llama 3.3 70B) | 30 req/min, blazing fast |
| **Backup LLM** | **Google Gemini 2.0 Flash** | 1M tokens/day |
| **Transcription** | **Groq Whisper** | Free, real-time speed |
| **Voice Cloning (Fire Drill)** | **F5-TTS** or **XTTS v2** on Google Colab | Open-source, free GPU |
| **TTS (responses)** | **Edge-TTS** (`edge-tts` Python pkg) | Unlimited, supports Hindi + Tamil |
| **Deepfake Detection** | **Resemblyzer** (local) | Open-source, pip install |

## Messaging (WhatsApp replacement)

| Tool | Why |
|------|-----|
| **Telegram Bot** | 100% free, no limits, handles text + voice + images. Setup in 2 min via BotFather. Judges can try it live. |

> **Note:** WhatsApp Cloud API *does* give 1,000 free conversations/month — enough for a hackathon. Use it if you want, but Telegram is zero-friction and zero-cost.

## Checks & Utils (all free, no API key)

| Task | Tool |
|------|------|
| WHOIS / Domain age | `python-whois` library |
| Lookalike domain | Levenshtein distance (built-in) |
| Media provenance | `c2pa-python` library |
| OCR (screenshots) | `pytesseract` or Gemini Vision |

## Hosting Summary

```
Frontend  →  Vercel        (free)
Backend   →  Render        (free)
Postgres  →  Supabase      (free)
Graph DB  →  Neo4j AuraDB  (free)
AI        →  Groq + Gemini (free tiers)
Bot       →  Telegram      (free)
Voice     →  Colab + Edge  (free)
```

**Total monthly cost: $0.**

---

## What to demo on what

| Demo Moment | Runs On |
|-------------|---------|
| Scam Fire Drill (clone + simulate) | Web app (Next.js) |
| Live Call Guardian | Web app (mic input → Groq Whisper → analysis) |
| Memory Handshake | Web app (simple UI) |
| Forward suspicious message | Telegram Bot |
| Scam Graph + Weather Map | Web dashboard (Neo4j + Leaflet.js) |

---

**This is locked in.** Tell me your team size, hours remaining, and who's strong at what — I'll break this into an hour-by-hour build plan and we start coding.