"""Memory router — Phase 4.5 Memory Handshake endpoints.

  POST   /memory/group                 create a family group (returns invite code)
  POST   /memory/group/join            join an existing group by invite code
  POST   /memory/setup                 save ≥3 challenge questions + TOTP secret
  GET    /memory/questions/{group_id}  active questions (never answers/hashes)
  GET    /memory/challenge/{group_id}  random question for an in-call challenge
  GET    /memory/totp/{group_id}       current rotating family code
  POST   /memory/verify                verify a typed answer (rate-limited)
  POST   /memory/verify-totp           verify a family code (±1 interval)

Storage: Supabase when configured, in-memory otherwise (service picks).

Run:  uv run uvicorn app.main:app --reload --port 8000
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.models.schemas import (
    ChallengeQuestion,
    FamilyGroupCreate,
    FamilyGroupJoin,
    FamilyGroupOut,
    MemorySetupRequest,
    MemorySetupResponse,
    MemoryVerifyRequest,
    MemoryVerifyResponse,
    TOTPResponse,
    TotpVerifyRequest,
)
from app.services import memory_handshake as service

router = APIRouter(tags=["memory"])


def _http_error(exc: service.MemoryError) -> HTTPException:
    if isinstance(exc, service.NotFoundError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, service.RateLimitedError):
        return HTTPException(
            status_code=429,
            detail=str(exc),
            headers={"Retry-After": str(exc.retry_after_seconds)},
        )
    return HTTPException(status_code=400, detail=str(exc))


@router.post("/group", response_model=FamilyGroupOut)
def create_group(body: FamilyGroupCreate | None = None) -> FamilyGroupOut:
    """Create a family group. The invite code is how members join."""
    payload = service.create_group(
        name=body.name if body else None,
        created_by=str(body.user_id) if body and body.user_id else None,
    )
    return FamilyGroupOut(**payload)


@router.post("/group/join", response_model=FamilyGroupOut)
def join_group(body: FamilyGroupJoin) -> FamilyGroupOut:
    try:
        payload = service.join_group(body.invite_code)
    except service.MemoryError as exc:
        raise _http_error(exc) from exc
    return FamilyGroupOut(**payload)


@router.post("/setup", response_model=MemorySetupResponse)
def setup(body: MemorySetupRequest) -> MemorySetupResponse:
    """Hash answers + create/keep the group's TOTP secret."""
    questions = [q.model_dump() for q in body.questions]
    try:
        result = service.setup_questions(body.family_group_id, questions)
    except service.MemoryError as exc:
        raise _http_error(exc) from exc
    return MemorySetupResponse(**result)


@router.get("/questions/{family_group_id}")
def questions(family_group_id: str) -> dict:
    """Active question texts + ids. Answer hashes are never exposed."""
    try:
        return {"questions": service.list_questions(family_group_id)}
    except service.MemoryError as exc:
        raise _http_error(exc) from exc


@router.get("/challenge/{family_group_id}", response_model=ChallengeQuestion)
def challenge(family_group_id: str) -> ChallengeQuestion:
    """Random active question — the one shown in the Guardian alert panel."""
    try:
        return ChallengeQuestion(**service.random_challenge(family_group_id))
    except service.MemoryError as exc:
        raise _http_error(exc) from exc


@router.get("/totp/{family_group_id}", response_model=TOTPResponse)
def totp(family_group_id: str) -> TOTPResponse:
    """Current 6-digit family code + seconds until rotation."""
    return TOTPResponse(**service.current_totp(family_group_id))


@router.post("/verify", response_model=MemoryVerifyResponse)
def verify(body: MemoryVerifyRequest) -> MemoryVerifyResponse:
    try:
        result = service.verify_answer(
            body.family_group_id, body.question_id, body.answer
        )
    except service.MemoryError as exc:
        raise _http_error(exc) from exc
    return MemoryVerifyResponse(**result)


@router.post("/verify-totp", response_model=MemoryVerifyResponse)
def verify_totp(body: TotpVerifyRequest) -> MemoryVerifyResponse:
    result = service.verify_totp(body.family_group_id, body.code)
    return MemoryVerifyResponse(**result)
