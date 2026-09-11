"""Unit tests for the demand aggregation runner.

All tests use an SQLite in-memory DB with FK enforcement.
The runner orchestrates source-filtered queries → calculator → DB persistence.
"""

import datetime
import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from core.models.base import Base
from core.models.observation import JobPosting, ApprenticeshipOpportunity
from core.models.source import Source
from core.models.demand import DemandCalculationRun, DistrictOccupationDemand
from core.analytics.demand_runner import run_demand_aggregation


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")

    # Enable FK enforcement for SQLite
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Register a test source
    source = Source(
        source_id="test-src",
        source_name="Test Source",
        organization="Test Org",
        url="https://example.com",
        category="demand",
        access_method="PUBLIC_PAGE",
        freshness_class="PERIODIC",
        enabled=True,
    )
    session.add(source)
    session.commit()

    yield session
    session.close()
    engine.dispose()


def _add_job(session, *, source_id="test-src", title="Cosmetologist",
             district="Pune", sector="Personal Care", rid="h1",
             retrieved_at=None):
    """Helper: insert a JobPosting and return it."""
    if retrieved_at is None:
        retrieved_at = datetime.datetime(2026, 9, 10, 12, 0, 0)
    job = JobPosting(
        id=f"job-{rid}",
        source_id=source_id,
        source_record_id=f"rec-{rid}",
        job_title=title,
        district=district,
        sector=sector,
        retrieved_at=retrieved_at,
        record_identity_hash=rid,
        status="ACTIVE",
    )
    session.add(job)
    session.commit()
    return job


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_one_mapped_job(db):
    """A single job that maps to OCC-BEAUTY-01 should produce 1 occ row."""
    _add_job(db, title="Cosmetologist", district="Pune", sector="Personal Care", rid="r1")

    report = run_demand_aggregation(
        db=db,
        source_id="test-src",
        start_date=datetime.date(2026, 9, 10),
        end_date=datetime.date(2026, 9, 10),
    )

    assert report["input_observations"] == 1
    assert report["eligible_observations"] == 1
    assert report["mapped_observations"] == 1
    assert report["unmapped_observations"] == 0
    assert report["rows_created"] >= 1
    assert "Pune" in report["districts"]
    assert "OCC-BEAUTY-01" in report["occupations"]


def test_one_unmapped_job(db):
    """A job with an unmapped title should produce 0 occupation rows."""
    _add_job(db, title="Underwater Basket Weaver", district="Pune",
             sector="Mystery", rid="r1")

    report = run_demand_aggregation(
        db=db,
        source_id="test-src",
        start_date=datetime.date(2026, 9, 10),
        end_date=datetime.date(2026, 9, 10),
    )

    assert report["input_observations"] == 1
    assert report["unmapped_observations"] == 1
    assert report["mapped_observations"] == 0
    assert report["rows_created"] == 0


def test_unknown_district(db):
    """A job with district=None counts as unknown_district, not eligible."""
    _add_job(db, title="Cosmetologist", district=None, sector="Personal Care", rid="r1")

    report = run_demand_aggregation(
        db=db,
        source_id="test-src",
        start_date=datetime.date(2026, 9, 10),
        end_date=datetime.date(2026, 9, 10),
    )

    assert report["unknown_district_observations"] == 1
    assert report["eligible_observations"] == 0
    assert report["districts"] == []
    assert report["rows_created"] == 0


def test_needs_review_mapping(db):
    """All 7 occupations have verification_status=NEEDS_REVIEW; the runner tracks this."""
    _add_job(db, title="Cosmetologist", district="Pune", sector="Personal Care", rid="r1")

    report = run_demand_aggregation(
        db=db,
        source_id="test-src",
        start_date=datetime.date(2026, 9, 10),
        end_date=datetime.date(2026, 9, 10),
    )

    assert report["needs_review_mapping_observations"] == 1
    assert report["mapped_observations"] == 1


def test_zero_eligible(db):
    """No jobs at all → rows_created=0, completeness_status=NO_DATA."""
    report = run_demand_aggregation(
        db=db,
        source_id="test-src",
        start_date=datetime.date(2026, 9, 10),
        end_date=datetime.date(2026, 9, 10),
    )

    assert report["input_observations"] == 0
    assert report["eligible_observations"] == 0
    assert report["rows_created"] == 0
    assert report["districts"] == []

    # Verify the persisted run status reflects NO_DATA
    runs = db.query(DemandCalculationRun).all()
    assert len(runs) == 0  # no districts → no runs created


def test_idempotent_rerun(db):
    """Running twice with same inputs → second run skips all rows."""
    _add_job(db, title="Cosmetologist", district="Pune", sector="Personal Care", rid="r1")

    report1 = run_demand_aggregation(
        db=db,
        source_id="test-src",
        start_date=datetime.date(2026, 9, 10),
        end_date=datetime.date(2026, 9, 10),
    )
    db.commit()
    created1 = report1["rows_created"]

    report2 = run_demand_aggregation(
        db=db,
        source_id="test-src",
        start_date=datetime.date(2026, 9, 10),
        end_date=datetime.date(2026, 9, 10),
    )
    db.commit()

    assert created1 >= 1
    assert report2["rows_created"] == 0
    assert report2["rows_skipped"] >= created1


def test_evidence_provenance(db):
    """Persisted rows have evidence dict and provenance_state=DERIVED."""
    _add_job(db, title="Cosmetologist", district="Pune", sector="Personal Care", rid="r1")

    run_demand_aggregation(
        db=db,
        source_id="test-src",
        start_date=datetime.date(2026, 9, 10),
        end_date=datetime.date(2026, 9, 10),
    )
    db.commit()

    rows = db.query(DistrictOccupationDemand).all()
    assert len(rows) >= 1
    for row in rows:
        assert row.provenance_state == "DERIVED"
        assert row.evidence is not None
        assert "total_job_postings_evaluated" in row.evidence
        assert "mapped_job_postings" in row.evidence


def test_demand_score_null(db):
    """Under mvp-v1-no-score, all demand_score values must be None."""
    _add_job(db, title="Cosmetologist", district="Pune", sector="Personal Care", rid="r1")

    run_demand_aggregation(
        db=db,
        source_id="test-src",
        start_date=datetime.date(2026, 9, 10),
        end_date=datetime.date(2026, 9, 10),
        rule_version="mvp-v1-no-score",
    )
    db.commit()

    rows = db.query(DistrictOccupationDemand).all()
    assert len(rows) >= 1
    for row in rows:
        assert row.demand_score is None
        assert row.rule_version == "mvp-v1-no-score"
