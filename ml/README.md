# Mirage ML

Two independent workstreams. Neither blocks Phase 0–2.

## 1. Voice cloning — `voice_cloning/`

**Purpose:** generate the audio for Scam Fire Drills (Phase 3).

| Item | Detail |
| --- | --- |
| Tool | [F5-TTS](https://github.com/SWivid/F5-TTS) |
| Where | Google Colab, T4 or better (`f5_tts_colab.ipynb`) |
| Output | `.wav` (24 kHz) → Supabase Storage → `drills.audio_asset_url` |
| Runtime | GPU. Not part of the deployed backend. |

Flow:

```
reference voice (10-20s, consented)
        + scam script (LLM-generated in Phase 3)
        -> F5-TTS (Colab)
        -> drill_audio.wav
        -> Supabase Storage
        -> frontend <audio> during drill run
```

> **Ethics:** voice samples are for drills run by the consenting owner only.
> Never clone a voice to deceive a third party.

## 2. Deepfake / voice detection — `deepfake_detection/`

**Purpose:** Phase 6 — decide whether a live caller is the person they claim to be,
and flag AI-synthesized speech.

| Item | Detail |
| --- | --- |
| Tool | Resemblyzer (d-vector embeddings) |
| Where | Local, inside the backend (`app/clients/resemblyzer_client.py`) |
| Install | `cd backend && uv sync --group voice` — **Python 3.11/3.12 only** |
| Test | `uv run python ../ml/deepfake_detection/resemblyzer_test.py` |

Why optional: `resemblyzer` depends on `webrtcvad`, which has no wheels for
Python 3.13 on Windows. The backend lazy-imports it and disables voice features
gracefully, so this never blocks anything else.

```python
from app.clients import resemblyzer_client as rc

if rc.is_available():
    score = rc.similarity(rc.embed_wav("a.wav"), rc.embed_wav("b.wav"))
```

`similarity()` returns cosine similarity in `[-1, 1]`. Above ~0.75 is the same
speaker; tune the threshold on your own recorded corpus before trusting it.

## Pipeline map

| Phase | Needs | Status |
| --- | --- | --- |
| 0 | repo scaffold | done |
| 2 | bot text/photo intake | stubs in `bot/handlers/` |
| 3 | F5-TTS Colab | notebook ready |
| 4 | live call transcription | Groq Whisper client ready (`backend/scripts/smoke_whisper.py`) |
| 6 | voice deepfake detection | Resemblyzer client + test ready |
