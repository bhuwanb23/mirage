"""Family hub endpoints (Phase 6 dashboard)."""

from __future__ import annotations

from fastapi import APIRouter

from app.services import memory_handshake as service

router = APIRouter(tags=["family"])


@router.get("/status/{user_id}")
def family_status(user_id: str, family_group_id: str | None = None) -> dict:
    """Group link, handshake readiness, and recent alerts for a user."""
    return service.family_status(user_id, family_group_id=family_group_id)
