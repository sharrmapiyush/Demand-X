"""
Tests for Naukri source registration and observation persistence.

Covers:
  1. source registration creates the source
  2. source registration is idempotent
  3. job observation with registered source succeeds
  4. job observation with missing source fails cleanly
  5. error counters correctly record failed rows
  6. transaction rollback works correctly
  7. batch continues safely after an individual record error
"""

import unittest
from datetime import datetime, date

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from core.models.base import Base
from core.models.source import Source
from core.models.observation import JobPosting, ObservationRelationship
from ingestion.contracts.observations import NormalizedJobPostingObservation
from core.services.observation_persistence import (
    ObservationPersistenceService,
    BulkObservationIngestor,
)


# ---------------------------------------------------------------------------
# SQLite FK enforcement — match PostgreSQL behaviour
# ---------------------------------------------------------------------------
@event.listens_for(create_engine("sqlite:///:memory:"), "connect")
def _set_sqlite_pragma(dbapi_conn, _):
    dbapi_conn.execute("PRAGMA foreign_keys = ON")


def _make_engine():
    engine = create_engine("sqlite:///:memory:")
    event.listen(engine, "connect", lambda c, _: c.execute("PRAGMA foreign_keys = ON"))
    Base.metadata.create_all(engine)
    return engine


def _register_source(session):
    """Register the canonical test source, return it."""
    source = session.query(Source).filter_by(source_id="test-src").first()
    if not source:
        source = Source(
            source_id="test-src",
            source_name="Test Source",
            organization="Test Org",
            url="https://example.com",
            category="demand",
            access_method="SOURCE_SNAPSHOT",
            freshness_class="HISTORICAL",
            source_type="SUPPLEMENTARY_HISTORICAL",
            official_government_source=False,
            verification_status="UNVERIFIED_EXTERNAL_DATASET",
            enabled=True,
        )
        session.add(source)
        session.commit()
    return source


def _obs(title="Software Engineer", hash_suffix="001"):
    return NormalizedJobPostingObservation(
        source_id="test-src",
        source_record_id=f"rec-{hash_suffix}",
        job_title=title,
        employer_name="Test Co",
        location_text="Pune",
        district="Pune",
        state="Maharashtra",
        sector="IT",
        description="Test",
        posted_date=date(2024, 1, 1),
        retrieved_at=datetime(2024, 6, 1),
        source_url=None,
        status="ACTIVE",
        record_identity_hash=f"aaaa{hash_suffix}",
    )


class TestSourceRegistration(unittest.TestCase):
    """1. registration creates the source
       2. registration is idempotent"""

    def setUp(self):
        self.engine = _make_engine()
        self.Session = sessionmaker(bind=self.engine)
        self.session = self.Session()

    def tearDown(self):
        self.session.close()

    def test_register_creates_source(self):
        from ingestion.pipelines.naukri_pipeline import (
            register_naukri_historical_source,
            NAUKRI_HISTORICAL_SOURCE_ID,
        )

        source = register_naukri_historical_source(self.session)

        self.assertIsNotNone(source)
        self.assertEqual(source.source_id, NAUKRI_HISTORICAL_SOURCE_ID)
        self.assertEqual(source.source_name, "PromptCloudHQ Jobs on Naukri.com")
        self.assertEqual(source.freshness_class, "HISTORICAL")
        self.assertEqual(source.source_type, "SUPPLEMENTARY_HISTORICAL")
        self.assertFalse(source.official_government_source)
        self.assertEqual(source.verification_status, "UNVERIFIED_EXTERNAL_DATASET")
        self.assertTrue(source.enabled)

        # Actually persisted
        row = self.session.query(Source).filter_by(source_id=NAUKRI_HISTORICAL_SOURCE_ID).first()
        self.assertIsNotNone(row)

    def test_register_idempotent(self):
        from ingestion.pipelines.naukri_pipeline import (
            register_naukri_historical_source,
            NAUKRI_HISTORICAL_SOURCE_ID,
        )

        s1 = register_naukri_historical_source(self.session)
        id1 = s1.source_id

        s2 = register_naukri_historical_source(self.session)
        id2 = s2.source_id

        self.assertEqual(id1, id2)
        count = self.session.query(Source).filter_by(source_id=NAUKRI_HISTORICAL_SOURCE_ID).count()
        self.assertEqual(count, 1)


class TestRegisteredSourcePersistence(unittest.TestCase):
    """3. job observation with registered source succeeds
       4. job observation with missing source fails cleanly"""

    def setUp(self):
        self.engine = _make_engine()
        self.Session = sessionmaker(bind=self.engine)
        self.session = self.Session()
        _register_source(self.session)

    def tearDown(self):
        self.session.close()

    def test_observation_with_registered_source(self):
        service = ObservationPersistenceService(self.session)
        obs = _obs()
        job, is_new = service.persist_observation(obs, override_status="EXPIRED")
        self.session.commit()

        self.assertTrue(is_new)
        self.assertEqual(job.job_title, "Software Engineer")
        self.assertEqual(job.status, "EXPIRED")
        self.assertEqual(job.source_id, "test-src")
        self.assertIsNotNone(job.record_identity_hash)

    def test_observation_with_missing_source_fails(self):
        obs = NormalizedJobPostingObservation(
            source_id="non-existent-source",
            source_record_id="rec-missing",
            job_title="Orphan Job",
            employer_name="No Co",
            retrieved_at=datetime(2024, 1, 1),
            status="ACTIVE",
            record_identity_hash="deadbeef00000000",
        )
        service = ObservationPersistenceService(self.session)
        with self.assertRaises(Exception) as ctx:
            job, _ = service.persist_observation(obs)
            self.session.flush()
        # Session remains usable after the failed flush
        self.session.rollback()

    def test_observation_idempotent(self):
        service = ObservationPersistenceService(self.session)
        obs = _obs()
        jp1, new1 = service.persist_observation(obs)
        self.session.commit()
        jp2, new2 = service.persist_observation(obs)
        self.session.commit()

        self.assertTrue(new1)
        self.assertFalse(new2)
        self.assertEqual(jp1.id, jp2.id)


class TestErrorAccounting(unittest.TestCase):
    """5. error counters correctly record failed rows"""

    def setUp(self):
        self.engine = _make_engine()
        self.Session = sessionmaker(bind=self.engine)
        self.session = self.Session()
        # Intentionally do NOT register source — every persist attempt will
        # trigger a FK violation → error

    def tearDown(self):
        self.session.close()

    def test_error_counter_matches_failed_observations(self):
        ingestor = BulkObservationIngestor(self.session, batch_size=10)
        observations = [_obs(f"Job-{i}", f"{i:04d}") for i in range(5)]

        report = ingestor.ingest_observations(
            observations,
            source_type="SUPPLEMENTARY_HISTORICAL",
            freshness_class="HISTORICAL",
            status_override="EXPIRED",
        )

        self.assertEqual(report["input_observations"], 5)
        self.assertEqual(report["inserted"], 0)
        self.assertEqual(report["skipped_duplicate"], 0)
        self.assertEqual(len(report["errors"]), 5)

        # The accounting invariant holds even for all-error batches
        self.assertEqual(
            report["input_observations"],
            report["inserted"] + report["skipped_duplicate"] + len(report["errors"]),
        )


class TestTransactionRollback(unittest.TestCase):
    """6. transaction rollback works correctly"""

    def setUp(self):
        self.engine = _make_engine()
        self.Session = sessionmaker(bind=self.engine)
        self.session = self.Session()
        _register_source(self.session)

    def tearDown(self):
        self.session.close()

    def test_failed_record_does_not_poison_session(self):
        """After one FK failure (missing source), the next good record succeeds."""
        ingestor = BulkObservationIngestor(self.session, batch_size=10)

        bad_obs = NormalizedJobPostingObservation(
            source_id="non-existent",
            source_record_id="bad",
            job_title="Bad Job",
            retrieved_at=datetime(2024, 1, 1),
            status="ACTIVE",
            record_identity_hash="bad11111111111111",
        )
        good_obs = _obs("Good Job", "good1")

        report = ingestor.ingest_observations([bad_obs, good_obs])

        self.assertEqual(len(report["errors"]), 1, "bad record error recorded")
        self.assertEqual(report["inserted"], 1, "good record inserted")
        self.assertFalse(report["fatal_error"], "no fatal error")


class TestBatchContinueAfterError(unittest.TestCase):
    """7. batch continues safely after an individual record error"""

    def setUp(self):
        self.engine = _make_engine()
        self.Session = sessionmaker(bind=self.engine)
        self.session = self.Session()
        _register_source(self.session)

    def tearDown(self):
        self.session.close()

    def test_alternating_good_bad_records(self):
        ingestor = BulkObservationIngestor(self.session, batch_size=10)

        bad = NormalizedJobPostingObservation(
            source_id="non-existent",
            source_record_id="x",
            job_title="Bad",
            retrieved_at=datetime(2024, 1, 1),
            status="ACTIVE",
            record_identity_hash="bad22222222222222",
        )

        observations = []
        for i in range(6):
            if i % 2 == 0:
                observations.append(_obs(f"Good-{i}", f"row{i:02d}"))
            else:
                observations.append(bad)

        report = ingestor.ingest_observations(
            observations,
            status_override="EXPIRED",
        )

        self.assertEqual(report["inserted"], 3)
        self.assertEqual(len(report["errors"]), 3)
        self.assertFalse(report["fatal_error"], "no fatal error")
        self.assertEqual(
            report["input_observations"],
            report["inserted"] + report["skipped_duplicate"] + len(report["errors"]),
        )


class TestRelationships(unittest.TestCase):
    """Additional: relationship insertion and rollback"""

    def setUp(self):
        self.engine = _make_engine()
        self.Session = sessionmaker(bind=self.engine)
        self.session = self.Session()
        _register_source(self.session)

    def tearDown(self):
        self.session.close()

    def test_relationship_persists_and_queries(self):
        service = ObservationPersistenceService(self.session)
        jp, _ = service.persist_observation(_obs("Rel-Test", "rel1"))
        self.session.commit()

        rel, is_new = service.persist_observation_relationship(
            member_record_id=jp.id,
            relationship_type="REPOSTING",
            group_id=jp.record_identity_hash,
        )
        self.session.commit()
        self.assertTrue(is_new, "first relationship should be new")

        rows = (
            self.session.query(ObservationRelationship)
            .filter_by(group_id=jp.record_identity_hash)
            .all()
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].relationship_type, "REPOSTING")


if __name__ == "__main__":
    unittest.main()
