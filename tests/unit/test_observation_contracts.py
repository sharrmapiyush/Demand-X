import pytest
from datetime import date, datetime
from pydantic import ValidationError
from ingestion.contracts.observations import (
    RawJobPostingInput,
    NormalizedJobPostingObservation,
    RawApprenticeshipInput,
    NormalizedApprenticeshipObservation
)
from core.provenance.identity import (
    generate_job_identity_hash,
    generate_apprenticeship_identity_hash
)


def test_valid_job_posting_input():
    raw = RawJobPostingInput(
        source_id="ncs-test",
        job_title="Software Engineer",
        retrieved_at=datetime(2026, 9, 9, 12, 0, 0)
    )
    assert raw.job_title == "Software Engineer"
    assert raw.source_record_id is None
    assert raw.status == "ACTIVE"

    norm = NormalizedJobPostingObservation.from_raw(raw)
    assert norm.job_title == "Software Engineer"
    assert len(norm.record_identity_hash) == 64


def test_valid_apprenticeship_input():
    raw = RawApprenticeshipInput(
        source_id="dvet-test",
        trade_title="Electrician",
        seats_available=10,
        retrieved_at=datetime(2026, 9, 9, 12, 0, 0)
    )
    assert raw.trade_title == "Electrician"
    assert raw.seats_available == 10

    norm = NormalizedApprenticeshipObservation.from_raw(raw)
    assert norm.trade_title == "Electrician"
    assert len(norm.record_identity_hash) == 64


def test_required_field_validation():
    with pytest.raises(ValidationError):
        RawJobPostingInput(
            source_id="ncs-test",
            job_title="",
            retrieved_at=datetime.utcnow()
        )


def test_whitespace_only_rejection():
    with pytest.raises(ValidationError):
        RawJobPostingInput(
            source_id="   ",
            job_title="Software Engineer",
            retrieved_at=datetime.utcnow()
        )
    with pytest.raises(ValidationError):
        RawApprenticeshipInput(
            source_id="dvet-test",
            trade_title="   \t   ",
            retrieved_at=datetime.utcnow()
        )


def test_optional_fields_may_be_absent():
    raw = RawJobPostingInput(
        source_id="ncs-test",
        source_record_id=None,
        job_title="Data Analyst",
        employer_name=None,
        location_text=None,
        district=None,
        state=None,
        sector=None,
        description=None,
        posted_date=None,
        retrieved_at=datetime.utcnow(),
        source_url=None
    )
    assert raw.source_record_id is None
    assert raw.employer_name is None


def test_invalid_dates_rejected():
    with pytest.raises(ValidationError):
        RawJobPostingInput(
            source_id="ncs-test",
            job_title="Job",
            posted_date="not-a-date",
            retrieved_at=datetime.utcnow()
        )


def test_negative_apprenticeship_seats_rejected():
    with pytest.raises(ValidationError):
        RawApprenticeshipInput(
            source_id="dvet-test",
            trade_title="Welder",
            seats_available=-5,
            retrieved_at=datetime.utcnow()
        )


def test_valid_statuses_accepted():
    for status in ["ACTIVE", "inactive", "CLOSED", "expired", "PENDING"]:
        raw = RawJobPostingInput(
            source_id="test",
            job_title="Title",
            status=status,
            retrieved_at=datetime.utcnow()
        )
        assert raw.status == status.upper()


def test_invalid_status_rejected():
    with pytest.raises(ValidationError):
        RawJobPostingInput(
            source_id="test",
            job_title="Title",
            status="INVALID_STATUS",
            retrieved_at=datetime.utcnow()
        )


def test_source_record_id_remains_optional():
    raw = RawJobPostingInput(
        source_id="test",
        job_title="Title",
        retrieved_at=datetime.utcnow()
    )
    assert raw.source_record_id is None


def test_identity_generation_delegates_to_hash_utility():
    raw = RawJobPostingInput(
        source_id="test-source",
        source_record_id="rec-123",
        job_title="Dev",
        employer_name="Corp",
        location_text="Pune",
        posted_date=date(2026, 9, 1),
        retrieved_at=datetime.utcnow()
    )
    norm = NormalizedJobPostingObservation.from_raw(raw)
    expected_hash = generate_job_identity_hash(
        source_id="test-source",
        source_record_id="rec-123",
        job_title="Dev",
        employer_name="Corp",
        location_text="Pune",
        posted_date=date(2026, 9, 1)
    )
    assert norm.record_identity_hash == expected_hash
