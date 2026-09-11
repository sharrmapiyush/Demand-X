import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError
from core.models.base import Base
from core.models.source import Source
from core.models.dvet import DVETInstitute, DVETTrade


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Create test source
    source = Source(
        source_id="test-dvet-source",
        source_name="Test DVET Source",
        organization="DVET Test Org",
        url="https://example.com/dvet",
        category="supply",
        access_method="PUBLIC_PAGE",
        freshness_class="PERIODIC",
        enabled=True
    )
    session.add(source)
    session.commit()

    yield session
    session.close()


def test_insert_retrieve_dvet_institute(db_session):
    inst = DVETInstitute(
        institute_id="inst_test_001",
        institute_code="TEST999",
        ncvt_mis_code="GU999999",
        institute_name="Test Industrial Training Institute",
        institute_category="General",
        district="Pune",
        state="Maharashtra",
        address="Test Address, Pune",
        source_id="test-dvet-source",
        record_identity_hash="hash_inst_001"
    )
    db_session.add(inst)
    db_session.commit()

    retrieved = db_session.query(DVETInstitute).filter_by(institute_id="inst_test_001").first()
    assert retrieved is not None
    assert retrieved.institute_name == "Test Industrial Training Institute"
    assert retrieved.district == "Pune"
    assert retrieved.source_id == "test-dvet-source"


def test_insert_retrieve_dvet_trade_with_institute_relationship(db_session):
    inst = DVETInstitute(
        institute_id="inst_test_002",
        institute_code="TEST888",
        institute_name="Test ITI 2",
        district="Pune",
        state="Maharashtra",
        source_id="test-dvet-source",
        record_identity_hash="hash_inst_002"
    )
    db_session.add(inst)
    db_session.commit()

    trade1 = DVETTrade(
        trade_id="trade_test_001",
        institute_code="TEST888",
        institute_name="Test ITI 2",
        trade_name="Electrician",
        unit_category="Govt ITI – General",
        intake="20",
        district="Pune",
        state="Maharashtra",
        source_id="test-dvet-source",
        institute_id="inst_test_002",
        trade_identity_hash="hash_trade_001"
    )
    db_session.add(trade1)
    db_session.commit()

    retrieved_trade = db_session.query(DVETTrade).filter_by(trade_id="trade_test_001").first()
    assert retrieved_trade is not None
    assert retrieved_trade.trade_name == "Electrician"
    assert retrieved_trade.institute is not None
    assert retrieved_trade.institute.institute_name == "Test ITI 2"
    assert len(retrieved_trade.institute.trades) == 1


def test_duplicate_institute_identity_rejected(db_session):
    inst1 = DVETInstitute(
        institute_id="inst_dup_1",
        institute_code="TEST111",
        institute_name="ITI 1",
        district="Pune",
        state="Maharashtra",
        source_id="test-dvet-source",
        record_identity_hash="hash_same_inst"
    )
    db_session.add(inst1)
    db_session.commit()

    inst2 = DVETInstitute(
        institute_id="inst_dup_2",
        institute_code="TEST222",
        institute_name="ITI 2",
        district="Pune",
        state="Maharashtra",
        source_id="test-dvet-source",
        record_identity_hash="hash_same_inst"  # duplicate hash
    )
    db_session.add(inst2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_duplicate_trade_identity_rejected(db_session):
    trade1 = DVETTrade(
        trade_id="trade_dup_1",
        institute_code="TEST333",
        trade_name="Welder",
        district="Pune",
        state="Maharashtra",
        source_id="test-dvet-source",
        trade_identity_hash="hash_same_trade"
    )
    db_session.add(trade1)
    db_session.commit()

    trade2 = DVETTrade(
        trade_id="trade_dup_2",
        institute_code="TEST333",
        trade_name="Welder",
        district="Pune",
        state="Maharashtra",
        source_id="test-dvet-source",
        trade_identity_hash="hash_same_trade"  # duplicate hash
    )
    db_session.add(trade2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_duplicate_trade_names_coexist_with_different_hashes(db_session):
    # Two trades with identical name "Machinist" but different unit/intake/index hashes
    trade1 = DVETTrade(
        trade_id="trade_mach_1",
        institute_code="TEST444",
        trade_name="Machinist",
        unit_category="General",
        intake="16",
        district="Pune",
        state="Maharashtra",
        source_id="test-dvet-source",
        trade_identity_hash="hash_mach_1"
    )
    trade2 = DVETTrade(
        trade_id="trade_mach_2",
        institute_code="TEST444",
        trade_name="Machinist",
        unit_category="General",
        intake="16",
        district="Pune",
        state="Maharashtra",
        source_id="test-dvet-source",
        trade_identity_hash="hash_mach_2"
    )
    db_session.add_all([trade1, trade2])
    db_session.commit()

    machinists = db_session.query(DVETTrade).filter_by(trade_name="Machinist").all()
    assert len(machinists) == 2


def test_district_filtering(db_session):
    inst_pune = DVETInstitute(
        institute_id="inst_pune",
        institute_code="PUNE01",
        institute_name="Pune ITI",
        district="Pune",
        state="Maharashtra",
        source_id="test-dvet-source",
        record_identity_hash="hash_inst_pune"
    )
    inst_mumbai = DVETInstitute(
        institute_id="inst_mumbai",
        institute_code="MUM01",
        institute_name="Mumbai ITI",
        district="Mumbai",
        state="Maharashtra",
        source_id="test-dvet-source",
        record_identity_hash="hash_inst_mumbai"
    )
    db_session.add_all([inst_pune, inst_mumbai])
    db_session.commit()

    pune_insts = db_session.query(DVETInstitute).filter_by(district="Pune").all()
    assert len(pune_insts) == 1
    assert pune_insts[0].institute_name == "Pune ITI"
