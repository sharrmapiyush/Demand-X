"""Exports Router — CSV/JSON export endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import Optional
import os

from db.session import get_db
from api.config import settings

router = APIRouter(prefix="/api/v1/exports", tags=["exports"])


EXPORTS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "exports")


@router.get("/skill-demand")
def export_skill_demand(
    source_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Export skill demand evidence to CSV."""
    from core.exports.reporter import export_skill_demand as _export

    filepath = _export(db, source_id=source_id)
    return FileResponse(filepath, filename=os.path.basename(filepath), media_type="text/csv")


@router.get("/district-occupation-demand")
def export_district_demand(db: Session = Depends(get_db)):
    """Export district occupation demand to CSV."""
    from core.exports.reporter import export_district_occupation_demand as _export

    filepath = _export(db)
    return FileResponse(filepath, filename=os.path.basename(filepath), media_type="text/csv")


@router.get("/sources")
def export_sources(db: Session = Depends(get_db)):
    """Export source registry to JSON."""
    from core.exports.reporter import export_sources as _export

    filepath = _export(db)
    return FileResponse(filepath, filename=os.path.basename(filepath), media_type="application/json")


@router.get("/occupations")
def export_occupations():
    """Export canonical occupations seed to JSON."""
    from core.exports.reporter import export_occupations as _export

    filepath = _export()
    return FileResponse(filepath, filename=os.path.basename(filepath), media_type="application/json")


@router.get("/skills")
def export_skills():
    """Export canonical skills seed to JSON."""
    from core.exports.reporter import export_skills as _export

    filepath = _export()
    return FileResponse(filepath, filename=os.path.basename(filepath), media_type="application/json")


@router.get("/demand-run-report")
def export_demand_run_report():
    """Download the latest demand aggregation run report."""
    report_path = os.path.join("data", "analytics", "demand_run_report.json")
    if not os.path.exists(report_path):
        return {"error": "No demand run report found. Run: python scripts/analytics/run_demand_aggregation.py"}
    return FileResponse(report_path, media_type="application/json")