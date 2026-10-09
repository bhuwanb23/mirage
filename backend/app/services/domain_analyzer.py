"""Domain-level scam signal analysis (Phase 1.2, Steps 3-8).

Takes a ParsedURL and returns a scored DomainAnalysis with red flags.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Optional

from app.services.url_extractor import ParsedURL
from app.utils.constants import (
    BRAND_KEYWORDS,
    LEGITIMATE_DOMAINS,
    SUSPICIOUS_PATH_KEYWORDS,
    SUSPICIOUS_TLDS,
)

# ------------------------------------------------------------------
# Score weights (spec table, Step 8)
# ------------------------------------------------------------------
WEIGHTS = {
    "age_lt_7": 0.30,
    "age_lt_30": 0.20,
    "lookalike": 0.25,
    "suspicious_tld": 0.10,
    "no_https": 0.05,
    "obfuscation": 0.15,
    "ip_domain": 0.25,
    "path_keywords": 0.10,
    "shortener": 0.10,
    "age_gt_2y": -0.15,
    "official_match": -0.50,
}

_MAX_RED_FLAGS = 10

@dataclass
class DomainAnalysis:
    parsed: ParsedURL
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
    suspicious_path_keywords: list[str] = field(default_factory=list)
    red_flags: list[str] = field(default_factory=list)

    @property
    def url(self) -> str:
        return self.parsed.raw

    @property
    def domain(self) -> str:
        return self.parsed.domain

    @property
    def tld(self) -> str:
        return self.parsed.tld

# ------------------------------------------------------------------
# Public entry point
# ------------------------------------------------------------------

def analyze_domain(parsed: ParsedURL) -> DomainAnalysis:
    """Run all domain signals on a single parsed URL.

    Fast-path: if the domain is in the official legitimate list, return
    immediately with a clean analysis (is_suspicious=False, score=0.0).
    """
    result = DomainAnalysis(parsed=parsed, https=parsed.scheme == "https")
    result.url_obfuscation = parsed.has_obfuscation
    result.suspicious_tld = _tld_is_suspicious(parsed.tld)
    result.suspicious_path_keywords = _path_keywords(parsed.path)

    # ---- official domain fast-path ------------------------------------
    if _is_official_domain(parsed.domain):
        result.is_suspicious = False
        result.risk_score = 0.0
        result.https = parsed.scheme == "https"
        return result

    # ---- official-domain-as-standalone checks already done,
    #      now run the full signal pipeline ----------------------------
    _apply_age_signal(result)
    _apply_lookalike_signal(result)
    _apply_tld_signal(result)
    _apply_https_signal(result)
    _apply_obfuscation_signal(result)
    _apply_path_keyword_signal(result)
    _apply_shortener_signal(result)

    result.risk_score = _clamp(_aggregate_score(result))
    result.is_suspicious = result.risk_score >= 0.3
    result.red_flags = _build_red_flags(result)
    return result

# ------------------------------------------------------------------
# Signals
# ------------------------------------------------------------------

def _apply_age_signal(result: DomainAnalysis) -> None:
    age = _whois_age_days(result.parsed.domain)
    result.domain_age_days = age
    if age is None:
        result.red_flags.append("WHOIS data unavailable")
        return
    if age < 7:
        result.red_flags.append(f"Domain is only {age} days old")
    elif age < 30:
        result.red_flags.append(f"Domain is only {age} days old")
    elif age > 730:
        # legitimacy signal — tracked via score, not a red flag
        pass

def _apply_lookalike_signal(result: DomainAnalysis) -> None:
    target = _find_lookalike(result.parsed.domain)
    if target is not None:
        result.is_lookalike = True
        result.lookalike_target = target
        result.contains_brand_keyword = True
        kw = _matching_brand_keyword(result.parsed.domain)
        result.brand_keyword = kw
        result.red_flags.append(
            f"Contains brand name '{kw}' but is NOT the official domain"
        )

def _apply_tld_signal(result: DomainAnalysis) -> None:
    if result.suspicious_tld:
        result.red_flags.append(f"Uses suspicious TLD {result.parsed.tld}")

def _apply_https_signal(result: DomainAnalysis) -> None:
    if not result.https:
        result.red_flags.append("No HTTPS encryption")

def _apply_obfuscation_signal(result: DomainAnalysis) -> None:
    if result.url_obfuscation:
        result.red_flags.append("URL contains an obfuscation '@' symbol")

def _apply_path_keyword_signal(result: DomainAnalysis) -> None:
    if result.suspicious_path_keywords:
        result.red_flags.append(
            "URL path contains suspicious keywords: "
            + ", ".join(result.suspicious_path_keywords)
        )

def _apply_shortener_signal(result: DomainAnalysis) -> None:
    if result.parsed.is_shortener:
        result.red_flags.append("Shortened URL — destination hidden")

# ------------------------------------------------------------------
# Aggregation
# ------------------------------------------------------------------

def _aggregate_score(result: DomainAnalysis) -> float:
    score = 0.0
    if result.parsed.is_ip_domain:
        score += WEIGHTS["ip_domain"]
    if result.domain_age_days is not None:
        if result.domain_age_days < 7:
            score += WEIGHTS["age_lt_7"]
        elif result.domain_age_days < 30:
            score += WEIGHTS["age_lt_30"]
        elif result.domain_age_days > 730:
            score += WEIGHTS["age_gt_2y"]
    if result.is_lookalike:
        score += WEIGHTS["lookalike"]
    if result.suspicious_tld:
        score += WEIGHTS["suspicious_tld"]
    if not result.https:
        score += WEIGHTS["no_https"]
    if result.url_obfuscation:
        score += WEIGHTS["obfuscation"]
    if result.suspicious_path_keywords:
        score += WEIGHTS["path_keywords"]
    if result.parsed.is_shortener:
        score += WEIGHTS["shortener"]
    if _is_official_domain(result.parsed.domain):
        score += WEIGHTS["official_match"]
    return score

def _build_red_flags(result: DomainAnalysis) -> list[str]:
    flags = list(result.red_flags)
    # dedupe, cap
    seen: set[str] = set()
    out: list[str] = []
    for f in flags:
        if f not in seen:
            seen.add(f)
            out.append(f)
    return out[:_MAX_RED_FLAGS]

# ------------------------------------------------------------------
# Lookalike detection (Levenshtein + brand keyword)
# ------------------------------------------------------------------

def _find_lookalike(domain: str) -> str | None:
    """Return the closest official domain if it is a plausible lookalike.

    A domain is a lookalike when it contains a known brand keyword AND is
    not itself an official domain. Levenshtein distance is used as a
    secondary confirmation: a close match (<= 3) is always a lookalike;
    a brand-keyword match with a longer distance is also flagged because
    scammers routinely register domains like sbi-kyc-verify.xyz that
    contain the brand but are nowhere near the official domain in edit
    distance.
    """
    if _is_official_domain(domain):
        return None

    kw = _matching_brand_keyword(domain)
    if kw is None:
        return None

    candidates = [d for d in LEGITIMATE_DOMAINS if kw in d]
    if not candidates:
        return None

    best: str | None = None
    best_dist = 10**9
    for c in candidates:
        d = _levenshtein(c, domain)
        if d < best_dist:
            best_dist = d
            best = c

    # Brand-keyword match with a non-official domain is always a lookalike.
    # Levenshtein <= 3 is the strong signal; longer distances still count
    # when a brand keyword is present.
    if best is not None and (best_dist <= 3 or kw is not None):
        return best
    return None

def _matching_brand_keyword(domain: str) -> str | None:
    """Return the brand keyword contained in `domain`, or None."""
    lower = domain.lower()
    for kw in BRAND_KEYWORDS:
        if kw in lower:
            return kw
    return None

# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _is_official_domain(domain: str) -> bool:
    return domain in LEGITIMATE_DOMAINS

def _tld_is_suspicious(tld: str) -> bool:
    return tld in SUSPICIOUS_TLDS

def _path_keywords(path: str) -> list[str]:
    lower = (path or "").lower()
    found: list[str] = []
    for kw in SUSPICIOUS_PATH_KEYWORDS:
        if kw in lower:
            found.append(kw)
    return found

def _whois_age_days(domain: str) -> int | None:
    """Return domain age in days from WHOIS, or None on failure.

    Import is lazy so the module loads even when python-whois is absent.
    """
    try:
        import python_whois as whois
    except Exception:
        return None

    try:
        w = whois.whois(domain)
    except Exception:
        return None

    created = getattr(w, "creation_date", None)
    if not created:
        return None

    # python-whois can return a single date or a list.
    if isinstance(created, list):
        created = created[0]
    if not created:
        return None

    try:
        if isinstance(created, date):
            birth = created
        else:
            birth = created.date()
    except Exception:
        return None

    return (date.today() - birth).days

def _levenshtein(a: str, b: str) -> int:
    """Classic edit-distance. Small-alphabet, short strings — fine as-is."""
    if a == b:
        return 0
    la, lb = len(a), len(b)
    if not la or not lb:
        return max(la, lb)

    prev = list(range(lb + 1))
    curr = [0] * (lb + 1)
    for i in range(1, la + 1):
        curr[0] = i
        for j in range(1, lb + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            curr[j] = min(
                prev[j] + 1,
                curr[j - 1] + 1,
                prev[j - 1] + cost,
            )
        prev, curr = curr, prev
    return prev[lb]

def _clamp(x: float) -> float:
    return max(0.0, min(1.0, x))
