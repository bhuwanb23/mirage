# Mirage — 60s launch ad (/brag-slim) — v2 narrative character cut

## Angle

**Input:** project (`D:\projects\website\mirage`), inspected from code.
**Format:** landscape 1920×1080, 30fps, **60s** (user override of the skill's ~20s default).
**Tone:** narrative character ad — a real scam call, a real save. Warm home set → cool product set → warm lockup.
**Audio:** two-voice VO (`en-IN-neerjaNeural` narrator + `en-IN-prabhatNeural` scammer) + a scored music bed, mixed as a single piece.

- **What it is:** Mirage is a scam *vaccine*. v1 showed the product; v2 shows the *moment* it works — an elderly mother nearly loses her OTP, the guardian cuts the call at stage 4 · Urgency, and the family learns from the debrief.
- **Who it's for:** Indian families and elders on Telegram/WhatsApp who get KYC, parcel, OTP and "officer" calls.
- **What sets it apart:** everyone else ships a classifier. Mirage stages the drama — hook, authority, isolation, urgency, payment — and the whole story is the 5-stage pipeline, played by people.
- **Best real line (the cut):** stage 3 sc3 is **atrim'd mid-sentence at t≈21** — the scammer's own voice is cut off by the save.
- **Visual hook:** flat-vector elderly mother ("Amma", silver bun, teal dress, warm skin) holding a phone; a hooded scammer silhouette with red eyes; an emerald shield that physically interrupts.

## Hook / highlights / punchline

- **Hook (0–3.6s):** warm living room, Amma answers. Narrator: *"This is the call that gets everyone."*
- **Highlight 1 — The Call (3.3–21.35s):** scammer voice over a darkening screen, red stage chips climb, OTP card types in. Cut off mid-urgent at stage 4.
- **Highlight 2 — The Save + Handshake (21–38.8s):** emerald flash, "SCAM INTERCEPTED", daughter's phone, Memory Handshake questions only family can answer.
- **Highlight 3 — Product montage (38.4–55.4s):** Guardian dashboard (247 shielded / 18 blocked / ₹4.2L), stage tracker; zero-install bot verdict (SCAM · 97%); Neo4j Scam Graph lighting up.
- **Punchline (55–60s):** *"Don't detect scams. Vaccinate people against them."* → **Mirage · The Scam Vaccine**.

## Visual identity (from the source, not invented)

- Sets: warm home (`--warm: oklch(0.72 0.12 60)`, wooden table, soft lamp) vs cool product (`--bg: oklch(0.145 0 0)`, `--card: oklch(0.205 0 0)`).
- Accent: **emerald-400** (shield, hero UI). Scam red: `--red: oklch(0.704 0.191 22.216)`. Amber warnings.
- Characters: Amma = `--skin: oklch(0.78 0.10 75)` + `--silver: oklch(0.85 0.02 260)` bun + teal dress; scammer = hooded silhouette + red eyes + red phone glow; daughter = ponytail + emerald top.
- Fonts: **Geist** + **Geist Mono** (bundled woff2, gated on `document.fonts.ready`).
- All on-screen product copy is repo verbatim (LAYERS, SCAM_SCRIPT, `format_verdict`, dashboard stats).

## Storyboard — durations sum to 60.0s

| # | Window | Scene | On-screen | VO |
|---|--------|-------|-----------|-----|
| 1 | 0.0–3.6 | **Home** — Amma at the table, phone rings | warm set, side table, phone | n1: *"This is the call that gets everyone."* |
| 2 | 3.3–17.4 | **The scammer** — hooded figure, red glow, stage chips climb | `1 · Hook → 2 · Authority → 3 · Isolation` | sc1/sc2 (prabhat): the officer script |
| 3 | 17.1–21.35 | **OTP card + cut** | OTP types in, red pulses hard | sc3 **atrim=0:3.65** — cut mid-urgent |
| 4 | 21.0–28.8 | **The save** — emerald flash, SCAM INTERCEPTED, daughter's phone | shield, green takeover, stage 4 struck | n2: guardian interrupts before transfer |
| 5 | 28.4–38.8 | **Memory Handshake** — family Q&A over the call | handshake card, biriyana / Coorg lines | n3: only family can answer |
| 6 | 38.4–44.5 | **Dashboard** — Guardian stats | 247 / 18 / ₹4.2L + stage tracker | n4: the whole pipeline, live |
| 7 | 44.1–49.3 | **Zero-install bot** — forward a screenshot | `SCAM · 97%` + 4 red flags | n5: forward it, verdict in seconds |
| 8 | 48.9–52.3 | **Scam Graph** — Neo4j tiles light | number / domain / UPI / mule / cash-out | (music) |
| 9 | 51.9–55.4 | **Graph full + debrief note** | network blooms, score 68 | (music) |
| 10 | 55.0–60.0 | **Outro lockup** | shield + **Mirage** + `The Scam Vaccine` + thesis | n6: *"Mirage. The scam vaccine."* |

Scene windows in `video.html` are slightly wider than the VO slots (crossfades overlap); `mix.ps1` owns exact audio placement.

## Audio plan

| Clip | Voice | Placed | Note |
|------|-------|--------|------|
| n1 | neerja | @0.4 | hook |
| sc1 | prabhat | @3.5 | officer opens |
| sc2 | prabhat | @10.0 | authority / isolation |
| sc3 | prabhat | @17.3, atrim **0:3.65** | cut mid-sentence by the save at t≈21 |
| n2 | neerja | @21.5 | the save |
| n3 | neerja | @29.0 | Memory Handshake |
| n4 | neerja | @39.0 | dashboard |
| n5 | neerja | @45.0 | zero-install bot |
| n6 | neerja | @55.6 | outro |

Music (`music2.py`, stdlib synth, 96 BPM): Am tension (3–20) → F **save** (20–28, boom @20.0) → C hope (28–38) → Am bridge (38–44) → G product (44–55) → Am outro (55–60). Riser into 20.0 and 38.0.

## Build (v2 pipeline — v1 patterns reused)

1. `work/vo2.py` + `vo2b.py` (edge-tts, two voices) → 9 WAVs; ffprobe timings override `manifest2.json` scammer entries.
2. `work/music2.py` → `work/audio/music.wav` (60.0s).
3. `work/video.html` — 10 scenes, flat-vector characters (CSS/SVG), `window.__seek(t)` pure, `window.__ready` gate. Three post-still fixes: Amma worried brows raised, `#s3 .amma-reach` moved to `left:400px`, S1 side table added under the phone.
4. `work/mix.ps1` → `master.wav` 60.0s (VO + music, ducked, peak ≤ −1 dBTP).
5. `work/check.mjs` → 46 stills in `work/stills-check/`; fixes verified at t2 / t7 / t20.
6. `work/render.mjs` → 1800 PNGs (~74s) → ffmpeg mux → `brag.mp4` (h264 1920×1080 30fps, aac, **duration 60.000000**, ~3 MB) — ffprobe verified.
7. Poster: settled **frame t=58.5** (outro lockup, no motion) → `brag.jpg` (replaces frame 0, not appended).
8. `share-copy.txt` rewritten for the narrative cut.

## Deliverables

- `brag.mp4` — v2 narrative character ad, 60.0s.
- `brag.jpg` — settled outro lockup poster.
- `share-copy.txt` — story-told-as-ad copy.
- This plan.
