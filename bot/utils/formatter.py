"""Telegram HTML formatting for scam verdicts (Phase 2.1 spec).

All functions return plain strings formatted with Telegram's HTML parse mode.
Text is escaped with html.escape before interpolation so untrusted verdict
content (LLM output, OCR text) can never break the markup.

Spec formats implemented:
  - format_verdict()      → SCAM DETECTED / UNCERTAIN / LIKELY LEGITIMATE block
  - format_voice_block()  → transcript + authenticity bar preamble
  - format_image_block()  → app + OCR + visual anomalies preamble
  - format_url_block()    → domain analysis preamble
  - split_message()       → 4096-char safe split (verdict first, evidence last)
"""

from __future__ import annotations

import html
from typing import Any, Iterable, Optional

from utils.constants import (
    FOOTER,
    NOT_CLASSIFIED,
    RISK_EMOJI,
    SCAM_TYPE_READABLE,
)

TELEGRAM_MAX_LEN = 4096


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def esc(text: Any) -> str:
    """HTML-escape for Telegram interpolation."""
    return html.escape(str(text), quote=False)


def risk_emoji(level: str) -> str:
    return RISK_EMOJI.get((level or "low").lower(), "\U0001f7e2")


def scam_type_readable(code: Optional[str]) -> str:
    if not code:
        return NOT_CLASSIFIED
    return SCAM_TYPE_READABLE.get(code, SCAM_TYPE_READABLE["unknown"])


def percent(confidence: Any) -> int:
    try:
        return round(float(confidence) * 100)
    except (TypeError, ValueError):
        return 0


def risk_bar(score: float, filled_char: str = "\U0001f7e5", empty_char: str = "\u2b1c") -> str:
    """5-segment bar from a 0..1 score, e.g. 🟥🟥🟥🟥⬜ 75%."""
    score = max(0.0, min(1.0, float(score or 0.0)))
    filled = round(score * 5)
    return filled_char * filled + empty_char * (5 - filled)


def _bullets(items: Iterable[str], limit: int = 10) -> str:
    lines = [f"• {esc(item)}" for item in list(items)[:limit]]
    return "\n".join(lines)


def _verdict_emoji_and_word(verdict: dict) -> tuple[str, str]:
    """Pick the header emoji/word per spec: scam / uncertain / legitimate."""
    confidence = float(verdict.get("confidence") or 0.0)
    is_scam = bool(verdict.get("is_scam"))
    if is_scam and confidence >= 0.6:
        return ("\U0001f6a8", "SCAM DETECTED")
    if 0.4 <= confidence < 0.6 or (is_scam and confidence < 0.6):
        return ("\U0001f7e1", "UNCERTAIN")
    return ("✅", "LIKELY LEGITIMATE")


# ---------------------------------------------------------------------------
# Standard verdict block (spec 2.1 Step 6)
# ---------------------------------------------------------------------------

def format_verdict(verdict: dict) -> str:
    """Format the standard scam/uncertain/legitimate verdict block."""
    if not isinstance(verdict, dict):
        return "⚠️ Analysis failed due to a server error. Please try again in a moment."

    emoji, word = _verdict_emoji_and_word(verdict)
    conf_pct = percent(verdict.get("confidence"))
    is_scam = bool(verdict.get("is_scam"))
    risk_level = str(verdict.get("risk_level") or "low").lower()
    summary = esc(verdict.get("summary") or "")
    action = esc(verdict.get("recommended_action") or "")
    red_flags = verdict.get("red_flags") or []
    evidence = verdict.get("evidence") or []

    if emoji == "\U0001f7e1" and not is_scam and conf_pct < 40:
        # Plain low-confidence legit → simple legit format.
        return _format_legit(conf_pct, summary)

    if word == "LIKELY LEGITIMATE":
        return _format_legit(conf_pct, summary)

    if word == "UNCERTAIN":
        return _format_uncertain(verdict, conf_pct, summary)

    return _format_scam(verdict, conf_pct, risk_level, red_flags, summary, action, evidence)


def _format_scam(
    verdict: dict,
    conf_pct: int,
    risk_level: str,
    red_flags: list,
    summary: str,
    action: str,
    evidence: list,
) -> str:
    lines = [
        f"\U0001f6a8 <b>SCAM DETECTED</b> — {conf_pct}% confident",
        "",
        f"<b>Type:</b> {esc(scam_type_readable(verdict.get('scam_type')))}",
        f"<b>Risk:</b> {risk_emoji(risk_level)} {esc(risk_level.upper())}",
    ]

    if red_flags:
        lines += ["", "<b>⚠️ Red Flags:</b>", _bullets(red_flags, limit=8)]

    if summary:
        lines += ["", "<b>📋 Summary:</b>", summary]

    if action:
        lines += ["", "<b>✅ What to do:</b>", action]

    if evidence:
        top = evidence[:3]
        lines += ["", "<b>🔬 Evidence:</b>"]
        for ev in top:
            detail = ev.get("detail", "") if isinstance(ev, dict) else str(ev)
            lines.append(f"• {esc(detail[:160])}")

    lines += ["", f"<i>{FOOTER}</i>"]
    return "\n".join(lines)


def _format_legit(conf_pct: int, summary: str) -> str:
    lines = [
        f"✅ <b>LIKELY LEGITIMATE</b> — {conf_pct}% confident",
        "",
    ]
    if summary:
        lines += ["<b>📋 Summary:</b>", summary, ""]
    lines += [
        "<b>💡 Tips:</b>",
        "• No significant scam indicators found",
        "• Always verify links by typing the URL manually",
        "• Never share your OTP with anyone",
        "",
        "<i>Still unsure? Call your bank on the official number.</i>",
    ]
    return "\n".join(lines)


def _format_uncertain(verdict: dict, conf_pct: int, summary: str) -> str:
    risk_level = str(verdict.get("risk_level") or "medium").lower()
    red_flags = verdict.get("red_flags") or []
    lines = [
        f"\U0001f7e1 <b>UNCERTAIN</b> — {conf_pct}% confident",
        "",
        f"<b>Type:</b> {esc(scam_type_readable(verdict.get('scam_type')))}",
        f"<b>Risk:</b> {risk_emoji(risk_level)} {esc(risk_level.upper())}",
    ]
    if red_flags:
        lines += ["", "<b>⚠️ Potential concerns:</b>", _bullets(red_flags, limit=6)]
    if summary:
        lines += ["", "<b>📋 Summary:</b>", summary]
    lines += [
        "",
        "<b>💡 Recommendation:</b>",
        "Proceed with caution. Verify through official channels before taking any "
        "action. When in doubt, call your bank on the number printed on your debit card.",
        "",
        "<i>Forward more context for a better analysis.</i>",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Input-specific preambles
# ---------------------------------------------------------------------------

def format_voice_block(
    transcript: str,
    language: str,
    synthetic_score: float,
    voice_verdict: str,
) -> str:
    """Transcript + authenticity bar (spec 2.2)."""
    pct = percent(synthetic_score)
    bar = authenticity_bar(synthetic_score)
    verdict_readable = _voice_verdict_readable(voice_verdict, synthetic_score)
    lang_names = {
        "en": "English", "hi": "Hindi", "ta": "Tamil", "te": "Telugu",
        "bn": "Bengali", "mr": "Marathi", "ru": "Russian",
    }
    lang = lang_names.get((language or "").lower(), language or "unknown")
    shown = transcript.strip() or "(no speech detected)"
    if len(shown) > 600:
        shown = shown[:600] + "…"
    return (
        "\U0001f3a4 <b>VOICE NOTE ANALYSIS</b>\n"
        "\n"
        "<b>📝 Transcript:</b>\n"
        f"<i>“{esc(shown)}”</i>\n"
        f"(Language: {esc(lang)})\n"
        "\n"
        "<b>🔊 Voice Authenticity:</b>\n"
        f"{bar} {pct}%\n"
        f"{verdict_readable}\n"
        "\n"
        "━━━━━━━━━━━━━━━━━━━━"
    )


def authenticity_bar(score: float) -> str:
    """5-bucket green/red bar per spec 2.2."""
    pct = percent(score)
    if pct <= 20:
        return "\U0001f7e9\U0001f7e9\U0001f7e9\U0001f7e9\U0001f7e9 Likely Human"
    if pct <= 40:
        return "\U0001f7e9\U0001f7e9\U0001f7e9\U0001f7e1\U0001f7e1 Probably Human"
    if pct <= 60:
        return "\U0001f7e9\U0001f7e9\U0001f7e1\U0001f7e1\U0001f7e1 Uncertain"
    if pct <= 80:
        return "\U0001f7e5\U0001f7e5\U0001f7e5\U0001f7e1\U0001f7e1 Likely AI-Generated ⚠️"
    return "\U0001f7e5\U0001f7e5\U0001f7e5\U0001f7e5\U0001f7e5 AI-Generated \U0001f6a8"


def _voice_verdict_readable(voice_verdict: str, score: float) -> str:
    v = (voice_verdict or "").lower()
    if v in ("likely_ai_generated", "ai_generated") or score >= 0.6:
        return "⚠️ Likely AI-Generated"
    if v in ("likely_human", "human"):
        return "\U0001f7e2 Likely Human"
    if v == "uncertain" or 0.4 <= score <= 0.6:
        return "\U0001f7e1 Uncertain"
    return "\U0001f7e2 Likely Human"


def format_image_block(
    ocr_text: str,
    app_identified: str,
    visual_red_flags: list,
) -> str:
    """App + OCR + visual anomalies (spec 2.3)."""
    lines = [
        "\U0001f4f8 <b>SCREENSHOT ANALYSIS</b>",
        "",
        f"<b>📱 App Detected:</b> {esc(app_identified or 'Unknown')}",
    ]
    ocr = (ocr_text or "").strip()
    if ocr:
        shown = ocr[:500] + ("...(truncated. Full text analyzed.)" if len(ocr) > 500 else "")
        lines += ["", "<b>📝 Extracted Text:</b>", f"<code>{esc(shown)}</code>"]
    if visual_red_flags:
        lines += ["", "<b>👁️ Visual Anomalies:</b>", _bullets(visual_red_flags, limit=6)]
    lines += ["", "━━━━━━━━━━━━━━━━━━━━"]
    return "\n".join(lines)


def format_url_block(url_info: dict) -> str:
    """Domain analysis preamble (spec 2.4)."""
    from utils.constants import age_emoji, tld_emoji

    url = url_info.get("url") or ""
    domain = url_info.get("domain") or ""
    tld = url_info.get("tld") or ""
    age_days = url_info.get("domain_age_days")
    registrar = url_info.get("registrar") or "Unknown"
    https = bool(url_info.get("https"))
    risk = float(url_info.get("risk_score") or 0.0)
    red_flags = url_info.get("red_flags") or []

    age_e, age_label = age_emoji(age_days)
    age_text = f"{age_days:,} days" if age_days is not None else "WHOIS unavailable"

    lines = [
        "\U0001f517 <b>DOMAIN ANALYSIS</b>",
        "",
        f"<b>URL:</b> <code>{esc(url)}</code>",
        f"<b>Domain:</b> {esc(domain)}",
        f"<b>TLD:</b> {esc(tld)} {tld_emoji(tld)}",
        "",
        f"<b>📅 Domain Age:</b> {age_text} {age_e} <i>({esc(age_label)})</i>",
        f"<b>🏢 Registrar:</b> {esc(registrar)}",
        f"<b>🔒 HTTPS:</b> {'✅ Yes' if https else '❌ No'}",
        "",
        "<b>🎯 Lookalike Check:</b>",
    ]

    if url_info.get("is_lookalike"):
        target = url_info.get("lookalike_target") or "the official domain"
        brand = url_info.get("brand_keyword") or ""
        lines.append(
            f"⚠️ Contains brand name <b>“{esc(brand)}”</b> but is NOT "
            f"the official domain ({esc(target)})"
        )
    elif not url_info.get("is_suspicious"):
        lines.append("✅ No lookalike detected — matches its official brand")
    else:
        lines.append("\U0001f7e1 No brand keywords found, but other red flags exist")

    lines += [
        "",
        f"<b>⚠️ Risk Score:</b> {risk_bar(risk)} {percent(risk)}%",
    ]

    if red_flags:
        lines += ["", "<b>🚩 Red Flags:</b>", _bullets(red_flags, limit=8)]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Message splitting (spec: >4096 → two messages)
# ---------------------------------------------------------------------------

def split_message(text: str, limit: int = TELEGRAM_MAX_LEN) -> list[str]:
    """Split HTML text into <=limit chunks, never cutting inside a line."""
    if len(text) <= limit:
        return [text]
    chunks: list[str] = []
    current = ""
    for line in text.split("\n"):
        candidate = f"{current}\n{line}" if current else line
        if len(candidate) <= limit:
            current = candidate
            continue
        if current:
            chunks.append(current)
        # Hard-cut a single over-long line.
        while len(line) > limit:
            chunks.append(line[:limit])
            line = line[limit:]
        current = line
    if current:
        chunks.append(current)
    return chunks
