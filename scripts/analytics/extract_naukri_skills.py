"""CLI entrypoint for the Skill Knowledge Base & Candidate Discovery engine.

Extracts canonical-skill evidence from all persisted Naukri job observations
and discovers NEW candidate skills — no LLM, deterministic, read-only.

Writes:
  - data/analytics/skill_extraction_report.json
  - data/analytics/skill_extraction_summary.csv
  - data/analytics/naukri_skill_candidates.csv

Usage:
    python scripts/analytics/extract_naukri_skills.py [--source-id SOURCE] [--top-candidates N]
"""

import os
import sys
import json
import csv
import argparse
from datetime import datetime, timezone

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from core.skills.knowledge_base import build_skill_knowledge_base
from core.skills.models import ExtractionSummaryRecord, SkillCandidate
from core.skills.ontology_matcher import SkillMatcher


def _build_db_url() -> str:
    return os.environ.get(
        "DATABASE_URL",
        "postgresql://postgres:postgres@localhost:5432/demand_x",
    )


def _write_report(report: dict, path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)
    print(f"[report] written to {path}")


def _write_summary_csv(report: dict, path: str) -> None:
    """Serialize the report's top-skills payload into a CSV for review.

    Since the extraction engine does not persist to DB, the summary rows are
    reconstructed from the report's top_skills_by_job_count entries (which
    already carry job_count + mention_count) merged with the confidence
    breakdown carried in the report.
    """
    rows = report.get("top_skills_by_job_count", [])
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "canonical_skill_id", "canonical_skill_name", "job_count",
            "mention_count", "source_skill_mentions", "title_mentions",
            "description_mentions", "high_confidence", "medium_confidence",
            "low_confidence", "verification_status",
        ])
        for row in rows:
            writer.writerow([
                row["skill_id"], row["skill_name"], row["job_count"],
                row["mention_count"],
                row.get("source_skill_mentions", 0),
                row.get("title_mentions", 0),
                row.get("description_mentions", 0),
                row.get("high_confidence", 0),
                row.get("medium_confidence", 0),
                row.get("low_confidence", 0),
                "SEED_NEEDS_REVIEW",  # canonical seed skills keep seed status
            ])
    print(f"[csv] summary written to {path} ({len(rows)} rows)")


def _write_candidates(report: dict, path: str) -> None:
    rows = report.get("top_new_candidates", [])
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "candidate_skill", "job_count", "mention_count", "recommended_action",
            "verification_status", "observed_forms", "example_source_skills",
        ])
        for row in rows:
            writer.writerow([
                row["candidate_skill"], row["job_count"],
                row.get("mention_count", 0),
                row.get("recommended_action", "NEEDS_REVIEW"),
                "NEEDS_REVIEW",
                row.get("observed_forms", row["candidate_skill"]),
                row.get("example_source_skills", ""),
            ])
    print(f"[csv] candidates written to {path} ({len(rows)} rows)")


def main():
    parser = argparse.ArgumentParser(
        description="Extract skills + discover new candidates from persisted "
                    "Naukri job observations (deterministic, read-only).",
    )
    parser.add_argument(
        "--source-id",
        default="naukri-historical-promptcloud",
        help="Source to extract from (default: naukri-historical-promptcloud)",
    )
    parser.add_argument(
        "--top-candidates",
        type=int,
        default=30,
        help="Number of new candidate skills to surface (default: 30)",
    )
    parser.add_argument(
        "--min-candidate-mentions",
        type=int,
        default=2,
        help="Minimum distinct jobs/mentions for a candidate (default: 2)",
    )
    args = parser.parse_args()

    print("[1/2] Building Skill Knowledge Base from persisted observations...")
    print(f"      source_id={args.source_id}")

    report = build_skill_knowledge_base(
        db_url=_build_db_url(),
        source_id=args.source_id,
        top_candidate_n=args.top_candidates,
        min_candidate_mentions=args.min_candidate_mentions,
    )

    report["generated_at_local"] = datetime.now().isoformat()

    report_dir = os.path.join(PROJECT_ROOT, "data", "analytics")
    report_path = os.path.join(report_dir, "skill_extraction_report.json")
    summary_path = os.path.join(report_dir, "skill_extraction_summary.csv")
    candidates_path = os.path.join(report_dir, "naukri_skill_candidates.csv")

    print("[2/2] Writing artifacts...")
    _write_report(report, report_path)
    _write_summary_csv(report, summary_path)
    _write_candidates(report, candidates_path)

    # ── Print summary ────────────────────────────────────────────────────
    inp = report["input"]
    ext = report["extraction"]
    skills = report["skills"]
    print("\n=== Skill Extraction Summary ===")
    print(f"  jobs_processed:            {inp['jobs_processed']}")
    print(f"  jobs_with_source_skills:   {inp['jobs_with_source_skills']}")
    print(f"  jobs_with_description:     {inp['jobs_with_description']}")
    print(f"  jobs_with_skill_evidence:  {ext['jobs_with_skill_evidence']}")
    print(f"  total_evidence_rows:       {ext['total_evidence_rows']}")
    print(f"  unique_skills_with_evidence: {ext['unique_evidence_skills']} of "
          f"{skills['canonical_seed_count']} canonical seed skills")
    print(f"  matched_mentions:          {ext['matched_mentions']} "
          f"(from titles/descriptions)")
    print(f"  unmatched_mentions:        {ext['unmatched_mentions']}")
    print(f"  total_mentions_observed:   {ext['total_mentions_observed']} "
          f"(matched + unmatched)")
    print(f"  invariant:                 {ext['metric_invariant']} "
          f"=> {ext['matched_mentions']} + {ext['unmatched_mentions']} "
          f"== {ext['total_mentions_observed']}")
    print(f"  new_candidates_discovered: {skills['new_candidates_discovered']}")
    print(f"  confidence:                {ext['mention_confidence']}")
    print(f"  source_policy:             {ext['source_policy']}")
    print("\n--- Top canonical technical skills (by title/desc mentions) ---")
    for row in report["top_skills_by_job_count"][:10]:
        print(f"  {row['skill_id']:14s} {row['skill_name']:55s} "
              f"jobs={row['job_count']:6d} mentions={row['mention_count']:6d}")
    print("\n--- Top new candidate skills ---")
    for row in report["top_new_candidates"][:10]:
        print(f"  {row['candidate_skill']:30s} jobs={row['job_count']:6d}"
              f"  mentions={row.get('mention_count',0):6d}")
    print("\n--- Top unmatched technical phrases (from titles/descriptions) ---")
    for row in report["top_unmatched_technical_phrases"][:10]:
        print(f"  {row['phrase']:30s} mentions={row['mention_count']:6d}"
              f"  jobs={row['distinct_jobs']:6d}")
    print("\nNOTE: No skill is 'in demand' yet. This step only extracts and")
    print("      normalizes skill evidence. Verification status for NEW skills")
    print("      is NEEDS_REVIEW. Demand scoring remains a later step.")
    print("================================\n")


if __name__ == "__main__":
    main()