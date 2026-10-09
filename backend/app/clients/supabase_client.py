"""Supabase (Postgres) client — soft-fails in development if unconfigured."""

from __future__ import annotations

import logging

from app.config import settings

logger = logging.getLogger("mirage.supabase")

_client = None


def init_supabase():
    """Create the client if configured. Returns None otherwise (dev-safe)."""
    global _client
    if not settings.supabase_url or not settings.supabase_anon_key:
        logger.warning("SUPABASE_URL/ANON_KEY not set - Supabase disabled (development)")
        return None
    try:
        from supabase import create_client

        _client = create_client(settings.supabase_url, settings.supabase_anon_key)
        logger.info("Supabase client initialized")
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("Supabase init failed: %s", exc)
        if settings.is_production:
            raise
        _client = None
    return _client


def get_supabase():
    """Lazily (re)initialize and return the client, or None."""
    global _client
    if _client is None:
        init_supabase()
    return _client
