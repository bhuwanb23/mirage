"""Tests for the Memory Handshake service + /memory API (Phase 4.5).

In-memory store throughout — no Supabase required. Rate-limit state and
store selection are reset between tests.
"""

from __future__ import annotations

import time

import pyotp
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import memory_handshake as m

QUESTIONS = [
    {"question": "What did we name our dog in 2019?", "answer": "Bruno"},
    {"question": "What street did we grow up on?", "answer": "MG Road, Indore"},
    {"question": "What's mom's middle name?", "answer": "Kumari"},
]


@pytest.fixture(autouse=True)
def fresh_state():
    m.set_store(m.InMemoryStore())
    m.reset_rate_limits()
    yield
    m.set_store(None)
    m.reset_rate_limits()


@pytest.fixture
def group() -> dict:
    return m.create_group("Sharma Family")


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


# ---------------------------------------------------------------------------
# Normalization + hashing
# ---------------------------------------------------------------------------
class TestNormalization:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("Bruno", "bruno"),
            ("  Bruno.  ", "bruno"),
            ("BRUNO", "bruno"),
            ("MG Road, Indore", "mg road indore"),
            ("What's", "whats"),
        ],
    )
    def test_normalize_answer(self, raw: str, expected: str):
        assert m.normalize_answer(raw) == expected

    def test_hash_is_deterministic_and_normalized(self):
        assert m.hash_answer(" Bruno. ") == m.hash_answer("bruno")
        assert len(m.hash_answer("bruno")) == 64  # sha256 hex

    def test_hash_differs_for_different_answers(self):
        assert m.hash_answer("bruno") != m.hash_answer("tommy")

    def test_hash_is_not_plaintext(self):
        assert "bruno" not in m.hash_answer("bruno")


# ---------------------------------------------------------------------------
# Service — groups + setup
# ---------------------------------------------------------------------------
class TestGroups:
    def test_create_group_returns_invite_code(self, group):
        assert group["family_group_id"]
        assert "-" in group["invite_code"]

    def test_join_by_invite(self, group):
        joined = m.join_group(group["invite_code"])
        assert joined["family_group_id"] == group["family_group_id"]

    def test_join_bad_code_raises(self, group):
        with pytest.raises(m.NotFoundError):
            m.join_group("NOPE-999")


class TestSetup:
    def test_setup_requires_at_least_three(self, group):
        with pytest.raises(m.MemoryError, match="at least 3"):
            m.setup_questions(group["family_group_id"], QUESTIONS[:2])

    def test_setup_saves_and_returns_totp(self, group):
        result = m.setup_questions(group["family_group_id"], QUESTIONS)
        assert result["status"] == "saved"
        assert result["questions_count"] == 3
        assert result["totp_secret"]  # base32 secret issued

    def test_setup_rejects_empty_answer(self, group):
        bad = QUESTIONS[:2] + [{"question": "q3", "answer": "   "}]
        with pytest.raises(m.MemoryError):
            m.setup_questions(group["family_group_id"], bad)

    def test_plaintext_answers_never_stored(self, group):
        m.setup_questions(group["family_group_id"], QUESTIONS)
        gid = group["family_group_id"]
        for row in QUESTIONS:
            # find the question's stored hash — must not contain the answer
            questions = m.list_questions(gid)
            assert len(questions) == 3
        stored_hash = m.get_store().get_answer_hash(gid, m.list_questions(gid)[0]["question_id"])
        assert "Bruno" not in stored_hash

    def test_reset_deactivates_and_replaces(self, group):
        gid = group["family_group_id"]
        m.setup_questions(gid, QUESTIONS)
        first_ids = {q["question_id"] for q in m.list_questions(gid)}
        new_questions = QUESTIONS[:2] + [{"question": "Old school name?", "answer": "St. Xaviers"}]
        m.setup_questions(gid, new_questions)
        second_ids = {q["question_id"] for q in m.list_questions(gid)}
        assert first_ids.isdisjoint(second_ids)  # new ids issued
        assert len(second_ids) == 3


# ---------------------------------------------------------------------------
# Service — verification
# ---------------------------------------------------------------------------
class TestVerify:
    def test_correct_answer_verifies(self, group):
        gid = group["family_group_id"]
        m.setup_questions(gid, QUESTIONS)
        qid = m.list_questions(gid)[0]["question_id"]
        result = m.verify_answer(gid, qid, "  bruno. ")
        assert result["verified"] is True
        assert "confirmed" in result["message"].lower()

    def test_wrong_answer_fails(self, group):
        gid = group["family_group_id"]
        m.setup_questions(gid, QUESTIONS)
        qid = m.list_questions(gid)[0]["question_id"]
        result = m.verify_answer(gid, qid, "tommy")
        assert result["verified"] is False

    def test_three_wrongs_lock_for_five_minutes(self, group):
        gid = group["family_group_id"]
        m.setup_questions(gid, QUESTIONS)
        qid = m.list_questions(gid)[0]["question_id"]
        m.verify_answer(gid, qid, "a")
        m.verify_answer(gid, qid, "b")
        with pytest.raises(m.RateLimitedError) as exc_info:
            m.verify_answer(gid, qid, "c")
        assert 0 < exc_info.value.retry_after_seconds <= m.LOCK_SECONDS

    def test_lock_survives_correct_answer_until_expiry(self, group):
        gid = group["family_group_id"]
        m.setup_questions(gid, QUESTIONS)
        qid = m.list_questions(gid)[0]["question_id"]
        for wrong in ("a", "b", "c"):
            try:
                m.verify_answer(gid, qid, wrong)
            except m.RateLimitedError:
                break
        with pytest.raises(m.RateLimitedError):
            m.verify_answer(gid, qid, "bruno")  # correct but locked

    def test_correct_answer_resets_failure_count(self, group):
        gid = group["family_group_id"]
        m.setup_questions(gid, QUESTIONS)
        qid = m.list_questions(gid)[0]["question_id"]
        m.verify_answer(gid, qid, "a")          # fails = 1
        m.verify_answer(gid, qid, "bruno")      # success → reset
        m.verify_answer(gid, qid, "b")          # fails = 1 (restarted)
        m.verify_answer(gid, qid, "c")          # fails = 2
        # Without the reset, these would already be fails=3 → locked.
        result = m.verify_answer(gid, qid, "bruno")
        assert result["verified"] is True

    def test_unknown_question_raises(self, group):
        with pytest.raises(m.NotFoundError):
            m.verify_answer(group["family_group_id"], "does-not-exist", "x")


# ---------------------------------------------------------------------------
# Service — challenge + TOTP
# ---------------------------------------------------------------------------
class TestChallengeAndTotp:
    def test_random_challenge_from_active_set(self, group):
        gid = group["family_group_id"]
        m.setup_questions(gid, QUESTIONS)
        challenge = m.random_challenge(gid)
        texts = {q["question"] for q in m.list_questions(gid)}
        assert challenge["question"] in texts
        assert challenge["question_id"]

    def test_challenge_without_setup_raises(self, group):
        with pytest.raises(m.NotFoundError):
            m.random_challenge(group["family_group_id"])

    def test_totp_rotates_every_five_minutes(self, group):
        totp = m.current_totp(group["family_group_id"])
        assert len(totp["code"]) == 6
        assert totp["code"].isdigit()
        assert totp["interval"] == 300
        assert 0 < totp["expires_in_seconds"] <= 300

    def test_totp_verifies(self, group):
        gid = group["family_group_id"]
        totp = m.current_totp(gid)
        assert m.verify_totp(gid, totp["code"])["verified"] is True

    def test_totp_rejects_garbage(self, group):
        gid = group["family_group_id"]
        # Collect the valid window (current ±1 interval) and pick a code
        # guaranteed to be outside it.
        t = pyotp.TOTP(m._get_or_create_secret(gid), interval=m.TOTP_INTERVAL)
        now = int(time.time())
        valid_codes = {t.at(now + offset) for offset in (-300, 0, 300)}
        candidate = "000000"
        while candidate in valid_codes:
            candidate = f"{int(candidate) + 1:06d}"[-6:]
        assert m.verify_totp(gid, candidate)["verified"] is False


# ---------------------------------------------------------------------------
# API layer
# ---------------------------------------------------------------------------
class TestMemoryApi:
    def _setup_group(self, client: TestClient) -> tuple[str, list[dict]]:
        resp = client.post("/memory/group", json={"name": "Sharma Family"})
        assert resp.status_code == 200
        gid = resp.json()["family_group_id"]
        payload = {"family_group_id": gid, "questions": QUESTIONS}
        assert client.post("/memory/setup", json=payload).status_code == 200
        questions = client.get(f"/memory/questions/{gid}").json()["questions"]
        return gid, questions

    def test_group_create_and_join(self, client):
        created = client.post("/memory/group", json={"name": "Fam"}).json()
        joined = client.post("/memory/group/join", json={"invite_code": created["invite_code"]})
        assert joined.status_code == 200
        assert joined.json()["family_group_id"] == created["family_group_id"]

    def test_join_invalid_code_404(self, client):
        resp = client.post("/memory/group/join", json={"invite_code": "ZZZ-999"})
        assert resp.status_code == 404

    def test_setup_min_three_enforced(self, client):
        gid = client.post("/memory/group", json={}).json()["family_group_id"]
        resp = client.post(
            "/memory/setup",
            json={"family_group_id": gid, "questions": QUESTIONS[:2]},
        )
        assert resp.status_code == 400
        assert "at least 3" in resp.json()["detail"]

    def test_full_flow(self, client):
        gid, questions = self._setup_group(client)
        # challenge
        challenge = client.get(f"/memory/challenge/{gid}").json()
        assert challenge["question"]
        # verify correct
        verify = client.post(
            "/memory/verify",
            json={
                "family_group_id": gid,
                "question_id": questions[0]["question_id"],
                "answer": " Bruno ",
            },
        )
        assert verify.status_code == 200
        assert verify.json()["verified"] is True
        # totp
        totp = client.get(f"/memory/totp/{gid}").json()
        assert len(totp["code"]) == 6
        assert client.post(
            "/memory/verify-totp", json={"family_group_id": gid, "code": totp["code"]}
        ).json()["verified"] is True

    def test_verify_wrong_then_locked_429(self, client):
        gid, questions = self._setup_group(client)
        qid = questions[0]["question_id"]
        for _ in range(3):
            resp = client.post(
                "/memory/verify",
                json={"family_group_id": gid, "question_id": qid, "answer": "nope"},
            )
        assert resp.status_code == 429
        assert "Retry-After" in resp.headers

    def test_questions_endpoint_never_leaks_answers(self, client):
        gid, _ = self._setup_group(client)
        body = client.get(f"/memory/questions/{gid}").json()
        for q in body["questions"]:
            assert set(q.keys()) == {"question_id", "question"}
