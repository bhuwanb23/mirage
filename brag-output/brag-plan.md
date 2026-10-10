# Mirage — 60s launch ad (/brag-slim)

## Angle

**Input:** project (`D:\projects\website\mirage`), inspected from code.
**Format:** landscape 1920×1080, 30fps, **60s** (user override of the skill's ~20s default).
**Tone:** `default` — punchy, playful, clean; soft transitions. 7 scenes (stretched from the usual 4–5 because of the duration).
**Audio:** voiceover `en-IN-neerjaNeural` (warm, Indian English) + one music/SFX bed, mixed as a single piece.

- **What it is:** Mirage is a scam *vaccine* — it runs a personalised attack against you first, debriefs your misses, scores your resilience, then shields you live when a real one calls.
- **Who it's for:** Indian families and elders on Telegram/WhatsApp who get KYC, parcel, OTP and "officer" calls — people who will never install another app.
- **What sets it apart:** everyone else ships a classifier that says `scam: 0.87`. Mirage inverts it — simulate the attack *before* the attacker does.
- **Best real line (the debrief):** "The 10-minute deadline pushed you to share the OTP. Missed."
- **Visual hook:** a real scam transcript typing itself, live, while an emerald stage tracker climbs `1 · Hook → 5 · Payment` and the alert fires between 4 and 5.

## Hook / highlights / punchline

- **Hook (2–3s):** dark screen, one real scam line types itself in, red `1 · Hook` chip. VO: *"You have had this call."*
- **Highlight 1 — Fire Drill:** the only product that attacks *you* on purpose, then hands you the debrief and a score.
- **Highlight 2 — Live Call Guardian:** the 5-stage pipeline climbing in real time, alert before the transfer, Memory Handshake only your family can answer.
- **Highlight 3 — Zero-install bot + Scammer Hunter:** forward it to a bot you already have; every catch lights the graph.
- **Punchline:** the real thesis, verbatim — *"Don't detect scams. Vaccinate people against them."* → **Mirage · The Scam Vaccine**.

## Visual identity (taken from the source, not invented)

- Dark UI: `--background oklch(0.145 0 0)`, `--card oklch(0.205 0 0)`, `--border` at 60%.
- Accent: **emerald-400** (every icon, link, score). Warning: amber. Critical: red.
- Fonts: **Geist** + **Geist Mono** (bundled locally as woff2, `document.fonts.ready` before capture).
- Texture: mono micro-labels (`Phase 2`, `Score 68`), hairline borders, rounded-lg cards — the landing page's own grammar.
- No invented numbers, testimonials or claims. All lines on screen are repo copy; small illustrative UI (a typing transcript) is the product's own demo script.

## Storyboard — durations sum to 60.0s

| # | Start | Dur | Scene | On-screen (real copy) | VO line |
|---|-------|-----|-------|-----------------------|---------|
| 1 | 0.0 | 3.0 | **Hook** — black; scam transcript types in | `This is Officer Rajesh from the SBI fraud department…` + chip `1 · Hook` (red pulse) | "You have had this call." |
| 2 | 3.0 | 5.0 | **Reveal** — shield, thesis lands word-by-word | **Don't detect scams. / Vaccinate people against them.** | "Don't detect scams. Vaccinate people against them." |
| 3 | 8.0 | 13.0 | **Fire Drill** entry → action → result | setup card → "Your responses, voice, and hesitation will be scored per hook." → scam bubbles type → **62** + `Missed.` notes | "So Mirage runs the attack on you first — then shows exactly which hooks you missed, and scores you." |
| 4 | 21.0 | 15.0 | **Live Call Guardian** | transcript types, `1·Hook → 5·Payment` climbs, alert fires between 4 and 5, **Memory Handshake** card | "On a live call, the guardian counts the stages — hook, authority, isolation, urgency, payment — and alerts before the transfer. Only your family can pass the handshake." |
| 5 | 36.0 | 11.0 | **Zero-install bot + Scammer Hunter** | forward → verdict card (real `format_verdict` text) → graph tiles `Fake FedEx parcel · 412 nodes` | "Forward a screenshot, a voice note, a link — to a bot you already have. No app to install." |
| 6 | 47.0 | 8.0 | **Four layers** slide in one by one | `LAYERS` array verbatim: Fire Drills / Live Call Guardian / Scammer Hunter / Zero-install Bot | "Four layers. One vaccine." |
| 7 | 55.0 | 5.0 | **Outro** | shield + **Mirage** + `The Scam Vaccine` + hero line small | "Mirage. The scam vaccine." |

Transitions: soft (stagger out-then-in, or dip through background) — never a crossfade between two busy layouts.

## Build

1. `work/capture.mjs` (Playwright) drives the real app at 1920×1080 → `work/stills/` (landing, drill ×4, guardian ×6, graph, dashboard).
2. `work/vo.py` (edge-tts, `en-IN-neerjaNeural`) → per-line audio placed at the storyboard times.
3. `work/music.py` (Python stdlib synth — no numpy on this box) → one 60s bed: pad + sub + kick + hat + arp in one key, scene accents (hook hit, reveal swell, guardian sting), then mixed with VO via ffmpeg (ducking, peak ≤ −1 dBTP).
4. `work/video.html` — single 1920×1080 stage, `window.__seek(t)` makes every frame a pure function of time.
5. Stills from every scene **and mid-transition** → fix overflow/collisions/contrast → re-check.
6. 1800 frames → `brag.mp4`; `ffprobe` verify 60.0s / 30fps / 1920×1080.
7. Strongest settled frame → `brag.jpg`, baked as **frame 0** (replaced, not appended).
8. `share-copy.txt`.
