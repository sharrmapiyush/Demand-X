"""Skill Gap Engine — compare skill demand evidence vs DVET training supply.

Compares the per-skill demand output from ``skill_demand_engine`` with the
DVET training supply (trade→skill mappings from ITI Haveli snapshot) to
identify gaps.

Gap classification
------------------
- ``HIGH_GAP``     : high demand evidence, no DVET supply evidence
- ``MEDIUM_GAP``   : moderate demand evidence, no DVET supply evidence
- ``LOW_GAP``      : low demand evidence, no DVET supply evidence
- ``NO_DATA``      : no demand evidence, no supply evidence
- ``NEEDS_REVIEW`` : supply evidence exists (all DVET mappings are NEEDS_REVIEW),
                     or demand level is ambiguous

Thresholds
----------
Defined as module-level constants — transparent, overridable, no hidden logic.
Thresholds are expressed as ``normalized_distinct_job_count`` (fraction of
total jobs in the source window that carry skill evidence).

``NEEDS_REVIEW`` takes precedence: if a skill has ANY DVET supply evidence,
its gap status is ``NEEDS_REVIEW`` regardless of demand level (the supply
mapping itself is unverified).

Design principles
-----------------
- No fabricated confidence scores or weighted composites.
- Raw demand + supply counts are always present alongside gap status.
- DVET supply is reported per-institute, never extrapolated.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

# ── Threshold configuration (transparent, documented) ────────────────────────
# These are normalized_distinct_job_count thresholds (fraction of source jobs).

HIGH_GAP_THRESHOLD = 0.05    # ≥ 5% of jobs reference this skill
MEDIUM_GAP_THRESHOLD = 0.01  # ≥ 1% of jobs reference this skill
# Below 1% → LOW_GAP (if demand exists at all)

# ── Gap status constants ─────────────────────────────────────────────────────

STATUS_HIGH_GAP = "HIGH_GAP"
STATUS_MEDIUM_GAP = "MEDIUM_GAP"
STATUS_LOW_GAP = "LOW_GAP"
STATUS_NO_DATA = "NO_DATA"
STATUS_NEEDS_REVIEW = "NEEDS_REVIEW"


def classify_gap(
    distinct_job_count: int,
    normalized_distinct_job_count: float,
    has_dvet_supply: bool,
    total_jobs: int,
) -> str:
    """Classify the gap status for a single skill.

    Parameters
    ----------
    distinct_job_count : int
        Number of distinct jobs with skill evidence.
    normalized_distinct_job_count : float
        ``distinct_job_count / total_jobs``.
    has_dvet_supply : bool
        True if the skill appears in any DVET trade→skill mapping.
    total_jobs : int
        Total jobs evaluated.

    Returns
    -------
    str — one of HIGH_GAP, MEDIUM_GAP, LOW_GAP, NO_DATA, NEEDS_REVIEW.
    """
    if has_dvet_supply:
        return STATUS_NEEDS_REVIEW

    if distinct_job_count == 0 and total_jobs > 0:
        return STATUS_NO_DATA

    if total_jobs == 0:
        return STATUS_NO_DATA

    if normalized_distinct_job_count >= HIGH_GAP_THRESHOLD:
        return STATUS_HIGH_GAP
    elif normalized_distinct_job_count >= MEDIUM_GAP_THRESHOLD:
        return STATUS_MEDIUM_GAP
    elif distinct_job_count > 0:
        return STATUS_LOW_GAP
    else:
        return STATUS_NO_DATA


def calculate_skill_gap(
    demand_report: Dict[str, Any],
) -> Dict[str, Any]:
    """Calculate skill gap by comparing demand evidence against DVET supply.

    Parameters
    ----------
    demand_report : dict
        Output of ``skill_demand_engine.calculate_skill_demand()``.

    Returns
    -------
    dict with gap_rows, gap_summary, and configuration.
    """
    total_jobs = demand_report.get("total_jobs_evaluated", 0)
    dvet_supply = demand_report.get("dvet_supply_summary", {})
    supply_skills = set(dvet_supply.get("skills_with_supply_evidence", {}).keys())

    demand_rows = demand_report.get("demand_rows", [])
    gap_rows: List[Dict[str, Any]] = []

    status_counts = {
        STATUS_HIGH_GAP: 0,
        STATUS_MEDIUM_GAP: 0,
        STATUS_LOW_GAP: 0,
        STATUS_NO_DATA: 0,
        STATUS_NEEDS_REVIEW: 0,
    }

    for dr in demand_rows:
        sid = dr["skill_id"]
        has_supply = sid in supply_skills
        norm = dr.get("normalized_distinct_job_count", 0.0)
        djc = dr.get("distinct_job_count", 0)

        status = classify_gap(
            distinct_job_count=djc,
            normalized_distinct_job_count=norm,
            has_dvet_supply=has_supply,
            total_jobs=total_jobs,
        )
        status_counts[status] += 1

        supply_detail = None
        if has_supply:
            supply_detail = dvet_supply["skills_with_supply_evidence"].get(sid)

        gap_rows.append({
            "skill_id": sid,
            "skill_name": dr.get("skill_name", sid),
            "gap_status": status,
            "demand_distinct_job_count": djc,
            "demand_mention_count": dr.get("mention_count", 0),
            "demand_normalized_distinct_job_count": norm,
            "has_dvet_supply_evidence": has_supply,
            "dvet_supply_detail": supply_detail,
            "demand_confidence": dr.get("confidence", {}),
            "verification_status": dr.get("verification_status", "NEEDS_REVIEW"),
        })

    gap_rows.sort(
        key=lambda r: (
            [
                STATUS_HIGH_GAP,
                STATUS_MEDIUM_GAP,
                STATUS_NEEDS_REVIEW,
                STATUS_LOW_GAP,
                STATUS_NO_DATA,
            ].index(r["gap_status"]),
            -r["demand_distinct_job_count"],
            r["skill_id"],
        )
    )

    return {
        "run_id": demand_report.get("run_id"),
        "source_id": demand_report.get("source_id"),
        "total_jobs_evaluated": total_jobs,
        "total_skills_evaluated": len(gap_rows),
        "dvet_institute_count": dvet_supply.get("institute_count", 0),
        "dvet_trades_total": dvet_supply.get("total_trades", 0),
        "dvet_extrapolation_note": dvet_supply.get("extrapolation_note", ""),
        "gap_thresholds": {
            "high_gap_threshold": HIGH_GAP_THRESHOLD,
            "medium_gap_threshold": MEDIUM_GAP_THRESHOLD,
            "rule": (
                "NEEDS_REVIEW if any DVET supply evidence; "
                "HIGH_GAP if >= high_threshold; "
                "MEDIUM_GAP if >= medium_threshold; "
                "LOW_GAP if any demand but below medium_threshold; "
                "NO_DATA if no demand evidence"
            ),
        },
        "gap_summary": status_counts,
        "gap_rows": gap_rows,
    }
