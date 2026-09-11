"""
Bulk ingestion script for Naukri historical canonical observations.

Loads raw CSV, adapts through canonical adapter, persists to PostgreSQL,
registers the source in the Source Registry, and creates audited reposting
relationships.

Accounting invariant (reported to stdout and the report JSON):

    normalized_rows == inserted_rows + updated_rows + skipped_rows + error_rows

where:
    normalized_rows  - rows that passed the canonical adapter
    inserted_rows    - rows newly persisted
    updated_rows     - rows updated (0 today; the persistence layer is
                       insert-or-idempotent-skip by identity hash)
    skipped_rows     - rows already present (identity-hash deduplication)
    error_rows       - normalized rows that failed to persist

Rows rejected during normalization are tracked separately as `rejected_rows`
and are excluded from `normalized_rows` by definition:

    input_rows == normalized_rows + rejected_rows
"""

import os
import json
import csv
import time
from datetime import datetime
from typing import Dict, List, Any, Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from ingestion.adapters.naukri_historical import load_naukri_historical, normalize_naukri_row
from core.geography.location_normalizer import normalize_location
from core.services.observation_persistence import BulkObservationIngestor
from core.models.observation import JobPosting
from ingestion.pipelines.naukri_pipeline import (
    NAUKRI_HISTORICAL_SOURCE_ID,
    register_naukri_historical_source,
)


def load_collision_groups_csv(csv_path: str) -> List[Dict[str, str]]:
    """Load collision groups from CSV."""
    groups = []
    with open(csv_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            groups.append(row)
    return groups


def resolve_collision_groups_to_relationships(
    session,
    collision_groups: List[Dict[str, str]],
) -> List[Dict[str, str]]:
    """
    Resolve audited collision groups into observation relationship records.

    Each collision group's ``identity`` is the 16-character prefix of the
    canonical ``record_identity_hash`` that collision chose to persist (the
    surviving row for that identity). We map it to the persisted JobPosting
    and emit one relationship row per group.

    Returns:
        List of {member_record_id, relationship_type, group_id}
    """
    relationships = []
    unresolved = 0

    for i, row in enumerate(collision_groups):
        identity = row.get("identity", "").strip()
        classification = row.get("classification", "").strip()

        if not identity:
            continue

        posting = (
            session.query(JobPosting)
            .filter(JobPosting.record_identity_hash.startswith(identity))
            .first()
        )

        if posting is None:
            unresolved += 1
            continue

        relationships.append({
            "member_record_id": posting.id,
            "relationship_type": classification,
            "group_id": posting.record_identity_hash,  # full canonical identity
            "audit_identity": identity,                # provenance link to audit
        })

    if unresolved:
        print(f"  ⚠ {unresolved} collision groups could not be resolved to a persisted posting")

    return relationships


def ingest_naukri_historical(
    csv_path: Optional[str] = None,
    audit_path: Optional[str] = None,
    collision_groups_csv_path: Optional[str] = None,
    db_url: Optional[str] = None,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    Bulk ingest Naukri historical dataset.

    Args:
        csv_path: Path to raw Naukri CSV
        audit_path: Path to identity collision audit JSON
        collision_groups_csv_path: Path to collision groups CSV
        db_url: Database connection URL
        dry_run: If True, don't touch the database

    Returns:
        Detailed ingestion report
    """
    if csv_path is None:
        csv_path = "data/raw/naukri_historical/naukri_com-job_sample.csv"
    if audit_path is None:
        audit_path = "data/raw/naukri_historical/identity_collision_audit.json"
    if collision_groups_csv_path is None:
        collision_groups_csv_path = "data/raw/naukri_historical/identity_collision_groups.csv"
    if db_url is None:
        db_url = os.environ.get(
            "DATABASE_URL",
            "postgresql://postgres:postgres@localhost:5432/demand_x",
        )

    start_time = time.time()

    report: Dict[str, Any] = {
        "source_id": NAUKRI_HISTORICAL_SOURCE_ID,
        "start_timestamp": datetime.utcnow().isoformat(),
        "input_rows": 0,
        "normalized_rows": 0,
        "rejected_rows": 0,
        "inserted_rows": 0,
        "updated_rows": 0,
        "skipped_rows": 0,
        "error_rows": 0,
        "reject_reasons_summary": {},
        "relationship_groups": 0,   # groups from the audit (REPOSTING + UNCERTAIN)
        "relationship_rows": 0,     # relationship rows actually persisted
        "pune_exclusive": 0,
        "pune_shared": 0,
        "pune_mentioned": 0,
        "unknown_location": 0,
        "duration_seconds": 0,
        "errors": [],
        "dry_run": dry_run,
    }

    print("=" * 80)
    print("NAUKRI HISTORICAL CANONICAL OBSERVATION INGESTION")
    print("=" * 80)
    print(f"CSV path: {csv_path}")
    print(f"Audit path: {audit_path}")
    print(f"Source ID: {NAUKRI_HISTORICAL_SOURCE_ID}")
    print(f"Dry run: {dry_run}")
    print()

    # ---------------------------------------------------------------- stage 1: load
    raw_rows = load_naukri_historical(csv_path)
    report["input_rows"] = len(raw_rows)
    print(f"Loaded {len(raw_rows)} raw rows")

    collision_audit = load_collision_audit(audit_path)
    print(f"Loaded audit with {collision_audit['duplicate_identity_groups']} collision groups")

    collision_groups = load_collision_groups_csv(collision_groups_csv_path)
    report["relationship_groups"] = len(collision_groups)
    print(f"Loaded {len(collision_groups)} collision groups")

    # ---------------------------------------------------------------- stage 2: normalize
    retrieved_at = datetime.utcnow()
    observations = []
    skills_map = {}
    seats_map = {}
    pune_evidence_map = {}
    reject_reasons_tally = {}

    for i, row in enumerate(raw_rows):
        obs, reasons, _flags = normalize_naukri_row(row, retrieved_at)

        if obs is None:
            report["rejected_rows"] += 1
            for r in reasons:
                reject_reasons_tally[r] = reject_reasons_tally.get(r, 0) + 1
            continue

        observations.append(obs)
        report["normalized_rows"] += 1

        skills_str = row.get("skills", "")
        if skills_str:
            skills_map[obs.record_identity_hash] = str(skills_str).strip()

        seats_str = row.get("numberofpositions", "")
        if seats_str:
            try:
                seats_map[obs.record_identity_hash] = int(float(seats_str))
            except (ValueError, TypeError):
                pass

        geo_res = normalize_location(obs.location_text)
        if geo_res.has_pune_evidence:
            pune_evidence_map[obs.record_identity_hash] = geo_res.pune_exclusivity

    report["reject_reasons_summary"] = reject_reasons_tally
    print(f"Normalized {report['normalized_rows']} observations, rejected {report['rejected_rows']}")

    for exclusivity in pune_evidence_map.values():
        if exclusivity == "EXCLUSIVE":
            report["pune_exclusive"] += 1
        elif exclusivity == "SHARED":
            report["pune_shared"] += 1
        elif exclusivity == "MENTIONED":
            report["pune_mentioned"] += 1
    report["unknown_location"] = report["normalized_rows"] - sum([
        report["pune_exclusive"],
        report["pune_shared"],
        report["pune_mentioned"],
    ])

    print(f"  Pune evidence: EXCLUSIVE {report['pune_exclusive']} | "
          f"SHARED {report['pune_shared']} | MENTIONED {report['pune_mentioned']} | "
          f"UNKNOWN {report['unknown_location']}")

    if dry_run:
        report["duration_seconds"] = time.time() - start_time
        report["end_timestamp"] = datetime.utcnow().isoformat()
        print("\n[DRY RUN] Skipping database operations")
        return report

    # ---------------------------------------------------------------- stage 3: persist
    print("\nConnecting to database...")
    engine = create_engine(db_url)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()

    try:
        # 3a. Register the source (idempotent bootstrap).
        source = register_naukri_historical_source(session)
        print(f"Source registered: {source.source_id}")

        # 3b. Ingest observations with per-record savepoints.
        ingestor = BulkObservationIngestor(session, batch_size=500)

        print("Ingesting observations...")
        obs_report = ingestor.ingest_observations(
            observations,
            source_type="SUPPLEMENTARY_HISTORICAL",
            freshness_class="HISTORICAL",
            status_override="EXPIRED",
            source_skills_map=skills_map,
            seats_map=seats_map,
        )

        report["inserted_rows"] = obs_report["inserted"]
        report["updated_rows"] = 0
        report["skipped_rows"] = obs_report["skipped_duplicate"]
        report["error_rows"] = len(obs_report["errors"])
        report["errors"].extend(obs_report["errors"][:10])

        print(f"  Inserted       : {obs_report['inserted']}")
        print(f"  Skipped (dup)  : {obs_report['skipped_duplicate']}")
        print(f"  Errors         : {len(obs_report['errors'])}")

        if obs_report["fatal_error"] is not None:
            report["errors"].append({"fatal_error": obs_report["fatal_error"]})
            print(f"  ✗ FATAL: {obs_report['fatal_error']}")
            session.rollback()
        else:
            # 3c. Build relationships from the audited collision groups.
            relationships = resolve_collision_groups_to_relationships(session, collision_groups)

            if relationships:
                print(f"Persisting {len(relationships)} observation relationships...")
                rel_report = ingestor.ingest_relationships(relationships)

                report["relationship_rows"] = rel_report["inserted"]
                report["errors"].extend(rel_report["errors"][:10])

                print(f"  Relationships written: {rel_report['inserted']}")
                if rel_report.get("skipped_duplicate", 0) > 0:
                    print(f"  Relationships skipped (dup): {rel_report['skipped_duplicate']}")
                if rel_report["errors"]:
                    print(f"  Relationship errors: {len(rel_report['errors'])}")
                if rel_report["fatal_error"] is not None:
                    report["errors"].append({"fatal_error": rel_report["fatal_error"]})
                    print(f"  ✗ FATAL: {rel_report['fatal_error']}")
                    session.rollback()
            else:
                print("No collision groups resolved to relationships")

        # Reconciliation guard.
        reconciled = (
            report["normalized_rows"]
            == report["inserted_rows"]
            + report["updated_rows"]
            + report["skipped_rows"]
            + report["error_rows"]
        )
        report["reconciled"] = reconciled
        if not reconciled:
            print(
                "  WARNING: accounting invariant NOT satisfied: "
                f"normalized={report['normalized_rows']} != "
                f"inserted+updated+skipped+errors="
                f"{report['inserted_rows'] + report['updated_rows'] + report['skipped_rows'] + report['error_rows']}"
            )

    except Exception as e:
        session.rollback()
        report["errors"].append({"fatal_error": f"{type(e).__name__}: {e}"})
        print(f"  ✗ Fatal error: {e}")
    finally:
        session.close()

    # ---------------------------------------------------------------- summary
    report["duration_seconds"] = time.time() - start_time
    report["end_timestamp"] = datetime.utcnow().isoformat()

    print("\n" + "=" * 80)
    print("INGESTION SUMMARY")
    print("=" * 80)
    print(f"Input rows    : {report['input_rows']}")
    print(f"Normalized    : {report['normalized_rows']}")
    print(f"Rejected      : {report['rejected_rows']}")
    print(f"Inserted      : {report['inserted_rows']}")
    print(f"Updated       : {report['updated_rows']}")
    print(f"Skipped       : {report['skipped_rows']}")
    print(f"Errors        : {report['error_rows']}")
    print(f"Relationships : {report['relationship_rows']} rows across {report['relationship_groups']} groups")
    print(f"Reconciled    : {report.get('reconciled', 'n/a')}")
    print(f"Duration      : {report['duration_seconds']:.2f}s")
    print("=" * 80)

    return report


def load_collision_audit(audit_path: str) -> Dict[str, Any]:
    """Load the identity collision audit JSON."""
    with open(audit_path, "r", encoding="utf-8") as f:
        return json.load(f)


if __name__ == "__main__":
    import sys

    dry_run = "--dry-run" in sys.argv

    report = ingest_naukri_historical(dry_run=dry_run)

    report_path = "data/raw/naukri_historical/postgres_ingestion_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print(f"\nReport saved to {report_path}")