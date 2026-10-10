# API contracts

Single source of truth for the Mirage HTTP surface. The frontend (`frontend/src/lib/api.ts`),
the bot (`bot/utils/api.py`), and the backend routers all implement against this file.

**Legend:** ✅ implemented and smoke-tested · 📋 contract only, built in the named phase.

Base URL: `http://localhost:8000` (dev) / set via `MIRAGE_API_URL`, `NEXT_PUBLIC_API_URL`.

Conventions: JSON in/out · `Content-Type: application/json` · errors return
`{"detail": "<message>"}` with a 4xx/5xx status · timestamps are ISO-8601 UTC.

---

## System

### ✅ `GET /health`

```jsonc
// 200
{
  "status": "ok",
  "service": "mirage-api",
  "version": "0.1.0",
  "timestamp": "2026-10-09T02:00:00Z",
  "providers": {
    "configured": "ollama",       // active LLM provider, or null
    "available": ["ollama"],      // providers that could be used
    "supabase": false,            // client initialized?
    "neo4j": false,
    "environment": "development"
  }
}
```

---

## Text & media analysis (Phase 2)

### 📋 `POST /analyze/text`

```jsonc
// req
{ "text": "Your KYC has expired...", "lang": "en" }
// 200
{
  "verdict": "SCAM",             // SAFE | SUSPICIOUS | SCAM
  "risk_level": "high",          // low | medium | high | critical
  "scam_type": "bank_kyc",       // see ScamType enum
  "stage": "urgency",            // hook | authority | isolation | urgency | payment
  "evidence": [
    { "type": "authority", "quote": "this is the bank KYC desk", "weight": 0.4 }
  ],
  "explanation": "…one plain sentence…"
}
```

### 📋 `POST /analyze/image`

`multipart/form-data` with `file` (screenshot), or JSON
`{"image_b64": "...", "lang": "en"}`. Response mirrors `/analyze/text`.

### 📋 `POST /analyze/voice`

`multipart/form-data` with `file` (ogg/mp3/wav). Transcribes via Groq Whisper,
then returns the `/analyze/text` shape.

---

## Fire drills (Phase 3)

Implemented in `backend/app/routers/drill.py`; frontend client lives in
`frontend/src/lib/drill-api.ts`. All bodies are JSON except the two noted.
In dev, drill state is held in memory (optional Supabase mirror) — restart
resets history.

### ✅ `POST /drill/profile`

```jsonc
// req
{ "name": "Priya Sharma", "city": "Mumbai", "bank": "sbi",
  "employer": "TCS", "relative_name": "Aarav", "relative_relation": "son",
  "language": "en", "user_id": "uuid-from-localStorage" }
// 200
{ "profile_id": "hex", "user_id": "uuid", "name": "Priya Sharma",
  "first_name": "Priya", "city": "Mumbai", "bank": "sbi",
  "bank_full_name": "State Bank of India", "employer": "TCS",
  "relative_name": "Aarav", "relative_relation": "son",
  "language": "en", "voice_clip_url": null, "voice_duration_seconds": 0,
  "status": "saved", "message": "Profile saved. …" }
// 422 blank name · defaults: city=Mumbai, bank=sbi
```

### ✅ `POST /drill/upload-voice`

`multipart/form-data` with `file` (`.wav|.mp3|.m4a|.ogg`, ≤ 5 MB, 5–120 s)
and `profile_id`.

```jsonc
// 200
{ "voice_clip_url": "/media/drill/voice/<id>.mp3",
  "duration_seconds": 12.5, "status": "ready", "message": "Voice clip saved." }
// 404 unknown profile · 422 bad format / too short / too large
```

### ✅ `POST /drill/generate-script`

```jsonc
// req  { "profile_id": "hex", "scam_type": "bank_kyc", "difficulty": "medium" }
// 200 — difficulty ∈ easy|medium|hard; scam_type ∈ the 5 types below
{ "script_id": "hex", "profile_id": "hex", "scam_type": "bank_kyc",
  "title": "Fake State Bank of India KYC Verification Call",
  "full_script": "Hello, am I speaking with Priya Sharma? [pause 2s] …",
  "stages": [
    { "stage": "hook", "order": 1, "timestamp_hint": "0:00-0:08",
      "start_seconds": 0.0, "end_seconds": 8.2,
      "script": "…", "tactic": "Uses your full name…" }
    /* authority, isolation, urgency, payment */
  ],
  "red_flags_planted": ["Used full name to create false familiarity", …],
  "difficulty_level": "medium", "estimated_duration_seconds": 55,
  "language": "en", "source": "llm" /* | template */ }
// 404 unknown profile_id
```

### ✅ `POST /drill/synthesize-voice`

```jsonc
// req  { "script_id": "hex", "method": "auto" }  // auto | edge-tts | f5tts
// 200
{ "script_id": "hex", "audio_url": "/media/drill/<script_id>.mp3",
  "duration_seconds": 70.5, "method_used": "edge-tts",
  "status": "ready", "message": "Voice: en-IN-PrabhatNeural." }
// status="failed" + audio_url=null → frontend falls back to the
// pre-generated /audio/drill/<scam_type>.mp3, then to text-only mode.
// 404 unknown script_id
```

### ✅ `POST /drill/respond`

```jsonc
// req
{ "script_id": "hex", "user_action": "identified_scam",
  "reaction_time_seconds": 18.3, "audio_position_seconds": 18.3 }
// user_action ∈ identified_scam | fell_for_it | no_response
// 200
{ "drill_id": "hex", "script_id": "hex", "scam_type": "bank_kyc",
  "user_action": "identified_scam", "reaction_time_seconds": 18.3,
  "stages_caught": ["hook", "authority"],
  "stages_missed": ["isolation", "urgency", "payment"],
  "trigger_stage": "authority",
  "drill_score": 62, "score_before": 42, "score_after": 55,
  "change": 13, "label": "Cautious",
  "debrief": {
    "outcome": "success", "headline": "…", "reaction_assessment": "…",
    "stages_caught": [{ "stage": "hook", "timestamp": "0:00-0:08",
      "what_happened": "…", "why_it_works": "…", "real_world_tip": "…" }],
    "stages_missed": [ /* same shape */ ],
    "key_lesson": "…", "real_world_action": "…", "encouragement": "…" } }
// 404 unknown script_id
```

### ✅ `GET /drill/score/{user_id}`

```jsonc
// 200 — powers ScoreCard/ScoreChart (empty history => zeros)
{ "user_id": "uuid", "current_score": 55, "previous_score": 42,
  "change": 13, "label": "Cautious", "drills_completed": 3,
  "best_reaction_time": 8.2, "weakest_scam_type": "fedex",
  "history": [
    { "drill_number": 1, "score": 25, "scam_type": "bank_kyc", "date": "2026-10-10" }
  ] }
```

### ✅ `GET /drill/scam-types`

```jsonc
// 200 — setup screen selector (frontend keeps a fallback list offline)
// estimated_duration_seconds is derived from the fallback template word count.
{ "scam_types": [
  { "id": "bank_kyc", "label": "Bank KYC Fraud", "default_difficulty": "medium",
    "estimated_duration_seconds": 63.2 },
  { "id": "fedex", "label": "FedEx / Customs Parcel", "default_difficulty": "medium",
    "estimated_duration_seconds": 57.2 },
  { "id": "relative_distress", "label": "Relative in Distress", "default_difficulty": "hard",
    "estimated_duration_seconds": 58.0 },
  { "id": "rbi_police", "label": "RBI / Police Impersonation", "default_difficulty": "hard",
    "estimated_duration_seconds": 57.6 },
  { "id": "job_offer", "label": "Job Offer / Work-from-Home", "default_difficulty": "easy",
    "estimated_duration_seconds": 64.4 }
] }
```

Generated audio and uploaded voice clips are served statically from
`GET /media/drill/...` (no auth in dev).

---

## Guardian (Phase 4)

### 📋 `POST /calls/stream`

`Content-Type: application/x-ndjson` — incremental audio in, NDJSON events out:

```jsonc
{ "stage": "urgency", "risk": 0.72, "hint": "They are creating a deadline." }
{ "stage": "payment", "risk": 0.94, "alert": "Do NOT share the OTP." }
```

### 📋 `POST /memory/handshake`

```jsonc
// req  { "user_id": "uuid", "spoken": "the answer the caller gave" }
// 200  { "match": false, "reason": "phrase mismatch" }
```

---

## Scammer Hunter + Scam graph (Phase 5) ✅ implemented

### ✅ `POST /honeypot/start` / `POST /honeypot/continue`

```jsonc
// req  { "scammer_message": "…", "persona": "ramesh", "mode": "live|simulate" }
// cont { "session_id": "hp-…", "scammer_message": "…" }
// 200
{
  "session_id": "hp-0a1b2c3d4e5f",
  "reply": "Okay beta, I'm writing it down. S-B-I dash safe at Y-B-L?…",
  "tactic_used": "mishearing",          // mishearing|tangent|confusion|app_failure|repetition|compliance
  "iocs_extracted_this_turn": { "phone_numbers": ["9876543211"], "upi_ids": ["sbi-safe@ybl"] },
  "total_iocs_extracted": 2,
  "conversation_health": "engaged",     // engaged|frustrated|about_to_hang_up
  "messages_in_session": 4,
  "estimated_time_wasted_seconds": 45,
  "mode": "simulate"
}
```

`mode="simulate"` skips the LLM (deterministic persona) — used by the scripted
demo and tests. `mode="live"` uses Groq→Gemini→Ollama with rule fallback.

### ✅ `GET /honeypot/session/{session_id}`

Full conversation log + accumulated `ThreatIOCs` + total time wasted.

### ✅ `GET /honeypot/scripted`

Pre-written demo exchange (plan §5.1 Option A) + `ioc_highlights` map the UI
renders as highlighted chips.

### ✅ `GET /graph/data?limit=200`

```jsonc
// 200 — force-directed payload (plan §5.4)
{
  "nodes": [{ "id": "phone:9876543210", "label": "98765-43210", "type": "PhoneNumber",
              "group": 1, "report_count": 3, "in_ring": true, "properties": {} }],
  "edges": [{ "source": "phone:9876543210", "target": "upi:sbi-safe@ybl", "type": "USES_UPI" }],
  "truncated": false
}
```

### ✅ `GET /graph/stats`

```jsonc
{ "phone_numbers": 8, "upi_ids": 3, "domains": 2, "bank_accounts": 2,
  "scam_reports": 8, "rings": 3, "scam_type_counts": { "bank_kyc": 4 },
  "backend": "sqlite" }   // "neo4j" when NEO4J_URI is configured
```

### ✅ `GET /graph/rings?min_size=3`

Plan §5.3 queries 1–3: connected-component rings + UPIs/domains shared by
multiple phone numbers.

### ✅ `GET /map/heatmap`

Plan §5.5 city dataset (`Delhi` 47 / Bank KYC / 0.9 …) + `national_stats`
enriched with live report + ring counts.

### ✅ `POST /report/generate`

```jsonc
// req  { "user_name": "Priya Sharma", "scam_type": "bank_kyc", "amount_lost": 0,
//        "honeypot_session_id": "hp-…"?, "iocs": {…}?, "anonymous": false }
// 200  { "report_id": "RPT-2026-1010-12345", "report_text": "CYBER CRIME COMPLAINT\n…",
//        "helpline_script": "📞 1930 HELPLINE SCRIPT\n…", "urgent": false }
```

Passing `honeypot_session_id` prefills IOCs from that session. LLM narrative
with deterministic template fallback.

---

## Bot intake (Phase 2)

The bot calls `POST /analyze/text` and `POST /analyze/image` today; both return
`501` until Phase 2 lands, so the bot replies with an acknowledgement stub
(`bot/handlers/check.py`).

---

## Error shape

```jsonc
// 422 — FastAPI validation
{ "detail": [{ "loc": ["body", "text"], "msg": "field required", "type": "value_error" }] }

// 503 — no LLM provider reachable
{ "detail": "No LLM provider available" }
```

## Versioning

No version prefix until something external depends on it. When that happens:
`/v1/...` and this file records the breaking change.
