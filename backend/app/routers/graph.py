"""Graph + map + report router — Phase 5.3 / 5.4 / 5.5 / 5.6.

Endpoints:
  GET  /graph/data     -> force-directed graph payload (nodes + edges)
  GET  /graph/stats    -> aggregate counts + ring count
  GET  /graph/rings    -> detected rings + shared infrastructure
  GET  /map/heatmap    -> city-level heat data for the weather map
  POST /report/generate -> cybercrime complaint text + 1930 script

Run:  uv run uvicorn app.main:app --reload --port 8000
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query

from app.models.schemas import (
    GraphData,
    GraphStats,
    MapCity,
    MapHeatmap,
    ReportRequest,
    ReportResponse,
)
from app.services import report_generator, scam_graph

logger = logging.getLogger("mirage.graph.api")

router = APIRouter(tags=["graph"])

# ---------------------------------------------------------------------------
# Demo dataset (plan §5.5) — used until real reports dominate the map.
# ---------------------------------------------------------------------------

DEMO_CITIES: list[MapCity] = [
    MapCity(city="Delhi", lat=28.6139, lng=77.2090, scam_count=47, top_type="bank_kyc", intensity=0.9, trend="increasing"),
    MapCity(city="Mumbai", lat=19.0760, lng=72.8777, scam_count=38, top_type="upi_reversal", intensity=0.75, trend="increasing"),
    MapCity(city="Bangalore", lat=12.9716, lng=77.5946, scam_count=29, top_type="job_offer", intensity=0.6, trend="stable"),
    MapCity(city="Hyderabad", lat=17.3850, lng=78.4867, scam_count=22, top_type="fedex", intensity=0.45, trend="stable"),
    MapCity(city="Chennai", lat=13.0827, lng=80.2707, scam_count=18, top_type="lottery", intensity=0.35, trend="decreasing"),
    MapCity(city="Kolkata", lat=22.5726, lng=88.3639, scam_count=15, top_type="impersonation", intensity=0.3, trend="stable"),
    MapCity(city="Pune", lat=18.5204, lng=73.8567, scam_count=12, top_type="investment", intensity=0.25, trend="increasing"),
    MapCity(city="Jaipur", lat=26.9124, lng=75.7873, scam_count=9, top_type="bank_kyc", intensity=0.2, trend="stable"),
    MapCity(city="Ahmedabad", lat=23.0225, lng=72.5714, scam_count=7, top_type="electricity", intensity=0.15, trend="stable"),
    MapCity(city="Lucknow", lat=26.8467, lng=80.9462, scam_count=5, top_type="relative_distress", intensity=0.1, trend="decreasing"),
]

DEMO_NATIONAL_STATS = {
    "total_reports_this_week": 202,
    "top_scam_type": "bank_kyc",
    "trend": "increasing",
}


# ---------------------------------------------------------------------------
# Graph (5.4)
# ---------------------------------------------------------------------------


@router.get("/graph/data", response_model=GraphData)
def graph_data(limit: int = Query(default=200, ge=1, le=1000)) -> GraphData:
    """Nodes + edges for the force-directed visualization."""
    return scam_graph.get_store().get_graph_data(limit=limit)


@router.get("/graph/stats", response_model=GraphStats)
def graph_stats() -> GraphStats:
    """Aggregate entity counts + detected ring count."""
    return scam_graph.get_store().get_stats()


@router.get("/graph/rings")
def graph_rings(min_size: int = Query(default=3, ge=2, le=10)) -> dict:
    """Detected rings + shared infrastructure (plan §5.3 queries 1-3)."""
    store = scam_graph.get_store()
    return {
        "rings": store.detect_rings(min_size=min_size),
        "shared": store.shared_infrastructure(min_phones=2),
    }


# ---------------------------------------------------------------------------
# Weather map (5.5)
# ---------------------------------------------------------------------------


@router.get("/map/heatmap", response_model=MapHeatmap)
def map_heatmap() -> MapHeatmap:
    """City-level heat data. Demo dataset, enriched with live report totals."""
    stats = scam_graph.get_store().get_stats()
    national = dict(DEMO_NATIONAL_STATS)
    if stats.scam_reports > national["total_reports_this_week"]:
        national["total_reports_this_week"] = stats.scam_reports
    if stats.scam_type_counts:
        national["top_scam_type"] = max(stats.scam_type_counts, key=stats.scam_type_counts.get)
    national["graph_rings_detected"] = stats.rings
    return MapHeatmap(cities=DEMO_CITIES, national_stats=national)


# ---------------------------------------------------------------------------
# Report generator (5.6)
# ---------------------------------------------------------------------------


@router.post("/report/generate", response_model=ReportResponse)
def generate_report(req: ReportRequest) -> ReportResponse:
    """Format a complaint for cybercrime.gov.in + the 1930 helpline script."""
    from app.routers.honeypot import SESSIONS

    iocs = req.iocs
    if req.honeypot_session_id:
        session = SESSIONS.get(req.honeypot_session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Honeypot session not found")
        iocs = session.iocs  # prefilled from the live honeypot extraction

    try:
        return report_generator.generate_report(req, iocs)
    except Exception as exc:
        logger.error("report generation failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Report generation failed") from exc
