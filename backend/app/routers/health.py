"""GET /health — liveness + readiness probe."""

from __future__ import annotations

from fastapi import APIRouter

from app.config import settings
from app.models.schemas import HealthCheck

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthCheck)
async def health() -> HealthCheck:
    return HealthCheck(
        status="healthy",
        service=settings.service_name,
        version=settings.version,
        providers={
            "configured": settings.primary_llm_provider,
            "available": settings.available_llm_providers,
            "supabase": bool(settings.supabase_url),
            "neo4j": bool(settings.neo4j_uri),
            "environment": settings.environment,
        },
    )
