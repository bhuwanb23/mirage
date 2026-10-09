"""Evidence Trail Builder (Phase 1.5).

Takes raw outputs from all analyzers (text, URL, image, audio) and produces a
unified, human-readable scam report with a merged confidence score.

Flow:
  1. Collect all signals from the orchestrator dict
  2. Merge confidence scores (weighted average with agreement boosts)
  3. Aggregate + deduplicate red flags (sorted by severity, capped at 10)
  4. Determine final verdict (is_scam, risk_level, scam_type, recommended_action)
  5. Generate human-readable summary (template-based, no LLM)
  6. Build final ScamVerdict with evidence items
"""

from __future__ import annotations

from collections import OrderedDict
from typing import Any, Optional

from app.models.schemas import (
    Evidence,
    EvidenceType,
    RiskLevel,
    ScamVerdict,
)

# ---------------------------------------------------------------------------
# Weights (spec table, Step 2)
# ---------------------------------------------------------------------------
TEXT_WEIGHT = 0.40
URL_WEIGHT = 0.30
VISUAL_WEIGHT = 0.15
AUDIO_WEIGHT = 0.15

# Adjustment deltas (spec Step 2)
URL_CONFIRM_BOOST = 0.10
VISUAL_CONFIRM_BOOST = 0.05
AUDIO_SYNTH_BOOST = 0.10
URL_CONTRADICT_PENALTY = -0.15
CONSENSUS_BOOST = 0.05

# Audio-only weights (spec special case)
AUDIO_ONLY_TEXT_WEIGHT = 0.60
AUDIO_ONLY_SYNTH_WEIGHT = 0.40

# ---------------------------------------------------------------------------
# Scam type → readable name (spec Step 5 table)
# ---------------------------------------------------------------------------
SCAM_TYPE_READABLE = {
    "bank_kyc": "Bank KYC / Account Freeze",
    "upi_reversal": "UPI Payment Reversal",
    "fedex": "Fake Delivery / Customs",
    "job_offer": "Fake Job Offer",
    "lottery": "Lottery / Prize",
    "relative_distress": "Relative in Distress",
    "otp_phishing": "OTP Phishing",
    "investment": "Investment / Trading",
    "romance": "Romance",
    "electricity": "Electricity Bill",
    "impersonation": "Govt / Police Impersonation",
    "qr_code": "QR Code",
    "unknown": "Unknown",
}

# ---------------------------------------------------------------------------
# Red flag severity ranking (for sorting)
# ---------------------------------------------------------------------------
# Keywords that indicate higher severity. Flags are ranked by severity band
# then by the presence of these keywords.
SeverityKey = tuple[int, int]  # (severity_band, keyword_rank)


def _severity_key(flag: str, evidence_severity: RiskLevel | str) -> SeverityKey:
    """Return a sort key for a red flag — higher severity sorts first."""
    sev = (
        evidence_severity
        if isinstance(evidence_severity, RiskLevel)
        else RiskLevel(evidence_severity)
    )
    band = {"critical": 0, "high": 1, "medium": 2, "low": 3}.get(
        sev.value, 2
    )
    # Within a band, flags mentioning money/payment/OTP/account rank higher
    kw_rank = 0
    lower = flag.lower()
    if any(k in lower for k in ("payment", "money", "transfer", "deposit", "bank account")):
        kw_rank = 0
    elif any(k in lower for k in ("otp", "pin", "password", "authorization", "verify your")):
        kw_rank = 1
    elif any(
        k in lower
        for k in ("blocked", "frozen", "closed", "suspended", "urgent", "immediately")
    ):
        kw_rank = 2
    elif any(k in lower for k in ("click", "link", "url", "website", "page")):
        kw_rank = 3
    else:
        kw_rank = 4
    return (band, kw_rank)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_evidence_trail(results: dict[str, Any]) -> ScamVerdict:
    """Build a unified ScamVerdict from all analyzer outputs.

    `results` is a dict with optional keys:
      - text_verdict: ScamVerdict | None
      - url_results: list[dict] | None  (URLAnalysisResult-style dicts or DomainInfo)
      - image_analysis: dict | None  (ImageAnalysisVerdict-style dict)
      - audio_analysis: dict | None  (VoiceAnalysisVerdict-style dict)

    Returns a ScamVerdict with merged confidence, aggregated red flags,
    evidence items from all sources, and a human-readable summary.
    """
    text_verdict = results.get("text_verdict")
    url_results = results.get("url_results")
    image_analysis = results.get("image_analysis")
    audio_analysis = results.get("audio_analysis")

    # Step 1: collect evidence items from each source
    evidence_items: list[Evidence] = []
    all_red_flags: list[tuple[str, RiskLevel | str]] = []  # (flag, severity)

    # --- text classifier evidence ---
    if text_verdict is not None:
        for ev in text_verdict.evidence:
            evidence_items.append(_normalize_evidence(ev))
        for flag in text_verdict.red_flags:
            all_red_flags.append((flag, RiskLevel.MEDIUM))
        # Linguistic evidence for stages detected
        for stage in text_verdict.stages_detected:
            evidence_items.append(
                Evidence(
                    type=EvidenceType.LINGUISTIC,
                    detail=f"Message uses {stage} tactic",
                    severity=RiskLevel.MEDIUM,
                    source="text_classifier",
                )
            )

    # --- URL analysis evidence ---
    url_confirms = False
    url_contradicts = False
    if url_results:
        for url_item in url_results:
            risk = url_item.get("risk_score", 0.0) if isinstance(url_item, dict) else 0.0
            is_susp = url_item.get("is_suspicious", False) if isinstance(url_item, dict) else False
            domain = url_item.get("domain", "") if isinstance(url_item, dict) else ""
            age = url_item.get("domain_age_days") if isinstance(url_item, dict) else None
            registrar = url_item.get("registrar") if isinstance(url_item, dict) else None
            red_flags = url_item.get("red_flags", []) if isinstance(url_item, dict) else []

            if is_susp:
                url_confirms = True
                for rf in red_flags:
                    all_red_flags.append((rf, RiskLevel.HIGH))
                # URL analysis evidence item
                detail_parts = [f"Domain {domain} analyzed"]
                if age is not None:
                    detail_parts.append(f"registered {age} days ago")
                if registrar:
                    detail_parts.append(f"via {registrar}")
                evidence_items.append(
                    Evidence(
                        type=EvidenceType.URL_ANALYSIS,
                        detail=". ".join(detail_parts) + f". Risk score: {risk:.2f}",
                        severity=RiskLevel.HIGH if risk >= 0.5 else RiskLevel.MEDIUM,
                        source="url_analyzer",
                    )
                )
                if age is not None:
                    evidence_items.append(
                        Evidence(
                            type=EvidenceType.DOMAIN_AGE,
                            detail=f"Domain {domain} registered on "
                            f"{_approx_date(age)} (only {age} days ago)",
                            severity=RiskLevel.HIGH if age < 7 else RiskLevel.MEDIUM,
                            source="url_analyzer",
                        )
                    )
            else:
                url_contradicts = True
                evidence_items.append(
                    Evidence(
                        type=EvidenceType.URL_ANALYSIS,
                        detail=f"Domain {domain} appears legitimate (risk score: {risk:.2f})",
                        severity=RiskLevel.LOW,
                        source="url_analyzer",
                    )
                )

    # --- image analysis evidence ---
    visual_confirms = False
    if image_analysis:
        vrf = (
            image_analysis.get("visual_red_flags", [])
            if isinstance(image_analysis, dict)
            else []
        )
        ocr = (
            image_analysis.get("ocr_text", "")
            if isinstance(image_analysis, dict)
            else ""
        )

        if vrf:
            visual_confirms = True
            for flag in vrf:
                all_red_flags.append((flag, RiskLevel.HIGH))
            for flag in vrf:
                evidence_items.append(
                    Evidence(
                        type=EvidenceType.VISUAL,
                        detail=flag,
                        severity=RiskLevel.HIGH,
                        source="image_analyzer",
                    )
                )
        if ocr:
            evidence_items.append(
                Evidence(
                    type=EvidenceType.VISUAL,
                    detail=f"OCR extracted {len(ocr)} characters from image",
                    severity=RiskLevel.LOW,
                    source="image_analyzer",
                )
            )

    # --- audio analysis evidence ---
    audio_confirms = False
    if audio_analysis:
        synth_score = (
            audio_analysis.get("synthetic_voice_score", 0.0)
            if isinstance(audio_analysis, dict)
            else 0.0
        )
        voice_verdict = (
            audio_analysis.get("voice_verdict", "unknown")
            if isinstance(audio_analysis, dict)
            else "unknown"
        )
        transcript = (
            audio_analysis.get("transcript", "")
            if isinstance(audio_analysis, dict)
            else ""
        )
        vrf = (
            audio_analysis.get("verdict", {}).get("red_flags", [])
            if isinstance(audio_analysis, dict)
            else []
        )

        if voice_verdict == "likely_ai_generated" or synth_score >= 0.6:
            audio_confirms = True
            evidence_items.append(
                Evidence(
                    type=EvidenceType.VOICE_SYNTHETIC,
                    detail=f"Voice has {synth_score:.0%} probability of being AI-generated",
                    severity=RiskLevel.HIGH if synth_score >= 0.6 else RiskLevel.MEDIUM,
                    source="audio_analyzer",
                )
            )
        elif voice_verdict == "likely_human":
            evidence_items.append(
                Evidence(
                    type=EvidenceType.VOICE_SYNTHETIC,
                    detail="Voice appears to be human (not AI-synthesized)",
                    severity=RiskLevel.LOW,
                    source="audio_analyzer",
                )
            )

        if transcript:
            # Transcript evidence — check for payment demands, urgency, etc.
            transcript_lower = transcript.lower()
            payment_keywords = ["transfer", "payment", "send", "deposit", " INR", "rs ", "₹", "upi"]
            if any(k in transcript_lower for k in payment_keywords):
                evidence_items.append(
                    Evidence(
                        type="transcript",
                        detail=f"Transcript contains payment demand: '{transcript[:120]}'",
                        severity=RiskLevel.HIGH,
                        source="audio_analyzer",
                    )
                )
            evidence_items.append(
                Evidence(
                    type="transcript",
                    detail=f"Transcript ({len(transcript)} chars): '{transcript[:100]}...'",
                    severity=RiskLevel.LOW,
                    source="audio_analyzer",
                )
            )

    # Step 2: merge confidence scores
    merged_confidence = _merge_confidence(
        text_verdict, url_results, image_analysis, audio_analysis,
        url_confirms, url_contradicts, visual_confirms, audio_confirms,
    )

    # Step 3: aggregate red flags (deduplicate, sort, cap)
    final_red_flags = _aggregate_red_flags(all_red_flags)

    # Step 4: determine final verdict
    is_scam = merged_confidence > 0.5
    risk_level = _risk_from_confidence(merged_confidence, is_scam)

    # scam_type: use text classifier's (most specific), fall back to URL-based if available
    scam_type = None
    if text_verdict is not None:
        scam_type = text_verdict.scam_type
    elif url_confirms and url_results:
        # Infer from URL lookalike target if available
        for item in url_results:
            if isinstance(item, dict) and item.get("is_lookalike") and item.get("brand_keyword"):
                bw = item["brand_keyword"]
                if bw == "sbi":
                    scam_type = "bank_kyc"
                elif bw == "hdfc":
                    scam_type = "bank_kyc"
                elif bw == "icici":
                    scam_type = "bank_kyc"
                else:
                    scam_type = "unknown"
                break
    if not scam_type:
        scam_type = "unknown"

    # recommended_action: based on risk level
    recommended_action = _recommended_action_for_risk(risk_level)

    # Step 5: generate human-readable summary
    summary = _generate_summary(
        merged_confidence, is_scam, scam_type, final_red_flags,
        evidence_items, text_verdict, audio_analysis, url_confirms,
    )

    # Step 6: build final ScamVerdict
    return ScamVerdict(
        is_scam=is_scam,
        confidence=round(merged_confidence, 3),
        scam_type=scam_type,
        risk_level=risk_level,
        red_flags=final_red_flags,
        evidence=evidence_items,
        stages_detected=text_verdict.stages_detected if text_verdict else [],
        summary=summary,
        recommended_action=recommended_action,
    )


# ---------------------------------------------------------------------------
# Confidence merging (Step 2)
# ---------------------------------------------------------------------------


def _merge_confidence(
    text_verdict: Optional[ScamVerdict],
    url_results: Optional[list[Any]],
    image_analysis: Optional[dict],
    audio_analysis: Optional[dict],
    url_confirms: bool,
    url_contradicts: bool,
    visual_confirms: bool,
    audio_confirms: bool,
) -> float:
    """Merge confidence from all signals using the spec's weighted formula.

    Returns a confidence in 0.0..1.0.
    """
    # Count available signals
    has_text = text_verdict is not None
    has_urls = url_results is not None and len(url_results) > 0
    has_visual = image_analysis is not None
    has_audio = audio_analysis is not None

    available_count = sum([has_text, has_urls, has_visual, has_audio])

    if available_count == 0:
        return 0.0

    # --- special case: ONLY URL available ---
    if has_urls and not has_text and not has_visual and not has_audio:
        # Use URL risk score as primary confidence
        highest_risk = 0.0
        for item in url_results:
            if isinstance(item, dict):
                highest_risk = max(highest_risk, item.get("risk_score", 0.0))
        confidence = highest_risk
        return round(max(0.0, min(1.0, confidence)), 3)

    # --- special case: ONLY audio available ---
    if has_audio and not has_text and not has_urls and not has_visual:
        synth_score = (
            audio_analysis.get("synthetic_voice_score", 0.0)
            if isinstance(audio_analysis, dict)
            else 0.0
        )
        # Weight transcript at 0.60 and synthetic score at 0.40
        # Transcript confidence: if transcript is non-empty, use 0.5 as base
        # (we don't have a text verdict, so use a moderate base)
        transcript_confidence = 0.5 if audio_analysis.get("transcript", "") else 0.0
        confidence = (
            AUDIO_ONLY_TEXT_WEIGHT * transcript_confidence
            + AUDIO_ONLY_SYNTH_WEIGHT * synth_score
        )
        return round(max(0.0, min(1.0, confidence)), 3)

    # --- general case: weighted average with boosts ---
    confidence = 0.0
    total_weight = 0.0

    # Text classifier (base signal)
    if has_text:
        text_conf = text_verdict.confidence if text_verdict else 0.0
        confidence += TEXT_WEIGHT * text_conf
        total_weight += TEXT_WEIGHT

    # URL analysis
    if has_urls:
        url_risk = 0.0
        for item in url_results:
            if isinstance(item, dict):
                url_risk = max(url_risk, item.get("risk_score", 0.0))
        confidence += URL_WEIGHT * url_risk
        total_weight += URL_WEIGHT

    # Visual analysis
    if has_visual:
        visual_conf = 0.0
        vrf = (
            image_analysis.get("visual_red_flags", [])
            if isinstance(image_analysis, dict)
            else []
        )
        # Visual confidence: base 0.5 + boost from visual red flags
        if vrf:
            visual_conf = min(0.9, 0.5 + len(vrf) * 0.1)
        else:
            visual_conf = 0.0
        confidence += VISUAL_WEIGHT * visual_conf
        total_weight += VISUAL_WEIGHT

    # Audio synthetic score
    if has_audio:
        synth_score = (
            audio_analysis.get("synthetic_voice_score", 0.0)
            if isinstance(audio_analysis, dict)
            else 0.0
        )
        confidence += AUDIO_WEIGHT * synth_score
        total_weight += AUDIO_WEIGHT

    # Normalize by total weight (in case some signals are missing)
    if total_weight > 0:
        confidence = confidence / total_weight

    # --- agreement boosts ---
    if url_confirms:
        confidence += URL_CONFIRM_BOOST
    if visual_confirms:
        confidence += VISUAL_CONFIRM_BOOST
    if audio_confirms:
        confidence += AUDIO_SYNTH_BOOST
    if url_contradicts:
        confidence += URL_CONTRADICT_PENALTY

    # --- consensus boost: if multiple signals agree (all say scam) ---
    signal_count = 0
    agreeing_count = 0
    if has_text and text_verdict and text_verdict.is_scam:
        agreeing_count += 1
    if has_urls:
        for item in url_results:
            if isinstance(item, dict) and item.get("is_suspicious"):
                agreeing_count += 1
                break
    if has_visual:
        vb = (
            image_analysis.get("confidence_boost", 0.0)
            if isinstance(image_analysis, dict)
            else 0.0
        )
        if vb > 0.1:
            agreeing_count += 1
    if has_audio:
        synth_score = (
            audio_analysis.get("synthetic_voice_score", 0.0)
            if isinstance(audio_analysis, dict)
            else 0.0
        )
        if synth_score >= 0.6:
            agreeing_count += 1

    signal_count = sum([has_text, has_urls, has_visual, has_audio])
    if signal_count >= 2 and agreeing_count >= 2:
        confidence += CONSENSUS_BOOST

    return round(max(0.0, min(1.0, confidence)), 3)


# ---------------------------------------------------------------------------
# Red flag aggregation (Step 3)
# ---------------------------------------------------------------------------


def _aggregate_red_flags(
    all_red_flags: list[tuple[str, RiskLevel | str]],
) -> list[str]:
    """Deduplicate, sort by severity, and cap at 10 red flags."""
    if not all_red_flags:
        return []

    # Deduplicate: keep the highest severity for each unique flag
    best: dict[str, RiskLevel | str] = OrderedDict()
    for flag, sev in all_red_flags:
        key = flag.strip().lower()
        if key not in best:
            best[key] = sev
        else:
            existing = best[key]
            existing_level = existing if isinstance(existing, RiskLevel) else RiskLevel(existing)
            new_level = sev if isinstance(sev, RiskLevel) else RiskLevel(sev)
            # Keep higher severity (lower enum value = higher severity)
            if existing_level.value <= new_level.value:
                best[key] = sev

    # Sort by severity key (critical first, then high, medium, low;
    # within same severity, payment/money/OTP flags first)
    sorted_items = sorted(
        best.items(),
        key=lambda item: _severity_key(item[0], item[1]),
    )

    # Take top 10, return original casing
    return [flag for flag, _ in sorted_items[:10]]


# ---------------------------------------------------------------------------
# Summary generation (Step 5)
# ---------------------------------------------------------------------------


def _generate_summary(
    confidence: float,
    is_scam: bool,
    scam_type: str,
    red_flags: list[str],
    evidence_items: list[Evidence],
    text_verdict: Optional[ScamVerdict],
    audio_analysis: Optional[dict],
    url_confirms: bool,
) -> str:
    """Generate a human-readable summary using templates (no LLM)."""
    pct = round(confidence * 100)

    if is_scam:
        readable = SCAM_TYPE_READABLE.get(scam_type, scam_type or "Unknown")
        parts = [f"🚨 This is a {readable} scam ({pct}% confidence)."]

        if red_flags:
            parts.append("Key red flags:")
            for i, flag in enumerate(red_flags[:5], 1):
                parts.append(f"  {i}. {flag}")

        # What the scammer is trying to do (one sentence based on scam_type)
        explanation = _scam_explanation(scam_type)
        if explanation:
            parts.append(f"What the scammer is trying to do: {explanation}")

            action = _recommended_action_for_risk(
                _risk_from_confidence(confidence, True)
            )
            parts.append(f"What you should do: {action}")

        # Evidence details
        if evidence_items:
            parts.append("Evidence:")
            for ev in evidence_items[:6]:
                sev_val = (
                ev.severity.value
                if isinstance(ev.severity, RiskLevel)
                else str(ev.severity)
            )
                parts.append(f"  - [{sev_val}] {ev.detail[:150]}")

        return "\n".join(parts)

    # Legitimate message
    parts = [f"✅ This appears to be a legitimate message ({pct}% confidence)."]
    parts.append("No significant scam indicators were found. However, always stay cautious:")
    parts.append("  - Never share your OTP with anyone")
    parts.append("  - Verify links by typing the URL manually")
    parts.append("  - Call your bank on the official number if unsure")

    return "\n".join(parts)


def _scam_explanation(scam_type: str) -> str:
    """One-sentence explanation of what the scammer is trying to do."""
    explanations = {
        "bank_kyc": (
            "The scammer is pretending to be your bank and trying to get your personal "
            "details, OTP, or money by claiming your account needs verification."
        ),
        "upi_reversal": (
            "The scammer is pretending you received money by mistake and asking you to "
            "'return' it - but the original payment was fake and will be reversed, "
            "leaving you out of pocket."
        ),
        "fedex": (
            "The scammer is pretending to be a delivery service and asking for a small "
            "fee or personal details to 'release' a package that doesn't exist."
        ),
        "job_offer": (
            "The scammer is offering a fake job with high pay and asking for an upfront "
            "fee, personal details, or bank information."
        ),
        "lottery": (
            "The scammer is claiming you won a lottery or prize and needs your bank "
            "details or an upfront fee to 'release' the winnings."
        ),
        "relative_distress": (
            "The scammer is pretending to be a relative in trouble (often using a "
            "cloned voice) and urgently asking for money - typically targeting elderly "
            "family members."
        ),
        "otp_phishing": (
            "The scammer is trying to trick you into sharing your OTP so they can "
            "access your bank account or UPI."
        ),
        "investment": (
            "The scammer is promoting a fake investment or trading platform with "
            "promised high returns - your money will be stolen, not invested."
        ),
        "romance": (
            "The scammer is building a fake romantic relationship to gain trust, then "
            "asking for money for an 'emergency' or 'visitation'."
        ),
        "electricity": (
            "The scammer is pretending to be your electricity board and threatening "
            "disconnection unless you pay immediately via a fake link or UPI."
        ),
        "impersonation": (
            "The scammer is pretending to be a government official (police, RBI, CBI) "
            "and threatening legal action unless you pay or share details."
        ),
        "qr_code": (
            "The scammer is asking you to scan a QR code to 'receive' money - but "
            "scanning it actually debits money from your account."
        ),
        "unknown": (
            "The scammer is using deceptive tactics to extract money or personal "
            "information from you."
        ),
    }
    return explanations.get(scam_type, "")


def _recommended_action_for_risk(risk_level: RiskLevel | str) -> str:
    """Recommended action based on risk level (spec Step 4 table)."""
    if isinstance(risk_level, str):
        risk_level = RiskLevel(risk_level)
    mapping = {
        RiskLevel.LOW: "This appears legitimate",
        RiskLevel.MEDIUM: (
            "Proceed with caution. Verify through official channels."
        ),
        RiskLevel.HIGH: (
            "Do NOT click any links or share personal information. Block the sender."
        ),
        RiskLevel.CRITICAL: (
            "HANG UP / DELETE IMMEDIATELY. Report to 1930 helpline. "
            "Do NOT share any OTP or make any payment."
        ),
    }
    return mapping.get(risk_level, "This appears legitimate")


def _risk_from_confidence(confidence: float, is_scam: bool) -> RiskLevel:
    """Risk level from confidence (same mapping as 1.1)."""
    if not is_scam:
        if confidence <= 0.5:
            return RiskLevel.LOW
        if confidence <= 0.7:
            return RiskLevel.MEDIUM
        return RiskLevel.HIGH
    if confidence <= 0.5:
        return RiskLevel.MEDIUM
    if confidence < 0.7:
        return RiskLevel.MEDIUM
    if confidence < 0.85:
        return RiskLevel.HIGH
    return RiskLevel.CRITICAL


def _normalize_evidence(ev: Evidence) -> Evidence:
    """Ensure evidence has a source field (default to 'unknown' if missing)."""
    if hasattr(ev, "source") and ev.source:
        return ev
    return Evidence(
        type=ev.type,
        detail=ev.detail,
        severity=ev.severity,
        source="unknown",
    )


def _approx_date(age_days: int) -> str:
    """Approximate registration date based on age in days."""
    from datetime import date, timedelta
    today = date.today()
    reg_date = today - timedelta(days=age_days)
    return reg_date.isoformat()
