"""Debrief engine (Phase 3.5) — LLM debrief with a deterministic fallback.

Turns a finished drill (which stages the user heard before clicking, the stage
that triggered the click, reaction time) into a warm, specific, educational
debrief. The LLM path is validated field-by-field; anything missing is filled
from the deterministic engine so the response schema is always complete.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from app.models.schemas import STAGE_ORDER

logger = logging.getLogger("mirage.debrief")

STAGE_LABELS = {
    "hook": "Hook",
    "authority": "Authority",
    "isolation": "Isolation",
    "urgency": "Urgency",
    "payment": "Payment",
}

# deterministic per-stage teaching content (fallback debriefs)
STAGE_KNOWLEDGE: dict[str, dict[str, str]] = {
    "hook": {
        "what_happened": (
            "The caller opened with your name and a familiar brand to feel "
            "like someone you already know."
        ),
        "why_it_works": (
            "Hearing your name from a stranger triggers a compliance reflex "
            "— you assume they must know you."
        ),
        "real_world_tip": (
            "Real institutions verify YOUR identity first; they don't just "
            "announce your name back to you."
        ),
    },
    "authority": {
        "what_happened": (
            "The caller impersonated an official — a bank officer, customs "
            "desk, or police — with fake reference numbers."
        ),
        "why_it_works": (
            "We are trained to obey authority, and specific-sounding details "
            "(case numbers, departments) feel verifiable even when invented."
        ),
        "real_world_tip": (
            "Hang up and call the institution on the number printed on your "
            "card or statement — never a number the caller gives you."
        ),
    },
    "isolation": {
        "what_happened": (
            "The caller told you to keep the call secret from family, bank "
            "staff, or anyone else."
        ),
        "why_it_works": (
            "Isolation removes your second opinion. Anyone else in the room "
            "would spot the scam in seconds."
        ),
        "real_world_tip": (
            "If anyone asks you to hide a financial call from your family, "
            "that alone is the #1 scam indicator. Hang up immediately."
        ),
    },
    "urgency": {
        "what_happened": (
            "The caller created a countdown — account frozen, parcel seized, "
            "someone in jail — all within minutes."
        ),
        "why_it_works": (
            "Deadlines switch your brain from thinking mode to panic mode. "
            "Panic is the scammer's best tool."
        ),
        "real_world_tip": (
            "Real banks and police never demand immediate action on a call. "
            "Say 'I'll call you back' — a real organization will wait."
        ),
    },
    "payment": {
        "what_happened": (
            "The caller demanded money, an OTP, a PIN, or a UPI transfer to "
            "'verify' something."
        ),
        "why_it_works": (
            "Once money or secrets move, the loss is instant and usually "
            "unrecoverable — that is the kill shot of the script."
        ),
        "real_world_tip": (
            "No real bank, courier, or government office ever asks for an "
            "OTP, PIN, or an up-front UPI payment. Hang up and call 1930 if "
            "you already paid."
        ),
    },
}

FAKE_PERCENTAGE = 72  # normalization stat used in 'failed' debriefs

SYSTEM_PROMPT = """You are the Mirage Debrief Engine. Your job is to provide a warm,
educational, and specific debrief after a user completes a scam fire drill.

RULES:
1. Be encouraging, not condescending. If the user fell for it, normalize it:
   "70% of people fall for this type of scam."
2. Be SPECIFIC. Reference exact moments in the script by timestamp. Don't
   give generic advice.
3. Explain the PSYCHOLOGY behind each tactic. Why does it work? What emotion
   does it exploit?
4. Give ACTIONABLE real-world advice. What should they do if they encounter
   this in real life?
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
      "what_happened": "The caller used your full name 'Priya Sharma'.",
      "why_it_works": "Hearing your name from a stranger triggers compliance.",
      "real_world_tip": "Real callers verify YOUR identity first."
    }
  ],
  "stages_missed": [
    {
      "stage": "isolation",
      "timestamp": "0:20-0:30",
      "what_happened": "The caller said 'don't tell your family.'",
      "why_it_works": "Isolation prevents you from getting a second opinion.",
      "real_world_tip": "Keep-a-secret financial calls are always a scam."
    }
  ],
  "key_lesson": "The single most important takeaway from this drill",
  "real_world_action": "What to do if this happens for real",
  "encouragement": "A positive closing note"
}
"""

USER_PROMPT = """DRILL RESULTS:
- Scam Type: {scam_type}
- User Action: {user_action}
- Reaction Time: {reaction_time}s
- Stages Heard Before Click: {stages_before}
- Stage at Click: {stage_at_click}
- Stages Not Heard: {stages_after}

SCRIPT DETAILS:
{script_details}

USER PROFILE (for personalization):
- Name: {name}
- Bank: {bank}
- City: {city}

Generate the debrief.
"""


# ---------------------------------------------------------------------------
# Stage classification (shared with scoring)
# ---------------------------------------------------------------------------

def classify_stages(
    stage_timings: dict[str, dict[str, float]],
    user_action: str,
    audio_position_seconds: float,
) -> tuple[list[str], list[str], str | None]:
    """Return (stages_caught, stages_missed, trigger_stage).

    Heard-and-recognized = stages that ENDED at or before the click position;
    the trigger is the stage containing the click; stages starting after the
    click are 'missed'. 'fell_for_it' / 'no_response' catch nothing.
    """
    if user_action != "identified_scam":
        return [], list(STAGE_ORDER), None

    pos = max(audio_position_seconds, 0.0)
    caught: list[str] = []
    missed: list[str] = []
    trigger: str | None = None
    for stage in STAGE_ORDER:
        timing = stage_timings.get(stage) or {}
        start = float(timing.get("start", 0.0))
        end = float(timing.get("end", 0.0))
        if pos >= end:
            caught.append(stage)
        elif pos >= start and trigger is None:
            trigger = stage
        else:
            missed.append(stage)
    if trigger is None and caught:
        trigger = caught[-1]
    return caught, missed, trigger


def _fmt_ts(seconds: float) -> str:
    seconds = max(int(round(seconds)), 0)
    return f"{seconds // 60}:{seconds % 60:02d}"


def _ts_range(timing: dict[str, float]) -> str:
    return f"{_fmt_ts(timing.get('start', 0.0))}-{_fmt_ts(timing.get('end', 0.0))}"


# ---------------------------------------------------------------------------
# Deterministic fallback debrief
# ---------------------------------------------------------------------------

def _stage_detail(stage: str, timing: dict[str, float]) -> dict[str, str]:
    knowledge = STAGE_KNOWLEDGE[stage]
    return {
        "stage": stage,
        "timestamp": _ts_range(timing or {}),
        "what_happened": knowledge["what_happened"],
        "why_it_works": knowledge["why_it_works"],
        "real_world_tip": knowledge["real_world_tip"],
    }


def _reaction_assessment(user_action: str, reaction_time: float) -> str:
    if user_action != "identified_scam":
        return (
            "You let the call play out and believed it. Totally normal on a first "
            f"try — about {FAKE_PERCENTAGE}% of people do. The breakdown below shows "
            "exactly where the trap was set."
        )
    if reaction_time < 3:
        return (
            f"You flagged it in {reaction_time:.1f}s — impressively fast. In a real "
            "call, scammers often start subtler, so make sure you can name the "
            "specific red flag, not just a gut feeling."
        )
    if reaction_time <= 20:
        return (
            f"{reaction_time:.1f}s — solid. You listened just enough to spot the "
            "tactic before the money ask."
        )
    if reaction_time <= 45:
        return (
            f"{reaction_time:.1f}s — you caught it, but the payment demand was close. "
            "Try to react sooner next drill."
        )
    return (
        f"{reaction_time:.1f}s — you caught it just before the kill shot. "
        "The earlier warning signs are cheaper to act on."
    )


def _outcome(user_action: str, caught: list[str]) -> str:
    if user_action != "identified_scam":
        return "failed"
    if len(caught) >= 4:
        return "success"
    if len(caught) >= 1:
        return "partial"
    return "partial"


def build_fallback_debrief(
    script: dict[str, Any],
    stage_timings: dict[str, dict[str, float]],
    user_action: str,
    reaction_time: float,
    caught: list[str],
    missed: list[str],
    attempt_number: int = 1,
) -> dict[str, Any]:
    """Deterministic debrief — always complete, never depends on an LLM."""
    outcome = _outcome(user_action, caught)

    if outcome == "success":
        headline = f"Caught it in {reaction_time:.1f}s — sharp work!"
    elif user_action == "identified_scam":
        headline = "You caught it — with room to react faster."
    elif user_action == "fell_for_it":
        headline = "This was a scam — and it's completely okay."
    else:
        headline = "You didn't react in time — let's break it down."

    if user_action == "fell_for_it":
        headline = f"This was a scam — and it's okay! {FAKE_PERCENTAGE}% miss it the first time."

    key_lesson = (
        "Urgency plus a request for secrets (OTP, PIN, password) or money is "
        "always a scam. Hang up and call your bank on the number on your card."
    )
    if "isolation" in missed:
        key_lesson = (
            "Anyone who asks you to keep a financial call secret from your family "
            "is running a scam. Isolation is the loudest red flag there is."
        )

    return {
        "outcome": outcome,
        "headline": headline,
        "reaction_assessment": _reaction_assessment(user_action, reaction_time),
        "stages_caught": [_stage_detail(s, stage_timings.get(s, {})) for s in caught],
        "stages_missed": [_stage_detail(s, stage_timings.get(s, {})) for s in missed],
        "key_lesson": key_lesson,
        "real_world_action": (
            "Hang up. Do not share anything. Call the institution on its official "
            "number or dial 1930 (cyber crime helpline) if money already moved."
        ),
        "encouragement": (
            "Every drill rewires your instinct. Train again tomorrow — variety "
            "beats repetition."
            if attempt_number < 3
            else (
                "You've built real reflexes now. Keep mixing up the scam types "
                "so you don't pattern-match one script."
            )
        ),
    }


# ---------------------------------------------------------------------------
# LLM path (validated, merged over the deterministic base)
# ---------------------------------------------------------------------------

def _extract_json(raw: str) -> dict[str, Any] | None:
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


def _valid_details(value: Any, stage: str, timing: dict[str, float]) -> dict[str, str]:
    fallback = _stage_detail(stage, timing)
    if not isinstance(value, dict):
        return fallback
    return {
        "stage": stage,
        "timestamp": str(value.get("timestamp") or fallback["timestamp"]),
        "what_happened": str(value.get("what_happened") or fallback["what_happened"]),
        "why_it_works": str(value.get("why_it_works") or fallback["why_it_works"]),
        "real_world_tip": str(value.get("real_world_tip") or fallback["real_world_tip"]),
    }


def generate_debrief(
    script: dict[str, Any],
    stage_timings: dict[str, dict[str, float]],
    user_action: str,
    reaction_time: float,
    caught: list[str],
    missed: list[str],
    trigger_stage: str | None,
    profile: dict[str, Any] | None = None,
    attempt_number: int = 1,
) -> dict[str, Any]:
    """Generate the debrief. LLM first (temp 0.5, JSON), always schema-complete."""
    base = build_fallback_debrief(
        script, stage_timings, user_action, reaction_time, caught, missed, attempt_number
    )

    try:
        from app.clients import llm
    except Exception:
        return base

    script_details = "\n".join(
        f"[{s.upper()} {_ts_range(stage_timings.get(s, {}))}] "
        f"{(script.get('stages', {}).get(s) or {}).get('script', '')}\n"
        f"TACTIC: {(script.get('stages', {}).get(s) or {}).get('tactic', '')}"
        for s in STAGE_ORDER
    )
    prompt = USER_PROMPT.format(
        scam_type=script.get("scam_type", "unknown"),
        user_action=user_action,
        reaction_time=round(reaction_time, 1),
        stages_before=", ".join(caught) or "none",
        stage_at_click=trigger_stage or "none",
        stages_after=", ".join(missed) or "none",
        script_details=script_details,
        name=(profile or {}).get("name", "the user"),
        bank=(profile or {}).get("bank_full_name", "their bank"),
        city=(profile or {}).get("city", "their city"),
    )
    try:
        raw = llm.chat_completion(
            [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            json_mode=True,
            temperature=0.5,
            timeout=25.0,
        )
    except Exception as exc:
        logger.warning("Debrief LLM unavailable, using deterministic debrief: %s", exc)
        return base

    data = _extract_json(raw)
    if data is None:
        logger.warning("Debrief LLM returned non-JSON; using deterministic debrief")
        return base

    # merge: LLM text where present, our structure/stage lists as the source of truth
    merged = dict(base)
    if str(data.get("headline", "")).strip():
        merged["headline"] = str(data["headline"]).strip()
    if str(data.get("reaction_assessment", "")).strip():
        merged["reaction_assessment"] = str(data["reaction_assessment"]).strip()
    if str(data.get("key_lesson", "")).strip():
        merged["key_lesson"] = str(data["key_lesson"]).strip()
    if str(data.get("real_world_action", "")).strip():
        merged["real_world_action"] = str(data["real_world_action"]).strip()
    if str(data.get("encouragement", "")).strip():
        merged["encouragement"] = str(data["encouragement"]).strip()
    if str(data.get("outcome", "")).strip() in {"success", "partial", "failed"}:
        merged["outcome"] = str(data["outcome"]).strip()

    # enrich stage details with LLM specifics when the stage lists match
    llm_caught = data.get("stages_caught") if isinstance(data.get("stages_caught"), list) else []
    llm_missed = data.get("stages_missed") if isinstance(data.get("stages_missed"), list) else []
    if len(llm_caught) == len(caught):
        merged["stages_caught"] = [
            _stage_detail(stage, stage_timings.get(stage, {})) if not isinstance(item, dict)
            else _valid_details(item, stage, stage_timings.get(stage, {}))
            for stage, item in zip(caught, llm_caught)
        ]
    if len(llm_missed) == len(missed):
        merged["stages_missed"] = [
            _stage_detail(stage, stage_timings.get(stage, {})) if not isinstance(item, dict)
            else _valid_details(item, stage, stage_timings.get(stage, {}))
            for stage, item in zip(missed, llm_missed)
        ]
    return merged
