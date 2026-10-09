"""Structured stdout logging (Render captures stdout as logs)."""

from __future__ import annotations

import json
import logging
import sys
import time
from datetime import datetime, timezone

_VALID_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        # Extra fields attached via `extra={...}` on logger calls
        extra_keys = (
            "method", "path", "status", "duration_ms",
            "model", "tokens_in", "tokens_out", "latency_ms",
        )
        for key in extra_keys:
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        return json.dumps(payload, ensure_ascii=False)


def setup_logging(level: str = "INFO") -> None:
    log_level = level.upper() if level.upper() in _VALID_LEVELS else "INFO"

    root = logging.getLogger()
    root.setLevel(log_level)

    # Remove handlers uvicorn may have added, then attach ours once.
    for handler in list(root.handlers):
        root.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root.addHandler(handler)

    # Quieten noisy libs
    for noisy in ("httpx", "httpcore", "urllib3", "neo4j"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def log_incoming_request(method: str, path: str, status: int, duration_ms: float) -> None:
    logging.getLogger("mirage.request").info(
        "%s %s -> %s",
        method,
        path,
        status,
        extra={
            "method": method, "path": path,
            "status": status, "duration_ms": round(duration_ms, 2),
        },
    )


def timed(fn):
    """Decorator: measures wall time of a function call and logs it."""
    from functools import wraps

    @wraps(fn)
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = fn(*args, **kwargs)
        elapsed = (time.perf_counter() - start) * 1000
        logging.getLogger("mirage.timed").info(
            "%s took %.1fms", getattr(fn, "__name__", "call"), elapsed
        )
        return result

    return wrapper
