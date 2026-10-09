"""Neo4j client — soft-fails in development if unconfigured."""

from __future__ import annotations

import logging

from app.config import settings

logger = logging.getLogger("mirage.neo4j")

_driver = None


def init_neo4j():
    """Create the driver if configured. Returns None otherwise (dev-safe)."""
    global _driver
    if not settings.neo4j_uri:
        logger.warning("NEO4J_URI not set - Neo4j disabled (development)")
        return None
    try:
        from neo4j import GraphDatabase

        _driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_username, settings.neo4j_password),
        )
        _driver.verify_connection()
        logger.info("Neo4j driver connected (%s)", settings.neo4j_uri)
    except Exception as exc:
        logger.error("Neo4j init failed: %s", exc)
        if settings.is_production:
            raise
        _driver = None
    return _driver


def get_neo4j():
    global _driver
    if _driver is None:
        init_neo4j()
    return _driver


def close_neo4j() -> None:
    global _driver
    if _driver is not None:
        try:
            _driver.close()
        finally:
            _driver = None


def run_query(query: str, parameters: dict | None = None) -> list[dict]:
    """Convenience helper: run a Cypher query, return list of record dicts."""
    driver = get_neo4j()
    if driver is None:
        return []
    with driver.session() as session:
        result = session.run(query, parameters or {})
        return [dict(record) for record in result]
