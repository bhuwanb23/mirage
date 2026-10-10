"""Scam script generator (Phase 3.2) — LLM generation + hard fallback.

Generates a personalized 5-stage scam call script (hook -> authority ->
isolation -> urgency -> payment) from the user's profile. The LLM is asked
for strict JSON; every failure mode (no provider, bad JSON, missing stages,
too short) degrades to the pre-written templates in `fallback_scripts.py` so
a live demo never breaks.
"""

from __future__ import annotations

import json
import logging
import re
from functools import lru_cache
from typing import Any

from app.services.drill_store import new_id
from app.services.fallback_scripts import FALLBACK_SCRIPTS, render_fallback

logger = logging.getLogger("mirage.script_generator")

STAGES = ["hook", "authority", "isolation", "urgency", "payment"]

SYSTEM_PROMPT = """You are a scam script generator for Mirage, an anti-scam training platform.
Your job is to generate REALISTIC scam call scripts that are used to TRAIN
people to recognize scams.

CRITICAL CONTEXT: These scripts are used in a controlled educational
environment. The user has CONSENTED to receiving a simulated scam. The script
will be played to the user, and they will be asked to identify it as a scam.
Afterward, they receive a detailed debrief explaining every tactic used.

RULES FOR SCRIPT GENERATION:

1. The script must be a PHONE CALL monologue (one side — the scammer
   speaking). Include natural pauses marked as [pause 2s], [pause 1s], etc.

2. The script MUST include ALL 5 stages in order. Mark each stage transition
   with a tag:
   [STAGE: HOOK] — Initial contact, grab attention
   [STAGE: AUTHORITY] — Impersonate an institution
   [STAGE: ISOLATION] — Prevent the victim from seeking help
   [STAGE: URGENCY] — Create time pressure
   [STAGE: PAYMENT] — Demand money or sensitive info

3. The script must be PERSONALIZED using the provided profile data. Use the
   person's real name, city, bank, and employer naturally in the conversation.

4. The script must sound NATURAL and CONVERSATIONAL. Real scammers don't
   sound robotic. Include filler words ("uh", "you know", "basically"), false
   empathy ("I understand this is stressful, madam"), and professional-sounding
   language.

5. The script should be 45–90 seconds long when spoken aloud (roughly
   120–250 words).

6. Include specific, realistic details:
   - Fake reference numbers (e.g., "Case number KYC-2025-8834")
   - Fake officer names (e.g., "This is Officer Rajesh from the fraud dept")
   - Specific amounts (e.g., "₹49,999 will be deducted")
   - Specific deadlines (e.g., "within the next 30 minutes")

7. DO NOT include any real bank phone numbers, real URLs, or real UPI IDs.
   Use obviously fake ones:
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
      "script": "This is Officer Rajesh from the SBI fraud desk. ...",
      "tactic": "Impersonates a specific bank officer with a fake badge"
    },
    "isolation": {
      "timestamp_hint": "0:20-0:30",
      "script": "Priya ji, this is confidential. Do not tell anyone. ...",
      "tactic": "Prevents the victim from getting a second opinion"
    },
    "urgency": {
      "timestamp_hint": "0:30-0:45",
      "script": "Your account will be frozen in 30 minutes. ...",
      "tactic": "Creates extreme time pressure to prevent rational thinking"
    },
    "payment": {
      "timestamp_hint": "0:45-1:00",
      "script": "Share the OTP on your phone, and your ATM PIN. ...",
      "tactic": "Demands OTP and PIN — no real bank ever asks for these"
    }
  },
  "full_script": "Complete script as one continuous text, with [pause] markers",
  "red_flags_planted": [
    "Used full name to create false familiarity",
    "Claimed to be from SBI fraud department",
    "Asked to keep the call secret from family",
    "Threatened account freeze within 30 minutes",
    "Asked for OTP and ATM PIN over the phone"
  ],
  "difficulty_level": "medium"
}
"""

USER_PROMPT = """Generate a scam call script with the following parameters:

SCAM TYPE: {scam_type}
TARGET PROFILE:
- Name: {name}
- City: {city}
- Bank: {bank_full_name}
- Employer: {employer}
- Relative: {relative}

DIFFICULTY: {difficulty}
- Easy: Obvious red flags, over-the-top urgency, bad grammar
- Medium: Realistic, most people would fall for it
- Hard: Very sophisticated, mimics real bank comms, only subtle red flags

Make it sound like a real phone call. The scammer should sound
professional and convincing.
"""

VALID_DIFFICULTIES = {"easy", "medium", "hard"}
VALID_SCAM_TYPES = set(FALLBACK_SCRIPTS)

# ~2.5 spoken words per second for deliberate scammer speech
_WORDS_PER_SECOND = 2.5
_MIN_WORDS = 80
_MAX_WORDS = 300


# ---------------------------------------------------------------------------
# Sanitizers — the LLM must never leak a real contact point into the demo
# ---------------------------------------------------------------------------

_PHONE_RE = re.compile(
    r"(?<![\d-])(?:\+?91[-\s]?)?(?:\d{5}[-\s]?\d{5}|1800[-\s]?\d{3}[-\s]?\d{4})(?![\d-])"
)
_URL_RE = re.compile(
    r"https?://[^\s\"']+|www\.[^\s\"']+|"
    r"(?:[a-z0-9-]+\.)+(?:com|in|net|org|xyz|co)(?:/[^\s\"']*)?",
    re.I,
)
_UPI_RE = re.compile(r"\b[\w.\-]+@(?:ybl|okaxis|paytm|ibl|upi)\b", re.I)


def sanitize_script(text: str) -> str:
    """Replace real-looking phone numbers / URLs / UPI ids with fake ones."""
    text = _PHONE_RE.sub("98765-XXXXX", text)
    text = _URL_RE.sub("fake-bank-verify.xyz", text)
    text = _UPI_RE.sub("scammer-demo@ybl", text)
    return text


def _truncate_words(text: str, max_words: int = _MAX_WORDS) -> str:
    words = text.split()
    if len(words) <= max_words:
        return text
    clipped = " ".join(words[:max_words])
    # snap back to the last sentence boundary
    for sep in [". ", "! ", "? "]:
        idx = clipped.rfind(sep)
        if idx > max_words // 2:
            return clipped[: idx + 1]
    return clipped + "."


def estimate_duration_seconds(text: str) -> float:
    words = max(len(text.split()), 1)
    return round(words / _WORDS_PER_SECOND, 1)


@lru_cache(maxsize=1)
def fallback_durations() -> dict[str, float]:
    """Estimated duration (seconds) of each fallback template.

    Powers the "~60s call" hint on the drill setup screen. Rendered once with
    a probe profile — placeholder names don't change the word count materially.
    """
    from app.services.footprint_scraper import build_profile

    probe = build_profile(name="Sample User")
    return {
        scam_type: estimate_duration_seconds(
            render_fallback(scam_type, probe)["full_script"]
        )
        for scam_type in sorted(FALLBACK_SCRIPTS)
    }


# ---------------------------------------------------------------------------
# LLM path
# ---------------------------------------------------------------------------

def _extract_json(raw: str) -> dict[str, Any] | None:
    """Pull a JSON object out of an LLM reply (tolerates code fences / prose)."""
    if not raw:
        return None
    candidate = raw.strip()
    if candidate.startswith("```"):
        candidate = re.sub(r"^```[a-zA-Z]*\s*", "", candidate)
        candidate = re.sub(r"\s*```$", "", candidate)
    try:
        obj = json.loads(candidate)
        return obj if isinstance(obj, dict) else None
    except (json.JSONDecodeError, ValueError):
        pass
    start, end = candidate.find("{"), candidate.rfind("}")
    if start != -1 and end > start:
        try:
            obj = json.loads(candidate[start : end + 1])
            return obj if isinstance(obj, dict) else None
        except (json.JSONDecodeError, ValueError):
            return None
    return None


def _normalize(
    data: dict[str, Any],
    profile: dict[str, Any],
    scam_type: str,
    difficulty: str,
) -> dict[str, Any] | None:
    """Validate + normalize LLM JSON into our canonical shape. None = unusable."""
    raw_stages = data.get("stages")
    if not isinstance(raw_stages, dict):
        return None

    stages: dict[str, dict[str, str]] = {}
    for stage in STAGES:
        entry = raw_stages.get(stage)
        if not isinstance(entry, dict):
            return None
        script = str(entry.get("script") or "").strip()
        if not script:
            return None
        stages[stage] = {
            "script": sanitize_script(script),
            "tactic": str(entry.get("tactic") or "").strip(),
            "timestamp_hint": str(entry.get("timestamp_hint") or "").strip(),
        }

    full_script = sanitize_script(
        str(data.get("full_script") or "").strip()
        or " ".join(s["script"] for s in stages.values())
    )

    # too short -> unusable, caller retries / falls back
    if len(full_script.split()) < _MIN_WORDS:
        return None
    full_script = _truncate_words(full_script)

    flags = data.get("red_flags_planted")
    if not isinstance(flags, list) or not flags:
        flags = [
            "Used full name to create false familiarity",
            "Impersonated an official from a trusted institution",
            "Asked to keep the call secret from family",
            "Created an artificial deadline",
            "Demanded money or secrets over the phone",
        ]

    default_title = f"Fake {profile.get('bank_full_name', 'Bank')} Scam Call"
    return {
        "scam_type": scam_type,
        "title": sanitize_script(str(data.get("title") or default_title).strip()),
        "stages": stages,
        "full_script": full_script,
        "red_flags_planted": [str(f) for f in flags][:8],
        "difficulty_level": str(data.get("difficulty_level") or difficulty).strip().lower(),
        "source": "llm",
    }


def _generate_with_llm(
    profile: dict[str, Any], scam_type: str, difficulty: str
) -> dict[str, Any] | None:
    try:
        from app.clients import llm
    except Exception as exc:  # pragma: no cover - import guard
        logger.warning("LLM import failed: %s", exc)
        return None

    user_prompt = USER_PROMPT.format(
        scam_type=scam_type,
        name=profile.get("name", "Customer"),
        city=profile.get("city", "Mumbai"),
        bank_full_name=profile.get("bank_full_name", "State Bank of India"),
        employer=profile.get("employer") or "not specified",
        relative=(
            f"{profile.get('relative_name')} ({profile.get('relative_relation')})"
            if profile.get("relative_name")
            else "not specified"
        ),
        difficulty=difficulty,
    )
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    for attempt in range(2):  # one retry, per plan edge-case table
        try:
            raw = llm.chat_completion(
                messages,
                json_mode=True,
                temperature=0.7,
                timeout=25.0,
            )
        except Exception as exc:
            logger.warning("Script LLM call failed (attempt %s): %s", attempt + 1, exc)
            return None
        data = _extract_json(raw)
        if data is None:
            if attempt == 0:
                messages.append({"role": "assistant", "content": raw[:2000]})
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            "That was not valid JSON. Reply ONLY with the JSON "
                            "object, no markdown."
                        ),
                    }
                )
            continue
        normalized = _normalize(data, profile, scam_type, difficulty)
        if normalized is not None:
            return normalized
        if attempt == 0:
            messages.append(
                {
                    "role": "user",                        "content": (
                            "The script was too short or missing stages. "
                            "Regenerate with ALL 5 stages and at least 150 "
                            "words total. Reply ONLY with JSON."
                        ),
                }
            )
    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_script(
    profile: dict[str, Any],
    scam_type: str,
    difficulty: str = "medium",
) -> dict[str, Any]:
    """Generate a personalized 5-stage scam script.

    Always returns a usable script dict (LLM first, template fallback), with a
    `script_id` assigned by the caller-friendly convention here.
    """
    scam_type = (scam_type or "").strip().lower()
    if scam_type not in VALID_SCAM_TYPES:
        scam_type = "bank_kyc"
    difficulty = (difficulty or "medium").strip().lower()
    if difficulty not in VALID_DIFFICULTIES:
        difficulty = "medium"

    result = _generate_with_llm(profile, scam_type, difficulty)
    if result is None:
        logger.info("Falling back to template script for %s", scam_type)
        result = render_fallback(scam_type, profile)
        result["source"] = "template"
    result.setdefault("difficulty_level", difficulty)

    result["full_script"] = _truncate_words(result["full_script"])
    result["estimated_duration_seconds"] = estimate_duration_seconds(
        result["full_script"]
    )
    result["script_id"] = new_id()
    result["language"] = profile.get("language", "en")
    return result


def list_supported_scam_types() -> list[str]:
    return sorted(VALID_SCAM_TYPES)
