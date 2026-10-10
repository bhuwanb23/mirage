"""Scam Stage Tracker (Phase 4.2).

Analyzes the rolling transcript of a live call in real time and classifies it
into the 5-stage scam pipeline:

    none → hook → authority → isolation → urgency → payment

Design:
  * Hybrid classification — rule-based keyword scoring every chunk, LLM
    classification every `llm_every`-th chunk (default 3rd, ~12 s) when an
    LLM provider is reachable. Any LLM failure silently degrades to rules.
  * Forward-only state machine — stages never regress; once a scam stage is
    detected the tracker stays in alert mode even if the caller goes quiet.
  * Confidence accumulation — +0.05 per confirming chunk (cap 0.95),
    −0.10 per contradicting chunk, −0.02 decay when no signal fires.
  * Alert thresholds per plan §4.2 (safe / suspicious / warning / critical),
    with an optional voice-synthetic override for the double alert.

Run:  uv run pytest tests/test_stage_tracker.py -q
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Optional

from app.models.schemas import AlertLevel, ScamStage

logger = logging.getLogger("mirage.stage_tracker")

# Ordered pipeline — index math depends on this exact order.
STAGE_ORDER: list[str] = [
    ScamStage.NONE.value,
    ScamStage.HOOK.value,
    ScamStage.AUTHORITY.value,
    ScamStage.ISOLATION.value,
    ScamStage.URGENCY.value,
    ScamStage.PAYMENT.value,
]


def stage_rank(stage: str) -> int:
    """Numeric rank of a stage (none=0 … payment=5). Unknown → 0."""
    try:
        return STAGE_ORDER.index(stage)
    except ValueError:
        return 0


# ---------------------------------------------------------------------------
# Rule-based keywords (English + Hinglish)
# ---------------------------------------------------------------------------
STAGE_KEYWORDS: dict[str, list[str]] = {
    "hook": [
        "selected", "won", "winner", "congratulations", "important",
        "regarding your account", "calling from", "hello", "is this",
        "good news", "exclusive offer", "kyc", "last warning",
    ],
    "authority": [
        "bank", "rbi", "police", "cbi", "officer", "department", "fraud",
        "investigation", "circular", "sbi", "hdfc", "icici", "customs",
        "passport office", "cyber cell", "kyc team", "verification team",
        "badge number", "agent id", "verify department",
    ],
    "isolation": [
        "don't tell", "do not tell", "dont tell", "confidential", "secret",
        "don't disconnect", "dont disconnect", "don't hang up", "dont hang up",
        "don't check", "dont check", "keep this between", "between us",
        "not even your", "stay on the call", "don't inform", "dont inform",
        "this is confidential", "do not share",
    ],
    "urgency": [
        "immediately", "within", "minutes", "blocked", "frozen", "suspended",
        "arrest", "last chance", "deadline", "right now", "act now",
        "within 30 minutes", "tonight", "final notice", "expire", "expired",
        "terminate", "legal action", "warrant", "verify now", "turant",
        "fauran", "jaldi", "band", "khatra", "last date",
    ],
    "payment": [
        "otp", "pin", "atm", "transfer", "upi", "pay", "amount", "rupees",
        "rs.", "qr code", "scan", "account number", "ifsc", "wire",
        "crypto", "wallet", "gift card", "google pay", "gpay", "phonepe",
        "paytm", "send money", "deposit", "bail money", "fee", "otp bataiye",
        "share the otp", "card details", "cvv",
    ],
}

# Keywords that alone justify a hook-stage hit (hello alone is too weak).
_WEAK_HOOK = {"hello", "is this", "calling from"}

# Scam-keyword highlight list for the transcript UI (shared via constant).
SCAM_HIGHLIGHT_WORDS: list[str] = [
    "otp", "pin", "transfer", "blocked", "immediately", "urgent",
    "qr code", "rupees", "upi", "suspend", "freeze", "deadline",
]

_SYSTEM_PROMPT = """You are a real-time scam call stage classifier for Mirage Guardian.

Your job: analyze the transcript of an ongoing phone call and determine
which stage of a scam the caller is currently in.

THE 5 SCAM STAGES (in order):
1. HOOK — Initial contact, grabbing attention, establishing familiarity
2. AUTHORITY — Impersonating an institution (bank, police, RBI, customs)
3. ISOLATION — Telling the victim not to tell anyone, not to hang up
4. URGENCY — Creating time pressure, threatening consequences
5. PAYMENT — Demanding money, OTP, PIN, UPI transfer, or sensitive info

RULES:
1. A call may be LEGITIMATE. If the conversation sounds normal (customer
   service, family chat, business call), return stage "none".
2. Stages typically progress in order (1→2→3→4→5), but scammers may skip
   stages or jump around.
3. A single chunk may contain signals of multiple stages. Return the
   HIGHEST stage detected.
4. Be conservative in early stages. Don't flag "hook" just because someone
   says "hello." Only flag when there's a clear scam pattern.
5. Once you detect stage 4 (urgency) or 5 (payment), confidence should be
   high — these are the most definitive signals.
6. Consider the FULL transcript context, not just the latest chunk. A
   single sentence might seem innocent but becomes suspicious in context.

OUTPUT FORMAT — valid JSON only:
{
  "current_stage": "none" | "hook" | "authority" | "isolation" | "urgency" | "payment",
  "confidence": 0.0,
  "signals": ["specific phrases or patterns that triggered this classification"],
  "alert_level": "safe" | "suspicious" | "warning" | "critical",
  "alert_message": "Human-readable alert for the user, or null if safe",
  "is_scam_likely": false
}"""


# ---------------------------------------------------------------------------
# Data contracts
# ---------------------------------------------------------------------------
@dataclass
class StageClassification:
    """Result of classifying one chunk (LLM or rules)."""

    stage: str = ScamStage.NONE.value
    confidence: float = 0.0
    signals: list[str] = field(default_factory=list)
    is_scam_likely: bool = False
    source: str = "rules"  # "llm" | "rules"


@dataclass
class StageUpdate:
    """Payload sent to the frontend after each processed chunk."""

    current_stage: str = ScamStage.NONE.value
    previous_stage: str = ScamStage.NONE.value
    confidence: float = 0.0
    alert_level: str = AlertLevel.SAFE.value
    alert_message: Optional[str] = None
    signals: list[str] = field(default_factory=list)
    transcript_so_far: str = ""
    call_duration_seconds: float = 0.0
    stage_timestamps: dict[str, Optional[float]] = field(default_factory=dict)
    is_scam_likely: bool = False
    classification_source: str = "rules"

    def to_payload(self) -> dict[str, Any]:
        return {
            "type": "stage_update",
            "current_stage": self.current_stage,
            "previous_stage": self.previous_stage,
            "confidence": round(self.confidence, 3),
            "alert_level": self.alert_level,
            "alert_message": self.alert_message,
            "signals": self.signals,
            "transcript_so_far": self.transcript_so_far,
            "call_duration_seconds": round(self.call_duration_seconds, 1),
            "stage_timestamps": self.stage_timestamps,
            "is_scam_likely": self.is_scam_likely,
            "classification_source": self.classification_source,
        }


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------
def classify_rules(text: str) -> StageClassification:
    """Keyword-count classifier. Fast (<1 ms), no external deps.

    Returns the highest-scoring stage; `none` when nothing matches.
    """
    if not text or not text.strip():
        return StageClassification(stage=ScamStage.NONE.value, confidence=0.0, source="rules")

    lowered = text.lower()
    best_stage = ScamStage.NONE.value
    best_rank = 0
    best_hits: list[str] = []
    best_conf = 0.0

    for stage, keywords in STAGE_KEYWORDS.items():
        hits = [kw for kw in keywords if kw in lowered]
        if stage == "hook":
            # "hello" alone must not trigger a hook classification.
            strong = [h for h in hits if h not in _WEAK_HOOK]
            if not strong and len(hits) < 3:
                hits = []
        if not hits:
            continue
        # Confidence: 1 hit = 0.50, +0.15 per extra hit, capped at 0.95.
        # Rounded so comparisons like `>= 0.65` are exact (0.35+0.15*2 is
        # 0.6499999999999999 in IEEE floats).
        conf = round(min(0.95, 0.35 + 0.15 * len(hits)), 3)
        rank = stage_rank(stage)
        # Highest stage wins ties; same stage keeps the richer signal list.
        if rank > best_rank or (rank == best_rank and len(hits) > len(best_hits)):
            best_stage, best_rank, best_hits, best_conf = stage, rank, hits, conf

    if best_rank == 0:
        return StageClassification(stage=ScamStage.NONE.value, confidence=0.0, source="rules")

    signals = [f"Said '{h}'" for h in best_hits[:5]]
    return StageClassification(
        stage=best_stage,
        confidence=best_conf,
        signals=signals,
        is_scam_likely=best_rank >= stage_rank(ScamStage.URGENCY.value),
        source="rules",
    )


def _extract_json(raw: str) -> dict:
    """Parse LLM output into a dict, tolerating code fences and prose."""
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-zA-Z]*\n?|\n?```$", "", raw).strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        start, end = raw.find("{"), raw.rfind("}")
        if start != -1 and end > start:
            return json.loads(raw[start : end + 1])
        raise


def classify_llm(transcript: str, latest_chunk: str, elapsed_seconds: float) -> StageClassification:
    """LLM classification via app.clients.llm (Groq → Gemini → Ollama).

    Raises on provider failure — callers degrade to rules.
    """
    from app.clients.llm import chat_completion

    user_prompt = (
        f'FULL TRANSCRIPT SO FAR:\n"{transcript}"\n\n'
        f'LATEST CHUNK (most recent seconds):\n"{latest_chunk}"\n\n'
        f"CALL DURATION: {int(elapsed_seconds)} seconds\n\n"
        "Classify the current stage."
    )
    raw = chat_completion(
        [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        json_mode=True,
        temperature=0.1,
        timeout=15.0,
    )
    data = _extract_json(raw)

    stage = str(data.get("current_stage", "none")).lower().strip()
    if stage not in STAGE_ORDER:
        stage = ScamStage.NONE.value
    confidence = float(data.get("confidence", 0.0) or 0.0)
    confidence = max(0.0, min(1.0, confidence))
    signals = [str(s) for s in (data.get("signals") or [])][:6]

    # Cross-check against our own keyword pass — never *lower* the stage if
    # the rule engine sees a clearly higher one (protects against LLM laxity).
    rules = classify_rules(latest_chunk or transcript)
    if stage_rank(rules.stage) > stage_rank(stage) and rules.confidence >= 0.65:
        stage, confidence = rules.stage, max(confidence, rules.confidence)
        signals = list(dict.fromkeys(signals + rules.signals))

    # Urgency/payment in the FINAL stage always means "scam likely", even
    # if a small model downplayed it in prose.
    is_scam_likely = bool(data.get("is_scam_likely")) or (
        stage_rank(stage) >= stage_rank(ScamStage.URGENCY.value)
    )

    return StageClassification(
        stage=stage,
        confidence=confidence,
        signals=signals,
        is_scam_likely=is_scam_likely,
        source="llm",
    )


# ---------------------------------------------------------------------------
# Alert decision
# ---------------------------------------------------------------------------
def decide_alert(
    stage: str,
    confidence: float,
    voice_synthetic: float = 0.0,
) -> tuple[str, Optional[str]]:
    """Map (stage, confidence, voice score) → (alert_level, message)."""
    # Double alert: scam stage + likely-AI voice.
    if stage_rank(stage) >= stage_rank(ScamStage.URGENCY.value) and voice_synthetic > 0.6:
        return (
            AlertLevel.CRITICAL.value,
            "🚨🚨 CONFIRMED SCAM — AI voice clone + scam demand detected. HANG UP NOW.",
        )
    if stage == ScamStage.PAYMENT.value and confidence > 0.5:
        return (
            AlertLevel.CRITICAL.value,
            "🚨 HANG UP NOW — payment demand detected. Never share OTP, PIN or UPI.",
        )
    if stage == ScamStage.URGENCY.value and confidence > 0.6:
        return (
            AlertLevel.WARNING.value,
            "⚠️ SCAM LIKELY — the caller is creating false urgency. "
            "Real institutions don't threaten deadlines on the phone.",
        )
    if stage in (ScamStage.ISOLATION.value, ScamStage.AUTHORITY.value) and confidence > 0.5:
        if stage == ScamStage.ISOLATION.value:
            return (
                AlertLevel.SUSPICIOUS.value,
                "Caller is asking you to keep this secret — a classic scam sign.",
            )
        return (
            AlertLevel.SUSPICIOUS.value,
            "Caller is claiming to be from an institution. Verify independently.",
        )
    return AlertLevel.SAFE.value, None


_LEVEL_RANK = {
    AlertLevel.SAFE.value: 0,
    AlertLevel.SUSPICIOUS.value: 1,
    AlertLevel.WARNING.value: 2,
    AlertLevel.CRITICAL.value: 3,
}


# ---------------------------------------------------------------------------
# State machine
# ---------------------------------------------------------------------------
class StageTracker:
    """Per-session forward-only stage state machine.

    Usage:
        tracker = StageTracker()
        update = tracker.process(chunk_text, elapsed_seconds)
        send(update.to_payload())
    """

    def __init__(
        self,
        llm_every: int = 3,
        llm_enabled: bool = True,
        confidence_floor: float = 0.2,
    ) -> None:
        self.current_stage: str = ScamStage.NONE.value
        self.confidence: float = 0.0
        self.alert_level: str = AlertLevel.SAFE.value
        self.alert_message: Optional[str] = None
        self.stage_timestamps: dict[str, Optional[float]] = {
            s: None for s in STAGE_ORDER
        }
        self.stage_timestamps[ScamStage.NONE.value] = 0.0
        self.signals: list[str] = []
        self.is_scam_likely: bool = False
        self.highest_stage: str = ScamStage.NONE.value
        self.classified_chunks: int = 0
        self.llm_chunks: int = 0

        self._llm_every = max(1, llm_every)
        self._llm_enabled = llm_enabled
        self._floor = confidence_floor
        self._scam_detected = False  # latch — never returns to safe

    # -- helpers ----------------------------------------------------------
    @property
    def stage_timestamp_map(self) -> dict[str, Optional[float]]:
        return dict(self.stage_timestamps)

    def _should_use_llm(self) -> bool:
        return self._llm_enabled and (self.classified_chunks % self._llm_every == 0)

    # -- classification ---------------------------------------------------
    def classify(self, chunk_text: str, transcript: str, elapsed: float) -> StageClassification:
        """Classify one chunk. LLM on cadence, rules otherwise; degrade on error."""
        use_llm = self._should_use_llm()
        if use_llm:
            try:
                result = classify_llm(transcript, chunk_text, elapsed)
                self.llm_chunks += 1
                return result
            except Exception as exc:  # noqa: BLE001 — degrade, never crash the call
                logger.warning("LLM classify failed, falling back to rules: %s", exc)
        return classify_rules(chunk_text or transcript)

    # -- state machine ----------------------------------------------------
    def _apply(self, classification: StageClassification, elapsed: float) -> tuple[str, str]:
        """Fold a classification into state. Returns (previous_stage, previous_alert)."""
        prev_stage = self.current_stage
        prev_alert = self.alert_level
        detected = classification.stage
        detected_rank = stage_rank(detected)
        current_rank = stage_rank(self.current_stage)

        if detected == ScamStage.NONE.value:
            # Never reset once a scam stage fired — small talk before the kill shot.
            if not self._scam_detected:
                self.confidence = max(0.0, self.confidence - 0.02)
        elif detected_rank > current_rank:
            # Forward transition (may skip stages).
            self.current_stage = detected
            self.confidence = max(classification.confidence, min(0.95, self.confidence + 0.10))
            if self.stage_timestamps.get(detected) is None:
                self.stage_timestamps[detected] = round(elapsed, 1)
            self._scam_detected = True
            self.signals = classification.signals
        elif detected_rank == current_rank:
            # Confirmation.
            self.confidence = min(0.95, self.confidence + 0.05)
            if classification.signals:
                self.signals = classification.signals
        else:
            # Lower-than-current detection: ignore for state, deduct confidence.
            if detected != ScamStage.NONE.value:
                self.confidence = max(self._floor, self.confidence - 0.10)
            else:
                self.confidence = max(self._floor, self.confidence - 0.02)

        if detected_rank > stage_rank(self.highest_stage):
            self.highest_stage = detected
        self.is_scam_likely = self.is_scam_likely or classification.is_scam_likely
        if self.current_stage != prev_stage and stage_rank(self.current_stage) > 0:
            self._scam_detected = True
        return prev_stage, prev_alert

    def _recompute_alert(self, voice_synthetic: float) -> None:
        level, message = decide_alert(self.current_stage, self.confidence, voice_synthetic)
        # Alerts are sticky within a session: never downgrade silently, only
        # upgrade — except when the user explicitly ends the session.
        if _LEVEL_RANK[level] >= _LEVEL_RANK[self.alert_level]:
            self.alert_level, self.alert_message = level, message
        elif self.alert_level == AlertLevel.CRITICAL.value and level == AlertLevel.SAFE.value:
            # Keep critical once earned.
            pass

    # -- public API -------------------------------------------------------
    def process(
        self,
        chunk_text: str,
        transcript: str,
        elapsed_seconds: float,
        voice_synthetic: float = 0.0,
        skip_classification: bool = False,
    ) -> StageUpdate:
        """Process one transcript chunk and produce a StageUpdate."""
        prev_stage = self.current_stage
        classification: Optional[StageClassification] = None

        if not skip_classification and (chunk_text or transcript).strip():
            classification = self.classify(chunk_text, transcript, elapsed_seconds)
            self.classified_chunks += 1
            self._apply(classification, elapsed_seconds)

        self._recompute_alert(voice_synthetic)

        return StageUpdate(
            current_stage=self.current_stage,
            previous_stage=prev_stage,
            confidence=self.confidence,
            alert_level=self.alert_level,
            alert_message=self.alert_message,
            signals=list(self.signals),
            transcript_so_far=transcript,
            call_duration_seconds=elapsed_seconds,
            stage_timestamps=self.stage_timestamp_map,
            is_scam_likely=self.is_scam_likely,
            classification_source=classification.source if classification else "none",
        )

    def summary(self, transcript: str, elapsed_seconds: float) -> dict[str, Any]:
        """Call summary shown when the user stops the Guardian."""
        verdict = (
            "Likely scam — hang up and report to 1930."
            if stage_rank(self.highest_stage) >= stage_rank(ScamStage.URGENCY.value)
            else "Suspicious call — verify independently before acting."
            if stage_rank(self.highest_stage) >= stage_rank(ScamStage.AUTHORITY.value)
            else "No strong scam signals detected."
        )
        return {
            "type": "summary",
            "duration_seconds": round(elapsed_seconds, 1),
            "highest_stage": self.highest_stage,
            "final_stage": self.current_stage,
            "peak_alert_level": self.alert_level,
            "confidence": round(self.confidence, 3),
            "is_scam_likely": self.is_scam_likely,
            "verdict": verdict,
            "chunks_classified": self.classified_chunks,
            "llm_classifications": self.llm_chunks,
            "transcript": transcript,
            "stage_timestamps": self.stage_timestamp_map,
        }


def new_tracker(llm_enabled: Optional[bool] = None) -> StageTracker:
    """Factory used by the WebSocket router (easy to monkeypatch in tests)."""
    if llm_enabled is None:
        from app.config import settings

        llm_enabled = bool(settings.available_llm_providers)
    return StageTracker(llm_enabled=llm_enabled)

