"""Shared Pydantic contracts — defined once, used by API, bot, and frontend types."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


# ----------------------------------------------------------------------------
# Enums
# ----------------------------------------------------------------------------
class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ScamType(str, Enum):
    BANK_KYC = "bank_kyc"
    UPI_REVERSAL = "upi_reversal"
    FEDEX = "fedex"
    JOB_OFFER = "job_offer"
    LOTTERY = "lottery"
    RELATIVE_DISTRESS = "relative_distress"
    OTP_PHISHING = "otp_phishing"
    INVESTMENT = "investment"
    ROMANCE = "romance"
    ELECTRICITY = "electricity"
    IMPERSONATION = "impersonation"
    QR_CODE = "qr_code"
    UNKNOWN = "unknown"


class InputType(str, Enum):
    TEXT = "text"
    AUDIO = "audio"
    IMAGE = "image"
    URL = "url"


class EvidenceType(str, Enum):
    URL_ANALYSIS = "url_analysis"
    DOMAIN_AGE = "domain_age"
    LINGUISTIC = "linguistic"
    VOICE_SYNTHETIC = "voice_synthetic"
    VISUAL = "visual"


class ScamStage(str, Enum):
    NONE = "none"
    HOOK = "hook"
    AUTHORITY = "authority"
    ISOLATION = "isolation"
    URGENCY = "urgency"
    PAYMENT = "payment"


class AlertLevel(str, Enum):
    SAFE = "safe"
    SUSPICIOUS = "suspicious"
    WARNING = "warning"
    CRITICAL = "critical"


class VerdictSource(str, Enum):
    WEB = "web"
    TELEGRAM = "telegram"
    GUARDIAN = "guardian"
    DRILL = "drill"


# ----------------------------------------------------------------------------
# Evidence + Verdict (Phase 1 output)
# ----------------------------------------------------------------------------
class Evidence(BaseModel):
    type: EvidenceType | str
    detail: str
    severity: RiskLevel | str = RiskLevel.MEDIUM
    source: str = "unknown"


class ScamVerdict(BaseModel):
    is_scam: bool
    confidence: float = Field(ge=0.0, le=1.0)
    scam_type: Optional[str] = None
    risk_level: RiskLevel | str = RiskLevel.LOW
    red_flags: list[str] = []
    evidence: list[Evidence] = []
    stages_detected: list[str] = []
    summary: str = ""
    recommended_action: str = ""


# ----------------------------------------------------------------------------
# Fire Drill (Phase 3)
# ----------------------------------------------------------------------------
class DrillResult(BaseModel):
    drill_id: UUID = Field(default_factory=uuid4)
    user_id: Optional[UUID] = None
    scam_type: str
    script_text: str = ""
    audio_url: Optional[str] = None
    user_detected_scam: bool = False
    detection_time_seconds: int = 0
    stages_identified: list[str] = []
    stages_missed: list[str] = []
    score_before: int = 0
    score_after: int = 0
    debrief: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ----------------------------------------------------------------------------
# Live Guardian (Phase 4)
# ----------------------------------------------------------------------------
class CallStage(BaseModel):
    current_stage: ScamStage | str = ScamStage.NONE
    stage_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    alert_level: AlertLevel | str = AlertLevel.SAFE
    alert_message: Optional[str] = None
    transcript_so_far: str = ""
    synthetic_voice_score: float = Field(default=0.0, ge=0.0, le=1.0)
    timestamps: dict[str, str] = {}


# ----------------------------------------------------------------------------
# IOC extraction (Phase 5)
# ----------------------------------------------------------------------------
class DomainInfo(BaseModel):
    """Lean IOC domain record for Phase 5 graph ingestion."""
    domain: str
    age_days: Optional[int] = None
    registrar: Optional[str] = None
    is_suspicious: bool = False
    lookalike_target: Optional[str] = None
    similarity_score: float = 0.0


class URLAnalysisResult(BaseModel):
    """Per-URL analysis output from the Phase 1.2 URL analyzer."""
    url: str
    domain: str
    tld: str
    is_suspicious: bool = False
    risk_score: float = 0.0
    domain_age_days: Optional[int] = None
    registrar: Optional[str] = None
    https: bool = True
    is_lookalike: bool = False
    lookalike_target: Optional[str] = None
    contains_brand_keyword: bool = False
    brand_keyword: Optional[str] = None
    suspicious_tld: bool = False
    url_obfuscation: bool = False
    suspicious_path_keywords: list[str] = []
    red_flags: list[str] = []


class URLAnalysisOutput(BaseModel):
    """Top-level response for POST /analyze/url."""
    urls_analyzed: list[URLAnalysisResult] = []
    overall_risk_score: float = 0.0
    overall_is_suspicious: bool = False
    highest_risk_url: Optional[str] = None


class ImageAnalysisVerdict(BaseModel):
    """Unified verdict for POST /analyze/image."""
    verdict: ScamVerdict
    ocr_text: str = ""
    ocr_engine: str = "none"
    visual_analysis_app: str = "Unknown"
    visual_red_flags: list[str] = []
    confidence_boost: float = 0.0
    processing_time_ms: float = 0.0
    image_metadata: dict[str, Any] = {}


class TranscriptSegment(BaseModel):
    """A single segment from Whisper transcription."""
    start: float
    end: float
    text: str


class VoiceAnalysisVerdict(BaseModel):
    """Unified verdict for POST /analyze/voice."""
    verdict: ScamVerdict
    transcript: str = ""
    transcript_segments: list[TranscriptSegment] = []
    detected_language: str = ""
    synthetic_voice_score: float = 0.0
    voice_verdict: str = "unknown"
    audio_duration_seconds: float = 0.0
    confidence_boost: float = 0.0
    processing_time_ms: float = 0.0
    audio_metadata: dict[str, Any] = {}
    voice_model_available: bool = False
    whisper_available: bool = False


# Note: the Phase 0/2-era ThreatIOCs stub (str lists + DomainInfo) was removed
# in Phase 5 — ThreatIOCs below (IOCItem-based, with source + context) is the
# single IOC contract used by the extractor, honeypot, graph, and report.


# ----------------------------------------------------------------------------
# Requests
# ----------------------------------------------------------------------------
class AnalyzeRequest(BaseModel):
    text: Optional[str] = None
    url: Optional[str] = None
    input_type: InputType | str = InputType.TEXT


class MemorySecret(BaseModel):
    question: str
    answer_hash: str
    totp_code: Optional[str] = None


# --- Memory Handshake API (Phase 4.5) ------------------------------------
class FamilyGroupCreate(BaseModel):
    name: Optional[str] = "Family"
    user_id: Optional[UUID] = None


class FamilyGroupJoin(BaseModel):
    invite_code: str


class FamilyGroupOut(BaseModel):
    family_group_id: str
    invite_code: str


class MemoryQuestionIn(BaseModel):
    question: str
    answer: str


class MemorySetupRequest(BaseModel):
    family_group_id: str
    questions: list[MemoryQuestionIn]


class MemorySetupResponse(BaseModel):
    status: str = "saved"
    questions_count: int = 0
    totp_secret: str = ""
    message: str = ""


class MemoryVerifyRequest(BaseModel):
    family_group_id: str
    question_id: str
    answer: str


class TotpVerifyRequest(BaseModel):
    family_group_id: str
    code: str


class MemoryVerifyResponse(BaseModel):
    verified: bool
    message: str


class TOTPResponse(BaseModel):
    code: str
    expires_in_seconds: int
    interval: int


class ChallengeQuestion(BaseModel):
    question_id: str
    question: str


# ----------------------------------------------------------------------------
# Scammer Hunter (Phase 5)
# ----------------------------------------------------------------------------
class IOCItem(BaseModel):
    value: str
    source: str = "regex"  # regex | llm | agent | url_parse
    context: str = ""


class ThreatIOCs(BaseModel):
    phone_numbers: list[IOCItem] = []
    upi_ids: list[IOCItem] = []
    urls: list[IOCItem] = []
    domains: list[IOCItem] = []
    bank_accounts: list[IOCItem] = []
    ifsc_codes: list[IOCItem] = []
    bank_names: list[str] = []
    scammer_names: list[str] = []
    reference_numbers: list[str] = []
    amounts: list[str] = []
    locations: list[str] = []

    def total(self) -> int:
        return (
            len(self.phone_numbers)
            + len(self.upi_ids)
            + len(self.urls)
            + len(self.bank_accounts)
        )


class HoneypotStartRequest(BaseModel):
    scammer_message: str
    session_id: Optional[str] = None
    persona: str = "ramesh"
    mode: str = "live"  # live | simulate


class HoneypotContinueRequest(BaseModel):
    session_id: str
    scammer_message: str
    mode: Optional[str] = None  # inherit session default


class HoneypotTurnResponse(BaseModel):
    session_id: str
    reply: str
    tactic_used: str
    iocs_extracted_this_turn: dict[str, list[str]] = {}
    total_iocs_extracted: int = 0
    conversation_health: str = "engaged"
    messages_in_session: int = 0
    estimated_time_wasted_seconds: int = 0
    mode: str = "live"


class HoneypotMessage(BaseModel):
    role: str  # scammer | ramesh (persona)
    text: str
    tactic: Optional[str] = None
    health: Optional[str] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class HoneypotSessionOut(BaseModel):
    session_id: str
    persona: str
    mode: str
    conversation_health: str
    messages: list[HoneypotMessage] = []
    iocs: ThreatIOCs = Field(default_factory=ThreatIOCs)
    total_time_wasted_seconds: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class GraphNode(BaseModel):
    id: str
    label: str
    type: str
    group: int = 0
    report_count: int = 1
    in_ring: bool = False
    properties: dict[str, Any] = {}


class GraphEdge(BaseModel):
    source: str
    target: str
    type: str


class GraphData(BaseModel):
    nodes: list[GraphNode] = []
    edges: list[GraphEdge] = []
    truncated: bool = False


class GraphStats(BaseModel):
    phone_numbers: int = 0
    upi_ids: int = 0
    domains: int = 0
    bank_accounts: int = 0
    scam_reports: int = 0
    rings: int = 0
    scam_type_counts: dict[str, int] = {}
    backend: str = "sqlite"  # sqlite | neo4j


class MapCity(BaseModel):
    city: str
    lat: float
    lng: float
    scam_count: int
    top_type: str
    intensity: float
    trend: str = "stable"


class MapHeatmap(BaseModel):
    cities: list[MapCity] = []
    national_stats: dict[str, Any] = {}


class ReportRequest(BaseModel):
    user_name: Optional[str] = None
    user_phone: Optional[str] = None
    user_city: Optional[str] = None
    user_email: Optional[str] = None
    scam_type: Optional[str] = None
    mode_of_contact: Optional[str] = None  # phone | whatsapp | sms | email | website
    incident_date: Optional[str] = None
    incident_time: Optional[str] = None
    amount_demanded: Optional[str] = None
    amount_lost: Optional[float] = 0
    transaction_ref: Optional[str] = None
    anonymous: bool = False
    honeypot_session_id: Optional[str] = None  # prefill IOCs from a honeypot session
    iocs: ThreatIOCs = Field(default_factory=ThreatIOCs)


class ReportResponse(BaseModel):
    report_id: str
    report_text: str
    helpline_script: str
    urgent: bool = False


# ----------------------------------------------------------------------------
# Health (Phase 0)
# ----------------------------------------------------------------------------
class AnalyzeResponse(BaseModel):
    verdict: ScamVerdict
    analysis_metadata: dict[str, Any] = {}


class HealthCheck(BaseModel):
    status: str = "healthy"
    service: str = "mirage-api"
    version: str = "0.1.0"
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    providers: dict[str, Any] = {}


# ---------------------------------------------------------------------------
# Fire Drill (Phase 3)
# ---------------------------------------------------------------------------

STAGE_ORDER = ["hook", "authority", "isolation", "urgency", "payment"]


class DrillProfileRequest(BaseModel):
    name: str
    city: Optional[str] = None
    bank: Optional[str] = None
    employer: Optional[str] = None
    relative_name: Optional[str] = None
    relative_relation: Optional[str] = None
    language: str = "en"
    user_id: Optional[str] = None  # client-generated uuid, persisted in localStorage


class DrillProfileOut(BaseModel):
    profile_id: str
    user_id: str
    name: str
    first_name: str
    city: str
    bank: str
    bank_full_name: str
    employer: Optional[str] = None
    relative_name: Optional[str] = None
    relative_relation: Optional[str] = None
    language: str = "en"
    voice_clip_url: Optional[str] = None
    voice_duration_seconds: float = 0.0
    status: str = "saved"
    message: str = "Profile saved. Upload a voice clip to continue."


class DrillStage(BaseModel):
    stage: str
    order: int
    timestamp_hint: str = ""
    start_seconds: float = 0.0
    end_seconds: float = 0.0
    script: str = ""
    tactic: str = ""


class DrillScriptOut(BaseModel):
    script_id: str
    profile_id: str
    scam_type: str
    title: str
    full_script: str
    stages: list[DrillStage]
    red_flags_planted: list[str] = []
    difficulty_level: str = "medium"
    estimated_duration_seconds: float = 60.0
    language: str = "en"
    source: str = "llm"  # llm | template


class DrillScriptRequest(BaseModel):
    profile_id: str
    scam_type: str
    difficulty: str = "medium"


class DrillSynthesizeRequest(BaseModel):
    script_id: str
    method: str = "auto"  # auto | edge-tts | f5tts


class DrillSynthesizeOut(BaseModel):
    script_id: str
    audio_url: Optional[str] = None
    duration_seconds: float = 0.0
    method_used: str = "edge-tts"
    status: str = "ready"  # ready | failed
    message: str = ""


class DrillRespondRequest(BaseModel):
    script_id: str
    user_action: str = "identified_scam"  # identified_scam | fell_for_it | no_response
    reaction_time_seconds: float = 0.0
    audio_position_seconds: float = 0.0


class DebriefStageDetail(BaseModel):
    stage: str
    timestamp: str = ""
    what_happened: str = ""
    why_it_works: str = ""
    real_world_tip: str = ""


class DrillDebrief(BaseModel):
    outcome: str = "success"  # success | partial | failed
    headline: str = ""
    reaction_assessment: str = ""
    stages_caught: list[DebriefStageDetail] = []
    stages_missed: list[DebriefStageDetail] = []
    key_lesson: str = ""
    real_world_action: str = ""
    encouragement: str = ""


class DrillRespondOut(BaseModel):
    drill_id: str
    script_id: str
    scam_type: str
    user_action: str
    reaction_time_seconds: float
    stages_caught: list[str]
    stages_missed: list[str]
    trigger_stage: Optional[str] = None
    drill_score: int
    score_before: int
    score_after: int
    change: int
    label: str
    debrief: DrillDebrief


class ScoreHistoryEntry(BaseModel):
    drill_number: int
    score: int
    scam_type: str
    date: str


class DrillScoreOut(BaseModel):
    user_id: str
    current_score: int
    previous_score: int
    change: int
    label: str
    drills_completed: int
    best_reaction_time: Optional[float] = None
    weakest_scam_type: Optional[str] = None
    history: list[ScoreHistoryEntry] = []
