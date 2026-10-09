"""Shared display constants for the bot (Phase 2 spec tables)."""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Risk level → emoji + colour word
# ---------------------------------------------------------------------------
RISK_EMOJI = {
    "low": "\U0001f7e2",        # 🟢
    "medium": "\U0001f7e1",     # 🟡
    "high": "\U0001f7e0",       # 🟠
    "critical": "\U0001f534",   # 🔴
}

RISK_COLOR_WORD = {
    "low": "GREEN",
    "medium": "YELLOW",
    "high": "ORANGE",
    "critical": "RED",
}

# ---------------------------------------------------------------------------
# Scam type code → readable name (same mapping as Phase 1)
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
    "impersonation": "Government / Police Impersonation",
    "qr_code": "QR Code",
    "unknown": "Unknown Scam Type",
}

NOT_CLASSIFIED = "Not Classified"

# ---------------------------------------------------------------------------
# Domain age → emoji + label (spec table)
# ---------------------------------------------------------------------------
def age_emoji(days: "int | None") -> tuple[str, str]:
    """Return (emoji, label) for a domain age in days."""
    if days is None:
        return ("\U0001f50d", "WHOIS data unavailable")
    if days < 7:
        return ("\U0001f6a8", "Brand new — extremely suspicious")
    if days < 30:
        return ("⚠️", "Very new — suspicious")
    if days < 90:
        return ("\U0001f7e1", "New — caution")
    if days < 365:
        return ("\U0001f7e2", "Established")
    return ("✅", "Well-established")


# ---------------------------------------------------------------------------
# TLD classification → emoji (spec table)
# ---------------------------------------------------------------------------
LEGITIMATE_TLDS = {".com", ".co.in", ".in", ".gov.in", ".org", ".ac.in"}
NEUTRAL_TLDS = {".net", ".info", ".biz"}


def tld_emoji(tld: str) -> str:
    t = (tld or "").lower()
    if t in LEGITIMATE_TLDS:
        return "✅"
    if t in NEUTRAL_TLDS:
        return "\U0001f7e1"
    return "\U0001f6a9"


# ---------------------------------------------------------------------------
# Language names for transcript display
# ---------------------------------------------------------------------------
LANGUAGE_NAMES = {
    "en": "English",
    "hi": "Hindi",
    "ta": "Tamil",
    "te": "Telugu",
    "bn": "Bengali",
    "mr": "Marathi",
    "kn": "Kannada",
    "ml": "Malayalam",
    "gu": "Gujarati",
    "pa": "Punjabi",
    "ur": "Urdu",
    "ru": "Russian",
}

# ---------------------------------------------------------------------------
# URL shorteners — flagged by the URL handler (Phase 2.4 edge cases)
# ---------------------------------------------------------------------------
URL_SHORTENER_DOMAINS = {
    "bit.ly", "tinyurl.com", "t.co", "goo.gl", "ow.ly",
    "is.gd", "buff.ly", "shorturl.at", "cutt.ly", "v.gd",
}

# ---------------------------------------------------------------------------
# Persistent footer
# ---------------------------------------------------------------------------
FOOTER = "\U0001f4ca Report to 1930 helpline | cybercrime.gov.in"

# ---------------------------------------------------------------------------
# Bot username used in /family instructions (override via env at runtime)
# ---------------------------------------------------------------------------
import os  # noqa: E402  (kept at bottom so constants load without env work)

BOT_USERNAME = os.getenv("TELEGRAM_BOT_USERNAME", "mirage_scam_bot")
