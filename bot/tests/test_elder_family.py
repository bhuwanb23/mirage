"""Elder Mode + Family Alert tests (Phase 2.6 / 2.7)."""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, patch

import pytest
from conftest import make_update

from handlers import check
from handlers import elder as elder_mod
from handlers import family as family_mod
from utils import alert_dispatcher as state
from utils.elder_formatter import simplify, strip_for_tts, voice_script

SCAM = {
    "is_scam": True,
    "confidence": 0.92,
    "scam_type": "bank_kyc",
    "risk_level": "critical",
    "summary": "KYC scam with <tags> & symbols",
    "red_flags": ["asks OTP"],
    "evidence": [],
}

HIGH_SCAM = dict(SCAM, confidence=0.9)
MEDIUM_SCAM = dict(SCAM, confidence=0.7)
LOW_CONF_SCAM = dict(SCAM, confidence=0.5)


# ---------------------------------------------------------------------------
# 2.6 — Elder Mode
# ---------------------------------------------------------------------------

class TestElderToggle:
    async def test_activate_sets_state_and_asks_language(self, bot, ctx):
        update = make_update(user_id=42)
        await elder_mod.elder(update, ctx)
        assert state.elder_enabled(42) is True
        assert state.elder_language(42) == "hi"  # default before choice
        texts = bot.texts()
        assert any("ELDER MODE ACTIVATED" in t for t in texts)
        assert any("Hindi" in t and "Tamil" in t for t in texts)

    async def test_deactivate(self, bot, ctx):
        update = make_update(user_id=42)
        await elder_mod.elder(update, ctx)
        await elder_mod.elder(update, ctx)
        assert state.elder_enabled(42) is False
        assert any("deactivated" in t for t in bot.texts())

    async def test_language_choice_consumed(self, bot, ctx):
        state.ELDER_MODE[42] = {"enabled": True, "language": "hi", "language_pending": True}
        update = make_update("2️⃣ Tamil", user_id=42)
        handled = await elder_mod.language_choice(update, ctx)
        assert handled is True
        assert state.elder_language(42) == "ta"
        assert any("Tamil" in t for t in bot.texts())

    async def test_language_choice_not_pending_passes_through(self, bot, ctx):
        state.ELDER_MODE[42] = {"enabled": True, "language": "hi"}
        update = make_update("some scam message", user_id=42)
        assert await elder_mod.language_choice(update, ctx) is False

    async def test_non_elder_user_passes_through(self, bot, ctx):
        update = make_update("1", user_id=99)
        assert await elder_mod.language_choice(update, ctx) is False

    async def test_default_language_job(self, bot, ctx):
        state.ELDER_MODE[42] = {"enabled": True, "language": "en", "language_pending": True}
        job = type("J", (), {"data": {"user_id": 42}})()
        ctx.job = job
        await elder_mod._default_language(ctx)
        assert state.elder_language(42) == "hi"
        assert any("defaulting to Hindi" in t for t in bot.texts())


class TestElderFormatter:
    def test_scam_text_verdict_first_no_jargon(self):
        out = simplify(SCAM)
        assert out.strip().startswith("\U0001f6a8")  # verdict FIRST
        assert "SCAM" in out or "धोखा" in out
        for jargon in ("domain", "TLD", "WHOIS", "confidence", "synthetic"):
            assert jargon not in out.lower()

    def test_legit_text(self):
        out = simplify({"is_scam": False, "confidence": 0.1})
        assert "looks OK" in out

    def test_uncertain_text(self):
        out = simplify({"is_scam": True, "confidence": 0.5})
        assert "Possible dhoka" in out

    @pytest.mark.parametrize("lang", ["en", "hi", "ta"])
    def test_voice_scripts_exist(self, lang):
        script = voice_script(SCAM, lang)
        assert len(script) > 30
        # TTS script must contain no emoji/html after stripping
        clean = strip_for_tts(script)
        assert "<b>" not in clean
        assert clean.isprintable() or all(c.isprintable() or c.isspace() for c in clean)

    def test_script_buckets(self):
        scam = voice_script({"is_scam": True, "confidence": 0.9}, "en")
        assert "scam" in scam.lower() or "warning" in scam.lower()
        ok = voice_script({"is_scam": False, "confidence": 0.1}, "en")
        assert "legitimate" in ok.lower()

    def test_strip_for_tts_removes_markup(self):
        out = strip_for_tts("❌ <b>SCAM</b> 🚨 हिंदी text")
        assert "<b>" not in out
        assert "SCAM" in out
        assert "हिंदी" in out  # Indic script preserved


class TestElderVoiceReply:
    async def test_voice_sent_when_elder_enabled(self, bot, ctx):
        state.ELDER_MODE[111] = {"enabled": True, "language": "en"}
        from utils import notify

        with patch("utils.notify._tts_temp_path") as tmp, patch(
            "edge_tts.Communicate"
        ) as comm:
            import os
            import tempfile

            fd = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
            fd.write(b"FAKE_MP3")
            fd.close()
            tmp.return_value = fd.name

            async def save(path):
                with open(path, "wb") as fh:
                    fh.write(b"FAKE_MP3")

            comm.return_value.save = save
            ok = await notify.send_elder_voice(ctx.bot if False else ctx, 111, SCAM, user_id=111)
        assert ok is True
        assert bot.has("send_voice")
        # temp file cleaned up
        assert not os.path.exists(fd.name)

    async def test_tts_failure_falls_back_to_text_only(self, bot, ctx):
        state.ELDER_MODE[111] = {"enabled": True, "language": "en"}
        from utils import notify

        with patch("edge_tts.Communicate", side_effect=RuntimeError("no network")):
            ok = await notify.send_elder_voice(ctx, 111, SCAM, user_id=111)
        assert ok is False
        assert not bot.has("send_voice")

    async def test_non_elder_skipped(self, bot, ctx):
        from utils import notify

        ok = await notify.send_elder_voice(ctx, 111, SCAM, user_id=111)
        assert ok is False


# ---------------------------------------------------------------------------
# 2.7 — Family alerts
# ---------------------------------------------------------------------------

class TestFamilyRegistration:
    async def test_group_links_user(self, bot, ctx):
        update = make_update(user_id=7, chat_id=-10055, chat_type="supergroup")
        await family_mod.family(update, ctx)
        assert state.family_group_for(7) == -10055
        assert any("linked for scam alerts" in t for t in bot.texts())

    async def test_private_shows_instructions(self, bot, ctx):
        update = make_update(user_id=7)
        await family_mod.family(update, ctx)
        texts = bot.texts()
        assert any("Family Alert Setup" in t for t in texts)
        assert any("/family in the group" in t for t in texts)

    async def test_private_linked_status(self, bot, ctx):
        state.link_family_group(7, -10055)
        update = make_update(user_id=7)
        await family_mod.family(update, ctx)
        assert any("You're linked" in t for t in bot.texts())


class TestThrottleLogic:
    def test_no_scam_no_alert(self):
        ok, reason = state.should_alert(1, {"is_scam": False, "confidence": 0.1})
        assert ok is False

    def test_low_confidence_no_alert(self):
        ok, _ = state.should_alert(1, LOW_CONF_SCAM)
        assert ok is False

    def test_no_group_no_alert(self):
        ok, reason = state.should_alert(1, HIGH_SCAM)
        assert ok is False and "no family group" in reason

    def test_high_confidence_with_group_alerts(self):
        state.link_family_group(1, -100)
        ok, _ = state.should_alert(1, HIGH_SCAM)
        assert ok is True

    def test_elder_threshold_drops_to_60(self):
        state.link_family_group(1, -100)
        state.ELDER_MODE[1] = {"enabled": True, "language": "hi"}
        ok, _ = state.should_alert(1, MEDIUM_SCAM)  # 0.70 > 0.60
        assert ok is True
        # and 0.65 with elder also passes (> 0.60)
        ok2, _ = state.should_alert(1, dict(SCAM, confidence=0.65))
        assert ok2 is True
        # exactly at threshold → no
        ok3, _ = state.should_alert(1, dict(SCAM, confidence=0.60))
        assert ok3 is False

    def test_three_per_hour_cap(self):
        state.link_family_group(1, -100)
        now = time.time()
        for i in range(3):
            state.record_alert(1, f"type_{i}", now=now - i)
        ok, reason = state.should_alert(1, HIGH_SCAM, now=now)
        assert ok is False and "hour" in reason

    def test_old_alerts_pruned(self):
        state.link_family_group(1, -100)
        now = time.time()
        for i in range(3):
            state.record_alert(1, "old", now=now - 4000)  # > 1h ago
        ok, _ = state.should_alert(1, HIGH_SCAM, now=now)
        assert ok is True

    def test_same_type_within_10_min_skipped(self):
        state.link_family_group(1, -100)
        now = time.time()
        state.record_alert(1, "bank_kyc", now=now - 60)
        ok, reason = state.should_alert(1, HIGH_SCAM, now=now)
        assert ok is False and "10 min" in reason

    def test_different_type_allowed(self):
        state.link_family_group(1, -100)
        now = time.time()
        state.record_alert(1, "lottery", now=now - 60)
        ok, _ = state.should_alert(1, HIGH_SCAM, now=now)  # bank_kyc
        assert ok is True


class TestAlertFormat:
    def test_alert_shows_who_what_when_action(self):
        from datetime import datetime

        text = state.format_alert("Ravi", HIGH_SCAM, when=datetime(2025, 1, 15, 15, 42))
        assert "FAMILY SCAM ALERT" in text
        assert "<b>Who:</b> Ravi" in text
        assert "<b>Threat:</b> Bank KYC / Account Freeze" in text
        assert "90%" in text  # HIGH_SCAM confidence is 0.9
        assert "Action needed" in text
        assert "1930" in text
        assert "15 Jan 2025" in text

    def test_alert_never_leaks_message_content(self):
        # summary IS included per spec (one-sentence), but the original
        # message text is not a field we ever pass — assert no red_flags leak.
        text = state.format_alert("Ravi", HIGH_SCAM)
        assert "asks OTP" not in text  # raw red flag not included
        assert "evidence" not in text.lower()

    def test_summary_truncated(self):
        long = dict(SCAM, summary="x" * 1000)
        text = state.format_alert("Ravi", long)
        assert "x" * 250 not in text


class TestFamilyAlertDispatch:
    async def test_alert_sent_to_group(self, bot, ctx):
        state.link_family_group(111, -10099)
        update = make_update("your account will be blocked, send otp", user_id=111)
        with patch(
            "handlers.check.api.analyze_text", new=AsyncMock(return_value={"verdict": HIGH_SCAM})
        ):
            await check.text_message(update, ctx)
        # Alert went to the group chat id
        group_sends = [
            k for c, k in bot.calls
            if c == "send_message" and k.get("chat_id") == -10099
        ]
        assert group_sends, "expected an alert to the family group"
        assert "FAMILY SCAM ALERT" in group_sends[0]["text"]

    async def test_no_group_no_alert_but_prompt_when_serious(self, bot, ctx):
        update = make_update("your account will be blocked, send otp", user_id=111)
        with patch(
            "handlers.check.api.analyze_text", new=AsyncMock(return_value={"verdict": HIGH_SCAM})
        ):
            await check.text_message(update, ctx)
        texts = bot.texts()
        assert not any("FAMILY SCAM ALERT" in t for t in texts)
        assert any("alert your family" in t for t in texts)

    async def test_alert_failure_notifies_user_privately(self, bot, ctx):
        from telegram.error import TelegramError

        state.link_family_group(111, -10099)

        original_send = bot.send_message

        async def failing_send(**kwargs):
            if kwargs.get("chat_id") == -10099:
                bot.calls.append(("send_message", kwargs))
                raise TelegramError("Forbidden: bot was kicked")
            return await original_send(**kwargs)

        bot.send_message = failing_send
        update = make_update("your account will be blocked, send otp", user_id=111)
        with patch(
            "handlers.check.api.analyze_text", new=AsyncMock(return_value={"verdict": HIGH_SCAM})
        ):
            await check.text_message(update, ctx)
        texts = bot.texts()
        assert any("no longer send alerts" in t for t in texts)

    async def test_throttled_alert_not_sent(self, bot, ctx):
        state.link_family_group(111, -10099)
        now = time.time()
        for i in range(3):
            state.record_alert(111, f"t{i}", now=now - i)
        update = make_update("your account will be blocked, send otp", user_id=111)
        with patch(
            "handlers.check.api.analyze_text", new=AsyncMock(return_value={"verdict": HIGH_SCAM})
        ):
            await check.text_message(update, ctx)
        group_sends = [
            k for c, k in bot.calls
            if c == "send_message" and k.get("chat_id") == -10099
        ]
        assert not group_sends

    async def test_elder_low_confidence_alerts_group(self, bot, ctx):
        state.link_family_group(111, -10099)
        state.ELDER_MODE[111] = {"enabled": True, "language": "hi"}
        update = make_update("your account will be blocked, send otp", user_id=111)
        with patch(
            "handlers.check.api.analyze_text",
            new=AsyncMock(return_value={"verdict": MEDIUM_SCAM}),  # 0.70
        ):
            await check.text_message(update, ctx)
        group_sends = [
            k for c, k in bot.calls
            if c == "send_message" and k.get("chat_id") == -10099
        ]
        assert group_sends
