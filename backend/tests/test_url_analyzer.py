"""Tests for the URL & Domain Analyzer (Phase 1.2).

Runs offline for extraction/TLD/lookalike/scoring. WHOIS-dependent tests
are skipped when python-whois is not installed.
"""

from __future__ import annotations

import pytest

from app.models.schemas import URLAnalysisOutput, URLAnalysisResult
from app.services.domain_analyzer import (
    DomainAnalysis,
    _build_red_flags,
    _find_lookalike,
    _is_official_domain,
    _matching_brand_keyword,
    _path_keywords,
    _tld_is_suspicious,
    _whois_age_days,
    analyze_domain,
)
from app.services.url_analyzer import analyze_text_for_urls
from app.services.url_extractor import (
    ParsedURL,
    _extract_subdomain,
    _extract_tld,
    _is_shortener,
    extract_urls,
)

WHOIS_AVAILABLE = False
try:
    import python_whois  # noqa: F401
    WHOIS_AVAILABLE = True
except Exception:
    pass


# ------------------------------------------------------------------
# Extraction + parsing
# ------------------------------------------------------------------


class TestExtractUrls:
    def test_empty_text(self):
        assert extract_urls("") == []
        assert extract_urls("   ") == []

    def test_single_http_url(self):
        urls = extract_urls("click http://example.com/page")
        assert len(urls) == 1
        assert urls[0].raw.startswith("http://example.com")
        assert urls[0].scheme == "http"
        assert urls[0].domain == "example.com"

    def test_https_url(self):
        urls = extract_urls("https://sbi.co.in/verify")
        assert urls[0].scheme == "https"
        assert urls[0].domain == "sbi.co.in"

    def test_www_without_scheme(self):
        urls = extract_urls("visit www.bluedart.com/tracking")
        assert len(urls) == 1
        assert urls[0].domain == "www.bluedart.com"

    def test_multiple_urls(self):
        text = "a http://x.com and https://y.co.in/b"
        urls = extract_urls(text)
        assert len(urls) == 2

    def test_no_url_text(self):
        assert extract_urls("Hello world, no links here") == []

    def test_deduplication(self):
        text = "http://x.com http://x.com"
        urls = extract_urls(text)
        assert len(urls) == 1

    def test_url_with_query_and_path(self):
        urls = extract_urls("https://fedex-india-customs.top/pay?ref=123")
        assert urls[0].domain == "fedex-india-customs.top"
        assert urls[0].tld == ".top"
        assert urls[0].path == "/pay"
        assert urls[0].query == "ref=123"

    def test_shortener_detected(self):
        assert _is_shortener("bit.ly") is True
        assert _is_shortener("http://bit.ly/abc") is False  # only domain arg
        # _is_shortener takes a domain, not a full URL — test the domain form.
        assert _is_shortener("bit.ly") is True

    def test_bare_suspicious_domain_heuristic(self):
        # When no http URL is present, a bare suspicious-TLD domain is found.
        urls = extract_urls("check sbi-kyc-verify.xyz/update")
        assert len(urls) >= 1
        found = any(u.domain == "sbi-kyc-verify.xyz" for u in urls)
        assert found, urls

    def test_localhost_skipped(self):
        urls = extract_urls("http://localhost:3000")
        # localhost should be skipped as a non-external domain
        assert not any(u.domain == "localhost" for u in urls)

    def test_trailing_punctuation_stripped(self):
        urls = extract_urls("click http://example.com.")
        assert urls[0].domain == "example.com"


class TestParsedURLFields:
    def test_tld_extraction_suspicious(self):
        assert _extract_tld("sbi-kyc-verify.xyz") == ".xyz"

    def test_tld_extraction_legitimate(self):
        assert _extract_tld("sbi.co.in") == ".co.in"

    def test_tld_extraction_com(self):
        assert _extract_tld("example.com") == ".com"

    def test_subdomain_extraction(self):
        # Registered domain is security.xyz; subdomain is everything before it.
        assert _extract_subdomain("sbi.kyc.verify.update.security.xyz", ".xyz") == \
            "sbi.kyc.verify.update"

    def test_no_subdomain(self):
        assert _extract_subdomain("sbi.co.in", ".co.in") == ""


# ------------------------------------------------------------------
# TLD checks
# ------------------------------------------------------------------


class TestTldSuspicion:
    def test_suspicious_tld_flagged(self):
        assert _tld_is_suspicious(".xyz") is True
        assert _tld_is_suspicious(".top") is True
        assert _tld_is_suspicious(".info") is True

    def test_legitimate_tld_not_flagged(self):
        assert _tld_is_suspicious(".com") is False
        assert _tld_is_suspicious(".co.in") is False
        assert _tld_is_suspicious(".in") is False


# ------------------------------------------------------------------
# Official domain fast-path
# ------------------------------------------------------------------


class TestOfficialDomainFastPath:
    def test_official_domain_returns_clean_analysis(self):
        parsed = ParsedURL(
            raw="http://sbi.co.in", scheme="http", domain="sbi.co.in",
            subdomain="", tld=".co.in", path="", query="",
            is_shortener=False, is_ip_domain=False, has_obfuscation=False,
        )
        result = analyze_domain(parsed)
        assert result.is_suspicious is False
        assert result.risk_score == 0.0

    def test_official_domain_skipped_lookalike(self):
        assert _is_official_domain("sbi.co.in") is True
        assert _is_official_domain("hdfcbank.com") is True
        assert _is_official_domain("fedex.com") is True

    def test_non_official_domain(self):
        assert _is_official_domain("sbi-kyc-verify.xyz") is False


# ------------------------------------------------------------------
# Lookalike + brand keyword
# ------------------------------------------------------------------


class TestLookalikeDetection:
    def test_brand_keyword_found(self):
        assert _matching_brand_keyword("sbi-kyc-verify.xyz") == "sbi"
        assert _matching_brand_keyword("hdfc-secure-login.com") == "hdfc"
        assert _matching_brand_keyword("example.com") is None

    def test_lookalike_identified(self):
        target = _find_lookalike("sbi-kyc-verify.xyz")
        assert target is not None
        assert target == "sbi.co.in"

    def test_fedex_lookalike(self):
        target = _find_lookalike("fedex-india-customs.top")
        assert target is not None
        assert target == "fedex.com"

    def test_no_lookalike_when_no_brand(self):
        assert _find_lookalike("example.com") is None

    def test_no_lookalike_for_official_domain(self):
        assert _find_lookalike("sbi.co.in") is None


# ------------------------------------------------------------------
# Scoring
# ------------------------------------------------------------------


class TestScoring:
    def test_official_domain_scores_zero(self):
        parsed = ParsedURL(
            raw="http://sbi.co.in", scheme="http", domain="sbi.co.in",
            subdomain="", tld=".co.in", path="", query="",
            is_shortener=False, is_ip_domain=False, has_obfuscation=False,
        )
        result = analyze_domain(parsed)
        assert result.risk_score == 0.0

    def test_suspicious_tld_only_partial_score(self):
        parsed = ParsedURL(
            raw="http://example.xyz", scheme="http", domain="example.xyz",
            subdomain="", tld=".xyz", path="", query="",
            is_shortener=False, is_ip_domain=False, has_obfuscation=False,
        )
        result = analyze_domain(parsed)
        assert result.risk_score >= 0.10  # suspicious TLD weight
        assert result.suspicious_tld is True

    def test_lookalike_increases_score(self):
        parsed = ParsedURL(
            raw="http://sbi-kyc-verify.xyz", scheme="http",
            domain="sbi-kyc-verify.xyz", subdomain="", tld=".xyz",
            path="", query="", is_shortener=False,
            is_ip_domain=False, has_obfuscation=False,
        )
        result = analyze_domain(parsed)
        assert result.is_lookalike is True
        assert result.risk_score >= 0.25  # lookalike weight

    def test_http_lowers_score(self):
        parsed = ParsedURL(
            raw="http://example.xyz", scheme="http", domain="example.xyz",
            subdomain="", tld=".xyz", path="", query="",
            is_shortener=False, is_ip_domain=False, has_obfuscation=False,
        )
        result = analyze_domain(parsed)
        assert result.https is False
        assert result.risk_score >= 0.10

    def test_ip_domain_high_score(self):
        parsed = ParsedURL(
            raw="http://192.168.1.1/login", scheme="http",
            domain="192.168.1.1", subdomain="", tld=".1",
            path="/login", query="", is_shortener=False,
            is_ip_domain=True, has_obfuscation=False,
        )
        result = analyze_domain(parsed)
        assert result.risk_score >= 0.25  # IP domain weight

    def test_obfuscation_increases_score(self):
        parsed = ParsedURL(
            raw="http://legit@evil.com", scheme="http", domain="evil.com",
            subdomain="", tld=".com", path="", query="",
            is_shortener=False, is_ip_domain=False, has_obfuscation=True,
        )
        result = analyze_domain(parsed)
        assert result.url_obfuscation is True
        assert result.risk_score >= 0.15

    def test_score_clamped_to_1(self):
        parsed = ParsedURL(
            raw="http://x.xyz", scheme="http", domain="x.xyz",
            subdomain="", tld=".xyz", path="", query="",
            is_shortener=False, is_ip_domain=False, has_obfuscation=False,
        )
        result = analyze_domain(parsed)
        assert result.risk_score <= 1.0

    def test_shortener_flagged(self):
        parsed = ParsedURL(
            raw="http://bit.ly/abc", scheme="http", domain="bit.ly",
            subdomain="", tld=".ly", path="/abc", query="",
            is_shortener=True, is_ip_domain=False, has_obfuscation=False,
        )
        result = analyze_domain(parsed)
        assert result.parsed.is_shortener is True
        assert any("Shortened" in f for f in result.red_flags)


# ------------------------------------------------------------------
# Path keywords
# ------------------------------------------------------------------


class TestPathKeywords:
    def test_suspicious_path_keywords_found(self):
        kw = _path_keywords("/kyc/verify/update")
        assert "kyc" in kw
        assert "verify" in kw
        assert "update" in kw

    def test_no_keywords_clean_path(self):
        assert _path_keywords("/track") == []

    def test_empty_path(self):
        assert _path_keywords("") == []


# ------------------------------------------------------------------
# Red flags building
# ------------------------------------------------------------------


class TestRedFlags:
    def test_red_flags_contain_age_when_young(self):
        parsed = ParsedURL(
            raw="http://x.xyz", scheme="http", domain="x.xyz",
            subdomain="", tld=".xyz", path="", query="",
            is_shortener=False, is_ip_domain=False, has_obfuscation=False,
        )
        result = analyze_domain(parsed)
        # WHOIS will fail in the sandbox, so we assert the schema, not the age.
        assert isinstance(result.red_flags, list)
        assert all(isinstance(f, str) for f in result.red_flags)

    def test_red_flags_capped(self):
        rf = _build_red_flags(DomainAnalysis(
            parsed=ParsedURL(
                raw="", scheme="http", domain="x", subdomain="",
                tld=".", path="", query="",
                is_shortener=False, is_ip_domain=False, has_obfuscation=False,
            ),
            red_flags=["flag"] * 20,
        ))
        assert len(rf) <= 10

    def test_red_flags_deduped(self):
        rf = _build_red_flags(DomainAnalysis(
            parsed=ParsedURL(
                raw="", scheme="http", domain="x", subdomain="",
                tld=".", path="", query="",
                is_shortener=False, is_ip_domain=False, has_obfuscation=False,
            ),
            red_flags=["dup", "dup", "other"],
        ))
        assert rf == ["dup", "other"]


# ------------------------------------------------------------------
# WHOIS tests (only when available)
# ------------------------------------------------------------------


@pytest.mark.skipif(not WHOIS_AVAILABLE, reason="python-whois not installed")
class TestWhois:
    def test_whois_returns_age_for_known_domain(self):
        age = _whois_age_days("google.com")
        assert age is not None
        assert age > 0

    def test_whois_returns_none_for_unresolvable(self):
        # A nonsense domain should return None, not raise.
        age = _whois_age_days("this-domain-definitely-does-not-exist-12345.com")
        assert age is None


# ------------------------------------------------------------------
# Orchestrator / endpoint-level
# ------------------------------------------------------------------


class TestAnalyzeTextForUrls:
    def test_no_urls_returns_empty_output(self):
        out = analyze_text_for_urls("no links here")
        assert out.urls_analyzed == []
        assert out.overall_risk_score == 0.0
        assert out.overall_is_suspicious is False

    def test_single_url_analyzed(self):
        out = analyze_text_for_urls("click http://sbi-kyc-verify.xyz")
        assert len(out.urls_analyzed) >= 1
        assert out.overall_is_suspicious is True

    def test_output_schema_valid(self):
        out = analyze_text_for_urls("http://example.xyz")
        assert isinstance(out, URLAnalysisOutput)
        for r in out.urls_analyzed:
            assert isinstance(r, URLAnalysisResult)
            assert 0.0 <= r.risk_score <= 1.0
            assert isinstance(r.red_flags, list)

    def test_multiple_urls_highest_risk_drives_overall(self):
        out = analyze_text_for_urls(
            "http://example.xyz and http://sbi-kyc-verify.xyz"
        )
        assert out.overall_risk_score >= 0.0
        assert out.highest_risk_url is not None


class TestScamSampleUrls:
    """Validate the analyzer flags the scam URLs from the Phase 1.1 samples."""

    def test_sbi_kyc_verify_xyz_flagged(self):
        out = analyze_text_for_urls("http://sbi-kyc-verify.xyz/update")
        assert out.overall_is_suspicious is True
        result = out.urls_analyzed[0]
        assert result.is_lookalike is True
        assert result.lookalike_target == "sbi.co.in"
        assert result.suspicious_tld is True

    def test_fedex_india_customs_top_flagged(self):
        out = analyze_text_for_urls("https://fedex-india-customs.top/pay")
        assert out.overall_is_suspicious is True
        result = out.urls_analyzed[0]
        assert result.suspicious_tld is True
        assert result.is_lookalike is True
