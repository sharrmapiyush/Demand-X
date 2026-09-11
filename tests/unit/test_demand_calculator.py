import pytest
import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from core.models.base import Base
from core.models.observation import JobPosting, ApprenticeshipOpportunity
from core.models.source import Source
from core.analytics.demand_calculator import calculate_district_demand, resolve_occupation, generate_run_id


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Add test source
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


def test_empty_dataset_no_data(db_session):
    start = datetime.date(2026, 1, 1)
    end = datetime.date(2026, 3, 31)
    result = calculate_district_demand(db_session, "Pune", start, end, rule_version="mvp-v1-no-score")

    assert result["completeness_status"] == "NO_DATA"
    assert len(result["occupation_demand"]) == 0
    assert len(result["skill_demand"]) == 0


def test_zero_db_records_not_true_zero(db_session):
    start = datetime.date(2026, 1, 1)
    end = datetime.date(2026, 3, 31)
    result = calculate_district_demand(db_session, "Pune", start, end)
    assert result["completeness_status"] != "TRUE_ZERO"
    assert result["completeness_status"] == "NO_DATA"


def test_one_job_deterministic_match_insufficient_data(db_session):
    start = datetime.date(2026, 1, 1)
    end = datetime.date(2026, 3, 31)

    job = JobPosting(
        id="job_1",
        source_id="test-source",
        source_record_id="rec-1",
        job_title="Cosmetologist",
        district="Pune",
        sector="Personal Care",
        retrieved_at=datetime.datetime(2026, 2, 1, 12, 0, 0),
        record_identity_hash="hash1",
        status="ACTIVE"
    )
    db_session.add(job)
    db_session.commit()

    result = calculate_district_demand(db_session, "Pune", start, end)
    assert result["completeness_status"] == "INSUFFICIENT_DATA"
    assert len(result["occupation_demand"]) == 1
    occ_agg = result["occupation_demand"][0]
    assert occ_agg["occupation_id"] == "OCC-BEAUTY-01"
    assert occ_agg["job_count"] == 1
    assert occ_agg["demand_score"] is None
    assert occ_agg["data_completeness_status"] == "INSUFFICIENT_DATA"


def test_unmapped_job_excluded(db_session):
    start = datetime.date(2026, 1, 1)
    end = datetime.date(2026, 3, 31)

    job = JobPosting(
        id="job_unmapped",
        source_id="test-source",
        source_record_id="rec-2",
        job_title="Underwater Basket Weaver",
        district="Pune",
        sector="Mystery",
        retrieved_at=datetime.datetime(2026, 2, 1, 12, 0, 0),
        record_identity_hash="hash2",
        status="ACTIVE"
    )
    db_session.add(job)
    db_session.commit()

    result = calculate_district_demand(db_session, "Pune", start, end)
    assert result["completeness_status"] == "INSUFFICIENT_DATA"
    assert len(result["occupation_demand"]) == 0
    assert result["global_evidence"]["unmapped_job_postings"] == 1


def test_unknown_district_excluded(db_session):
    start = datetime.date(2026, 1, 1)
    end = datetime.date(2026, 3, 31)

    job = JobPosting(
        id="job_nodistrict",
        source_id="test-source",
        source_record_id="rec-3",
        job_title="Cosmetologist",
        district=None,
        sector="Personal Care",
        retrieved_at=datetime.datetime(2026, 2, 1, 12, 0, 0),
        record_identity_hash="hash3",
        status="ACTIVE"
    )
    db_session.add(job)
    db_session.commit()

    result = calculate_district_demand(db_session, "Pune", start, end)
    assert len(result["occupation_demand"]) == 0
    assert result["global_evidence"]["unknown_district_job_postings"] == 1


def test_unknown_sector_excluded(db_session):
    start = datetime.date(2026, 1, 1)
    end = datetime.date(2026, 3, 31)

    job = JobPosting(
        id="job_nosector",
        source_id="test-source",
        source_record_id="rec-4",
        job_title="Cosmetologist",
        district="Pune",
        sector=None,
        retrieved_at=datetime.datetime(2026, 2, 1, 12, 0, 0),
        record_identity_hash="hash4",
        status="ACTIVE"
    )
    db_session.add(job)
    db_session.commit()

    result = calculate_district_demand(db_session, "Pune", start, end)
    assert len(result["occupation_demand"]) == 0
    assert result["global_evidence"]["unknown_sector_job_postings"] == 1


def test_apprenticeship_opportunity_mapping(db_session):
    start = datetime.date(2026, 1, 1)
    end = datetime.date(2026, 3, 31)

    appr = ApprenticeshipOpportunity(
        id="appr_1",
        source_id="test-source",
        source_record_id="appr-rec-1",
        trade_title="Basic Cosmetology",
        district="Pune",
        sector="Personal Care",
        seats_available=25,
        retrieved_at=datetime.datetime(2026, 2, 1, 12, 0, 0),
        record_identity_hash="hash5",
        status="ACTIVE"
    )
    db_session.add(appr)
    db_session.commit()

    result = calculate_district_demand(db_session, "Pune", start, end)
    assert len(result["occupation_demand"]) == 1
    occ_agg = result["occupation_demand"][0]
    assert occ_agg["occupation_id"] == "OCC-BEAUTY-01"
    # Rule check: apprenticeship_count uses opportunity count (1), NOT seats_available (25)
    assert occ_agg["apprenticeship_count"] == 1


def test_determinism_same_inputs_same_output(db_session):
    start = datetime.date(2026, 1, 1)
    end = datetime.date(2026, 3, 31)

    job = JobPosting(
        id="job_det",
        source_id="test-source",
        source_record_id="rec-det",
        job_title="Cosmetologist",
        district="Pune",
        sector="Personal Care",
        retrieved_at=datetime.datetime(2026, 2, 1, 12, 0, 0),
        record_identity_hash="hash_det",
        status="ACTIVE"
    )
    db_session.add(job)
    db_session.commit()

    res1 = calculate_district_demand(db_session, "Pune", start, end, rule_version="v1")
    res2 = calculate_district_demand(db_session, "Pune", start, end, rule_version="v1")

    assert res1["run_id"] == res2["run_id"]
    assert res1["occupation_demand"] == res2["occupation_demand"]


def test_different_rule_version_distinct_run(db_session):
    start = datetime.date(2026, 1, 1)
    end = datetime.date(2026, 3, 31)

    res1 = calculate_district_demand(db_session, "Pune", start, end, rule_version="v1")
    res2 = calculate_district_demand(db_session, "Pune", start, end, rule_version="v2")

    assert res1["run_id"] != res2["run_id"]
    assert res1["rule_version"] == "v1"
    assert res2["rule_version"] == "v2"


def test_demand_score_null_under_mvp(db_session):
    start = datetime.date(2026, 1, 1)
    end = datetime.date(2026, 3, 31)
    job = JobPosting(
        id="job_score",
        source_id="test-source",
        source_record_id="rec-score",
        job_title="Cosmetologist",
        district="Pune",
        sector="Personal Care",
        retrieved_at=datetime.datetime(2026, 2, 1, 12, 0, 0),
        record_identity_hash="hash_score",
        status="ACTIVE"
    )
    db_session.add(job)
    db_session.commit()

    result = calculate_district_demand(db_session, "Pune", start, end, rule_version="mvp-v1-no-score")
    for occ in result["occupation_demand"]:
        assert occ["demand_score"] is None


def test_skill_demand_unavailable(db_session):
    start = datetime.date(2026, 1, 1)
    end = datetime.date(2026, 3, 31)
    result = calculate_district_demand(db_session, "Pune", start, end)
    assert len(result["skill_demand"]) == 0


def test_occupation_resolver_adversarial_cases(db_session):
    # Expected OCC mappings
    cases = [
        ("Cosmetologist", "OCC-BEAUTY-01"),
        ("Basic Cosmetology", "OCC-BEAUTY-01"),
        ("Computer Operator", "OCC-COMP-01"),
        ("Computer Programming Assistant", "OCC-COMP-01"),
        ("Motor Vehicle Mechanic", "OCC-AUTO-01"),
        ("Automotive Mechanic", "OCC-AUTO-01"),
        ("Garment Technician", "OCC-FASHION-01"),
        ("ICT System Maintenance Technician", "OCC-ICT-01"),
        ("Painter General", "OCC-PAINT-01"),
    ]
    for title, expected_id in cases:
        occ_id, _, _, _ = resolve_occupation(title)
        assert occ_id == expected_id, f"Failed mapping for: {title}"

    # Expected UNMAPPED
    unmapped_cases = [
        "Lathe Machine Operator",
        "Machine Learning Engineer",
        "Graphic Designer",
        "Interior Designer",
        "UI UX Designer",
        "System Administrator",
        "Building Maintenance Technician",
        "Computer Science Intern",
        "Generic Operator",
        "Generic Technician",
    ]
    for title in unmapped_cases:
        occ_id, _, _, _ = resolve_occupation(title)
        assert occ_id is None, f"Incorrectly mapped title: {title} to {occ_id}"

    # Verify determinism and no seed dependency
    res1 = resolve_occupation("Cosmetologist")
    res2 = resolve_occupation("Cosmetologist")
    assert res1 == res2
