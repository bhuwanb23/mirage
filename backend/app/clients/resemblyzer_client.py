"""Resemblyzer voice-embedding client — OPTIONAL (voice clone phase).

Resemblyzer depends on webrtcvad, which has no Python 3.13 Windows wheels.
This module imports lazily and degrades gracefully so the app boots without it.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Optional

logger = logging.getLogger("mirage.resemblyzer")

_import_error: Optional[str] = None
_model = None


@lru_cache(maxsize=1)
def is_available() -> bool:
    """True if resemblyzer imports successfully. Logs the reason otherwise."""
    global _import_error
    try:
        import resemblyzer  # noqa: F401

        return True
    except Exception as exc:
        _import_error = str(exc)
        logger.warning("Resemblyzer unavailable (voice features disabled): %s", exc)
        return False


def _load_model():
    global _model
    if _model is None:
        from resemblyzer import VoiceEncoder

        _model = VoiceEncoder()
    return _model


def embed_wav(file_path: str) -> Optional[list[float]]:
    """Compute a 256-d embedding for a wav file. None if unavailable."""
    if not is_available():
        logger.warning("embed_wav skipped - resemblyzer unavailable: %s", _import_error)
        return None
    try:
        import numpy as np
        from resemblyzer import preprocess_wav

        wav = preprocess_wav(file_path)
        embedding = _load_model().embed_utterance(wav)
        return np.asarray(embedding, dtype=float).tolist()
    except Exception as exc:
        logger.error("embed_wav failed: %s", exc)
        return None


def similarity(emb_a: list[float], emb_b: list[float]) -> float:
    """Cosine similarity between two embeddings, 0..1."""
    import math

    dot = sum(a * b for a, b in zip(emb_a, emb_b))
    norm_a = math.sqrt(sum(a * a for a in emb_a))
    norm_b = math.sqrt(sum(b * b for b in emb_b))
    if not norm_a or not norm_b:
        return 0.0
    return max(0.0, min(1.0, dot / (norm_a * norm_b)))


def availability_report() -> dict:
    ok = is_available()
    return {"available": ok, "detail": "ok" if ok else (_import_error or "not installed")}
