# Phase 1 — Scam Analysis Engine (Complete Deep Dive)

---

## Architecture Overview

```
                    POST /analyze
                         │
            ┌────────────▼────────────┐
            │   Multi-Modal Orchestrator │  ← 1.6
            │   (detect input type)      │
            └────┬───────┬───────┬───┬──┘
                 │       │       │   │
          ┌──────▼──┐ ┌──▼───┐ ┌▼───▼────┐
          │  Text    │ │ URL  │ │  Image   │  ← 1.1, 1.2, 1.3
          │Classifier│ │Analyzer│ │Analyzer │
          └──────┬──┘ └──┬───┘ └┬───┬────┘
                 │       │      │   │
                 │       │      │   │ (OCR → feeds back to
                 │       │      │   │  Text + URL analyzers)
                 │       │      │   │
          ┌──────▼───────▼──────▼───▼────┐
          │       Audio Analyzer          │  ← 1.4
          │  (Whisper → Text Classifier   │
          │   + Resemblyzer voice check)  │
          └──────────────┬───────────────┘
                         │
            ┌────────────▼────────────┐
            │   Evidence Trail Builder │  ← 1.5
            │   (merge, score, report) │
            └────────────┬────────────┘
                         │
                    ScamVerdict
```

---

## 1.1 · Text Scam Classifier

### File Location
`backend/app/services/scam_analyzer.py`

### What It Does
Takes raw message text and returns a structured scam verdict using Groq's Llama 3.3 70B with forced JSON output.

### System Prompt (exact — copy this into your code)

```
You are Mirage, an expert scam detection AI specializing in Indian financial and social engineering scams.

Your job: analyze the given message and determine if it is a scam.

RULES:
1. Be conservative. Only flag as scam if there are clear indicators.
2. Legitimate bank messages DO exist. Banks DO send OTP alerts, transaction confirmations, and KYC reminders. The difference is:
   - Real banks NEVER ask you to click a link and enter your OTP on a webpage
   - Real banks NEVER ask you to call a mobile number for verification
   - Real banks NEVER create extreme urgency ("your account will be blocked in 30 minutes")
   - Real bank URLs end in the bank's official domain (sbi.co.in, hdfcbank.com, icicibank.com)
3. Consider context. A message from "Mom" saying "send me ₹5000" is probably real. A message from "Mom" saying "I'm in the hospital, send ₹50,000 to this UPI immediately, don't tell Dad" is suspicious.
4. Indian scam types to watch for:
   - Bank KYC / account freeze scams
   - UPI payment reversal scams ("you received ₹10,000 by mistake, send it back")
   - FedEx / customs / parcel scams
   - Job offer / work-from-home scams
   - Lottery / prize scams
   - Relative in distress (voice clone scams)
   - OTP phishing
   - Investment / crypto / trading scams
   - Romance scams
   - Electricity bill / disconnection scams
   - RBI / police / CBI impersonation scams
   - QR code scams ("scan this to receive payment")

OUTPUT FORMAT — respond ONLY with valid JSON, no markdown, no explanation:
{
  "is_scam": true/false,
  "confidence": 0.0-1.0,
  "scam_type": "bank_kyc" | "upi_reversal" | "fedex" | "job_offer" | "lottery" | "relative_distress" | "otp_phishing" | "investment" | "romance" | "electricity" | "impersonation" | "qr_code" | "unknown" | null,
  "risk_level": "low" | "medium" | "high" | "critical",
  "red_flags": ["string array of specific red flags found in this message"],
  "stages_detected": ["hook" | "authority" | "isolation" | "urgency" | "payment"],
  "summary": "One paragraph explaining your verdict in simple English",
  "recommended_action": "Ignore and delete" | "Block the sender" | "Do NOT click any links" | "Call your bank on the official number" | "Report to 1930 helpline" | "This appears legitimate"
}
```

### User Prompt Template

```
Analyze this message for scam indicators:

---
{message_text}
---

Sender context (if available): {sender_info}
```

### How to Call Groq (logic flow)

1. Construct the messages array: `[{role: "system", content: SYSTEM_PROMPT}, {role: "user", content: user_prompt}]`
2. Call Groq chat completions with:
   - `model`: `llama-3.3-70b-versatile`
   - `response_format`: `{"type": "json_object"}` ← this forces valid JSON output
   - `temperature`: `0.1` ← low temperature for consistent, deterministic analysis
   - `max_tokens`: `1000`
3. Parse the JSON response
4. Validate all required fields exist. If any are missing, fill with defaults (`is_scam: false`, `confidence: 0.0`, etc.)
5. Return the parsed `ScamVerdict` Pydantic model

### Confidence Calibration Logic

The LLM will output a confidence number, but LLMs are notoriously poorly calibrated. Apply these adjustments in your code:

| Condition | Adjustment |
|-----------|-----------|
| LLM says `is_scam: true` AND `confidence > 0.8` AND URL analysis also flags the domain | Keep confidence as-is (high confidence confirmed by multiple signals) |
| LLM says `is_scam: true` BUT no URL and no phone number in the message | Reduce confidence by 0.15 (text-only signals are weaker) |
| LLM says `is_scam: false` BUT URL analysis flags a suspicious domain | Override to `is_scam: true`, set confidence to 0.7 (URL signals are strong) |
| Message is very short (< 10 words) | Cap confidence at 0.6 (not enough context) |
| Message contains a known legitimate bank template (e.g., "Your a/c XX1234 is debited with Rs") | Reduce scam confidence by 0.3 |

### Risk Level Mapping

| Confidence Range | is_scam | Risk Level |
|-----------------|---------|------------|
| 0.0 – 0.3 | false | low |
| 0.3 – 0.5 | false | low |
| 0.5 – 0.7 | true | medium |
| 0.7 – 0.85 | true | high |
| 0.85 – 1.0 | true | critical |

### 20 Test Samples (with expected outputs)

Use these to validate your classifier. Store them in `backend/tests/test_samples.json`.

**Sample 1 — Bank KYC Scam (critical)**
```
Dear Customer, your SBI account will be BLOCKED within 24 hours due to incomplete KYC. Click here to update immediately: http://sbi-kyc-verify.xyz/update. Enter your account number, ATM PIN, and OTP to verify. SBI Helpline: 9876543210
```
**Expected:** `is_scam: true`, `confidence: 0.95`, `scam_type: "bank_kyc"`, `risk_level: "critical"`, red_flags: ["asks for ATM PIN", "asks for OTP", "suspicious domain sbi-kyc-verify.xyz", "extreme urgency 24 hours", "helpline is a mobile number"]

**Sample 2 — UPI Reversal Scam (high)**
```
Hi, I accidentally sent ₹15,000 to your UPI ID. Please send it back to my UPI: scammer@ybl immediately. I'm in urgent need. God bless you.
```
**Expected:** `is_scam: true`, `confidence: 0.85`, `scam_type: "upi_reversal"`, `risk_level: "high"`

**Sample 3 — FedEx Parcel Scam (high)**
```
FedEx India: Your parcel #FX8834521 is held at customs. A fine of ₹2,499 is pending. Pay now to avoid return: https://fedex-india-customs.top/pay. Track: https://fedex-india-customs.top/track
```
**Expected:** `is_scam: true`, `confidence: 0.92`, `scam_type: "fedex"`, `risk_level: "high"`, red_flags: ["suspicious domain .top TLD", "not official fedex.com domain", "asks for payment via link"]

**Sample 4 — OTP Phishing (critical)**
```
Your OTP for transaction of ₹49,999 is 847293. Do NOT share this with anyone. If you did not initiate this, call 1800-123-4567 immediately.
```
**Expected:** `is_scam: false`, `confidence: 0.3`, `scam_type: null`, `risk_level: "low"` ← This is a LEGITIMATE bank OTP message. The key differentiator is it says "Do NOT share" and provides a toll-free number.

**Sample 5 — Job Offer Scam (high)**
```
Congratulations! You've been selected for a work-from-home position at Amazon India. Earn ₹5,000-₹15,000 daily by liking YouTube videos. No experience needed. WhatsApp us at +91-98765-43210 to start. Registration fee: ₹999 (refundable).
```
**Expected:** `is_scam: true`, `confidence: 0.90`, `scam_type: "job_offer"`, `risk_level: "high"`, red_flags: ["unrealistic daily income", "asks for registration fee", "task is liking YouTube videos", "WhatsApp contact instead of official channel"]

**Sample 6 — Lottery Scam (high)**
```
CONGRATULATIONS!!! Your mobile number has won ₹25,00,000 in the Kaun Banega Crorepati Lucky Draw 2024! To claim your prize, send your bank details and pay ₹5,000 processing fee to UPI: kbc-prize@paytm. Contact: 9876543210. Offer valid 48 hours only!
```
**Expected:** `is_scam: true`, `confidence: 0.95`, `scam_type: "lottery"`, `risk_level: "critical"`

**Sample 7 — Relative in Distress (high)**
```
Mom, I'm in trouble. I met with an accident near the airport. I need ₹50,000 for hospital admission immediately. Please send to this UPI: emergency.help@ybl. Don't tell Dad, he'll panic. I'll call you later, my phone is about to die.
```
**Expected:** `is_scam: true`, `confidence: 0.80`, `scam_type: "relative_distress"`, `risk_level: "high"`, red_flags: ["isolation tactic don't tell Dad", "extreme urgency", "unusual UPI ID for a family member", "phone dying prevents verification"]

**Sample 8 — Legitimate Bank Transaction Alert (low)**
```
SBI: A/c XX1234 debited with Rs 1,250.00 on 15/01/25 at AMAZON PAY. Avl Bal: Rs 45,678.90. Not you? Call 1800-11-2211 or SMS BLOCK to 567676.
```
**Expected:** `is_scam: false`, `confidence: 0.1`, `risk_level: "low"`, red_flags: []

**Sample 9 — Electricity Bill Scam (high)**
```
URGENT: Your electricity connection (Consumer No: 456789123) will be DISCONNECTED tonight at 9 PM due to unpaid bill of ₹3,847. Pay immediately to avoid disconnection: https://mseb-payment-portal.xyz/pay. Reference: EB2024-8834.
```
**Expected:** `is_scam: true`, `confidence: 0.88`, `scam_type: "electricity"`, `risk_level: "high"`

**Sample 10 — RBI Impersonation (critical)**
```
This is a message from the Reserve Bank of India. Your PAN card is linked to illegal transactions totaling ₹45,00,000. A case has been filed against you under Section 420 IPC. Contact CBI Officer Rajesh Kumar on WhatsApp +91-98765-43210 within 2 hours to avoid arrest. Do not inform anyone as this is a confidential investigation.
```
**Expected:** `is_scam: true`, `confidence: 0.97`, `scam_type: "impersonation"`, `risk_level: "critical"`, red_flags: ["RBI does not contact individuals via SMS", "threatens arrest", "WhatsApp contact for CBI", "isolation tactic", "extreme urgency"]

**Sample 11 — QR Code Scam (high)**
```
You have received a payment of ₹10,000 from Flipkart Seller Program! To accept this payment, scan the QR code below using your UPI app and enter your PIN to confirm receipt.
```
**Expected:** `is_scam: true`, `confidence: 0.90`, `scam_type: "qr_code"`, red_flags: ["you never need to enter PIN to RECEIVE money", "QR code scam pattern"]

**Sample 12 — Investment Scam (high)**
```
🚀 Join India's #1 Trading Group! Turn ₹10,000 into ₹1,00,000 in just 7 days with our AI-powered stock tips. 5000+ members earning daily. Join our Telegram group: t.me/surefire-trading-india. Limited seats! Message now: +91-87654-32100
```
**Expected:** `is_scam: true`, `confidence: 0.88`, `scam_type: "investment"`, `risk_level: "high"`

**Sample 13 — Romance Scam (medium)**
```
Hello dear, I am Priya from Mumbai. I saw your profile and felt a connection. I am a doctor working in the army and currently posted in Kashmir. I would love to chat with you. Can we move to WhatsApp? My number is +91-99887-76655. I am looking for a genuine life partner.
```
**Expected:** `is_scam: true`, `confidence: 0.65`, `scam_type: "romance"`, `risk_level: "medium"` ← lower confidence because it could be genuine, but the pattern is classic

**Sample 14 — Legitimate OTP Warning (low)**
```
HDFC Bank: OTP 456789 for Rs 5,000 txn. Valid for 5 mins. NEVER share OTP with anyone. HDFC Bank will NEVER call you to ask for OTP. If not you, call 1800-202-6161.
```
**Expected:** `is_scam: false`, `confidence: 0.05`, `risk_level: "low"`

**Sample 15 — KYC Reminder (legitimate) (low)**
```
Dear Customer, your KYC is due for renewal. Please visit your nearest SBI branch with your Aadhaar and PAN card. This is a mandatory RBI guideline. Ignore if already done. - State Bank of India
```
**Expected:** `is_scam: false`, `confidence: 0.15`, `risk_level: "low"` ← legitimate because it asks to visit a branch, not click a link

**Sample 16 — Fake Police (critical)**
```
THIS IS DELHI POLICE CYBER CELL. Your Aadhaar number 1234-5678-9012 has been used to open a fraudulent bank account. You are required to appear at the Cyber Cell office tomorrow at 10 AM. For online verification, download the app from: https://delhi-police-verification.xyz/app. Case No: CYB/2024/8834.
```
**Expected:** `is_scam: true`, `confidence: 0.93`, `scam_type: "impersonation"`

**Sample 17 — Legitimate Delivery Update (low)**
```
Your Amazon.in order #402-1234567-8901234 has been shipped via BlueDart. Tracking ID: 8834567890. Expected delivery: 17 Jan. Track at: https://www.bluedart.com/tracking
```
**Expected:** `is_scam: false`, `confidence: 0.1`, `risk_level: "low"`

**Sample 18 — Loan Scam (high)**
```
Pre-approved Personal Loan of ₹5,00,000 at 8.5% interest! No CIBIL check required. Instant disbursement. Processing fee: ₹2,500 only. Send your Aadhaar photo and bank details to WhatsApp +91-76543-21098. Offer expires today!
```
**Expected:** `is_scam: true`, `confidence: 0.85`, `scam_type: "unknown"` (or a new "loan" type)

**Sample 19 — Legitimate UPI Confirmation (low)**
```
₹500 sent to Ramesh Kumar (ramesh@okicici) via UPI. Ref: 4567890123. Date: 15/01/25 14:30.
```
**Expected:** `is_scam: false`, `confidence: 0.05`, `risk_level: "low"`

**Sample 20 — SIM Swap Warning (medium)**
```
Dear Customer, a SIM swap request has been initiated for your mobile number 98765XXXXX. If you did not request this, immediately call your telecom operator. Do NOT share any OTP received on your phone.
```
**Expected:** `is_scam: false`, `confidence: 0.25`, `risk_level: "low"` ← this is actually a legitimate warning from a telecom operator, but it could also be a social engineering attempt to make you call a fake number. The classifier should flag it as low risk but note the ambiguity.

### Edge Cases to Handle

| Edge Case | Behavior |
|-----------|----------|
| Empty or whitespace-only text | Return `is_scam: false`, `confidence: 0.0`, `summary: "No content to analyze"` |
| Text longer than 5,000 characters | Truncate to 4,000 chars, add note: "Message truncated for analysis" |
| Text in Hindi or Tamil | Llama 3.3 handles Hindi reasonably well. For Tamil, prepend a note in the user prompt: "The following message is in Tamil. Analyze it for scam indicators." |
| Text contains only a URL, no other content | Route to URL analyzer (1.2) as primary, text classifier as secondary |
| Text contains only an emoji or greeting | Return `is_scam: false`, `confidence: 0.0` |
| Groq API returns invalid JSON | Retry once. If still invalid, return a fallback verdict with `confidence: 0.0` and `summary: "Analysis failed — please try again"` |
| Groq rate limit (429) | Wait 2 seconds, retry once. If still rate-limited, fall back to Gemini |

---

## 1.2 · URL & Domain Analyzer

### File Location
`backend/app/services/url_analyzer.py`

### What It Does
Takes a URL or extracts URLs from text, then runs a multi-signal analysis to determine if the domain is suspicious.

### Logic Flow (step by step)

**Step 1: Extract URLs from text**
- Use a regex to find all URLs in the input text
- Regex pattern: match `http://`, `https://`, or bare domains like `www.example.com`
- Also catch shortened URLs (bit.ly, tinyurl.com, t.co) — flag these as suspicious by default because scammers use them to hide the real destination
- If no URLs found, skip this analyzer (return empty result)

**Step 2: Parse each URL**
- Extract: protocol (http/https), domain, subdomain, path, query parameters, TLD
- Use Python's `urllib.parse.urlparse` for this
- Example: `https://sbi-kyc-verify.xyz/update?ref=123` → domain: `sbi-kyc-verify.xyz`, subdomain: none, path: `/update`, TLD: `.xyz`

**Step 3: WHOIS Lookup**
- Use `python-whois` library to query WHOIS data for the domain
- Extract: creation date, registrar, expiration date, name servers
- Calculate **domain age in days** = (today - creation date)
- **Key signal:** If domain age < 30 days → HIGH suspicion. If < 7 days → CRITICAL.
- Handle WHOIS failures gracefully: some domains block WHOIS queries. If lookup fails, note it as "WHOIS unavailable" but don't treat it as a scam signal alone.
- **Rate limiting:** WHOIS servers will block you if you query too fast. Add a 1-second delay between queries. For the hackathon, you'll rarely hit this.

**Step 4: Lookalike Domain Detection**
- Compare the domain against a known legitimate domains list (see below)
- Use **Levenshtein distance** (edit distance) to find the closest match
- If the Levenshtein distance between the suspicious domain and a legitimate domain is ≤ 3 characters, flag it as a lookalike
- Example: `sbi-kyc-verify.xyz` vs `sbi.co.in` → distance is high, but the substring `sbi` is present → use a secondary check: does the domain *contain* a known brand name as a substring?
- **Better approach:** Check if the domain contains any brand keyword (sbi, hdfc, icici, axis, rbi, amazon, flipkart, fedex, dhl) AND the domain is NOT the official domain → flag as lookalike

**Step 5: TLD Suspicion Check**
- Maintain a list of suspicious TLDs commonly used by scammers
- **Suspicious TLDs:** `.xyz`, `.top`, `.click`, `.link`, `.buzz`, `.tk`, `.ml`, `.ga`, `.cf`, `.gq`, `.pw`, `.cc`, `.ws`, `.info`, `.icu`, `.cam`, `.loan`, `.work`
- **Legitimate TLDs (for Indian context):** `.co.in`, `.in`, `.com`, `.org`, `.gov.in`, `.ac.in`, `.net`
- If the TLD is in the suspicious list → add a red flag

**Step 6: HTTPS Check**
- If the URL uses `http://` (not `https://`) → flag as suspicious
- Exception: some legitimate Indian government sites still use HTTP (unfortunately). Don't overweight this signal.

**Step 7: URL Pattern Analysis**
- Check for these suspicious URL patterns:
  - Contains `@` symbol (URL obfuscation: `http://legit-site.com@evil.com`)
  - Contains IP address instead of domain (e.g., `http://192.168.1.1/login`)
  - Contains excessive subdomains (e.g., `sbi.kyc.verify.update.security.xyz`)
  - Contains keywords in the path: `login`, `verify`, `update`, `secure`, `confirm`, `bank`, `otp`, `kyc` — these are suspicious when combined with a non-official domain
  - URL-encoded characters that decode to something different

**Step 8: Score Aggregation**

| Signal | Weight | Condition |
|--------|--------|-----------|
| Domain age < 7 days | +0.30 | Critical |
| Domain age < 30 days | +0.20 | High |
| Lookalike of known brand | +0.25 | High |
| Suspicious TLD | +0.10 | Medium |
| No HTTPS | +0.05 | Low |
| URL obfuscation (@ or IP) | +0.15 | High |
| Suspicious path keywords | +0.10 | Medium |
| URL shortener | +0.10 | Medium |
| Domain age > 2 years | -0.15 | Legitimacy signal |
| Official domain match | -0.50 | Strong legitimacy |

Final URL risk score = sum of weights, clamped to 0.0–1.0

### Known Legitimate Domains List (Indian context)

Store this as a constant in `backend/app/utils/constants.py`:

```
BANKS:
sbi.co.in, sbi.com, onlinesbi.com
hdfcbank.com, hdfc.com
icicibank.com
axisbank.com
kotak.com
yesbank.in
pnbindia.in
bankofbaroda.in
canarabank.com
idbibank.in
federalbank.co.in

GOVERNMENT:
rbi.org.in
incometax.gov.in
gov.in
nic.in
uidai.gov.in
epassport.gov.in

TELECOM:
jio.com
airtel.in
vodafoneidea.com
bsnl.co.in

E-COMMERCE:
amazon.in, amazon.com
flipkart.com
myntra.com
meesho.com

DELIVERY:
bluedart.com
delhivery.com
dhl.com
fedex.com
indiapost.gov.in
ekartlogistics.com

PAYMENTS:
paytm.com
phonepe.com
razorpay.com
billdesk.com
```

### Output Format

```json
{
  "urls_analyzed": [
    {
      "url": "http://sbi-kyc-verify.xyz/update",
      "domain": "sbi-kyc-verify.xyz",
      "tld": ".xyz",
      "is_suspicious": true,
      "risk_score": 0.75,
      "domain_age_days": 4,
      "registrar": "Namecheap",
      "https": false,
      "is_lookalike": true,
      "lookalike_target": "sbi.co.in",
      "contains_brand_keyword": true,
      "brand_keyword": "sbi",
      "suspicious_tld": true,
      "url_obfuscation": false,
      "suspicious_path_keywords": ["kyc", "verify", "update"],
      "red_flags": [
        "Domain is only 4 days old",
        "Uses suspicious TLD .xyz",
        "Contains brand name 'sbi' but is NOT the official SBI domain",
        "No HTTPS encryption",
        "URL path contains suspicious keywords: kyc, verify, update"
      ]
    }
  ]
}
```

### Edge Cases

| Edge Case | Behavior |
|-----------|----------|
| URL shortener (bit.ly, tinyurl) | Flag as suspicious, note: "Shortened URL — destination hidden" |
| Multiple URLs in one message | Analyze all of them, return the highest risk score as the overall URL risk |
| URL with no TLD (e.g., `localhost`) | Skip, not a real external URL |
| WHOIS returns no creation date | Note "WHOIS data unavailable", don't penalize |
| Domain is an IP address | Flag as highly suspicious (+0.25) |
| URL is in the legitimate domains list | Return `is_suspicious: false`, `risk_score: 0.0` immediately — skip all other checks |

---

## 1.3 · Image / Screenshot Analyzer

### File Location
`backend/app/services/image_analyzer.py`

### What It Does
Takes a screenshot (usually of a WhatsApp message, bank page, or SMS), extracts text via OCR, and feeds it to the text and URL analyzers.

### Logic Flow

**Step 1: Receive and validate the image**
- Accept formats: `.png`, `.jpg`, `.jpeg`, `.webp`
- Max file size: 5 MB (reject larger with a clear error)
- Convert to bytes for the API call

**Step 2: Send to Gemini Vision for OCR + Analysis**

Use a **two-part prompt** to Gemini:

**Part A — OCR Prompt:**
```
Extract ALL text visible in this screenshot exactly as it appears. Include:
- Sender name/number
- Message content
- Any URLs or links
- Any phone numbers
- Any UPI IDs
- Any amounts (₹)
- Timestamps
- App name (WhatsApp, SMS, etc.) if visible

Return the extracted text in a structured format.
```

**Part B — Visual Analysis Prompt:**
```
Analyze this screenshot for visual signs of a scam or fake interface:
1. Does this look like a real bank app/website or a fake one?
2. Are there any blurred or pixelated logos?
3. Are the fonts inconsistent (mixing different font families)?
4. Are the colors slightly off from the real brand?
5. Does the URL bar (if visible) show a suspicious domain?
6. Are there any grammatical errors in the UI text?
7. Does the layout look like a legitimate app or a web page pretending to be an app?

Return your visual analysis as JSON:
{
  "app_identified": "WhatsApp" | "SMS" | "Bank App" | "Browser" | "Unknown",
  "visual_red_flags": ["list of visual anomalies"],
  "looks_legitimate": true/false,
  "confidence": 0.0-1.0
}
```

**Why two prompts instead of one:** Gemini handles focused tasks better. The OCR prompt extracts raw data. The visual prompt analyzes design authenticity. Combining them in one prompt often causes the model to skip one or the other.

**Step 3: Pipeline the OCR output**
- Take the extracted text from Part A
- Feed it to the **Text Scam Classifier** (1.1) → get a `ScamVerdict`
- Extract any URLs from the OCR text → feed to the **URL Analyzer** (1.2) → get `DomainInfo`
- Extract any phone numbers from OCR → flag if they're mobile numbers pretending to be bank helplines (bank helplines are always 1800-xxx-xxxx toll-free)

**Step 4: Merge results**
- Combine the text verdict, URL verdict, and visual analysis into a single `ScamVerdict`
- The visual red flags get added to the overall `red_flags` array
- If the visual analysis says `looks_legitimate: false` AND the text classifier says `is_scam: true`, boost confidence by 0.1 (multiple modalities agree)
- If visual says legitimate but text says scam, trust the text more (scammers often use real-looking screenshots)

### Gemini Vision Call Details

- Model: `gemini-2.0-flash`
- Input: image bytes + text prompt
- Temperature: `0.2`
- Max tokens: `1500`
- The `google-genai` SDK handles image input natively — you pass the image as a `Part` in the content

### Edge Cases

| Edge Case | Behavior |
|-----------|----------|
| Image is too blurry for OCR | Gemini will return partial text. Proceed with what you have, add red flag: "Image quality too low for full analysis" |
| Image contains no text (e.g., a photo) | Return `is_scam: false`, `confidence: 0.0`, `summary: "No text content found in image"` |
| Image is a meme or joke | The text classifier should handle this — memes usually don't match scam patterns |
| Screenshot of a legitimate bank app | Visual analysis should identify the real app, text classifier should return low risk |
| Image contains a QR code | Flag it: "Image contains a QR code — never scan QR codes to RECEIVE money" |
| Multiple messages in one screenshot | OCR will extract all of them. The text classifier should analyze the full block. |

---

## 1.4 · Audio / Voice Note Analyzer

### File Location
`backend/app/services/voice_analyzer.py`

### What It Does
Takes an audio file (voice note, call recording), transcribes it, analyzes the transcript for scam content, and checks if the voice is AI-generated.

### Logic Flow

**Step 1: Receive and validate the audio**
- Accept formats: `.ogg` (Telegram voice notes), `.mp3`, `.wav`, `.m4a`, `.webm`
- Max file size: 10 MB
- Max duration: 60 seconds (Groq Whisper limit is 25 MB, but keep it short for latency)
- If the file is `.ogg` (Telegram's default), you may need to convert it to `.wav` or `.mp3` first using `pydub` or `ffmpeg`. Groq Whisper accepts `.ogg` natively, so this may not be needed — test it.

**Step 2: Transcribe via Groq Whisper**
- Call Groq's audio transcription endpoint
- Parameters:
  - `model`: `whisper-large-v3-turbo`
  - `file`: the audio file
  - `language`: auto-detect (or pass `hi` for Hindi, `ta` for Tamil, `en` for English if you know)
  - `response_format`: `verbose_json` ← this gives you timestamps and segments, not just raw text
- The verbose response includes:
  - `text`: full transcription
  - `segments`: array of `{start, end, text}` — useful for pinpointing which part of the audio contains the scam
  - `language`: detected language

**Step 3: Feed transcript to Text Scam Classifier**
- Take the full transcription text
- Pass it to the **Text Scam Classifier** (1.1)
- Get back a `ScamVerdict`
- The `stages_detected` field is especially useful for audio — you can map stages to timestamps from the Whisper segments

**Step 4: Synthetic Voice Detection (parallel to Step 3)**
- Run **Resemblyzer** on the audio file
- Logic:
  1. Load the audio into a numpy array (sample rate 16kHz, mono)
  2. Generate a voice embedding (d-vector, 256 dimensions)
  3. If the user has a **reference voice embedding** stored (from a family member's real voice), compare the two embeddings using cosine similarity
  4. If no reference is available, use a **heuristic approach**:
     - Analyze the embedding's distance from a cluster of known human voice embeddings (you'd need a small dataset of real voices — for the hackathon, record 5–10 real voice samples and pre-compute their embeddings)
     - If the embedding is an outlier (far from the human cluster), flag as potentially synthetic
  5. Return a `synthetic_voice_score`: 0.0 (definitely human) to 1.0 (definitely AI)

**Simplified heuristic for the hackathon (no reference voice):**
- Resemblyzer embeddings of AI-generated voices tend to have lower variance across segments (AI voices are "too consistent")
- Split the audio into 3-second segments, compute embeddings for each, and calculate the **variance** of the embeddings
- Low variance (< threshold) → likely AI (score > 0.6)
- High variance → likely human (score < 0.3)
- This is a rough heuristic. For the demo, it's good enough.

**Step 5: Merge results**
- Combine the text verdict with the synthetic voice score
- If text says scam AND voice is synthetic → boost confidence to 0.95+ (double confirmation)
- If text says scam BUT voice is human → keep text confidence (could be a real scammer, not AI)
- If text says legitimate BUT voice is synthetic → flag as suspicious (why is an AI voice sending you a legitimate-sounding message?)
- Add the synthetic voice score to the evidence trail

### Output Addition

The audio analyzer adds these fields to the standard `ScamVerdict`:

```json
{
  "transcript": "Hello, this is from your bank's fraud department...",
  "transcript_segments": [
    {"start": 0.0, "end": 3.2, "text": "Hello, this is from your bank"},
    {"start": 3.2, "end": 7.1, "text": "fraud department. Your account has been compromised"}
  ],
  "detected_language": "hi",
  "synthetic_voice_score": 0.78,
  "voice_verdict": "likely_ai_generated",
  "audio_duration_seconds": 15.3
}
```

### Edge Cases

| Edge Case | Behavior |
|-----------|----------|
| Audio is silent or just noise | Whisper returns empty text. Return `is_scam: false`, `confidence: 0.0`, `summary: "No speech detected in audio"` |
| Audio is in a language Whisper can't handle well | Whisper supports 99 languages. Hindi and Tamil work reasonably well. If confidence is low, note: "Transcription may be inaccurate" |
| Audio is very short (< 2 seconds) | Not enough data for voice analysis. Skip synthetic detection, only transcribe |
| Audio is very long (> 60 seconds) | Split into 30-second chunks, transcribe each, concatenate. For synthetic detection, use the first 30 seconds |
| Multiple speakers in the audio | Whisper handles this but doesn't separate speakers. The transcript will be a single block. Note: "Multiple speakers detected — analysis may be less accurate" |
| Background music or noise | Whisper is robust to moderate noise. If transcription quality is poor, note it |

---

## 1.5 · Evidence Trail Builder

### File Location
`backend/app/services/evidence_builder.py`

### What It Does
Takes the raw outputs from all analyzers (text, URL, image, audio) and produces a unified, human-readable scam report with a merged confidence score.

### Logic Flow

**Step 1: Collect all signals**

The orchestrator (1.6) will pass a dictionary of results:
```
{
  "text_verdict": ScamVerdict or None,
  "url_results": list[DomainInfo] or None,
  "image_analysis": {visual_verdict, ocr_text} or None,
  "audio_analysis": {transcript, synthetic_score} or None
}
```

**Step 2: Merge confidence scores**

Use a **weighted average** with a **boost for agreement**:

| Signal | Weight |
|--------|--------|
| Text classifier | 0.40 |
| URL analysis | 0.30 |
| Visual analysis | 0.15 |
| Audio synthetic score | 0.15 |

**Merging formula:**
1. Start with the text classifier confidence as the base (it's the strongest signal)
2. If URL analysis confirms (suspicious domain found), add 0.10 to confidence
3. If visual analysis confirms (fake UI detected), add 0.05
4. If audio is synthetic, add 0.10
5. If URL analysis contradicts (domain is legitimate), subtract 0.15
6. Clamp final confidence to 0.0–1.0

**Special cases:**
- If ONLY URL analysis is available (user sent just a URL), use URL risk score as the primary confidence
- If ONLY audio is available, weight text transcript at 0.60 and synthetic score at 0.40
- If multiple signals agree (all say scam), apply a 0.05 "consensus boost"

**Step 3: Aggregate red flags**

- Collect all red flags from all analyzers into a single list
- Deduplicate (e.g., both text and URL analyzers might flag the same domain)
- Sort by severity: critical first, then high, medium, low
- Limit to top 10 red flags (too many overwhelms the user)

**Step 4: Determine final verdict**

- `is_scam`: true if merged confidence > 0.5
- `risk_level`: based on the merged confidence (use the mapping from 1.1)
- `scam_type`: use the text classifier's scam_type (it's the most specific)
- `recommended_action`: based on risk level:
  - Low: "This appears legitimate"
  - Medium: "Proceed with caution. Verify through official channels."
  - High: "Do NOT click any links or share personal information. Block the sender."
  - Critical: "🚨 HANG UP / DELETE IMMEDIATELY. Report to 1930 helpline. Do NOT share any OTP or make any payment."

**Step 5: Generate human-readable summary**

Use a **template-based approach** (not LLM — faster and more reliable):

**Template for high/critical scam:**
```
🚨 This is a {scam_type_readable} scam ({confidence_percent}% confidence).

Key red flags:
{numbered red flags list}

What the scammer is trying to do:
{one sentence explanation based on scam_type}

What you should do:
{recommended_action}

Evidence:
{detailed evidence items}
```

**Template for legitimate:**
```
✅ This appears to be a legitimate message ({confidence_percent}% confidence).

No significant scam indicators were found. However, always stay cautious:
- Never share your OTP with anyone
- Verify links by typing the URL manually
- Call your bank on the official number if unsure
```

**Scam type readable names:**
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

**Step 6: Build the final ScamVerdict object**

Assemble all the pieces into the Pydantic `ScamVerdict` model from Phase 0. This is what gets returned to the frontend and the Telegram bot.

### Evidence Object Structure

Each evidence item in the `evidence` array:

```json
{
  "type": "url_analysis",
  "detail": "Domain sbi-kyc-verify.xyz was registered only 4 days ago via Namecheap. The official SBI domain is sbi.co.in.",
  "severity": "high",
  "source": "url_analyzer"
}
```

**Evidence types:**
| Type | Source | Example |
|------|--------|---------|
| `linguistic` | Text classifier | "Message uses extreme urgency: 'blocked within 24 hours'" |
| `url_analysis` | URL analyzer | "Domain age: 4 days. Official domain: sbi.co.in" |
| `domain_age` | URL analyzer | "Domain registered on 2025-01-11, only 4 days ago" |
| `visual` | Image analyzer | "Screenshot shows blurred SBI logo inconsistent with official app" |
| `voice_synthetic` | Audio analyzer | "Voice has 78% probability of being AI-generated" |
| `transcript` | Audio analyzer | "Transcript contains payment demand: 'transfer ₹50,000'" |
| `pattern_match` | Text classifier | "Message matches known UPI reversal scam pattern" |

---

## 1.6 · Multi-Modal Orchestrator

### File Location
`backend/app/routers/analyze.py` (endpoint) + `backend/app/services/orchestrator.py` (logic)

### What It Does
Single entry point that accepts any input type, detects what it is, routes to the right analyzers, and returns a unified verdict.

### API Endpoint Design

**Endpoint:** `POST /analyze`

**Content-Type:** `multipart/form-data` (to handle both text and file uploads)

**Form Fields:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `text` | string | No | Message text (if no file) |
| `url` | string | No | URL to check (if no file) |
| `file` | file | No | Audio, image, or document file |
| `input_type` | string | No | `text`, `audio`, `image`, `url` — auto-detected if not provided |

**At least one of `text`, `url`, or `file` must be provided.**

### Auto-Detection Logic

If `input_type` is not explicitly provided, detect it:

1. **If `file` is present:**
   - Check the MIME type from the uploaded file
   - `image/*` (png, jpg, jpeg, webp) → `image`
   - `audio/*` (ogg, mp3, wav, m4a, webm) → `audio`
   - `application/pdf` → treat as `image` (OCR the first page) — stretch goal
   - Anything else → return error: "Unsupported file type"

2. **If `url` is present and `text` is empty:**
   - → `url`

3. **If `text` is present:**
   - Check if the text contains a URL (regex match)
   - If the text is ONLY a URL → `url`
   - If the text contains a URL AND other content → `text` (the URL analyzer will be called as a sub-step)
   - If no URL → `text`

### Routing Logic

```
Input detected as TEXT:
  → Call Text Classifier (1.1) with the full text
  → Extract URLs from text → if found, call URL Analyzer (1.2)
  → Pass all results to Evidence Builder (1.5)

Input detected as URL:
  → Call URL Analyzer (1.2) with the URL
  → Call Text Classifier (1.1) with the URL as text (for pattern matching)
  → Pass all results to Evidence Builder (1.5)

Input detected as IMAGE:
  → Call Image Analyzer (1.3) with the image file
  → Image Analyzer internally calls Text Classifier and URL Analyzer on OCR output
  → Pass all results to Evidence Builder (1.5)

Input detected as AUDIO:
  → Call Audio Analyzer (1.4) with the audio file
  → Audio Analyzer internally calls Text Classifier on transcript
  → Pass all results to Evidence Builder (1.5)
```

### Error Handling

| Error | HTTP Status | Response |
|-------|-------------|----------|
| No input provided | 400 | `{"error": "Provide text, url, or file"}` |
| Unsupported file type | 400 | `{"error": "Unsupported file type: .exe"}` |
| File too large | 413 | `{"error": "File too large. Max 10MB for audio, 5MB for images"}` |
| Groq API down | 503 | Fall back to Gemini. If both down: `{"error": "AI service temporarily unavailable"}` |
| Analysis timeout (> 30 sec) | 504 | `{"error": "Analysis timed out. Try a shorter message"}` |
| Internal error | 500 | Log the full error, return `{"error": "Internal error. Please try again"}` |

### Response Format

**Success (200):**
```json
{
  "verdict": {
    "is_scam": true,
    "confidence": 0.92,
    "scam_type": "bank_kyc",
    "risk_level": "critical",
    "red_flags": [
      "Domain sbi-kyc-verify.xyz is only 4 days old",
      "Asks for ATM PIN and OTP",
      "Creates extreme urgency: 'blocked in 24 hours'",
      "Helpline number is a mobile number, not toll-free"
    ],
    "stages_detected": ["hook", "authority", "urgency", "payment"],
    "summary": "🚨 This is a Bank KYC scam (92% confidence). The message claims your SBI account will be blocked and asks you to click a link to a fake website registered 4 days ago. It asks for your ATM PIN and OTP, which no real bank will ever request.",
    "recommended_action": "🚨 DELETE IMMEDIATELY. Do NOT click the link. Do NOT share any OTP. Report to 1930 helpline.",
    "evidence": [
      {
        "type": "url_analysis",
        "detail": "Domain sbi-kyc-verify.xyz registered 4 days ago via Namecheap",
        "severity": "high",
        "source": "url_analyzer"
      },
      {
        "type": "linguistic",
        "detail": "Message asks for ATM PIN — banks never ask for PIN via SMS",
        "severity": "critical",
        "source": "text_classifier"
      }
    ]
  },
  "analysis_metadata": {
    "input_type": "text",
    "analyzers_used": ["text_classifier", "url_analyzer"],
    "processing_time_ms": 1250,
    "language_detected": "en"
  }
}
```

### Performance Targets

| Input Type | Target Latency | Bottleneck |
|------------|---------------|------------|
| Text only | < 2 seconds | Groq LLM call |
| URL only | < 3 seconds | WHOIS lookup |
| Image | < 5 seconds | Gemini Vision + OCR + text analysis |
| Audio | < 8 seconds | Whisper transcription + text analysis + Resemblyzer |

### Caching Strategy (optional, for demo)

- Cache URL analysis results by domain for 1 hour (WHOIS data doesn't change fast)
- Cache identical text inputs for 10 minutes (same scam message forwarded by multiple users)
- Use a simple in-memory dict for the hackathon. No need for Redis.

---

## File Summary for Phase 1

| File | Purpose | Lines (estimate) |
|------|---------|-----------------|
| `backend/app/services/scam_analyzer.py` | Text classifier with LLM prompt | ~120 |
| `backend/app/services/url_analyzer.py` | URL/domain analysis | ~180 |
| `backend/app/services/image_analyzer.py` | Image OCR + visual analysis | ~130 |
| `backend/app/services/voice_analyzer.py` | Audio transcription + deepfake detection | ~150 |
| `backend/app/services/evidence_builder.py` | Merge signals, build report | ~160 |
| `backend/app/services/orchestrator.py` | Route inputs, coordinate analyzers | ~100 |
| `backend/app/routers/analyze.py` | FastAPI endpoint | ~80 |
| `backend/app/utils/constants.py` | Legitimate domains, suspicious TLDs | ~60 |
| `backend/tests/test_samples.json` | 20 test samples | ~200 |
| `backend/tests/test_analyzer.py` | Test runner | ~80 |

**Total estimated:** ~1,260 lines of Python

---

## Phase 1 Completion Checklist

```
□ Text classifier returns valid JSON for all 20 test samples
□ Text classifier correctly identifies at least 18/20 samples
□ Text classifier correctly identifies the 5 legitimate messages as NOT scams
□ URL analyzer correctly flags sbi-kyc-verify.xyz as suspicious
□ URL analyzer correctly identifies sbi.co.in as legitimate
□ URL analyzer handles WHOIS failures gracefully
□ URL analyzer detects lookalike domains
□ Image analyzer extracts text from a WhatsApp screenshot
□ Image analyzer feeds OCR text to text classifier
□ Image analyzer detects visual anomalies in fake bank pages
□ Audio analyzer transcribes a Hindi voice note
□ Audio analyzer transcribes an English voice note
□ Audio analyzer returns a synthetic voice score
□ Evidence builder merges multiple signals correctly
□ Evidence builder generates human-readable summaries
□ POST /analyze works with text input
□ POST /analyze works with URL input
□ POST /analyze works with image upload
□ POST /analyze works with audio upload
□ POST /analyze auto-detects input type correctly
□ Error handling works for empty input, large files, API failures
□ Response time < 5 seconds for text, < 8 seconds for audio
□ All results match the ScamVerdict Pydantic schema
```

**When every box is checked, Phase 1 is done. Move to Phase 2 (Telegram Bot) or Phase 3 (Fire Drill).**

---

Ready for the next phase deep dive? Say which one — Phase 2 (Bot), Phase 3 (Fire Drill), or Phase 4 (Guardian).