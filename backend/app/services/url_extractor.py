"""URL extraction + parsing helpers (Phase 1.2, Step 1-2).

Pure functions — no network, no WHOIS. Easy to test offline.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlparse

from app.utils.constants import URL_SHORTENER_DOMAINS

# Matches http/https URLs and bare www.<domain> occurrences.
_URL_RE = re.compile(
    r"""\b(?:https?://|www\.)"""
    r"""[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?"""
    r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?)+"""
    r"""(?::\d+)?"""
    r"""(?:/[^\s\"'<>()]*)?""",
    re.IGNORECASE,
)

# Bare domain-style patterns without a scheme (e.g. "sbi-kyc-verify.xyz/update")
# Matches a domain ending in a suspicious TLD, optionally followed by a path.
_BARE_DOMAIN_RE = re.compile(
    r"""\b([A-Za-z0-9][A-Za-z0-9.-]*\.(?:xyz|top|click|link|buzz|tk|ml|ga|cf|gq|pw|cc|ws|info|icu|cam|loan|work))"""
    r"""(?:/\S*)?""",
    re.IGNORECASE,
)

_IP_DOMAIN_RE = re.compile(
    r"""\b(?:\d{1,3}\.){3}\d{1,3}\b""",
)


@dataclass(frozen=True)
class ParsedURL:
    raw: str
    scheme: str
    domain: str
    subdomain: str
    tld: str
    path: str
    query: str
    is_shortener: bool
    is_ip_domain: bool
    has_obfuscation: bool  # contains @ in authority


def extract_urls(text: str) -> list[ParsedURL]:
    """Extract every URL-like token from `text`.

    Returns an empty list when nothing is found. Handles:
    - http/https URLs
    - www.<domain> occurrences
    - bare suspicious-TLD domains (heuristic, no scheme)
    """
    if not text:
        return []

    seen: set[str] = set()
    results: list[ParsedURL] = []

    for raw in _iter_url_strings(text):
        normalized = raw.lower().rstrip(".,;:)!")
        if normalized in seen:
            continue
        seen.add(normalized)
        parsed = _parse_one(normalized)
        if parsed is not None:
            results.append(parsed)

    return results


def _iter_url_strings(text: str):
    """Yield candidate URL strings from the text, including bare domains."""
    for m in _URL_RE.finditer(text):
        yield m.group(0)

    # Bare suspicious-domain heuristic (no scheme). Only yield when the
    # domain ends in a suspicious TLD — reduces noise from random words.
    if not any(_URL_RE.finditer(text)):
        for m in _BARE_DOMAIN_RE.finditer(text):
            candidate = "http://" + m.group(1)
            yield candidate


def _parse_one(raw: str) -> ParsedURL | None:
    """Parse a single URL string into a ParsedURL, or None if unparseable."""
    try:
        # Add a scheme so urlparse can extract the domain from "www.x" forms.
        if not raw.startswith(("http://", "https://")):
            raw_with_scheme = "http://" + raw
        else:
            raw_with_scheme = raw

        parsed = urlparse(raw_with_scheme)
        netloc = parsed.netloc or parsed.path
        if not netloc:
            return None

        # Strip port and userinfo for domain analysis.
        authority = netloc
        has_obfuscation = "@" in netloc
        if "@" in netloc:
            authority = netloc.split("@")[-1]
        if ":" in authority:
            authority = authority.split(":")[0]

        domain = authority.lower()
        if not domain or domain in ("localhost", "127.0.0.1", "[::1]"):
            return None

        tld = _extract_tld(domain)
        subdomain = _extract_subdomain(domain, tld)

        return ParsedURL(
            raw=raw,
            scheme="https" if raw_with_scheme.startswith("https") else "http",
            domain=domain,
            subdomain=subdomain,
            tld=tld,
            path=parsed.path or "",
            query=parsed.query or "",
            is_shortener=_is_shortener(domain),
            is_ip_domain=bool(_IP_DOMAIN_RE.fullmatch(domain)),
            has_obfuscation=has_obfuscation,
        )
    except Exception:
        return None


def _extract_tld(domain: str) -> str:
    """Return the longest matching TLD from the known TLD sets.

    Falls back to the last dot-segment when no known TLD matches.
    """
    from app.utils.constants import LEGITIMATE_TLDS, SUSPICIOUS_TLDS

    dots = domain.split(".")
    for candidate_len in (3, 2, 1):
        if len(dots) >= candidate_len:
            candidate = "." + ".".join(dots[-candidate_len:])
            if candidate in LEGITIMATE_TLDS or candidate in SUSPICIOUS_TLDS:
                return candidate
    return "." + dots[-1] if dots else ""


def _extract_subdomain(domain: str, tld: str) -> str:
    """Return the subdomain portion, or '' when the domain has none.

    The registered domain is the rightmost label + the TLD (e.g. for
    ``sub.example.com`` the registered domain is ``example.com`` and the
    subdomain is ``sub``). Multi-part TLDs like ``.co.in`` count as one
    unit, so ``sbi.co.in`` has no subdomain.
    """
    suffix = tld.lstrip(".")
    if not suffix:
        return ""
    tld_parts = suffix.count(".") + 1
    labels = domain.split(".")
    registered_labels = tld_parts + 1
    if len(labels) <= registered_labels:
        return ""
    return ".".join(labels[: -registered_labels])


def _is_shortener(domain: str) -> bool:
    """True when the registered domain matches a known shortener."""
    return domain in URL_SHORTENER_DOMAINS or any(
        domain.endswith("." + sd) for sd in URL_SHORTENER_DOMAINS
    )
