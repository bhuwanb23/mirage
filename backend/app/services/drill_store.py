"""In-memory drill store (Phase 3) with optional Supabase persistence.

Development-safe: everything works without a database. When Supabase is
configured, drill results and user scores are also written there (best-effort,
failures are logged, never raised).
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

logger = logging.getLogger("mirage.drill_store")

_lock = threading.Lock()

# profile_id -> profile dict
_profiles: dict[str, dict[str, Any]] = {}
# script_id -> script dict
_scripts: dict[str, dict[str, Any]] = {}
# user_id -> list of result dicts (drill history, oldest first)
_results: dict[str, list[dict[str, Any]]] = {}
# user_id -> current resilience score
_scores: dict[str, int] = {}


def new_id() -> str:
    return uuid4().hex


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Profiles
# ---------------------------------------------------------------------------

def save_profile(profile: dict[str, Any]) -> dict[str, Any]:
    with _lock:
        _profiles[profile["profile_id"]] = profile
    return profile


def get_profile(profile_id: str) -> Optional[dict[str, Any]]:
    with _lock:
        return _profiles.get(profile_id)


def update_profile(profile_id: str, **fields: Any) -> Optional[dict[str, Any]]:
    with _lock:
        profile = _profiles.get(profile_id)
        if profile is None:
            return None
        profile.update(fields)
        return profile


# ---------------------------------------------------------------------------
# Scripts
# ---------------------------------------------------------------------------

def save_script(script: dict[str, Any]) -> dict[str, Any]:
    with _lock:
        _scripts[script["script_id"]] = script
    return script


def get_script(script_id: str) -> Optional[dict[str, Any]]:
    with _lock:
        return _scripts.get(script_id)


def update_script(script_id: str, **fields: Any) -> Optional[dict[str, Any]]:
    with _lock:
        script = _scripts.get(script_id)
        if script is None:
            return None
        script.update(fields)
        return script


# ---------------------------------------------------------------------------
# Results + scores
# ---------------------------------------------------------------------------

def record_result(user_id: str, result: dict[str, Any]) -> None:
    """Append a drill result to the user's history and persist to Supabase."""
    with _lock:
        _results.setdefault(user_id, []).append(result)
    _persist_result(user_id, result)


def get_history(user_id: str) -> list[dict[str, Any]]:
    with _lock:
        return list(_results.get(user_id, []))


def get_score(user_id: str) -> int:
    with _lock:
        return _scores.get(user_id, 0)


def set_score(user_id: str, score: int) -> None:
    with _lock:
        _scores[user_id] = score
    _persist_score(user_id, score)


def reset() -> None:
    """Clear all in-memory state (tests use this)."""
    with _lock:
        _profiles.clear()
        _scripts.clear()
        _results.clear()
        _scores.clear()


# ---------------------------------------------------------------------------
# Supabase persistence (best-effort)
# ---------------------------------------------------------------------------

def _persist_result(user_id: str, result: dict[str, Any]) -> None:
    try:
        from app.clients.supabase_client import get_supabase

        client = get_supabase()
        if client is None:
            return
        client.table("drills").insert(
            {
                "user_id": _resolve_user_uuid(user_id),
                "scam_type": result.get("scam_type", "unknown"),
                "script_text": result.get("script_text", ""),
                "audio_url": result.get("audio_url"),
                "user_detected_scam": bool(result.get("user_detected_scam")),
                "detection_time_seconds": int(result.get("reaction_time_seconds", 0)),
                "stages_identified": result.get("stages_caught", []),
                "stages_missed": result.get("stages_missed", []),
                "score_before": result.get("score_before", 0),
                "score_after": result.get("score_after", 0),
                "debrief": result.get("debrief_text", ""),
            }
        ).execute()
    except Exception as exc:  # pragma: no cover - defensive, dev-safe
        logger.warning("Supabase drill persist failed: %s", exc)


def _persist_score(user_id: str, score: int) -> None:
    try:
        from app.clients.supabase_client import get_supabase

        client = get_supabase()
        if client is None:
            return
        client.table("users").upsert(
            {"id": _resolve_user_uuid(user_id), "score_after": score},
            on_conflict="id",
        ).execute()
    except Exception as exc:  # pragma: no cover - defensive, dev-safe
        logger.warning("Supabase score persist failed: %s", exc)


def _resolve_user_uuid(user_id: str) -> Optional[str]:
    """Supabase users.id is uuid; map opaque client ids to a stable uuid.

    Client-generated ids are already uuid hex — pass through. Anything else
    (e.g. 'anonymous') returns None so the FK stays satisfied-by-null.
    """
    try:
        from uuid import UUID

        UUID(user_id)
        return user_id
    except (ValueError, TypeError, AttributeError):
        return None
