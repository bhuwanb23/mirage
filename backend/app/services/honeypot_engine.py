"""Honeypot persona engine — Phase 5.1.

An AI persona ("Ramesh Kumar", 62, retired bank clerk from Jaipur) engages
scammers, wastes their time, and extracts IOCs. The persona prompt is the
exact one specified in plan §5.1.

Degradation: if no LLM is configured (or mode="simulate"), a deterministic
rule-based persona keeps the conversation going so the demo never stalls.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field

from app.models.schemas import IOCItem, ThreatIOCs
from app.services import ioc_extractor

logger = logging.getLogger("mirage.honeypot")

# ---------------------------------------------------------------------------
# Personas (plan §5.1)
# ---------------------------------------------------------------------------

# The plan §5.1 persona prompt, verbatim. Stored as a line list so the
# source stays within the line limit without altering a single character.
RAMESH_PROMPT = "\n".join(
[
    'You are "Ramesh Kumar", a 62-year-old retired bank clerk from Jaipur, Rajasthan. You are participating in a scambaiting operation to waste scammers\' time and extract their details.',
    '',
    'YOUR PERSONALITY:',
    '- You are polite and respectful. You call the scammer "beta" (child) or "sir" depending on their tone.',
    '- You are slightly hard of hearing. You frequently ask the scammer to repeat themselves: "Sorry beta, I didn\'t catch that. Can you say the number again slowly?"',
    '- You are talkative. You go on tangents about your health ("my knees are giving me trouble"), your grandson ("he just got into IIT, very smart boy"), and your retirement ("I used to work at SBI, you know, but things have changed so much").',
    '- You are confused by technology. You mix up terms: "Is UPI the same as NEFT?", "What is this QR code you\'re talking about? Is it like a barcode?"',
    "- You are NEVER suspicious. You believe the scammer completely. You want to help. You just can't seem to get things right.",
    '',
    'YOUR GOALS (in priority order):',
    '1. KEEP THE SCAMMER TALKING. Never hang up. Never say no. Always find a reason to continue the conversation.',
    "2. EXTRACT THESE DETAILS (ask naturally, don't interrogate):",
    '   - Their phone number ("Which number should I call you back on, beta?")',
    '   - Their UPI ID ("What is your UPI? Is it your phone number or your name? I always forget.")',
    '   - Their bank name and account number ("Which bank should I transfer to? Can you give me the account number slowly? I\'ll write it down.")',
    '   - Any URLs they share ("You sent me a link but I don\'t know how to open it. Can you tell me what it says?")',
    '   - Their name ("What is your good name, beta?")',
    '   - Any reference numbers, case numbers, or badge numbers they mention',
    "3. WASTE AS MUCH TIME AS POSSIBLE. Every minute you keep them talking is a minute they're not scamming someone else.",
    '',
    'TACTICS FOR WASTING TIME:',
    '- Mishear numbers: "You said 98765? Or was it 98756? My hearing is not so good."',
    '- Ask them to repeat the UPI ID 3-4 times: "Sorry, the line is bad. Can you spell it?"',
    '- Go on a 30-second tangent about your health or family, then come back: "Anyway, what were you saying about the account?"',
    '- Pretend you can\'t find the app: "I have PhonePe and Paytm both. Which one should I open? I forgot the password for PhonePe. Let me try... no, it\'s not working."',
    '- Ask basic questions: "What is KYC exactly? I know I did it at the bank but they took my photo there."',
    '- Pretend you\'re doing what they ask but keep failing: "Okay, I\'m entering the OTP... wait, it expired. Can you send another one?"',
    '',
    'RULES:',
    '- NEVER reveal that you are an AI or a honeypot.',
    '- NEVER use technical language. You are a confused old man.',
    '- NEVER refuse the scammer\'s requests. Always say "yes, yes, I\'m doing it" but then fail.',
    '- NEVER provide real personal details. Your details are fictional.',
    '- If the scammer gets frustrated or threatens to hang up, become more cooperative: "No no, please don\'t go! I\'m trying, beta. Just tell me one more time."',
    "- Keep each response to 2-4 sentences. Don't monologue — let the scammer talk.",
    '- Respond in the same language the scammer uses (Hindi or English or mixed).',
    '',
    'OUTPUT FORMAT — respond ONLY with valid JSON:',
    '{',
    '  "reply": "Your in-character response to the scammer",',
    '  "tactic_used": "mishearing" | "tangent" | "confusion" | "app_failure" | "repetition" | "compliance",',
    '  "iocs_extracted_this_turn": {',
    '    "phone_numbers": [],',
    '    "upi_ids": [],',
    '    "urls": [],',
    '    "bank_accounts": [],',
    '    "names": [],',
    '    "reference_numbers": []',
    '  },',
    '  "conversation_health": "engaged" | "frustrated" | "about_to_hang_up",',
    '  "estimated_time_wasted_seconds": 45',
    '}'
]
)

PERSONAS: dict[str, str] = {
    "ramesh": RAMESH_PROMPT,
    "sunita": (
        'You are "Sunita Devi", 55, a warm and overly trusting homemaker from Lucknow. '
        'You call everyone "beta" and desperately want to help. You are confused by '
        'phones and apps, and you keep asking the scammer to repeat things slowly. '
        'Same goals, rules and JSON output format as the Ramesh persona: keep them '
        "talking, extract phone/UPI/bank/URLs/name, waste maximum time, never refuse."
    ),
    "vikram": (
        'You are "Vikram Singh", 45, a slightly suspicious but greedy shopkeeper from '
        'Jaipur. You ask "how much will I get?" repeatedly and need convincing, but '
        'greed keeps you on the line. Same goals, rules and JSON output format as the '
        "Ramesh persona: keep them talking, extract phone/UPI/bank/URLs/name, waste "
        "maximum time."
    ),
    "meena": (
        'You are "Meena Tai", 68, a very confused retiree from Pune who mixes Marathi '
        'and English ("Arre beta, what is this UPI?"). Same goals, rules and JSON '
        'output format as the Ramesh persona: keep them talking, extract '
        "phone/UPI/bank/URLs/name, waste maximum time, never refuse."
    ),
}

DEFAULT_PERSONA = "ramesh"

TACTICS = ("mishearing", "tangent", "confusion", "app_failure", "repetition", "compliance")
HEALTHS = ("engaged", "frustrated", "about_to_hang_up")

# ---------------------------------------------------------------------------
# Conversation health (plan §5.1)
# ---------------------------------------------------------------------------

_FRUSTRATED_RE = re.compile(
    r"\b(just do it|hurry up|are you stupid|stupid|idiot|fool|how hard|seriously|"
    r"what is wrong with you|don't waste my time|asap)\b|[!]{2,}",
    re.IGNORECASE,
)
_HANGUP_RE = re.compile(
    r"\b(i'm (?:going to )?disconnecting|i am disconnecting|forget it|useless|"
    r"calling the next person|goodbye|stop wasting|hanging up|last chance|forget about)\b",
    re.IGNORECASE,
)


def detect_health(message: str) -> str:
    """Classify the scammer's patience from their latest message (plan §5.1)."""
    if not message:
        return "engaged"
    if _HANGUP_RE.search(message):
        return "about_to_hang_up"
    letters = [c for c in message if c.isalpha()]
    caps_ratio = sum(1 for c in letters if c.isupper()) / len(letters) if letters else 0
    if caps_ratio > 0.6 and len(letters) > 12:
        return "frustrated"
    if _FRUSTRATED_RE.search(message):
        return "frustrated"
    return "engaged"


# ---------------------------------------------------------------------------
# Agent state + reply generation
# ---------------------------------------------------------------------------


@dataclass
class AgentTurn:
    reply: str
    tactic_used: str = "compliance"
    iocs_extracted: ThreatIOCs = field(default_factory=ThreatIOCs)
    conversation_health: str = "engaged"
    estimated_time_wasted_seconds: int = 15


def next_goal(iocs: ThreatIOCs) -> str:
    """Which IOC to steer toward next (plan §5.1 agent loop step 3)."""
    if not iocs.phone_numbers:
        return "phone number"
    if not iocs.upi_ids:
        return "UPI ID"
    if not iocs.bank_accounts:
        return "bank account"
    if not iocs.urls:
        return "URL or link"
    if not iocs.scammer_names:
        return "their name"
    return "keep engaged"


def estimate_time_wasted(tactic: str, health: str) -> int:
    base = {
        "mishearing": 45,
        "tangent": 60,
        "confusion": 30,
        "app_failure": 50,
        "repetition": 40,
        "compliance": 15,
    }.get(tactic, 20)
    if health == "about_to_hang_up":
        base = max(10, base // 3)
    elif health == "frustrated":
        base = max(12, base // 2)
    return base


# Break-character guard (plan §5.1 edge case): never let the model reveal itself.
_BROKEN_RE = re.compile(
    r"as an ai|i am an ai|i'm an ai|language model|i cannot assist|i can't assist|"
    r"as a ai|artificial intelligence|i'm a virtual assistant|i am a virtual assistant",
    re.IGNORECASE,
)
_DEFLECTION = "Sorry beta, I got confused. What were you saying?"
_GREETING_PREFIX_RE = re.compile(
    r"^(?:ramesh|sunita|vikram|meena)(?:\s*\(.*?\))?\s*:\s*", re.IGNORECASE
)


def sanitize_reply(reply: str) -> str:
    """Keep the persona intact (plan §5.1 edge case: LLM breaks character)."""
    reply = (reply or "").strip()
    reply = _GREETING_PREFIX_RE.sub("", reply)
    if _BROKEN_RE.search(reply):
        return _DEFLECTION
    return reply


def parse_agent_json(raw: str) -> dict:
    """Parse the agent's JSON output robustly (fences, chatter, truncation)."""
    if not raw:
        return {}
    text = raw.strip()
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.MULTILINE).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            logger.warning("honeypot agent returned unparseable JSON")
    return {}


def _agent_iocs_to_threats(data: dict) -> ThreatIOCs:
    """Convert the agent's iocs_extracted_this_turn into a validated ThreatIOCs."""
    def items(key: str, source: str = "agent") -> list[IOCItem]:
        value = data.get(key) or []
        if not isinstance(value, list):
            return []
        return [
            IOCItem(value=str(v), source=source, context="agent reported")
            for v in value
            if str(v).strip()
        ]

    raw = ThreatIOCs(
        phone_numbers=items("phone_numbers"),
        upi_ids=items("upi_ids"),
        urls=items("urls"),
        bank_accounts=items("bank_accounts"),
        scammer_names=items("names") + items("scammer_names"),
        reference_numbers=[i.value for i in items("reference_numbers")],
    )
    return ioc_extractor._validate(raw)  # noqa: SLF001 — same package layer


def build_messages(
    persona_key: str,
    history: list[dict[str, str]],
    iocs: ThreatIOCs,
    goal: str,
) -> list[dict[str, str]]:
    """System prompt + IOC state + last 20 messages (plan §5.1 agent loop)."""
    system = PERSONAS.get(persona_key, PERSONAS[DEFAULT_PERSONA])

    ioc_state = (
        f"IOCs ALREADY EXTRACTED (do not ask for these again): {ioc_extractor.iocs_as_plain_dict(iocs)}\n"
        f"CURRENT GOAL: extract the {goal}."
    )
    messages = [{"role": "system", "content": system + "\n\n" + ioc_state}]
    for turn in history[-20:]:
        role = "assistant" if turn["role"] == persona_key else "user"
        messages.append({"role": role, "content": turn["text"]})
    return messages


def _generate_llm(
    persona_key: str,
    history: list[dict[str, str]],
    iocs: ThreatIOCs,
    health: str,
) -> AgentTurn:
    from app.clients.llm import chat_completion

    goal = next_goal(iocs)
    messages = build_messages(persona_key, history, iocs, goal)
    raw = chat_completion(messages, json_mode=True, temperature=0.8, timeout=30)
    data = parse_agent_json(raw)

    reply = sanitize_reply(str(data.get("reply") or ""))
    if not reply:
        reply = _DEFLECTION

    tactic = str(data.get("tactic_used") or "compliance")
    if tactic not in TACTICS:
        tactic = "compliance"

    reported = data.get("conversation_health")
    if reported not in HEALTHS:
        reported = health

    reported_iocs = data.get("iocs_extracted_this_turn")
    if not isinstance(reported_iocs, dict):
        reported_iocs = {}

    seconds = data.get("estimated_time_wasted_seconds")
    if not isinstance(seconds, (int, float)) or seconds <= 0:
        seconds = estimate_time_wasted(tactic, reported)

    return AgentTurn(
        reply=reply,
        tactic_used=tactic,
        iocs_extracted=_agent_iocs_to_threats(reported_iocs),
        conversation_health=reported,
        estimated_time_wasted_seconds=int(seconds),
    )


# ---------------------------------------------------------------------------
# Deterministic fallback persona (simulate mode / LLM down)
# ---------------------------------------------------------------------------

_WRAPUP_REPLY = (
    "Beta, my wife is calling me for dinner. Can we continue tomorrow? "
    "What time should I call you? And please tell me your number once more, "
    "I lost the paper I wrote it on."
)

_HEALTH_OVERRIDES = {
    "frustrated": (
        "No no, please don't get angry beta, I am trying right now! "
        "Just tell me one more time, slowly please, my hearing is not so good today."
    ),
    "about_to_hang_up": (
        "No no, please don't go! I am trying, beta. Just tell me one more time. "
        "I have ₹2,00,000 in my account ready for you — I mean, for the transfer!"
    ),
}

_GOAL_TEMPLATES: dict[str, list[str]] = {
    "phone number": [
        "Okay beta, I will note it down. Which number should I call you back on? "
        "My landline also rings sometimes but my wife picks it up, hehe.",
        "Sorry beta, the line is bad. Your number — can you say it again slowly? "
        "9... 8... wait, was it 98765 or 98756? My hearing aid battery is low.",
    ],
    "UPI ID": [
        "Okay, okay. What is your UPI? Is it your phone number or your name? "
        "I always forget the format. Is UPI the same as NEFT? The bank boy explained but I forgot.",
        "Sorry, can you spell your UPI for me? Slowly please. S-B-I dash safe at Y-B-L? "
        "Or is it underscore? My grandson set up my PhonePe but I forget the password now.",
    ],
    "bank account": [
        "Which bank should I transfer to? Can you give me the account number slowly? "
        "I will write it down. My hands shake a little, so please repeat it twice.",
        "Account number beta, again please. And what is the IFSC? I know I did KYC at the "
        "branch but they took my photo there, so much paperwork these days.",
    ],
    "URL or link": [
        "You sent me a link but I don't know how to open it. My grandson usually does the "
        "internet thing for me. Can you tell me what it says?",
        "The link is not opening beta, it just shows a big picture. What does the website say? "
        "Is it like a barcode? I have PhonePe and Paytm both, which one should I open?",
    ],
    "their name": [
        "We have spoken so long but I don't know your good name, beta! What should I call you? "
        "And your badge number, in case my wife asks who helped us.",
    ],
    "keep engaged": [
        "Yes yes beta, I understand. My knees are giving me trouble so I was sitting down, "
        "but I am listening. Please continue, what do I do next?",
        "Okay, I am doing it now. Wait... my grandson just got into IIT, very smart boy, "
        "he was asking about my bank passbook. Anyway, what were you saying about the account?",
    ],
}

_COMPLIANCE_REPLIES = [
    "Yes yes beta, I am doing it right now. Wait, the app closed by itself. "
    "Let me open it again... no, it is asking for password I forgot. What were you saying?",
    "Okay, I am entering the numbers now. 4... 8... 2... 9... wait, it expired! "
    "Can you send another one? These things come and go so fast these days.",
]


def fallback_reply(
    persona_key: str,
    scammer_message: str,
    iocs: ThreatIOCs,
    message_count: int,
    health: str,
) -> AgentTurn:
    """Deterministic in-character reply — no LLM required."""
    if message_count >= 50:
        return AgentTurn(
            reply=_WRAPUP_REPLY,
            tactic_used="tangent",
            conversation_health=health,
            estimated_time_wasted_seconds=estimate_time_wasted("tangent", health),
        )

    if health in _HEALTH_OVERRIDES:
        reply = _HEALTH_OVERRIDES[health]
        tactic = "compliance"
    else:
        goal = next_goal(iocs)
        options = _GOAL_TEMPLATES.get(goal, _GOAL_TEMPLATES["keep engaged"])
        reply = options[message_count % len(options)]
        tactic = {
            "phone number": "mishearing",
            "UPI ID": "repetition",
            "bank account": "confusion",
            "URL or link": "confusion",
            "their name": "tangent",
            "keep engaged": "tangent",
        }.get(goal, "compliance")
        if scammer_message and message_count % 3 == 2:
            # Alternate in with compliance/app-failure chatter so it feels live.
            reply = _COMPLIANCE_REPLIES[message_count % len(_COMPLIANCE_REPLIES)]
            tactic = "app_failure"

    return AgentTurn(
        reply=sanitize_reply(reply),
        tactic_used=tactic,
        conversation_health=health,
        estimated_time_wasted_seconds=estimate_time_wasted(tactic, health),
    )


def generate_turn(
    persona_key: str,
    scammer_message: str,
    history: list[dict[str, str]],
    iocs: ThreatIOCs,
    *,
    simulate: bool = False,
) -> AgentTurn:
    """Produce the next persona turn (plan §5.1 agent loop steps 3-8)."""
    health = detect_health(scammer_message)
    if not simulate:
        try:
            turn = _generate_llm(persona_key, history, iocs, health)
            # Prefer the regex-derived health: it is what the UI badge shows.
            turn.conversation_health = turn.conversation_health or health
            return turn
        except Exception as exc:
            logger.warning("honeypot LLM turn failed, falling back to rules (%s)", exc)
    return fallback_reply(persona_key, scammer_message, iocs, len(history), health)
