"""CLI entrypoint for demand aggregation.

Writes:
  - data/analytics/demand_run_report.json
  - data/analytics/district_occupation_demand.csv

Usage:
    python scripts/analytics/run_demand_aggregation.py [--dry-run] [--source-id SOURCE]
"""

import os
import sys
import json
import csv
import argparse
from datetime import date, datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Windows consoles default to cp1252, which cannot encode unicode in the
# summary output; force UTF-8 for stdout.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Ensure project root on sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from core.models.base import Base
from core.models.observation import JobPosting  # noqa: F401 — ensure model is loaded
from core.models.demand import DemandCalculationRun, DistrictOccupationDemand
from core.analytics.demand_runner import run_demand_aggregation


def _build_db_url() -> str:
    """Resolve the PostgreSQL connection URL from the environment.

    Follows the repo convention (same as scripts/ingestion/ingest_naukri_historical.py):
    read ``DATABASE_URL``, falling back to the default local connection.
    """
    return os.environ.get(
        "DATABASE_URL",
        "postgresql://postgres:postgres@localhost:5432/demand_x",
    )


def _write_report(report: dict, path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)
    print(f"[report] written to {path}")


def _write_csv(report: dict, db_session, path: str) -> None:
    """Export all DistrictOccupationDemand rows for this run to CSV."""
    # Find all run_ids that match the input period and rule_version
    runs = (
        db_session.query(DemandCalculationRun)
        .filter(
            DemandCalculationRun.input_data_start_date == report["period_start"],
            DemandCalculationRun.input_data_end_date == report["period_end"],
            DemandCalculationRun.rule_version == report["rule_version"],
        )
        .all()
    )
    run_ids = [r.run_id for r in runs]

    if not run_ids:
        # No runs — write an empty CSV with headers
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "run_id", "district", "occupation_id", "sector",
                "observation_period_start", "observation_period_end",
                "job_count", "apprenticeship_count", "demand_score",
                "data_completeness_status", "provenance_state", "rule_version",
            ])
        print(f"[csv] written to {path} (0 rows)")
        return

    rows = (
        db_session.query(DistrictOccupationDemand)
        .filter(DistrictOccupationDemand.run_id.in_(run_ids))
        .order_by(DistrictOccupationDemand.district, DistrictOccupationDemand.job_count.desc())
        .all()
    )

    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "run_id", "district", "occupation_id", "sector",
            "observation_period_start", "observation_period_end",
            "job_count", "apprenticeship_count", "demand_score",
            "data_completeness_status", "provenance_state", "rule_version",
        ])
        for row in rows:
            writer.writerow([
                row.run_id, row.district, row.occupation_id, row.sector,
                row.observation_period_start, row.observation_period_end,
                row.job_count, row.apprenticeship_count, row.demand_score,
                row.data_completeness_status, row.provenance_state, row.rule_version,
            ])
    print(f"[csv] written to {path} ({len(rows)} rows)")


def main():
    parser = argparse.ArgumentParser(
        description="Run demand aggregation on persisted job observations",
    )
    parser.add_argument(
        "--source-id",
        default="naukri-historical-promptcloud",
        help="Source to aggregate (default: naukri-historical-promptcloud)",
    )
    parser.add_argument(
        "--start-date",
        default="2026-09-10",
        help="Observation window start (YYYY-MM-DD, default: 2026-09-10)",
    )
    parser.add_argument(
        "--end-date",
        default="2026-09-10",
        help="Observation window end (YYYY-MM-DD, default: 2026-09-10)",
    )
    parser.add_argument("--district", default=None, help="Restrict to single district")
    parser.add_argument("--sector", default=None, help="Restrict to single sector")
    parser.add_argument(
        "--dry-run",
        "--report-only",
        action="store_true",
        help="Run aggregation but rollback (no DB writes)",
    )
    args = parser.parse_args()

    start_date = date.fromisoformat(args.start_date)
    end_date = date.fromisoformat(args.end_date)

    db_url = _build_db_url()
    engine = create_engine(db_url)
    Session = sessionmaker(bind=engine)
    db = Session()

    try:
        report = run_demand_aggregation(
            db=db,
            source_id=args.source_id,
            start_date=start_date,
            end_date=end_date,
            district=args.district,
            sector=args.sector,
        )

        report_dir = os.path.join(PROJECT_ROOT, "data", "analytics")
        report_path = os.path.join(report_dir, "demand_run_report.json")
        csv_path = os.path.join(report_dir, "district_occupation_demand.csv")

        if args.dry_run:
            db.rollback()
            print("\n[DRY RUN] Rolled back - no DB changes.\n")
        else:
            db.commit()
            print("\n[COMMITTED] Demand aggregation persisted.\n")

        _write_report(report, report_path)
        if not args.dry_run:
            _write_csv(report, db, csv_path)

        # Print summary
        print("=== Demand Aggregation Summary ===")
        print(f"  source_id:               {report['source_id']}")
        print(f"  period:                  {report['period_start']} to {report['period_end']}")
        print(f"  input_observations:      {report['input_observations']}")
        print(f"  eligible_observations:   {report['eligible_observations']}")
        print(f"  mapped_observations:     {report['mapped_observations']}")
        print(f"  unmapped_observations:   {report['unmapped_observations']}")
        print(f"  unknown_district:        {report['unknown_district_observations']}")
        print(f"  needs_review_mapping:    {report['needs_review_mapping_observations']}")
        print(f"  districts:               {report['districts']}")
        print(f"  occupations:             {report['occupations']}")
        print(f"  runs_created:            {report['runs_created']}")
        print(f"  rows_created:            {report['rows_created']}")
        print(f"  rows_updated:            {report['rows_updated']}")
        print(f"  rows_skipped:            {report['rows_skipped']}")
        print("==================================\n")

    except Exception as e:
        db.rollback()
        print(f"\n[ERROR] {type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        db.close()
        engine.dispose()


if __name__ == "__main__":
    main()
