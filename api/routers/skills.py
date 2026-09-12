"""Skills Router — Skill demand evidence (deterministic engine) and extraction."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from typing import Optional

from api.config import settings

router = APIRouter(prefix="/api/v1/skills", tags=["skills"])


@router.get("/demand")
def skill_demand(
    source_id: str = Query("naukri-historical-promptcloud"),
    district: Optional[str] = Query(None),
    sector: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
):
    """Skill demand from persisted job evidence — deterministic engine.

    Uses the authoritative skill_demand_engine: recomputes skill evidence from
    persisted JobPosting rows with the canonical 32-skill matcher. Returns
    distinct-job counts and normalized shares — never an invented score.
    """
    from core.analytics.skill_demand_engine import calculate_skill_demand

    report = calculate_skill_demand(
        db_url=settings.DATABASE_URL,
        source_id=source_id,
        district=district,
        sector=sector,
    )

    rows = [
        {
            "skill_id": r["skill_id"],
            "skill_name": r["skill_name"],
            "distinct_job_count": r["distinct_job_count"],
            "mention_count": r["mention_count"],
            "normalized_distinct_job_count": r["normalized_distinct_job_count"],
            "confidence": r["confidence"],
            "evidence_type_breakdown": r["evidence_type_breakdown"],
            "verification_status": r["verification_status"],
        }
        for r in report["demand_rows"]
        if r["distinct_job_count"] > 0
    ][:limit]

    return {
        "rows": rows,
        "count": len(rows),
        "total_jobs_evaluated": report["total_jobs_evaluated"],
        "jobs_with_skill_evidence": report["jobs_with_skill_evidence"],
        "skills_with_evidence": report["skills_with_evidence"],
        "total_evidence_rows": report["total_evidence_rows"],
        "source_id": report["source_id"],
        "district": report["district"],
        "sector": report["sector"],
        "observation_period": [report["period_start"], report["period_end"]],
        "rule_version": report["rule_version"],
        "run_id": report["run_id"],
        "note": "Shares are normalized distinct-job counts of evidence, NOT weighted demand scores.",
    }


@router.get("/supply")
def skill_supply(
    source_id: str = Query("naukri-historical-promptcloud"),
):
    """DVET supply coverage summary from the persisted DVET snapshot.

    Read-only: reports what the DVET snapshot covers. Never extrapolates from
    the single institute to all of Pune.
    """
    from core.analytics.skill_demand_engine import calculate_skill_demand

    report = calculate_skill_demand(db_url=settings.DATABASE_URL, source_id=source_id)
    return {
        "dvet_supply_summary": report["dvet_supply_summary"],
        "note": "DVET snapshot covers a single institute; supply is NOT extrapolated district-wide.",
    }


@router.get("/velocity")
def skill_velocity(
    source_id: str = Query("naukri-historical-promptcloud"),
    limit: int = Query(30, ge=1, le=100),
):
    """Skill velocity — honestly labeled.

    The current persisted evidence is a single static historical snapshot
    (one retrieval run), so two observation windows cannot be constructed.
    Velocity is reported as INSUFFICIENT_DATA / STATIC_SNAPSHOT rather than
    fabricating a rising/falling trend.
    """
    from core.analytics.skill_velocity import compute_skill_velocity

    result = compute_skill_velocity(
        db_url=settings.DATABASE_URL,
        source_id=source_id,
        window_start=None,
        window_end=None,
        previous_start=None,
        previous_end=None,
    )
    # Restrict to the requested limit at the edge.
    demand = result.get("demand", [])
    return {
        "rows": demand[:limit],
        "status": result.get("status", "NO_DATA"),
        "labels": result.get("labels", {}),
        "note": "Velocity requires ≥2 observation windows from distinct ingestion runs.",
    }


@router.post("/extract")
def extract_skills(payload: dict):
    """Extract canonical skills from a job text payload.

    Deterministic, ontology-constrained — resolves only to the existing
    32 canonical skills. Never invents new skills.
    """
    from core.skills.ontology_matcher import SkillMatcher
    from core.skills.extractor import extract_job_skills
    from types import SimpleNamespace

    text = payload.get("text", "")
    title = payload.get("job_title", "")
    if not text and not title:
        return {"error": "Provide 'text' and/or 'job_title'."}

    job = SimpleNamespace(id="api-extract", source_skills=None, job_title=title, description=text)
    matcher = SkillMatcher()
    evidence, unmatched = extract_job_skills(job, matcher)

    return {
        "evidence": [
            {
                "skill_id": e.canonical_skill_id,
                "skill_name": e.canonical_skill_name,
                "confidence": e.match_confidence.value,
                "method": e.extraction_method.value,
                "evidence_type": e.evidence_type,
                "matched_text": e.source_skill_text,
            }
            for e in evidence
        ],
        "unmatched_mentions": [
            {"raw_text": m.raw_text, "normalized_text": m.normalized_text}
            for m in unmatched
        ],
        "count": len(evidence),
    }