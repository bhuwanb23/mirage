"""Pytest configuration for Mirage backend tests.

Samples are loaded from test_samples.json. LLM-dependent tests use a patched
app.clients.llm.chat_completion so they never require API keys.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

TEST_DIR = Path(__file__).resolve().parent
SAMPLES_PATH = TEST_DIR / "test_samples.json"


def load_samples() -> list[dict]:
    with SAMPLES_PATH.open(encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="session")
def samples() -> list[dict]:
    return load_samples()


def _json_response(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False)


def _patch_completion(response=None, side_effect=None):
    """Patch app.services.scam_analyzer.chat_completion.

    Pass either `response` (a str returned on every call) or `side_effect`
    (an exception or callable, forwarded to unittest.mock.patch).
    """
    from unittest.mock import patch

    kwargs: dict = {}
    if response is not None:
        kwargs["return_value"] = response
    if side_effect is not None:
        kwargs["side_effect"] = side_effect
    return patch("app.services.scam_analyzer.chat_completion", **kwargs)


# A realistic-looking scam verdict the LLM might return for a bank KYC scam.
_BANK_KYC_LLM_JSON = {
    "is_scam": True,
    "confidence": 0.95,
    "scam_type": "bank_kyc",
    "risk_level": "critical",
    "red_flags": [
        "asks for ATM PIN",
        "asks for OTP",
        "suspicious domain sbi-kyc-verify.xyz",
        "extreme urgency 24 hours",
        "helpline is a mobile number",
    ],
    "stages_detected": ["hook", "authority", "urgency", "payment"],
    "summary": (
        "This is a Bank KYC scam. The message claims your SBI account will be "
        "blocked within 24 hours and asks you to click a link to a fake website. "
        "It asks for your ATM PIN and OTP, which no real bank will ever request."
    ),
    "recommended_action": "Do NOT click any links",
}


@pytest.fixture
def bank_kyc_llm_json() -> str:
    return _json_response(_BANK_KYC_LLM_JSON)
