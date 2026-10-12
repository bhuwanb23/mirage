"""Demo seed (plan §7.3) — makes the app look lived-in for the pitch.

Seeds, idempotently:
  * Drill profile: Priya Sharma (Mumbai, SBI, TCS)
  * 3 drill results -> resilience trend 25 -> 42 -> 67
  * 12 analyze events (the §7.3 report table, back-dated over 3 days)
  * Family group "Sharma Family" with 3 Memory Handshake questions + TOTP

The scam graph has its own seeder (graph_seed.seed_full) because it persists
to SQLite/Neo4j; this module only fills the in-process stores, so it runs at
startup (main.py lifespan) and via scripts/seed_data.py --in-process.

Everything keys off DEMO_USER_ID — a stable UUID the frontend mirrors via
NEXT_PUBLIC_DEMO_USER_ID, so the demo browser sees Priya's history.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

logger = logging.getLogger("mirage.demo_seed")

# Stable demo identity — must match NEXT_PUBLIC_DEMO_USER_ID in .env.
DEMO_USER_ID = "7f3a9c1e-5d2b-4f8a-9e6c-1b8d4a7f2c9e"

DEMO_PROFILE: dict[str, Any] = {
    "name": "Priya Sharma",
    "city": "Mumbai",
    "bank": "SBI",
    "employer": "TCS",
    "relative_name": "Aarav Sharma",
    "relative_relation": "brother",
    "language": "en",
}

# (scam_type, difficulty, reaction_time, score_before, score_after, days_ago)
DEMO_DRILLS = [
    ("lottery", "easy", 12.5, 0, 25, 2),
    ("bank_kyc", "medium", 22.1, 25, 42, 1),
    ("bank_kyc", "hard", 18.3, 42, 67, 0),
]

# (scam_type, source/input_type, confidence, city, days_ago)
DEMO_REPORTS = [
    ("bank_kyc", "telegram", 0.92, "Delhi", 0),
    ("upi_reversal", "web", 0.85, "Mumbai", 0),
    ("fedex", "telegram", 0.88, "Delhi", 0),
    ("job_offer", "web", 0.78, "Bangalore", 1),
    ("lottery", "telegram", 0.95, "Chennai", 1),
    ("impersonation", "guardian", 0.97, "Delhi", 1),
    ("investment", "telegram", 0.82, "Hyderabad", 2),
    ("electricity", "web", 0.75, "Pune", 2),
    ("qr_code", "telegram", 0.90, "Mumbai", 2),
    ("relative_distress", "guardian", 0.88, "Kolkata", 3),
    ("bank_kyc", "telegram", 0.91, "Delhi", 3),
    ("romance", "web", 0.65, "Jaipur", 3),
]

DEMO_FAMILY_NAME = "Sharma Family"

DEMO_QUESTIONS = [
    {"question": "What did we name our dog in 2019?", "answer": "Moti"},
    {"question": "Which city did we visit for New Year 2022?", "answer": "Goa"},
    {"question": "What is the name of my first school?", "answer": "St. Mary's"},
]


def _iso_days_ago(days: int, hour: int = 10) -> str:
    moment = datetime.now(timezone.utc) - timedelta(days=days)
    return moment.replace(hour=hour, minute=0, second=0, microsecond=0).isoformat()


def _seed_profile_and_drills() -> bool:
    """Priya's profile + 3-drill history (25 -> 42 -> 67). Returns True if seeded."""
    from app.services.drill_store import (
        get_history,
        record_result,
        save_profile,
        set_score,
    )
    from app.services.footprint_scraper import build_profile

    if get_history(DEMO_USER_ID):
        return False  # already seeded (idempotent)

    profile = build_profile(user_id=DEMO_USER_ID, **DEMO_PROFILE)
    profile["created_at"] = _iso_days_ago(2)
    save_profile(profile)

    for i, (scam_type, difficulty, rt, before, after, days) in enumerate(DEMO_DRILLS, start=1):
        record_result(
            DEMO_USER_ID,
            {
                "drill_id": f"drill-demo-{i}",
                "script_id": f"script-demo-{i}",
                "scam_type": scam_type,
                "difficulty": difficulty,
                "user_action": "identified_scam",
                "reaction_time_seconds": rt,
                "audio_position_seconds": rt,
                "stages_caught": ["hook", "authority"],
                "stages_missed": ["isolation", "urgency", "payment"],
                "trigger_stage": "authority",
                "drill_score": max(0, after - before),
                "score_before": before,
                "score_after": after,
                "score_change": after - before,
                "script_text": "",
                "debrief_text": (
                    f"Caught the scam at the authority stage after {rt}s. "
                    "Review the isolation tactic you missed."
                ),
                "created_at": _iso_days_ago(days),
            },
        )
    set_score(DEMO_USER_ID, DEMO_DRILLS[-1][4])
    return True


def _seed_reports() -> bool:
    """12 back-dated analyze events for the dashboard activity feed."""
    from app.services import recent_activity

    existing = recent_activity.list_recent(limit=50)
    if any(e.get("summary", "").startswith("[demo]") for e in existing):
        return False

    # Oldest first so the deque's newest-first order matches the table.
    for scam_type, source, confidence, city, days in reversed(DEMO_REPORTS):
        recent_activity.record_analyze(
            is_scam=True,
            scam_type=scam_type,
            confidence=confidence,
            input_type=source,
            summary=f"[demo] {scam_type.replace('_', ' ').title()} report — {city}",
            created_at=_iso_days_ago(days),
        )
    return True


def _seed_family() -> bool:
    """'Sharma Family' group with handshake questions + TOTP (ready state)."""
    from app.services import memory_handshake as mem

    store = mem.get_store()
    if store.find_group_for_user(DEMO_USER_ID):
        return False

    group = store.create_group(name=DEMO_FAMILY_NAME, created_by=DEMO_USER_ID)
    group_id = str(group["id"])
    # Two more members so member_count looks like a real family.
    store.link_user(group_id, "demo-family-member-1")
    store.link_user(group_id, "demo-family-member-2")
    mem.setup_questions(group_id, DEMO_QUESTIONS)  # also generates the TOTP secret
    logger.info("Seeded demo family group %s (handshake ready)", group_id)
    return True


def seed_demo() -> dict[str, bool]:
    """Seed every in-process demo store. Idempotent; returns what was seeded."""
    results = {
        "profile_and_drills": _seed_profile_and_drills(),
        "reports": _seed_reports(),
        "family": _seed_family(),
    }
    if any(results.values()):
        logger.info("Demo seed complete: %s", results)
    return results


def is_seeded() -> bool:
    from app.services.drill_store import get_history

    return bool(get_history(DEMO_USER_ID))
