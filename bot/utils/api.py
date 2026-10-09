"""HTTP client for the Mirage backend."""

from __future__ import annotations

import os

import httpx

API_URL = os.getenv("MIRAGE_API_URL", "http://localhost:8000").rstrip("/")

TIMEOUT = httpx.Timeout(30.0, connect=5.0)


def _get(path: str) -> dict | None:
    try:
        resp = httpx.get(f"{API_URL}{path}", timeout=TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return None


def _post(path: str, payload: dict) -> dict | None:
    try:
        resp = httpx.post(f"{API_URL}{path}", json=payload, timeout=TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return None


def health() -> dict | None:
    return _get("/health")


def analyze_text(text: str) -> dict | None:
    """POST /analyze/text — Phase 2 endpoint, returns None until it exists."""
    return _post("/analyze/text", {"text": text})


def analyze_image(payload: dict) -> dict | None:
    """POST /analyze/image — Phase 2 endpoint, returns None until it exists."""
    return _post("/analyze/image", payload)
