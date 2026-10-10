"""Scam resilience score (Phase 3.6) — per-drill scoring + weighted history.

Per plan:
  drill_score  = detection + speed + stages*5 + difficulty + penalties (0..80)
  cumulative   = weighted moving average (0.4 / 0.3 / 0.2 / 0.1 older avg),
                 first drill = raw drill score,
                 diminishing gain (-50%) after 3 drills of the same scam type,
                 inactivity decay (-2/week, hard cap 40 after 30 days),
                 clamped 0..100.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

STAGES = ["hook", "authority", "isolation", "urgency", "payment"]

LABELS = [
    (0, 20, "Beginner"),
    (21, 40, "Vulnerable"),
    (41, 60, "Cautious"),
    (61, 80, "Resilient"),
    (81, 100, "Scam-Proof"),
]

DIFFICULTY_BONUS = {"easy": 0, "medium": 2, "hard": 5}

MAX_DRILL_SCORE = 80
SAME_TYPE_DIMINISH_AFTER = 3  # gain halved from the 3rd same-type drill on


def label_for(score: int) -> str:
    score = max(0, min(100, int(score)))
    for low, high, name in LABELS:
        if low <= score <= high:
            return name
    return "Beginner"  # pragma: no cover


def speed_bonus(reaction_time: float) -> int:
    rt = max(float(reaction_time), 0.0)
    if rt < 5:
        return 20
    if rt < 10:
        return 18
    if rt < 15:
        return 15
    if rt < 20:
        return 12
    if rt < 30:
        return 8
    if rt < 45:
        return 5
    if rt < 60:
        return 2
    return 0


def calculate_drill_score(
    user_action: str,
    reaction_time: float,
    stages_heard: int,
    difficulty: str = "medium",
) -> int:
    """Score a single drill, clamped to 0..80 (plan 3.6 table)."""
    if user_action == "identified_scam":
        points = 30 + speed_bonus(reaction_time)
        points += 5 * max(0, min(int(stages_heard), 5))
        points += DIFFICULTY_BONUS.get(difficulty, 2)
        if reaction_time < 2:
            points -= 5  # too fast — likely a guess
    elif user_action == "fell_for_it":
        points = -10
    else:  # no_response
        points = -5
    return max(0, min(points, MAX_DRILL_SCORE))


def _parse_date(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str) and value:
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    return None


def _inactivity_decay(score: int, last_drill_at: Optional[datetime]) -> int:
    if last_drill_at is None:
        return score
    now = datetime.now(timezone.utc)
    days = max((now - last_drill_at).days, 0)
    if days >= 30:
        return min(score, 40)  # "immunity is fading" cap
    if days >= 7:
        return max(0, score - 2 * (days // 7))
    return score


def _weighted_average(scores: list[int]) -> float:
    """0.4 latest + 0.3 prev + 0.2 prev-prev + 0.1 older average."""
    if not scores:
        return 0.0
    if len(scores) == 1:
        return float(scores[0])
    if len(scores) == 2:
        return scores[1] * 0.6 + scores[0] * 0.4
    recent = (
        scores[-1] * 0.4
        + scores[-2] * 0.3
        + scores[-3] * 0.2
    )
    older = scores[:-3]
    if older:
        older_avg = sum(older) / len(older)
    else:
        older_avg = (scores[-1] * 0.4 + scores[-2] * 0.3 + scores[-3] * 0.2) / 0.9
    # when there is no older history, the 0.1 slice re-weights onto the recent 3
    if not older:
        return (scores[-1] * 0.4 + scores[-2] * 0.3 + scores[-3] * 0.2) / 0.9
    return recent + older_avg * 0.1


def same_type_count(history: list[dict[str, Any]], scam_type: str) -> int:
    return sum(1 for r in history if r.get("scam_type") == scam_type)


def _cumulative_score(entry: dict[str, Any]) -> int:
    """Cumulative score stored on a history row (schema varies by writer)."""
    for key in ("resilience_score", "score_after", "score"):
        if entry.get(key) is not None:
            return int(entry[key])
    return 0


def update_resilience(
    history: list[dict[str, Any]],
    new_drill: dict[str, Any],
) -> dict[str, Any]:
    """Apply `new_drill` to the history; returns the full score payload.

    `history` items: {drill_score, scam_type, reaction_time_seconds, date}
    `new_drill` adds: difficulty, user_action, stages_caught, audio_url, ...
    Mutates nothing — returns a new cumulative score + stats.
    """
    drill_score = calculate_drill_score(
        user_action=new_drill.get("user_action", "no_response"),
        reaction_time=float(new_drill.get("reaction_time_seconds") or 0.0),
        stages_heard=len(new_drill.get("stages_caught") or []),
        difficulty=new_drill.get("difficulty", "medium"),
    )
    previous = int(_cumulative_score(history[-1])) if history else 0
    prior_scores = [_cumulative_score(r) for r in history]
    prior_drill_scores = [int(r.get("drill_score", 0)) for r in history]

    raw = _weighted_average(prior_drill_scores + [drill_score])
    score_after = int(round(raw))

    # diminishing returns for grinding the same scam type
    if same_type_count(history, new_drill.get("scam_type", "")) + 1 >= SAME_TYPE_DIMINISH_AFTER:
        score_after = previous + round((score_after - previous) * 0.5)

    # inactivity decay relative to the last drill
    last_dt = None
    for r in reversed(history):
        last_dt = _parse_date(r.get("date") or r.get("created_at"))
        if last_dt:
            break
    if last_dt is not None:
        score_after = _inactivity_decay(score_after, last_dt)

    score_after = max(0, min(100, score_after))

    # history entry for this drill (cumulative score AFTER the drill)
    entry = {
        "drill_number": len(history) + 1,
        "score": score_after,
        "scam_type": new_drill.get("scam_type", "unknown"),
        "date": (new_drill.get("date") or datetime.now(timezone.utc).isoformat())[:10],
        "drill_score": drill_score,
        "resilience_score": score_after,
        "reaction_time_seconds": float(new_drill.get("reaction_time_seconds") or 0.0),
        "user_action": new_drill.get("user_action", "no_response"),
        "difficulty": new_drill.get("difficulty", "medium"),
    }

    history_entries = [
        {
            "drill_number": i + 1,
            "score": _cumulative_score(r),
            "scam_type": r.get("scam_type", "unknown"),
            "date": str(r.get("date") or r.get("created_at") or "")[:10],
        }
        for i, r in enumerate(history)
    ]

    reactions = [
        float(r.get("reaction_time_seconds"))
        for r in history
        if r.get("user_action") == "identified_scam"
        and r.get("reaction_time_seconds") is not None
    ]
    if new_drill.get("user_action") == "identified_scam":
        reactions.append(float(new_drill.get("reaction_time_seconds") or 0.0))

    weakest = _weakest_scam_type(history + [entry])

    return {
        "drill_score": drill_score,
        "score_before": previous,
        "score_after": score_after,
        "change": score_after - previous,
        "label": label_for(score_after),
        "entry": entry,
        "history_entries": history_entries,
        "drills_completed": len(history) + 1,
        "best_reaction_time": min(reactions) if reactions else None,
        "weakest_scam_type": weakest,
        "prior_scores": prior_scores,
    }


def _weakest_scam_type(history: list[dict[str, Any]]) -> Optional[str]:
    """Scam type with the lowest average per-drill score (min 1 drill)."""
    buckets: dict[str, list[int]] = {}
    for r in history:
        buckets.setdefault(r.get("scam_type", "unknown"), []).append(
            int(r.get("drill_score", 0))
        )
    if not buckets:
        return None
    averages = {k: sum(v) / len(v) for k, v in buckets.items()}
    return min(averages, key=averages.get)  # type: ignore[arg-type]
