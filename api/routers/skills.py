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


@router.get("/gaps")
def skill_gaps(
    source_id: str = Query("naukri-historical-promptcloud"),
    district: Optional[str] = Query(None),
    sector: Optional[str] = Query(None),
):
    """Skill gap analysis: demand vs DVET supply, with deterministic classification."""
    from core.analytics.skill_demand_engine import calculate_skill_demand
    from core.analytics.skill_gap_engine import calculate_skill_gap

    demand_report = calculate_skill_demand(
        db_url=settings.DATABASE_URL,
        source_id=source_id,
        district=district,
        sector=sector,
    )
    gap_report = calculate_skill_gap(demand_report)
    return {
        "rows": gap_report["gap_rows"],
        "count": len(gap_report["gap_rows"]),
        "total_jobs_evaluated": gap_report["total_jobs_evaluated"],
        "gap_summary": gap_report["gap_summary"],
        "gap_thresholds": gap_report["gap_thresholds"],
        "dvet_institute_count": gap_report["dvet_institute_count"],
        "dvet_trades_total": gap_report["dvet_trades_total"],
        "dvet_extrapolation_note": gap_report["dvet_extrapolation_note"],
        "run_id": gap_report.get("run_id", ""),
        "source_id": gap_report.get("source_id", ""),
    }


@router.get("/gaps/{skill_id}")
def skill_gap_detail(
    skill_id: str,
    source_id: str = Query("naukri-historical-promptcloud"),
    district: Optional[str] = Query(None),
    sector: Optional[str] = Query(None),
):
    """Single skill gap detail with recommendation."""
    from core.analytics.skill_demand_engine import calculate_skill_demand
    from core.analytics.skill_gap_engine import calculate_skill_gap

    demand_report = calculate_skill_demand(
        db_url=settings.DATABASE_URL,
        source_id=source_id,
        district=district,
        sector=sector,
    )
    gap_report = calculate_skill_gap(demand_report)
    for row in gap_report["gap_rows"]:
        if row["skill_id"] == skill_id:
            rec = _build_recommendation(row)
            return {**row, "recommendation": rec}
    return {"error": f"Skill {skill_id} not found in gap analysis."}


@router.get("/recommendations")
def skill_recommendations(
    source_id: str = Query("naukri-historical-promptcloud"),
    district: Optional[str] = Query(None),
    sector: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
):
    """Deterministic skill-recommendation report: gap-based, no LLM involved."""
    from core.analytics.skill_demand_engine import calculate_skill_demand
    from core.analytics.skill_gap_engine import calculate_skill_gap

    demand_report = calculate_skill_demand(
        db_url=settings.DATABASE_URL,
        source_id=source_id,
        district=district,
        sector=sector,
    )
    gap_report = calculate_skill_gap(demand_report)
    recs = []
    for row in gap_report["gap_rows"][:limit]:
        recs.append(_build_recommendation(row))
    return {
        "recommendations": recs,
        "count": len(recs),
        "total_jobs_evaluated": gap_report["total_jobs_evaluated"],
        "rule_version": "deterministic-v1",
        "note": "Recommendations are deterministic rules applied to verified evidence. No LLM generated this.",
    }


def _build_recommendation(gap_row: dict) -> dict:
    """Deterministic recommendation rules — conservative, evidence-gated, auditable.

    Safety rules enforced:
    - HIGH_GAP: Only "increase capacity" when demand meets minimum evidence threshold
      AND supply is VERIFIED (not just present) AND demand is not INSUFFICIENT_DATA.
    - HIGH_GAP + NEEDS_REVIEW supply → "Review / validate training supply"
    - HIGH_GAP + no verified supply → "Investigate training supply availability"
    - INSUFFICIENT_DATA / NO_DATA → data collection only
    - Never claim "no institute offers this" (we don't have a complete Pune directory)
    - Never extrapolate single-institute supply to Pune-wide
    - Every recommendation includes all required provenance fields.
    """
    status = gap_row["gap_status"]
    demand = gap_row["demand_distinct_job_count"]
    norm = gap_row.get("demand_normalized_distinct_job_count", 0.0)
    skill_name = gap_row["skill_name"]
    has_supply = gap_row["has_dvet_supply_evidence"]
    supply_detail = gap_row.get("dvet_supply_detail")
    verification_status = gap_row.get("verification_status", "NEEDS_REVIEW")
    demand_confidence = gap_row.get("demand_confidence", {})

    # Thresholds from gap engine
    HIGH_THRESHOLD = 0.05
    MEDIUM_THRESHOLD = 0.01

    # Determine evidence quality label
    if demand == 0:
        evidence_status = "NO_DATA"
    elif norm >= HIGH_THRESHOLD:
        evidence_status = "OBSERVED"
    elif norm >= MEDIUM_THRESHOLD:
        evidence_status = "OBSERVED"
    elif demand > 0:
        evidence_status = "OBSERVED"
    else:
        evidence_status = "INSUFFICIENT_DATA"

    # Supply coverage quality
    if has_supply:
        supply_status = "NEEDS_REVIEW"  # All DVET supply is NEEDS_REVIEW per our data
        supply_evidence_note = (
            f"DVET supply evidence present from ITI Haveli (1 institute, {len(supply_detail.get('trades', [])) if supply_detail else 0} trades). "
            "NOT verified against full Pune directory. NOT extrapolated district-wide."
        )
    else:
        supply_status = "NO_SUPPLY_EVIDENCE"
        supply_evidence_note = "No DVET supply evidence in current snapshot (ITI Haveli only)."

    base = {
        "skill_id": gap_row["skill_id"],
        "skill_name": skill_name,
        "priority": "LOW",
        "confidence": "LOW",
        "source": "naukri-historical-promptcloud",
        "freshness": "HISTORICAL",
        "evidence_status": evidence_status,
        "supply_status": supply_status,
        "data_quality": verification_status,
    }

    if status == "HIGH_GAP":
        if has_supply:
            # Supply exists but is NEEDS_REVIEW — cannot recommend capacity increase
            return {
                **base,
                "recommendation": f"Review / validate training supply for {skill_name}",
                "reason": (
                    f"High demand evidence ({demand} jobs, {norm:.1%} share) but DVET supply evidence "
                    "is unverified (NEEDS_REVIEW). Cannot recommend capacity changes until supply is validated."
                ),
                "evidence": (
                    f"{demand} distinct jobs reference this skill ({norm:.1%} of evaluated jobs). "
                    f"{supply_evidence_note}"
                ),
                "priority": "MEDIUM",
                "confidence": "LOW",
                "next_action": "Cross-verify DVET trade mappings against authoritative directory; validate if programmes actually cover this skill.",
            }

        # No verified supply
        return {
            **base,
            "recommendation": f"Investigate training supply availability for {skill_name}",
            "reason": (
                f"High demand evidence ({demand} jobs, {norm:.1%} share) with NO DVET supply evidence "
                "in current snapshot. Current snapshot covers only ITI Haveli (1 institute); "
                "Pune-wide training landscape is UNKNOWN."
            ),
            "evidence": (
                f"{demand} distinct jobs reference this skill ({norm:.1%} of evaluated jobs). "
                f"{supply_evidence_note}"
            ),
            "priority": "MEDIUM",
            "confidence": "LOW",
            "next_action": "Commission a supply mapping study against authoritative DVET directory before proposing new programmes.",
        }

    if status == "MEDIUM_GAP":
        return {
            **base,
            "recommendation": f"Targeted capacity review for {skill_name}",
            "reason": (
                f"Moderate demand evidence ({demand} jobs, {norm:.1%} share). "
                f"{supply_evidence_note}"
            ),
            "evidence": (
                f"{demand} distinct jobs reference this skill ({norm:.1%} of evaluated jobs). "
                f"{supply_evidence_note}"
            ),
            "priority": "LOW",
            "confidence": "LOW",
            "next_action": "Assess whether existing programmes partially cover this skill; validate against full DVET directory.",
        }

    if status == "NEEDS_REVIEW":
        return {
            **base,
            "recommendation": f"Verify supply data for {skill_name}",
            "reason": (
                "DVET supply evidence exists but is unverified (NEEDS_REVIEW). "
                "Demand-supply alignment cannot be determined."
            ),
            "evidence": f"Supply evidence present from ITI Haveli snapshot. {demand} demand jobs. {supply_evidence_note}",
            "priority": "LOW",
            "confidence": "LOW",
            "next_action": "Cross-verify DVET trade mappings against authoritative directory and current intake records.",
        }

    if status == "NO_DATA":
        return {
            **base,
            "recommendation": f"Collect more data on {skill_name}",
            "reason": "No demand or supply evidence available for this skill in current observation window.",
            "evidence": f"Zero distinct jobs with this skill in {gap_row.get('total_jobs_evaluated', 'N/A')} evaluated jobs. {supply_evidence_note}",
            "priority": "LOW",
            "confidence": "LOW",
            "next_action": "Include in next ingestion batch; widen observation window; expand source coverage.",
        }

    # LOW_GAP
    return {
        **base,
        "recommendation": f"Monitor {skill_name} demand trend",
        "reason": f"Low demand evidence ({demand} jobs, {norm:.1%} share). {supply_evidence_note}",
        "evidence": f"{demand} distinct jobs reference this skill at low volume ({norm:.1%}). {supply_evidence_note}",
        "priority": "LOW",
        "confidence": "LOW",
        "next_action": "Monitor over next observation window before acting.",
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