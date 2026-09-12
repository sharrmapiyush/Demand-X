"""Search Router — Keyword search over persisted observations."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional

from db.session import get_db

router = APIRouter(prefix="/api/v1/search", tags=["search"])


@router.get("/")
def search(
    q: str = Query(..., min_length=2, description="Search query"),
    district: Optional[str] = Query(None),
    sector: Optional[str] = Query(None),
    source_id: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Keyword search across persisted job postings and skill evidence.

    Not vector/semantic search — a deterministic keyword fallback over the
    real DB. Semantic search is deferred per P14.
    """
    import re
    from core.models.observation import JobPosting
    from core.models.demand import DistrictOccupationDemand
    from sqlalchemy import or_

    tokens = [t for t in re.findall(r"[a-z0-9]{3,}", q.lower()) if t]
    if not tokens:
        return {"results": [], "note": "No valid search tokens (minimum 3 chars)."}

    results = []

    # 1. Job postings (keyword match on title + description)
    job_filters = []
    if district:
        job_filters.append(JobPosting.district == district)
    if sector:
        job_filters.append(JobPosting.sector == sector)
    if source_id:
        job_filters.append(JobPosting.source_id == source_id)

    jobs = db.query(JobPosting).filter(*job_filters).limit(limit * 2).all()
    for job in jobs:
        searchable = f"{job.job_title or ''} {job.description or ''}".lower()
        if any(t in searchable for t in tokens):
            results.append({
                "record_type": "JOB_POSTING",
                "record_id": str(job.id),
                "title": job.job_title,
                "snippet": (job.description or "")[:200],
                "district": job.district,
                "source_id": job.source_id,
                "score": 0.5,  # keyword match, not a semantic score
            })
        if len(results) >= limit:
            break

    # 2. District occupation demand
    demand_q = db.query(DistrictOccupationDemand)
    if district:
        demand_q = demand_q.filter(DistrictOccupationDemand.district == district)
    demand_rows = demand_q.limit(20).all()
    for row in demand_rows:
        searchable = f"{row.district} {row.occupation_id} {row.id}".lower()
        if any(t in searchable for t in tokens):
            results.append({
                "record_type": "DISTRICT_OCCUPATION_DEMAND",
                "record_id": row.id,
                "title": f"{row.district} — {row.occupation_id}",
                "snippet": f"job_count={row.job_count}, apprenticeship_count={row.apprenticeship_count}",
                "district": row.district,
                "score": 0.3,
            })

    return {
        "results": results[:limit],
        "count": min(len(results), limit),
        "search_type": "keyword",
        "note": "Keyword-based retrieval only — vector search deferred per P14.",
    }