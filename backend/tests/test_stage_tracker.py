"""Tests for the Scam Stage Tracker (Phase 4.2).

Fully offline: rule-based classification, the forward-only state machine,
confidence accumulation, alert thresholds, and the LLM cadence (with the
LLM mocked to either succeed or fail → fallback).
"""

from __future__ import annotations

import json

import pytest

from app.models.schemas import AlertLevel, ScamStage
from app.services import stage_tracker as st
from app.services.stage_tracker import (
    STAGE_ORDER,
    StageTracker,
    classify_rules,
    decide_alert,
    stage_rank,
)

# ---------------------------------------------------------------------------
# Fixtures — one test script per stage (plan checklist: classifier detects
# each stage from a test script, and returns "none" for legitimate calls).
# ---------------------------------------------------------------------------
SCRIPTS = {
    "hook": "Hello, is this Priya Sharma? I am calling from the rewards team. "
            "You've been selected for an exclusive offer.",
    "authority": "This is Officer Rajesh from the SBI fraud department. "
                 "This call is part of an RBI circular investigation by the cyber cell.",
    "isolation": "Do not tell anyone about this call. This is confidential. "
                 "Don't disconnect the call and don't inform your family.",
    "urgency": "Your account will be blocked within 30 minutes. Act immediately, "
               "this is your last chance or legal action will be taken tonight.",
    "payment": "Share the OTP and your ATM PIN. Transfer ₹50,000 to this UPI "
               "and scan this QR code immediately.",
    "none": "Hi mom, I'll be home around 7. Should I pick up bread on the way?",
}


def make_tracker(**kwargs) -> StageTracker:
    kwargs.setdefault("llm_enabled", False)
    return StageTracker(**kwargs)


# ---------------------------------------------------------------------------
# Rule-based classification
# ---------------------------------------------------------------------------
class TestClassifyRules:
    @pytest.mark.parametrize("stage", ["hook", "authority", "isolation", "urgency", "payment"])
    def test_detects_each_stage_from_script(self, stage: str):
        result = classify_rules(SCRIPTS[stage])
        assert stage_rank(result.stage) >= stage_rank(stage)
        assert result.confidence > 0.4
        assert result.signals

    def test_legitimate_conversation_returns_none(self):
        result = classify_rules(SCRIPTS["none"])
        assert result.stage == ScamStage.NONE.value
        assert result.confidence == 0.0

    def test_hello_alone_is_not_a_hook(self):
        assert classify_rules("Hello.").stage == ScamStage.NONE.value

    def test_empty_text_returns_none(self):
        assert classify_rules("").stage == ScamStage.NONE.value
        assert classify_rules("   ").stage == ScamStage.NONE.value

    def test_highest_stage_wins_when_multiple_match(self):
        # Contains authority + urgency + payment signals → payment wins.
        result = classify_rules(
            "This is the bank fraud department, your account will be "
            "blocked, share the OTP now"
        )
        assert stage_rank(result.stage) >= stage_rank(ScamStage.URGENCY.value)

    def test_hinglish_keywords(self):
        assert classify_rules("turant apna account band karo").stage != ScamStage.NONE.value


# ---------------------------------------------------------------------------
# Alert thresholds
# ---------------------------------------------------------------------------
class TestAlertThresholds:
    def test_safe_for_none(self):
        level, message = decide_alert("none", 0.1)
        assert level == AlertLevel.SAFE.value
        assert message is None

    def test_suspicious_for_authority(self):
        level, _ = decide_alert("authority", 0.7)
        assert level == AlertLevel.SUSPICIOUS.value

    def test_suspicious_for_isolation(self):
        level, _ = decide_alert("isolation", 0.7)
        assert level == AlertLevel.SUSPICIOUS.value

    def test_warning_for_urgency(self):
        level, message = decide_alert("urgency", 0.8)
        assert level == AlertLevel.WARNING.value
        assert "SCAM LIKELY" in message

    def test_critical_for_payment(self):
        level, message = decide_alert("payment", 0.7)
        assert level == AlertLevel.CRITICAL.value
        assert "HANG UP" in message

    def test_double_alert_with_ai_voice(self):
        level, message = decide_alert("urgency", 0.8, voice_synthetic=0.72)
        assert level == AlertLevel.CRITICAL.value
        assert "CONFIRMED SCAM" in message

    def test_low_confidence_authority_stays_safe(self):
        level, _ = decide_alert("authority", 0.3)
        assert level == AlertLevel.SAFE.value


# ---------------------------------------------------------------------------
# State machine
# ---------------------------------------------------------------------------
class TestStateMachine:
    def test_forward_only_no_backward_transitions(self):
        tracker = make_tracker()
        # Reach payment first.
        tracker.process(SCRIPTS["payment"], SCRIPTS["payment"], 10)
        assert tracker.current_stage == "payment"
        # A later hook-level chunk must NOT regress the stage.
        tracker.process("Hello, is this Priya?", SCRIPTS["payment"] + " Hello", 14)
        assert tracker.current_stage == "payment"

    def test_stages_can_skip_forward(self):
        tracker = make_tracker()
        tracker.process(SCRIPTS["payment"], SCRIPTS["payment"], 5)
        assert tracker.current_stage == "payment"

    def test_latch_stays_alerted_on_none(self):
        tracker = make_tracker()
        tracker.process(SCRIPTS["urgency"], SCRIPTS["urgency"], 8)
        stage_before = tracker.current_stage
        # Caller makes small talk — stage must not reset to none.
        tracker.process("So how is the weather there?", SCRIPTS["urgency"], 12)
        assert tracker.current_stage == stage_before

    def test_confidence_accumulates_on_confirmation(self):
        tracker = make_tracker()
        first = tracker.process(SCRIPTS["authority"], SCRIPTS["authority"], 4)
        confidence = first.confidence
        second = tracker.process(
            "The bank department is verifying your account",
            SCRIPTS["authority"] + " The bank department",
            8,
        )
        assert second.confidence >= confidence  # +0.05 confirm or forward boost
        assert second.confidence <= 0.95

    def test_confidence_cap_at_095(self):
        tracker = make_tracker()
        for i in range(30):
            tracker.process(
                "bank officer fraud department cyber cell rbi",
                "bank officer fraud department cyber cell rbi",
                i,
            )
        assert tracker.confidence <= 0.95

    def test_stage_timestamps_recorded(self):
        tracker = make_tracker()
        tracker.process(SCRIPTS["urgency"], SCRIPTS["urgency"], 33)
        assert tracker.stage_timestamps["urgency"] == 33

    def test_llm_disabled_never_calls_llm(self, monkeypatch):
        def boom(*_args, **_kwargs):
            raise AssertionError("LLM should not be called")

        monkeypatch.setattr(st, "classify_llm", boom)
        tracker = StageTracker(llm_enabled=False)
        tracker.process(SCRIPTS["hook"], SCRIPTS["hook"], 1)
        assert tracker.llm_chunks == 0
        assert tracker.classified_chunks == 1

    def test_llm_cadence_every_third_chunk(self, monkeypatch):
        calls = {"n": 0}

        def fake_llm(transcript, chunk, elapsed):
            calls["n"] += 1
            return st.StageClassification(
                stage="urgency", confidence=0.9, signals=["llm"], source="llm"
            )

        monkeypatch.setattr(st, "classify_llm", fake_llm)
        tracker = StageTracker(llm_every=3, llm_enabled=True)
        for i in range(7):
            tracker.process("some words", "some words", i)
        # chunks 0, 3, 6 → 3 LLM calls, 7 total classifications
        assert calls["n"] == 3
        assert tracker.llm_chunks == 3
        assert tracker.classified_chunks == 7

    def test_llm_failure_falls_back_to_rules(self, monkeypatch):
        def boom(*_args, **_kwargs):
            raise RuntimeError("all providers failed")

        monkeypatch.setattr(st, "classify_llm", boom)
        tracker = StageTracker(llm_every=1, llm_enabled=True)
        update = tracker.process(SCRIPTS["payment"], SCRIPTS["payment"], 5)
        assert tracker.llm_chunks == 0  # never incremented on failure
        assert stage_rank(update.current_stage) >= stage_rank("payment")
        assert update.classification_source == "rules"

    def test_empty_chunk_skips_classification(self):
        tracker = make_tracker()
        update = tracker.process("", "", 1, skip_classification=True)
        assert tracker.classified_chunks == 0
        assert update.alert_level == AlertLevel.SAFE.value


# ---------------------------------------------------------------------------
# Payload + summary
# ---------------------------------------------------------------------------
class TestPayloadAndSummary:
    def test_stage_update_payload_shape(self):
        tracker = make_tracker()
        update = tracker.process(SCRIPTS["urgency"], SCRIPTS["urgency"], 41)
        payload = update.to_payload()
        assert payload["type"] == "stage_update"
        for key in (
            "current_stage", "previous_stage", "confidence", "alert_level",
            "alert_message", "signals", "transcript_so_far",
            "call_duration_seconds", "stage_timestamps",
        ):
            assert key in payload
        assert payload["call_duration_seconds"] == 41

    def test_alert_level_never_downgrades_within_session(self):
        tracker = make_tracker()
        tracker.process(SCRIPTS["payment"], SCRIPTS["payment"], 10)
        assert tracker.alert_level == AlertLevel.CRITICAL.value
        tracker.process("hello there friend", SCRIPTS["payment"] + " hello", 14)
        assert tracker.alert_level == AlertLevel.CRITICAL.value

    def test_summary_reports_highest_stage_and_verdict(self):
        tracker = make_tracker()
        tracker.process(SCRIPTS["urgency"], SCRIPTS["urgency"], 40)
        summary = tracker.summary(SCRIPTS["urgency"], 44)
        assert summary["type"] == "summary"
        assert summary["highest_stage"] == "urgency"
        assert "scam" in summary["verdict"].lower()
        assert summary["duration_seconds"] == 44

    def test_summary_benign_call(self):
        tracker = make_tracker()
        tracker.process(SCRIPTS["none"], SCRIPTS["none"], 20)
        summary = tracker.summary(SCRIPTS["none"], 30)
        assert summary["highest_stage"] == "none"
        assert "No strong scam signals" in summary["verdict"]

    def test_stage_order_constant(self):
        assert STAGE_ORDER == ["none", "hook", "authority", "isolation", "urgency", "payment"]
        assert stage_rank("payment") == 5


def test_llm_output_parsing_tolerates_code_fences():
    payload = {
        "current_stage": "urgency",
        "confidence": 0.8,
        "signals": ["deadline"],
        "alert_level": "warning",
        "alert_message": "x",
        "is_scam_likely": True,
    }
    fenced = "```json\n" + json.dumps(payload) + "\n```"
    parsed = st._extract_json(fenced)
    assert parsed["current_stage"] == "urgency"
