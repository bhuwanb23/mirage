"""Handler flow tests — text/voice/image/URL/commands with a mocked backend.

Every test builds a fake Update/Context from conftest, patches utils.api,
then asserts on the recorded bot calls (progress → edit → overflow).
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from conftest import make_update

from handlers import check, start
from handlers import help as help_mod

SCAM_BODY = {
    "verdict": {
        "is_scam": True,
        "confidence": 0.92,
        "scam_type": "bank_kyc",
        "risk_level": "critical",
        "red_flags": ["Asks for OTP", "Domain is 4 days old"],
        "summary": "Classic KYC scam.",
        "recommended_action": "DELETE IMMEDIATELY",
        "evidence": [{"type": "linguistic", "detail": "urgency"}],
    },
    "analysis_metadata": {"input_type": "text"},
}

LEGIT_BODY = {
    "verdict": {
        "is_scam": False,
        "confidence": 0.1,
        "summary": "Normal bank alert.",
        "red_flags": [],
        "evidence": [],
    },
    "analysis_metadata": {"input_type": "text"},
}

URL_BODY = {
    "urls_analyzed": [
        {
            "url": "http://sbi-kyc-verify.xyz/update",
            "domain": "sbi-kyc-verify.xyz",
            "tld": ".xyz",
            "domain_age_days": 4,
            "registrar": "Namecheap",
            "https": False,
            "risk_score": 0.75,
            "is_lookalike": True,
            "lookalike_target": "sbi.co.in",
            "brand_keyword": "sbi",
            "is_suspicious": True,
            "red_flags": ["Domain is only 4 days old"],
        }
    ],
    "overall_risk_score": 0.75,
    "overall_is_suspicious": True,
    "highest_risk_url": "http://sbi-kyc-verify.xyz/update",
}

VOICE_BODY = {
    "verdict": {
        "is_scam": True,
        "confidence": 0.88,
        "scam_type": "relative_distress",
        "risk_level": "critical",
        "red_flags": ["Isolation tactic"],
        "summary": "AI-cloned relative scam.",
        "recommended_action": "Do NOT send money",
        "evidence": [],
    },
    "transcript": "Send 50000 to this UPI immediately",
    "detected_language": "hi",
    "synthetic_voice_score": 0.72,
    "voice_verdict": "likely_ai_generated",
    "audio_duration_seconds": 15.3,
}

IMAGE_BODY = {
    "verdict": {
        "is_scam": True,
        "confidence": 0.9,
        "scam_type": "qr_code",
        "risk_level": "high",
        "red_flags": ["QR code scam pattern"],
        "summary": "QR receive scam.",
        "recommended_action": "Do NOT scan",
        "evidence": [],
    },
    "ocr_text": "Scan this QR code to receive 10000 from Flipkart",
    "visual_analysis_app": "WhatsApp",
    "visual_red_flags": ["pixelated logo"],
}


# ---------------------------------------------------------------------------
# 2.1 — Text
# ---------------------------------------------------------------------------

class TestTextHandler:
    async def test_scam_message_flow(self, bot, ctx):
        update = make_update("Your SBI account will be blocked within 24 hours!")
        with patch("handlers.check.api.analyze_text", new=AsyncMock(return_value=SCAM_BODY)):
            await check.text_message(update, ctx)

        names = [c for c, _ in bot.calls]
        assert "send_chat_action" in names          # typing indicator
        assert "send_message" in names              # progress
        assert "edit_message_text" in names         # verdict replaces progress
        edited = bot.last_edit()
        assert "SCAM DETECTED" in edited
        assert "92%" in edited
        assert "DELETE IMMEDIATELY" in edited

    async def test_progress_is_sent_before_edit(self, bot, ctx):
        update = make_update("will my account be blocked? send otp now")
        with patch("handlers.check.api.analyze_text", new=AsyncMock(return_value=SCAM_BODY)):
            await check.text_message(update, ctx)
        names = [c for c, _ in bot.calls]
        assert names.index("send_message") < names.index("edit_message_text")

    async def test_legit_message(self, bot, ctx):
        update = make_update("SBI: A/c XX1234 debited with Rs 1,250.00. Call 1800-11-2211")
        with patch("handlers.check.api.analyze_text", new=AsyncMock(return_value=LEGIT_BODY)):
            await check.text_message(update, ctx)
        assert "LIKELY LEGITIMATE" in bot.last_edit()

    async def test_greeting_not_analyzed(self, bot, ctx):
        update = make_update("hi")
        mock = AsyncMock()
        with patch("handlers.check.api.analyze_text", new=mock):
            await check.text_message(update, ctx)
        mock.assert_not_awaited()
        assert any("Hi!" in t for t in bot.texts())

    async def test_emoji_only(self, bot, ctx):
        update = make_update("😂👍🔥")
        mock = AsyncMock()
        with patch("handlers.check.api.analyze_text", new=mock):
            await check.text_message(update, ctx)
        mock.assert_not_awaited()
        assert any("I need text to analyze" in t for t in bot.texts())

    async def test_too_short(self, bot, ctx):
        update = make_update("ok.")
        # "ok." strips to "ok" → greeting; use a 4-char non-greeting instead
        update = make_update("ab.")
        mock = AsyncMock(return_value=LEGIT_BODY)
        with patch("handlers.check.api.analyze_text", new=mock):
            await check.text_message(update, ctx)
        assert mock.await_count == 0
        assert any("too short" in t.lower() for t in bot.texts())

    async def test_long_message_truncated(self, bot, ctx):
        update = make_update("a" * 6000)
        mock = AsyncMock(return_value=LEGIT_BODY)
        with patch("handlers.check.api.analyze_text", new=mock):
            await check.text_message(update, ctx)
        sent = mock.await_args.args[0]
        assert len(sent) <= 4000 + len("\n(Message truncated for analysis)")
        assert "truncated for analysis" in sent

    async def test_backend_400_shows_friendly_error(self, bot, ctx):
        from utils import api

        update = make_update("some message to analyse")
        with patch(
            "handlers.check.api.analyze_text",
            new=AsyncMock(side_effect=api.ApiError(400, "bad")),
        ):
            await check.text_message(update, ctx)
        assert any("Invalid input" in t for t in bot.texts())

    async def test_backend_down_shows_connection_error(self, bot, ctx):
        from utils import api

        update = make_update("some message to analyse")
        with patch(
            "handlers.check.api.analyze_text",
            new=AsyncMock(side_effect=api.ApiConnectionError("refused")),
        ):
            await check.text_message(update, ctx)
        assert any("Cannot reach the analysis server" in t for t in bot.texts())

    async def test_malformed_response(self, bot, ctx):
        update = make_update("some message to analyse")
        bad = AsyncMock(return_value={"no": "verdict"})
        with patch("handlers.check.api.analyze_text", new=bad):
            await check.text_message(update, ctx)
        assert any("server error" in t.lower() for t in bot.texts())

    async def test_phone_only_gets_tip(self, bot, ctx):
        update = make_update("+91 98765 43210")
        with patch("handlers.check.api.analyze_text", new=AsyncMock(return_value=LEGIT_BODY)):
            await check.text_message(update, ctx)
        assert any("call recording" in t for t in bot.texts())


# ---------------------------------------------------------------------------
# 2.4 — URL
# ---------------------------------------------------------------------------

class TestUrlHandler:
    async def test_bare_url_triggers_domain_analysis(self, bot, ctx):
        update = make_update("https://sbi-kyc-verify.xyz/update")
        mock = AsyncMock(return_value=URL_BODY)
        with patch("handlers.check.api.analyze_url", new=mock) as url_mock, patch(
            "handlers.check.api.analyze_text", new=AsyncMock()
        ) as text_mock:
            await check.url_message(update, ctx)
        url_mock.assert_awaited_once()
        text_mock.assert_not_awaited()
        edited = bot.last_edit()
        assert "DOMAIN ANALYSIS" in edited
        assert "4 days" in edited
        assert "75%" in edited
        assert "DO NOT visit" in edited

    async def test_url_with_other_text_falls_through_to_text(self, bot, ctx):
        update = make_update("check this link https://sbi-kyc-verify.xyz please")
        with patch("handlers.check.api.analyze_url", new=AsyncMock()) as url_mock, patch(
            "handlers.check.api.analyze_text", new=AsyncMock(return_value=SCAM_BODY)
        ) as text_mock:
            await check.url_message(update, ctx)
        url_mock.assert_not_awaited()
        text_mock.assert_awaited_once()

    async def test_normalization_adds_scheme(self):
        assert check.normalize_url("www.sbi.co.in/x") == "https://www.sbi.co.in/x"
        assert check.normalize_url("https://a.com") == "https://a.com"
        assert check.normalize_url("sbi-kyc-verify.xyz/update.") == "https://sbi-kyc-verify.xyz/update"

    async def test_shortener_note(self, bot, ctx):
        body = {
            "urls_analyzed": [
                {
                    "url": "https://bit.ly/abc",
                    "domain": "bit.ly",
                    "tld": ".ly",
                    "domain_age_days": 5000,
                    "registrar": "Bitly",
                    "https": True,
                    "risk_score": 0.5,
                    "is_lookalike": False,
                    "lookalike_target": None,
                    "brand_keyword": None,
                    "is_suspicious": True,
                    "red_flags": ["Shortened URL — destination hidden"],
                }
            ],
            "overall_risk_score": 0.5,
            "overall_is_suspicious": True,
            "highest_risk_url": "https://bit.ly/abc",
        }
        update = make_update("https://bit.ly/abc")
        with patch("handlers.check.api.analyze_url", new=AsyncMock(return_value=body)):
            await check.url_message(update, ctx)
        assert any("shortened URL" in t for t in bot.texts())

    async def test_no_urls_found(self, bot, ctx):
        update = make_update("https://sbi-kyc-verify.xyz")
        with patch(
            "handlers.check.api.analyze_url",
            new=AsyncMock(return_value={"urls_analyzed": []}),
        ):
            await check.url_message(update, ctx)
        assert any("No URL could be extracted" in t for t in bot.texts())


# ---------------------------------------------------------------------------
# 2.2 — Voice
# ---------------------------------------------------------------------------

def _voice_meta(duration=15, size=500_000):
    return SimpleNamespace(
        file_id="voice-file-1", duration=duration, file_size=size,
        mime_type="audio/ogg", file_name=None,
    )


class TestVoiceHandler:
    async def test_voice_flow(self, bot, ctx):
        update = make_update(voice=_voice_meta())
        with patch("handlers.check.api.analyze_audio", new=AsyncMock(return_value=VOICE_BODY)):
            await check.voice_message(update, ctx)
        edited = bot.last_edit()
        assert "VOICE NOTE ANALYSIS" in edited
        assert "Send 50000 to this UPI immediately" in edited
        assert "72%" in edited
        assert "Hindi" in edited
        assert "SCAM DETECTED" in edited
        # downloaded via get_file
        assert bot.has("get_file")

    async def test_too_short_audio(self, bot, ctx):
        update = make_update(voice=_voice_meta(duration=0.5))
        mock = AsyncMock()
        with patch("handlers.check.api.analyze_audio", new=mock):
            await check.voice_message(update, ctx)
        mock.assert_not_awaited()
        assert any("too short" in t.lower() for t in bot.texts())

    async def test_too_long_audio(self, bot, ctx):
        update = make_update(voice=_voice_meta(duration=200))
        with patch("handlers.check.api.analyze_audio", new=AsyncMock()) as mock:
            await check.voice_message(update, ctx)
        mock.assert_not_awaited()
        assert any("max 2 minutes" in t for t in bot.texts())

    async def test_too_large_audio(self, bot, ctx):
        update = make_update(voice=_voice_meta(size=11 * 1024 * 1024))
        with patch("handlers.check.api.analyze_audio", new=AsyncMock()) as mock:
            await check.voice_message(update, ctx)
        mock.assert_not_awaited()
        assert any("too large" in t.lower() for t in bot.texts())

    async def test_no_speech(self, bot, ctx):
        body = dict(VOICE_BODY, transcript="No speech detected in audio")
        update = make_update(voice=_voice_meta())
        with patch("handlers.check.api.analyze_audio", new=AsyncMock(return_value=body)):
            await check.voice_message(update, ctx)
        assert any("No clear speech detected" in t for t in bot.texts())


# ---------------------------------------------------------------------------
# 2.3 — Image
# ---------------------------------------------------------------------------

def _photo(size=100_000):
    return [
        SimpleNamespace(file_id="small", file_size=1),
        SimpleNamespace(file_id="big", file_size=size),
    ]


class TestImageHandler:
    async def test_photo_flow(self, bot, ctx):
        update = make_update(photo=_photo())
        with patch("handlers.check.api.analyze_image", new=AsyncMock(return_value=IMAGE_BODY)):
            await check.photo_message(update, ctx)
        edited = bot.last_edit()
        assert "SCREENSHOT ANALYSIS" in edited
        assert "WhatsApp" in edited
        assert "<code>" in edited
        assert "pixelated logo" in edited
        assert "SCAM DETECTED" in edited
        assert "QR code" in edited  # QR warning appended

    async def test_highest_resolution_used(self, bot, ctx):
        update = make_update(photo=_photo())
        with patch("handlers.check.api.analyze_image", new=AsyncMock(return_value=IMAGE_BODY)):
            await check.photo_message(update, ctx)
        get_file_calls = [k for c, k in bot.calls if c == "get_file"]
        assert get_file_calls[0]["file_id"] == "big"

    async def test_too_large_image(self, bot, ctx):
        update = make_update(photo=_photo(size=6 * 1024 * 1024))
        with patch("handlers.check.api.analyze_image", new=AsyncMock()) as mock:
            await check.photo_message(update, ctx)
        mock.assert_not_awaited()
        assert any("5 MB" in t for t in bot.texts())

    async def test_no_text_image(self, bot, ctx):
        body = dict(IMAGE_BODY, ocr_text="   ")
        update = make_update(photo=_photo())
        with patch("handlers.check.api.analyze_image", new=AsyncMock(return_value=body)):
            await check.photo_message(update, ctx)
        assert any("No text found" in t for t in bot.texts())

    async def test_unsupported_document(self, bot, ctx):
        doc = SimpleNamespace(
            file_id="d", file_size=1000, mime_type="application/pdf", file_name="x.pdf"
        )
        update = make_update(document=doc)
        with patch("handlers.check.api.analyze_image", new=AsyncMock()) as mock:
            await check.photo_message(update, ctx)
        mock.assert_not_awaited()
        assert any("Unsupported file type" in t for t in bot.texts())


# ---------------------------------------------------------------------------
# 2.5 — Commands
# ---------------------------------------------------------------------------

class TestCommands:
    async def test_start_welcome(self, bot, ctx):
        update = make_update()
        await start.start(update, ctx)
        assert "AI Scam Shield" in bot.texts()[0]
        assert "/check" in bot.texts()[0]

    async def test_help_guide(self, bot, ctx):
        update = make_update()
        await help_mod.help_command(update, ctx)
        assert "Mirage Help" in bot.texts()[0]
        assert "Voice notes" in bot.texts()[0]

    async def test_check_without_args_shows_usage(self, bot, ctx):
        update = make_update()
        await check.check_command(update, ctx)
        assert any("Usage:" in t for t in bot.texts())

    async def test_check_with_text(self, bot, ctx):
        update = make_update()
        ctx.args = ["your", "account", "will", "be", "blocked", "now", "send", "otp"]
        with patch("handlers.check.api.analyze_text", new=AsyncMock(return_value=SCAM_BODY)):
            await check.check_command(update, ctx)
        assert "SCAM DETECTED" in bot.last_edit()

    async def test_check_too_short_args(self, bot, ctx):
        update = make_update()
        ctx.args = ["hi"]
        with patch("handlers.check.api.analyze_text", new=AsyncMock()) as mock:
            await check.check_command(update, ctx)
        mock.assert_not_awaited()
        assert any("more text" in t for t in bot.texts())

    async def test_check_with_url_routes_to_url_analysis(self, bot, ctx):
        update = make_update()
        ctx.args = ["https://sbi-kyc-verify.xyz/update"]
        url_mock = AsyncMock(return_value=URL_BODY)
        text_mock = AsyncMock()
        with patch("handlers.check.api.analyze_url", new=url_mock), patch(
            "handlers.check.api.analyze_text", new=text_mock
        ):
            await check.check_command(update, ctx)
        url_mock.assert_awaited_once()
        text_mock.assert_not_awaited()
