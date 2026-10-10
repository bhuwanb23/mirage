"""Memory Handshake service (Phase 4.5–4.6).

2FA for human identity: shared secrets a voice clone cannot answer.

  * Answers are SHA-256 hashed after aggressive normalization — plain
    text never touches storage. Optional server-side pepper via
    `MEMORY_HASH_PEPPER`.
  * TOTP (`pyotp`, 300 s interval) gives the family a rotating code a
    real relative can read from their app during a suspicious call.
  * Verification is rate-limited: 3 wrong answers → 5-minute lock per
    question (in-memory — resets with the process, documented tradeoff).
  * Storage: Supabase when configured (tables `family_groups` +
    `memory_secrets`, migration 003), in-memory fallback otherwise.

Run:  uv run pytest tests/test_memory_handshake.py -q
"""

from __future__ import annotations

import hashlib
import logging
import random
import re
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

import pyotp

from app.config import settings

logger = logging.getLogger("mirage.memory")

TOTP_INTERVAL = 300          # 5 minutes (plan §4.5 step 4)
MIN_QUESTIONS = 3            # plan: "minimum is 3"
MAX_QUESTIONS = 10
MAX_FAILS = 3                # plan: 3 wrong answers → lock
LOCK_SECONDS = 300           # plan: lock for 5 minutes


class MemoryError(Exception):
    """Domain error with an HTTP-mappable message."""


class NotFoundError(MemoryError):
    pass


class RateLimitedError(MemoryError):
    def __init__(self, retry_after_seconds: int) -> None:
        super().__init__(
            f"Too many wrong answers. Try again in {retry_after_seconds} seconds."
        )
        self.retry_after_seconds = retry_after_seconds


# ---------------------------------------------------------------------------
# Normalization + hashing
# ---------------------------------------------------------------------------
_PUNCT_RE = re.compile(r"[^\w\s]", flags=re.UNICODE)
_WS_RE = re.compile(r"\s+")


def normalize_answer(answer: str) -> str:
    """Lowercase, drop punctuation, collapse whitespace.

    " Bruno. " == "bruno" == "BRUNO" (plan §4.5 edge cases).
    """
    lowered = (answer or "").strip().lower()
    no_punct = _PUNCT_RE.sub("", lowered)
    return _WS_RE.sub(" ", no_punct).strip()


def hash_answer(answer: str) -> str:
    """SHA-256 of the normalized answer, peppered when configured."""
    normalized = normalize_answer(answer)
    payload = f"{settings.memory_hash_pepper}{normalized}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


# ---------------------------------------------------------------------------
# Rate limiter (in-memory, per process)
# ---------------------------------------------------------------------------
@dataclass
class _AttemptState:
    fails: int = 0
    locked_until: float = 0.0


_lock = threading.Lock()
_attempts: dict[str, _AttemptState] = {}


def _attempt_key(group_id: str, question_id: str) -> str:
    return f"{group_id}:{question_id}"


def lock_remaining_seconds(key: str) -> int:
    with _lock:
        state = _attempts.get(key)
        if not state or state.locked_until <= time.time():
            return 0
        return int(state.locked_until - time.time()) + 1


def _record_failure(key: str) -> None:
    with _lock:
        state = _attempts.setdefault(key, _AttemptState())
        state.fails += 1
        if state.fails >= MAX_FAILS:
            state.locked_until = time.time() + LOCK_SECONDS
            state.fails = 0
            logger.warning("memory question locked for %ss (%s)", LOCK_SECONDS, key)


def _reset_failures(key: str) -> None:
    with _lock:
        _attempts.pop(key, None)


def reset_rate_limits() -> None:
    """Test helper — clear all lock state."""
    with _lock:
        _attempts.clear()


# ---------------------------------------------------------------------------
# Storage layer
# ---------------------------------------------------------------------------
@dataclass
class Question:
    id: str
    question: str


class MemoryStore:
    """Storage interface. Supabase-backed or in-memory."""

    name = "base"

    def create_group(self, name: Optional[str] = None, created_by: Optional[str] = None) -> dict:
        raise NotImplementedError

    def find_group_by_invite(self, invite_code: str) -> Optional[dict]:
        raise NotImplementedError

    def save_questions(self, group_id: str, rows: list[dict]) -> None:
        """Deactivate existing questions, insert new rows.

        Each row: {"id", "question", "answer_hash"}.
        """
        raise NotImplementedError

    def list_questions(self, group_id: str) -> list[Question]:
        raise NotImplementedError

    def get_answer_hash(self, group_id: str, question_id: str) -> Optional[str]:
        raise NotImplementedError

    def get_totp_secret(self, group_id: str) -> Optional[str]:
        raise NotImplementedError

    def set_totp_secret(self, group_id: str, secret: str) -> None:
        raise NotImplementedError


class InMemoryStore(MemoryStore):
    """Dev / no-Supabase fallback. Lives as long as the process."""

    name = "memory"

    def __init__(self) -> None:
        self._groups: dict[str, dict] = {}
        self._by_invite: dict[str, str] = {}
        self._questions: dict[str, list[dict]] = {}  # group_id -> rows
        self._secrets: dict[str, str] = {}           # group_id -> totp secret

    def create_group(self, name: Optional[str] = None, created_by: Optional[str] = None) -> dict:
        group_id = str(uuid.uuid4())
        invite = _generate_invite_code()
        self._groups[group_id] = {
            "id": group_id,
            "name": name or "Family",
            "invite_code": invite,
            "created_by": created_by,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self._by_invite[invite] = group_id
        self._questions.setdefault(group_id, [])
        return dict(self._groups[group_id])

    def find_group_by_invite(self, invite_code: str) -> Optional[dict]:
        group_id = self._by_invite.get(invite_code.strip().upper())
        if group_id:
            return dict(self._groups[group_id])
        return None

    def save_questions(self, group_id: str, rows: list[dict]) -> None:
        if group_id not in self._groups:
            raise NotFoundError("family group not found")
        self._questions[group_id] = [dict(r, active=True) for r in rows]

    def list_questions(self, group_id: str) -> list[Question]:
        rows = self._questions.get(group_id, [])
        return [Question(id=r["id"], question=r["question"]) for r in rows if r.get("active", True)]

    def get_answer_hash(self, group_id: str, question_id: str) -> Optional[str]:
        for row in self._questions.get(group_id, []):
            if row["id"] == question_id and row.get("active", True):
                return row["answer_hash"]
        return None

    def get_totp_secret(self, group_id: str) -> Optional[str]:
        return self._secrets.get(group_id)

    def set_totp_secret(self, group_id: str, secret: str) -> None:
        self._secrets[group_id] = secret


class SupabaseStore(MemoryStore):
    """Postgres-backed store (migration 003 adds family_group_id + TOTP)."""

    name = "supabase"

    def __init__(self, client: Any) -> None:
        self._sb = client

    def create_group(self, name: Optional[str] = None, created_by: Optional[str] = None) -> dict:
        # NOTE: `family_groups` has no name column (001) — name is in-memory only.
        payload: dict[str, Any] = {}
        if created_by:
            payload["created_by"] = created_by
        resp = self._sb.table("family_groups").insert(payload).execute()
        rows = resp.data or []
        if not rows:
            raise MemoryError("failed to create family group")
        return rows[0]

    def find_group_by_invite(self, invite_code: str) -> Optional[dict]:
        resp = (
            self._sb.table("family_groups")
            .select("*")
            .eq("invite_code", invite_code.strip().upper())
            .limit(1)
            .execute()
        )
        rows = resp.data or []
        return rows[0] if rows else None

    def save_questions(self, group_id: str, rows: list[dict]) -> None:
        # Deactivate old (kept for audit — plan §4.5 edge case).
        self._sb.table("memory_secrets").update({"active": False}).eq(
            "family_group_id", group_id
        ).eq("active", True).execute()
        insert_rows = [
            {
                "family_group_id": group_id,
                "question": r["question"],
                "answer_hash": r["answer_hash"],
                "active": True,
            }
            for r in rows
        ]
        self._sb.table("memory_secrets").insert(insert_rows).execute()

    def list_questions(self, group_id: str) -> list[Question]:
        resp = (
            self._sb.table("memory_secrets")
            .select("id, question")
            .eq("family_group_id", group_id)
            .eq("active", True)
            .execute()
        )
        return [Question(id=str(r["id"]), question=r["question"]) for r in (resp.data or [])]

    def get_answer_hash(self, group_id: str, question_id: str) -> Optional[str]:
        resp = (
            self._sb.table("memory_secrets")
            .select("answer_hash")
            .eq("family_group_id", group_id)
            .eq("id", question_id)
            .eq("active", True)
            .limit(1)
            .execute()
        )
        rows = resp.data or []
        return rows[0]["answer_hash"] if rows else None

    def get_totp_secret(self, group_id: str) -> Optional[str]:
        resp = (
            self._sb.table("family_groups")
            .select("totp_secret")
            .eq("id", group_id)
            .limit(1)
            .execute()
        )
        rows = resp.data or []
        return rows[0].get("totp_secret") if rows else None

    def set_totp_secret(self, group_id: str, secret: str) -> None:
        self._sb.table("family_groups").update({"totp_secret": secret}).eq(
            "id", group_id
        ).execute()


# ---------------------------------------------------------------------------
# Store selection (Supabase → in-memory fallback)
# ---------------------------------------------------------------------------
_store: Optional[MemoryStore] = None
_store_lock = threading.Lock()


def _generate_invite_code() -> str:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O/1/I
    body = "".join(random.SystemRandom().choice(alphabet) for _ in range(6))
    return f"{body[:3]}-{body[3:]}"


def get_store() -> MemoryStore:
    """Return the active store, probing Supabase once and caching the result."""
    global _store
    if _store is not None:
        return _store
    with _store_lock:
        if _store is not None:
            return _store
        from app.clients.supabase_client import get_supabase

        client = get_supabase()
        if client is not None:
            try:
                client.table("family_groups").select("id").limit(1).execute()
                _store = SupabaseStore(client)
                logger.info("Memory store: supabase")
                return _store
            except Exception as exc:  # noqa: BLE001 — fall back, never block boot
                logger.warning(
                    "Supabase probe failed (%s) - falling back to in-memory store", exc
                )
        _store = InMemoryStore()
        logger.info("Memory store: in-memory (development)")
        return _store


def set_store(store: Optional[MemoryStore]) -> None:
    """Test hook — inject/replace the store (None resets selection)."""
    global _store
    _store = store


# ---------------------------------------------------------------------------
# Public API — groups
# ---------------------------------------------------------------------------
def create_group(name: Optional[str] = None, created_by: Optional[str] = None) -> dict:
    group = get_store().create_group(name=name, created_by=created_by)
    return {
        "family_group_id": str(group["id"]),
        "invite_code": group["invite_code"],
    }


def join_group(invite_code: str) -> dict:
    group = get_store().find_group_by_invite(invite_code)
    if not group:
        raise NotFoundError("invalid invite code")
    return {
        "family_group_id": str(group["id"]),
        "invite_code": group["invite_code"],
    }


# ---------------------------------------------------------------------------
# Public API — questions
# ---------------------------------------------------------------------------
def setup_questions(group_id: str, questions: list[dict]) -> dict:
    """Validate, hash, and persist challenge questions. Returns setup summary.

    Each input dict: {"question": str, "answer": str}. Answers are hashed
    here — callers may pass plaintext; storage only ever sees hashes.
    """
    cleaned = []
    for q in questions:
        question_text = (q.get("question") or "").strip()
        answer = q.get("answer") or ""
        if not question_text or not answer.strip():
            raise MemoryError("Each question needs both text and an answer.")
        cleaned.append({"question": question_text, "answer": answer})

    if len(cleaned) < MIN_QUESTIONS:
        raise MemoryError(
            f"Please add at least {MIN_QUESTIONS} questions for reliable verification."
        )
    if len(cleaned) > MAX_QUESTIONS:
        raise MemoryError(f"At most {MAX_QUESTIONS} questions.")

    store = get_store()
    rows = [
        {
            "id": str(uuid.uuid4()),
            "question": c["question"],
            "answer_hash": hash_answer(c["answer"]),
        }
        for c in cleaned
    ]
    store.save_questions(group_id, rows)

    secret = store.get_totp_secret(group_id)
    if not secret:
        secret = pyotp.random_base32()
        store.set_totp_secret(group_id, secret)

    return {
        "status": "saved",
        "questions_count": len(rows),
        "totp_secret": secret,
        "message": (
            "Memory Handshake configured. Share the TOTP secret with your "
            "family members so they can read the family code."
        ),
    }


def list_questions(group_id: str) -> list[dict]:
    questions = get_store().list_questions(group_id)
    return [{"question_id": q.id, "question": q.question} for q in questions]


def random_challenge(group_id: str) -> dict:
    """Pick a random active question for the in-call challenge (plan §4.6)."""
    questions = get_store().list_questions(group_id)
    if not questions:
        raise NotFoundError("no questions set up for this family group")
    pick = random.choice(questions)
    return {"question_id": pick.id, "question": pick.question}


def verify_answer(group_id: str, question_id: str, answer: str) -> dict:
    """Verify a typed answer against the stored hash. Rate-limited."""
    key = _attempt_key(group_id, question_id)
    remaining = lock_remaining_seconds(key)
    if remaining:
        raise RateLimitedError(remaining)

    stored_hash = get_store().get_answer_hash(group_id, question_id)
    if stored_hash is None:
        raise NotFoundError("question not found for this family group")

    if hash_answer(answer) == stored_hash:
        _reset_failures(key)
        return {"verified": True, "message": "Identity confirmed."}

    _record_failure(key)
    remaining = lock_remaining_seconds(key)
    if remaining:
        raise RateLimitedError(remaining)
    return {
        "verified": False,
        "message": (
            "The answer doesn't match. This could mean the caller is a "
            "scammer, OR they simply forgot. When in doubt, hang up and "
            "call them back on their known number."
        ),
    }


# ---------------------------------------------------------------------------
# Public API — TOTP
# ---------------------------------------------------------------------------
def _get_or_create_secret(group_id: str) -> str:
    secret = get_store().get_totp_secret(group_id)
    if not secret:
        secret = pyotp.random_base32()
        get_store().set_totp_secret(group_id, secret)
    return secret


def current_totp(group_id: str) -> dict:
    """Current rotating family code + seconds until rotation."""
    secret = _get_or_create_secret(group_id)
    totp = pyotp.TOTP(secret, interval=TOTP_INTERVAL)
    now = int(time.time())
    expires = TOTP_INTERVAL - (now % TOTP_INTERVAL)
    return {
        "code": totp.at(now),
        "expires_in_seconds": expires,
        "interval": TOTP_INTERVAL,
    }


def verify_totp(group_id: str, code: str) -> dict:
    """Verify a family code with ±1 interval clock-drift tolerance."""
    secret = _get_or_create_secret(group_id)
    totp = pyotp.TOTP(secret, interval=TOTP_INTERVAL)
    clean = (code or "").strip().replace(" ", "")
    if totp.verify(clean, valid_window=1):
        return {"verified": True, "message": "Identity confirmed."}
    return {"verified": False, "message": "That family code is not valid right now."}
