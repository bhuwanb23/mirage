# Security Policy

## Overview

Mirage is an anti-scam training and assistance system: a Next.js frontend plus a
FastAPI backend that classifies scam texts/URLs/images/voice, runs a live
Guardian call-pipeline, operates a honeypot “Ramesh” persona that wastes
scammers’ time and extracts IOCs, and maintains a scam IOC graph (SQLite or
Neo4j).

Current threat-model summary:

- **Authentication is not yet implemented**. In the current code a non-local
  deployment exposes every API endpoint to any caller. Until auth/authorization
  land, treat the API as a public assist tool, not a private one.
- **Crown jewels are secrets, not the app logic**: LLM keys
  (`GROQ_API_KEY`, `GEMINI_API_KEY`), Supabase anon key, Neo4j URI/password,
  and the memory handshake pepper. If any of these leak, rotate first, then
  purge history.
- **User PII** entered into Fire Drill profiles (name, city, bank, employer,
  relative name/relation, optional uploaded voice clip) and the Memory Handshake
  answers are the main privacy surface.
- **Scam IOC graph data** (phone numbers, UPI IDs, domains, bank accounts,
  scammer names, report narratives) is public-by-design for the scam-hunter
  feature, but ingestion still must be validated so the graph cannot be poisoned
  by crafted input.

## Supported Versions

| Version | Branch | Supported          |
|---------|--------|--------------------|
| 0.1.0   | `main` | Yes (current line) |

Only the `main` branch is supported. Older commits are historical.

## Reporting a Vulnerability

Please do **not** open a public issue for a security problem until we have had
a chance to coordinate a fix.

- Preferred: email **security@mirage.example** with a description, step-by-step
  repro, and any relevant request/response or log excerpts.
- Alternative: open a private/disclosure issue in the repo if the platform
  supports it, and request confidentiality.

Please include:
- What you expected to happen
- What actually happened
- The endpoint(s) or component(s) involved
- Any auth/role assumptions (note that most endpoints are currently unprotected)

Expect an acknowledgment within **5 business days**. We will try to keep
reporters informed of progress and coordinate disclosure timing.

## Hardening Status

### Already in place

- **Memory Handshake secrets are not stored in plaintext.** Answers are
  normalized and HMAC-SHA-256-peppered using `MEMORY_HASH_PEPPER`; only hashes
  are persisted. TOTP (`pyotp`) gives the family a rotating code. Answer
  verification is rate-limited: 3 wrong answers locks that question for 5
  minutes. Group join uses an invite code.
- **IOC extraction is validated and filtered.** Regex-first extraction normalizes
  and filters out the honeypot persona’s own fabricated phone numbers/accounts
  and real helplines that must never be flagged. LLM-extracted and agent-reported
  IOCs go through the same validation/filtering path before storage or graph
  ingestion.
- **Honeypot agent JSON is sanitized.** The agent is an untrusted LLM output;
  parsed agent turns are checked against the expected shape and bad fields are
  dropped rather than passed through blindly.
- **File uploads are validated.** Voice uploads accept `.wav/.mp3/.m4a/.ogg`
  up to 5 MB and check the `audio/*` media type where provided. Images accept
  `png/jpg/jpeg/webp` up to 5 MB with MIME inference from magic bytes and
  size checks. Temp files are cleaned up in `finally` blocks.
- **Audio processing is defensive.** ffmpeg is called with timeouts, error
  capture, and explicit flags; decode failures are logged and degrade gracefully
  instead of crashing the call.
- **CORS is explicit-origin based.** Origins come from `CORS_ORIGINS` plus an
  explicit Render preview regex. A production startup guard rejects an empty or
  wildcard `CORS_ORIGINS` when `ENVIRONMENT=production`.
- **Security headers on every response.** `X-Content-Type-Options: nosniff`,
  `X-Frame-Options: SAMEORIGIN`, `Referrer-Policy:
  strict-origin-when-cross-origin`, `Permissions-Policy:
  camera=(), microphone=(), geolocation=()`. `Server` and `X-Powered-By` are
  stripped. Sensitive browser endpoints get a stricter `Cache-Control`
  (`no-store, no-cache, must-revalidate, private`).
- **Error payloads are scrubbed.** JSON serialization for analysis/image/voice/URL
  responses runs through a safe dump that removes exception objects and
  traceback-like strings so internal details do not leak to clients.
- **LLM output is treated as untrusted.** Drill scripts are sanitized so real
  phone numbers, URLs, and UPI IDs never leak into demo audio/scripts; scripted
  values are replaced with obviously fake placeholders. Narratives and structured
  data are serialized defensively before any use.
- **Secrets come from the environment.** `.env.example` is committed with
  placeholders. Real `.env`/`.env.local` files are gitignored. Provider clients
  soft-fail in development when keys are missing rather than hard-crashing the
  demo.

## Known Limitations

These are the current gaps. They are the priorities for any public-facing
deployment.

- **No authentication or per-user authorization yet.** Any caller can currently
  hit `/analyze/*`, `/drill/*`, `/guardian/stream`, `/memory/*`, `/graph/*`,
  `/honeypot/*`, and `/report/generate`. This is the single largest gap for any
  non-local deployment.
- **Partial rate limiting.** Memory answer verification is rate-limited in-process.
  Transcription client code retries on 429. Other endpoints do not yet have a
  shared rate limiter. In multi-instance deployments an in-memory limiter does
  not coordinate across instances.
- **In-memory session/state stores are process-local.** Guardian sessions,
  honeypot sessions, in-memory drill store, and the in-memory memory-handshake
  store live in one process and are lost on restart. Multi-instance deployments
  need the real Supabase/Neo4j backends wired for these features.
- **SQLite graph store is file-backed.** It is fine for single-process demo use.
  Multi-instance or concurrent-writer scenarios need the Neo4j backend (or a
  properly locked/shared store) and appropriate deployment discipline.
- **Static media is served without per-request auth in dev.** Generated drill
  audio and uploaded voice clips are served from `/media/drill`. In production
  these should be served with the right CORS/auth posture and cache control, not
  treated as a public static bucket.
- **Dependency install scripts are not yet blocked at install time.** Follow the
  current install-carefully guidance in `docs/CONTRIBUTING.md`. Before each
  release, run the native package-manager audit against the committed lockfile and
  triage critical/high findings by reachability; do not blindly apply forced
  remediation.
- **No CSP header yet.** The frontend relies on framework auto-escaping. Before
  trusting any rich user-supplied HTML/Markdown, audit direct `innerHTML`/bypass
  paths and consider adding a strict CSP.

## Environment and Secrets

Secrets are read from the environment only. Do not commit real values.

Required/important secrets:

- `GROQ_API_KEY`
- `GEMINI_API_KEY`
- `SUPABASE_URL`
- `SUPABASE_ANON_KEY` (or `SUPABASE_PUBLISHABLE_KEY`)
- `NEO4J_URI`
- `NEO4J_PASSWORD`
- `MEMORY_HASH_PEPPER` (strongly recommended for production memory handshake)

Production deploy expectations:

- Set `ENVIRONMENT=production`.
- Set `CORS_ORIGINS` to the exact allowed origins; the production guard will
  reject an empty or wildcard value at startup.
- Provide all required secrets in the hosting environment, not in the repo.
- If a secret is suspected compromised, rotate it first, then purge any history
  it may have reached. A secret that has touched a remote is treated as
  compromised the moment it lands there.

## Deployment Checklist

Before exposing Mirage beyond localhost:

- [ ] Set `ENVIRONMENT=production`.
- [ ] Set `CORS_ORIGINS` to the exact frontend origins you trust.
- [ ] Provide all required secrets in the host environment (LLM keys, Supabase,
  Neo4j, memory pepper).
- [ ] Terminate TLS at the edge / proxy; the app should not be reachable over
  plain HTTP in production.
- [ ] Decide on auth/authorization for the currently-open endpoints before
  going public. At minimum, protect endpoints that accept PII, files, or
  report generation.
- [ ] Serve static drill media and uploaded voice clips behind the same origin
  and auth/CORS posture as the rest of the app, with appropriate cache control.
- [ ] Use the shared backend (Supabase/Neo4j) for multi-instance or
  multi-process deployments so session/graph/state stores are not local-only.
- [ ] Run the native dependency audit against the committed lockfile before each
  release and triage critical/high findings by reachability.
- [ ] Add monitoring/alerting for 429s, graph ingest failures, client errors,
  and unexpected auth/provider failures.
- [ ] If you collect or store personal data, define retention and deletion
  behavior before launch, not after.

## Scope Notes

- This policy covers the Mirage repository as shipped here. Third-party services
  (LLM providers, Supabase, Neo4j Aura, hosting) have their own security models
  and incident processes; treat their keys as compromised if they leak.
- The ML/ directory contains experimental notebook/research material and is not
  part of the hardened production path by default.
