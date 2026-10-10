"""Tests for the Phase 5.1 honeypot engine (persona, health, guard, fallback)."""

from __future__ import annotations

from unittest.mock import patch

from app.services import honeypot_engine
from app.services.honeypot_engine import (
    detect_health,
    fallback_reply,
    generate_turn,
    parse_agent_json,
    sanitize_reply,
)


class TestPersona:
    def test_ramesh_prompt_matches_plan(self):
        prompt = honeypot_engine.PERSONAS["ramesh"]
        assert 'You are "Ramesh Kumar", a 62-year-old retired bank clerk' in prompt
        assert "Jaipur, Rajasthan" in prompt
        assert "NEVER reveal that you are an AI" in prompt
        assert "KEEP THE SCAMMER TALKING" in prompt
        assert "mishearing" in prompt  # tactic enum in the JSON format

    def test_all_personas_available(self):
        for key in ("ramesh", "sunita", "vikram", "meena"):
            assert key in honeypot_engine.PERSONAS
            assert len(honeypot_engine.PERSONAS[key]) > 100


class TestConversationHealth:
    def test_normal_message_is_engaged(self):
        assert detect_health("Yes, transfer the money to the safe account.") == "engaged"

    def test_caps_and_shouting_is_frustrated(self):
        assert detect_health("JUST DO IT NOW!!!") == "frustrated"

    def test_frustrated_keywords(self):
        assert detect_health("are you stupid? just do it") == "frustrated"

    def test_hangup_signals(self):
        assert detect_health("I am disconnecting, useless person") == "about_to_hang_up"
        assert detect_health("forget it, calling the next person") == "about_to_hang_up"

    def test_empty_message(self):
        assert detect_health("") == "engaged"


class TestBreakCharacterGuard:
    def test_ai_revelation_replaced(self):
        assert sanitize_reply("As an AI, I cannot help you with that.") == (
            "Sorry beta, I got confused. What were you saying?"
        )
        assert "language model" in sanitize_reply("I'm a language model.").lower() or (
            sanitize_reply("I'm a language model.")
            == "Sorry beta, I got confused. What were you saying?"
        )

    def test_greeting_prefix_stripped(self):
        assert sanitize_reply("Ramesh: Okay beta, I am doing it.") == "Okay beta, I am doing it."

    def test_in_character_reply_untouched(self):
        reply = "Sorry beta, I didn't catch that. Can you say the number again slowly?"
        assert sanitize_reply(reply) == reply


class TestAgentJSONParsing:
    def test_plain_json(self):
        assert parse_agent_json('{"reply": "hi", "tactic_used": "tangent"}')["reply"] == "hi"

    def test_fenced_json(self):
        raw = '```json\n{"reply": "beta"}\n```'
        assert parse_agent_json(raw)["reply"] == "beta"

    def test_json_with_surrounding_chatter(self):
        raw = 'Sure! Here is my response: {"reply": "okay beta"} — hope that helps.'
        assert parse_agent_json(raw)["reply"] == "okay beta"

    def test_garbage_returns_empty(self):
        assert parse_agent_json("not json at all") == {}
        assert parse_agent_json("") == {}


class TestFallbackReply:
    def test_goal_phone_asked_with_mishearing(self):
        from app.models.schemas import ThreatIOCs

        turn = fallback_reply("ramesh", "transfer the money", ThreatIOCs(), 0, "engaged")
        assert turn.tactic_used in honeypot_engine.TACTICS
        assert "beta" in turn.reply.lower() or "hearing" in turn.reply.lower()
        assert len(turn.reply.split(".")) <= 6  # 2-4 sentences, not a monologue

    def test_frustrated_scammer_gets_compliance(self):
        from app.models.schemas import ThreatIOCs

        turn = fallback_reply("ramesh", "JUST DO IT!!!", ThreatIOCs(), 2, "frustrated")
        assert turn.tactic_used == "compliance"
        assert "sorry" in turn.reply.lower() or "please" in turn.reply.lower()

    def test_hangup_threat_gets_greed_emergency(self):
        from app.models.schemas import ThreatIOCs

        turn = fallback_reply(
            "ramesh", "forget it, useless", ThreatIOCs(), 4, "about_to_hang_up"
        )
        assert "2,00,000" in turn.reply  # greed keeps them on the line

    def test_wrapup_after_50_messages(self):
        from app.models.schemas import ThreatIOCs

        turn = fallback_reply("ramesh", "yes", ThreatIOCs(), 50, "engaged")
        assert "dinner" in turn.reply.lower()

    def test_never_reveals_ai(self):
        from app.models.schemas import ThreatIOCs

        for n in range(8):
            turn = fallback_reply("ramesh", "hello", ThreatIOCs(), n, "engaged")
            assert "ai" not in turn.reply.lower().split()


class TestGenerateTurn:
    def test_llm_turn_used_when_available(self):
        import json

        from app.models.schemas import ThreatIOCs

        payload = {
            "reply": "Okay beta, I am opening PhonePe now...",
            "tactic_used": "app_failure",
            "iocs_extracted_this_turn": {"upi_ids": ["sbi-safe@ybl"]},
            "conversation_health": "engaged",
            "estimated_time_wasted_seconds": 50,
        }
        with patch(
            "app.clients.llm.chat_completion", return_value=json.dumps(payload)
        ):
            turn = generate_turn("ramesh", "pay now", [], ThreatIOCs())
        assert turn.tactic_used == "app_failure"
        assert [i.value for i in turn.iocs_extracted.upi_ids] == ["sbi-safe@ybl"]

    def test_llm_failure_falls_back_to_rules(self):
        from app.models.schemas import ThreatIOCs

        with patch(
            "app.clients.llm.chat_completion", side_effect=RuntimeError("no key")
        ):
            turn = generate_turn("ramesh", "pay now", [], ThreatIOCs())
        assert turn.reply  # deterministic in-character reply
        assert "ai" not in turn.reply.lower().split()

    def test_simulate_skips_llm_entirely(self):
        from app.models.schemas import ThreatIOCs

        with patch(
            "app.clients.llm.chat_completion",
            side_effect=AssertionError("LLM must not be called in simulate mode"),
        ):
            turn = generate_turn("ramesh", "pay now", [], ThreatIOCs(), simulate=True)
        assert turn.reply

    def test_agent_reported_iocs_validated(self):
        import json

        from app.models.schemas import ThreatIOCs

        payload = {
            "reply": "beta",
            "tactic_used": "mishearing",
            "iocs_extracted_this_turn": {"phone_numbers": ["+91 98111 22233", "12345"]},
            "conversation_health": "engaged",
            "estimated_time_wasted_seconds": 30,
        }
        with patch("app.clients.llm.chat_completion", return_value=json.dumps(payload)):
            turn = generate_turn("ramesh", "call me", [], ThreatIOCs())
        assert [i.value for i in turn.iocs_extracted.phone_numbers] == ["9811122233"]


def test_next_goal_priority():
    from app.models.schemas import IOCItem, ThreatIOCs

    assert honeypot_engine.next_goal(ThreatIOCs()) == "phone number"
    iocs = ThreatIOCs(phone_numbers=[IOCItem(value="9876543211")])
    assert honeypot_engine.next_goal(iocs) == "UPI ID"
    iocs.upi_ids = [IOCItem(value="sbi-safe@ybl")]
    assert honeypot_engine.next_goal(iocs) == "bank account"


def test_estimate_time_wasted_positive():
    for tactic in honeypot_engine.TACTICS:
        assert honeypot_engine.estimate_time_wasted(tactic, "engaged") > 0
    assert honeypot_engine.estimate_time_wasted(
        "tangent", "about_to_hang_up"
    ) < honeypot_engine.estimate_time_wasted("tangent", "engaged")
