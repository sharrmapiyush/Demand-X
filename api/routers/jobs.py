"""Jobs Router — Job posting query and ingestion status."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional

from db.session import get_db

router = APIRouter(prefix="/api/v1/jobs", tags=["jobs"])


@router.get("/")
def list_jobs(
    district: Optional[str] = Query(None),
    sector: Optional[str] = Query(None),
    source_id: Optional[str] = Query(None),
    job_title: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """List job postings with optional filters."""
    from core.models.observation import JobPosting

    query = db.query(JobPosting)
    if district:
        query = query.filter(JobPosting.district == district)
    if sector:
        query = query.filter(JobPosting.sector == sector)
    if source_id:
        query = query.filter(JobPosting.source_id == source_id)
    if job_title:
        query = query.filter(JobPosting.job_title.ilike(f"%{job_title}%"))

    total = query.count()
    rows = query.order_by(JobPosting.retrieved_at.desc()).offset(offset).limit(limit).all()
    return {
        "jobs": [
            {
                "id": str(r.id),
                "job_title": r.job_title,
                "employer_name": r.employer_name,
                "district": r.district,
                "sector": r.sector,
                "source_id": r.source_id,
                "retrieved_at": str(r.retrieved_at) if r.retrieved_at else None,
            }
            for r in rows
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/stats")
def job_stats(db: Session = Depends(get_db)):
    """Job posting aggregate statistics (real persisted counts only)."""
    from core.models.observation import JobPosting

    total = db.query(func.count(JobPosting.id)).scalar() or 0
    with_district = db.query(func.count(JobPosting.id)).filter(
        JobPosting.district.isnot(None), JobPosting.district != ""
    ).scalar() or 0
    without_district = total - with_district

    districts = db.query(JobPosting.district, func.count(JobPosting.id)).filter(
        JobPosting.district.isnot(None), JobPosting.district != ""
    ).group_by(JobPosting.district).order_by(func.count(JobPosting.id).desc()).all()

    sources = db.query(JobPosting.source_id, func.count(JobPosting.id)).group_by(
        JobPosting.source_id
    ).all()

    return {
        "total": total,
        "with_district": with_district,
        "without_district": without_district,
        "by_district": {d: c for d, c in districts},
        "by_source": {s: c for s, c in sources},
    }


@router.get("/staging")
def list_staging(
    status: Optional[str] = Query(None, description="Processing status: pending, extracted, staged, failed"),
    source_id: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """List recent job staging records."""
    from core.models.job import JobStaging

    query = db.query(JobStaging)
    if status:
        query = query.filter(JobStaging.processing_status == status)
    if source_id:
        query = query.filter(JobStaging.source_id == source_id)
    rows = query.order_by(JobStaging.staging_id.desc()).limit(limit).all()
    return {
        "staging": [
            {
                "id": str(r.staging_id),
                "source_id": r.source_id,
                "raw_title": r.raw_title,
                "processing_status": r.processing_status,
                "is_valid": r.is_valid,
            }
            for r in rows
        ],
        "count": len(rows),
    }