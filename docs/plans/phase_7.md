# Phase 7 — Demo Polish & Pitch (Complete Deep Dive)

---

## Overview

This is the most important phase. You can have the best code in the world, but if your demo crashes or your pitch is boring, you lose. This phase turns your working prototype into a **winning presentation**.

**Time allocation:** 4–6 hours, split across the last day of the hackathon.

**Golden rule:** A flawless 2-minute demo beats a broken 5-minute demo every time.

---

## 7.1 · Demo Script Rehearsal

### The 3-Minute Demo Script (Word-for-Word)

**Total time:** 180 seconds (3:00)
**Speaker:** Assign ONE person. No switching speakers mid-demo — it wastes time and breaks flow.
**Backup speaker:** Assign a second person who knows the script in case the primary gets sick.

---

**[0:00–0:20] THE HOOK (20 seconds)**

> "Last year, Indians lost over 7,000 crore rupees to cyber scams. That's not a typo — 7,000 crore. And 85% of victims are over 50 years old — people like our parents and grandparents.
>
> Every existing solution does the same thing: you paste a message, it says 'scam' or 'not scam.' That's like giving someone a fire extinguisher after their house has already burned down.
>
> We built something different. We built a **vaccine**."

**[What's on screen:]** Landing page. The hero section with the tagline "Your Personal AI Immune System Against Scams."

**[Demo operator:]** Have the landing page loaded and ready. No scrolling, no clicking — just the hero.

---

**[0:20–1:10] FIRE DRILL DEMO (50 seconds)**

> "This is Priya. She lives in Mumbai, banks with SBI, and works at TCS. These are her real details — the same details a scammer would find on LinkedIn in 30 seconds.
>
> We're going to attack Priya. Safely.
>
> I select 'Bank KYC Fraud' and click 'Start Fire Drill.'
>
> *(click)*
>
> Mirage generates a scam call script personalized to Priya — using her real name, her real bank, her real city — and synthesizes it using a cloned voice.
>
> *(audio plays for 8 seconds)*
>
> 'Hello, am I speaking with Priya Sharma? This is Officer Rajesh from the State Bank of India fraud department in Mumbai. Your KYC is incomplete and your account will be blocked in 30 minutes. Please don't tell anyone about this call...'
>
> *(pause audio)*
>
> Priya clicks 'This is a Scam' at 18 seconds. She caught it during the Authority stage — good. But she missed the Isolation tactic where the caller said 'don't tell anyone.' The debrief explains exactly what she missed and why it works psychologically.
>
> Her Resilience Score jumps from 42 to 67. She just got vaccinated against this exact scam."

**[What's on screen:]**
1. Drill setup form (pre-filled with Priya's details)
2. Click "Start Fire Drill"
3. Loading screen (2 seconds)
4. Drill player with audio playing
5. Click "This is a Scam"
6. Debrief screen showing stages caught/missed
7. Score animation: 42 → 67

**[Demo operator:]**
- Pre-fill the form before the presentation
- Use pre-generated audio (don't rely on live Colab generation)
- Have the audio cued to the right timestamp
- Click "This is a Scam" at exactly the right moment
- The debrief and score should already be pre-computed

**[CRITICAL:]** Rehearse the timing. The audio clip should be exactly 8 seconds of the most impactful part of the scam call. Not the beginning (boring), not the end (too late). The Authority stage is the sweet spot — it sounds official and convincing.

---

**[1:10–1:55] LIVE GUARDIAN DEMO (45 seconds)**

> "Now, what about real-time protection? This is the Live Guardian.
>
> I click 'Start Listening.' Mirage is now monitoring my microphone.
>
> *(teammate reads scam script aloud from phone on speaker)*
>
> 'Hello, this is from the RBI cyber cell. Your PAN card is linked to illegal transactions...'
>
> *(Guardian UI updates live)*
>
> You can see the transcript appearing in real-time. The stage tracker lights up: Hook... Authority... Isolation...
>
> Now it hits Urgency — 'your account will be frozen in 30 minutes' — and Mirage fires a warning alert.
>
> Then the Memory Handshake triggers. Mirage asks: 'Ask the caller: What did we name our dog in 2019?'
>
> A real family member would know this. A voice clone cannot. The caller can't answer — **confirmed scam.** Hang up now."

**[What's on screen:]**
1. Guardian page, click "Start Listening"
2. Live transcript scrolling
3. Stage bars lighting up one by one
4. Alert panel appearing at Urgency stage
5. Memory Handshake panel appearing
6. Click "They couldn't answer"
7. "🚨 CONFIRMED SCAM" alert

**[Demo operator:]**
- Have a teammate read the scam script from a phone on speakerphone, positioned near the laptop mic
- OR play a pre-recorded scam audio through the laptop speakers (safer, more reliable)
- The Guardian should be pre-configured with the right Memory Handshake question
- If the live mic doesn't pick up well, have a pre-recorded demo video ready to switch to

**[CRITICAL:]** This is the riskiest part of the demo because it depends on live audio. Have TWO backup plans:
1. Pre-recorded video of the Guardian working (switch to it if live fails)
2. Pre-loaded screenshots of each stage (advance through them manually if everything fails)

---

**[1:55–2:25] SCAM GRAPH + HONEYPOT (30 seconds)**

> "But Mirage doesn't just defend — it attacks back.
>
> Our AI honeypot persona 'Ramesh' — a 62-year-old retired bank clerk — keeps scammers on the phone for 15+ minutes, wasting their time and extracting their UPI IDs, phone numbers, and bank accounts.
>
> Every extracted detail feeds into this Scam Graph.
>
> *(show graph)*
>
> You can see how 8 phone numbers, 3 UPI IDs, and 2 fake domains are all connected to the same scam ring operating in Delhi. One UPI ID links to 5 different phone numbers — that's a confirmed mule account.
>
> And this heatmap shows active scam campaigns across India. Delhi is seeing a spike in bank KYC fraud this week."

**[What's on screen:]**
1. Honeypot chat UI showing a snippet of the Ramesh conversation (pre-loaded)
2. Switch to Graph page
3. Zoom into a cluster of connected nodes
4. Click a node to show details
5. Switch to the Weather Map tab
6. Point at Delhi's red hotspot

**[Demo operator:]**
- The graph should be pre-seeded with 50+ nodes (see 7.3)
- Pre-position the graph view on the most impressive cluster
- The honeypot chat should have a pre-loaded conversation that shows IOCs being extracted

---

**[2:25–2:50] ECOSYSTEM + BOT (25 seconds)**

> "All of this is accessible without installing any app. Forward any suspicious message to our Telegram bot — text, voice note, screenshot — and get an instant verdict with evidence.
>
> *(show Telegram bot on phone)*
>
> And for elderly family members, Elder Mode sends voice replies in Hindi or Tamil and automatically alerts the family group when a high-risk scam is detected.
>
> One-click report to the 1930 cybercrime helpline."

**[What's on screen:]**
1. Phone screen showing Telegram bot (hold up phone or show screenshot)
2. Show a voice note being forwarded → verdict response
3. Show Elder Mode voice reply
4. Show the "Report to 1930" button

**[Demo operator:]**
- Have the Telegram bot pre-loaded with a conversation on a real phone
- Hold the phone up to the camera or have a screenshot embedded in the presentation
- Don't try to demo the bot live on stage — phone screens are hard to see

---

**[2:50–3:00] THE CLOSE (10 seconds)**

> "Mirage. The scam vaccine. We attack you first, so real scammers can't.
>
> Thank you."

**[What's on screen:]** Landing page hero with the tagline. Or a final slide with the logo, tagline, and QR code to try the bot.

**[Demo operator:]** Switch back to the landing page. Let it sit while the judges clap.

---

### Rehearsal Schedule

| Rehearsal | When | Focus | Duration |
|-----------|------|-------|----------|
| #1 | 4 hours before demo | Run through the script slowly. Find awkward transitions. Fix timing. | 30 min |
| #2 | 3 hours before | Full speed. Time it. Target: 2:50–3:00. If over 3:00, cut the Graph section. | 20 min |
| #3 | 2 hours before | Simulate failures. What happens if the Guardian mic doesn't work? Switch to backup. | 20 min |
| #4 | 1 hour before | Full dress rehearsal. Wear what you'll wear on stage. Use the actual laptop. | 15 min |
| #5 | 30 min before | One final run. No changes after this. Breathe. | 10 min |

### Rehearsal Rules

1. **Never ad-lib during the demo.** The script is timed to the second. Improvising adds time and introduces errors.
2. **The demo operator and speaker must rehearse together.** The speaker's words cue the operator's clicks. If they're out of sync, the demo falls apart.
3. **Practice the transitions.** The most common demo failure is fumbling between screens. Know exactly which tab to click, which button to press, and when.
4. **Time every section with a stopwatch.** If the Fire Drill section takes 60 seconds instead of 50, you need to cut 10 seconds from somewhere.
5. **Rehearse in the actual venue if possible.** The acoustics, lighting, and projector resolution may affect your demo.

---

## 7.2 · Pre-Record Fallback Videos

### Why You Need This

Live demos fail. Wi-Fi drops. APIs rate-limit. Microphones don't pick up. The Groq API goes down. Your teammate's voice cracks. It happens to every team at every hackathon. The teams that win are the ones that recover seamlessly.

### What to Record

| Video | Duration | Content | When to Use |
|-------|----------|---------|-------------|
| **Full Demo** | 3:00 | The entire demo, screen-recorded, with voiceover | If EVERYTHING breaks. Play this and narrate live over it. |
| **Fire Drill** | 0:50 | Just the Fire Drill flow (setup → audio → debrief → score) | If the live drill generation fails |
| **Guardian** | 0:45 | Just the Guardian flow (mic → transcript → stages → alert → handshake) | If the live mic/WebSocket fails |
| **Graph** | 0:30 | Just the graph and map with pre-seeded data | If Neo4j is unreachable |
| **Telegram Bot** | 0:25 | Phone screen recording of the bot in action | If you can't show the phone live |

### Recording Setup

**Tool:** OBS Studio (free) or Loom (free tier: 5 min per video, which is enough)

**OBS Settings:**
- Resolution: 1920×1080
- FPS: 30
- Output format: MP4 (H.264)
- Audio: System audio + microphone (for voiceover)

**Recording Process:**
1. Close all unnecessary tabs and apps (notifications will ruin the recording)
2. Set your screen to the right resolution (match the projector if possible)
3. Do a dry run without recording to make sure everything works
4. Hit record
5. Perform the demo section slowly and deliberately
6. Stop recording
7. Trim the start and end in any video editor (even the built-in Photos app)

**Voiceover Script:** Record the voiceover separately in a quiet room. Don't rely on the live demo audio. Use the exact same script from 7.1 so the narration matches the visuals.

### How to Switch During the Demo

**The seamless switch technique:**

1. Have all fallback videos open in a video player (VLC or QuickTime) on a **second monitor** or in a **separate virtual desktop**
2. If the live demo breaks, the speaker says: "Let me show you a quick clip of this in action" (this sounds intentional, not like a failure)
3. The operator switches to the video and plays it
4. The speaker narrates live over the video (don't use the video's audio — live narration is more engaging)
5. When the video ends, switch back to the live app for the next section

**Practice this switch at least twice during rehearsal.** The transition should take < 5 seconds.

---

## 7.3 · Seed Data

### Why You Need This

An empty graph looks broken. A score of 0 looks like the app doesn't work. A weather map with no data looks like a placeholder. You need the app to look **lived-in** and **real**.

### Seed Script Location
`backend/scripts/seed_data.py`

### What to Seed

**1. User Profile (1 user)**

```
User: Priya Sharma
City: Mumbai
Bank: SBI
Resilience Score: 67
Elder Mode: false
Family Group: "Sharma Family"
```

**2. Drill History (3 drills)**

| Drill | Type | Result | Reaction Time | Score Before | Score After | Date |
|-------|------|--------|--------------|-------------|-------------|------|
| 1 | Lottery | Identified | 12.5s | 0 | 25 | 2 days ago |
| 2 | Bank KYC | Identified | 22.1s | 25 | 42 | Yesterday |
| 3 | Bank KYC (Hard) | Identified | 18.3s | 42 | 67 | Today |

This gives a nice upward trend on the Resilience Chart: 25 → 42 → 67.

**3. Scam Reports (12 reports)**

| # | Type | Source | Confidence | City | Date |
|---|------|--------|-----------|------|------|
| 1 | Bank KYC | Telegram | 92% | Delhi | Today |
| 2 | UPI Reversal | Web | 85% | Mumbai | Today |
| 3 | FedEx | Telegram | 88% | Delhi | Today |
| 4 | Job Offer | Web | 78% | Bangalore | Yesterday |
| 5 | Lottery | Telegram | 95% | Chennai | Yesterday |
| 6 | Impersonation | Guardian | 97% | Delhi | Yesterday |
| 7 | Investment | Telegram | 82% | Hyderabad | 2 days ago |
| 8 | Electricity | Web | 75% | Pune | 2 days ago |
| 9 | QR Code | Telegram | 90% | Mumbai | 2 days ago |
| 10 | Relative | Guardian | 88% | Kolkata | 3 days ago |
| 11 | Bank KYC | Telegram | 91% | Delhi | 3 days ago |
| 12 | Romance | Web | 65% | Jaipur | 3 days ago |

**4. Scam Graph (50+ nodes)**

**Phone Numbers (15):**
```
98765-43210 (primary KYC scammer, Delhi)
98765-43211 (secondary, same ring)
98765-43212 (tertiary)
87654-32109 (WhatsApp contact)
76543-21098 (backup)
99887-76655 (new, 2 days old)
88776-65544 (UPI reversal scammer, Mumbai)
77665-54433 (same ring)
66554-43322 (FedEx scammer, Delhi)
55443-32211 (job offer, Bangalore)
44332-21100 (lottery, Chennai)
33221-10099 (impersonation, Delhi)
22110-09988 (investment, Hyderabad)
11099-88776 (electricity, Pune)
99988-77665 (romance, Jaipur)
```

**UPI IDs (8):**
```
sbi-safe@ybl (KYC ring, linked to 4 phones)
kyc-verify@paytm (KYC ring)
ramesh.kumar@okhdfc (mule account)
refund-process@ybl (UPI reversal)
customs-fee@paytm (FedEx)
job-reg@okicici (job offer)
prize-claim@ybl (lottery)
rbi-secure@paytm (impersonation)
```

**Domains (6):**
```
sbi-kyc-verify.xyz (4 days old)
rbi-verification.top (2 days old)
fedex-india-customs.top (6 days old)
amazon-job-apply.click (3 days old)
kbc-prize-claim.xyz (5 days old)
delhi-police-verify.xyz (1 day old)
```

**Bank Accounts (4):**
```
1234567890123 (SBI, linked to sbi-safe@ybl)
9876543210123 (HDFC, linked to ramesh.kumar@okhdfc)
4567890123456 (ICICI, linked to refund-process@ybl)
7890123456789 (Axis, linked to customs-fee@paytm)
```

**Relationships (30+ edges):**
```
98765-43210 → USES_UPI → sbi-safe@ybl
98765-43211 → USES_UPI → sbi-safe@ybl
98765-43212 → USES_UPI → sbi-safe@ybl
99887-76655 → USES_UPI → sbi-safe@ybl
98765-43210 → LINKED_TO → sbi-kyc-verify.xyz
98765-43211 → LINKED_TO → sbi-kyc-verify.xyz
33221-10099 → LINKED_TO → rbi-verification.top
sbi-safe@ybl → DEPOSITS_TO → 1234567890123
ramesh.kumar@okhdfc → DEPOSITS_TO → 9876543210123
88776-65544 → USES_UPI → refund-process@ybl
77665-54433 → USES_UPI → refund-process@ybl
66554-43322 → USES_UPI → customs-fee@paytm
66554-43322 → LINKED_TO → fedex-india-customs.top
55443-32211 → USES_UPI → job-reg@okicici
55443-32211 → LINKED_TO → amazon-job-apply.click
44332-21100 → USES_UPI → prize-claim@ybl
44332-21100 → LINKED_TO → kbc-prize-claim.xyz
33221-10099 → USES_UPI → rbi-secure@paytm
... (add more to reach 30+)
```

**5. Weather Map Data (10 cities)**

Use the data from Phase 5 (5.5). Hardcode it in the backend response if the aggregation query is too slow.

**6. Honeypot Conversation (1 pre-loaded session)**

A 15-message conversation between "Ramesh" and a KYC scammer. Show it in the honeypot chat UI. Highlight the extracted IOCs.

### How to Seed

**Option A: Python script (recommended)**
```
python backend/scripts/seed_data.py
```
This script:
1. Connects to Supabase and inserts user, drills, and reports
2. Connects to Neo4j and creates all nodes and relationships
3. Runs ring detection to verify the graph is correct

**Option B: Manual SQL + Cypher**
Run the INSERT statements directly in Supabase SQL Editor and Neo4j Browser. Slower but more control.

**Option C: API calls**
Call your own API endpoints to create the data. This tests the endpoints too.

### When to Seed

- **First seed:** After Phase 5 is complete (so you can test the graph and map)
- **Final seed:** 2 hours before the demo (to ensure fresh timestamps)
- **Backup seed:** Have the seed script on a USB drive in case the database gets wiped

---

## 7.4 · Pitch Deck

### Format
5 slides maximum. Judges see 20+ pitches — they won't remember your 15-slide deck. They WILL remember 5 powerful slides.

### Tool
Figma (free, collaborative) or Canva (free, faster). Export as PDF.

---

**Slide 1: THE PROBLEM**

**Visual:** Dark background. Large red number in the center. Minimal text.

```
₹7,000 CRORE

Lost to cyber scams in India in 2024.

85% of victims are over 50 years old.
Current tools detect scams AFTER you've been hit.
```

**Design notes:**
- Font: Inter Bold, 96px for the number
- Color: Red (#ef4444) for the number, white for the text
- Background: Near black (#030712)
- No images, no clutter. Let the number speak.

---

**Slide 2: THE INSIGHT**

**Visual:** Split screen. Left side: "Current approach" (fire extinguisher icon). Right side: "Mirage" (vaccine/syringe icon).

```
Current Approach          Mirage

🧯 Fire Extinguisher     💉 Vaccine
Detect after the fact     Train before you're hit
Generic verdicts          Personalized attacks
Text only                 Voice, image, live calls
Solo tool                 Family network

"We attack you first, so real scammers can't."
```

**Design notes:**
- Left side: gray, muted (the old way)
- Right side: blue glow, vibrant (the new way)
- The tagline at the bottom is the most important text on this slide

---

**Slide 3: THE DEMO (screenshot collage)**

**Visual:** 4 screenshots arranged in a 2×2 grid, each with a one-line label.

```
┌──────────────────┐ ┌──────────────────┐
│ 🔥 Fire Drill    │ │ 🛡️ Live Guardian │
│ [Screenshot of   │ │ [Screenshot of   │
│  the drill       │ │  the stage       │
│  player with     │ │  tracker with    │
│  cloned audio]   │ │  red alert]      │
└──────────────────┘ └──────────────────┘
┌──────────────────┐ ┌──────────────────┐
│ 🕸️ Scam Graph    │ │ 📱 Telegram Bot  │
│ [Screenshot of   │ │ [Screenshot of   │
│  the Neo4j graph │ │  the bot reply   │
│  with rings]     │ │  on a phone]     │
└──────────────────┘ └──────────────────┘
```

**Design notes:**
- Screenshots should be from YOUR actual app, not mockups
- Add a subtle border and shadow to each screenshot
- Labels in the top-left corner of each screenshot
- This slide proves you actually built the thing

---

**Slide 4: THE ARCHITECTURE**

**Visual:** Simplified architecture diagram. Not a technical deep dive — just enough to show engineering depth.

```
┌─────────┐    ┌──────────┐    ┌─────────┐
│ Telegram │    │  Web App  │    │  Mobile  │
│   Bot    │    │ (Next.js) │    │ Guardian │
└────┬─────┘    └─────┬────┘    └────┬────┘
     │                │              │
     └────────┬───────┴──────────────┘
              │
     ┌────────▼────────┐
     │   FastAPI + AI   │
     │  Groq • Gemini   │
     │  Whisper • TTS   │
     └───┬─────────┬───┘
         │         │
    ┌────▼───┐ ┌───▼────┐
    │Supabase│ │ Neo4j  │
    │Postgres│ │ Graph  │
    └────────┘ └────────┘
```

**Design notes:**
- Use the same dark theme as the app
- Color-code: blue for frontend, green for backend, purple for databases
- Keep it simple — 3 layers max
- Add a small "100% free stack" badge in the corner (judges love cost efficiency)

---

**Slide 5: THE ASK**

**Visual:** Clean, bold, memorable.

```
MIRAGE

The Scam Vaccine.

🔥 Try the Fire Drill: [QR code to web app]
📱 Try the Bot: [QR code to Telegram bot]
📞 Report scams: 1930

Built by Team [Name] • Forgehacks 2025
GitHub: github.com/[repo]
```

**Design notes:**
- QR codes are critical — judges can scan them and try the app during Q&A
- Generate QR codes using `qrcode` Python package or any free online tool
- The GitHub link shows you're open-source and real
- Keep the 1930 helpline — it shows social impact awareness

---

### Pitch Deck Rules

1. **No more than 30 words per slide.** The slides support your voice, they don't replace it.
2. **Dark theme.** Match your app's aesthetic.
3. **No stock photos.** Use screenshots of your actual app.
4. **No bullet points with more than 5 items.** If you need more, split into two slides (but you shouldn't — you only have 5).
5. **Font size ≥ 24px.** If the judge in the back row can't read it, it's too small.

---

## 7.5 · One-Liner & Tagline

### Primary Tagline (use everywhere)

> **"Mirage: The Scam Vaccine."**

### Secondary Tagline (for the demo opening)

> **"We attack you first, so real scammers can't."**

### Elevator Pitch (30 seconds, for networking)

> "Mirage is a personal AI immune system against scams. Instead of detecting scams after you've been targeted, we simulate personalized scam attacks using your real details — your name, your bank, your city — so you learn to spot the signs before a real scammer calls. We also monitor your live calls in real-time, verify caller identity with a Memory Handshake that voice clones can't beat, and track scammer networks across India. It's free, works on WhatsApp and Telegram, and supports Hindi, Tamil, and English. We're the fire drill for fraud."

### Alternative Taglines (pick your favorite)

| Tagline | Vibe |
|---------|------|
| "Your AI immune system against fraud." | Medical metaphor, clean |
| "Get scammed safely. So you never get scammed for real." | Provocative, memorable |
| "The fire drill for your finances." | Simple, relatable |
| "Scam-proof your parents." | Emotional, targets the real user |
| "Before they call you, we call you." | Clever, action-oriented |
| "Training humans, not just classifiers." | Technical, differentiator |

### Where to Use Each

| Context | Use |
|---------|-----|
| Pitch deck title slide | "Mirage: The Scam Vaccine" |
| Demo opening line | "We attack you first, so real scammers can't" |
| README header | "Mirage — Personal AI Immune System Against Scams" |
| Telegram bot description | "Your AI scam shield. Forward any suspicious message." |
| T-shirt / sticker | "Scam-proof your parents 🛡️" |
| Judge Q&A | "Training humans, not just classifiers" |

---

## 7.6 · Bug Bash

### When
1–2 hours before the demo. No new features after this point.

### Who
Everyone on the team. Each person tries to break a different part of the app.

### Bug Bash Checklist

**Frontend:**
```
□ Load every page on Chrome, Firefox, and Safari
□ Load every page on mobile (iPhone + Android)
□ Click every button and link — do they go where they should?
□ Resize the browser window — does the layout break?
□ Refresh every page — does it reload correctly?
□ Navigate with keyboard only (Tab, Enter) — is it accessible?
□ Check for console errors (F12 → Console)
□ Check for broken images or missing icons
□ Check for text overflow (especially on mobile)
□ Check dark mode — are there any white flashes?
```

**Backend:**
```
□ Hit every API endpoint with valid data
□ Hit every API endpoint with invalid data (empty, null, huge)
□ Hit /health — does it return 200?
□ Check CORS — can the frontend reach the backend?
□ Check rate limits — what happens if you spam the API?
□ Check error responses — are they helpful, not 500s?
□ Check database connections — are they stable?
□ Check Neo4j queries — do they return data?
□ Check file uploads — do they work for all formats?
□ Check WebSocket — does it connect and stream?
```

**Telegram Bot:**
```
□ Send /start — does it reply?
□ Forward a text message — does it analyze?
□ Forward a voice note — does it transcribe?
□ Forward a screenshot — does it OCR?
□ Send a URL — does it check the domain?
□ Send /check with text — does it work?
□ Send /elder — does it toggle?
□ Send gibberish — does it handle gracefully?
□ Send a huge file — does it reject politely?
□ Send nothing (empty message) — does it prompt?
```

**Demo-Specific:**
```
□ Run the full 3-minute demo end-to-end
□ Time it — is it under 3:00?
□ Check the Fire Drill audio — does it play?
□ Check the Guardian mic — does it pick up sound?
□ Check the Graph — does it render with seed data?
□ Check the Map — does it show cities?
□ Check the Score animation — does it count up?
□ Check the Telegram bot on a real phone
□ Check the fallback videos — do they play?
□ Check the pitch deck — does it display on the projector?
```

### Bug Triage Rules

| Severity | Action | Example |
|----------|--------|---------|
| **Critical** (demo-breaking) | Fix immediately | Fire Drill audio doesn't play, Guardian WebSocket won't connect |
| **High** (visible to judges) | Fix if time permits | Graph shows no data, score doesn't animate |
| **Medium** (noticeable but not fatal) | Hide the feature | Weather map is blank → remove the map tab |
| **Low** (cosmetic) | Ignore | Typo in a label, slight misalignment |

**The golden rule of bug bashing:** If you can't fix it in 10 minutes, **hide it**. Remove the button, collapse the section, skip it in the demo. A missing feature is better than a broken feature.

---

## 7.7 · README & Submission

### README Template

```markdown
# 🛡️ Mirage — Personal AI Immune System Against Scams

> **We attack you first, so real scammers can't.**

Mirage is an AI-powered scam prevention platform that trains users to recognize scams through personalized simulations ("Scam Fire Drills"), monitors live calls in real-time, verifies caller identity with a Memory Handshake, and tracks scammer networks across India.

## 🏆 Built for Forgehacks 2025

## 🎯 The Problem

- ₹7,000+ crore lost to cyber scams in India in 2024
- 85% of victims are over 50 years old
- Current tools detect scams AFTER the damage is done
- No existing solution trains users proactively

## 💡 The Solution

### 🔥 Scam Fire Drills (Signature Feature)
Mirage scans your public footprint and simulates a personalized scam attack using your real name, bank, city, and even a cloned voice. You learn to spot red flags in a safe environment. Your Scam Resilience Score improves with each drill.

### 🛡️ Live Call Guardian
Real-time call monitoring with a 5-stage scam pipeline tracker (Hook → Authority → Isolation → Urgency → Payment). Alerts you BEFORE the payment stage. Includes synthetic voice detection to catch AI-generated deepfake calls.

### 🔐 Memory Handshake
2FA for human identity. Register shared secrets with family members. During a suspicious call, ask the caller a question only the real person would know. A voice clone can replicate timbre but cannot answer "What did we name our dog in 2019?"

### 🕸️ Scammer Hunter & Scam Graph
AI honeypot persona "Ramesh" wastes scammers' time and extracts UPI IDs, phone numbers, and bank details. All IOCs feed into a Neo4j knowledge graph that reveals scam rings and active campaigns.

### 📱 Zero-Install Access
Telegram bot handles text, voice notes, screenshots, and URLs. Elder Mode provides voice replies in Hindi and Tamil with automatic family alerts.

## 🏗️ Architecture

[Insert architecture diagram image]

## 🛠️ Tech Stack (100% Free)

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 14, Tailwind CSS, shadcn/ui, Recharts |
| Backend | FastAPI, Pydantic, Uvicorn |
| Database | Supabase (PostgreSQL), Neo4j AuraDB |
| AI/LLM | Groq (Llama 3.3 70B + Whisper), Google Gemini 2.0 Flash |
| Voice | F5-TTS (cloning), Edge-TTS (synthesis), Resemblyzer (detection) |
| Messaging | Telegram Bot API |
| Deployment | Vercel (frontend), Render (backend) |

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- Node.js 18+
- API keys: Groq, Gemini, Supabase, Neo4j, Telegram

### Backend
```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # Fill in your API keys
uvicorn app.main:app --reload --port 8000
```

### Frontend
```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

### Telegram Bot
```bash
cd bot
pip install -r requirements.txt
cp .env.example .env
python main.py
```

## 📸 Screenshots

[Insert 4-6 screenshots: Landing page, Fire Drill, Guardian, Graph, Bot]

## 🎬 Demo Video

[Insert link to demo video]

## 📊 Key Metrics (Demo)

- Scam analysis accuracy: 92% across 20 test samples
- Fire Drill completion time: < 2 minutes
- Guardian alert latency: 5-7 seconds
- Honeypot average time-wasted per scammer: 12+ minutes
- Supported languages: English, Hindi, Tamil

## 🤝 Team

- [Name] — [Role]
- [Name] — [Role]
- [Name] — [Role]

## 📄 License

MIT

## 📞 Report Scams

- National Cyber Crime Helpline: **1930**
- Portal: [cybercrime.gov.in](https://cybercrime.gov.in)
```

### Submission Checklist

```
□ GitHub repo is public (or shared with judges)
□ README has screenshots, architecture, and setup instructions
□ All API keys are in .env.example (NOT committed)
□ .gitignore excludes node_modules, venv, .env, __pycache__
□ Seed data script is included and documented
□ Demo video is uploaded (YouTube unlisted or Loom)
□ Pitch deck is uploaded (PDF)
□ Live demo links work:
  □ Frontend: https://mirage-ai.vercel.app
  □ Backend: https://mirage-api.onrender.com/health
  □ Telegram Bot: @mirage_scam_bot
□ Submission form is filled out completely
□ Team members are listed with roles
□ Track/category is selected correctly
```

---

## Final Timeline (Last 6 Hours)

| Time | Activity | Who |
|------|----------|-----|
| T-6:00 | Phase 6 wrap-up. All pages functional. | Frontend team |
| T-5:00 | Seed data script runs. Graph, map, scores populated. | Backend team |
| T-4:00 | Record fallback videos (full demo + individual features). | Everyone |
| T-3:00 | Pitch deck finalized. Export to PDF. | Designer/speaker |
| T-2:00 | Bug bash. Fix critical, hide cosmetic. | Everyone |
| T-1:30 | First full rehearsal. Time it. | Speaker + operator |
| T-1:00 | Second rehearsal. Test backup videos. | Speaker + operator |
| T-0:45 | Final seed data refresh (timestamps). | Backend |
| T-0:30 | Third rehearsal. No more changes. | Speaker + operator |
| T-0:15 | Set up laptop. Open all tabs. Queue audio. Test mic. | Operator |
| T-0:05 | Deep breath. You've got this. | Everyone |
| T-0:00 | **DEMO TIME** 🚀 | Speaker |

---

## Phase 7 Completion Checklist

```
□ Demo script is written word-for-word and timed to 3:00
□ Speaker is assigned and has rehearsed 5+ times
□ Demo operator knows every click and transition
□ Fallback videos recorded for all 5 features
□ Full demo fallback video recorded (3 min)
□ Fallback video switch technique rehearsed
□ Seed data script populates 50+ graph nodes
□ Seed data populates 3 drill history entries
□ Seed data populates 10 city weather map entries
□ Seed data populates 1 honeypot conversation
□ Pitch deck has exactly 5 slides
□ Pitch deck uses dark theme matching the app
□ Pitch deck includes real screenshots (not mockups)
□ Pitch deck includes QR codes to try the app
□ Primary tagline is chosen and used consistently
□ Elevator pitch is memorized
□ Bug bash completed (all critical bugs fixed)
□ Non-fixable features are hidden
□ README is complete with screenshots and setup
□ GitHub repo is clean and public
□ All submission materials uploaded
□ Live links tested and working
□ Laptop is charged and ready
□ Backup laptop is available (if possible)
□ Team knows the plan if things go wrong
```

---

**When every box is checked, you are ready to win.**

Go build something incredible. The scam vaccine the world needs. 🛡️💉

**Good luck at Forgehacks. Make Priya's parents proud.** 🚀