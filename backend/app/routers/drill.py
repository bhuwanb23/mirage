"""Drill router — Phase 3 fire drill simulator.

Endpoints:
  POST /drill/profile           -> DrillProfileOut
  POST /drill/upload-voice      -> {voice_clip_url, duration_seconds, status}
  POST /drill/generate-script   -> DrillScriptOut
  POST /drill/synthesize-voice  -> DrillSynthesizeOut
  POST /drill/respond           -> DrillRespondOut   (score + debrief)
  GET  /drill/score/{user_id}   -> DrillScoreOut
  GET  /drill/scam-types        -> supported scam types for the setup screen

Everything is dev-safe without Supabase / LLM / network: each stage has a
template or deterministic fallback so a live demo never 500s.
"""

from __future__ import annotations

import logging
import time
import wave
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.config import settings
from app.models.schemas import (
    DebriefStageDetail,
    DrillDebrief,
    DrillProfileOut,
    DrillProfileRequest,
    DrillRespondOut,
    DrillRespondRequest,
    DrillScoreOut,
    DrillScriptOut,
    DrillScriptRequest,
    DrillStage,
    DrillSynthesizeOut,
    DrillSynthesizeRequest,
    ScoreHistoryEntry,
)
from app.services import debrief_engine, resilience_score, script_generator, voice_synthesizer
from app.services.drill_store import (
    get_history,
    get_profile,
    get_script,
    new_id,
    record_result,
    save_profile,
    save_script,
    set_score,
    update_profile,
    update_script,
)
from app.services.footprint_scraper import build_profile

logger = logging.getLogger("mirage.drill")

router = APIRouter(tags=["drill"])

ALLOWED_AUDIO_EXT = {".wav", ".mp3", ".m4a", ".ogg"}
MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 MB
MIN_VOICE_SECONDS = 5.0
MAX_VOICE_SECONDS = 120.0

# mp3 bitrate guess for uploaded clips (unknown encoding) — 128 kbps
_UPLOAD_BYTES_PER_SECOND = 128_000 / 8


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# 3.1 profile
# ---------------------------------------------------------------------------

@router.post("/profile", response_model=DrillProfileOut)
def create_profile(req: DrillProfileRequest) -> DrillProfileOut:
    try:
        profile = build_profile(
            name=req.name,
            city=req.city,
            bank=req.bank,
            employer=req.employer,
            relative_name=req.relative_name,
            relative_relation=req.relative_relation,
            language=req.language,
            user_id=req.user_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    profile["created_at"] = _utc_now()
    save_profile(profile)
    return DrillProfileOut(
        profile_id=profile["profile_id"],
        user_id=profile["user_id"],
        name=profile["name"],
        first_name=profile["first_name"],
        city=profile["city"],
        bank=profile["bank"],
        bank_full_name=profile["bank_full_name"],
        employer=profile["employer"],
        relative_name=profile["relative_name"],
        relative_relation=profile["relative_relation"],
        language=profile["language"],
        voice_clip_url=profile.get("voice_clip_url"),
        voice_duration_seconds=float(profile.get("voice_duration_seconds") or 0.0),
        status="saved",
        message="Profile saved. Upload a voice clip to continue.",
    )


def _estimate_duration(path: Path) -> float:
    """Best-effort duration: exact for WAV (stdlib wave), estimated for MP3/etc."""
    if path.suffix.lower() == ".wav":
        try:
            with wave.open(str(path), "rb") as wav:
                rate = wav.getframerate() or 1
                return round(wav.getnframes() / rate, 2)
        except Exception:
            pass
    return round(path.stat().st_size / _UPLOAD_BYTES_PER_SECOND, 2)


@router.post("/upload-voice")
async def upload_voice(
    file: UploadFile = File(...),
    profile_id: str = Form(...),
) -> dict[str, Any]:
    profile = get_profile(profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Unknown profile_id. Create a profile first.")

    suffix = Path(file.filename or "clip.wav").suffix.lower()
    if suffix not in ALLOWED_AUDIO_EXT:
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported format {suffix}. Use .wav, .mp3, .m4a, or .ogg.",
        )
    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=422, detail="Voice clip too large (max 5 MB).")

    media_root = Path(settings.drill_media_dir) / "voice"
    media_root.mkdir(parents=True, exist_ok=True)
    filename = f"{profile_id}_{int(time.time())}{suffix}"
    path = media_root / filename
    path.write_bytes(data)

    duration = _estimate_duration(path)
    if duration < MIN_VOICE_SECONDS:
        path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=422,
            detail="Voice clip too short. Please record at least 5 seconds of clear speech.",
        )
    if duration > MAX_VOICE_SECONDS:
        path.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail="Voice clip too long (max 2 minutes).")

    update_profile(
        profile_id,
        voice_clip_path=str(path),
        voice_clip_url=f"/media/drill/voice/{filename}",
        voice_duration_seconds=duration,
    )
    return {
        "voice_clip_url": f"/media/drill/voice/{filename}",
        "duration_seconds": duration,
        "status": "ready",
        "message": "Voice clip saved.",
    }


# ---------------------------------------------------------------------------
# 3.2 script generation
# ---------------------------------------------------------------------------

def _timestamp_hint(start: float, end: float) -> str:
    def fmt(s: float) -> str:
        s = max(int(round(s)), 0)
        return f"{s // 60}:{s % 60:02d}"

    return f"{fmt(start)}-{fmt(end)}"


@router.post("/generate-script", response_model=DrillScriptOut)
def generate_script(req: DrillScriptRequest) -> DrillScriptOut:
    profile = get_profile(req.profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Unknown profile_id. Create a profile first.")

    start = time.perf_counter()
    result = script_generator.generate_script(profile, req.scam_type, req.difficulty)
    latency_ms = (time.perf_counter() - start) * 1000
    logger.info(
        "script generated",
        extra={
            "source": result.get("source"),
            "scam_type": result.get("scam_type"),
            "latency_ms": round(latency_ms, 1),
        },
    )

    duration = float(result.get("estimated_duration_seconds") or 60.0)
    timings = voice_synthesizer._fallback_stage_timings(result.get("stages", {}), result)

    script_id = result["script_id"]
    record = {
        "script_id": script_id,
        "profile_id": req.profile_id,
        "scam_type": result["scam_type"],
        "title": result["title"],
        "full_script": result["full_script"],
        "stages": result["stages"],
        "red_flags_planted": result.get("red_flags_planted", []),
        "difficulty_level": result.get("difficulty_level", req.difficulty),
        "estimated_duration_seconds": duration,
        "language": result.get("language", profile.get("language", "en")),
        "source": result.get("source", "template"),
        "audio_url": None,
        "duration_seconds": None,
        "stage_timings": timings,
        "created_at": _utc_now(),
    }
    save_script(record)

    stages = [
        DrillStage(
            stage=stage_name,
            order=i + 1,
            timestamp_hint=_timestamp_hint(
                timings[stage_name]["start"], timings[stage_name]["end"]
            ),
            start_seconds=timings[stage_name]["start"],
            end_seconds=timings[stage_name]["end"],
            script=record["stages"][stage_name]["script"],
            tactic=record["stages"][stage_name].get("tactic", ""),
        )
        for i, stage_name in enumerate(script_generator.STAGES)
        if stage_name in record["stages"]
    ]
    return DrillScriptOut(
        script_id=script_id,
        profile_id=req.profile_id,
        scam_type=record["scam_type"],
        title=record["title"],
        full_script=record["full_script"],
        stages=stages,
        red_flags_planted=record["red_flags_planted"],
        difficulty_level=record["difficulty_level"],
        estimated_duration_seconds=duration,
        language=record["language"],
        source=record["source"],
    )


# ---------------------------------------------------------------------------
# 3.3 voice synthesis
# ---------------------------------------------------------------------------

@router.post("/synthesize-voice", response_model=DrillSynthesizeOut)
def synthesize_voice(req: DrillSynthesizeRequest) -> DrillSynthesizeOut:
    script = get_script(req.script_id)
    if script is None:
        raise HTTPException(status_code=404, detail="Unknown script_id.")
    profile = get_profile(script.get("profile_id", "")) or {}

    start = time.perf_counter()
    result = voice_synthesizer.synthesize_script(script, profile, method=req.method)
    latency_ms = (time.perf_counter() - start) * 1000
    logger.info(
        "voice synthesized",
        extra={
            "script_id": req.script_id,
            "method": result.get("method_used"),
            "latency_ms": round(latency_ms, 1),
        },
    )

    if result["status"] == "ready":
        updates: dict[str, Any] = {
            "audio_url": result["audio_url"],
            "duration_seconds": result["duration_seconds"],
            "stage_timings": result["stage_timings"],
        }
        if result["duration_seconds"]:
            # re-stamp hints on exact timings so the debrief quotes real moments
            updates["timestamp_hints"] = {
                s: _timestamp_hint(t["start"], t["end"])
                for s, t in result["stage_timings"].items()
            }
        update_script(req.script_id, **updates)

    return DrillSynthesizeOut(
        script_id=req.script_id,
        audio_url=result.get("audio_url"),
        duration_seconds=float(result.get("duration_seconds") or 0.0),
        method_used=result.get("method_used", "edge-tts"),
        status=result.get("status", "failed"),
        message=result.get("message", ""),
    )


# ---------------------------------------------------------------------------
# 3.4/3.5 respond -> score + debrief
# ---------------------------------------------------------------------------

@router.post("/respond", response_model=DrillRespondOut)
def respond(req: DrillRespondRequest) -> DrillRespondOut:
    script = get_script(req.script_id)
    if script is None:
        raise HTTPException(status_code=404, detail="Unknown script_id.")
    profile = get_profile(script.get("profile_id", "")) or {}
    user_id = profile.get("user_id") or "anonymous"
    history = get_history(user_id)

    timings = script.get("stage_timings") or voice_synthesizer._fallback_stage_timings(
        script.get("stages", {}), script
    )
    caught, missed, trigger = debrief_engine.classify_stages(
        timings, req.user_action, req.audio_position_seconds
    )

    drill_result = {
        "user_action": req.user_action,
        "reaction_time_seconds": req.reaction_time_seconds,
        "scam_type": script.get("scam_type", "unknown"),
        "difficulty": script.get("difficulty_level", "medium"),
        "stages_caught": caught,
        "date": _utc_now(),
    }
    score = resilience_score.update_resilience(history, drill_result)

    attempt_number = len(history) + 1
    debrief_raw = debrief_engine.generate_debrief(
        script=script,
        stage_timings=timings,
        user_action=req.user_action,
        reaction_time=req.reaction_time_seconds,
        caught=caught,
        missed=missed,
        trigger_stage=trigger,
        profile=profile,
        attempt_number=attempt_number,
    )

    drill_id = new_id()
    record = {
        "drill_id": drill_id,
        "script_id": req.script_id,
        "scam_type": script.get("scam_type", "unknown"),
        "user_action": req.user_action,
        "reaction_time_seconds": req.reaction_time_seconds,
        "audio_position_seconds": req.audio_position_seconds,
        "stages_caught": caught,
        "stages_missed": missed,
        "trigger_stage": trigger,
        "drill_score": score["drill_score"],
        "score_before": score["score_before"],
        "score_after": score["score_after"],
        "script_text": script.get("full_script", ""),
        "audio_url": script.get("audio_url"),
        "debrief_text": (
            f"{debrief_raw.get('headline', '')} {debrief_raw.get('key_lesson', '')}"
        ).strip(),
        "created_at": _utc_now(),
    }
    record_result(user_id, record)
    set_score(user_id, score["score_after"])

    debrief = DrillDebrief(
        outcome=debrief_raw.get("outcome", "partial"),
        headline=debrief_raw.get("headline", ""),
        reaction_assessment=debrief_raw.get("reaction_assessment", ""),
        stages_caught=[DebriefStageDetail(**d) for d in debrief_raw.get("stages_caught", [])],
        stages_missed=[DebriefStageDetail(**d) for d in debrief_raw.get("stages_missed", [])],
        key_lesson=debrief_raw.get("key_lesson", ""),
        real_world_action=debrief_raw.get("real_world_action", ""),
        encouragement=debrief_raw.get("encouragement", ""),
    )

    return DrillRespondOut(
        drill_id=drill_id,
        script_id=req.script_id,
        scam_type=script.get("scam_type", "unknown"),
        user_action=req.user_action,
        reaction_time_seconds=req.reaction_time_seconds,
        stages_caught=caught,
        stages_missed=missed,
        trigger_stage=trigger,
        drill_score=score["drill_score"],
        score_before=score["score_before"],
        score_after=score["score_after"],
        change=score["change"],
        label=score["label"],
        debrief=debrief,
    )


# ---------------------------------------------------------------------------
# 3.6 score
# ---------------------------------------------------------------------------

@router.get("/score/{user_id}", response_model=DrillScoreOut)
def get_score_endpoint(user_id: str) -> DrillScoreOut:
    history = get_history(user_id)
    if not history:
        return DrillScoreOut(
            user_id=user_id,
            current_score=0,
            previous_score=0,
            change=0,
            label=resilience_score.label_for(0),
            drills_completed=0,
            best_reaction_time=None,
            weakest_scam_type=None,
            history=[],
        )

    entries = [
        ScoreHistoryEntry(
            drill_number=i + 1,
            score=int(r.get("score_after", 0)),
            scam_type=r.get("scam_type", "unknown"),
            date=str(r.get("created_at", ""))[:10],
        )
        for i, r in enumerate(history)
    ]
    current = int(history[-1].get("score_after", 0))
    previous = int(history[-2].get("score_after", 0)) if len(history) > 1 else 0
    reactions = [
        float(r["reaction_time_seconds"])
        for r in history
        if r.get("user_action") == "identified_scam" and r.get("reaction_time_seconds") is not None
    ]
    weakest = resilience_score._weakest_scam_type(history)

    return DrillScoreOut(
        user_id=user_id,
        current_score=current,
        previous_score=previous,
        change=current - previous,
        label=resilience_score.label_for(current),
        drills_completed=len(history),
        best_reaction_time=min(reactions) if reactions else None,
        weakest_scam_type=weakest,
        history=entries,
    )


@router.get("/scam-types")
def scam_types() -> dict[str, Any]:
    """Scam types offered on the setup screen (difficulty + duration defaults)."""
    durations = script_generator.fallback_durations()
    return {
        "scam_types": [
            {
                "id": "bank_kyc",
                "label": "Bank KYC Fraud",
                "default_difficulty": "medium",
                "estimated_duration_seconds": durations.get("bank_kyc", 60.0),
            },
            {
                "id": "fedex",
                "label": "FedEx / Customs Parcel",
                "default_difficulty": "medium",
                "estimated_duration_seconds": durations.get("fedex", 60.0),
            },
            {
                "id": "relative_distress",
                "label": "Relative in Distress",
                "default_difficulty": "hard",
                "estimated_duration_seconds": durations.get("relative_distress", 60.0),
            },
            {
                "id": "rbi_police",
                "label": "RBI / Police Impersonation",
                "default_difficulty": "hard",
                "estimated_duration_seconds": durations.get("rbi_police", 60.0),
            },
            {
                "id": "job_offer",
                "label": "Job Offer / Work-from-Home",
                "default_difficulty": "easy",
                "estimated_duration_seconds": durations.get("job_offer", 60.0),
            },
        ]
    }
