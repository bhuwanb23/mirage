# API contracts

Single source of truth for the Mirage HTTP surface. The frontend (`frontend/src/lib/api.ts`),
the bot (`bot/utils/api.py`), and the backend routers all implement against this file.

**Legend:** ✅ implemented in Phase 0 · 📋 contract only, built in the named phase.

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

### 📋 `POST /drills`

```jsonc
// req
{ "user_id": "uuid", "scam_type": "fedex", "lang": "hi", "name": "Priya" }
// 200
{
  "drill_id": "uuid",
  "script": "…narrative…",
  "stages": [{ "id": "hook", "order": 1, "line": "…" }],
  "audio_url": null              // filled by F5-TTS, see ml/README.md
}
```

### 📋 `POST /drills/{drill_id}/result`

```jsonc
// req
{ "responses": [{ "stage": "urgency", "user_text": "…", "latency_ms": 4200 }] }
// 200
{
  "score": 68,
  "caught": ["hook", "payment"],
  "missed": ["isolation", "urgency"],
  "advice": "…"
}
```

### 📋 `GET /users/{user_id}/resilience`

```jsonc
// 200 — powers the Dashboard chart
{ "score": 68, "history": [{ "day": "2026-10-02", "score": 61 }] }
```

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
