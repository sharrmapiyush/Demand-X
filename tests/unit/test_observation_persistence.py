"""
Tests for observation persistence layer.
"""

import unittest
from datetime import datetime, date
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.models.base import Base
from core.models.observation import JobPosting, ObservationRelationship
from ingestion.contracts.observations import NormalizedJobPostingObservation
from core.services.observation_persistence import ObservationPersistenceService


class TestObservationPersistence(unittest.TestCase):
    """Unit tests for observation persistence with SQLite."""

    def setUp(self):
        """Fresh in-memory database per test so rows never leak across tests."""
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.session = sessionmaker(bind=self.engine)()
        self.service = ObservationPersistenceService(self.session)

    def tearDown(self):
        """Clean up session."""
        self.session.close()

    def _create_test_observation(self, title="Test Job", hash_suffix="001") -> NormalizedJobPostingObservation:
        """Helper to create a test observation."""
        return NormalizedJobPostingObservation(
            source_id="test-source",
            source_record_id="test-rec-001",
            job_title=title,
            employer_name="Test Company",
            location_text="Pune",
            district="Pune",
            state="Maharashtra",
            sector="IT",
            description="Test description",
            posted_date=date(2016, 5, 21),
            retrieved_at=datetime.utcnow(),
            source_url=None,
            status="ACTIVE",
            record_identity_hash=f"hash_{hash_suffix}",
        )

    def test_persist_single_observation(self):
        """Test persisting a single observation."""
        obs = self._create_test_observation()
        job_posting, is_new = self.service.persist_observation(obs)

        self.assertTrue(is_new)
        self.assertEqual(job_posting.job_title, "Test Job")
        self.assertEqual(job_posting.status, "ACTIVE")
        self.assertEqual(job_posting.record_identity_hash, "hash_001")

    def test_persist_observation_with_provenance(self):
        """Test persisting with source type and freshness class."""
        obs = self._create_test_observation()
        job_posting, is_new = self.service.persist_observation(
            obs,
            source_type="SUPPLEMENTARY_HISTORICAL",
            freshness_class="HISTORICAL",
        )

        self.assertTrue(is_new)
        self.assertEqual(job_posting.source_type, "SUPPLEMENTARY_HISTORICAL")
        self.assertEqual(job_posting.freshness_class, "HISTORICAL")

    def test_persist_observation_with_skills_and_seats(self):
        """Test persisting with source skills and seats."""
        obs = self._create_test_observation()
        job_posting, is_new = self.service.persist_observation(
            obs,
            source_skills="Python, SQL, Docker",
            seats=5,
        )

        self.assertTrue(is_new)
        self.assertEqual(job_posting.source_skills, "Python, SQL, Docker")
        self.assertEqual(job_posting.seats, 5)

    def test_persist_observation_expired_status(self):
        """Test persisting with EXPIRED status override."""
        obs = self._create_test_observation()
        job_posting, is_new = self.service.persist_observation(
            obs,
            override_status="EXPIRED",
        )

        self.assertTrue(is_new)
        self.assertEqual(job_posting.status, "EXPIRED")

    def test_persist_observation_with_geographic_evidence(self):
        """Test that geographic evidence is persisted."""
        obs = self._create_test_observation()
        job_posting, is_new = self.service.persist_observation(obs)

        self.assertTrue(is_new)
        self.assertIsNotNone(job_posting.geographic_evidence)
        self.assertIn("district", job_posting.geographic_evidence)
        self.assertEqual(job_posting.geographic_evidence["district"], "Pune")

    def test_idempotent_persistence(self):
        """Test that persisting the same observation twice is idempotent."""
        obs = self._create_test_observation()

        # First persist
        job_posting_1, is_new_1 = self.service.persist_observation(obs)
        self.assertTrue(is_new_1)

        # Second persist (should be skipped)
        job_posting_2, is_new_2 = self.service.persist_observation(obs)
        self.assertFalse(is_new_2)
        self.assertEqual(job_posting_1.id, job_posting_2.id)

    def test_persist_observation_relationship_reposting(self):
        """Test persisting a REPOSTING relationship."""
        # First create a job posting
        obs = self._create_test_observation()
        job_posting, _ = self.service.persist_observation(obs)
        self.service.commit()

        # Create a relationship
        rel, is_new = self.service.persist_observation_relationship(
            member_record_id=job_posting.id,
            relationship_type="REPOSTING",
            group_id="group_001",
        )
        self.service.commit()

        # Verify
        self.assertTrue(is_new)
        self.assertEqual(rel.relationship_type, "REPOSTING")
        self.assertEqual(rel.group_id, "group_001")
        self.assertEqual(rel.member_record_id, job_posting.id)

    def test_persist_observation_relationship_uncertain(self):
        """Test persisting an UNCERTAIN relationship."""
        obs = self._create_test_observation()
        job_posting, _ = self.service.persist_observation(obs)
        self.service.commit()

        rel, is_new = self.service.persist_observation_relationship(
            member_record_id=job_posting.id,
            relationship_type="UNCERTAIN",
            group_id="group_002",
        )
        self.service.commit()

        self.assertTrue(is_new)
        self.assertEqual(rel.relationship_type, "UNCERTAIN")

    def test_persist_multiple_relationships_same_group(self):
        """Test multiple observations in same relationship group."""
        obs1 = self._create_test_observation(title="Job 1", hash_suffix="001")
        obs2 = self._create_test_observation(title="Job 2", hash_suffix="002")

        jp1, _ = self.service.persist_observation(obs1)
        jp2, _ = self.service.persist_observation(obs2)
        self.service.commit()

        rel1, _ = self.service.persist_observation_relationship(
            member_record_id=jp1.id,
            relationship_type="REPOSTING",
            group_id="group_repost",
        )
        rel2, _ = self.service.persist_observation_relationship(
            member_record_id=jp2.id,
            relationship_type="REPOSTING",
            group_id="group_repost",
        )
        self.service.commit()

        # Verify both are in same group
        self.assertEqual(rel1.group_id, rel2.group_id)

        # Query to verify
        related = self.session.query(ObservationRelationship).filter(
            ObservationRelationship.group_id == "group_repost"
        ).all()
        self.assertEqual(len(related), 2)

    def test_observation_historical_status_rule(self):
        """Test Naukri historical status mapping via explicit rule."""
        obs = self._create_test_observation()

        # Simulate the Naukri historical source rule
        job_posting, _ = self.service.persist_observation(
            obs,
            source_type="SUPPLEMENTARY_HISTORICAL",
            freshness_class="HISTORICAL",
            override_status="EXPIRED",  # Explicit rule
        )
        self.service.commit()

        self.assertEqual(job_posting.status, "EXPIRED")
        self.assertEqual(job_posting.source_type, "SUPPLEMENTARY_HISTORICAL")
        self.assertEqual(job_posting.freshness_class, "HISTORICAL")

    def test_observation_source_provenance_preserved(self):
        """Test that source provenance is fully preserved."""
        obs = self._create_test_observation()

        job_posting, _ = self.service.persist_observation(
            obs,
            source_type="SUPPLEMENTARY_HISTORICAL",
            freshness_class="HISTORICAL",
        )
        self.service.commit()

        # Verify all provenance fields
        self.assertEqual(job_posting.source_id, "test-source")
        self.assertEqual(job_posting.source_record_id, "test-rec-001")
        self.assertEqual(job_posting.source_type, "SUPPLEMENTARY_HISTORICAL")
        self.assertEqual(job_posting.freshness_class, "HISTORICAL")
        self.assertEqual(job_posting.record_identity_hash, "hash_001")


class TestObservationModel(unittest.TestCase):
    """Tests for the JobPosting model schema."""

    @classmethod
    def setUpClass(cls):
        """Set up in-memory SQLite database."""
        cls.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(cls.engine)
        cls.SessionLocal = sessionmaker(bind=cls.engine)

    def setUp(self):
        """Create a new session for each test."""
        self.session = self.SessionLocal()

    def tearDown(self):
        """Clean up session."""
        self.session.close()

    def test_job_posting_new_columns_exist(self):
        """Test that new columns exist in JobPosting model."""
        # Check model attributes
        self.assertTrue(hasattr(JobPosting, "source_skills"))
        self.assertTrue(hasattr(JobPosting, "seats"))
        self.assertTrue(hasattr(JobPosting, "source_type"))
        self.assertTrue(hasattr(JobPosting, "freshness_class"))
        self.assertTrue(hasattr(JobPosting, "geographic_evidence"))

    def test_observation_relationship_model(self):
        """Test ObservationRelationship model exists and has required fields."""
        self.assertTrue(hasattr(ObservationRelationship, "relationship_id"))
        self.assertTrue(hasattr(ObservationRelationship, "relationship_type"))
        self.assertTrue(hasattr(ObservationRelationship, "group_id"))
        self.assertTrue(hasattr(ObservationRelationship, "member_record_id"))
        self.assertTrue(hasattr(ObservationRelationship, "created_at"))


if __name__ == "__main__":
    unittest.main()
