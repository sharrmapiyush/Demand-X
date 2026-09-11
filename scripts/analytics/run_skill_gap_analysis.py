"""CLI entrypoint for Skill Demand + Gap analysis.

Writes:
  - data/analytics/skill_demand_report.json
  - data/analytics/skill_demand_summary.csv
  - data/analytics/skill_gap_report.json
  - data/analytics/skill_gap_summary.csv

Usage:
    python scripts/analytics/run_skill_gap_analysis.py [--dry-run] [--source-id SOURCE]
"""

from __future__ import annotations

import csv
import json
import os
import sys
from datetime import date

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from core.analytics.skill_demand_engine import calculate_skill_demand
from core.analytics.skill_gap_engine import calculate_skill_gap


def _build_db_url() -> str:
    return os.environ.get(
        "DATABASE_URL",
        "postgresql://postgres:postgres@localhost:5432/demand_x",
    )


def _write_json(report: dict, path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)
    print(f"[report] written to {path}")


def _write_demand_csv(demand_rows: list, path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "skill_id", "skill_name", "distinct_job_count", "mention_count",
            "normalized_distinct_job_count",
            "high_confidence", "medium_confidence", "low_confidence",
            "title_mentions", "description_mentions", "source_skill_mentions",
            "verification_status",
        ])
        for row in demand_rows:
            conf = row.get("confidence", {})
            ev = row.get("evidence_type_breakdown", {})
            writer.writerow([
                row["skill_id"], row["skill_name"],
                row["distinct_job_count"], row["mention_count"],
                row["normalized_distinct_job_count"],
                conf.get("HIGH", 0), conf.get("MEDIUM", 0), conf.get("LOW", 0),
                ev.get("TITLE", 0), ev.get("DESCRIPTION", 0), ev.get("SOURCE_SKILL", 0),
                row.get("verification_status", "NEEDS_REVIEW"),
            ])
    print(f"[csv] demand summary written to {path} ({len(demand_rows)} rows)")


def _write_gap_csv(gap_rows: list, path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "skill_id", "skill_name", "gap_status",
            "demand_distinct_job_count", "demand_mention_count",
            "demand_normalized_distinct_job_count",
            "has_dvet_supply_evidence", "verification_status",
        ])
        for row in gap_rows:
            writer.writerow([
                row["skill_id"], row["skill_name"], row["gap_status"],
                row["demand_distinct_job_count"], row["demand_mention_count"],
                row["demand_normalized_distinct_job_count"],
                row["has_dvet_supply_evidence"], row.get("verification_status", ""),
            ])
    print(f"[csv] gap summary written to {path} ({len(gap_rows)} rows)")


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Skill Demand + Gap Analysis (deterministic, read-only)",
    )
    parser.add_argument(
        "--source-id",
        default="naukri-historical-promptcloud",
        help="Source to analyze (default: naukri-historical-promptcloud)",
    )
    parser.add_argument(
        "--district", default=None, help="Restrict to single district",
    )
    parser.add_argument(
        "--sector", default=None, help="Restrict to single sector",
    )
    parser.add_argument(
        "--start-date", default=None, help="Observation window start (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--end-date", default=None, help="Observation window end (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Run analysis but do not write reports",
    )
    args = parser.parse_args()

    db_url = _build_db_url()

    start_date = date.fromisoformat(args.start_date) if args.start_date else None
    end_date = date.fromisoformat(args.end_date) if args.end_date else None

    print("[1/3] Calculating per-skill demand...")
    demand_report = calculate_skill_demand(
        db_url=db_url,
        source_id=args.source_id,
        district=args.district,
        sector=args.sector,
        observation_period_start=start_date,
        observation_period_end=end_date,
    )

    print("[2/3] Calculating skill gaps...")
    gap_report = calculate_skill_gap(demand_report)

    report_dir = os.path.join(PROJECT_ROOT, "data", "analytics")

    if args.dry_run:
        print("\n[DRY RUN] No files written.\n")
    else:
        _write_json(demand_report, os.path.join(report_dir, "skill_demand_report.json"))
        _write_demand_csv(demand_report.get("demand_rows", []),
                          os.path.join(report_dir, "skill_demand_summary.csv"))
        _write_json(gap_report, os.path.join(report_dir, "skill_gap_report.json"))
        _write_gap_csv(gap_report.get("gap_rows", []),
                       os.path.join(report_dir, "skill_gap_summary.csv"))

    # ── Print summary ────────────────────────────────────────────────────
    print("\n=== Skill Demand Summary ===")
    print(f"  source_id:              {demand_report['source_id']}")
    print(f"  district:               {demand_report.get('district') or 'ALL'}")
    print(f"  total_jobs_evaluated:   {demand_report['total_jobs_evaluated']}")
    print(f"  jobs_with_skill_evidence: {demand_report['jobs_with_skill_evidence']}")
    print(f"  skills_with_evidence:   {demand_report['skills_with_evidence']}"
          f" / {len(demand_report.get('demand_rows', []))}")
    print(f"  total_evidence_rows:    {demand_report['total_evidence_rows']}")

    dvet = demand_report.get("dvet_supply_summary", {})
    print(f"  dvet_institutes:        {dvet.get('institute_count', 0)}")
    print(f"  dvet_skills_with_supply: {len(dvet.get('skills_with_supply_evidence', {}))}")

    print("\n=== Skill Gap Summary ===")
    for status, count in gap_report.get("gap_summary", {}).items():
        print(f"  {status:20s}: {count}")

    print(f"\n  Top 10 HIGH_GAP skills:")
    for row in [r for r in gap_report.get("gap_rows", []) if r["gap_status"] == "HIGH_GAP"][:10]:
        print(f"    {row['skill_id']:30s} jobs={row['demand_distinct_job_count']:6d}"
              f"  norm={row['demand_normalized_distinct_job_count']:.4f}")
    print()


if __name__ == "__main__":
    main()
