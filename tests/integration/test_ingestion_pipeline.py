import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from core.models.base import Base
from core.models.source import Source
from core.models.job import Job, JobStaging
from ingestion.pipelines.ncs_pipeline import ingest_snapshot, register_unverified_ncs_fixture_source


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def test_register_ncs_source(db_session):
    source = register_unverified_ncs_fixture_source(db_session)
    assert source.source_id == "ncs-pune-job-snapshot-unverified"
    assert source.access_method == "UNVERIFIED_FIXTURE"
    assert source.freshness_class == "STATIC"


def test_ingest_snapshot_pipeline(db_session):
    result = ingest_snapshot(db_session, "data/fixtures/ncs_pune_jobs_unverified_fixture.json")
    assert result["status"] == "success"
    assert result["classification"] == "UNVERIFIED_OR_SYNTHETIC"
    assert result["total_records_processed"] == 15
    assert result["staged"] == 15
    assert result["normalized"] == 15
    assert result["errors"] == 0

    # Verify jobs in db
    jobs = db_session.query(Job).all()
    assert len(jobs) == 15

    # Verify sector and district counts for pilot
    it_jobs = db_session.query(Job).filter(Job.sector == "IT-ITeS").all()
    auto_jobs = db_session.query(Job).filter(Job.sector == "Automotive/Manufacturing").all()
    elec_jobs = db_session.query(Job).filter(Job.sector == "Electronics").all()

    assert len(it_jobs) == 5
    assert len(auto_jobs) == 5
    assert len(elec_jobs) == 5

    for job in jobs:
        assert job.district == "Pune"
        assert job.state == "Maharashtra"
        assert job.source_id == "ncs-pune-job-snapshot-unverified"
        assert job.job_identity_hash is not None
        assert job.raw_json is not None
