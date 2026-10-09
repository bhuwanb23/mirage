# Phase 2 — Telegram Bot (Complete Deep Dive)

---

## Architecture Overview

```
User (Telegram)
    │
    │ forwards message / sends command
    │
    ▼
┌─────────────────────────────────────┐
│         Telegram Bot (bot/)         │
│                                     │
│  ┌───────────┐  ┌────────────────┐  │
│  │ Command    │  │ Message Type   │  │
│  │ Handlers   │  │ Router         │  │
│  │ /start     │  │ text → 2.1     │  │
│  │ /check     │  │ voice → 2.2    │  │
│  │ /elder     │  │ photo → 2.3    │  │
│  │ /help      │  │ url → 2.4      │  │
│  │ /family    │  │                │  │
│  └─────┬─────┘  └───────┬────────┘  │
│        │                │           │
│  ┌─────▼────────────────▼────────┐  │
│  │     Backend API Client        │  │
│  │  POST /analyze (HTTPX)        │  │
│  └─────────────┬─────────────────┘  │
│                │                    │
│  ┌─────────────▼─────────────────┐  │
│  │     Response Formatter        │  │
│  │  (Telegram Markdown/HTML)     │  │
│  └─────────────┬─────────────────┘  │
│                │                    │
│  ┌─────────────▼─────────────────┐  │
│  │     Elder Mode Engine         │  │
│  │  (Edge-TTS → voice reply)     │  │
│  └─────────────┬─────────────────┘  │
│                │                    │
│  ┌─────────────▼─────────────────┐  │
│  │     Family Alert Dispatcher   │  │
│  │  (confidence > 85% → group)   │  │
│  └───────────────────────────────┘  │
└─────────────────────────────────────┘
                │
                ▼
        Backend (FastAPI)
        POST /analyze
```

---

## Prerequisites (from Phase 0)

Before starting Phase 2, confirm:
- Telegram bot created via BotFather with token in `.env`
- `python-telegram-bot` v20+ installed
- Backend `POST /analyze` endpoint working and returning valid `ScamVerdict` JSON
- `httpx` installed for async HTTP calls to backend
- Edge-TTS installed (`pip install edge-tts`)

---

## 2.1 · Text Message Handler

### File Location
`bot/handlers/text_handler.py`

### What It Does
When a user forwards or types a text message to the bot, the handler sends it to the backend for analysis and returns a beautifully formatted Telegram verdict.

### Logic Flow (step by step)

**Step 1: Receive the message**
- The handler triggers on any incoming text message that is NOT a command (commands start with `/` and are caught by CommandHandlers first)
- Extract: `message.text`, `message.from_user.id`, `message.from_user.first_name`, `message.chat.id`
- Check if the message is a **forward** from another chat: `message.forward_from` or `message.forward_sender_name` will be set if it is. This is useful context — forwarded messages are more likely to be real scam messages the user received

**Step 2: Validate the input**
- If text is empty or only whitespace → reply: "Please send a message with actual content."
- If text is shorter than 5 characters → reply: "Message too short to analyze. Please forward the full scam message."
- If text is longer than 4,000 characters → truncate to 4,000 and add a note: "(Message truncated for analysis)"

**Step 3: Send "analyzing" feedback**
- Immediately reply with a typing indicator: `await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)`
- Then send a temporary message: "🔍 Analyzing your message..." and save its `message_id`
- This gives the user instant feedback while the backend processes (which takes 1–3 seconds)
- Later, you'll **edit** this message with the real verdict instead of sending a new one (cleaner UX)

**Step 4: Call the backend**
- Use `httpx.AsyncClient` to call `POST {BACKEND_URL}/analyze`
- Send as `multipart/form-data` with field `text` = the message text
- Set a timeout of 15 seconds (backend should respond in < 3 seconds, but allow buffer)
- Handle HTTP errors:
  - 400 → "Invalid input. Please try again."
  - 503 → "AI service is temporarily busy. Please try again in 30 seconds."
  - 504 → "Analysis timed out. Try a shorter message."
  - Connection error → "Cannot reach the analysis server. Please try again later."
  - Any other error → "Something went wrong. Please try again."

**Step 5: Parse the response**
- Parse the JSON response into the `ScamVerdict` structure
- Extract: `is_scam`, `confidence`, `scam_type`, `risk_level`, `red_flags`, `summary`, `recommended_action`, `evidence`

**Step 6: Format the Telegram reply**

This is the most important part for user experience. The reply must be **visually scannable** in a small phone screen. Use Telegram's HTML parse mode.

**Format for SCAM detected (is_scam = true):**

```
🚨 <b>SCAM DETECTED</b> — {confidence_percent}% confident

<b>Type:</b> {scam_type_readable}
<b>Risk:</b> {risk_emoji} {risk_level_upper}

<b>⚠️ Red Flags:</b>
{numbered red flags, each on a new line with • bullet}

<b>📋 Summary:</b>
{summary text}

<b>✅ What to do:</b>
{recommended_action}

<b>🔬 Evidence:</b>
{top 3 evidence items, brief}

<i>Report to 1930 helpline | cybercrime.gov.in</i>
```

**Concrete example of what the user sees:**

```
🚨 SCAM DETECTED — 92% confident

Type: Bank KYC / Account Freeze
Risk: 🔴 CRITICAL

⚠️ Red Flags:
• Domain sbi-kyc-verify.xyz is only 4 days old
• Asks for ATM PIN — banks NEVER ask for PIN via SMS
• Creates extreme urgency: "blocked in 24 hours"
• Helpline is a mobile number, not toll-free

📋 Summary:
This is a Bank KYC scam. The message claims your SBI account will be blocked and directs you to a fake website registered 4 days ago. It asks for your ATM PIN and OTP, which no real bank will ever request.

✅ What to do:
🚨 DELETE IMMEDIATELY. Do NOT click the link. Do NOT share any OTP. Report to 1930 helpline.

🔬 Evidence:
• Domain registered 4 days ago via Namecheap (sbi-kyc-verify.xyz)
• Message asks for ATM PIN — banks never ask for PIN via SMS
• URL path contains suspicious keywords: kyc, verify, update

Report to 1930 helpline | cybercrime.gov.in
```

**Format for LEGITIMATE message (is_scam = false):**

```
✅ <b>LIKELY LEGITIMATE</b> — {confidence_percent}% confident

<b>📋 Summary:</b>
{summary text}

<b>💡 Tips:</b>
• No significant scam indicators found
• Always verify links by typing the URL manually
• Never share your OTP with anyone

<i>Still unsure? Call your bank on the official number.</i>
```

**Format for UNCERTAIN (confidence 40–60%):**

```
🟡 <b>UNCERTAIN</b> — {confidence_percent}% confident

<b>Type:</b> {scam_type_readable or "Unknown"}
<b>Risk:</b> 🟡 MEDIUM

<b>⚠️ Potential concerns:</b>
{red flags if any}

<b>📋 Summary:</b>
{summary text}

<b>💡 Recommendation:</b>
Proceed with caution. Verify through official channels before taking any action. When in doubt, call your bank on the number printed on your debit card.

<i>Forward more context for a better analysis.</i>
```

**Step 7: Edit the temporary message**
- Use `await context.bot.edit_message_text(chat_id=chat_id, message_id=temp_msg_id, text=formatted_reply, parse_mode="HTML")`
- This replaces the "🔍 Analyzing..." message with the real verdict
- If the formatted text exceeds Telegram's 4,096 character limit → split into two messages: first message has the verdict + red flags, second message has the evidence details

**Step 8: Log the interaction**
- Log: user_id, chat_id, input_type (text), input_length, is_scam, confidence, processing_time
- This data feeds the scam graph and analytics later

### Risk Emoji Mapping

| Risk Level | Emoji | Color Word |
|------------|-------|-----------|
| low | 🟢 | GREEN |
| medium | 🟡 | YELLOW |
| high | 🟠 | ORANGE |
| critical | 🔴 | RED |

### Scam Type Readable Names

(Reuse the same mapping from Phase 1)

| Code | Readable |
|------|----------|
| bank_kyc | Bank KYC / Account Freeze |
| upi_reversal | UPI Payment Reversal |
| fedex | Fake Delivery / Customs |
| job_offer | Fake Job Offer |
| lottery | Lottery / Prize |
| relative_distress | Relative in Distress |
| otp_phishing | OTP Phishing |
| investment | Investment / Trading |
| romance | Romance |
| electricity | Electricity Bill |
| impersonation | Government / Police Impersonation |
| qr_code | QR Code |
| unknown | Unknown Scam Type |
| null | Not Classified |

### Edge Cases

| Edge Case | Behavior |
|-----------|----------|
| User sends a greeting ("hi", "hello") | Don't analyze. Reply: "👋 Hi! Forward me any suspicious message, voice note, or screenshot and I'll check if it's a scam. Type /help for more info." |
| User sends a very long forwarded chain (10+ messages forwarded as one block) | Analyze the full text. The LLM can handle it. If it exceeds 4,000 chars, truncate. |
| User sends a message in Hindi | Backend handles it (Llama 3.3 supports Hindi). Bot reply should be in the same language as the input. Detect language from the input text: if > 50% Devanagari characters → reply in Hindi. Use a simple Unicode range check. |
| User sends a message in Tamil | Same as Hindi — detect Tamil Unicode range, reply in Tamil if backend supports it. For Phase 2, English reply is acceptable; add Tamil replies in a later iteration. |
| User sends a message that's just an emoji | Reply: "I need text to analyze. Please forward the full suspicious message." |
| User sends a message with only a phone number | Treat as text. The backend will likely return low confidence. Add a note: "Tip: If you received a call from this number, forward the call recording for better analysis." |
| User sends the same message twice | Don't cache at the bot level — let the backend handle caching. Just process normally. |
| Backend returns a malformed response | Catch the JSON parse error. Reply: "⚠️ Analysis failed due to a server error. Please try again in a moment." |
| Telegram message has entities (bold, italic, links) | `message.text` gives you the plain text without formatting. That's fine for analysis. If you need the entities, use `message.entities` to extract URLs specifically. |

---

## 2.2 · Voice Note Handler

### File Location
`bot/handlers/voice_handler.py`

### What It Does
When a user forwards a voice note (the `.ogg` audio messages common on WhatsApp and Telegram), the bot downloads it, sends it to the backend's audio pipeline, and returns the transcript + scam verdict + synthetic voice score.

### Logic Flow

**Step 1: Receive the voice message**
- Trigger on `MessageHandler(filters.VOICE | filters.AUDIO, voice_handler)`
- `filters.VOICE` catches voice notes (recorded in-app)
- `filters.AUDIO` catches forwarded audio files (`.mp3`, `.wav`, etc.)
- Extract: `message.voice.file_id` (for voice notes) or `message.audio.file_id` (for audio files)
- Get file metadata: `duration` (seconds), `file_size` (bytes), `mime_type`

**Step 2: Validate the audio**
- If duration < 1 second → reply: "Audio too short to analyze. Please send a longer recording."
- If duration > 120 seconds → reply: "Audio too long (max 2 minutes). Please send a shorter clip or the most suspicious part."
- If file_size > 10 MB → reply: "Audio file too large (max 10 MB). Please compress or trim it."

**Step 3: Download the audio file**
- Use the Telegram Bot API to download the file:
  1. `file = await context.bot.get_file(message.voice.file_id)`
  2. `file_bytes = await file.download_as_bytearray()`
- Save to a temporary file on disk: `/tmp/mirage_voice_{user_id}_{timestamp}.ogg`
- Use `tempfile` module to handle cleanup automatically
- **Important:** Delete the temp file after analysis to avoid filling up disk space on the server

**Step 4: Send "analyzing" feedback**
- Send typing indicator + temporary message: "🎤 Analyzing voice note... This may take a few seconds."
- Voice analysis takes longer than text (5–8 seconds) because of transcription + synthetic voice detection

**Step 5: Call the backend**
- Use `httpx.AsyncClient` to call `POST {BACKEND_URL}/analyze`
- Send as `multipart/form-data` with:
  - `file`: the audio file bytes, with filename and MIME type
  - `input_type`: `audio`
- Timeout: 20 seconds (audio analysis is slower)

**Step 6: Parse the response**
- The response will include the standard `ScamVerdict` plus audio-specific fields:
  - `transcript`: the full transcription
  - `transcript_segments`: timestamped segments
  - `detected_language`: "en", "hi", "ta"
  - `synthetic_voice_score`: 0.0–1.0
  - `voice_verdict`: "human", "likely_human", "uncertain", "likely_ai_generated", "ai_generated"
  - `audio_duration_seconds`: duration

**Step 7: Format the Telegram reply**

**Format for voice note analysis:**

```
🎤 <b>VOICE NOTE ANALYSIS</b>

<b>📝 Transcript:</b>
<i>"{transcript_text}"</i>
(Language: {detected_language_readable})

<b>🔊 Voice Authenticity:</b>
{voice_authenticity_bar} {synthetic_score_percent}%
{voice_verdict_emoji} {voice_verdict_readable}

━━━━━━━━━━━━━━━━━━━━

{standard scam verdict block from 2.1}
```

**Voice Authenticity Bar Visualization:**

Create a visual bar using block characters:
- 0–20% synthetic: `🟩🟩🟩🟩🟩 Likely Human` (safe)
- 21–40% synthetic: `🟩🟩🟩🟨🟨 Probably Human`
- 41–60% synthetic: `🟩🟩🟨🟨🟨 Uncertain`
- 61–80% synthetic: `🟥🟥🟥🟨🟨 Likely AI-Generated ⚠️`
- 81–100% synthetic: `🟥🟥🟥🟥🟥 AI-Generated 🚨`

**Concrete example:**

```
🎤 VOICE NOTE ANALYSIS

📝 Transcript:
"Hello beta, this is your uncle. I am in the hospital in Delhi. I met with an accident. Please send ₹50,000 to this UPI ID immediately. Don't tell your father."
(Language: Hindi)

🔊 Voice Authenticity:
🟥🟥🟥🟨🟨 72%
⚠️ Likely AI-Generated

━━━━━━━━━━━━━━━━━━━━

🚨 SCAM DETECTED — 88% confident

Type: Relative in Distress
Risk: 🔴 CRITICAL

⚠️ Red Flags:
• Voice is likely AI-generated (72% synthetic)
• Isolation tactic: "Don't tell your father"
• Extreme urgency: "immediately"
• Unusual UPI ID for a family member

📋 Summary:
This voice note appears to be an AI-generated clone impersonating a relative. The caller claims to be in the hospital and demands urgent payment — a classic relative-in-distress scam. The synthetic voice score confirms this is not a real human voice.

✅ What to do:
🚨 DO NOT SEND MONEY. Call your uncle directly on his known phone number to verify. Report to 1930 helpline.

Report to 1930 helpline | cybercrime.gov.in
```

**Step 8: Edit the temporary message**
- Same as text handler — edit the "Analyzing..." message with the real verdict
- If the response is too long (> 4,096 chars), split: first message = transcript + voice score, second message = scam verdict

**Step 9: Clean up**
- Delete the temporary audio file from `/tmp/`

### Edge Cases

| Edge Case | Behavior |
|-----------|----------|
| Voice note is just background noise | Transcript will be empty or gibberish. Reply: "No clear speech detected in this audio. Please send a recording with clear voice." |
| Voice note has multiple speakers | Transcript will mix them. Add note: "Multiple speakers detected — analysis may be less accurate." |
| Voice note is in a regional language (Telugu, Bengali, etc.) | Whisper handles most Indian languages. If transcription quality is poor, note: "Transcription may be inaccurate for this language." |
| Voice note is a song or music | Whisper will try to transcribe lyrics. The scam classifier will return `is_scam: false`. Add note: "This appears to be music, not a voice message." |
| Audio file is corrupted | Backend returns an error. Bot replies: "Could not process this audio file. Please try re-recording or re-forwarding." |
| Voice note is forwarded from WhatsApp | Telegram converts WhatsApp audio to `.ogg`. The backend handles `.ogg` natively via Groq Whisper. No conversion needed. |

---

## 2.3 · Image / Screenshot Handler

### File Location
`bot/handlers/image_handler.py`

### What It Does
When a user forwards a screenshot (of a WhatsApp chat, bank page, SMS, email, etc.), the bot downloads the image, sends it to the backend's image pipeline, and returns the OCR'd text + visual analysis + scam verdict.

### Logic Flow

**Step 1: Receive the image**
- Trigger on `MessageHandler(filters.PHOTO | filters.Document.IMAGE, image_handler)`
- `filters.PHOTO` catches compressed photos (Telegram sends multiple resolutions)
- `filters.Document.IMAGE` catches uncompressed images sent as files
- For photos: always use the **highest resolution** version → `message.photo[-1].file_id` (the last element in the photo array is the largest)
- For documents: `message.document.file_id`
- Extract: `file_size`, `mime_type`, `file_name` (if document)

**Step 2: Validate the image**
- If file_size > 5 MB → reply: "Image too large (max 5 MB). Please compress or crop it."
- Supported formats: `.jpg`, `.jpeg`, `.png`, `.webp`. If unsupported → reply with error.

**Step 3: Download the image**
- Same as voice handler: `get_file()` → `download_as_bytearray()`
- Save to `/tmp/mirage_image_{user_id}_{timestamp}.jpg`

**Step 4: Send "analyzing" feedback**
- "📸 Analyzing screenshot... Reading text and checking for fake UI elements."

**Step 5: Call the backend**
- `POST {BACKEND_URL}/analyze` with:
  - `file`: image bytes
  - `input_type`: `image`
- Timeout: 15 seconds

**Step 6: Parse the response**
- Standard `ScamVerdict` plus image-specific fields:
  - `ocr_text`: the extracted text from the screenshot
  - `app_identified`: "WhatsApp", "SMS", "Bank App", "Browser", "Email", "Unknown"
  - `visual_red_flags`: list of visual anomalies
  - `looks_legitimate`: boolean

**Step 7: Format the Telegram reply**

**Format for image analysis:**

```
📸 <b>SCREENSHOT ANALYSIS</b>

<b>📱 App Detected:</b> {app_identified}

<b>📝 Extracted Text:</b>
<code>{ocr_text, truncated to 500 chars}</code>

{if visual_red_flags exist:}
<b>👁️ Visual Anomalies:</b>
{bulleted visual red flags}

━━━━━━━━━━━━━━━━━━━━

{standard scam verdict block from 2.1}
```

**Concrete example:**

```
📸 SCREENSHOT ANALYSIS

📱 App Detected: Browser (fake bank page)

📝 Extracted Text:
State Bank of India - KYC Update
Your account will be suspended. Enter Account No, IFSC, ATM PIN, and OTP to verify.
URL: sbi-kyc-verify.xyz

👁️ Visual Anomalies:
• SBI logo is pixelated and slightly wrong shade of blue
• Font is Arial instead of SBI's official font
• URL bar shows suspicious domain

━━━━━━━━━━━━━━━━━━━━

🚨 SCAM DETECTED — 95% confident

Type: Bank KYC / Account Freeze
Risk: 🔴 CRITICAL

⚠️ Red Flags:
• Fake SBI webpage detected
• Asks for ATM PIN and OTP on a webpage
• Domain sbi-kyc-verify.xyz is not the official SBI domain
• Visual analysis confirms fake UI elements

✅ What to do:
🚨 DO NOT enter any details on this page. Close it immediately. The real SBI website is sbi.co.in. Report to 1930.

Report to 1930 helpline | cybercrime.gov.in
```

**Step 8: Handle the OCR text display**
- Use Telegram's `<code>` tag for the OCR text — it renders in monospace, making it easy to distinguish from the bot's commentary
- If OCR text is very long (> 500 chars), truncate and add: "...(truncated. Full text analyzed.)"
- If OCR extracted no text (image is a photo, not a screenshot) → reply: "No text found in this image. This appears to be a photo, not a screenshot. Please forward the actual scam message or screenshot."

### Edge Cases

| Edge Case | Behavior |
|-----------|----------|
| Screenshot is of a legitimate bank app | Visual analysis should say `looks_legitimate: true`. Verdict should be `is_scam: false`. |
| Screenshot contains multiple messages (long WhatsApp chat) | OCR will extract all of them. The backend analyzes the full block. |
| Screenshot is partially cropped | OCR will work on what's visible. Add note: "Image appears cropped — some context may be missing." |
| Screenshot is of a QR code | Flag: "⚠️ This image contains a QR code. NEVER scan a QR code to RECEIVE money. QR codes are only for SENDING payments." |
| Screenshot is a meme or joke | Text classifier should return `is_scam: false`. |
| Image is a photo of a physical letter or document | OCR will extract the text. Analyze normally. Add note: "This appears to be a photo of a physical document." |
| Screenshot has dark mode vs light mode | Gemini Vision handles both. No special handling needed. |
| User sends an image with no scam context (e.g., a selfie) | OCR returns nothing meaningful. Reply: "No suspicious content detected in this image. Forward me actual scam messages or screenshots for analysis." |

---

## 2.4 · URL Handler

### File Location
`bot/handlers/url_handler.py`

### What It Does
When a user sends a bare URL (or a message containing only a URL), the bot runs a focused domain analysis and returns the domain age, lookalike check, and risk score.

### Logic Flow

**Step 1: Detect URLs in the message**
- This handler should be registered BEFORE the general text handler so it catches URL-only messages first
- Use a regex to check if the message text is primarily a URL:
  - Pattern: `^(https?://)?(www\.)?[a-zA-Z0-9-]+\.[a-zA-Z]{2,}(/\S*)?$`
  - If the message matches this pattern (with optional surrounding whitespace) → route to URL handler
  - If the message contains a URL AND other text → route to text handler (which will internally call URL analyzer)

**Step 2: Extract and normalize the URL**
- Add `https://` if no protocol is present
- Strip trailing whitespace and punctuation
- Handle common user errors:
  - `www.sbi-kyc-verify.xyz` → `https://www.sbi-kyc-verify.xyz`
  - `sbi-kyc-verify.xyz/update?ref=123` → `https://sbi-kyc-verify.xyz/update?ref=123`

**Step 3: Send "analyzing" feedback**
- "🔗 Checking domain: {domain}..."

**Step 4: Call the backend**
- `POST {BACKEND_URL}/analyze` with:
  - `url`: the normalized URL
  - `input_type`: `url`
- Timeout: 10 seconds (URL analysis is fast, mostly WHOIS)

**Step 5: Format the Telegram reply**

**Format for URL analysis:**

```
🔗 <b>DOMAIN ANALYSIS</b>

<b>URL:</b> <code>{url}</code>
<b>Domain:</b> {domain}
<b>TLD:</b> {tld} {tld_emoji}

<b>📅 Domain Age:</b> {age_days} days {age_emoji}
<b>🏢 Registrar:</b> {registrar}
<b>🔒 HTTPS:</b> {https_emoji} {yes/no}

<b>🎯 Lookalike Check:</b>
{lookalike_result}

<b>⚠️ Risk Score:</b> {risk_bar} {risk_percent}%

{red flags if any}

{recommended action}
```

**Concrete example (suspicious):**

```
🔗 DOMAIN ANALYSIS

URL: http://sbi-kyc-verify.xyz/update
Domain: sbi-kyc-verify.xyz
TLD: .xyz 🚩

📅 Domain Age: 4 days 🚨
🏢 Registrar: Namecheap
🔒 HTTPS: ❌ No

🎯 Lookalike Check:
⚠️ Contains brand name "sbi" but is NOT the official SBI domain (sbi.co.in)

⚠️ Risk Score: 🟥🟥🟥🟥⬜ 75%

Red Flags:
• Domain registered only 4 days ago
• Uses suspicious TLD .xyz
• No HTTPS encryption
• URL path contains: kyc, verify, update

🚨 DO NOT visit this link. The real SBI website is sbi.co.in.
```

**Concrete example (legitimate):**

```
🔗 DOMAIN ANALYSIS

URL: https://www.sbi.co.in
Domain: sbi.co.in
TLD: .co.in ✅

📅 Domain Age: 8,765 days ✅
🏢 Registrar: National Informatics Centre
🔒 HTTPS: ✅ Yes

🎯 Lookalike Check:
✅ This IS the official SBI domain

⚠️ Risk Score: 🟩⬜⬜⬜⬜ 2%

✅ This domain appears legitimate.
```

### Age Emoji Mapping

| Age | Emoji | Label |
|-----|-------|-------|
| < 7 days | 🚨 | "Brand new — extremely suspicious" |
| 7–30 days | ⚠️ | "Very new — suspicious" |
| 30–90 days | 🟡 | "New — caution" |
| 90–365 days | 🟢 | "Established" |
| > 1 year | ✅ | "Well-established" |

### TLD Emoji Mapping

| TLD Type | Emoji |
|----------|-------|
| Legitimate (.com, .co.in, .in, .gov.in, .org) | ✅ |
| Neutral (.net, .info, .biz) | 🟡 |
| Suspicious (.xyz, .top, .tk, .click, .buzz) | 🚩 |

### Edge Cases

| Edge Case | Behavior |
|-----------|----------|
| URL is a URL shortener (bit.ly, tinyurl) | Reply: "⚠️ This is a shortened URL. The real destination is hidden. Shortened URLs are commonly used by scammers. Do NOT click unless you trust the sender." |
| URL is an IP address | Reply: "🚨 This link uses an IP address instead of a domain name. This is a strong scam indicator. Legitimate services always use domain names." |
| URL returns a 404 or is unreachable | Note: "Domain exists but the page is unreachable. This could mean the scam site was taken down." |
| URL is a Google Docs or Forms link | Flag: "⚠️ Scammers sometimes use Google Forms to collect personal information. Verify who created this form before entering any data." |
| User sends multiple URLs | Analyze all of them. Show the highest-risk URL first. |

---

## 2.5 · Inline Quick-Check

### File Location
`bot/handlers/command_handler.py` (add to existing command handlers)

### What It Does
Provides a `/check` command for quick inline analysis without needing to forward a message. Useful when the user wants to paste a suspicious text directly.

### Logic Flow

**Step 1: Parse the command**
- Trigger on `CommandHandler("check", check_handler)`
- Extract the text after `/check`: `context.args` gives you a list of words
- Join them: `text = " ".join(context.args)`

**Step 2: Validate**
- If no text after `/check` → reply: "Usage: `/check <paste suspicious message here>`\n\nExample: `/check Dear Customer, your SBI account will be blocked...`"
- If text is too short (< 10 chars) → reply: "Please provide more text for accurate analysis."

**Step 3: Analyze**
- Same flow as text handler (2.1): call `POST /analyze` with the text
- Use the same formatting for the reply

**Step 4: Reply**
- Since this is a command (not a forwarded message), reply directly in the chat
- Use the same verdict format as 2.1

### Additional Commands to Register

**`/start`** (already exists from Phase 0, but enhance it):
```
🛡️ <b>Welcome to Mirage — Your AI Scam Shield</b>

I protect you from scams by analyzing messages, voice notes, screenshots, and URLs.

<b>How to use:</b>
1️⃣ Forward me any suspicious message
2️⃣ I'll tell you if it's a scam
3️⃣ I'll explain exactly WHY it's a scam

<b>What I can check:</b>
📝 Text messages (WhatsApp, SMS, email)
🎤 Voice notes and call recordings
📸 Screenshots of fake websites
🔗 Suspicious URLs and links

<b>Commands:</b>
/check <text> — Quick scam check
/elder — Toggle Elder Mode
/family — Set up family alerts
/help — Detailed help

<b>Try it now!</b> Forward me a suspicious message 👇
```

**`/help`**:
```
🛡️ <b>Mirage Help</b>

<b>Forwarding messages:</b>
• Long-press any message in WhatsApp/Telegram
• Select "Forward"
• Choose "Mirage Scam Shield"
• I'll analyze it instantly

<b>Voice notes:</b>
• Forward any suspicious voice note
• I'll transcribe it and check for AI-generated voices

<b>Screenshots:</b>
• Take a screenshot of any suspicious page
• Send it to me
• I'll read the text and check for fake UI

<b>URLs:</b>
• Paste any suspicious link
• I'll check the domain age and legitimacy

<b>Commands:</b>
/check <text> — Quick analysis
/elder — Elder Mode (voice replies, big text)
/family — Family alert setup
/help — This message

<b>Privacy:</b>
• I don't store your messages
• Analysis happens in real-time
• Your data is never shared

Report scams: 📞 1930 | 🌐 cybercrime.gov.in
```

**`/family`** (preview — full implementation in 2.7):
```
👨‍👩‍👧‍👦 <b>Family Alert Setup</b>

When I detect a high-risk scam, I can automatically alert your family members.

To set up:
1️⃣ Create a Telegram group with your family
2️⃣ Add me (@mirage_scam_bot) to the group
3️⃣ Send /family in the group to link it

I'll alert the group whenever a family member receives a critical scam.

<i>Feature coming soon! For now, forward this bot to your family members.</i>
```

### Edge Cases

| Edge Case | Behavior |
|-----------|----------|
| User types `/check` with no arguments | Show usage instructions with an example |
| User types `/check` with a URL | Detect it's a URL, route to URL analysis instead of text |
| User types `/check` with Hindi text | Works the same as text handler — backend handles Hindi |
| User types `/check` inside a group chat | Reply in the group. Add a note: "Tip: You can also add me to your family group for automatic alerts." |

---

## 2.6 · Elder Mode Toggle

### File Location
`bot/handlers/elder_mode.py` + `bot/utils/elder_formatter.py`

### What It Does
Toggles a special mode designed for elderly users who may have difficulty reading small text, understanding technical jargon, or navigating complex interfaces. In Elder Mode, the bot responds with voice messages (in Hindi or Tamil), uses simpler language, larger formatting, and automatically alerts family members.

### Logic Flow

**Step 1: Toggle command**
- Trigger on `CommandHandler("elder", elder_handler)`
- Check the user's current Elder Mode status (stored in a simple in-memory dict or Supabase)
- Toggle it: if currently off → turn on, if on → turn off
- Reply with confirmation:

**When turning ON:**
```
👴 <b>ELDER MODE ACTIVATED</b>

From now on:
✅ I will send voice replies (easier to listen)
✅ I will use simple language
✅ I will use bigger text
✅ I will alert your family if I detect a scam

To turn off: type /elder again

🙏 Stay safe! Forward me any suspicious message.
```

**When turning OFF:**
```
👴 Elder Mode deactivated.
I'll go back to normal text replies.
Type /elder to re-enable.
```

**Step 2: Store the preference**
- Use a simple dict: `elder_mode_users = {user_id: {"enabled": True, "language": "hi"}}`
- When the user enables Elder Mode, ask for their preferred language:
  - "Which language would you like voice replies in?\n1️⃣ Hindi\n2️⃣ Tamil\n3️⃣ English"
  - Handle the reply with a `ConversationHandler` or a simple state machine
  - Default to Hindi if no response within 30 seconds

**Step 3: Modify all handlers for Elder Mode**

When Elder Mode is active, every handler (text, voice, image, URL) should:

**A. Simplify the text response:**
- Remove technical terms like "domain", "TLD", "WHOIS", "synthetic voice score"
- Use simple, direct language
- Add more emojis for visual clarity
- Make the verdict the VERY FIRST thing in the message (don't bury it)

**Elder Mode text format:**
```
🚨🚨🚨 <b>यह SCAM है! धोखा है!</b> 🚨🚨🚨

<b>क्या करें:</b>
❌ इस लिंक पर क्लिक मत करो
❌ कोई OTP मत दो
❌ पैसे मत भेजो
✅ अपने बेटे/बेटी को बताओ
✅ 1930 पर कॉल करो

<b>क्यों:</b>
यह मैसेज आपके बैंक से नहीं है। कोई ठग आपके पैसे चुराना चाहता है।

📞 हेल्पलाइन: 1930
```

**B. Generate a voice reply:**
- After sending the text, ALSO send a voice message with the same content
- Use Edge-TTS to generate the audio:
  1. Take the simplified text (in Hindi/Tamil/English)
  2. Strip all emojis and Markdown formatting (TTS can't read them)
  3. Generate audio with Edge-TTS:
     - Hindi: `hi-IN-SwaraNeural` (female) or `hi-IN-MadhurNeural` (male)
     - Tamil: `ta-IN-PallaviNeural` (female) or `ta-IN-ValluvarNeural` (male)
     - English: `en-IN-NeerjaNeural` (female)
  4. Save the audio to a temp file
  5. Send it via `context.bot.send_voice(chat_id=chat_id, voice=open(temp_file, 'rb'))`
  6. Delete the temp file

**Voice reply script template (Hindi):**
```
Namaste. Mirage scam shield ki taraf se chetavni.
Yeh message ek scam hai. Dhokha hai.
Is link par click mat kijiye. Koi OTP mat dijiye. Paise mat bhejiye.
Apne parivaar ko bataiye. 1930 par call kijiye.
Surakshit rahiye.
```

**Voice reply script template (Tamil):**
```
Vanakkam. Mirage scam shield ilirundhu echcharikkai.
Idhu oru scam. Mosam.
Indha link-ai click seyyadheenga. OTP kudukkadheenga. Panam anuppadheenga.
Ungal kudumbaththinai theriyapaduthunga. 1930-ku call pannunga.
Paathukonga.
```

**C. Auto-trigger family alert:**
- In Elder Mode, the threshold for family alerts drops from 85% to 60%
- Any scam with confidence > 60% triggers an alert to the family group (see 2.7)

### Edge Cases

| Edge Case | Behavior |
|-----------|----------|
| User enables Elder Mode but doesn't choose a language | Default to Hindi after 30 seconds |
| Edge-TTS fails to generate audio | Fall back to text-only reply. Add note: "Voice reply unavailable. Showing text instead." |
| User is in Elder Mode and sends a voice note | Analyze normally, but reply with voice + simplified text |
| User is in Elder Mode and sends an image | Analyze normally, but reply with voice + simplified text. The voice should describe what was found: "Aapne jo screenshot bheja hai, usme ek fake bank website dikhai de rahi hai..." |
| Multiple family members have Elder Mode | Each user's preference is independent |

---

## 2.7 · Family Alert Webhook

### File Location
`bot/handlers/family_alert.py` + `bot/utils/alert_dispatcher.py`

### What It Does
When the bot detects a high-confidence scam (confidence > 85%, or > 60% in Elder Mode), it automatically sends an alert to a pre-registered family Telegram group. This ensures that even if the elderly person doesn't understand the warning, their family knows.

### Setup Flow

**Step 1: Family group registration**
- User creates a Telegram group with family members
- User adds the Mirage bot to the group
- User sends `/family` in the group
- Bot detects the group context (`message.chat.type == "group"` or `"supergroup"`)
- Bot saves the group's `chat_id` and links it to the user's `user_id`
- Reply in the group: "✅ This group is now linked for scam alerts. When any family member receives a high-risk scam, I'll alert everyone here."

**Step 2: Link individual users to the family group**
- When a user sends a message to the bot (in private chat), check if they're linked to a family group
- If not linked, and the scam confidence is high, prompt: "⚠️ This is a serious scam. Would you like me to alert your family? Create a Telegram group, add me, and send /family to set it up."
- For the hackathon demo: pre-link a test user to a test group

**Step 3: Store the mapping**
- Simple dict or Supabase table: `family_alerts = {user_id: group_chat_id}`
- For the hackathon, an in-memory dict is fine

### Alert Logic

**When to trigger:**
- After every analysis, check:
  1. Is `verdict.is_scam == true`?
  2. Is `verdict.confidence > 0.85`? (or > 0.60 if user is in Elder Mode)
  3. Is the user linked to a family group?
- If all three → send alert

**Alert message format:**

```
🚨 <b>FAMILY SCAM ALERT</b> 🚨

<b>Who:</b> {user_first_name}
<b>When:</b> {timestamp}
<b>Threat:</b> {scam_type_readable}
<b>Confidence:</b> {confidence_percent}%
<b>Risk:</b> {risk_emoji} {risk_level_upper}

<b>What happened:</b>
{user_first_name} received a {scam_type_readable} scam message. {one_sentence_summary}

<b>⚠️ Action needed:</b>
Please check on {user_first_name} and make sure they have NOT:
❌ Clicked any links
❌ Shared any OTP
❌ Made any payment
❌ Shared any personal details

<b>📞 If money was sent:</b>
Call 1930 immediately and report to cybercrime.gov.in

<i>This alert was sent by Mirage Scam Shield.</i>
```

**Concrete example:**

```
🚨 FAMILY SCAM ALERT 🚨

Who: Dad (Ramesh)
When: 15 Jan 2025, 3:42 PM
Threat: Bank KYC / Account Freeze
Confidence: 92%
Risk: 🔴 CRITICAL

What happened:
Dad received a fake SBI message claiming his account will be blocked. The message contains a link to a fake website registered 4 days ago and asks for his ATM PIN and OTP.

⚠️ Action needed:
Please check on Dad and make sure he has NOT:
❌ Clicked any links
❌ Shared any OTP
❌ Made any payment
❌ Shared any personal details

📞 If money was sent:
Call 1930 immediately and report to cybercrime.gov.in

This alert was sent by Mirage Scam Shield.
```

### Alert Throttling

To avoid spamming the family group:
- Don't send more than **3 alerts per hour** per user
- If the same scam type is detected within 10 minutes, skip the alert (user is probably forwarding the same message multiple times)
- Track alert timestamps in a simple dict: `alert_history = {user_id: [timestamp1, timestamp2, ...]}`
- Clean up entries older than 1 hour periodically

### Edge Cases

| Edge Case | Behavior |
|-----------|----------|
| Bot is removed from the family group | The next alert attempt will fail with a Telegram API error. Catch it, log it, and notify the user privately: "I can no longer send alerts to your family group. Please add me back." |
| Family group is very active | The alert might get buried. Pin the alert message using `context.bot.pin_chat_message()` if the bot has admin rights |
| User doesn't want family alerts for low-risk scams | Only alert for high/critical risk. Never alert for medium or low. |
| Multiple family members use the bot | Each user can be linked to the same group. Alerts will show who specifically received the scam. |
| Alert contains sensitive information | The alert only shows the scam type and summary, NOT the full message content. Don't leak the user's private messages to the group. |

---

## Bot Handler Registration Order

The order matters in `python-telegram-bot` because the first matching handler wins. Register in this order:

```
1. CommandHandler("start")      → /start
2. CommandHandler("help")       → /help
3. CommandHandler("check")      → /check <text>
4. CommandHandler("elder")      → /elder
5. CommandHandler("family")     → /family
6. MessageHandler(filters.PHOTO | filters.Document.IMAGE)  → image handler
7. MessageHandler(filters.VOICE | filters.AUDIO)           → voice handler
8. MessageHandler(filters.TEXT & ~filters.COMMAND & URL_REGEX) → URL handler
9. MessageHandler(filters.TEXT & ~filters.COMMAND)         → text handler (catch-all)
```

**Why this order:**
- Commands first (they're explicit)
- Media types before text (a photo message also has a caption which is text)
- URL handler before general text (URL-only messages should get focused domain analysis)
- General text last (catch-all)

---

## File Summary for Phase 2

| File | Purpose | Lines (estimate) |
|------|---------|-----------------|
| `bot/main.py` | Bot entry point, handler registration | ~80 |
| `bot/handlers/text_handler.py` | Text message analysis | ~120 |
| `bot/handlers/voice_handler.py` | Voice note analysis | ~130 |
| `bot/handlers/image_handler.py` | Screenshot analysis | ~120 |
| `bot/handlers/url_handler.py` | URL domain analysis | ~100 |
| `bot/handlers/command_handler.py` | /start, /help, /check, /family | ~150 |
| `bot/handlers/elder_mode.py` | Elder Mode toggle + language selection | ~100 |
| `bot/handlers/family_alert.py` | Family group registration | ~80 |
| `bot/utils/api_client.py` | HTTPX wrapper for backend calls | ~60 |
| `bot/utils/formatter.py` | Telegram HTML formatting | ~150 |
| `bot/utils/elder_formatter.py` | Simplified Elder Mode formatting + TTS | ~120 |
| `bot/utils/alert_dispatcher.py` | Family alert logic + throttling | ~90 |
| `bot/utils/constants.py` | Emoji mappings, readable names | ~40 |
| `bot/requirements.txt` | Dependencies | ~5 |

**Total estimated:** ~1,345 lines of Python

---

## Phase 2 Completion Checklist

Validated 2026-10-09. Every item is backed by an automated test in
`bot/tests/` (128 passed, ruff clean) unless marked ⏳ — those need a live
bot token (to be supplied later).

```
[x] /start returns a clear welcome message with instructions
[x] /help returns detailed usage guide
[x] /check <text> analyzes pasted text and returns verdict
[x] /elder toggles Elder Mode on/off
[x] /elder asks for language preference (Hindi/Tamil/English)
[x] Text handler: forwarded text message returns formatted scam verdict
[x] Text handler: legitimate messages return "likely legitimate" verdict
[x] Text handler: uncertain messages return "proceed with caution" verdict
[~] Text handler: Hindi messages are analyzed correctly
    → Backend handles Hindi (Llama/Gemini); reply stays English per scope.
[x] Text handler: "analyzing..." feedback appears instantly
[x] Text handler: verdict replaces the "analyzing..." message (edit, not new)
[x] Voice handler: voice note is downloaded and transcribed
[x] Voice handler: transcript + scam verdict + synthetic voice score displayed
[x] Voice handler: voice authenticity bar is visually clear (5 buckets)
[x] Image handler: screenshot is downloaded and OCR'd
[x] Image handler: extracted text + visual analysis + verdict displayed
[x] Image handler: QR code images are flagged
[x] URL handler: bare URL triggers domain analysis
[x] URL handler: domain age, lookalike, TLD, HTTPS all displayed
[x] URL handler: legitimate domains show green, suspicious show red
[x] Elder Mode: text replies are simplified (no jargon, verdict first)
[x] Elder Mode: voice replies are generated in Hindi via Edge-TTS
[x] Elder Mode: voice replies are generated in Tamil via Edge-TTS
[x] Elder Mode: family alert threshold drops to 60%
[x] Family alert: /family in a group links the group
[x] Family alert: high-confidence scam triggers group notification
[x] Family alert: alert message shows who, what, when, and action needed
[x] Family alert: throttling prevents more than 3 alerts/hour
[x] Family alert: sensitive message content is NOT leaked to group
[x] Error handling: backend down → graceful error message
[x] Error handling: file too large → clear error message
[x] Error handling: unsupported file type → clear error message
[x] Error handling: empty message → helpful prompt
[~] Bot runs continuously without crashing
    → All handlers wrapped in error guards; 🏳 needs live-token soak test
[~] Bot handles 5+ concurrent users without errors
    → Async httpx + per-handler isolation; 🏳 needs live-token load check
```

### Test Results Summary (2026-10-09)

| Suite | Tests | Result |
|-------|-------|--------|
| bot/tests/test_formatter.py | 40 | PASS |
| bot/tests/test_api.py | 19 | PASS |
| bot/tests/test_handlers.py | 32 | PASS |
| bot/tests/test_elder_family.py | 37 | PASS |
| **Bot total** | **128** | **PASS** |
| backend/tests (regression) | 140 passed, 2 skipped | PASS |
| ruff (bot + backend) | — | clean |

### Live Smoke Test (pending bot token)

When the Telegram token is ready:

```
1. bot/.env → TELEGRAM_BOT_TOKEN=<token>
2. backend: cd backend && uv run uvicorn app.main:app --reload --port 8000
   (LLM: add GROQ_API_KEY/GEMINI_API_KEY to backend/.env, or pull an
    Ollama model — without one, verdicts fall back to low-confidence)
3. bot:     cd bot && uv run python main.py
4. In Telegram: /start → /check <scam text> → forward a voice note →
   send a screenshot → paste a bare URL → /elder → pick language →
   /family inside a family group → forward a >85% scam → confirm alert
```

**When every box is checked (incl. ⏳ items), Phase 2 is done. Move to Phase 3 (Fire Drill) or Phase 4 (Guardian).**

---

Ready for the next phase? Phase 3 (Scam Fire Drill — the demo centerpiece) is the most complex and the most important for winning. Say the word.