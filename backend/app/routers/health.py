"""GET /health — liveness + readiness probe."""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.config import settings
from app.models.schemas import HealthCheck

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthCheck)
async def health(request: Request) -> HealthCheck:
    # Prefer live client init state over env-presence (avoids false positives).
    supabase_ready = getattr(request.app.state, "supabase", None) is not None
    neo4j_ready = getattr(request.app.state, "neo4j", None) is not None
    graph_backend = "neo4j" if neo4j_ready else "sqlite"

    return HealthCheck(
        status="healthy",
        service=settings.service_name,
        version=settings.version,
        providers={
            "configured": settings.primary_llm_provider,
            "available": settings.available_llm_providers,
            "supabase": supabase_ready,
            "neo4j": neo4j_ready,
            "graph_backend": graph_backend,
            "environment": settings.environment,
        },
    )
