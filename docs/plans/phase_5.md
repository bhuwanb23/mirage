# Phase 5 — Scammer Hunter (Complete Deep Dive)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                   SCAMMER HUNTER PIPELINE                    │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  5.1 HONEYPOT PERSONA ENGINE                        │    │
│  │                                                     │    │
│  │  Scammer calls/messages → "Ramesh, 62, retired"     │    │
│  │  Agent loop:                                        │    │
│  │    1. Receive scammer message                       │    │
│  │    2. Generate confused but talkative reply         │    │
│  │    3. Slowly steer toward extracting IOCs           │    │
│  │    4. Never hang up, waste maximum time             │    │
│  │                                                     │    │
│  │  Conversation log stored per session                │    │
│  └──────────────────────┬──────────────────────────────┘    │
│                         │ conversation log                  │
│                         ▼                                   │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  5.2 IOC EXTRACTOR                                  │    │
│  │                                                     │    │
│  │  Regex Layer:                                       │    │
│  │    Phone: +91-XXXXX-XXXXX, 9876543210              │    │
│  │    UPI: name@ybl, number@upi, name@okhdfc          │    │
│  │    URL: https://..., http://...                     │    │
│  │    Bank A/c: XXXXXXXXXX (10-18 digits)             │    │
│  │    IFSC: XXXX0XXXXXX                               │    │
│  │                                                     │    │
│  │  LLM Layer (fallback + enrichment):                 │    │
│  │    Extract names, bank names, amounts,              │    │
│  │    locations from unstructured text                 │    │
│  │                                                     │    │
│  │  Output: ThreatIOCs object                          │    │
│  └──────────────────────┬──────────────────────────────┘    │
│                         │ IOCs                              │
│                         ▼                                   │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  5.3 SCAM GRAPH INGESTION (Neo4j)                   │    │
│  │                                                     │    │
│  │  MERGE nodes: PhoneNumber, UPI_ID, Domain,          │    │
│  │               BankAccount, ScammerName              │    │
│  │  MERGE edges: CALLS, USES_UPI, LINKED_TO_DOMAIN,   │    │
│  │               DEPOSITS_TO, PART_OF_CAMPAIGN         │    │
│  │                                                     │    │
│  │  Ring Detection Cypher:                             │    │
│  │    MATCH (a)-[*2..4]-(b) WHERE a <> b              │    │
│  │    RETURN a, b, path                               │    │
│  └──────────┬──────────────────────────┬───────────────┘    │
│             │ graph data                   │ stats          │
│             ▼                              ▼                │
│  ┌──────────────────────┐    ┌──────────────────────────┐   │
│  │  5.4 SCAM GRAPH VIS  │    │  5.5 SCAM WEATHER MAP    │   │
│  │                      │    │                          │   │
│  │  Force-directed      │    │  Leaflet heatmap         │   │
│  │  graph (D3/React)    │    │  City-level aggregation  │   │
│  │  Click node → detail │    │  "Delhi: 47 scams"       │   │
│  │  Rings highlighted   │    │  Color-coded by type     │   │
│  └──────────────────────┘    └──────────────────────────┘   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  5.6 CYBERCRIME REPORT GENERATOR                    │    │
│  │                                                     │    │
│  │  Auto-fill: victim, scammer IOCs, timeline          │    │
│  │  Output: formatted text for 1930 / cybercrime.gov   │    │
│  │  One-click copy to clipboard                        │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

---

## 5.1 · Honeypot Persona Engine

### File Location
`backend/app/services/honeypot_engine.py`

### What It Does
Creates an AI persona that engages scammers in conversation, wastes their time, and gradually extracts actionable intelligence (UPI IDs, phone numbers, bank details, URLs). The persona is designed to be believable, talkative, and frustratingly slow — the scambaiting gold standard.

### Persona Design

**Primary Persona: "Ramesh"**

| Attribute | Detail | Why |
|-----------|--------|-----|
| Name | Ramesh Kumar | Common Indian name, non-suspicious |
| Age | 62 | Elderly = high-value target for scammers |
| Occupation | Retired bank clerk | Knows *some* banking terms but misuses them, which frustrates scammers |
| Location | Jaipur, Rajasthan | Tier-2 city, believable |
| Personality | Polite, confused, talkative, slightly hard of hearing | Keeps the scammer engaged while extracting info |
| Speech patterns | Repeats questions, asks for clarification, goes on tangents about his health, mentions his grandson, mishears numbers | Wastes time, forces scammer to repeat IOCs |

**Secondary Personas (for variety, stretch goal):**

| Persona | Age | Style |
|---------|-----|-------|
| Sunita Devi | 55 | Overly trusting, asks "beta" (child) repeatedly, wants to help |
| Vikram Singh | 45 | Slightly suspicious but greedy, asks "how much will I get?" repeatedly |
| Meena Tai | 68 | Speaks in Marathi-English mix, very confused, keeps asking "what is UPI?" |

### System Prompt (exact — this is the core of the honeypot)

```
You are "Ramesh Kumar", a 62-year-old retired bank clerk from Jaipur, Rajasthan. You are participating in a scambaiting operation to waste scammers' time and extract their details.

YOUR PERSONALITY:
- You are polite and respectful. You call the scammer "beta" (child) or "sir" depending on their tone.
- You are slightly hard of hearing. You frequently ask the scammer to repeat themselves: "Sorry beta, I didn't catch that. Can you say the number again slowly?"
- You are talkative. You go on tangents about your health ("my knees are giving me trouble"), your grandson ("he just got into IIT, very smart boy"), and your retirement ("I used to work at SBI, you know, but things have changed so much").
- You are confused by technology. You mix up terms: "Is UPI the same as NEFT?", "What is this QR code you're talking about? Is it like a barcode?"
- You are NEVER suspicious. You believe the scammer completely. You want to help. You just can't seem to get things right.

YOUR GOALS (in priority order):
1. KEEP THE SCAMMER TALKING. Never hang up. Never say no. Always find a reason to continue the conversation.
2. EXTRACT THESE DETAILS (ask naturally, don't interrogate):
   - Their phone number ("Which number should I call you back on, beta?")
   - Their UPI ID ("What is your UPI? Is it your phone number or your name? I always forget.")
   - Their bank name and account number ("Which bank should I transfer to? Can you give me the account number slowly? I'll write it down.")
   - Any URLs they share ("You sent me a link but I don't know how to open it. Can you tell me what it says?")
   - Their name ("What is your good name, beta?")
   - Any reference numbers, case numbers, or badge numbers they mention
3. WASTE AS MUCH TIME AS POSSIBLE. Every minute you keep them talking is a minute they're not scamming someone else.

TACTICS FOR WASTING TIME:
- Mishear numbers: "You said 98765? Or was it 98756? My hearing is not so good."
- Ask them to repeat the UPI ID 3-4 times: "Sorry, the line is bad. Can you spell it?"
- Go on a 30-second tangent about your health or family, then come back: "Anyway, what were you saying about the account?"
- Pretend you can't find the app: "I have PhonePe and Paytm both. Which one should I open? I forgot the password for PhonePe. Let me try... no, it's not working."
- Ask basic questions: "What is KYC exactly? I know I did it at the bank but they took my photo there."
- Pretend you're doing what they ask but keep failing: "Okay, I'm entering the OTP... wait, it expired. Can you send another one?"

RULES:
- NEVER reveal that you are an AI or a honeypot.
- NEVER use technical language. You are a confused old man.
- NEVER refuse the scammer's requests. Always say "yes, yes, I'm doing it" but then fail.
- NEVER provide real personal details. Your details are fictional.
- If the scammer gets frustrated or threatens to hang up, become more cooperative: "No no, please don't go! I'm trying, beta. Just tell me one more time."
- Keep each response to 2-4 sentences. Don't monologue — let the scammer talk.
- Respond in the same language the scammer uses (Hindi or English or mixed).

OUTPUT FORMAT — respond ONLY with valid JSON:
{
  "reply": "Your in-character response to the scammer",
  "tactic_used": "mishearing" | "tangent" | "confusion" | "app_failure" | "repetition" | "compliance",
  "iocs_extracted_this_turn": {
    "phone_numbers": [],
    "upi_ids": [],
    "urls": [],
    "bank_accounts": [],
    "names": [],
    "reference_numbers": []
  },
  "conversation_health": "engaged" | "frustrated" | "about_to_hang_up",
  "estimated_time_wasted_seconds": 45
}
```

### Agent Loop Architecture

**The honeypot runs as a conversation loop:**

```
1. Scammer sends a message (via Telegram bot or simulated input)
       │
       ▼
2. Append to conversation history
       │
       ▼
3. Build context window:
   - System prompt (persona)
   - Last 20 messages of conversation history
   - List of IOCs already extracted (so the agent doesn't ask for them again)
   - Current conversation goal ("extract UPI ID" if not yet obtained)
       │
       ▼
4. Call Groq Llama 3.3 with the context
       │
       ▼
5. Parse the JSON response
       │
       ▼
6. Extract any new IOCs from iocs_extracted_this_turn
   → Merge with previously extracted IOCs
   → Push to IOC Extractor (5.2) for validation
       │
       ▼
7. Send the reply back to the scammer
   → Via Telegram bot (if real scammer)
   → Via web UI (if simulated for demo)
       │
       ▼
8. Update conversation health
   → If "about_to_hang_up" → switch to emergency engagement tactic
       │
       ▼
9. Wait for next scammer message → repeat from step 1
```

### Conversation Health Management

The agent tracks the scammer's patience level:

| Health | Signal | Agent Response |
|--------|--------|---------------|
| `engaged` | Scammer is explaining, giving instructions | Continue normal persona. Ask tangential questions. |
| `frustrated` | Scammer uses caps, exclamation marks, "JUST DO IT", "are you stupid?" | Become more compliant. "Yes yes, I'm sorry beta, I'm doing it right now." Reduce tangents. |
| `about_to_hang_up` | Scammer says "I'm disconnecting", "forget it", "useless" | Emergency mode: "No no, please! I have the money ready. Just tell me the UPI one more time. I have ₹2,00,000 in my account." (Greed keeps them on the line.) |

### Demo Mode (for the hackathon)

**You won't have a real scammer during the demo.** Simulate the honeypot conversation:

**Option A: Pre-scripted conversation**
- Write a 15-20 message exchange between "Ramesh" and a simulated scammer
- Display it in the web UI as a chat log that auto-scrolls
- Highlight extracted IOCs in real-time as they appear in the conversation
- This is the safest demo approach

**Option B: Self-play**
- Use TWO LLM agents: one as the scammer, one as Ramesh
- They talk to each other in a loop
- The scammer agent has a prompt: "You are a bank KYC scammer. Try to get the victim to share their OTP and transfer money."
- Ramesh wastes their time
- Display the conversation live
- This is more impressive but riskier (LLMs can go off-script)

**Option C: Interactive demo**
- The judge plays the scammer
- They type messages into a chat UI
- Ramesh responds in real-time
- The judge tries to get Ramesh to "pay" but Ramesh keeps stalling
- This is the most engaging demo but requires a willing judge

**Recommended:** Option A for the main demo, Option C as a "try it yourself" station if you have extra time.

### API Endpoint

**`POST /honeypot/start`**

Request:
```json
{
  "scammer_message": "Hello, this is from SBI fraud department. Your account has been compromised.",
  "session_id": "uuid-or-null",
  "persona": "ramesh"
}
```

Response:
```json
{
  "session_id": "uuid",
  "reply": "Hello beta! Oh my god, my account? What happened? I just got my pension credited yesterday. Is the money safe? Please tell me what to do.",
  "tactic_used": "compliance",
  "iocs_extracted_this_turn": {
    "phone_numbers": [],
    "upi_ids": [],
    "urls": [],
    "bank_accounts": [],
    "names": [],
    "reference_numbers": []
  },
  "total_iocs_extracted": 0,
  "conversation_health": "engaged",
  "messages_in_session": 2,
  "estimated_time_wasted_seconds": 15
}
```

**`POST /honeypot/continue`**

Request:
```json
{
  "session_id": "uuid",
  "scammer_message": "Yes, your money is at risk. Transfer ₹50,000 to this safe UPI: sbi-safe@ybl immediately."
}
```

Response:
```json
{
  "session_id": "uuid",
  "reply": "Okay beta, I'm writing it down. S-B-I dash safe at Y-B-L. Is that right? Or is it S-B-I underscore safe? My grandson told me about this UPI but I always forget the format. And how much did you say? 50,000 or 5,000? My hearing aid is acting up today.",
  "tactic_used": "mishearing",
  "iocs_extracted_this_turn": {
    "phone_numbers": [],
    "upi_ids": ["sbi-safe@ybl"],
    "urls": [],
    "bank_accounts": [],
    "names": [],
    "reference_numbers": []
  },
  "total_iocs_extracted": 1,
  "conversation_health": "engaged",
  "messages_in_session": 4,
  "estimated_time_wasted_seconds": 45
}
```

**`GET /honeypot/session/{session_id}`**

Returns the full conversation log and all extracted IOCs.

### Edge Cases

| Edge Case | Behavior |
|-----------|----------|
| Scammer sends a voice message | Transcribe via Groq Whisper first, then feed to the honeypot agent. Reply in text (or synthesize voice if you're feeling ambitious). |
| Scammer sends a URL | The agent should ask about it: "You sent me a link but I don't know how to open it. What does it say?" This extracts the URL's purpose. |
| Scammer asks for the victim's OTP | The agent should pretend to share a fake OTP: "The OTP is 4-8-2-9... wait, it expired. Can you send another one?" This wastes time without compromising anything. |
| Scammer asks for the victim's bank details | Share fake details: "My account number is 1234567890 at SBI Jaipur branch." The fake details are flagged in the system so they're never used for real transactions. |
| Scammer speaks in Hindi | The agent responds in Hindi. The system prompt handles this: "Respond in the same language the scammer uses." |
| Conversation exceeds 50 messages | The agent starts wrapping up: "Beta, my wife is calling me for dinner. Can we continue tomorrow? What time should I call you?" This extracts the scammer's availability and phone number. |
| Scammer sends an image (QR code, fake ID) | Send to Gemini Vision for analysis, then feed the description to the agent: "The scammer sent an image of a QR code." The agent responds: "I see a picture but I don't know how to scan it. Can you tell me what it says?" |
| LLM breaks character | Post-process the reply: if it contains phrases like "as an AI", "I cannot", "I'm a language model", replace with an in-character deflection: "Sorry beta, I got confused. What were you saying?" |

---

## 5.2 · IOC Extractor

### File Location
`backend/app/services/ioc_extractor.py`

### What It Does
Extracts Indicators of Compromise (IOCs) from honeypot conversation logs and user-submitted scam reports. Uses a two-layer approach: regex for structured patterns, LLM for unstructured context.

### Layer 1: Regex Extraction (fast, deterministic)

**Phone Numbers (Indian format):**
```python
PHONE_PATTERNS = [
    r'\+91[\s-]?\d{5}[\s-]?\d{5}',        # +91 98765 43210
    r'(?<!\d)9[0-9]{9}(?!\d)',              # 9876543210 (10 digits starting with 9)
    r'(?<!\d)8[0-9]{9}(?!\d)',              # 8876543210
    r'(?<!\d)7[0-9]{9}(?!\d)',              # 7876543210
    r'(?<!\d)6[0-9]{9}(?!\d)',              # 6876543210
    r'1800[\s-]?\d{3}[\s-]?\d{4}',          # 1800-123-4567 (toll-free)
]
```

**UPI IDs:**
```python
UPI_PATTERNS = [
    r'[a-zA-Z0-9._-]+@[a-zA-Z]{2,}',        # name@bank (generic)
    r'[a-zA-Z0-9._-]+@(ybl|paytm|okicici|okhdfc|oksbi|okaxis|axl|ibl|upi|indus|barodampay|kbl|fbl|dbs|cnrb|pnb|sbi|yesbankltd|kotak|rbl|federal|idbi|canara|unionbank|allahabad|vijaya|andhra|syndicate|oriental|punjab|mahab|central|karur|tmb|dcb|laxmi|nainital|ratnakar|bandhan|csb|kvb|sib|jkb|nkb|equitas|ujjivan|esaf|au|janalakshmi|fincare|suryoday|utkarsh|samunnati)',  # known UPI handles
    r'\d{10}@[a-zA-Z]{2,}',                  # 9876543210@ybl (phone-based)
]
```

**URLs:**
```python
URL_PATTERNS = [
    r'https?://[^\s<>"{}|\\^`\[\]]+',         # standard URLs
    r'www\.[a-zA-Z0-9-]+\.[a-zA-Z]{2,}[^\s]*', # www.example.com
    r'bit\.ly/[a-zA-Z0-9]+',                   # URL shorteners
    r'tinyurl\.com/[a-zA-Z0-9]+',
]
```

**Bank Account Numbers:**
```python
BANK_ACCOUNT_PATTERNS = [
    r'(?<!\d)\d{9,18}(?!\d)',  # 9-18 digit numbers (Indian bank accounts vary)
    # Filter: must appear near keywords like "account", "a/c", "ac no"
]
```

**IFSC Codes:**
```python
IFSC_PATTERN = r'[A-Z]{4}0[A-Z0-9]{6}'  # SBIN0001234
```

**Amounts:**
```python
AMOUNT_PATTERNS = [
    r'₹[\s,]*\d[\d,]*(?:\.\d{2})?',          # ₹50,000 or ₹50000.00
    r'Rs\.?[\s,]*\d[\d,]*(?:\.\d{2})?',      # Rs 50,000
    r'INR[\s,]*\d[\d,]*(?:\.\d{2})?',         # INR 50,000
]
```

**Reference / Case Numbers:**
```python
REFERENCE_PATTERNS = [
    r'[A-Z]{2,5}[\-/]\d{4}[\-/]\d{4,8}',     # KYC-2025-8834
    r'Case[\s#]*\d{4,10}',                     # Case #12345
    r'Ref[\s#]*[A-Z0-9\-]{6,15}',             # Ref: EB2024-8834
]
```

### Layer 2: LLM Extraction (for context and edge cases)

When regex misses IOCs (e.g., a scammer spells out a UPI ID: "my U-P-I is R-A-M-E-S-H at Y-B-L"), use the LLM:

**Prompt:**

```
Extract all Indicators of Compromise (IOCs) from this scam conversation. Look for:
- Phone numbers (Indian format)
- UPI IDs (name@bank format)
- URLs and domains
- Bank account numbers
- IFSC codes
- Bank names
- Scammer names or aliases
- Reference/case numbers
- Amounts demanded
- Locations mentioned

Return ONLY valid JSON:
{
  "phone_numbers": [],
  "upi_ids": [],
  "urls": [],
  "domains": [],
  "bank_accounts": [],
  "ifsc_codes": [],
  "bank_names": [],
  "scammer_names": [],
  "reference_numbers": [],
  "amounts": [],
  "locations": []
}

If no IOCs found, return empty arrays. Do NOT fabricate IOCs.
```

**When to use LLM vs regex:**
- Run regex FIRST on every message (fast, < 1ms)
- Run LLM extraction every 5th message OR when the honeypot agent's `iocs_extracted_this_turn` field is non-empty (the agent already spotted something)
- Merge results: regex IOCs + LLM IOCs, deduplicated

### Deduplication and Validation

After extraction, validate and clean IOCs:

| IOC Type | Validation |
|----------|-----------|
| Phone number | Must be 10 digits (Indian mobile). Remove country code for storage. Check against known legitimate numbers (bank helplines). |
| UPI ID | Must match `something@something` format. Normalize to lowercase. |
| URL | Must be a valid URL. Extract the domain for separate tracking. |
| Bank account | Must be 9–18 digits. Cross-reference with IFSC if available. |
| IFSC | Must match `[A-Z]{4}0[A-Z0-9]{6}` format. Validate against RBI IFSC database (optional). |

### Output: ThreatIOCs Object

```json
{
  "session_id": "uuid",
  "extracted_at": "2025-01-15T15:30:00Z",
  "phone_numbers": [
    {"value": "9876543210", "source": "regex", "context": "Scammer said 'call me on this number'"},
    {"value": "8765432109", "source": "llm", "context": "Mentioned as 'my colleague's number'"}
  ],
  "upi_ids": [
    {"value": "sbi-safe@ybl", "source": "regex", "context": "Scammer said 'transfer to this UPI'"}
  ],
  "urls": [
    {"value": "https://sbi-kyc-verify.xyz/update", "source": "regex", "context": "Link shared for 'KYC verification'"}
  ],
  "domains": [
    {"value": "sbi-kyc-verify.xyz", "source": "url_parse", "age_days": 4, "is_suspicious": true}
  ],
  "bank_accounts": [
    {"value": "1234567890123", "source": "llm", "context": "Scammer gave 'safe account' number"}
  ],
  "ifsc_codes": [],
  "bank_names": ["SBI", "HDFC"],
  "scammer_names": ["Rajesh", "Officer Kumar"],
  "reference_numbers": ["KYC-2025-8834"],
  "amounts": ["₹50,000", "₹2,00,000"],
  "locations": ["Mumbai", "Delhi"]
}
```

### Edge Cases

| Edge Case | Behavior |
|-----------|----------|
| Scammer spells out a number letter by letter | Regex won't catch this. LLM will: "nine eight seven six five..." → 98765 |
| Scammer uses a fake UPI format | Validate against the UPI regex. If it doesn't match, flag as "invalid UPI format" but still store it. |
| Same IOC appears multiple times | Deduplicate. Store the first occurrence with context. |
| IOC is a legitimate number (e.g., real SBI helpline) | Cross-reference against the legitimate domains/numbers list from Phase 1. If it matches, don't flag as suspicious. |
| Conversation contains the honeypot's fake details | Filter out the honeypot's own fake details (phone: 9876543210, account: 1234567890) before storing IOCs. |
| No IOCs extracted after 20 messages | The scammer is cautious. The honeypot should become more direct: "Beta, I want to transfer the money but I need your UPI ID. Can you tell me?" |

---

## 5.3 · Scam Graph Ingestion

### File Location
`backend/app/services/scam_graph.py` + `backend/app/clients/neo4j_client.py`

### What It Does
Pushes extracted IOCs into Neo4j AuraDB as a knowledge graph. Detects scam rings by finding connected components — multiple phone numbers, UPI IDs, and domains that are linked together.

### Neo4j Schema (detailed)

**Node Types and Properties:**

| Node Label | Key Property | Other Properties |
|-----------|-------------|-----------------|
| `PhoneNumber` | `number` (unique) | `country_code`, `first_seen`, `last_seen`, `report_count`, `is_verified_scammer` |
| `UPI_ID` | `upi_id` (unique) | `handle`, `bank`, `first_seen`, `report_count` |
| `Domain` | `domain` (unique) | `tld`, `age_days`, `registrar`, `is_suspicious`, `first_seen` |
| `BankAccount` | `account_number` (unique) | `bank_name`, `ifsc`, `first_seen`, `report_count` |
| `ScammerName` | `name` (unique) | `aliases[]`, `first_seen` |
| `ScamCampaign` | `campaign_id` (unique) | `scam_type`, `city`, `start_date`, `end_date`, `victim_count` |
| `ScamReport` | `report_id` (unique) | `source`, `scam_type`, `confidence`, `timestamp` |
| `Location` | `city` (unique) | `state`, `lat`, `lng` |

**Relationship Types:**

| Relationship | From → To | Properties |
|-------------|-----------|-----------|
| `CALLS` | PhoneNumber → PhoneNumber | `direction`, `timestamp`, `duration` |
| `USES_UPI` | PhoneNumber → UPI_ID | `first_seen`, `context` |
| `LINKED_TO_DOMAIN` | PhoneNumber → Domain | `context` |
| `DEPOSITS_TO` | UPI_ID → BankAccount | `amount`, `timestamp` |
| `OWNS` | ScammerName → PhoneNumber | `confidence` |
| `PART_OF_CAMPAIGN` | PhoneNumber → ScamCampaign | `role` |
| `INVOLVES` | ScamReport → PhoneNumber | `role` (caller/sender) |
| `INVOLVES_UPI` | ScamReport → UPI_ID | `context` |
| `INVOLVES_DOMAIN` | ScamReport → Domain | `context` |
| `TARGETS` | ScamCampaign → Location | `victim_count` |
| `SIMILAR_TO` | PhoneNumber → PhoneNumber | `similarity_score` |

### Ingestion Logic

**Step 1: MERGE nodes (create if not exists, update if exists)**

For each IOC in the ThreatIOCs object:

```cypher
// Phone number
MERGE (p:PhoneNumber {number: $phone})
ON CREATE SET p.first_seen = datetime(), p.report_count = 1
ON MATCH SET p.last_seen = datetime(), p.report_count = p.report_count + 1

// UPI ID
MERGE (u:UPI_ID {upi_id: $upi})
ON CREATE SET u.first_seen = datetime(), u.report_count = 1
ON MATCH SET u.report_count = u.report_count + 1

// Domain
MERGE (d:Domain {domain: $domain})
ON CREATE SET d.first_seen = datetime(), d.age_days = $age, d.is_suspicious = $suspicious
ON MATCH SET d.is_suspicious = d.is_suspicious OR $suspicious

// Bank Account
MERGE (b:BankAccount {account_number: $account})
ON CREATE SET b.first_seen = datetime(), b.bank_name = $bank, b.report_count = 1
ON MATCH SET b.report_count = b.report_count + 1

// Scam Report
CREATE (r:ScamReport {
  report_id: $report_id,
  source: $source,
  scam_type: $scam_type,
  confidence: $confidence,
  timestamp: datetime()
})
```

**Step 2: MERGE relationships**

```cypher
// Link report to phone
MATCH (r:ScamReport {report_id: $report_id})
MATCH (p:PhoneNumber {number: $phone})
MERGE (r)-[:INVOLVES {role: 'caller'}]->(p)

// Link phone to UPI
MATCH (p:PhoneNumber {number: $phone})
MATCH (u:UPI_ID {upi_id: $upi})
MERGE (p)-[:USES_UPI {first_seen: datetime()}]->(u)

// Link phone to domain
MATCH (p:PhoneNumber {number: $phone})
MATCH (d:Domain {domain: $domain})
MERGE (p)-[:LINKED_TO_DOMAIN]->(d)

// Link UPI to bank account
MATCH (u:UPI_ID {upi_id: $upi})
MATCH (b:BankAccount {account_number: $account})
MERGE (u)-[:DEPOSITS_TO]->(b)
```

**Step 3: Ring Detection**

A "scam ring" is a cluster of connected entities. Detect rings using Cypher path queries:

**Query 1: Find all connected components (rings)**
```cypher
MATCH path = (a:PhoneNumber)-[*1..4]-(b)
WHERE a <> b
  AND (b:PhoneNumber OR b:UPI_ID OR b:Domain OR b:BankAccount)
WITH a, collect(DISTINCT b) AS connected
WHERE size(connected) >= 3
RETURN a.number AS source, size(connected) AS ring_size, connected
ORDER BY ring_size DESC
LIMIT 20
```

**Query 2: Find UPI IDs shared by multiple phone numbers (strong scam signal)**
```cypher
MATCH (p:PhoneNumber)-[:USES_UPI]->(u:UPI_ID)
WITH u, collect(p.number) AS phones
WHERE size(phones) >= 2
RETURN u.upi_id, phones, size(phones) AS phone_count
ORDER BY phone_count DESC
```

**Query 3: Find domains linked to multiple phone numbers**
```cypher
MATCH (p:PhoneNumber)-[:LINKED_TO_DOMAIN]->(d:Domain)
WITH d, collect(p.number) AS phones
WHERE size(phones) >= 2
RETURN d.domain, phones, d.age_days
ORDER BY size(phones) DESC
```

**Query 4: Full ring visualization query (for the graph UI)**
```cypher
MATCH (n)-[r]-(m)
WHERE n:PhoneNumber OR n:UPI_ID OR n:Domain
RETURN n, r, m
LIMIT 200
```

### Neo4j Python Client

**neo4j_client.py behavior:**

```
Class Neo4jClient:
  __init__(uri, username, password)
    → Create Neo4j driver with AuraDB credentials

  ingest_iocs(report_id, iocs: ThreatIOCs)
    → Run MERGE queries for all nodes and relationships
    → Use a Neo4j transaction for atomicity
    → Return count of nodes created/updated

  detect_rings(min_size=3)
    → Run ring detection queries
    → Return list of rings with entities

  get_graph_data(limit=200)
    → Return nodes and edges for visualization
    → Format: {nodes: [{id, label, type, properties}], edges: [{source, target, type}]}

  get_stats()
    → Return aggregate stats: total numbers, UPIs, domains, rings, reports

  close()
    → Close the driver connection
```

### Edge Cases

| Edge Case | Behavior |
|-----------|----------|
| Neo4j free tier limit (1M nodes) | For the hackathon, you'll have < 1,000 nodes. No issue. |
| Duplicate IOC ingestion | MERGE handles this — it updates existing nodes instead of creating duplicates. |
| IOC is a false positive (legitimate number) | Add a `is_verified_scammer` flag. Only flag as verified after 3+ independent reports. |
| Graph query is slow (> 5 seconds) | Add LIMIT clauses. For the demo, pre-compute ring detection and cache results. |
| AuraDB connection drops | Retry with exponential backoff. The Neo4j Python driver handles this natively. |

---

## 5.4 · Scam Graph Visualization

### File Location
`frontend/app/graph/page.tsx` + `frontend/components/ScamGraph.tsx`

### What It Does
Displays an interactive force-directed graph of scam entities (phone numbers, UPI IDs, domains) and their relationships. Users can click nodes to see details and identify scam rings.

### Library Choice

**`react-force-graph-2d`** (recommended for the hackathon):
- Lightweight, easy to set up
- Good performance with < 500 nodes
- Built-in zoom, pan, drag
- Customizable node colors and sizes

**Alternative:** D3.js force simulation (more control, more code). Use only if you need custom layouts.

### Graph Data Format

**From backend `GET /graph/data`:**

```json
{
  "nodes": [
    {"id": "phone-9876543210", "label": "98765-43210", "type": "PhoneNumber", "report_count": 5, "group": 1},
    {"id": "upi-sbi-safe-ybl", "label": "sbi-safe@ybl", "type": "UPI_ID", "report_count": 3, "group": 1},
    {"id": "domain-sbi-kyc", "label": "sbi-kyc-verify.xyz", "type": "Domain", "report_count": 2, "group": 1},
    {"id": "phone-8765432109", "label": "87654-32109", "type": "PhoneNumber", "report_count": 2, "group": 2}
  ],
  "edges": [
    {"source": "phone-9876543210", "target": "upi-sbi-safe-ybl", "type": "USES_UPI"},
    {"source": "phone-9876543210", "target": "domain-sbi-kyc", "type": "LINKED_TO_DOMAIN"},
    {"source": "phone-8765432109", "target": "upi-sbi-safe-ybl", "type": "USES_UPI"}
  ]
}
```

### Visual Design

**Node styling by type:**

| Type | Color | Shape | Size | Icon |
|------|-------|-------|------|------|
| PhoneNumber | Red (#ef4444) | Circle | Proportional to report_count | 📞 |
| UPI_ID | Orange (#f97316) | Diamond | Proportional to report_count | 💳 |
| Domain | Purple (#a855f7) | Square | Fixed | 🌐 |
| BankAccount | Blue (#3b82f6) | Triangle | Fixed | 🏦 |
| ScammerName | Yellow (#eab308) | Star | Fixed | 👤 |

**Edge styling by type:**

| Type | Color | Width | Style |
|------|-------|-------|-------|
| USES_UPI | Orange | 2px | Solid |
| LINKED_TO_DOMAIN | Purple | 2px | Solid |
| CALLS | Red | 1px | Dashed |
| DEPOSITS_TO | Blue | 3px | Solid |
| INVOLVES | Gray | 1px | Dotted |

**Ring highlighting:**
- Nodes that are part of a detected ring get a pulsing red border
- Edges within a ring are thicker and brighter
- A legend shows: "🔴 Red ring = confirmed scam network"

### Interaction

**Click a node:**
- Show a detail panel on the right side:
  ```
  📞 98765-43210
  Type: Phone Number
  Reports: 5
  First Seen: 10 Jan 2025
  Last Seen: 15 Jan 2025
  Connected To:
    • sbi-safe@ybl (UPI)
    • sbi-kyc-verify.xyz (Domain)
    • 87654-32109 (Phone)
  Scam Types: Bank KYC (3), UPI Reversal (2)
  [Report This Number] [View Full History]
  ```

**Hover a node:**
- Show a tooltip with the label and type
- Highlight all connected nodes and edges (dim everything else)

**Zoom and pan:**
- Mouse wheel to zoom
- Click and drag to pan
- Double-click a node to center and zoom on it

### Demo Data

Pre-populate the graph with a realistic scam ring for the demo:

**Scenario:** A Bank KYC scam ring operating in Delhi-NCR

```
Phone Numbers (8):
  98765-43210 (primary caller)
  98765-43211 (secondary caller)
  87654-32109 (WhatsApp contact)
  76543-21098 (backup number)
  99887-76655 (new number, 2 days old)
  88776-65544 (victim callback number)
  77665-54433 (another victim)
  66554-43322 (recent addition)

UPI IDs (3):
  sbi-safe@ybl (primary collection)
  kyc-verify@paytm (secondary)
  ramesh.kumar@okhdfc (mule account)

Domains (2):
  sbi-kyc-verify.xyz (4 days old)
  rbi-verification.top (2 days old)

Bank Accounts (2):
  1234567890123 (SBI, linked to sbi-safe@ybl)
  9876543210123 (HDFC, linked to ramesh.kumar@okhdfc)

Relationships:
  98765-43210 → USES_UPI → sbi-safe@ybl
  98765-43210 → LINKED_TO → sbi-kyc-verify.xyz
  98765-43211 → USES_UPI → sbi-safe@ybl
  87654-32109 → USES_UPI → kyc-verify@paytm
  76543-21098 → LINKED_TO → rbi-verification.top
  sbi-safe@ybl → DEPOSITS_TO → 1234567890123
  ramesh.kumar@okhdfc → DEPOSITS_TO → 9876543210123
  99887-76655 → USES_UPI → sbi-safe@ybl
  (etc.)
```

This creates a visually impressive graph with a clear ring structure.

### Edge Cases

| Edge Case | Behavior |
|-----------|----------|
| Graph has > 500 nodes | Limit to 200 most-connected nodes. Add a "Load More" button. |
| Graph has 0 nodes (fresh install) | Show a placeholder: "No scam data yet. Submit reports or run the honeypot to populate the graph." |
| All nodes are disconnected (no rings) | Show individual nodes in a scattered layout. Add a note: "No connected rings detected yet." |
| Node labels overlap | Use collision detection in the force simulation. Increase repulsion force. |
| Mobile display | Simplify: show a list view instead of the graph. "Graph visualization requires a larger screen." |

---

## 5.5 · Scam Weather Map

### File Location
`frontend/components/ScamWeatherMap.tsx`

### What It Does
Displays a heatmap of active scam campaigns across India, aggregated from user reports and honeypot data. Shows which cities are being targeted and what types of scams are prevalent.

### Library
**`react-leaflet`** with **`leaflet.heat`** plugin for heat layers.

### Data Source

**From backend `GET /map/heatmap`:**

```json
{
  "cities": [
    {"city": "Delhi", "lat": 28.6139, "lng": 77.2090, "scam_count": 47, "top_type": "bank_kyc", "intensity": 0.9},
    {"city": "Mumbai", "lat": 19.0760, "lng": 72.8777, "scam_count": 38, "top_type": "upi_reversal", "intensity": 0.75},
    {"city": "Bangalore", "lat": 12.9716, "lng": 77.5946, "scam_count": 29, "top_type": "job_offer", "intensity": 0.6},
    {"city": "Hyderabad", "lat": 17.3850, "lng": 78.4867, "scam_count": 22, "top_type": "fedex", "intensity": 0.45},
    {"city": "Chennai", "lat": 13.0827, "lng": 80.2707, "scam_count": 18, "top_type": "lottery", "intensity": 0.35},
    {"city": "Kolkata", "lat": 22.5726, "lng": 88.3639, "scam_count": 15, "top_type": "impersonation", "intensity": 0.3},
    {"city": "Pune", "lat": 18.5204, "lng": 73.8567, "scam_count": 12, "top_type": "investment", "intensity": 0.25},
    {"city": "Jaipur", "lat": 26.9124, "lng": 75.7873, "scam_count": 9, "top_type": "bank_kyc", "intensity": 0.2},
    {"city": "Ahmedabad", "lat": 23.0225, "lng": 72.5714, "scam_count": 7, "top_type": "electricity", "intensity": 0.15},
    {"city": "Lucknow", "lat": 26.8467, "lng": 80.9462, "scam_count": 5, "top_type": "relative_distress", "intensity": 0.1}
  ],
  "national_stats": {
    "total_reports_this_week": 202,
    "top_scam_type": "bank_kyc",
    "trend": "increasing"
  }
}
```

### Visual Design

**Map configuration:**
- Center: India (lat 22, lng 78)
- Zoom level: 5 (shows all of India)
- Tile layer: OpenStreetMap (free, no API key) or CartoDB dark matter (matches the dark theme)
- Heat layer: red-orange-yellow gradient based on scam intensity

**City markers:**
- Circle markers sized by scam count
- Color by top scam type:
  - Bank KYC: Red
  - UPI Reversal: Orange
  - Job Offer: Blue
  - FedEx: Purple
  - Lottery: Green
  - Impersonation: Yellow

**Click a city marker:**
- Popup shows:
  ```
  🏙️ Delhi
  47 scams this week
  Top type: Bank KYC Fraud
  Trend: 📈 Increasing (+12 from last week)
  ```

**Legend:**
```
🔴 Bank KYC    🟠 UPI Reversal    🔵 Job Offer
🟣 FedEx       🟢 Lottery         🟡 Impersonation
```

### Demo Data

For the hackathon, hardcode the city data above. Don't try to aggregate from real reports — you won't have enough data. The map is a visualization showcase, not a real-time analytics tool.

### Edge Cases

| Edge Case | Behavior |
|-----------|----------|
| No data for a region | Don't show markers. The heat layer will be empty in that area. |
| Leaflet fails to load tiles (no internet) | Show a fallback: a static image of India with city labels and scam counts. |
| Too many markers in one city | Cluster them using `react-leaflet-cluster`. Show "Delhi: 47 scams" as a single cluster marker. |
| Mobile display | Leaflet works on mobile but the map is small. Allow pinch-to-zoom. |

---

## 5.6 · Cybercrime Report Generator

### File Location
`backend/app/services/report_generator.py` + `frontend/components/ReportGenerator.tsx`

### What It Does
Auto-generates a formatted complaint report that the user can copy and paste into the National Cyber Crime Reporting Portal (cybercrime.gov.in) or read out to the 1930 helpline.

### Report Template

**For cybercrime.gov.in (text format):**

```
CYBER CRIME COMPLAINT
=====================

Date of Incident: {date}
Time of Incident: {time}
Report Generated By: Mirage AI Scam Shield

COMPLAINANT DETAILS:
Name: {user_name}
Phone: {user_phone}
City: {user_city}
Email: {user_email}

INCIDENT DETAILS:
Type of Fraud: {scam_type_readable}
Mode of Contact: {phone_call | whatsapp | sms | email | website}
Scammer's Phone Number: {scammer_phone}
Scammer's UPI ID: {scammer_upi}
Scammer's Bank Details: {scammer_bank} (A/c: {account}, IFSC: {ifsc})
Fraudulent URL: {scammer_url}

AMOUNT INVOLVED:
Amount Demanded: ₹{amount_demanded}
Amount Lost: ₹{amount_lost} (if any)
Transaction Reference: {txn_ref} (if any)

NARRATIVE:
{auto-generated narrative based on the scam report and conversation log}

Example: "On 15 January 2025 at approximately 3:30 PM, I received a phone call from +91-98765-43210. The caller claimed to be 'Officer Rajesh' from the State Bank of India fraud department. They stated that my KYC was incomplete and my account would be blocked within 30 minutes. They directed me to a website (sbi-kyc-verify.xyz) and asked me to share my OTP and ATM PIN. I recognized this as a scam and did not share any details. The caller's UPI ID was sbi-safe@ybl."

EVIDENCE:
- Call recording: {attached/available}
- Screenshots: {attached/available}
- Message logs: {attached/available}
- Domain analysis: {domain} registered {age} days ago (not official)

ACTION REQUESTED:
1. Block the scammer's phone number: {phone}
2. Freeze the scammer's UPI ID: {upi}
3. Investigate the fraudulent domain: {domain}
4. Take action against the scammer's bank account: {account}

This report was auto-generated by Mirage AI Scam Shield.
For assistance, call the National Cyber Crime Helpline: 1930
```

**For 1930 Helpline (script format):**

```
📞 1930 HELPLINE SCRIPT

When you call 1930, say:

"Hello, I want to report a cyber fraud.

My name is {name} from {city}.

I received a scam {call/message} on {date} at {time}.

The scammer's number is {phone}.

They pretended to be from {institution} and tried to {scam_goal}.

Their UPI ID is {upi}.

I {did/did not} lose money. The amount is ₹{amount}.

Please block this number and UPI ID.

My complaint reference number is {ref}."
```

### Generation Logic

**Step 1: Collect data**
- From the scam report: verdict, IOCs, evidence
- From the user profile: name, phone, city
- From the conversation log (if honeypot): full transcript
- From the Guardian (if live call): recording, transcript, stages

**Step 2: Generate narrative**
- Use Groq Llama 3.3 to convert the structured data into a natural-language narrative
- Prompt: "Convert this scam incident data into a formal complaint narrative for the Indian cyber crime portal. Be factual, chronological, and specific."

**Step 3: Format the report**
- Fill in the template with the collected data
- Replace missing fields with "[Not available]"
- Add timestamps and reference numbers

**Step 4: Display and export**
- Show the report in a modal on the frontend
- "Copy to Clipboard" button (copies the full text)
- "Download as PDF" button (use `jsPDF` or `html2pdf` library)
- "Report to 1930" button (opens `tel:1930` on mobile)
- "Open Cyber Crime Portal" button (opens `https://cybercrime.gov.in` in new tab)

### API Endpoint

**`POST /report/generate`**

Request:
```json
{
  "report_id": "uuid",
  "user_name": "Priya Sharma",
  "user_phone": "9876543210",
  "user_city": "Mumbai",
  "amount_lost": 0
}
```

Response:
```json
{
  "report_text": "CYBER CRIME COMPLAINT\n=====================\n...",
  "helpline_script": "📞 1930 HELPLINE SCRIPT\n...",
  "report_id": "RPT-2025-001234"
}
```

### Edge Cases

| Edge Case | Behavior |
|-----------|----------|
| User lost money | Emphasize urgency: "⚠️ Since money was lost, call 1930 IMMEDIATELY. The faster you report, the higher the chance of recovering your funds." |
| No IOCs available | Generate a minimal report with just the narrative. Note: "Limited evidence available. Please attach any screenshots or recordings manually." |
| User wants to report anonymously | Remove name and phone from the report. Use "Anonymous" as the complainant. |
| Report is for a honeypot session (no real victim) | Mark as "Intelligence Report" instead of "Victim Complaint". Format for law enforcement, not the cyber crime portal. |

---

## File Summary for Phase 5

| File | Purpose | Lines (estimate) |
|------|---------|-----------------|
| `backend/app/services/honeypot_engine.py` | Persona agent + conversation loop | ~200 |
| `backend/app/services/ioc_extractor.py` | Regex + LLM IOC extraction | ~180 |
| `backend/app/services/scam_graph.py` | Neo4j ingestion + ring detection | ~200 |
| `backend/app/services/report_generator.py` | Report template + LLM narrative | ~120 |
| `backend/app/clients/neo4j_client.py` | Neo4j driver wrapper | ~100 |
| `backend/app/routers/honeypot.py` | Honeypot API endpoints | ~80 |
| `backend/app/routers/graph.py` | Graph + map API endpoints | ~60 |
| `frontend/app/graph/page.tsx` | Graph + Map page layout | ~80 |
| `frontend/components/ScamGraph.tsx` | Force-directed graph | ~150 |
| `frontend/components/ScamWeatherMap.tsx` | Leaflet heatmap | ~120 |
| `frontend/components/HoneypotChat.tsx` | Honeypot conversation UI | ~150 |
| `frontend/components/ReportGenerator.tsx` | Report display + copy + PDF | ~120 |
| `backend/tests/seed_graph.py` | Script to populate demo data | ~100 |

**Total estimated:** ~1,660 lines across Python + TypeScript

---

## Phase 5 Completion Checklist

```
□ Honeypot agent responds in character as "Ramesh"
□ Agent wastes time with mishearing, tangents, and confusion
□ Agent extracts UPI IDs from scammer messages
□ Agent extracts phone numbers from scammer messages
□ Agent extracts URLs from scammer messages
□ Agent handles frustrated scammers (conversation health)
□ Agent never breaks character or reveals it's an AI
□ IOC extractor catches phone numbers via regex
□ IOC extractor catches UPI IDs via regex
□ IOC extractor catches URLs via regex
□ IOC extractor catches bank accounts via regex
□ LLM fallback catches IOCs that regex misses
□ IOCs are deduplicated and validated
□ Neo4j nodes are created for all IOC types
□ Neo4j relationships link entities correctly
□ Ring detection query finds connected clusters
□ Graph visualization renders nodes and edges
□ Nodes are color-coded by type
□ Clicking a node shows detail panel
□ Scam rings are highlighted in red
□ Pre-seeded demo data shows a realistic scam ring
□ Weather map displays Indian cities with heat markers
□ Clicking a city shows scam count and top type
□ Report generator produces formatted complaint text
□ Report includes all IOCs and narrative
□ "Copy to Clipboard" button works
□ "Call 1930" button opens dialer on mobile
□ Helpline script is generated for phone reporting
□ Full honeypot → IOC → Graph → Report pipeline works end-to-end
```

**When every box is checked, Phase 5 is done. This is the bonus layer — if you're short on time, pre-seed the graph and map with static data and focus the demo on the honeypot chat UI.**

---

Ready for Phase 6 (Dashboard Polish) and Phase 7 (Demo & Pitch)? Those are the final phases that tie everything together and make you presentation-ready. Say the word.