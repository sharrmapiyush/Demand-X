import pytest
from datetime import date, datetime
from sqlalchemy.exc import IntegrityError
from db.session import SessionLocal, engine
from core.models.source import Source
from core.models.observation import JobPosting, ApprenticeshipOpportunity
from core.provenance.identity import generate_job_identity_hash, generate_apprenticeship_identity_hash


@pytest.fixture
def db_session():
    try:
        connection = engine.connect()
        connection.close()
    except Exception as e:
        pytest.skip(f"PostgreSQL database not reachable: {e}")

    session = SessionLocal()
    # Create test source
    source = session.query(Source).filter_by(source_id="test-obs-source").first()
    if not source:
        source = Source(
            source_id="test-obs-source",
            source_name="Test Observation Source",
            organization="Test Org",
            url="https://example.com",
            category="Test",
            access_method="SOURCE_SNAPSHOT",
            freshness_class="STATIC",
            enabled=True
        )
        session.add(source)
        session.commit()

    yield session

    # Cleanup test observations
    session.query(JobPosting).filter_by(source_id="test-obs-source").delete()
    session.query(ApprenticeshipOpportunity).filter_by(source_id="test-obs-source").delete()
    session.commit()
    session.close()


def test_insert_retrieve_job_posting(db_session):
    h = generate_job_identity_hash("test-obs-source", source_record_id="job-101", job_title="Test Job")
    job = JobPosting(
        id="job_test_101",
        source_id="test-obs-source",
        source_record_id="job-101",
        job_title="Test Job",
        district="Pune",
        state="Maharashtra",
        retrieved_at=datetime.utcnow(),
        record_identity_hash=h,
        status="ACTIVE"
    )
    db_session.add(job)
    db_session.commit()

    retrieved = db_session.query(JobPosting).filter_by(id="job_test_101").first()
    assert retrieved is not None
    assert retrieved.job_title == "Test Job"
    assert retrieved.district == "Pune"


def test_insert_retrieve_apprenticeship_opportunity(db_session):
    h = generate_apprenticeship_identity_hash("test-obs-source", source_record_id="appr-202", trade_title="Test Trade")
    appr = ApprenticeshipOpportunity(
        id="appr_test_202",
        source_id="test-obs-source",
        source_record_id="appr-202",
        trade_title="Test Trade",
        district="Pune",
        state="Maharashtra",
        seats_available=5,
        retrieved_at=datetime.utcnow(),
        record_identity_hash=h,
        status="ACTIVE"
    )
    db_session.add(appr)
    db_session.commit()

    retrieved = db_session.query(ApprenticeshipOpportunity).filter_by(id="appr_test_202").first()
    assert retrieved is not None
    assert retrieved.trade_title == "Test Trade"
    assert retrieved.seats_available == 5


def test_duplicate_record_identity_hash_rejection(db_session):
    h = generate_job_identity_hash("test-obs-source", source_record_id="job-dup", job_title="Duplicate Test")
    job1 = JobPosting(
        id="job_dup_1",
        source_id="test-obs-source",
        source_record_id="job-dup",
        job_title="Duplicate Test",
        retrieved_at=datetime.utcnow(),
        record_identity_hash=h,
        status="ACTIVE"
    )
    db_session.add(job1)
    db_session.commit()

    job2 = JobPosting(
        id="job_dup_2",
        source_id="test-obs-source",
        source_record_id="job-dup-different",
        job_title="Duplicate Test",
        retrieved_at=datetime.utcnow(),
        record_identity_hash=h,  # same hash
        status="ACTIVE"
    )
    db_session.add(job2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_source_foreign_key_behavior(db_session):
    h = generate_job_identity_hash("non-existent-source", job_title="FK Test")
    job = JobPosting(
        id="job_fk_1",
        source_id="non-existent-source",
        job_title="FK Test",
        retrieved_at=datetime.utcnow(),
        record_identity_hash=h,
        status="ACTIVE"
    )
    db_session.add(job)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_district_filtering(db_session):
    h1 = generate_job_identity_hash("test-obs-source", source_record_id="job-pune-1", job_title="Pune Job")
    h2 = generate_job_identity_hash("test-obs-source", source_record_id="job-mumbai-1", job_title="Mumbai Job")

    db_session.add(JobPosting(
        id="job_punes_1",
        source_id="test-obs-source",
        source_record_id="job-pune-1",
        job_title="Pune Job",
        district="Pune",
        retrieved_at=datetime.utcnow(),
        record_identity_hash=h1,
        status="ACTIVE"
    ))
    db_session.add(JobPosting(
        id="job_mumbais_1",
        source_id="test-obs-source",
        source_record_id="job-mumbai-1",
        job_title="Mumbai Job",
        district="Mumbai",
        retrieved_at=datetime.utcnow(),
        record_identity_hash=h2,
        status="ACTIVE"
    ))
    db_session.commit()

    # Scope by source: other sources (e.g. the Naukri historical ingestion) also
    # have Pune-district rows, so a bare district filter is not isolation-safe.
    pune_jobs = (
        db_session.query(JobPosting)
        .filter_by(source_id="test-obs-source", district="Pune")
        .all()
    )
    assert len(pune_jobs) == 1
    assert pune_jobs[0].job_title == "Pune Job"


def test_source_filtering(db_session):
    h = generate_job_identity_hash("test-obs-source", source_record_id="job-src-1", job_title="Source Test")
    db_session.add(JobPosting(
        id="job_src_1",
        source_id="test-obs-source",
        source_record_id="job-src-1",
        job_title="Source Test",
        retrieved_at=datetime.utcnow(),
        record_identity_hash=h,
        status="ACTIVE"
    ))
    db_session.commit()

    source_jobs = db_session.query(JobPosting).filter_by(source_id="test-obs-source").all()
    assert len(source_jobs) >= 1
