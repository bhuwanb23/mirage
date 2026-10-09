# Phase 3 — Scam Fire Drill Simulator (Complete Deep Dive)

---

## Architecture Overview

```
User arrives at /drill
       │
       ▼
┌──────────────────────────────────────────────────┐
│           STEP 1: PROFILE INPUT (3.1)            │
│                                                  │
│  Upload voice clip ──┐                           │
│  Enter name          │                           │
│  Enter city          ├──→ User Profile JSON       │
│  Enter bank          │                           │
│  Enter employer ─────┘                           │
└──────────────────────┬───────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────┐
│         STEP 2: CHOOSE SCAM TYPE (3.2)           │
│                                                  │
│  ○ Bank KYC Fraud                                │
│  ○ FedEx / Customs Parcel                        │
│  ○ Relative in Distress                          │
│  ○ RBI / Police Impersonation                    │
│  ○ Job Offer / Work-from-Home                    │
│                                                  │
│  [Start Fire Drill]                              │
└──────────────────────┬───────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────┐
│      STEP 3: SCRIPT + VOICE GENERATION (3.2+3.3) │
│                                                  │
│  LLM generates personalized scam script          │
│       │                                          │
│       ▼                                          │
│  Voice cloning synthesizes script as audio       │
│       │                                          │
│       ▼                                          │
│  Audio file ready (or pre-generated for demo)    │
└──────────────────────┬───────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────┐
│         STEP 4: DRILL DELIVERY (3.4)             │
│                                                  │
│  ┌────────────────────────────────────┐          │
│  │  📞 Incoming Call: "Unknown"       │          │
│  │                                    │          │
│  │  ▶️ ━━━━━━━━━●━━━━━━━━ 0:18/0:45   │          │
│  │                                    │          │
│  │  [🚨 This is a Scam]  [✅ Real]    │          │
│  │                                    │          │
│  │  Timer: 18 seconds                 │          │
│  └────────────────────────────────────┘          │
└──────────────────────┬───────────────────────────┘
                       │ user clicks a button
                       ▼
┌──────────────────────────────────────────────────┐
│         STEP 5: DEBRIEF (3.5)                    │
│                                                  │
│  "You caught it in 18 seconds! 🎉"               │
│                                                  │
│  ✅ You spotted: Hook, Authority, Urgency        │
│  ❌ You missed: Isolation ("don't tell family")  │
│                                                  │
│  "At 0:18, the caller said 'don't tell your      │
│   wife about this call.' This is the isolation   │
│   tactic — scammers prevent you from getting a   │
│   second opinion."                               │
└──────────────────────┬───────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────┐
│      STEP 6: RESILIENCE SCORE UPDATE (3.6)       │
│                                                  │
│  Score: 42 → 67 (+25) 📈                        │
│                                                  │
│  ┌────────────────────────────────────┐          │
│  │  100│         ╱                    │          │
│  │   75│      ╱──●                    │          │
│  │   50│   ╱──                        │          │
│  │   25│──●                           │          │
│  │    0│──────────────────            │          │
│  │     Drill 1   Drill 2   Drill 3   │          │
│  └────────────────────────────────────┘          │
└──────────────────────────────────────────────────┘
```

---

## 3.1 · Public Footprint Scraper

### File Location
`backend/app/services/footprint_scraper.py`

### What It Does
Collects personal details about the user that a real scammer would use to personalize their attack. In production, this would scrape public profiles. For the hackathon demo, the user enters their details manually via a form.

### Demo Approach (Manual Input)

**Why manual for the demo:**
- Instagram and LinkedIn have aggressive anti-scraping measures
- Building a reliable scraper takes 4–6 hours you don't have
- Judges care about the *output* (the personalized scam), not how you got the input
- Manual input is actually *better* for the demo because you control the data and avoid scraping failures

**The form on the `/drill` page collects:**

| Field | Type | Required | Example | Why a scammer needs it |
|-------|------|----------|---------|----------------------|
| Full Name | text | Yes | "Priya Sharma" | To address you by name (hook) |
| City | text | Yes | "Mumbai" | To reference local branches, police stations |
| Bank Name | dropdown | Yes | "SBI" | To impersonate your specific bank |
| Employer | text | No | "TCS" | To reference your workplace in the scam |
| Relative's Name | text | No | "Rahul" (brother) | For relative-in-distress scams |
| Voice Clip | audio file | Yes (for voice cloning) | 10-second .wav/.mp3 | To clone your voice or a relative's voice |

### Data Structure

```
UserProfile:
  name: str                    # "Priya Sharma"
  first_name: str              # "Priya" (extracted from full name)
  city: str                    # "Mumbai"
  bank: str                    # "SBI"
  bank_full_name: str          # "State Bank of India" (mapped from code)
  employer: str or null        # "TCS"
  relative_name: str or null   # "Rahul"
  relative_relation: str or null # "brother"
  voice_clip_url: str or null  # URL to uploaded voice file
  voice_clip_path: str or null # Local path for processing
```

### Bank Name Mapping

Map short names to full names for more realistic scam scripts:

| Short | Full Name | Official Domain | Toll-Free |
|-------|-----------|----------------|-----------|
| SBI | State Bank of India | sbi.co.in | 1800-11-2211 |
| HDFC | HDFC Bank | hdfcbank.com | 1800-202-6161 |
| ICICI | ICICI Bank | icicibank.com | 1800-1080 |
| Axis | Axis Bank | axisbank.com | 1860-419-5555 |
| Kotak | Kotak Mahindra Bank | kotak.com | 1860-266-2666 |
| PNB | Punjab National Bank | pnbindia.in | 1800-180-2222 |
| BOB | Bank of Baroda | bankofbaroda.in | 1800-258-4455 |
| Yes | Yes Bank | yesbank.in | 1800-1200 |
| Canara | Canara Bank | canarabank.com | 1800-425-0018 |
| IDBI | IDBI Bank | idbibank.in | 1800-200-1947 |

### Voice Clip Handling

**Upload flow:**
1. User uploads a 10–30 second audio clip via the Next.js form
2. Frontend sends it as `multipart/form-data` to `POST /drill/upload-voice`
3. Backend validates:
   - Format: `.wav`, `.mp3`, `.m4a`, `.ogg`
   - Duration: 5–60 seconds (use `pydub` to check)
   - Size: < 5 MB
4. Backend saves to Supabase Storage bucket `voice-clips` with path `{user_id}/{timestamp}.wav`
5. Returns the storage URL

**For the demo (simpler approach):**
- Skip Supabase Storage
- Save the file locally to `/tmp/mirage_voice_{user_id}.wav`
- Pass the local path to the voice cloning pipeline
- This is fine for a live demo on a single machine

### Stretch Goal: Real Scraping (if you have extra time)

**Instagram scraper (BeautifulSoup + requests):**
- Fetch `https://www.instagram.com/{handle}/` (will likely be blocked by login wall)
- Alternative: use the public embed endpoint `https://www.instagram.com/{handle}/?__a=1&__d=dis` (unreliable)
- Extract from bio: name, city, employer, links
- **Reality check:** Instagram blocks almost all scraping. Don't waste time on this for the hackathon.

**LinkedIn scraper:**
- Similar issues — login wall, anti-bot detection
- **Don't attempt for the hackathon.**

**Better stretch goal:** If you want to show "scraping" in the demo, pre-prepare a JSON file that *looks like* scraped data and show it loading with a fake progress bar. Judges won't verify the scraping — they'll care about the personalization result.

### API Endpoint

**`POST /drill/profile`**

Request body (JSON):
```json
{
  "name": "Priya Sharma",
  "city": "Mumbai",
  "bank": "SBI",
  "employer": "TCS",
  "relative_name": "Rahul",
  "relative_relation": "brother"
}
```

Response:
```json
{
  "profile_id": "uuid-here",
  "status": "saved",
  "message": "Profile saved. Upload a voice clip to continue."
}
```

**`POST /drill/upload-voice`**

Request: `multipart/form-data` with `file` field and `profile_id` field

Response:
```json
{
  "voice_clip_url": "/tmp/mirage_voice_123.wav",
  "duration_seconds": 12.5,
  "status": "ready"
}
```

### Edge Cases

| Edge Case | Behavior |
|-----------|----------|
| User doesn't provide a bank | Default to "SBI" (most common Indian bank, most common scam target) |
| User doesn't provide a city | Default to "Mumbai" |
| User provides a voice clip shorter than 5 seconds | Reply: "Voice clip too short. Please record at least 5 seconds of clear speech." |
| Voice clip has heavy background noise | Proceed anyway — the voice cloning will still work, just with lower quality. Add a note: "Voice quality is low — cloned audio may sound distorted." |
| User skips voice clip entirely | Use Edge-TTS with a generic Indian English voice as fallback. The drill still works, just without the personalized voice clone. |

---

## 3.2 · Scam Script Generator

### File Location
`backend/app/services/script_generator.py`

### What It Does
Takes the user's profile and a chosen scam type, then uses Groq Llama 3.3 to generate a realistic, personalized scam call script that includes all 5 stages of a scam (hook → authority → isolation → urgency → payment).

### System Prompt (exact — this is the most critical prompt in the entire project)

```
You are a scam script generator for Mirage, an anti-scam training platform. Your job is to generate REALISTIC scam call scripts that are used to TRAIN people to recognize scams.

CRITICAL CONTEXT: These scripts are used in a controlled educational environment. The user has CONSENTED to receiving a simulated scam. The script will be played to the user, and they will be asked to identify it as a scam. Afterward, they receive a detailed debrief explaining every tactic used.

RULES FOR SCRIPT GENERATION:

1. The script must be a PHONE CALL monologue (one side — the scammer speaking). Include natural pauses marked as [pause 2s], [pause 1s], etc.

2. The script MUST include ALL 5 stages in order. Mark each stage transition with a tag:
   [STAGE: HOOK] — Initial contact, grab attention
   [STAGE: AUTHORITY] — Impersonate an institution
   [STAGE: ISOLATION] — Prevent the victim from seeking help
   [STAGE: URGENCY] — Create time pressure
   [STAGE: PAYMENT] — Demand money or sensitive info

3. The script must be PERSONALIZED using the provided profile data. Use the person's real name, city, bank, and employer naturally in the conversation.

4. The script must sound NATURAL and CONVERSATIONAL. Real scammers don't sound robotic. Include filler words ("uh", "you know", "basically"), false empathy ("I understand this is stressful, madam"), and professional-sounding language.

5. The script should be 45–90 seconds long when spoken aloud (roughly 120–250 words).

6. Include specific, realistic details:
   - Fake reference numbers (e.g., "Case number KYC-2025-8834")
   - Fake officer names (e.g., "This is Officer Rajesh from the fraud department")
   - Specific amounts (e.g., "₹49,999 will be deducted")
   - Specific deadlines (e.g., "within the next 30 minutes")

7. DO NOT include any real bank phone numbers, real URLs, or real UPI IDs. Use obviously fake ones:
   - Phone: 98765-XXXXX
   - UPI: scammer-demo@ybl
   - URL: fake-bank-verify.xyz

OUTPUT FORMAT — respond ONLY with valid JSON:
{
  "scam_type": "bank_kyc",
  "title": "Fake SBI KYC Verification Call",
  "stages": {
    "hook": {
      "timestamp_hint": "0:00-0:08",
      "script": "Hello, am I speaking with Priya Sharma? ...",
      "tactic": "Uses your full name to establish familiarity"
    },
    "authority": {
      "timestamp_hint": "0:08-0:20",
      "script": "This is Officer Rajesh from the State Bank of India fraud department in Mumbai. ...",
      "tactic": "Impersonates a specific bank officer with a fake badge number"
    },
    "isolation": {
      "timestamp_hint": "0:20-0:30",
      "script": "Now Priya ji, this is a confidential matter. Please do not discuss this with anyone, not even your family members. ...",
      "tactic": "Prevents the victim from getting a second opinion"
    },
    "urgency": {
      "timestamp_hint": "0:30-0:45",
      "script": "Your account will be permanently frozen in the next 30 minutes if KYC is not verified. ...",
      "tactic": "Creates extreme time pressure to prevent rational thinking"
    },
    "payment": {
      "timestamp_hint": "0:45-1:00",
      "script": "To verify, I need you to share the OTP you just received on your phone. Also, your ATM PIN for verification. ...",
      "tactic": "Demands OTP and PIN — no real bank ever asks for these"
    }
  },
  "full_script": "The complete script as a single continuous text for voice synthesis, with [pause] markers",
  "red_flags_planted": [
    "Used full name to create false familiarity",
    "Claimed to be from SBI fraud department (SBI doesn't have a 'fraud department' that calls customers)",
    "Asked to keep the call secret from family",
    "Threatened account freeze within 30 minutes",
    "Asked for OTP and ATM PIN over the phone"
  ],
  "difficulty_level": "medium"
}
```

### User Prompt Template

```
Generate a scam call script with the following parameters:

SCAM TYPE: {scam_type}
TARGET PROFILE:
- Name: {name}
- City: {city}
- Bank: {bank_full_name}
- Employer: {employer or "not specified"}
- Relative: {relative_name} ({relative_relation}) or "not specified"

DIFFICULTY: {easy | medium | hard}
- Easy: Obvious red flags, over-the-top urgency, bad grammar
- Medium: Realistic, most people would fall for it
- Hard: Very sophisticated, mimics real bank communication closely, only subtle red flags

Make it sound like a real phone call. The scammer should sound professional and convincing.
```

### Scam Type Templates (pre-built scenarios)

Each scam type has a specific narrative structure. The LLM fills in the personalized details.

**1. Bank KYC Fraud**
- Narrative: "Your KYC is incomplete, account will be blocked"
- Key personalization: bank name, city branch
- Payment ask: OTP + ATM PIN + account number
- Difficulty range: easy to hard

**2. FedEx / Customs Parcel**
- Narrative: "A parcel in your name contains illegal items / unpaid customs duty"
- Key personalization: name, city
- Payment ask: "Pay ₹2,499 customs fee via UPI"
- Difficulty range: medium

**3. Relative in Distress**
- Narrative: "{relative_name} has met with an accident / is in police custody"
- Key personalization: relative's name, relationship, city
- Payment ask: "Send ₹50,000 to this UPI immediately"
- Difficulty range: hard (emotionally manipulative)
- Special: This is where voice cloning of the relative's voice is most impactful

**4. RBI / Police Impersonation**
- Narrative: "Your PAN/Aadhaar is linked to money laundering / illegal transactions"
- Key personalization: name, city, employer (to make the "investigation" specific)
- Payment ask: "Transfer ₹2,00,000 to a 'safe RBI account' for verification"
- Difficulty range: hard (uses legal threats)

**5. Job Offer / Work-from-Home**
- Narrative: "You've been selected for a high-paying remote job at {employer's competitor}"
- Key personalization: employer (to make the offer relevant), city
- Payment ask: "Pay ₹999 registration fee"
- Difficulty range: easy to medium

### API Endpoint

**`POST /drill/generate-script`**

Request:
```json
{
  "profile_id": "uuid-here",
  "scam_type": "bank_kyc",
  "difficulty": "medium"
}
```

Response:
```json
{
  "script_id": "uuid-here",
  "scam_type": "bank_kyc",
  "title": "Fake SBI KYC Verification Call",
  "full_script": "Hello, am I speaking with Priya Sharma? [pause 2s] Great. Priya ji, my name is Rajesh, I'm calling from the State Bank of India fraud department at our Mumbai regional office. [pause 1s] ...",
  "stages": { ... },
  "red_flags_planted": [ ... ],
  "difficulty_level": "medium",
  "estimated_duration_seconds": 55
}
```

### Groq Call Parameters

- Model: `llama-3.3-70b-versatile`
- Temperature: `0.7` (higher than the analyzer — you want creative, varied scripts)
- Max tokens: `1500`
- Response format: `{"type": "json_object"}`

### Edge Cases

| Edge Case | Behavior |
|-----------|----------|
| LLM generates a script that's too short (< 80 words) | Retry with prompt: "Make the script longer — at least 150 words. Add more detail to the authority and urgency stages." |
| LLM generates a script that's too long (> 300 words) | Truncate to 250 words at the nearest sentence boundary. The urgency and payment stages must be preserved. |
| LLM includes a real bank phone number | Post-process the script with regex to replace any 1800-xxx-xxxx or 10-digit numbers with fake ones (98765-XXXXX) |
| LLM includes real URLs | Replace any URLs with `fake-bank-verify.xyz` |
| User selects "Relative in Distress" but didn't provide a relative's name | Default to "your brother" or "your son" |
| LLM output is not valid JSON | Retry once. If still invalid, fall back to a pre-written template script with the user's name and bank inserted via string replacement |

### Pre-Written Fallback Templates (if LLM fails)

Have 5 pre-written scripts (one per scam type) with `{name}`, `{city}`, `{bank}` placeholders. If the LLM call fails or returns garbage, do a simple string replace and use the template. This ensures the demo NEVER breaks.

**Example fallback for Bank KYC:**
```
Hello, am I speaking with {name}? [pause 2s] This is Officer Kumar from the {bank} fraud department in {city}. [pause 1s] I'm calling because your KYC verification is incomplete and your account will be blocked within 30 minutes. [pause 1s] Please do not tell anyone about this call as it is a confidential security matter. [pause 1s] To verify your identity, I need you to share the OTP you will receive on your phone and your ATM PIN. [pause 1s] If you don't do this in the next 15 minutes, your account will be permanently frozen and your balance of ₹2,45,000 will be held.
```

---

## 3.3 · Voice Cloning Pipeline

### File Location
`ml/voice_cloning/f5_tts_colab.ipynb` (Colab) + `backend/app/services/voice_synthesizer.py` (backend integration)

### What It Does
Takes the generated scam script and a reference voice clip, then synthesizes the script as audio using the cloned voice. This is what makes the Fire Drill feel real — the scam call sounds like someone the user knows.

### Two Approaches (choose based on time)

---

#### APPROACH A: Real Voice Cloning via F5-TTS on Colab (recommended for demo)

**Setup (do this BEFORE the hackathon, takes ~30 minutes):**

1. Open Google Colab → New Notebook → Change runtime to T4 GPU
2. Install F5-TTS:
   ```
   !pip install f5-tts
   !pip install gradio
   ```
3. Upload a 10-second reference voice clip (your own voice or a teammate's)
4. Test the cloning with a sample sentence: "Hello, this is a test of the voice cloning system."
5. Verify the output sounds convincing

**During the hackathon (generation flow):**

**Step 1: Prepare the script for TTS**
- Take the `full_script` from the script generator (3.2)
- Remove all stage tags (`[STAGE: HOOK]`, etc.)
- Convert pause markers to actual silence:
  - `[pause 1s]` → insert 1 second of silence in the audio
  - `[pause 2s]` → insert 2 seconds of silence
- Remove any other non-speech markers
- The result is a clean text string ready for TTS

**Step 2: Generate audio via Colab**

**Option 1: Manual (simplest for demo)**
- Copy the script text into the Colab notebook
- Run the F5-TTS cell with the reference voice
- Download the output `.wav` file
- Upload it to the backend via `POST /drill/upload-audio`
- This takes ~60 seconds per generation

**Option 2: API via ngrok (more automated)**
- In the Colab notebook, wrap F5-TTS in a simple Flask/FastAPI server
- Expose it via ngrok: `!ngrok http 5000`
- The backend calls this ngrok URL to generate audio on demand
- This is more complex but allows the demo to be fully automated
- **Risk:** ngrok URLs change if the Colab disconnects. Have a backup plan.

**F5-TTS Colab Notebook Structure:**

```
Cell 1: Install dependencies
Cell 2: Import F5-TTS, load model
Cell 3: Upload reference voice (file picker)
Cell 4: Define the synthesis function
Cell 5: Input script text → Generate audio → Play preview → Download
Cell 6 (optional): Flask server + ngrok for API access
```

**F5-TTS Parameters:**
- Reference audio: 10-second clip, 16kHz, mono
- Target text: the scam script (up to 250 words)
- Output: `.wav` file, 16kHz
- Generation time: ~20–40 seconds on T4 GPU for a 60-second clip

---

#### APPROACH B: Edge-TTS Fallback (if voice cloning fails or you run out of time)

**When to use:**
- Colab GPU is unavailable
- F5-TTS produces poor quality
- You need to generate audio in < 5 seconds
- The voice clone doesn't sound convincing enough

**How it works:**
- Use Edge-TTS with an Indian English voice
- It won't sound like the user's relative, but it will sound like a realistic Indian caller
- Voices to use:
  - Male scammer: `en-IN-PrabhatNeural` (deep, authoritative)
  - Female scammer: `en-IN-NeerjaNeural` (professional)
  - Hindi scammer: `hi-IN-MadhurNeural` (male) or `hi-IN-SwaraNeural` (female)

**Edge-TTS Parameters:**
- Rate: `-5%` (slightly slower than normal — scammers speak deliberately)
- Pitch: `-10%` (slightly lower — sounds more authoritative)
- Volume: `+0%` (normal)

**For the demo:** Pre-generate 3–5 scam audios using Edge-TTS with different scripts. Store them as static files. When the user starts a drill, play the pre-generated audio that matches their scam type. Insert their name via a quick text splice or just use a generic greeting.

---

### Demo Strategy (critical for hackathon success)

**The safest demo approach:**

1. **Before the presentation:** Generate 3 cloned-voice scam audios using F5-TTS on Colab:
   - One Bank KYC scam (using teammate A's voice as the "relative")
   - One Relative in Distress scam (using teammate B's voice)
   - One RBI Impersonation scam (using Edge-TTS as the "official")
2. **Store these** as static files in `frontend/public/audio/`
3. **During the demo:** When the judge selects a scam type, play the corresponding pre-generated audio. The personalization (name, city, bank) is already baked into the script.
4. **If you want to show real-time generation:** Have the Colab notebook open on a second screen, generate a new audio live, and play it. This is impressive but risky — only attempt if you've rehearsed it 3+ times.

### Audio Post-Processing

After generation, apply these effects to make the audio sound like a real phone call:

1. **Band-pass filter:** Limit frequencies to 300Hz–3400Hz (telephone bandwidth). This makes it sound like a real phone call instead of studio-quality audio. Use `pydub` or `scipy.signal`.
2. **Add phone ring tone:** Prepend 2 seconds of Indian phone ring tone before the scammer starts speaking. This makes the drill feel like an actual incoming call.
3. **Add slight static/noise:** Mix in a very low level of white noise (-30dB) to simulate phone line quality.
4. **Normalize volume:** Ensure consistent loudness across all generated audios.

**pydub pipeline:**
```
raw_audio → band_pass(300, 3400) → add_ring_tone(2s) → add_noise(-30dB) → normalize → export .mp3
```

### API Endpoint

**`POST /drill/synthesize-voice`**

Request:
```json
{
  "script_id": "uuid-here",
  "voice_clip_url": "/tmp/mirage_voice_123.wav",
  "method": "f5tts"  // or "edge-tts"
}
```

Response:
```json
{
  "audio_url": "/api/drill/audio/uuid-here.mp3",
  "duration_seconds": 52,
  "method_used": "f5tts",
  "status": "ready"
}
```

### Edge Cases

| Edge Case | Behavior |
|-----------|----------|
| Voice clip is too short for F5-TTS (< 5 seconds) | Fall back to Edge-TTS. Notify user: "Voice clip too short for cloning. Using a generic voice instead." |
| F5-TTS generation takes too long (> 60 seconds) | Timeout and fall back to Edge-TTS. Show a loading spinner during generation. |
| Generated audio sounds robotic or unnatural | This is actually FINE for the demo — it reinforces the "this is AI-generated" lesson. In the debrief, point out: "Notice how the voice sounded slightly unnatural? That's a clue." |
| Colab disconnects during demo | Have Edge-TTS pre-generated audios ready as backup. Switch seamlessly. |
| Audio file is too large for the frontend (> 5 MB) | Compress to 128kbps MP3. A 60-second clip at 128kbps is ~1 MB. |

---

## 3.4 · Drill Delivery UI

### File Location
`frontend/app/drill/page.tsx` + `frontend/components/DrillPlayer.tsx`

### What It Does
The web page where the user experiences the simulated scam call. It plays the cloned audio, lets the user react in real time, and tracks their response time.

### Page Flow (4 screens)

---

**Screen 1: Setup (before drill starts)**

```
┌─────────────────────────────────────────────┐
│                                             │
│   🔥 SCAM FIRE DRILL                        │
│                                             │
│   We're about to simulate a real scam call  │
│   targeting YOU, using your real details.   │
│                                             │
│   Your job: Listen carefully and click      │
│   "This is a Scam" the moment you're sure.  │
│                                             │
│   ⏱️ A timer will track how fast you react.  │
│                                             │
│   Scam Type: Bank KYC Fraud                 │
│   Difficulty: Medium                        │
│   Estimated Duration: ~55 seconds           │
│                                             │
│   [🔥 Start Fire Drill]                     │
│                                             │
│   ⚠️ This is a simulation. No real scam     │
│   is being attempted. Your data is safe.    │
│                                             │
└─────────────────────────────────────────────┘
```

**Screen 2: Active Drill (audio playing)**

This is the most important screen. It should look like a phone call interface.

```
┌─────────────────────────────────────────────┐
│                                             │
│   📞 INCOMING CALL                          │
│                                             │
│   ┌─────────────────────────────────┐       │
│   │                                 │       │
│   │         👤                      │       │
│   │     Unknown Number              │       │
│   │     +91 98765-XXXXX             │       │
│   │                                 │       │
│   │   🔊 ━━━━━━━●━━━━━━━━ 0:18/0:55 │       │
│   │                                 │       │
│   │   ⏱️ Reaction Timer: 18s        │       │
│   │                                 │       │
│   └─────────────────────────────────┘       │
│                                             │
│   ┌───────────────┐ ┌───────────────┐       │
│   │  🚨 THIS IS   │ │  ✅ THIS      │       │
│   │  A SCAM       │ │  SEEMS REAL   │       │
│   └───────────────┘ └───────────────┘       │
│                                             │
│   💡 Hint: Listen for red flags in how      │
│   the caller identifies themselves and      │
│   what they're asking you to do.            │
│                                             │
└─────────────────────────────────────────────┘
```

**Screen 2 Behavior:**
- When user clicks "Start Fire Drill":
  1. Show a 3-second countdown: "3... 2... 1... 📞 Ringing..."
  2. Play the Indian phone ring tone for 2 seconds
  3. Start the scam audio
  4. Start the reaction timer (counts up from 0)
  5. The audio progress bar moves in real time
- The two buttons ("This is a Scam" / "This Seems Real") are always visible
- The user can click at ANY point during the audio
- If the user clicks "This is a Scam":
  1. Pause the audio
  2. Record the reaction time
  3. Record the current audio position (which stage were they at?)
  4. Transition to Screen 3 (Debrief)
- If the user clicks "This Seems Real":
  1. Pause the audio
  2. Record that they fell for it
  3. Transition to Screen 3 with a different debrief tone
- If the audio finishes and the user hasn't clicked anything:
  1. Auto-transition to Screen 3
  2. Record: user did not identify the scam

**Screen 3: Debrief (see 3.5 for details)**

**Screen 4: Score Update (see 3.6 for details)**

### Technical Implementation Details

**Audio playback:**
- Use the HTML5 `<audio>` element or the `useAudio` hook from a library like `react-use`
- Load the audio file from the backend URL or static file path
- Track `currentTime` and `duration` for the progress bar
- Update the progress bar every 100ms using `requestAnimationFrame` or `setInterval`

**Timer:**
- Use `performance.now()` for accurate timing (not `Date.now()`)
- Start the timer when the scam audio begins (after the ring tone)
- Stop the timer when the user clicks a button or the audio ends
- Display in seconds with one decimal place: "18.3s"

**Stage tracking during playback:**
- The backend provides stage timestamps in the script: `hook: 0:00-0:08`, `authority: 0:08-0:20`, etc.
- As the audio plays, highlight which stage the caller is currently in
- Show a small label above the progress bar: "Current stage: Authority"
- This helps the user learn the stages in real time (optional — can be hidden for "hard" difficulty)

**Mobile responsiveness:**
- The drill page MUST work on mobile (judges might try it on their phones)
- Stack the buttons vertically on small screens
- Make the buttons large and easy to tap (min 48px height)
- Use `touch-action: manipulation` to prevent double-tap zoom on buttons

### Keyboard Shortcuts (for demo)

- `Space` → Start/Pause audio
- `S` → "This is a Scam"
- `R` → "This Seems Real"
- These make the live demo smoother when you're presenting

### Edge Cases

| Edge Case | Behavior |
|-----------|----------|
| User's browser blocks autoplay | Show a prominent "Click to Play" button. Browsers require user interaction before playing audio. The "Start Fire Drill" button counts as user interaction. |
| Audio fails to load | Show error: "Could not load the drill audio. Please try again." Offer a text-only version of the drill as fallback. |
| User clicks "This is a Scam" within the first 2 seconds | Flag as "too fast — likely a guess." In the debrief, note: "You flagged this very quickly. Were you guessing, or did you spot a specific red flag?" |
| User switches tabs during the drill | Pause the audio and timer. Resume when they return. Use the `visibilitychange` event. |
| User refreshes the page during the drill | The drill state is lost. Show: "Drill interrupted. Start a new drill?" Don't count it as a failed drill. |

---

## 3.5 · Debrief Engine

### File Location
`backend/app/services/debrief_engine.py`

### What It Does
After the drill ends, generates a personalized, educational debrief that explains exactly what happened, what the user got right, what they missed, and how to protect themselves in real life.

### Logic Flow

**Step 1: Collect drill results**

From the frontend, receive:
```json
{
  "script_id": "uuid",
  "user_action": "identified_scam" | "fell_for_it" | "no_response",
  "reaction_time_seconds": 18.3,
  "audio_position_at_click": 18.3,
  "stages_at_click": "authority"  // which stage was playing when they clicked
}
```

**Step 2: Determine what the user caught and missed**

Compare the audio position at click against the stage timestamps:

| Stage | Timestamp Range | User clicked at 18.3s | Caught? |
|-------|----------------|----------------------|---------|
| Hook | 0:00–0:08 | 18.3s > 0:08 | ✅ Yes (they heard it and continued listening) |
| Authority | 0:08–0:20 | 18.3s is within this range | ✅ Yes (they caught it during this stage) |
| Isolation | 0:20–0:30 | 18.3s < 0:20 | ❌ Not yet reached |
| Urgency | 0:30–0:45 | 18.3s < 0:30 | ❌ Not yet reached |
| Payment | 0:45–1:00 | 18.3s < 0:45 | ❌ Not yet reached |

**Interpretation:**
- Stages BEFORE the click point = stages the user heard and (presumably) recognized as suspicious
- The stage AT the click point = the stage that triggered their "aha" moment
- Stages AFTER the click point = stages they didn't hear (but would have encountered in a real scam)

**Special cases:**
- If user clicked "This Seems Real" → they missed ALL stages. Debrief should be more detailed and educational.
- If user didn't click at all → same as "fell for it."
- If user clicked within the first 5 seconds → they caught it at the Hook stage. Impressive, but note that real scams often start subtly.

**Step 3: Generate the debrief via LLM**

**System Prompt:**

```
You are the Mirage Debrief Engine. Your job is to provide a warm, educational, and specific debrief after a user completes a scam fire drill.

RULES:
1. Be encouraging, not condescending. If the user fell for it, normalize it: "70% of people fall for this type of scam."
2. Be SPECIFIC. Reference exact moments in the script by timestamp. Don't give generic advice.
3. Explain the PSYCHOLOGY behind each tactic. Why does it work? What emotion does it exploit?
4. Give ACTIONABLE real-world advice. What should they do if they encounter this in real life?
5. Keep the debrief under 300 words. People won't read a wall of text.

OUTPUT FORMAT — valid JSON only:
{
  "outcome": "success" | "partial" | "failed",
  "headline": "One-line summary of how they did",
  "reaction_assessment": "Assessment of their reaction time",
  "stages_caught": [
    {
      "stage": "hook",
      "timestamp": "0:00-0:08",
      "what_happened": "The caller used your full name 'Priya Sharma' to create instant familiarity.",
      "why_it_works": "Hearing your name from a stranger triggers a compliance reflex — you assume they know you.",
      "real_world_tip": "Real bank callers will verify YOUR identity first, not just announce your name."
    }
  ],
  "stages_missed": [
    {
      "stage": "isolation",
      "timestamp": "0:20-0:30",
      "what_happened": "The caller said 'don't tell your family about this call.'",
      "why_it_works": "Isolation prevents you from getting a second opinion from someone who might recognize the scam.",
      "real_world_tip": "If anyone tells you to keep a financial call secret, hang up immediately. That is the #1 scam indicator."
    }
  ],
  "key_lesson": "The single most important takeaway from this drill",
  "real_world_action": "What to do if this happens for real",
  "encouragement": "A positive closing note"
}
```

**User Prompt:**

```
DRILL RESULTS:
- Scam Type: {scam_type}
- User Action: {user_action}
- Reaction Time: {reaction_time}s
- Stages Heard Before Click: {stages_before}
- Stage at Click: {stage_at_click}
- Stages Not Heard: {stages_after}

SCRIPT DETAILS:
{full script with stage markers and tactics}

USER PROFILE (for personalization):
- Name: {name}
- Bank: {bank}
- City: {city}

Generate the debrief.
```

### Debrief UI (Screen 3)

**If user caught the scam (success):**

```
┌─────────────────────────────────────────────┐
│                                             │
│   🎉 GREAT JOB! You caught the scam!        │
│                                             │
│   ⏱️ Reaction Time: 18.3 seconds            │
│   🎯 You spotted it during: Authority stage │
│                                             │
│   ✅ What you caught:                       │
│   • Hook (0:00): Caller used your full name │
│     "Priya Sharma" to create familiarity    │
│   • Authority (0:08): Claimed to be from    │
│     "SBI fraud department" — SBI doesn't    │
│     have a fraud department that calls      │
│                                             │
│   ❌ What you would have heard next:        │
│   • Isolation (0:20): "Don't tell your      │
│     family" — the #1 scam red flag          │
│   • Urgency (0:30): "30 minutes or your     │
│     account is frozen"                      │
│   • Payment (0:45): Asked for OTP and PIN   │
│                                             │
│   💡 Key Lesson:                            │
│   No real bank will EVER ask for your OTP   │
│   or ATM PIN over the phone. If anyone      │
│   does, hang up and call 1800-11-2211.      │
│                                             │
│   [Continue to Score →]                     │
│                                             │
└─────────────────────────────────────────────┘
```

**If user fell for it (failed):**

```
┌─────────────────────────────────────────────┐
│                                             │
│   😟 This was a scam — and it's okay!       │
│                                             │
│   72% of people fall for this type of scam  │
│   on their first try. That's why we train.  │
│                                             │
│   Here's what the scammer did to you:       │
│                                             │
│   1️⃣ HOOK (0:00): Used your name "Priya"   │
│      to make you trust them instantly        │
│                                             │
│   2️⃣ AUTHORITY (0:08): Claimed to be from  │
│      "SBI fraud department" with a fake     │
│      badge number. Sounds official, right?   │
│                                             │
│   3️⃣ ISOLATION (0:20): Said "don't tell    │
│      your family." This prevents you from   │
│      getting a second opinion.              │
│                                             │
│   4️⃣ URGENCY (0:30): "30 minutes or your   │
│      account is frozen." Panic makes you    │
│      stop thinking critically.              │
│                                             │
│   5️⃣ PAYMENT (0:45): Asked for your OTP    │
│      and ATM PIN. THIS is the kill shot.    │
│      No bank EVER asks for these.           │
│                                             │
│   💡 Key Lesson:                            │
│   If a caller creates urgency AND asks for  │
│   secrets (OTP, PIN, password), it is       │
│   ALWAYS a scam. Hang up. Call your bank    │
│   on the number on your debit card.         │
│                                             │
│   [Try Again →]  [Continue to Score →]      │
│                                             │
└─────────────────────────────────────────────┘
```

### Groq Call Parameters

- Model: `llama-3.3-70b-versatile`
- Temperature: `0.5` (balanced — creative but consistent)
- Max tokens: `1000`
- Response format: `{"type": "json_object"}`

### Edge Cases

| Edge Case | Behavior |
|-----------|----------|
| User caught the scam in < 3 seconds | Debrief: "Incredibly fast! You likely spotted the hook immediately. In real life, scammers often start more subtly. Try the 'Hard' difficulty next." |
| User caught the scam at the very last stage (payment) | Debrief: "You caught it just in time! The payment demand is the final stage — in a real scam, this is when money leaves your account. Try to spot the earlier warning signs next time." |
| User fell for it on their 3rd+ attempt | Debrief: "This is a tough one. Let's break down exactly why it's so convincing..." Provide extra detail. |
| LLM generates a generic debrief | Post-process: if the debrief doesn't contain the user's name or bank name, inject them manually. |

---

## 3.6 · Scam Resilience Score

### File Location
`backend/app/services/resilience_score.py` + `frontend/components/ScoreCard.tsx` + `frontend/components/ScoreChart.tsx`

### What It Does
Calculates and tracks a 0–100 score that represents the user's ability to identify scams. The score improves with each successful drill and decays slightly over time (like a fitness tracker).

### Scoring Algorithm

**Base score calculation for a single drill:**

| Factor | Points | Logic |
|--------|--------|-------|
| **Detection** | +30 | User identified the scam (clicked "This is a Scam") |
| **Speed bonus** | +0 to +20 | Based on reaction time (see table below) |
| **Stage bonus** | +5 per stage | For each stage the user heard and correctly identified (max +25 for all 5 stages) |
| **Difficulty bonus** | +5 | If difficulty was "hard" |
| **Difficulty bonus** | +2 | If difficulty was "medium" |
| **Penalty: fell for it** | -10 | User clicked "This Seems Real" |
| **Penalty: no response** | -5 | User didn't click anything |
| **Penalty: too fast** | -5 | User clicked in < 2 seconds (likely guessing) |

**Speed bonus table:**

| Reaction Time | Bonus |
|--------------|-------|
| < 5 seconds | +20 (but check for guessing penalty) |
| 5–10 seconds | +18 |
| 10–15 seconds | +15 |
| 15–20 seconds | +12 |
| 20–30 seconds | +8 |
| 30–45 seconds | +5 |
| 45–60 seconds | +2 |
| > 60 seconds | +0 |

**Single drill score formula:**
```
drill_score = detection_points + speed_bonus + stage_bonus + difficulty_bonus + penalties
drill_score = clamp(drill_score, 0, 80)  // single drill max is 80
```

**Cumulative Resilience Score:**

The overall score is a **weighted moving average** of all drill scores, with recent drills weighted more heavily:

```
resilience_score = (drill_n * 0.4) + (drill_n-1 * 0.3) + (drill_n-2 * 0.2) + (older_average * 0.1)
```

**For the first drill:**
```
resilience_score = drill_score  // no history to average
```

**For the second drill:**
```
resilience_score = (drill_2 * 0.6) + (drill_1 * 0.4)
```

**Time decay (optional, for realism):**
- If the user hasn't done a drill in 7+ days, reduce the score by 2 points per week of inactivity
- Minimum score: 0 (never goes negative)
- This simulates "skill decay" — like a fitness tracker showing your streak breaking

### Score Ranges and Labels

| Score | Label | Color | Emoji |
|-------|-------|-------|-------|
| 0–20 | Beginner | Red | 🟥 |
| 21–40 | Vulnerable | Orange | 🟧 |
| 41–60 | Cautious | Yellow | 🟨 |
| 61–80 | Resilient | Green | 🟩 |
| 81–100 | Scam-Proof | Blue | 🟦 |

### Database Storage

**Update the `drills` table** (from Phase 0) after each drill:
```sql
INSERT INTO drills (
  user_id, scam_type, script_text, audio_url,
  user_response, detection_time_seconds,
  stages_identified, stages_missed,
  score_before, score_after, debrief_text
) VALUES (
  'user-uuid', 'bank_kyc', 'script text...', '/audio/url.mp3',
  'identified_scam', 18.3,
  ARRAY['hook', 'authority'], ARRAY['isolation', 'urgency', 'payment'],
  42, 67, 'debrief text...'
);
```

**Update the `users` table:**
```sql
UPDATE users SET resilience_score = 67, updated_at = now()
WHERE id = 'user-uuid';
```

### Score Display UI

**Score Card (on dashboard and after drill):**

```
┌─────────────────────────────────┐
│                                 │
│   SCAM RESILIENCE SCORE         │
│                                 │
│        ┌───────────┐            │
│        │           │            │
│        │    67     │            │
│        │  / 100    │            │
│        │           │            │
│        └───────────┘            │
│         🟩 Resilient            │
│                                 │
│   Previous: 42 → 67 (+25) 📈   │
│                                 │
│   Drills Completed: 3           │
│   Best Reaction: 8.2s           │
│   Weakest Scam Type: FedEx      │
│                                 │
└─────────────────────────────────┘
```

**Score Chart (on dashboard):**

Use Recharts `LineChart` or `AreaChart`:
- X-axis: Drill number (Drill 1, Drill 2, Drill 3, ...)
- Y-axis: Resilience Score (0–100)
- Line color: gradient from red (low) to green (high)
- Area fill: semi-transparent green
- Data points: clickable, show drill details on hover
- Reference line at y=50 labeled "Minimum Safe Level"

**Score Update Animation (after drill):**
- Show the old score → count up to the new score over 1.5 seconds
- Use a spring animation (Framer Motion `useSpring`)
- If score increased: green flash + "📈 +25 points!"
- If score decreased: red flash + "📉 -10 points. Try again!"
- If score unchanged: "Score unchanged. Keep practicing!"

### API Endpoint

**`GET /drill/score/{user_id}`**

Response:
```json
{
  "current_score": 67,
  "previous_score": 42,
  "change": 25,
  "label": "Resilient",
  "drills_completed": 3,
  "best_reaction_time": 8.2,
  "weakest_scam_type": "fedex",
  "history": [
    {"drill_number": 1, "score": 25, "scam_type": "lottery", "date": "2025-01-13"},
    {"drill_number": 2, "score": 42, "scam_type": "bank_kyc", "date": "2025-01-14"},
    {"drill_number": 3, "score": 67, "scam_type": "bank_kyc", "date": "2025-01-15"}
  ]
}
```

### Edge Cases

| Edge Case | Behavior |
|-----------|----------|
| First drill ever | Score = drill score. No history to average. Show: "Your baseline score is 42. Complete more drills to improve!" |
| User does 10 drills of the same type | Diminishing returns: after 3 drills of the same type, reduce the score gain by 50%. Encourage variety: "You've mastered Bank KYC scams! Try a FedEx scam next." |
| User's score is 100 | Cap at 100. Show: "🏆 You're Scam-Proof! But stay vigilant — scammers evolve." |
| User's score drops below previous | Show encouragement: "Scores fluctuate. The important thing is you're training." |
| User hasn't drilled in 30 days | Score decays to max 40. Show: "Your scam immunity is fading. Time for a refresher drill!" |

---

## Complete Drill Flow (End-to-End Sequence)

Here's the exact sequence of API calls and UI transitions during a full drill:

```
1. User visits /drill
   → Frontend loads the setup form

2. User fills in profile (name, city, bank, employer)
   → POST /drill/profile → returns profile_id

3. User uploads voice clip
   → POST /drill/upload-voice → returns voice_clip_url

4. User selects scam type and difficulty
   → User clicks "Start Fire Drill"

5. Frontend calls backend to generate script
   → POST /drill/generate-script {profile_id, scam_type, difficulty}
   → Returns script_id, full_script, stages, red_flags

6. Frontend calls backend to synthesize voice
   → POST /drill/synthesize-voice {script_id, voice_clip_url}
   → Returns audio_url
   → Show loading spinner: "Generating your personalized scam call..."
   → (For demo: skip this step, use pre-generated audio)

7. Audio is ready → Show Screen 2 (Active Drill)
   → Play ring tone (2s)
   → Play scam audio
   → Start timer

8. User clicks "This is a Scam" at 18.3 seconds
   → Pause audio
   → Record: action="identified_scam", time=18.3, stage="authority"

9. Frontend sends results to backend
   → POST /drill/respond {script_id, user_action, reaction_time, audio_position}
   → Backend calculates score, generates debrief
   → Returns: debrief, score_before, score_after, stages_caught, stages_missed

10. Show Screen 3 (Debrief)
    → Display personalized debrief text
    → Show stages caught/missed with timestamps

11. User clicks "Continue to Score"
    → Show Screen 4 (Score Update)
    → Animate score change: 42 → 67
    → Show chart with history

12. User clicks "Back to Dashboard"
    → Navigate to /dashboard
    → Dashboard shows updated score
```

---

## File Summary for Phase 3

| File | Purpose | Lines (estimate) |
|------|---------|-----------------|
| `backend/app/services/footprint_scraper.py` | Profile handling + bank mapping | ~80 |
| `backend/app/services/script_generator.py` | LLM scam script generation | ~150 |
| `backend/app/services/voice_synthesizer.py` | Voice cloning + Edge-TTS fallback | ~120 |
| `backend/app/services/debrief_engine.py` | LLM debrief generation | ~130 |
| `backend/app/services/resilience_score.py` | Score calculation algorithm | ~100 |
| `backend/app/routers/drill.py` | All drill API endpoints | ~150 |
| `ml/voice_cloning/f5_tts_colab.ipynb` | Colab voice cloning notebook | ~80 |
| `frontend/app/drill/page.tsx` | Drill page (4 screens) | ~300 |
| `frontend/components/DrillPlayer.tsx` | Audio player + timer + buttons | ~200 |
| `frontend/components/DrillSetup.tsx` | Profile form + scam type selector | ~150 |
| `frontend/components/DrillDebrief.tsx` | Debrief display | ~150 |
| `frontend/components/ScoreCard.tsx` | Score display card | ~80 |
| `frontend/components/ScoreChart.tsx` | Recharts score history | ~100 |
| `backend/app/services/fallback_scripts.py` | 5 pre-written template scripts | ~100 |

**Total estimated:** ~1,890 lines across Python + TypeScript

---

## Phase 3 Completion Checklist

```
□ Profile form collects name, city, bank, employer, relative, voice clip
□ Bank dropdown maps short names to full names
□ Voice clip upload validates format, duration, size
□ Script generator produces valid JSON for all 5 scam types
□ Script includes all 5 stages with tags and timestamp hints
□ Script is personalized with user's name, city, bank
□ Script includes realistic details (reference numbers, officer names, amounts)
□ Script does NOT contain real phone numbers, URLs, or UPI IDs
□ Fallback templates exist for all 5 scam types (if LLM fails)
□ Voice cloning produces audio from script + voice clip (F5-TTS or Edge-TTS)
□ Audio has phone-call quality (band-pass filter, ring tone)
□ Pre-generated demo audios exist for at least 2 scam types
□ Drill setup screen shows scam type, difficulty, estimated duration
□ Drill player shows phone-call UI with progress bar and timer
□ Drill player plays ring tone before scam audio
□ "This is a Scam" button records reaction time and audio position
□ "This Seems Real" button records that user fell for it
□ Timer stops when user clicks or audio ends
□ Debrief is generated with specific timestamps and tactics
□ Debrief explains the psychology behind each tactic
□ Debrief is encouraging for users who fell for it
□ Debrief shows stages caught and stages missed
□ Resilience score is calculated correctly
□ Score updates in the database after each drill
□ Score card shows current score, change, and label
□ Score chart shows history with Recharts
□ Score animation counts up/down smoothly
□ Full drill flow works end-to-end in < 2 minutes
□ Demo can be completed with pre-generated audios (no Colab dependency)
□ Mobile layout works for drill player
```

**When every box is checked, Phase 3 is done. This is your demo centerpiece — rehearse it at least 5 times before the presentation.**

---

Ready for Phase 4 (Live Call Guardian + Memory Handshake)? That's the other signature feature and the second "wow moment" in the demo. Say the word.