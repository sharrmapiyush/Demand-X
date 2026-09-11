import pytest
import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError
from core.models.base import Base
from core.models.source import Source
from core.models.demand import DemandCalculationRun, DistrictOccupationDemand, DistrictSkillDemand


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


def test_unique_constraint_run_district_occupation_with_period(db_session):
    run = DemandCalculationRun(
        run_id="run_int_001",
        started_at=datetime.datetime.utcnow(),
        rule_version="v1.0.0",
        status="COMPLETED"
    )
    db_session.add(run)
    db_session.commit()

    period_start = datetime.date(2026, 1, 1)
    period_end = datetime.date(2026, 3, 31)

    d1 = DistrictOccupationDemand(
        id="do_1",
        run_id="run_int_001",
        district="Pune",
        occupation_id="OCC-001",
        observation_period_start=period_start,
        observation_period_end=period_end,
        job_count=10,
        apprenticeship_count=2,
        data_completeness_status="TRUE_ZERO",
        rule_version="v1.0.0"
    )
    db_session.add(d1)
    db_session.commit()

    # Duplicate constraint test: same run_id, district, occupation_id, observation period
    d2 = DistrictOccupationDemand(
        id="do_2",
        run_id="run_int_001",
        district="Pune",
        occupation_id="OCC-001",
        observation_period_start=period_start,
        observation_period_end=period_end,
        job_count=15,
        apprenticeship_count=3,
        data_completeness_status="TRUE_ZERO",
        rule_version="v1.0.0"
    )
    db_session.add(d2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_unique_constraint_run_district_skill_with_period(db_session):
    run = DemandCalculationRun(
        run_id="run_int_002",
        started_at=datetime.datetime.utcnow(),
        rule_version="v1.0.0",
        status="COMPLETED"
    )
    db_session.add(run)
    db_session.commit()

    period_start = datetime.date(2026, 1, 1)
    period_end = datetime.date(2026, 3, 31)

    s1 = DistrictSkillDemand(
        id="ds_1",
        run_id="run_int_002",
        district="Pune",
        skill_id="SKILL-001",
        observation_period_start=period_start,
        observation_period_end=period_end,
        normalized_count=5.0,
        data_completeness_status="NO_DATA",
        rule_version="v1.0.0"
    )
    db_session.add(s1)
    db_session.commit()

    # Duplicate constraint test: same run_id, district, skill_id, observation period
    s2 = DistrictSkillDemand(
        id="ds_2",
        run_id="run_int_002",
        district="Pune",
        skill_id="SKILL-001",
        observation_period_start=period_start,
        observation_period_end=period_end,
        normalized_count=8.0,
        data_completeness_status="NO_DATA",
        rule_version="v1.0.0"
    )
    db_session.add(s2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()
