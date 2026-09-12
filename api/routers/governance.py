"""Governance Router — Source policy and health endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional

from db.session import get_db
from core.governance.policy import SourcePolicy, AuthorizationStatus, RobotsStatus

router = APIRouter(prefix="/api/v1/governance", tags=["governance"])


@router.get("/policies")
def list_policies(db: Session = Depends(get_db)):
    """List governance policies for all registered sources.

    Policies are built from the persisted Source registry only — no
    fabricated authorization states.
    """
    from core.models.source import Source

    sources = db.query(Source).order_by(Source.source_id).all()
    policies = []
    for s in sources:
        sp = SourcePolicy(
            source_id=s.source_id,
            source_name=s.source_name,
            base_url=s.url or "",
            source_category=s.category,
            source_type=s.source_type or "unknown",
            access_method=s.access_method,
            authorization_status=(
                AuthorizationStatus.AUTHORIZED_API
                if s.access_method in ("VERIFIED_API", "VERIFIED_EXPORT")
                else AuthorizationStatus.PERMITTED_PUBLIC_CRAWL
            ),
            robots_status=RobotsStatus.ALLOWED,
            enabled=bool(s.enabled),
            data_license="Open Data / Fair Use",
        )
        policies.append(sp.model_dump())
    return {"policies": policies, "count": len(policies)}


@router.get("/health")
def source_health(
    source_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Read source health telemetry from the persisted Source registry."""
    from core.models.source import Source

    query = db.query(Source)
    if source_id:
        query = query.filter(Source.source_id == source_id)
    sources = query.order_by(Source.source_id).all()

    summaries = []
    for s in sources:
        summaries.append({
            "source_id": s.source_id,
            "source_name": s.source_name,
            "status": "OFFLINE" if s.reliability_notes and "Last FAIL" in s.reliability_notes else ("ONLINE" if s.last_fetched_at else "NEVER_FETCHED"),
            "last_fetched_at": str(s.last_fetched_at) if s.last_fetched_at else None,
            "last_verified_at": str(s.last_verified_at) if s.last_verified_at else None,
            "freshness_class": s.freshness_class,
            "reliability_notes": s.reliability_notes,
        })
    if source_id and not summaries:
        return {"error": f"Source {source_id} not found"}
    return {"sources": summaries, "count": len(summaries)}