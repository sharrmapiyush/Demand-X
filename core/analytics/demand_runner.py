"""Demand aggregation runner — wires the existing deterministic calculator
to persisted JobPosting observations and persists DemandCalculationRun /
DistrictOccupationDemand rows.

This is the integration layer: it does not change calculation rules, scoring,
or occupation mapping.  It:
  1. Queries eligible observations (source-filtered, date-windowed).
  2. Calls ``calculate_district_demand`` per discovered district.
  3. Persists run + demand rows with idempotent upsert semantics.
  4. Returns a comprehensive report dict.

Date policy: uses ``retrieved_at`` (the existing calculator's documented
policy).  ``posted_date`` is never used for observation period selection.
"""

import logging
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from core.models.observation import JobPosting
from core.models.demand import DemandCalculationRun, DistrictOccupationDemand
from core.analytics.demand_calculator import (
    calculate_district_demand,
    resolve_occupation,
    generate_run_id,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _occupation_demand_row_matches(existing: DistrictOccupationDemand,
                                   incoming: Dict[str, Any]) -> bool:
    """Return True when every persisted field matches the incoming record."""
    return (
        existing.district == incoming["district"]
        and existing.occupation_id == incoming["occupation_id"]
        and existing.sector == incoming["sector"]
        and existing.observation_period_start == incoming["observation_period_start"]
        and existing.observation_period_end == incoming["observation_period_end"]
        and existing.job_count == incoming["job_count"]
        and existing.apprenticeship_count == incoming["apprenticeship_count"]
        and existing.demand_score == incoming["demand_score"]
        and existing.data_completeness_status == incoming["data_completeness_status"]
        and existing.rule_version == incoming["rule_version"]
    )


# ---------------------------------------------------------------------------
# main entry point
# ---------------------------------------------------------------------------

def run_demand_aggregation(
    db: Session,
    source_id: str,
    start_date: date,
    end_date: date,
    rule_version: str = "mvp-v1-no-score",
    district: Optional[str] = None,
    sector: Optional[str] = None,
) -> Dict[str, Any]:
    """Run demand aggregation for a single source over an observation window.

    Args:
        db: database session (caller must commit/rollback)
        source_id: only observations from this source
        start_date: observation window start (inclusive, compared to ``retrieved_at``)
        end_date: observation window end (inclusive, compared to ``retrieved_at``)
        rule_version: calculation rule identifier
        district: optional — restrict to a single district
        sector: optional — restrict observations to this sector

    Returns:
        report dict with all requested counters
    """
    start_dt = datetime.combine(start_date, datetime.min.time())
    end_dt = datetime.combine(end_date, datetime.max.time())

    # ------------------------------------------------------------------
    # 1. Pre-query: classify all eligible observations for report counters
    # ------------------------------------------------------------------
    job_filters = [
        JobPosting.source_id == source_id,
        JobPosting.retrieved_at >= start_dt,
        JobPosting.retrieved_at <= end_dt,
    ]
    if sector:
        job_filters.append(JobPosting.sector == sector)

    all_jobs = db.query(JobPosting).filter(*job_filters).all()

    input_observations = len(all_jobs)
    unknown_district_observations = 0
    eligible_observations = 0
    mapped_observations = 0
    unmapped_observations = 0
    needs_review_mapping_observations = 0

    district_set: set = set()
    occupation_set: set = set()

    for job in all_jobs:
        dist = (job.district or "").strip()
        if not dist:
            unknown_district_observations += 1
            continue
        district_set.add(dist)

        # eligible = has district (+ has sector, which is enforced by optional filter)
        if not (job.sector or "").strip():
            # sector required by calculator (excluded as unknown_sector)
            continue

        eligible_observations += 1

        occ_id, _matched, status, _method = resolve_occupation(job.job_title)
        if occ_id and status != "UNMAPPED":
            mapped_observations += 1
            occupation_set.add(occ_id)
            if status == "NEEDS_REVIEW":
                needs_review_mapping_observations += 1
        else:
            unmapped_observations += 1

    # If caller specified a single district, honour it; otherwise use discovered districts
    if district:
        districts_to_run = [district]
        # verify it has data (may have zero eligible)
        if district not in district_set:
            # district exists but has no district-tagged rows in the source filter;
            # still call the calculator — it will count unknown_district within its
            # own query and return no occupation aggregates.
            districts_to_run = [district]
    else:
        districts_to_run = sorted(district_set)

    if not districts_to_run:
        # no district-tagged rows at all — return a report with zero occupation rows
        return _build_report(
            source_id=source_id,
            rule_version=rule_version,
            start_date=start_date,
            end_date=end_date,
            input_observations=input_observations,
            unknown_district_observations=unknown_district_observations,
            eligible_observations=eligible_observations,
            mapped_observations=mapped_observations,
            unmapped_observations=unmapped_observations,
            needs_review_mapping_observations=needs_review_mapping_observations,
            districts=[],
            occupation_ids=[],
            rows_created=0,
            rows_updated=0,
            rows_skipped=0,
            runs_created=0,
            source_coverage={},
        )

    # ------------------------------------------------------------------
    # 2. Per-district calculator calls + persistence
    # ------------------------------------------------------------------
    rows_created = 0
    rows_updated = 0
    rows_skipped = 0
    runs_created = 0

    for dist in districts_to_run:
        calc_result = calculate_district_demand(
            db=db,
            district=dist,
            observation_period_start=start_date,
            observation_period_end=end_date,
            rule_version=rule_version,
            source_id=source_id,
            sector=sector,
        )

        run_id = calc_result["run_id"]

        # 2a. Upsert DemandCalculationRun
        existing_run = db.query(DemandCalculationRun).filter_by(run_id=run_id).first()
        now = datetime.utcnow()
        if existing_run is None:
            run_row = DemandCalculationRun(
                run_id=run_id,
                started_at=now,
                completed_at=now,
                input_data_start_date=start_date,
                input_data_end_date=end_date,
                rule_version=rule_version,
                status="COMPLETED",
            )
            db.add(run_row)
            runs_created += 1
        else:
            existing_run.completed_at = now
            existing_run.status = "COMPLETED"

        # 2b. Upsert DistrictOccupationDemand rows
        for occ_record in calc_result.get("occupation_demand", []):
            occ_id = occ_record["occupation_id"]
            row_id = occ_record["id"]

            existing = db.query(DistrictOccupationDemand).filter_by(id=row_id).first()
            if existing is None:
                new_row = DistrictOccupationDemand(
                    id=row_id,
                    run_id=run_id,
                    district=occ_record["district"],
                    occupation_id=occ_id,
                    sector=occ_record.get("sector"),
                    observation_period_start=occ_record["observation_period_start"],
                    observation_period_end=occ_record["observation_period_end"],
                    job_count=occ_record["job_count"],
                    apprenticeship_count=occ_record["apprenticeship_count"],
                    demand_score=occ_record.get("demand_score"),
                    data_completeness_status=occ_record["data_completeness_status"],
                    source_coverage_summary=occ_record.get("source_coverage_summary"),
                    evidence=occ_record.get("evidence"),
                    provenance_state=occ_record.get("provenance_state", "DERIVED"),
                    rule_version=occ_record["rule_version"],
                )
                db.add(new_row)
                rows_created += 1
            elif _occupation_demand_row_matches(existing, occ_record):
                rows_skipped += 1
            else:
                # update changed fields
                existing.job_count = occ_record["job_count"]
                existing.apprenticeship_count = occ_record["apprenticeship_count"]
                existing.demand_score = occ_record.get("demand_score")
                existing.data_completeness_status = occ_record["data_completeness_status"]
                existing.source_coverage_summary = occ_record.get("source_coverage_summary")
                existing.evidence = occ_record.get("evidence")
                existing.rule_version = occ_record["rule_version"]
                rows_updated += 1

    db.flush()

    # ------------------------------------------------------------------
    # 3. Build and return report
    # ------------------------------------------------------------------
    report = _build_report(
        source_id=source_id,
        rule_version=rule_version,
        start_date=start_date,
        end_date=end_date,
        input_observations=input_observations,
        unknown_district_observations=unknown_district_observations,
        eligible_observations=eligible_observations,
        mapped_observations=mapped_observations,
        unmapped_observations=unmapped_observations,
        needs_review_mapping_observations=needs_review_mapping_observations,
        districts=districts_to_run,
        occupation_ids=sorted(occupation_set),
        rows_created=rows_created,
        rows_updated=rows_updated,
        rows_skipped=rows_skipped,
        runs_created=runs_created,
        source_coverage={source_id: {"row_count": input_observations}},
    )

    return report


def _build_report(
    *,
    source_id: str,
    rule_version: str,
    start_date: date,
    end_date: date,
    input_observations: int,
    unknown_district_observations: int,
    eligible_observations: int,
    mapped_observations: int,
    unmapped_observations: int,
    needs_review_mapping_observations: int,
    districts: List[str],
    occupation_ids: List[str],
    rows_created: int,
    rows_updated: int,
    rows_skipped: int,
    runs_created: int,
    source_coverage: Dict[str, Any],
) -> Dict[str, Any]:
    """Build the standard report dict."""
    return {
        "source_id": source_id,
        "rule_version": rule_version,
        "period_start": start_date.isoformat(),
        "period_end": end_date.isoformat(),
        "input_observations": input_observations,
        "eligible_observations": eligible_observations,
        "mapped_observations": mapped_observations,
        "unmapped_observations": unmapped_observations,
        "unknown_district_observations": unknown_district_observations,
        "needs_review_mapping_observations": needs_review_mapping_observations,
        "districts": districts,
        "occupations": occupation_ids,
        "rows_created": rows_created,
        "rows_updated": rows_updated,
        "rows_skipped": rows_skipped,
        "runs_created": runs_created,
        "source_coverage": source_coverage,
    }
