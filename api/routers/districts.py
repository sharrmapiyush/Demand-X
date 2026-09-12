"""Districts Router — Maharashtra geography and district occupation demand."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from typing import Optional

from db.session import get_db

router = APIRouter(prefix="/api/v1/districts", tags=["districts"])


@router.get("/")
def list_districts():
    """List all 36 Maharashtra districts grouped by revenue division."""
    from core.geography.maharashtra import MaharashtraGeoEngine
    engine = MaharashtraGeoEngine()
    districts = []
    for norm, entry in engine.districts.items():
        districts.append({
            "name": entry.name,
            "division": entry.division,
            "coordinates": list(entry.coordinates) if entry.coordinates else None,
        })
    return {"districts": districts, "count": len(districts)}


@router.get("/divisions")
def list_divisions():
    """List districts grouped by revenue division."""
    from core.geography.maharashtra import MaharashtraGeoEngine
    engine = MaharashtraGeoEngine()
    divisions = engine.divisions()
    return {"divisions": divisions, "count": len(divisions)}


@router.get("/resolve")
def resolve_location(text: str = Query(..., description="Location text to resolve")):
    """Resolve location text to a district with evidence status."""
    from core.geography.maharashtra import MaharashtraGeoEngine
    engine = MaharashtraGeoEngine()
    result = engine.resolve(text)
    return {
        "input": text,
        "district": result.district,
        "division": engine.district_division(result.district) if result.district else None,
        "state": result.state,
        "location_evidence_level": result.location_evidence_level,
        "location_scope": result.location_scope,
        "location_confidence": result.location_confidence,
        "matched_locations": result.matched_locations,
        "has_pune_evidence": result.has_pune_evidence,
    }


@router.get("/demand")
def district_demand(
    district: Optional[str] = Query(None),
    occupation_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """Get district occupation demand rows."""
    from core.models.demand import DistrictOccupationDemand

    query = db.query(DistrictOccupationDemand)
    if district:
        query = query.filter(DistrictOccupationDemand.district == district)
    if occupation_id:
        query = query.filter(DistrictOccupationDemand.occupation_id == occupation_id)
    rows = query.order_by(DistrictOccupationDemand.job_count.desc()).limit(limit).all()
    return {
        "rows": [
            {
                "id": r.id,
                "district": r.district,
                "occupation_id": r.occupation_id,
                "job_count": r.job_count,
                "apprenticeship_count": r.apprenticeship_count,
                "demand_score": r.demand_score,
                "observation_period_start": str(r.observation_period_start) if r.observation_period_start else None,
                "observation_period_end": str(r.observation_period_end) if r.observation_period_end else None,
                "data_completeness_status": r.data_completeness_status,
                "provenance_state": r.provenance_state,
                "rule_version": r.rule_version,
            }
            for r in rows
        ],
        "count": len(rows),
    }