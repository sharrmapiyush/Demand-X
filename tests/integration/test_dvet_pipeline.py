import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from core.models.base import Base
from core.models.source import Source
from core.models.dvet import DVETInstitute, DVETTrade
from ingestion.pipelines.dvet_pipeline import ingest_dvet_snapshot, register_dvet_source


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def test_register_dvet_source(db_session):
    source = register_dvet_source(db_session)
    assert source.source_id == "dvet-pune-haveli-verified-snapshot"
    assert source.access_method == "PUBLIC_PAGE"
    assert source.freshness_class == "PERIODIC"
    assert source.category == "supply"


def test_dvet_ingestion_pipeline(db_session):
    result = ingest_dvet_snapshot(db_session, "data/raw/dvet_pune/dvet_pune_haveli_verified_snapshot.json")
    assert result["status"] == "success"
    assert result["institutes_processed"] == 1
    assert result["trades_processed"] == 10
    assert result["errors"] == 0

    # Verify institutes in db
    institutes = db_session.query(DVETInstitute).all()
    assert len(institutes) == 1
    assert institutes[0].institute_name == "Industrial Training Institute, Haveli"
    assert institutes[0].institute_code == "2765211006"
    assert institutes[0].ncvt_mis_code == "GU27000616"

    for inst in institutes:
        assert inst.district == "Pune"
        assert inst.state == "Maharashtra"
        assert inst.source_id == "dvet-pune-haveli-verified-snapshot"
        assert inst.record_identity_hash is not None
        assert inst.raw_json is not None

    # Verify trades in db
    trades = db_session.query(DVETTrade).all()
    assert len(trades) == 10

    for trade in trades:
        assert trade.district == "Pune"
        assert trade.state == "Maharashtra"
        assert trade.source_id == "dvet-pune-haveli-verified-snapshot"
        assert trade.trade_identity_hash is not None
        assert trade.trade_name is not None
        assert trade.institute_code == "2765211006"


def test_dvet_duplicate_handling_and_determinism(db_session):
    result1 = ingest_dvet_snapshot(db_session, "data/raw/dvet_pune/dvet_pune_haveli_verified_snapshot.json")
    result2 = ingest_dvet_snapshot(db_session, "data/raw/dvet_pune/dvet_pune_haveli_verified_snapshot.json")

    assert result2["institutes_processed"] == 0
    assert result2["trades_processed"] == 0

    institutes = db_session.query(DVETInstitute).all()
    assert len(institutes) == 1
    trades = db_session.query(DVETTrade).all()
    assert len(trades) == 10
