import pytest
from datetime import date, datetime
from core.models.observation import JobPosting, ApprenticeshipOpportunity
from core.provenance.identity import (
    generate_job_identity_hash,
    generate_apprenticeship_identity_hash
)


class TestJobPostingModel:
    def test_job_posting_construction(self):
        job = JobPosting(
            id="job_test_001",
            source_id="ncs-pune",
            job_title="Software Developer",
            employer_name="Tech Corp",
            location_text="Pune, Maharashtra",
            district="Pune",
            state="Maharashtra",
            sector="IT-ITeS",
            description="Software development role",
            posted_date=date(2026, 9, 1),
            retrieved_at=datetime(2026, 9, 9, 10, 0, 0),
            source_url="https://example.com/job/123",
            record_identity_hash="abc123",
            status="ACTIVE"
        )
        assert job.id == "job_test_001"
        assert job.job_title == "Software Developer"
        assert job.status == "ACTIVE"


class TestApprenticeshipOpportunityModel:
    def test_apprenticeship_opportunity_construction(self):
        appr = ApprenticeshipOpportunity(
            id="appr_test_001",
            source_id="dvet-apprenticeship",
            trade_title="Computer Operator and Programming Assistant",
            organization_name="Tech Industries Ltd",
            location_text="Pune, Maharashtra",
            district="Pune",
            state="Maharashtra",
            sector="IT-ITeS",
            seats_available=10,
            application_start_date=date(2026, 9, 1),
            application_end_date=date(2026, 9, 30),
            posted_date=date(2026, 8, 15),
            retrieved_at=datetime(2026, 9, 9, 10, 0, 0),
            source_url="https://example.com/apprenticeship/456",
            record_identity_hash="def456",
            status="ACTIVE"
        )
        assert appr.id == "appr_test_001"
        assert appr.trade_title == "Computer Operator and Programming Assistant"
        assert appr.seats_available == 10
        assert appr.status == "ACTIVE"


class TestJobIdentityHash:
    def test_source_record_id_takes_precedence(self):
        hash1 = generate_job_identity_hash(
            source_id="ncs-pune",
            source_record_id="NCS-JOB-12345",
            job_title="Software Developer",
            employer_name="Tech Corp",
            location_text="Pune",
            posted_date=date(2026, 9, 1)
        )
        hash2 = generate_job_identity_hash(
            source_id="ncs-pune",
            source_record_id="NCS-JOB-12345",
            job_title="DIFFERENT TITLE",
            employer_name="Different Employer",
            location_text="Mumbai",
            posted_date=date(2025, 1, 1)
        )
        assert hash1 == hash2, "source_record_id should take precedence when available"

    def test_same_logical_record_produces_same_hash(self):
        hash1 = generate_job_identity_hash(
            source_id="ncs-pune",
            source_record_id=None,
            job_title="  Software Developer  ",
            employer_name="  Tech Corp  ",
            location_text="Pune",
            posted_date=date(2026, 9, 1)
        )
        hash2 = generate_job_identity_hash(
            source_id="ncs-pune",
            source_record_id=None,
            job_title="software developer",
            employer_name="tech corp",
            location_text="pune",
            posted_date=date(2026, 9, 1)
        )
        assert hash1 == hash2, "Normalized fields should produce identical hashes"

    def test_materially_different_record_produces_different_hash(self):
        hash1 = generate_job_identity_hash(
            source_id="ncs-pune",
            source_record_id=None,
            job_title="Software Developer",
            employer_name="Tech Corp",
            location_text="Pune",
            posted_date=date(2026, 9, 1)
        )
        hash2 = generate_job_identity_hash(
            source_id="ncs-pune",
            source_record_id=None,
            job_title="Data Analyst",
            employer_name="Data Inc",
            location_text="Mumbai",
            posted_date=date(2026, 9, 1)
        )
        assert hash1 != hash2, "Different records should produce different hashes"

    def test_missing_optional_fields_do_not_break_hash(self):
        hash1 = generate_job_identity_hash(
            source_id="ncs-pune",
            source_record_id=None,
            job_title="Software Developer",
            employer_name="Tech Corp",
            location_text=None,
            posted_date=None
        )
        hash2 = generate_job_identity_hash(
            source_id="ncs-pune",
            source_record_id=None,
            job_title="Software Developer",
            employer_name="Tech Corp",
            location_text="",
            posted_date=None
        )
        assert hash1 == hash2, "Missing/empty optional fields should not break hash generation"


class TestApprenticeshipIdentityHash:
    def test_source_record_id_takes_precedence(self):
        hash1 = generate_apprenticeship_identity_hash(
            source_id="apprenticeship-india",
            source_record_id="AI-APPR-67890",
            trade_title="Computer Operator and Programming Assistant",
            organization_name="Tech Industries",
            location_text="Pune",
            application_start_date=date(2026, 9, 1),
            application_end_date=date(2026, 9, 30)
        )
        hash2 = generate_apprenticeship_identity_hash(
            source_id="apprenticeship-india",
            source_record_id="AI-APPR-67890",
            trade_title="DIFFERENT TRADE",
            organization_name="Different Org",
            location_text="Mumbai",
            application_start_date=date(2025, 1, 1),
            application_end_date=date(2025, 1, 31)
        )
        assert hash1 == hash2, "source_record_id should take precedence when available"

    def test_same_logical_record_produces_same_hash(self):
        hash1 = generate_apprenticeship_identity_hash(
            source_id="apprenticeship-india",
            source_record_id=None,
            trade_title="  Machinist  ",
            organization_name="  Manufacturing Ltd  ",
            location_text="Pune",
            application_start_date=date(2026, 9, 1),
            application_end_date=date(2026, 9, 30)
        )
        hash2 = generate_apprenticeship_identity_hash(
            source_id="apprenticeship-india",
            source_record_id=None,
            trade_title="machinist",
            organization_name="manufacturing ltd",
            location_text="pune",
            application_start_date=date(2026, 9, 1),
            application_end_date=date(2026, 9, 30)
        )
        assert hash1 == hash2, "Normalized fields should produce identical hashes"

    def test_materially_different_record_produces_different_hash(self):
        hash1 = generate_apprenticeship_identity_hash(
            source_id="apprenticeship-india",
            source_record_id=None,
            trade_title="Machinist",
            organization_name="Manufacturing Ltd",
            location_text="Pune",
            application_start_date=date(2026, 9, 1),
            application_end_date=date(2026, 9, 30)
        )
        hash2 = generate_apprenticeship_identity_hash(
            source_id="apprenticeship-india",
            source_record_id=None,
            trade_title="Fashion Design & Technology",
            organization_name="Fashion House",
            location_text="Mumbai",
            application_start_date=date(2026, 9, 1),
            application_end_date=date(2026, 9, 30)
        )
        assert hash1 != hash2, "Different records should produce different hashes"