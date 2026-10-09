"""URL analyzer orchestrator (Phase 1.2).

Entry point for the URL/domain analysis service layer. Extracts URLs from
text, analyzes each domain, and returns the full result set plus an
overall risk summary (highest-risk URL drives the overall verdict).
"""

from __future__ import annotations

from app.models.schemas import URLAnalysisOutput, URLAnalysisResult
from app.services.domain_analyzer import analyze_domain
from app.services.url_extractor import extract_urls


def analyze_text_for_urls(text: str) -> URLAnalysisOutput:
    """Extract URLs from `text` and analyze each one.

    When no URLs are found, returns an empty output with a zero risk score.
    When multiple URLs are present, the highest-risk URL drives the overall
    verdict.
    """
    parsed_list = extract_urls(text)
    if not parsed_list:
        return URLAnalysisOutput()

    results: list[URLAnalysisResult] = []
    highest: URLAnalysisResult | None = None

    for parsed in parsed_list:
        analysis = analyze_domain(parsed)
        result = _to_result(analysis)
        results.append(result)
        if highest is None or analysis.risk_score > highest.risk_score:
            highest = result

    overall = highest.risk_score if highest else 0.0
    return URLAnalysisOutput(
        urls_analyzed=results,
        overall_risk_score=overall,
        overall_is_suspicious=overall >= 0.3,
        highest_risk_url=highest.url if highest else None,
    )


def _to_result(analysis) -> URLAnalysisResult:
    return URLAnalysisResult(
        url=analysis.url,
        domain=analysis.domain,
        tld=analysis.tld,
        is_suspicious=analysis.is_suspicious,
        risk_score=analysis.risk_score,
        domain_age_days=analysis.domain_age_days,
        registrar=analysis.registrar,
        https=analysis.https,
        is_lookalike=analysis.is_lookalike,
        lookalike_target=analysis.lookalike_target,
        contains_brand_keyword=analysis.contains_brand_keyword,
        brand_keyword=analysis.brand_keyword,
        suspicious_tld=analysis.suspicious_tld,
        url_obfuscation=analysis.url_obfuscation,
        suspicious_path_keywords=analysis.suspicious_path_keywords,
        red_flags=analysis.red_flags,
    )
