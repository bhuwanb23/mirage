"""In-memory ring buffer of recent analyze / activity events for the dashboard."""

from __future__ import annotations

import threading
from collections import deque
from datetime import datetime, timezone
from typing import Any, Optional

_MAX = 50
_lock = threading.Lock()
_events: deque[dict[str, Any]] = deque(maxlen=_MAX)


def record_analyze(
    *,
    is_scam: bool,
    scam_type: Optional[str],
    confidence: float,
    input_type: str = "text",
    summary: str = "",
    created_at: Optional[str] = None,
) -> None:
    """Append a recent analyze event (oldest dropped when full).

    `created_at` is optional so the demo seeder can back-date events
    (plan §7.3); normal callers get "now".
    """
    event = {
        "type": "scam_detected" if is_scam else "analyze_safe",
        "scam_type": scam_type or "unknown",
        "confidence": confidence,
        "input_type": input_type,
        "summary": summary
        or (
            f"{'Scam' if is_scam else 'Safe'}: {scam_type or input_type}"
        ),
        "created_at": created_at or datetime.now(timezone.utc).isoformat(),
    }
    with _lock:
        _events.appendleft(event)


def list_recent(limit: int = 5) -> list[dict[str, Any]]:
    with _lock:
        return list(_events)[: max(0, min(limit, _MAX))]


def clear() -> None:
    """Test helper."""
    with _lock:
        _events.clear()
