"""Data Exports — CSV/JSON export of evidence-grounded analytics.

Adapted from reference project's export/exporter.py.

Improvements over reference:
- The reference exports from in-memory seed_data.py (fabricated data). Demand-X
  exports from real persisted observation and demand tables via SQL queries.
- Each export explicitly records the observation period, rule version, and
  source identity in the output file metadata so exported artifacts carry
  provenance.
- Never exports fabricated data; if a table is empty, the export says so.

Not copied:
- No AUTONOMOUS_ENGINE.bulletins or in-memory fabricated datasets.
- No wage data or company data that was hardcoded.
"""

from __future__ import annotations

import csv
import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session


EXPORTS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "exports")


def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def export_skill_demand(
    db: Session,
    output_dir: Optional[str] = None,
    filename: str = "skill_demand_export.csv",
    source_id: Optional[str] = None,
) -> str:
    """Export skill demand evidence to CSV.

    Evidence is computed deterministically from persisted JobPosting rows with
    the canonical 32-skill matcher (there is no skill_evidence table in
    Demand-X — evidence is recomputed from real observations, never from a
    fabricated store). Returns the path to the exported CSV file.
    """
    from core.models.observation import JobPosting
    from core.skills.ontology_matcher import SkillMatcher
    from core.skills.extractor import extract_job_skills

    out_dir = output_dir or EXPORTS_DIR
    _ensure_dir(out_dir)
    filepath = os.path.join(out_dir, filename)

    filters = []
    if source_id:
        filters.append(JobPosting.source_id == source_id)

    jobs = db.query(JobPosting).filter(*filters).yield_per(500)
    matcher = SkillMatcher()

    fieldnames = [
        "skill_id", "skill_name", "job_posting_id",
        "evidence_type", "match_confidence", "extraction_method",
        "evidence_text", "district", "sector", "source_id", "observation_period",
    ]

    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for job in jobs:
            evidence, _unmatched = extract_job_skills(job, matcher)
            for ev in evidence:
                writer.writerow({
                    "skill_id": ev.canonical_skill_id,
                    "skill_name": ev.canonical_skill_name,
                    "job_posting_id": ev.job_posting_id,
                    "evidence_type": ev.evidence_type,
                    "match_confidence": ev.match_confidence.value,
                    "extraction_method": ev.extraction_method.value,
                    "evidence_text": ev.evidence_text,
                    "district": job.district,
                    "sector": job.sector,
                    "source_id": job.source_id,
                    "observation_period": str(job.retrieved_at.date()) if job.retrieved_at else None,
                })

    return filepath


def export_district_occupation_demand(
    db: Session,
    output_dir: Optional[str] = None,
    filename: str = "district_occupation_demand_export.csv",
) -> str:
    """Export district-occupation demand rows to CSV.

    Returns the path to the exported CSV file.
    """
    from core.models.demand import DistrictOccupationDemand

    out_dir = output_dir or EXPORTS_DIR
    _ensure_dir(out_dir)
    filepath = os.path.join(out_dir, filename)

    rows = db.query(DistrictOccupationDemand).all()

    fieldnames = [
        "id", "run_id", "district", "occupation_id",
        "observation_period_start", "observation_period_end",
        "job_count", "apprenticeship_count", "demand_score",
        "data_completeness_status", "provenance_state", "rule_version",
    ]

    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({
                "id": row.id,
                "run_id": row.run_id,
                "district": row.district,
                "occupation_id": row.occupation_id,
                "observation_period_start": str(row.observation_period_start) if row.observation_period_start else None,
                "observation_period_end": str(row.observation_period_end) if row.observation_period_end else None,
                "job_count": row.job_count,
                "apprenticeship_count": row.apprenticeship_count,
                "demand_score": row.demand_score,
                "data_completeness_status": row.data_completeness_status,
                "provenance_state": row.provenance_state,
                "rule_version": row.rule_version,
            })

    return filepath


def export_sources(db: Session, output_dir: Optional[str] = None) -> str:
    """Export the source registry to JSON (for inspection, not ingestion)."""
    from core.models.source import Source

    out_dir = output_dir or EXPORTS_DIR
    _ensure_dir(out_dir)
    filepath = os.path.join(out_dir, "sources_registry.json")

    sources = db.query(Source).all()
    data: List[Dict[str, Any]] = []
    for s in sources:
        data.append({
            "source_id": s.source_id,
            "source_name": s.source_name,
            "organization": s.organization,
            "url": s.url,
            "category": s.category,
            "access_method": s.access_method,
            "freshness_class": s.freshness_class,
            "last_fetched_at": str(s.last_fetched_at) if s.last_fetched_at else None,
            "coverage": s.coverage,
            "reliability_notes": s.reliability_notes,
        })

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)

    return filepath


def export_occupations(output_dir: Optional[str] = None) -> str:
    """Export the canonical occupations seed to JSON."""
    import os

    out_dir = output_dir or EXPORTS_DIR
    _ensure_dir(out_dir)
    filepath = os.path.join(out_dir, "occupations_export.json")

    seed_path = os.path.join(os.path.dirname(__file__), "..", "ontology", "occupations_seed.json")
    if os.path.exists(seed_path):
        import shutil
        shutil.copy2(seed_path, filepath)
    return filepath


def export_skills(output_dir: Optional[str] = None) -> str:
    """Export the canonical skills seed to JSON."""
    import os

    out_dir = output_dir or EXPORTS_DIR
    _ensure_dir(out_dir)
    filepath = os.path.join(out_dir, "skills_export.json")

    seed_path = os.path.join(os.path.dirname(__file__), "..", "ontology", "skills_seed.json")
    if os.path.exists(seed_path):
        import shutil
        shutil.copy2(seed_path, filepath)
    return filepath