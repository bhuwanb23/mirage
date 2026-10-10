"""Phase 3 fire drill tests — services + router end-to-end.

LLM and network calls are always patched: these tests run with no API keys.
"""

from __future__ import annotations

import io
import json
import wave
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from app.services import debrief_engine, resilience_score, script_generator, voice_synthesizer
from app.services.drill_store import reset as reset_store
from app.services.fallback_scripts import FALLBACK_SCRIPTS, render_fallback
from app.services.footprint_scraper import (
    bank_full_name,
    build_profile,
    first_name_of,
    resolve_bank,
)


@pytest.fixture(autouse=True)
def _clean_store(tmp_path, monkeypatch):
    """Isolate drill state + media dir per test."""
    from app.config import settings

    reset_store()
    monkeypatch.setattr(settings, "drill_media_dir", str(tmp_path / "media"))
    yield
    reset_store()


# ---------------------------------------------------------------------------
# 3.1 footprint_scraper
# ---------------------------------------------------------------------------

class TestFootprintScraper:
    def test_bank_defaults_to_sbi(self):
        assert resolve_bank(None) == "sbi"
        assert resolve_bank("  ") == "sbi"

    def test_bank_aliases(self):
        assert resolve_bank("SBI") == "sbi"
        assert resolve_bank("State Bank of India") == "sbi"
        assert resolve_bank("hdfc bank") == "hdfc"
        assert resolve_bank("ICICI") == "icici"

    def test_unknown_bank_falls_back(self):
        assert resolve_bank("some credit union") == "sbi"

    def test_bank_full_name(self):
        assert bank_full_name("HDFC") == "HDFC Bank"

    def test_first_name(self):
        assert first_name_of("Priya Sharma") == "Priya"
        assert first_name_of("  Ravi ") == "Ravi"

    def test_build_profile_defaults(self):
        p = build_profile(name="Priya Sharma")
        assert p["first_name"] == "Priya"
        assert p["city"] == "Mumbai"
        assert p["bank_full_name"] == "State Bank of India"
        assert p["profile_id"] and p["user_id"]

    def test_build_profile_requires_name(self):
        with pytest.raises(ValueError):
            build_profile(name="  ")


# ---------------------------------------------------------------------------
# fallback templates
# ---------------------------------------------------------------------------

class TestFallbackScripts:
    def test_all_five_scam_types_present(self):
        assert set(FALLBACK_SCRIPTS) == {
            "bank_kyc", "fedex", "relative_distress", "rbi_police", "job_offer",
        }

    @pytest.mark.parametrize("scam_type", sorted(FALLBACK_SCRIPTS))
    def test_rendered_has_all_stages_and_no_placeholders(self, scam_type):
        p = build_profile(name="Priya Sharma", city="Pune", bank="HDFC",
                           relative_name="Rahul", relative_relation="brother")
        out = render_fallback(scam_type, p)
        assert set(out["stages"]) == set(script_generator.STAGES)
        blob = json.dumps(out)
        assert "{name}" not in blob and "{city}" not in blob and "{bank}" not in blob
        assert "Priya Sharma" in out["full_script"]
        assert "Pune" in out["full_script"] or "Priya" in out["full_script"]
        assert len(out["red_flags_planted"]) >= 4
        assert len(out["full_script"].split()) >= 80

    def test_unknown_type_falls_back_to_bank_kyc(self):
        p = build_profile(name="Priya Sharma")
        out = render_fallback("not_a_real_type", p)
        assert out["scam_type"] == "bank_kyc"


# ---------------------------------------------------------------------------
# 3.2 script_generator
# ---------------------------------------------------------------------------

def _long_stage(word: str = "really") -> str:
    return " ".join([word] * 28)


def _valid_llm_script_json() -> str:
    stages = {
        stage: {
            "timestamp_hint": "0:00-0:10",
            "script": f"{_long_stage()}",
            "tactic": f"tactic for {stage}",
        }
        for stage in script_generator.STAGES
    }
    return json.dumps({
        "scam_type": "bank_kyc",
        "title": "Fake SBI KYC Verification Call",
        "stages": stages,
        "full_script": " ".join(_long_stage() for _ in script_generator.STAGES),
        "red_flags_planted": ["asked for OTP", "fake deadline"],
        "difficulty_level": "hard",
    })


class TestScriptGenerator:
    def test_sanitize_replaces_phone_url_upi(self):
        out = script_generator.sanitize_script(
            "Call 1800-111-2233 or 9876543210, visit https://sbi.co.in/login "
            "or pay to scam@okaxis"
        )
        assert "1800-111-2233" not in out
        assert "9876543210" not in out
        assert "https://" not in out
        assert "okaxis" not in out
        assert "98765-XXXXX" in out

    def test_estimate_duration(self):
        text = " ".join(["word"] * 150)
        assert script_generator.estimate_duration_seconds(text) == 60.0

    def test_fallback_when_llm_fails(self):
        p = build_profile(name="Priya Sharma", bank="HDFC")
        with patch("app.clients.llm.chat_completion", side_effect=RuntimeError("no key")):
            out = script_generator.generate_script(p, "fedex", "medium")
        assert out["source"] == "template"
        assert out["scam_type"] == "fedex"
        assert set(out["stages"]) == set(script_generator.STAGES)
        assert out["script_id"]
        assert out["estimated_duration_seconds"] > 30

    def test_llm_happy_path(self):
        p = build_profile(name="Priya Sharma")
        with patch("app.clients.llm.chat_completion", return_value=_valid_llm_script_json()):
            out = script_generator.generate_script(p, "bank_kyc", "hard")
        assert out["source"] == "llm"
        assert out["difficulty_level"] == "hard"
        assert set(out["stages"]) == set(script_generator.STAGES)
        assert len(out["full_script"].split()) <= 300  # truncated at sentence boundary

    def test_llm_garbage_falls_back(self):
        p = build_profile(name="Priya Sharma")
        with patch("app.clients.llm.chat_completion", return_value="sorry, I cannot help"):
            out = script_generator.generate_script(p, "bank_kyc", "medium")
        assert out["source"] == "template"

    def test_llm_too_short_falls_back(self):
        p = build_profile(name="Priya Sharma")
        short = json.dumps({
            "scam_type": "bank_kyc",
            "title": "tiny",
            "stages": {s: {"script": "too short", "tactic": "t"} for s in script_generator.STAGES},
            "full_script": "way too short to use",
            "red_flags_planted": ["x"],
        })
        with patch("app.clients.llm.chat_completion", return_value=short):
            out = script_generator.generate_script(p, "bank_kyc", "medium")
        assert out["source"] == "template"

    def test_unknown_scam_type_normalized(self):
        p = build_profile(name="Priya Sharma")
        with patch("app.clients.llm.chat_completion", side_effect=RuntimeError("x")):
            out = script_generator.generate_script(p, "bogus", "weird-difficulty")
        assert out["scam_type"] == "bank_kyc"
        assert out["difficulty_level"] in {"easy", "medium", "hard"}


# ---------------------------------------------------------------------------
# 3.3 voice_synthesizer
# ---------------------------------------------------------------------------

class TestVoiceSynthesizer:
    def test_prepare_text_strips_tags_and_keeps_pauses(self):
        text = voice_synthesizer.prepare_tts_text(
            "[STAGE: HOOK] Hello there. [pause 2s] More text."
        )
        assert "STAGE" not in text
        assert "…" in text
        assert "Hello there." in text

    def test_pick_voice(self):
        assert voice_synthesizer.pick_voice("job_offer", "en") == "en-IN-NeerjaNeural"
        assert voice_synthesizer.pick_voice("bank_kyc", "en") == "en-IN-PrabhatNeural"
        assert voice_synthesizer.pick_voice("bank_kyc", "hi") == "hi-IN-MadhurNeural"

    def test_strip_id3(self):
        payload = b"ID3\x04\x00\x00\x00\x00\x00\x05TAG!!\xff\xfbframe"
        assert voice_synthesizer._strip_id3(payload) == b"\xff\xfbframe"
        assert voice_synthesizer._strip_id3(b"\xff\xfbpad") == b"\xff\xfbpad"

    def test_is_cert_error(self):
        import ssl
        assert voice_synthesizer._is_cert_error(ssl.SSLError("boom"))
        assert voice_synthesizer._is_cert_error(Exception("CERTIFICATE_VERIFY_FAILED"))
        assert not voice_synthesizer._is_cert_error(Exception("connection reset"))

    def test_synthesize_writes_audio_with_stage_timings(self, tmp_path):
        p = build_profile(name="Priya Sharma")
        script = render_fallback("bank_kyc", p)
        script["script_id"] = "t1"
        script["language"] = "en"
        script["estimated_duration_seconds"] = 60.0

        # 6000 bytes == 1 second of edge-tts output (48 kbps CBR)
        async def fake_stream(text, voice):
            return b"\xff\xfb" + b"\x00" * 5998

        with patch.object(voice_synthesizer, "_stream_segment", fake_stream):
            out = voice_synthesizer.synthesize_script(script, p)

        assert out["status"] == "ready"
        assert out["method_used"] == "edge-tts"
        assert out["duration_seconds"] == 5.0  # 5 stages x 1s
        audio = Path(settings_path(out["audio_url"]))
        assert audio.exists() and audio.stat().st_size > 0
        # contiguous timings, all 5 stages
        assert list(out["stage_timings"]) == script_generator.STAGES
        assert out["stage_timings"]["payment"]["end"] == 5.0
        assert out["stage_timings"]["authority"]["start"] == 1.0

    def test_synthesize_failure_returns_graceful_payload(self):
        p = build_profile(name="Priya Sharma")
        script = render_fallback("bank_kyc", p)
        script["script_id"] = "t2"

        async def boom(text, voice):
            raise RuntimeError("network down")

        with patch.object(voice_synthesizer, "_stream_segment", boom):
            out = voice_synthesizer.synthesize_script(script, p)

        assert out["status"] == "failed"
        assert out["audio_url"] is None
        # fallback timings still cover the full script
        assert out["stage_timings"]["payment"]["end"] > 0


def settings_path(url: str) -> str:
    from app.config import settings
    return str(Path(settings.drill_media_dir) / Path(url).name)


# ---------------------------------------------------------------------------
# 3.5 debrief_engine
# ---------------------------------------------------------------------------

TIMINGS = {
    "hook": {"start": 0.0, "end": 8.0},
    "authority": {"start": 8.0, "end": 20.0},
    "isolation": {"start": 20.0, "end": 30.0},
    "urgency": {"start": 30.0, "end": 45.0},
    "payment": {"start": 45.0, "end": 60.0},
}


class TestDebriefEngine:
    def test_classify_stages_click_in_authority(self):
        caught, missed, trigger = debrief_engine.classify_stages(
            TIMINGS, "identified_scam", 18.3
        )
        assert caught == ["hook"]
        assert trigger == "authority"
        assert missed == ["isolation", "urgency", "payment"]

    def test_classify_stages_late_click(self):
        caught, missed, trigger = debrief_engine.classify_stages(
            TIMINGS, "identified_scam", 50.0
        )
        assert caught == ["hook", "authority", "isolation", "urgency"]
        assert trigger == "payment"  # clicked during the payment demand
        assert missed == []

    def test_classify_stages_fell_for_it(self):
        caught, missed, trigger = debrief_engine.classify_stages(TIMINGS, "fell_for_it", 60.0)
        assert caught == []
        assert missed == script_generator.STAGES
        assert trigger is None

    def test_fallback_debrief_complete(self):
        out = debrief_engine.build_fallback_debrief(
            script={"scam_type": "bank_kyc"},
            stage_timings=TIMINGS,
            user_action="fell_for_it",
            reaction_time=60.0,
            caught=[],
            missed=list(script_generator.STAGES),
        )
        assert out["outcome"] == "failed"
        assert "okay" in out["headline"].lower()
        assert len(out["stages_missed"]) == 5
        assert out["stages_caught"] == []
        assert out["key_lesson"] and out["real_world_action"] and out["encouragement"]
        # each missed stage detail teaches what/why/tip
        for d in out["stages_missed"]:
            assert d["what_happened"] and d["why_it_works"] and d["real_world_tip"]
            assert "-" in d["timestamp"]

    def test_fallback_debrief_success_fast(self):
        out = debrief_engine.build_fallback_debrief(
            script={"scam_type": "bank_kyc"},
            stage_timings=TIMINGS,
            user_action="identified_scam",
            reaction_time=1.5,
            caught=["hook"],
            missed=["authority", "isolation", "urgency", "payment"],
        )
        assert out["outcome"] in {"partial", "success"}
        assert "1.5" in out["reaction_assessment"]
        assert "fast" in out["reaction_assessment"].lower()

    def test_generate_debrief_llm_merge(self):
        payload = json.dumps({
            "outcome": "success",
            "headline": "Lightning fast!",
            "reaction_assessment": "Great reflexes.",
            "stages_caught": [{
                "stage": "hook", "timestamp": "0:00-0:08",
                "what_happened": "used your name",
                "why_it_works": "compliance reflex",
                "real_world_tip": "verify identity first",
            }],
            "stages_missed": [
                {"stage": s, "timestamp": "x", "what_happened": "w",
                 "why_it_works": "y", "real_world_tip": "z"}
                for s in ["isolation", "urgency", "payment"]
            ],
            "key_lesson": "never share OTP",
            "real_world_action": "hang up and call 1930",
            "encouragement": "keep training",
        })
        with patch("app.clients.llm.chat_completion", return_value=payload):
            out = debrief_engine.generate_debrief(
                script={"scam_type": "bank_kyc", "stages": {}},
                stage_timings=TIMINGS,
                user_action="identified_scam",
                reaction_time=18.3,
                caught=["hook"],
                missed=["isolation", "urgency", "payment"],
                trigger_stage="authority",
                profile=build_profile(name="Priya Sharma"),
            )
        assert out["headline"] == "Lightning fast!"
        assert out["outcome"] == "success"
        assert len(out["stages_caught"]) == 1
        assert out["stages_caught"][0]["what_happened"] == "used your name"
        assert len(out["stages_missed"]) == 3

    def test_generate_debrief_llm_down_uses_fallback(self):
        with patch("app.clients.llm.chat_completion", side_effect=RuntimeError("down")):
            out = debrief_engine.generate_debrief(
                script={"scam_type": "fedex", "stages": {}},
                stage_timings=TIMINGS,
                user_action="identified_scam",
                reaction_time=12.0,
                caught=["hook", "authority"],
                missed=["isolation", "urgency", "payment"],
                trigger_stage="authority",
                profile=build_profile(name="Priya Sharma"),
            )
        assert len(out["stages_caught"]) == 2
        assert out["key_lesson"]


# ---------------------------------------------------------------------------
# 3.6 resilience_score
# ---------------------------------------------------------------------------

class TestResilienceScore:
    @pytest.mark.parametrize("rt,bonus", [
        (3, 20), (7, 18), (12, 15), (17, 12), (25, 8), (40, 5), (50, 2), (75, 0),
    ])
    def test_speed_bonus_table(self, rt, bonus):
        assert resilience_score.speed_bonus(rt) == bonus

    def test_identified_fast_hard_difficulty(self):
        # 30 + 20 (speed) + 15 (3 stages) + 5 (hard) = 70
        score = resilience_score.calculate_drill_score("identified_scam", 4.0, 3, "hard")
        assert score == 70

    def test_guessing_penalty(self):
        with_guess = resilience_score.calculate_drill_score("identified_scam", 1.0, 1, "medium")
        # 30 + 20 + 5 + 2 - 5 = 52
        assert with_guess == 52

    def test_fell_for_it_and_no_response_clamp_to_zero(self):
        assert resilience_score.calculate_drill_score("fell_for_it", 60.0, 0, "medium") == 0
        assert resilience_score.calculate_drill_score("no_response", 0.0, 0, "medium") == 0

    def test_labels(self):
        assert resilience_score.label_for(15) == "Beginner"
        assert resilience_score.label_for(35) == "Vulnerable"
        assert resilience_score.label_for(50) == "Cautious"
        assert resilience_score.label_for(70) == "Resilient"
        assert resilience_score.label_for(95) == "Scam-Proof"

    def test_first_drill_baseline(self):
        out = resilience_score.update_resilience([], {
            "user_action": "identified_scam",
            "reaction_time_seconds": 18.3,
            "scam_type": "bank_kyc",
            "difficulty": "medium",
            "stages_caught": ["hook", "authority"],
        })
        assert out["score_before"] == 0
        assert out["score_after"] == out["drill_score"]
        assert out["drills_completed"] == 1
        assert out["entry"]["drill_number"] == 1

    def test_second_drill_weighted(self):
        first = _history_entry(drill_score=40, resilience_score=40, scam_type="bank_kyc")
        out = resilience_score.update_resilience([first], {
            "user_action": "identified_scam",
            "reaction_time_seconds": 10.0,
            "scam_type": "fedex",
            "difficulty": "medium",
            "stages_caught": ["hook", "authority", "isolation"],
        })
        # expected raw = 65*0.6 + 40*0.4 = 55 (see calculate below)
        expected_drill = resilience_score.calculate_drill_score(
            "identified_scam", 10.0, 3, "medium"
        )
        expected = round(expected_drill * 0.6 + 40 * 0.4)
        assert out["drill_score"] == expected_drill
        assert out["score_after"] == expected

    def test_cap_at_100(self):
        history = [
            _history_entry(drill_score=80, resilience_score=80, scam_type="bank_kyc")
            for _ in range(4)
        ]
        out = resilience_score.update_resilience(history, {
            "user_action": "identified_scam",
            "reaction_time_seconds": 3.0,
            "scam_type": "fedex",
            "difficulty": "hard",
            "stages_caught": list(script_generator.STAGES),
        })
        assert out["score_after"] <= 100

    def test_same_type_diminishing_returns(self):
        history = [
            _history_entry(drill_score=30, resilience_score=30, scam_type="bank_kyc",
                           date="2026-10-08T00:00:00+00:00"),
            _history_entry(drill_score=40, resilience_score=35, scam_type="bank_kyc",
                           date="2026-10-08T01:00:00+00:00"),
        ]
        out = resilience_score.update_resilience(history, {
            "user_action": "identified_scam",
            "reaction_time_seconds": 8.0,
            "scam_type": "bank_kyc",
            "difficulty": "medium",
            "stages_caught": ["hook", "authority", "urgency"],
            "date": "2026-10-08T02:00:00+00:00",
        })
        # full raw gain halved from the 3rd same-type drill
        raw = (out["drill_score"] * 0.4 + 40 * 0.3 + 30 * 0.2) / 0.9
        expected = 35 + round((round(raw) - 35) * 0.5)
        assert out["score_after"] == expected

    def test_inactivity_decay(self):
        history = [_history_entry(drill_score=60, resilience_score=60,
                                  scam_type="fedex", date="2026-09-15T00:00:00+00:00")]
        out = resilience_score.update_resilience(history, {
            "user_action": "identified_scam",
            "reaction_time_seconds": 12.0,
            "scam_type": "bank_kyc",
            "difficulty": "medium",
            "stages_caught": ["hook", "authority"],
            "date": "2026-10-09T00:00:00+00:00",
        })
        raw = round(out["drill_score"] * 0.6 + 60 * 0.4)
        # ~24 days inactive -> 3 weeks * 2 points
        assert out["score_after"] == max(0, raw - 6)

    def test_weakest_scam_type(self):
        history = [
            _history_entry(drill_score=70, resilience_score=70, scam_type="bank_kyc"),
            _history_entry(drill_score=25, resilience_score=60, scam_type="fedex"),
        ]
        out = resilience_score.update_resilience(history, {
            "user_action": "fell_for_it",
            "reaction_time_seconds": 60.0,
            "scam_type": "fedex",
            "difficulty": "hard",
            "stages_caught": [],
        })
        assert out["weakest_scam_type"] == "fedex"
        assert out["best_reaction_time"] == 20.0  # from the two history drills


def _history_entry(
    drill_score,
    resilience_score,
    scam_type,
    date=None,
):
    date = date or datetime.now(timezone.utc).isoformat()
    return {
        "drill_score": drill_score,
        "resilience_score": resilience_score,
        "score_after": resilience_score,
        "scam_type": scam_type,
        "reaction_time_seconds": 20.0,
        "user_action": "identified_scam",
        "date": date,
        "created_at": date,
    }


# ---------------------------------------------------------------------------
# router end-to-end
# ---------------------------------------------------------------------------

@pytest.fixture()
def client(_clean_store):
    """Fresh app so the /media/drill mount points at this test's tmp dir."""
    from fastapi.testclient import TestClient

    from app.main import create_app

    with TestClient(create_app()) as c:
        yield c


def _make_profile(client, **overrides):
    payload = {"name": "Priya Sharma", "city": "Mumbai", "bank": "HDFC", "language": "en"}
    payload.update(overrides)
    resp = client.post("/drill/profile", json=payload)
    assert resp.status_code == 200, resp.text
    return resp.json()


def _wav_bytes(seconds: float = 6.0, rate: int = 8000) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\x00\x00" * int(rate * seconds))
    return buf.getvalue()


class TestDrillRouter:
    def test_profile_endpoint(self, client):
        out = _make_profile(client)
        assert out["first_name"] == "Priya"
        assert out["bank_full_name"] == "HDFC Bank"
        assert out["status"] == "saved"

    def test_scam_types_endpoint(self, client):
        out = client.get("/drill/scam-types").json()
        assert len(out["scam_types"]) == 5
        assert {t["id"] for t in out["scam_types"]} == set(FALLBACK_SCRIPTS)
        # setup screen shows the estimate before the drill starts
        for t in out["scam_types"]:
            assert 30 <= t["estimated_duration_seconds"] <= 180

    def test_upload_voice_valid(self, client):
        profile = _make_profile(client)
        resp = client.post(
            "/drill/upload-voice",
            data={"profile_id": profile["profile_id"]},
            files={"file": ("clip.wav", _wav_bytes(6.0), "audio/wav")},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["status"] == "ready"
        assert body["duration_seconds"] == pytest.approx(6.0, abs=0.1)
        assert body["voice_clip_url"].startswith("/media/drill/voice/")
        # file actually served by the static mount
        assert client.get(body["voice_clip_url"]).status_code == 200

    def test_upload_voice_too_short(self, client):
        profile = _make_profile(client)
        resp = client.post(
            "/drill/upload-voice",
            data={"profile_id": profile["profile_id"]},
            files={"file": ("clip.wav", _wav_bytes(2.0), "audio/wav")},
        )
        assert resp.status_code == 422
        assert "too short" in resp.json()["detail"]

    def test_upload_voice_bad_format(self, client):
        profile = _make_profile(client)
        resp = client.post(
            "/drill/upload-voice",
            data={"profile_id": profile["profile_id"]},
            files={"file": ("clip.exe", b"zzz", "application/octet-stream")},
        )
        assert resp.status_code == 422

    def test_generate_script_unknown_profile(self, client):
        resp = client.post("/drill/generate-script",
                           json={"profile_id": "nope", "scam_type": "bank_kyc"})
        assert resp.status_code == 404

    def test_full_drill_flow(self, client):
        """profile -> script (template) -> synthesize -> respond -> score."""
        profile = _make_profile(client)

        # script (LLM down -> template)
        with patch("app.clients.llm.chat_completion", side_effect=RuntimeError("no key")):
            resp = client.post("/drill/generate-script", json={
                "profile_id": profile["profile_id"],
                "scam_type": "bank_kyc",
                "difficulty": "medium",
            })
        assert resp.status_code == 200, resp.text
        script = resp.json()
        assert script["source"] == "template"
        assert len(script["stages"]) == 5
        assert script["stages"][0]["stage"] == "hook"
        assert script["title"]
        assert script["estimated_duration_seconds"] > 30

        # synthesize (edge-tts stubbed: 1s per stage)
        async def fake_stream(text, voice):
            return b"\xff\xfb" + b"\x00" * 5998

        with patch.object(voice_synthesizer, "_stream_segment", fake_stream):
            resp = client.post("/drill/synthesize-voice",
                               json={"script_id": script["script_id"], "method": "auto"})
        assert resp.status_code == 200, resp.text
        synth = resp.json()
        assert synth["status"] == "ready"
        assert synth["duration_seconds"] == 5.0
        assert client.get(synth["audio_url"]).status_code == 200

        # respond — clicked at 1.5s (inside authority since stages are 1s each)
        with patch("app.clients.llm.chat_completion", side_effect=RuntimeError("no key")):
            resp = client.post("/drill/respond", json={
                "script_id": script["script_id"],
                "user_action": "identified_scam",
                "reaction_time_seconds": 1.5,
                "audio_position_seconds": 1.5,
            })
        assert resp.status_code == 200, resp.text
        result = resp.json()
        assert result["stages_caught"] == ["hook"]
        assert result["trigger_stage"] == "authority"
        assert result["stages_missed"] == ["isolation", "urgency", "payment"]
        assert result["score_before"] == 0
        assert result["score_after"] > 0
        assert result["drill_score"] > 0
        assert result["debrief"]["stages_caught"][0]["why_it_works"]
        assert result["debrief"]["stages_missed"]

        # score
        resp = client.get(f"/drill/score/{profile['user_id']}")
        assert resp.status_code == 200
        score = resp.json()
        assert score["drills_completed"] == 1
        assert score["current_score"] == result["score_after"]
        assert score["label"] == result["label"]
        assert len(score["history"]) == 1
        assert score["history"][0]["scam_type"] == "bank_kyc"

    def test_respond_fell_for_it(self, client):
        profile = _make_profile(client)
        with patch("app.clients.llm.chat_completion", side_effect=RuntimeError("no key")):
            script = client.post("/drill/generate-script", json={
                "profile_id": profile["profile_id"],
                "scam_type": "fedex",
                "difficulty": "hard",
            }).json()
            resp = client.post("/drill/respond", json={
                "script_id": script["script_id"],
                "user_action": "fell_for_it",
                "reaction_time_seconds": 61.0,
                "audio_position_seconds": 61.0,
            })
        assert resp.status_code == 200, resp.text
        out = resp.json()
        assert out["stages_caught"] == []
        assert out["stages_missed"] == script_generator.STAGES
        assert out["debrief"]["outcome"] == "failed"
        assert out["drill_score"] == 0
        assert out["score_after"] == 0

    def test_respond_unknown_script(self, client):
        resp = client.post("/drill/respond", json={"script_id": "nope"})
        assert resp.status_code == 404

    def test_empty_score(self, client):
        resp = client.get("/drill/score/never-seen")
        assert resp.status_code == 200
        body = resp.json()
        assert body["drills_completed"] == 0
        assert body["current_score"] == 0
        assert body["history"] == []
