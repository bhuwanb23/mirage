"""Public footprint scraper (Phase 3.1) — profile handling + bank mapping.

In production this would scrape public profiles. For the demo the user enters
their details via the /drill form; this module validates them, applies the
plan's defaults (bank=SBI, city=Mumbai), and maps short bank names to full
names for realistic scam scripts.
"""

from __future__ import annotations

from typing import Any, Optional

from app.services.drill_store import new_id

# short name -> (full name, official domain, toll-free number)
BANK_MAP: dict[str, tuple[str, str, str]] = {
    "sbi": ("State Bank of India", "sbi.co.in", "1800-11-2211"),
    "hdfc": ("HDFC Bank", "hdfcbank.com", "1800-202-6161"),
    "icici": ("ICICI Bank", "icicibank.com", "1800-1080"),
    "axis": ("Axis Bank", "axisbank.com", "1860-419-5555"),
    "kotak": ("Kotak Mahindra Bank", "kotak.com", "1860-266-2666"),
    "pnb": ("Punjab National Bank", "pnbindia.in", "1800-180-2222"),
    "bob": ("Bank of Baroda", "bankofbaroda.in", "1800-258-4455"),
    "yes": ("Yes Bank", "yesbank.in", "1800-1200"),
    "canara": ("Canara Bank", "canarabank.com", "1800-425-0018"),
    "idbi": ("IDBI Bank", "idbibank.in", "1800-200-1947"),
}

DEFAULT_BANK = "sbi"
DEFAULT_CITY = "Mumbai"

# Free-text bank names users might type -> canonical short key
_BANK_ALIASES = {
    "state bank of india": "sbi",
    "s.b.i.": "sbi",
    "hdfc bank": "hdfc",
    "icici bank": "icici",
    "axis bank": "axis",
    "kotak mahindra bank": "kotak",
    "kotak bank": "kotak",
    "punjab national bank": "pnb",
    "bank of baroda": "bob",
    "yes bank": "yes",
    "canara bank": "canara",
    "idbi bank": "idbi",
}


def resolve_bank(bank: Optional[str]) -> str:
    """Normalize user input to a BANK_MAP key. Defaults to SBI."""
    if not bank or not bank.strip():
        return DEFAULT_BANK
    key = bank.strip().lower()
    key = _BANK_ALIASES.get(key, key)
    # allow full names that match a map value
    for short, (full, _domain, _toll) in BANK_MAP.items():
        if key == full.lower():
            return short
    return key if key in BANK_MAP else DEFAULT_BANK


def bank_full_name(bank: str) -> str:
    short = resolve_bank(bank)
    return BANK_MAP[short][0]


def first_name_of(full_name: str) -> str:
    """'Priya Sharma' -> 'Priya'."""
    parts = full_name.strip().split()
    return parts[0] if parts else ""


def build_profile(
    name: str,
    city: Optional[str] = None,
    bank: Optional[str] = None,
    employer: Optional[str] = None,
    relative_name: Optional[str] = None,
    relative_relation: Optional[str] = None,
    language: str = "en",
    user_id: Optional[str] = None,
) -> dict[str, Any]:
    """Build and (caller saves) a profile dict per the Phase 3.1 data structure."""
    name = (name or "").strip()
    if not name:
        raise ValueError("Name is required")

    bank_key = resolve_bank(bank)
    relative_relation = (relative_relation or "").strip() or None

    return {
        "profile_id": new_id(),
        "user_id": (user_id or "").strip() or new_id(),
        "name": name,
        "first_name": first_name_of(name),
        "city": (city or "").strip() or DEFAULT_CITY,
        "bank": bank_key,
        "bank_full_name": BANK_MAP[bank_key][0],
        "bank_domain": BANK_MAP[bank_key][1],
        "bank_toll_free": BANK_MAP[bank_key][2],
        "employer": (employer or "").strip() or None,
        "relative_name": (relative_name or "").strip() or None,
        "relative_relation": relative_relation,
        "language": (language or "en").strip() or "en",
        "voice_clip_path": None,
        "voice_clip_url": None,
        "voice_duration_seconds": 0.0,
        "created_at": None,  # filled on save
    }
