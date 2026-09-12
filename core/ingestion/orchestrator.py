"""Raw ingestion orchestrator — governance → fetch → normalize → stage.

Adapted from reference project's ingestion/orchestrator.py (SHA256 content-hash
dedup against a raw-store) and crawlers/dispatcher.py (governance preflight).

Integrated with Demand-X rather than copied wholesale:
- Staging artifacts are written to the existing JobStaging model.
- Final persistence stays with the existing BulkObservationIngestor — this
  orchestrator is the governance + dedup framework in front of it.
- Every step has an auditable result; an empty source fetch is a legitimate
  outcome, never fabricated into synthetic observations.
"""

import hashlib
import json
import logging
import time
import uuid
from datetime import datetime, date
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from core.governance.policy import PolicyEnforcer, PolicyViolationException
from core.ingestion.sources import SourceConnector
from core.models.job import JobStaging

logger = logging.getLogger(__name__)


class RawIngestionOrchestrator:
    """Framework for governed, auditable raw ingestion."""

    def __init__(self, db: Optional[Session] = None):
        self.db = db
        self._seen_content_hashes: set = set()
        self._stats: Dict[str, Any] = {
            "fetched": 0,
            "normalized": 0,
            "validation_errors": 0,
            "duplicates": 0,
            "staged": 0,
            "empty_fetch": False,
        }

    def _reset_stats(self) -> None:
        self._stats = {
            "fetched": 0,
            "normalized": 0,
            "validation_errors": 0,
            "duplicates": 0,
            "staged": 0,
            "empty_fetch": False,
        }

    def ingest_source(
        self,
        connector: SourceConnector,
        source_type: str = "PRIMARY_LIVE",
        freshness_class: str = "STATIC",
        status_override: Optional[str] = None,
        days_to_keep: Optional[int] = None,
        **fetch_kwargs: Any,
    ) -> Dict[str, Any]:
        """Run one connector through the full governed pipeline.

        Returns a structured, auditable result dict. Never fabricates rows.
        """
        start = time.time()
        self._reset_stats()
        result: Dict[str, Any] = {
            "source_id": connector.source_id(),
            "status": "NOT_EXECUTED",
            "stage": None,
            "message": "",
            "duration_ms": 0,
            "policy": None,
        }

        # 1. Governance preflight
        if connector.policy is None:
            result.update({"status": "UNGOVERNED", "stage": "preflight"})
            return result
        try:
            PolicyEnforcer.verify(connector.policy)
        except PolicyViolationException as exc:
            result.update({
                "status": "BLOCKED_BY_POLICY",
                "stage": "preflight",
                "message": str(exc),
                "policy": {
                    "authorization_status": connector.policy.authorization_status.value,
                    "robots_status": connector.policy.robots_status.value,
                },
            })
            return result
        result["policy"] = {
            "authorization_status": connector.policy.authorization_status.value,
            "robots_status": connector.policy.robots_status.value,
        }

        # 2. Fetch (actual evidence only)
        raw_records: List[Dict[str, Any]] = connector.fetch_raw(**fetch_kwargs)
        result["stage"] = "fetch"
        result["fetched"] = len(raw_records)
        self._stats["fetched"] = len(raw_records)
        if not raw_records:
            self._stats["empty_fetch"] = True
            result.update({
                "status": "EMPTY_SOURCE",
                "stage": "fetch",
                "message": "Source returned no records; no observations generated.",
            })
            self._finalize(result, start)
            return result

        # 3. Normalize + validate + dedup
        staged_rows: List[Dict[str, Any]] = []
        reject_reasons: Dict[str, int] = {}

        for raw in raw_records:
            try:
                record = connector.normalize_job(raw)
            except Exception as exc:  # connector bug in this record only
                self._stats["validation_errors"] += 1
                reject_reasons[type(exc).__name__] = reject_reasons.get(type(exc).__name__, 0) + 1
                continue
            self._stats["normalized"] += 1

            errors = connector.validate_job(record)
            if errors:
                self._stats["validation_errors"] += 1
                reasons_key = "; ".join(sorted(errors))
                reject_reasons[reasons_key] = reject_reasons.get(reasons_key, 0) + 1
                continue

            content_hash = connector.generate_content_hash(raw)
            if content_hash in self._seen_content_hashes:
                self._stats["duplicates"] += 1
                continue
            self._seen_content_hashes.add(content_hash)

            record["_content_hash"] = content_hash
            staged_rows.append(record)

        result["stage"] = "normalize"
        result["normalized"] = self._stats["normalized"]
        result["validation_errors"] = self._stats["validation_errors"]
        result["duplicates"] = self._stats["duplicates"]
        result["reject_reasons"] = reject_reasons

        # 4. Persist staging (if a DB session is attached)
        if self.db is not None and staged_rows:
            inserted_staging = 0
            for record in staged_rows:
                # Within-batch dedup is handled by _seen_content_hashes above;
                # cross-run dedup is enforced downstream by the persisted
                # record_identity_hash in the BulkObservationIngestor.
                staging_id = record.get("_content_hash", f"stg-{uuid.uuid4().hex[:12]}")
                staging = JobStaging(
                    staging_id=staging_id,
                    source_id=result["source_id"],
                    source_record_id=record.get("source_record_id") or staging_id,
                    raw_title=record.get("job_title", ""),
                    raw_employer=record.get("employer_name", ""),
                    raw_description=record.get("description"),
                    raw_location=record.get("location_text"),
                    raw_salary=record.get("salary_text"),
                    raw_experience=record.get("experience_text"),
                    raw_education=record.get("education_text"),
                    raw_sector=record.get("sector", ""),
                    raw_district=record.get("district", ""),
                    raw_state=record.get("state", ""),
                    raw_posted_date=record.get("posted_date"),
                    raw_json=json.dumps(record, ensure_ascii=False, default=str),
                    is_valid="valid",
                    processing_status="pending",
                    created_at=datetime.utcnow(),
                )
                self.db.add(staging)
                inserted_staging += 1

            try:
                self.db.commit()
                self._stats["staged"] = inserted_staging
            except Exception as exc:
                self.db.rollback()
                logger.error("Staging commit failed: %s", exc)
                inserted_staging = 0

            result["stage"] = "staging"
            result["staged"] = inserted_staging

        # NOTE: promotion from staging to job_postings is the caller's step,
        # using the existing BulkObservationIngestor so that identity hashes,
        # provenance columns, and geographic evidence are preserved exactly.

        if not staged_rows:
            result.update({
                "status": "NO_NEW_ROWS",
                "message": "All fetched records were duplicates or invalid.",
            })
        else:
            result.update({
                "status": "STAGED",
                "message": f"Staged {len(staged_rows)} raw records.",
            })

        self._finalize(result, start)
        return result

    def _finalize(self, result: Dict[str, Any], start: float) -> None:
        result["duration_ms"] = round((time.time() - start) * 1000, 2)
        result["audit"] = {k: v for k, v in self._stats.items()}