"""IOC extractor — Phase 5.2.

Two layers (plan §5.2):
  1. Regex  — fast, deterministic, runs on every message (< 1 ms).
  2. LLM    — fallback/enrichment for spelled-out numbers and odd phrasing.

Output is a ThreatIOCs object (app.models.schemas). Every IOC carries its
source and a short context snippet so the report generator can quote it.
"""

from __future__ import annotations

import logging
import re
from typing import Iterable
from urllib.parse import urlparse

from app.models.schemas import IOCItem, ThreatIOCs

logger = logging.getLogger("mirage.ioc")

# ---------------------------------------------------------------------------
# Regex layer
# ---------------------------------------------------------------------------

PHONE_PATTERNS = [
    r"\+91[\s-]?\d{5}[\s-]?\d{5}",          # +91 98765 43210
    r"(?<!\d)\d{5}[\s-]\d{5}(?!\d)",         # 98765 43210 (spaced, no country code)
    r"(?<!\d)9\d{9}(?!\d)",                 # 9876543210
    r"(?<!\d)8\d{9}(?!\d)",                 # 8876543210
    r"(?<!\d)7\d{9}(?!\d)",                 # 7876543210
    r"(?<!\d)6\d{9}(?!\d)",                 # 6876543210
    r"1800[\s-]?\d{3}[\s-]?\d{4}",          # 1800-123-4567 (toll-free)
]
PHONE_RE = re.compile("|".join(f"(?:{p})" for p in PHONE_PATTERNS))

# Generic handle@domain. Email-looking TLDs are dropped (see _EMAILISH).
UPI_RE = re.compile(r"[a-zA-Z0-9._-]{3,}@[a-zA-Z]{2,11}")

# TLD-ish suffixes that mean "this is an email address", not a UPI handle.
_EMAILISH = {
    "com", "net", "org", "edu", "gov", "co", "io", "ai", "info", "me",
    "xyz", "online", "site", "store", "app", "dev", "biz", "shop", "tech",
    # multi-part TLDs
    "co.in", "com.in", "ac.in", "gov.in", "edu.in", "co.uk", "com.au",
}

URL_RE = re.compile(
    r"https?://[^\s<>\"{}|\\^`\[\]]+"          # standard URLs
    r"|www\.[a-zA-Z0-9-]+(?:\.[a-zA-Z]{2,})[^\s]*"  # www.example.com
    r"|bit\.ly/[a-zA-Z0-9]+"
    r"|tinyurl\.com/[a-zA-Z0-9]+",
    re.IGNORECASE,
)
DOMAIN_RE = re.compile(r"\b(?:[a-zA-Z0-9-]+\.)+(?:com|net|org|xyz|top|in|io|info|site|online|biz|co)\b", re.IGNORECASE)

# Bank accounts: 9-18 digits, only when near an account keyword (plan §5.2).
ACCOUNT_KEYWORD_RE = re.compile(
    r"(?:a/?c|acct|account|ac no|account no|account number|acc)\b", re.IGNORECASE
)
ACCOUNT_WINDOW = 48  # chars of context either side of the number

IFSC_RE = re.compile(r"\b[A-Z]{4}0[A-Z0-9]{6}\b")

AMOUNT_PATTERNS = [
    r"₹[\s,]*\d[\d,]*(?:\.\d{2})?",
    r"Rs\.?[\s,]*\d[\d,]*(?:\.\d{2})?",
    r"INR[\s,]*\d[\d,]*(?:\.\d{2})?",
]
AMOUNT_RE = re.compile("|".join(f"(?:{p})" for p in AMOUNT_PATTERNS), re.IGNORECASE)

REFERENCE_PATTERNS = [
    r"[A-Z]{2,5}[/-]\d{4}[/-]\d{4,8}",       # KYC-2025-8834
    r"Case[\s#]*\d{4,10}",                    # Case #12345
    r"Ref[\s#:]*\s*[A-Z0-9-]{6,15}",          # Ref: EB2024-8834
]
REFERENCE_RE = re.compile("|".join(f"(?:{p})" for p in REFERENCE_PATTERNS))

BANK_NAME_RE = re.compile(
    r"\b(SBI|HDFC|ICICI|Axis|Kotak|PNB|Bank of Baroda|Yes Bank|IDFC|IDBI|"
    r"Canara|Union Bank|IndusInd|Federal Bank|AU Bank|Jio Finance)\b",
    re.IGNORECASE,
)

LOCATION_RE = re.compile(
    r"\b(Delhi|Mumbai|Bangalore|Bengaluru|Hyderabad|Chennai|Kolkata|Pune|"
    r"Jaipur|Ahmedabad|Lucknow|Surat|Kanpur|Nagpur|Indore|Bhopal|"
    r"Chandigarh|Patna|Kochi|Coimbatore)\b",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Validation / filtering
# ---------------------------------------------------------------------------

# The honeypot persona's own fabricated details (plan §5.2 edge case) — never
# stored as IOCs, they would poison the graph.
HONEYPOT_FAKE_PHONES = {"9876543210"}
HONEYPOT_FAKE_ACCOUNTS = {"1234567890", "1234567890123"}

# Real helplines that must never be flagged (plan §5.2 edge case).
LEGIT_PHONE_ALLOWLIST = {
    "1930",        # National Cyber Crime Helpline
    "1944",
    "18004253800",  # SBI
    "18002094324",  # HDFC
    "1800112211",   # generic bank helpline pattern
    "18001801100",
}

_PHONE_TEN = re.compile(r"\d{10}")


def _context(text: str, start: int, end: int, width: int = 60) -> str:
    a, b = max(0, start - width), min(len(text), end + width)
    snippet = text[a:b].strip()
    return ("…" if a > 0 else "") + snippet + ("…" if b < len(text) else "")


def _normalize_phone(raw: str) -> str | None:
    digits = re.sub(r"\D", "", raw)
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    if len(digits) == 13 and digits.startswith("091"):
        digits = digits[3:]
    if len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]
    if len(digits) == 10 and digits[0] in "6789":
        return digits
    if digits.startswith("1800") and len(digits) == 10:
        return digits
    return None


def _looks_like_email(domain_part: str) -> bool:
    return domain_part.lower() in _EMAILISH


def _domain_from_url(url: str) -> str | None:
    try:
        candidate = url if "://" in url else "http://" + url
        host = urlparse(candidate).hostname or ""
        host = host.lower().removeprefix("www.")
        return host if "." in host else None
    except ValueError:
        return None


def _dedupe(items: Iterable[IOCItem]) -> list[IOCItem]:
    seen: dict[str, IOCItem] = {}
    for item in items:
        key = item.value.lower()
        if key not in seen:
            seen[key] = item
    return list(seen.values())


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def extract_iocs(
    text: str,
    *,
    source: str = "regex",
    filter_fake_details: bool = True,
) -> ThreatIOCs:
    """Regex extraction over one message. Returns a ThreatIOCs object."""
    out = ThreatIOCs()
    if not text:
        return out

    # --- phones ---
    phones: list[IOCItem] = []
    for m in PHONE_RE.finditer(text):
        norm = _normalize_phone(m.group(0))
        if not norm:
            continue
        if norm in LEGIT_PHONE_ALLOWLIST:
            continue
        if filter_fake_details and norm in HONEYPOT_FAKE_PHONES:
            continue
        phones.append(IOCItem(value=norm, source=source, context=_context(text, *m.span())))
    out.phone_numbers = _dedupe(phones)

    # --- UPI ids ---
    upis: list[IOCItem] = []
    for m in UPI_RE.finditer(text):
        handle = m.group(0).lower().rstrip(".,;:!?")
        domain_part = handle.split("@", 1)[1]
        if _looks_like_email(domain_part):
            continue
        upis.append(IOCItem(value=handle, source=source, context=_context(text, *m.span())))
    out.upi_ids = _dedupe(upis)

    # --- urls + domains ---
    urls: list[IOCItem] = []
    domains: list[IOCItem] = []
    for m in URL_RE.finditer(text):
        url = m.group(0).rstrip(".,;:!?)")
        urls.append(IOCItem(value=url, source=source, context=_context(text, *m.span())))
        dom = _domain_from_url(url)
        if dom:
            domains.append(IOCItem(value=dom, source="url_parse", context=url))
    for m in DOMAIN_RE.finditer(text):
        dom = m.group(0).lower().rstrip(".,;:!?")
        if "@" + dom in text:  # part of a UPI handle, not a standalone domain
            continue
        domains.append(IOCItem(value=dom, source=source, context=_context(text, *m.span())))
    out.urls = _dedupe(urls)
    out.domains = _dedupe(domains)

    # --- bank accounts (keyword-gated) ---
    accounts: list[IOCItem] = []
    for m in re.finditer(r"(?<!\d)\d{9,18}(?!\d)", text):
        value = m.group(0)
        window_start = max(0, m.start() - ACCOUNT_WINDOW)
        window = text[window_start : m.end() + ACCOUNT_WINDOW]
        if not ACCOUNT_KEYWORD_RE.search(window):
            continue
        if len(value) == 10 and value[0] in "6789":
            continue  # that's a phone number
        if filter_fake_details and value in HONEYPOT_FAKE_ACCOUNTS:
            continue
        accounts.append(IOCItem(value=value, source=source, context=_context(text, *m.span())))
    out.bank_accounts = _dedupe(accounts)

    # --- IFSC ---
    out.ifsc_codes = _dedupe(
        IOCItem(value=m.group(0).upper(), source=source, context=_context(text, *m.span()))
        for m in IFSC_RE.finditer(text)
    )

    # --- amounts / references / bank names / locations (plain values) ---
    out.amounts = list(dict.fromkeys(m.group(0).strip() for m in AMOUNT_RE.finditer(text)))
    out.reference_numbers = list(
        dict.fromkeys(m.group(0).strip() for m in REFERENCE_RE.finditer(text))
    )
    out.bank_names = list(dict.fromkeys(m.group(1) for m in BANK_NAME_RE.finditer(text)))
    out.locations = list(dict.fromkeys(m.group(1).title() for m in LOCATION_RE.finditer(text)))

    return out


LLM_IOC_PROMPT = """\
Extract all Indicators of Compromise (IOCs) from this scam conversation. Look for:
- Phone numbers (Indian format)
- UPI IDs (name@bank format)
- URLs and domains
- Bank account numbers
- IFSC codes
- Bank names
- Scammer names or aliases
- Reference/case numbers
- Amounts demanded
- Locations mentioned

Return ONLY valid JSON with these exact keys (all arrays):
{
  "phone_numbers": [],
  "upi_ids": [],
  "urls": [],
  "domains": [],
  "bank_accounts": [],
  "ifsc_codes": [],
  "bank_names": [],
  "scammer_names": [],
  "reference_numbers": [],
  "amounts": [],
  "locations": []
}

If no IOCs found, return empty arrays. Do NOT fabricate IOCs."""


def _to_str_list(value) -> list[str]:
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def llm_extract_iocs(text: str) -> ThreatIOCs:
    """LLM enrichment layer. Returns empty ThreatIOCs if the LLM is unavailable
    or returns garbage — never raises."""
    import json

    from app.clients.llm import chat_completion

    try:
        raw = chat_completion(
            [
                {"role": "system", "content": LLM_IOC_PROMPT},
                {"role": "user", "content": text},
            ],
            json_mode=True,
            temperature=0.0,
            timeout=20,
        )
        data = json.loads(raw)
    except Exception as exc:
        logger.warning("LLM IOC extraction unavailable (%s)", exc)
        return ThreatIOCs()

    def items(key: str) -> list[IOCItem]:
        return [IOCItem(value=v, source="llm", context="llm extraction") for v in _to_str_list(data.get(key))]

    out = ThreatIOCs(
        phone_numbers=items("phone_numbers"),
        upi_ids=items("upi_ids"),
        urls=items("urls"),
        domains=items("domains"),
        bank_accounts=items("bank_accounts"),
        ifsc_codes=items("ifsc_codes"),
        bank_names=_to_str_list(data.get("bank_names")),
        scammer_names=_to_str_list(data.get("scammer_names")),
        reference_numbers=_to_str_list(data.get("reference_numbers")),
        amounts=_to_str_list(data.get("amounts")),
        locations=_to_str_list(data.get("locations")),
    )
    return _validate(out)


def _validate(iocs: ThreatIOCs) -> ThreatIOCs:
    """Normalize + filter an IOC set (LLM output or agent-reported IOCs)."""
    phones: list[IOCItem] = []
    for item in iocs.phone_numbers:
        norm = _normalize_phone(item.value)
        if not norm or norm in LEGIT_PHONE_ALLOWLIST:
            continue
        if norm in HONEYPOT_FAKE_PHONES:
            continue
        phones.append(item.model_copy(update={"value": norm}))

    upis: list[IOCItem] = []
    for item in iocs.upi_ids:
        handle = item.value.lower().strip().rstrip(".,;:!?")
        if "@" not in handle or _looks_like_email(handle.split("@", 1)[1]):
            continue
        upis.append(item.model_copy(update={"value": handle}))

    accounts = [
        item
        for item in iocs.bank_accounts
        if item.value.isdigit()
        and 9 <= len(item.value) <= 18
        and item.value not in HONEYPOT_FAKE_ACCOUNTS
    ]

    urls = [item.model_copy(update={"value": item.value.rstrip(".,;:!?)")}) for item in iocs.urls]

    domains = iocs.domains
    for item in urls:  # ensure every URL's domain is tracked
        dom = _domain_from_url(item.value)
        if dom and all(d.value != dom for d in domains):
            domains = domains + [IOCItem(value=dom, source="url_parse", context=item.value)]

    return iocs.model_copy(
        update={
            "phone_numbers": _dedupe(phones),
            "upi_ids": _dedupe(upis),
            "bank_accounts": _dedupe(accounts),
            "urls": _dedupe(urls),
            "domains": _dedupe(domains),
            "ifsc_codes": _dedupe(
                IOCItem(value=i.value.upper(), source=i.source, context=i.context)
                for i in iocs.ifsc_codes
            ),
            "bank_names": list(dict.fromkeys(iocs.bank_names)),
            "scammer_names": list(dict.fromkeys(iocs.scammer_names)),
            "reference_numbers": list(dict.fromkeys(iocs.reference_numbers)),
            "amounts": list(dict.fromkeys(iocs.amounts)),
            "locations": list(dict.fromkeys(iocs.locations)),
        }
    )


def merge_iocs(base: ThreatIOCs, new: ThreatIOCs) -> ThreatIOCs:
    """Union of two IOC sets, deduped by (type, value)."""
    merged = ThreatIOCs(
        phone_numbers=_dedupe([*base.phone_numbers, *new.phone_numbers]),
        upi_ids=_dedupe([*base.upi_ids, *new.upi_ids]),
        urls=_dedupe([*base.urls, *new.urls]),
        domains=_dedupe([*base.domains, *new.domains]),
        bank_accounts=_dedupe([*base.bank_accounts, *new.bank_accounts]),
        ifsc_codes=_dedupe([*base.ifsc_codes, *new.ifsc_codes]),
        bank_names=list(dict.fromkeys([*base.bank_names, *new.bank_names])),
        scammer_names=list(dict.fromkeys([*base.scammer_names, *new.scammer_names])),
        reference_numbers=list(dict.fromkeys([*base.reference_numbers, *new.reference_numbers])),
        amounts=list(dict.fromkeys([*base.amounts, *new.amounts])),
        locations=list(dict.fromkeys([*base.locations, *new.locations])),
    )
    return merged


def extract_all(text: str, *, use_llm: bool = False) -> ThreatIOCs:
    """Regex first, optional LLM enrichment, merged and validated."""
    regex_iocs = extract_iocs(text)
    if not use_llm:
        return regex_iocs
    return merge_iocs(regex_iocs, llm_extract_iocs(text))


def iocs_as_plain_dict(iocs: ThreatIOCs) -> dict[str, list[str]]:
    """Compact {type: [values]} view for the honeypot turn response."""
    return {
        "phone_numbers": [i.value for i in iocs.phone_numbers],
        "upi_ids": [i.value for i in iocs.upi_ids],
        "urls": [i.value for i in iocs.urls],
        "bank_accounts": [i.value for i in iocs.bank_accounts],
        "names": iocs.scammer_names,
        "reference_numbers": iocs.reference_numbers,
    }
