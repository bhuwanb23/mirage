"""Honeypot router — Phase 5.1 / 5.2 / 5.3.

Endpoints:
  POST /honeypot/start        -> first turn, creates a session
  POST /honeypot/continue     -> next turn in an existing session
  GET  /honeypot/session/{id} -> full conversation log + extracted IOCs
  GET  /honeypot/scripted     -> scripted demo exchange (Option A, plan §5.1)

Every turn runs the regex IOC extractor on the scammer's message, merges any
IOCs the agent claims to have spotted (validated), and ingests new IOCs into
the scam graph (plan §5.3 co-occurrence linking).

mode="simulate" skips the LLM entirely (deterministic persona) — used by the
scripted demo and by tests. mode="live" uses the LLM with rule fallback.

Run:  uv run uvicorn app.main:app --reload --port 8000
"""

from __future__ import annotations

import logging
import time
import uuid

from fastapi import APIRouter, HTTPException

from app.models.schemas import (
    HoneypotContinueRequest,
    HoneypotMessage,
    HoneypotSessionOut,
    HoneypotStartRequest,
    HoneypotTurnResponse,
    ThreatIOCs,
)
from app.services import honeypot_engine, ioc_extractor, scam_graph

logger = logging.getLogger("mirage.honeypot.api")

router = APIRouter(prefix="/honeypot", tags=["honeypot"])

# In-process session store (same pattern as guardian.ACTIVE_SESSIONS).
SESSIONS: dict[str, dict] = {}

PERSONA_NAMES = {"ramesh": "Ramesh", "sunita": "Sunita", "vikram": "Vikram", "meena": "Meena"}


class _Session:
    def __init__(self, persona: str, mode: str):
        self.session_id = f"hp-{uuid.uuid4().hex[:12]}"
        self.persona = persona if persona in honeypot_engine.PERSONAS else "ramesh"
        self.mode = mode if mode in ("live", "simulate") else "live"
        self.health = "engaged"
        self.messages: list[dict] = []  # {role, text, tactic?, health?}
        self.iocs = ThreatIOCs()
        self.time_wasted = 0
        self.created_at = time.time()

    @property
    def scammer_turns(self) -> int:
        return sum(1 for m in self.messages if m["role"] == "scammer")


def _plain_iocs(iocs: ThreatIOCs) -> dict[str, list[str]]:
    return ioc_extractor.iocs_as_plain_dict(iocs)


def _process_turn(session: _Session, scammer_message: str, mode: str) -> HoneypotTurnResponse:
    """One iteration of the agent loop (plan §5.1): extract, reply, ingest."""
    # 1. Record the scammer's message + regex IOC extraction (every message).
    session.messages.append({"role": "scammer", "text": scammer_message})
    regex_iocs = ioc_extractor.extract_iocs(scammer_message)
    session.iocs = ioc_extractor.merge_iocs(session.iocs, regex_iocs)

    # 2. Persona reply (LLM in live mode, deterministic in simulate / on failure).
    turn = honeypot_engine.generate_turn(
        session.persona,
        scammer_message,
        session.messages,
        session.iocs,
        simulate=(mode == "simulate"),
    )

    # 3. Validate + merge any IOCs the agent claims to have spotted.
    if turn.iocs_extracted.total() > 0 or turn.iocs_extracted.scammer_names:
        session.iocs = ioc_extractor.merge_iocs(session.iocs, turn.iocs_extracted)

    session.health = turn.conversation_health
    session.time_wasted += turn.estimated_time_wasted_seconds
    session.messages.append(
        {
            "role": session.persona,
            "text": turn.reply,
            "tactic": turn.tactic_used,
            "health": session.health,
        }
    )

    # 4. Graph ingestion on new IOCs only (plan §5.3).
    new_iocs = ioc_extractor.merge_iocs(regex_iocs, turn.iocs_extracted)
    if new_iocs.total() > 0 or new_iocs.scammer_names:
        try:
            scam_graph.get_store().ingest_iocs(
                session.session_id,
                new_iocs,
                source="honeypot",
                scam_type="unknown",
                confidence=0.7,
            )
        except Exception as exc:  # graph failure must not break the conversation
            logger.error("graph ingest failed: %s", exc)

    return HoneypotTurnResponse(
        session_id=session.session_id,
        reply=turn.reply,
        tactic_used=turn.tactic_used,
        iocs_extracted_this_turn=_plain_iocs(new_iocs),
        total_iocs_extracted=session.iocs.total(),
        conversation_health=session.health,
        messages_in_session=len(session.messages),
        estimated_time_wasted_seconds=session.time_wasted,
        mode=mode,
    )


@router.post("/start")
def start_session(req: HoneypotStartRequest) -> HoneypotTurnResponse:
    """First turn: create a honeypot session and reply to the scammer."""
    if not req.scammer_message.strip():
        raise HTTPException(status_code=422, detail="scammer_message is required")

    session = _Session(req.persona, req.mode)
    SESSIONS[session.session_id] = session
    logger.info("honeypot session %s started (persona=%s, mode=%s)",
                session.session_id, session.persona, session.mode)
    return _process_turn(session, req.scammer_message, session.mode)


@router.post("/continue")
def continue_session(req: HoneypotContinueRequest) -> HoneypotTurnResponse:
    """Next turn in an existing session."""
    session = SESSIONS.get(req.session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if not req.scammer_message.strip():
        raise HTTPException(status_code=422, detail="scammer_message is required")
    mode = req.mode or session.mode
    return _process_turn(session, req.scammer_message, mode)


@router.get("/session/{session_id}")
def get_session(session_id: str) -> HoneypotSessionOut:
    """Full conversation log + all extracted IOCs."""
    session = SESSIONS.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    persona_name = PERSONA_NAMES.get(session.persona, "Ramesh")
    return HoneypotSessionOut(
        session_id=session.session_id,
        persona=session.persona,
        mode=session.mode,
        conversation_health=session.health,
        messages=[
            HoneypotMessage(
                role=m["role"],
                text=m["text"],
                tactic=m.get("tactic"),
                health=m.get("health"),
            )
            for m in session.messages
        ],
        iocs=session.iocs,
        total_time_wasted_seconds=session.time_wasted,
    )


# ---------------------------------------------------------------------------
# Scripted demo (Option A, plan §5.1) — pre-written exchange the UI plays
# back with realistic pacing. IOCs are highlighted client-side from this list.
# ---------------------------------------------------------------------------

SCRIPTED_DEMO = [
    {"role": "scammer", "text": "Good afternoon, I am Officer Rajesh from the SBI Fraud Department. Your KYC is incomplete and your account will be blocked in 30 minutes."},
    {"role": "ramesh", "text": "Hello beta! Oh my god, my account? I just got my pension credited yesterday. Is the money safe? Please tell me what to do.", "tactic": "compliance"},
    {"role": "scammer", "text": "Your money is at risk. Transfer ₹50,000 to this safe UPI immediately: sbi-safe@ybl"},
    {"role": "ramesh", "text": "Okay beta, I'm writing it down. S-B-I dash safe at Y-B-L? Is that right? Or is it S-B-I underscore? My grandson told me about this UPI but I always forget the format. And how much did you say? 50,000 or 5,000?", "tactic": "mishearing"},
    {"role": "scammer", "text": "50,000! And call me on 9876543211 when done. Or WhatsApp me on 8765432109."},
    {"role": "ramesh", "text": "98765... sorry beta, the line is bad. 9876543211 or 9876543210? My hearing aid battery is low today. I will save your number properly.", "tactic": "mishearing"},
    {"role": "scammer", "text": "9876543211!! Also open this link and enter your details: https://sbi-kyc-verify.xyz/update"},
    {"role": "ramesh", "text": "The link is not opening beta, it shows a big picture of a lock. What does the website say? Is it like a barcode? Meanwhile my knees are giving me trouble, let me sit down. What do I do next?", "tactic": "app_failure"},
    {"role": "scammer", "text": "USELESS! Are you stupid? Just open the link! I am disconnecting and calling the next person."},
    {"role": "ramesh", "text": "No no, please don't go! I am trying, beta. Just tell me one more time. I have ₹2,00,000 in my account ready — I mean, for the transfer!", "tactic": "compliance"},
]

SCRIPTED_IOC_HIGHLIGHTS = {
    "sbi-safe@ybl": "UPI ID",
    "9876543211": "Phone",
    "8765432109": "Phone",
    "sbi-kyc-verify.xyz": "Domain",
}


@router.get("/scripted")
def scripted_demo() -> dict:
    """Pre-scripted demo exchange (plan §5.1 Option A)."""
    return {
        "messages": SCRIPTED_DEMO,
        "ioc_highlights": SCRIPTED_IOC_HIGHLIGHTS,
        "persona_name": "Ramesh",
    }
