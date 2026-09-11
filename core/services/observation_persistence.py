"""
Reusable persistence service for canonical job posting observations.

Handles:
- Idempotent insertion/update of observations
- Preservation of identity hash, provenance, geographic evidence
- Preservation of source skills and seats
- Correct status assignment per source rules
"""

import uuid
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert as pg_insert
from core.models.observation import JobPosting, ObservationRelationship
from ingestion.contracts.observations import NormalizedJobPostingObservation
from core.geography.location_normalizer import normalize_location


class ObservationPersistenceService:
    """
    Service for persisting canonical observations into job_postings table.

    Supports idempotent persistence: running the same dataset twice will not
    create duplicate records (checked via record_identity_hash).
    """

    def __init__(self, session: Session):
        self.session = session

    def persist_observation(
        self,
        observation: NormalizedJobPostingObservation,
        source_skills: Optional[str] = None,
        seats: Optional[int] = None,
        source_type: Optional[str] = None,
        freshness_class: Optional[str] = None,
        override_status: Optional[str] = None,
    ) -> Tuple[JobPosting, bool]:
        """
        Persist a single canonical observation.

        Args:
            observation: NormalizedJobPostingObservation
            source_skills: Raw skills from source
            seats: Number of available positions
            source_type: e.g., "SUPPLEMENTARY_HISTORICAL", "PRIMARY_LIVE"
            freshness_class: e.g., "HISTORICAL", "FRESH"
            override_status: If provided, use this status instead of observation.status

        Returns:
            (JobPosting record, is_new: bool)
            - is_new=True if inserted
            - is_new=False if already existed (idempotent)
        """
        # Check for existing record by identity hash
        existing = self.session.query(JobPosting).filter(
            JobPosting.record_identity_hash == observation.record_identity_hash
        ).first()

        if existing:
            return existing, False

        # Get geographic evidence
        geo_evidence = None
        if observation.location_text:
            geo_res = normalize_location(observation.location_text)
            geo_evidence = {
                "raw_location": geo_res.raw_location,
                "district": geo_res.district,
                "state": geo_res.state,
                "locality": geo_res.locality,
                "location_scope": geo_res.location_scope,
                "location_confidence": geo_res.location_confidence,
                "matched_locations": geo_res.matched_locations,
                "location_evidence_level": geo_res.location_evidence_level,
                "has_pune_evidence": geo_res.has_pune_evidence,
                "pune_exclusivity": geo_res.pune_exclusivity,
                "normalization_method": geo_res.normalization_method,
            }

        # Determine status
        status = override_status or observation.status

        # Create new JobPosting
        job_posting = JobPosting(
            id=str(uuid.uuid4()),
            source_id=observation.source_id,
            source_record_id=observation.source_record_id,
            job_title=observation.job_title,
            employer_name=observation.employer_name,
            location_text=observation.location_text,
            district=observation.district,
            state=observation.state,
            sector=observation.sector,
            description=observation.description,
            posted_date=observation.posted_date,
            retrieved_at=observation.retrieved_at,
            source_url=observation.source_url,
            record_identity_hash=observation.record_identity_hash,
            status=status,
            source_skills=source_skills,
            seats=seats,
            source_type=source_type,
            freshness_class=freshness_class,
            geographic_evidence=geo_evidence,
        )

        self.session.add(job_posting)
        self.session.flush()

        return job_posting, True

    def persist_observation_relationship(
        self,
        member_record_id: str,
        relationship_type: str,
        group_id: str,
    ) -> tuple[ObservationRelationship, bool]:
        """
        Persist an observation relationship (e.g., REPOSTING, UNCERTAIN).

        Idempotent: if a relationship with the same member, group, and type
        already exists, returns the existing record without creating a duplicate.

        Args:
            member_record_id: FK to job_postings.id
            relationship_type: e.g., "REPOSTING", "UNCERTAIN"
            group_id: Collision group identifier

        Returns:
            (ObservationRelationship record, is_new: bool)
        """
        existing = (
            self.session.query(ObservationRelationship)
            .filter(
                ObservationRelationship.member_record_id == member_record_id,
                ObservationRelationship.group_id == group_id,
                ObservationRelationship.relationship_type == relationship_type,
            )
            .first()
        )
        if existing is not None:
            return existing, False

        rel = ObservationRelationship(
            relationship_id=str(uuid.uuid4()),
            relationship_type=relationship_type,
            group_id=group_id,
            member_record_id=member_record_id,
            created_at=datetime.utcnow(),
        )

        self.session.add(rel)
        self.session.flush()

        return rel, True

    def commit(self) -> None:
        """Commit the current transaction."""
        self.session.commit()

    def rollback(self) -> None:
        """Rollback the current transaction."""
        self.session.rollback()


class BulkObservationIngestor:
    """
    Bulk ingestion coordinator for observations + relationships.

    Handles batched persistence with transactional safety.
    """

    def __init__(self, session: Session, batch_size: int = 500):
        self.session = session
        self.batch_size = batch_size
        self.service = ObservationPersistenceService(session)

    def ingest_observations(
        self,
        observations: List[NormalizedJobPostingObservation],
        source_type: Optional[str] = None,
        freshness_class: Optional[str] = None,
        status_override: Optional[str] = None,
        source_skills_map: Optional[Dict[str, str]] = None,
        seats_map: Optional[Dict[str, int]] = None,
    ) -> Dict[str, Any]:
        """
        Ingest a batch of observations.

        Each observation is persisted inside its own SAVEPOINT (``begin_nested``)
        so that a single failing record rolls back only that record and the batch
        can continue. The outer transaction is committed periodically. If a batch
        commit itself fails (systemic error), the transaction is rolled back and
        ingestion stops with a ``fatal_error`` recorded — the session is never left
        in a failed-transaction state and no success is reported after a failure.

        Args:
            observations: List of NormalizedJobPostingObservation
            source_type: Applied to all observations
            freshness_class: Applied to all observations
            status_override: Applied to all observations
            source_skills_map: Dict[record_identity_hash] -> skills_text
            seats_map: Dict[record_identity_hash] -> seat_count

        Returns:
            Ingestion report with honest counts:
            input_observations = inserted + skipped_duplicate + len(errors)
            (plus the last successfully staged row before a fatal commit error)
        """
        report = {
            "input_observations": len(observations),
            "inserted": 0,
            "skipped_duplicate": 0,
            "errors": [],
            "job_posting_ids": [],
            "inserted_identity_hashes": [],
            "fatal_error": None,
            "committed_at": None,
        }

        source_skills_map = source_skills_map or {}
        seats_map = seats_map or {}

        for i, obs in enumerate(observations):
            # SAVEPOINT: individual record failure rolls back only this record.
            try:
                with self.session.begin_nested():
                    skills = source_skills_map.get(obs.record_identity_hash)
                    seats = seats_map.get(obs.record_identity_hash)

                    job_posting, is_new = self.service.persist_observation(
                        obs,
                        source_skills=skills,
                        seats=seats,
                        source_type=source_type,
                        freshness_class=freshness_class,
                        override_status=status_override,
                    )
            except Exception as e:
                report["errors"].append({
                    "index": i,
                    "identity_hash": obs.record_identity_hash,
                    "source_record_id": obs.source_record_id,
                    "job_title": obs.job_title[:100] if obs.job_title else None,
                    "error": f"{type(e).__name__}: {e}",
                })
                continue

            # Savepoint committed; the record is staged in the outer transaction.
            if is_new:
                report["inserted"] += 1
                report["job_posting_ids"].append(job_posting.id)
                report["inserted_identity_hashes"].append(job_posting.record_identity_hash)
            else:
                report["skipped_duplicate"] += 1

            # Periodic commit of the outer transaction.
            if (i + 1) % self.batch_size == 0:
                try:
                    self.service.commit()
                    report["committed_at"] = i + 1
                except Exception as e:
                    self.service.rollback()
                    report["fatal_error"] = (
                        f"batch commit failed at row {i} "
                        f"({type(e).__name__}: {e}); transaction rolled back"
                    )
                    break

        # Final commit of everything staged since the last batch commit.
        if report["inserted"] > 0 and report["fatal_error"] is None:
            try:
                self.service.commit()
                report["committed_at"] = len(observations)
            except Exception as e:
                self.service.rollback()
                report["fatal_error"] = (
                    f"final commit failed ({type(e).__name__}: {e}); "
                    "transaction rolled back"
                )

        return report

    def ingest_relationships(
        self,
        relationships: List[Dict[str, str]],
    ) -> Dict[str, Any]:
        """
        Ingest observation relationships.

        Each relationship is persisted inside its own SAVEPOINT so a single bad
        relationship (e.g. referencing a non-existent member record) does not
        poison the rest of the batch.

        Args:
            relationships: List of {member_record_id, relationship_type, group_id}

        Returns:
            Ingestion report
        """
        report = {
            "input_relationships": len(relationships),
            "inserted": 0,
            "skipped_duplicate": 0,
            "errors": [],
            "fatal_error": None,
        }

        for i, rel_data in enumerate(relationships):
            try:
                with self.session.begin_nested():
                    _rel, is_new = self.service.persist_observation_relationship(
                        member_record_id=rel_data["member_record_id"],
                        relationship_type=rel_data["relationship_type"],
                        group_id=rel_data["group_id"],
                    )
            except Exception as e:
                report["errors"].append({
                    "index": i,
                    "relationship_data": rel_data,
                    "error": f"{type(e).__name__}: {e}",
                })
                continue

            if is_new:
                report["inserted"] += 1
            else:
                report["skipped_duplicate"] += 1

            if (i + 1) % self.batch_size == 0:
                try:
                    self.service.commit()
                except Exception as e:
                    self.service.rollback()
                    report["fatal_error"] = (
                        f"batch commit failed at relationship row {i} "
                        f"({type(e).__name__}: {e}); transaction rolled back"
                    )
                    break

        if report["inserted"] > 0 and report["fatal_error"] is None:
            try:
                self.service.commit()
            except Exception as e:
                self.service.rollback()
                report["fatal_error"] = (
                    f"final commit failed ({type(e).__name__}: {e}); "
                    "transaction rolled back"
                )

        return report
