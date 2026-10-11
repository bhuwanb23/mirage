"""Mirage API — FastAPI application entry point.

Run:  uv run uvicorn app.main:app --reload --port 8000
"""

from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.routers import health
from app.utils.logger import setup_logging

setup_logging(settings.log_level)
logger = logging.getLogger("mirage.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.validate_startup()

    # Soft-init external clients: log failures, never block boot in development.
    from app.clients.neo4j_client import init_neo4j
    from app.clients.supabase_client import init_supabase

    app.state.supabase = init_supabase()
    app.state.neo4j = init_neo4j()

    # Seed demo scam graph when empty so /graph is never blank on first boot.
    # Skip under pytest so unit tests can assert an empty store.
    import os
    import sys

    if "pytest" not in sys.modules and os.getenv("MIRAGE_SEED_GRAPH", "1") != "0":
        try:
            from app.services import scam_graph
            from app.services.graph_seed import seed as seed_graph

            store = scam_graph.get_store()
            stats = store.get_stats()
            if (stats.phone_numbers or 0) == 0 and (stats.scam_reports or 0) == 0:
                seed_graph(store)
                logger.info("Seeded demo scam graph (empty store)")
        except Exception as exc:  # noqa: BLE001
            logger.warning("Graph seed skipped: %s", exc)

    logger.info("Mirage API started (env=%s, version=%s)", settings.environment, settings.version)
    yield

    from app.clients.neo4j_client import close_neo4j

    close_neo4j()
    logger.info("Mirage API shut down")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Mirage API",
        description="Don't detect scams. Vaccinate people against them.",
        version=settings.version,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list or ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def request_logging(request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000
        logging.getLogger("mirage.request").info(
            "%s %s -> %s",
            request.method,
            request.url.path,
            response.status_code,
            extra={
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "duration_ms": round(duration_ms, 2),
            },
        )
        response.headers["X-Response-Time-Ms"] = f"{duration_ms:.1f}"
        return response

    app.include_router(health.router)
    from app.routers import analyze, drill

    app.include_router(analyze.router, prefix="/analyze")
    app.include_router(drill.router, prefix="/drill")

    # static media: generated drill audio + uploaded voice clips (Phase 3)
    media_dir = Path(settings.drill_media_dir)
    media_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/media/drill", StaticFiles(directory=media_dir), name="drill_media")

    # Phase 4 — Live Guardian + Memory Handshake
    from app.routers import guardian, memory

    app.include_router(memory.router, prefix="/memory")
    app.include_router(guardian.router)

    # Phase 5 — Scammer Hunter + Scam Graph
    from app.routers import family, graph, honeypot

    app.include_router(honeypot.router)
    app.include_router(graph.router)
    app.include_router(family.router, prefix="/family")

    return app


app = create_app()
