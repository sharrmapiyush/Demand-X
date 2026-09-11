import pytest
import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from core.models.base import Base
from core.models.observation import JobPosting, ApprenticeshipOpportunity
from core.models.source import Source
from core.analytics.demand_calculator import calculate_district_demand


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    source = Source(
        source_id="test-source",
        source_name="Test Source",
        organization="Test Org",
        url="https://example.com",
        category="demand",
        access_method="PUBLIC_PAGE",
        freshness_class="PERIODIC",
        enabled=True
    )
    session.add(source)
    session.commit()

    yield session
    session.close()


def test_postgres_demand_calculator_simulation(db_session):
    start = datetime.date(2026, 1, 1)
    end = datetime.date(2026, 3, 31)

    job = JobPosting(
        id="job_pg_1",
        source_id="test-source",
        source_record_id="pg-rec-1",
        job_title="Cosmetologist",
        district="Pune",
        sector="Personal Care",
        retrieved_at=datetime.datetime(2026, 2, 1, 12, 0, 0),
        record_identity_hash="pghash1",
        status="ACTIVE"
    )
    db_session.add(job)
    db_session.commit()

    result = calculate_district_demand(db_session, "Pune", start, end)
    assert result["completeness_status"] == "INSUFFICIENT_DATA"
    assert len(result["occupation_demand"]) == 1
    assert result["occupation_demand"][0]["occupation_id"] == "OCC-BEAUTY-01"
