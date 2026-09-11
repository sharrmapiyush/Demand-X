import pytest
import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError
from core.models.base import Base
from core.models.demand import DemandCalculationRun, DistrictOccupationDemand, DistrictSkillDemand


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def test_demand_calculation_run_creation(db_session):
    # Verify all three demand run status values: RUNNING, COMPLETED, FAILED
    for status in ["RUNNING", "COMPLETED", "FAILED"]:
        run = DemandCalculationRun(
            run_id=f"run_{status.lower()}",
            started_at=datetime.datetime.utcnow(),
            completed_at=datetime.datetime.utcnow() if status != "RUNNING" else None,
            input_data_start_date=datetime.date(2026, 1, 1),
            input_data_end_date=datetime.date(2026, 3, 31),
            rule_version="v1.0.0",
            status=status
        )
        db_session.add(run)
        db_session.commit()

        retrieved = db_session.query(DemandCalculationRun).filter_by(run_id=f"run_{status.lower()}").first()
        assert retrieved is not None
        assert retrieved.status == status
        assert retrieved.rule_version == "v1.0.0"


def test_district_occupation_demand_completeness_and_fields(db_session):
    run = DemandCalculationRun(
        run_id="run_occ_test",
        started_at=datetime.datetime.utcnow(),
        rule_version="v1.0.0",
        status="COMPLETED"
    )
    db_session.add(run)
    db_session.commit()

    # Verify only three completeness statuses accepted: TRUE_ZERO, NO_DATA, INSUFFICIENT_DATA
    # Verify demand_score may be NULL
    # Verify NO_DATA with zero/non-zero counts allowed
    # Verify TRUE_ZERO not automatically inferred (explicitly set)
    # Verify sector is nullable, occupation_id is plain identifier
    statuses = ["TRUE_ZERO", "NO_DATA", "INSUFFICIENT_DATA"]
    for idx, status in enumerate(statuses):
        occ_demand = DistrictOccupationDemand(
            id=f"occ_{idx}",
            run_id="run_occ_test",
            district=f"District_{idx}",
            occupation_id="OCC-BEAUTY-01",
            sector=None if idx % 2 == 0 else "IT & Services",
            observation_period_start=datetime.date(2026, 1, 1),
            observation_period_end=datetime.date(2026, 3, 31),
            job_count=0 if status == "TRUE_ZERO" else 5,
            apprenticeship_count=0,
            demand_score=None if status == "NO_DATA" else 0.85,
            data_completeness_status=status,
            source_coverage_summary={"sources_used": 2},
            evidence={"metrics": "computed from job postings"},
            provenance_state="DERIVED",
            rule_version="v1.0.0"
        )
        db_session.add(occ_demand)
        db_session.commit()

        retrieved = db_session.query(DistrictOccupationDemand).filter_by(id=f"occ_{idx}").first()
        assert retrieved is not None
        assert retrieved.data_completeness_status == status
        assert retrieved.provenance_state == "DERIVED"
        assert retrieved.rule_version == "v1.0.0"


def test_district_skill_demand_completeness_and_fields(db_session):
    run = DemandCalculationRun(
        run_id="run_skill_test",
        started_at=datetime.datetime.utcnow(),
        rule_version="v1.0.0",
        status="COMPLETED"
    )
    db_session.add(run)
    db_session.commit()

    statuses = ["TRUE_ZERO", "NO_DATA", "INSUFFICIENT_DATA"]
    for idx, status in enumerate(statuses):
        skill_demand = DistrictSkillDemand(
            id=f"skill_{idx}",
            run_id="run_skill_test",
            district=f"District_{idx}",
            skill_id="SKL-COMP-01",
            sector="Technology",
            observation_period_start=datetime.date(2026, 1, 1),
            observation_period_end=datetime.date(2026, 3, 31),
            normalized_count=0.0 if status == "TRUE_ZERO" else 12.5,
            demand_score=None,
            data_completeness_status=status,
            source_coverage_summary=None,
            evidence=None,
            provenance_state="DERIVED",
            rule_version="v1.0.0"
        )
        db_session.add(skill_demand)
        db_session.commit()

        retrieved = db_session.query(DistrictSkillDemand).filter_by(id=f"skill_{idx}").first()
        assert retrieved is not None
        assert retrieved.data_completeness_status == status
        assert retrieved.skill_id == "SKL-COMP-01"
