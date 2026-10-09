"""Family alert engine (Phase 2.7): in-memory state, throttle, formatting.

State is intentionally in-memory (hackathon scope):
  FAMILY_LINKS  user_id -> group chat_id          (registered via /family in a group)
  ELDER_MODE    user_id -> {"enabled", "language"} (toggled via /elder)
  ALERT_HISTORY user_id -> [ts, ...]              (for throttling)

Trigger rules:
  - verdict.is_scam AND confidence > 0.85  (> 0.60 when user is in Elder Mode)
  - user linked to a family group
  - throttle: max 3 alerts/hour/user; skip same scam type within 10 minutes

Privacy: the alert NEVER contains the original message text — only scam type,
confidence, risk level and a generic action checklist.
"""

from __future__ import annotations

import time
from datetime import datetime
from typing import Any, Optional

from utils.constants import BOT_USERNAME, RISK_EMOJI, SCAM_TYPE_READABLE

# ---------------------------------------------------------------------------
# State (module-level, in-memory)
# ---------------------------------------------------------------------------

FAMILY_LINKS: dict[int, int] = {}          # user_id -> group chat_id
ELDER_MODE: dict[int, dict] = {}           # user_id -> {"enabled", "language"}
ALERT_HISTORY: dict[int, list[float]] = {}  # user_id -> [timestamps]
ALERT_TYPES: dict[int, list[tuple[float, str]]] = {}  # user_id -> [(ts, scam_type)]

MAX_ALERTS_PER_HOUR = 3
SAME_TYPE_WINDOW_S = 600  # 10 minutes
HOUR_S = 3600


def reset_state() -> None:
    """Test helper — clear all in-memory state."""
    FAMILY_LINKS.clear()
    ELDER_MODE.clear()
    ALERT_HISTORY.clear()
    ALERT_TYPES.clear()


# ---------------------------------------------------------------------------
# Elder mode helpers
# ---------------------------------------------------------------------------

def elder_enabled(user_id: Optional[int]) -> bool:
    if user_id is None:
        return False
    return bool(ELDER_MODE.get(user_id, {}).get("enabled"))


def elder_language(user_id: Optional[int]) -> str:
    if user_id is None:
        return "en"
    return ELDER_MODE.get(user_id, {}).get("language", "hi")


# ---------------------------------------------------------------------------
# Family group registration
# ---------------------------------------------------------------------------

def link_family_group(user_id: int, chat_id: int) -> None:
    FAMILY_LINKS[user_id] = chat_id


def family_group_for(user_id: Optional[int]) -> Optional[int]:
    if user_id is None:
        return None
    return FAMILY_LINKS.get(user_id)


def register_group_member(user_id: int, chat_id: int) -> None:
    """A group /family also links every member who triggers future alerts.

    For the hackathon we link the sender of /family; other members link
    themselves by sending /family to the bot in private too.
    """
    FAMILY_LINKS[user_id] = chat_id


# ---------------------------------------------------------------------------
# Throttle
# ---------------------------------------------------------------------------

def _prune(user_id: int, now: Optional[float] = None) -> None:
    now = now if now is not None else time.time()
    cutoff = now - HOUR_S
    history = [t for t in ALERT_HISTORY.get(user_id, []) if t > cutoff]
    if history:
        ALERT_HISTORY[user_id] = history
    else:
        ALERT_HISTORY.pop(user_id, None)
    types = [
        (t, s)
        for t, s in ALERT_TYPES.get(user_id, [])
        if t > now - SAME_TYPE_WINDOW_S
    ]
    if types:
        ALERT_TYPES[user_id] = types
    else:
        ALERT_TYPES.pop(user_id, None)


def should_alert(
    user_id: int,
    verdict: dict[str, Any],
    now: Optional[float] = None,
) -> tuple[bool, str]:
    """Decide whether to send a family alert. Returns (ok, reason)."""
    if not isinstance(verdict, dict):
        return False, "no verdict"
    if not verdict.get("is_scam"):
        return False, "not a scam"

    now = now if now is not None else time.time()
    threshold = 0.60 if elder_enabled(user_id) else 0.85
    confidence = float(verdict.get("confidence") or 0.0)
    if confidence <= threshold:
        return False, f"confidence {confidence:.2f} <= {threshold}"

    group = family_group_for(user_id)
    if group is None:
        return False, "no family group linked"

    _prune(user_id, now)

    history = ALERT_HISTORY.get(user_id, [])
    if len(history) >= MAX_ALERTS_PER_HOUR:
        return False, f"throttled: {len(history)} alerts in the last hour"

    scam_type = str(verdict.get("scam_type") or "unknown")
    for ts, seen_type in ALERT_TYPES.get(user_id, []):
        if seen_type == scam_type and (now - ts) < SAME_TYPE_WINDOW_S:
            return False, f"same scam type within {SAME_TYPE_WINDOW_S // 60} min"

    return True, "ok"


def record_alert(user_id: int, scam_type: str, now: Optional[float] = None) -> None:
    now = now if now is not None else time.time()
    ALERT_HISTORY.setdefault(user_id, []).append(now)
    ALERT_TYPES.setdefault(user_id, []).append((now, scam_type))


# ---------------------------------------------------------------------------
# Alert message formatting (no private content!)
# ---------------------------------------------------------------------------

def format_alert(
    user_first_name: str,
    verdict: dict[str, Any],
    when: Optional[datetime] = None,
) -> str:
    when = when or datetime.now()
    scam_type = SCAM_TYPE_READABLE.get(
        str(verdict.get("scam_type") or ""), "Unknown Scam Type"
    )
    confidence = round(float(verdict.get("confidence") or 0.0) * 100)
    risk_level = str(verdict.get("risk_level") or "high").lower()
    risk_emoji = RISK_EMOJI.get(risk_level, "\U0001f534")
    name = user_first_name or "A family member"
    summary = str(verdict.get("summary") or "")[:200]

    return (
        "\U0001f6a8 <b>FAMILY SCAM ALERT</b> \U0001f6a8\n"
        "\n"
        f"<b>Who:</b> {name}\n"
        f"<b>When:</b> {when.strftime('%d %b %Y, %I:%M %p')}\n"
        f"<b>Threat:</b> {scam_type}\n"
        f"<b>Confidence:</b> {confidence}%\n"
        f"<b>Risk:</b> {risk_emoji} {risk_level.upper()}\n"
        "\n"
        f"<b>What happened:</b>\n{summary}\n"
        "\n"
        "<b>⚠️ Action needed:</b>\n"
        f"Please check on {name} and make sure they have NOT:\n"
        "❌ Clicked any links\n"
        "❌ Shared any OTP\n"
        "❌ Made any payment\n"
        "❌ Shared any personal details\n"
        "\n"
        "<b>📞 If money was sent:</b>\n"
        "Call 1930 immediately and report to cybercrime.gov.in\n"
        "\n"
        f"<i>Sent by Mirage Scam Shield. Set up your own: /start on @{BOT_USERNAME}</i>"
    )


def setup_prompt() -> str:
    """Prompt shown to a user who isn't linked to a family group yet."""
    return (
        "⚠️ This is a serious scam. Would you like me to alert your family?\n\n"
        "1️⃣ Create a Telegram group with your family\n"
        f"2️⃣ Add me to the group (@{BOT_USERNAME})\n"
        "3️⃣ Send /family in the group\n\n"
        "I'll alert them when a high-risk scam targets you."
    )


def group_linked_message() -> str:
    return (
        "✅ This group is now linked for scam alerts. When any family member "
        "receives a high-risk scam, I'll alert everyone here."
    )
