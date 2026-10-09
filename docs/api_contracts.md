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

## Scam graph (Phase 5)

### 📋 `GET /graph/stats`

```jsonc
{ "phones": 1240, "upi_ids": 812, "domains": 96, "campaigns": 31 }
```

### 📋 `GET /graph/campaigns`

```jsonc
// 200
[{ "name": "Fake FedEx parcel", "nodes": 412, "active": true, "last_seen": "…Z" }]
```

### 📋 `GET /iocs/{type}/{value}`

`type` ∈ `phone | upi | domain | ip`. Returns the node plus its campaign links.

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
