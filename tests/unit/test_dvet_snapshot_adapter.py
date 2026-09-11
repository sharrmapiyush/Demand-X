import pytest
from pydantic import ValidationError
from ingestion.adapters.dvet_snapshot import (
    RawDVETSnapshotInput,
    RawDVETInstituteInput,
    RawDVETTradeInput,
    load_dvet_snapshot_file,
    parse_dvet_snapshot
)


def test_load_and_parse_verified_dvet_snapshot():
    snapshot_path = "data/raw/dvet_pune/dvet_pune_haveli_verified_snapshot.json"
    raw_snapshot = load_dvet_snapshot_file(snapshot_path)
    assert raw_snapshot.source_id == "dvet-pune-haveli-verified-snapshot"
    assert raw_snapshot.total_institutes == 1
    assert len(raw_snapshot.institutes) == 1

    inst = raw_snapshot.institutes[0]
    assert inst.institute_code == "2765211006"
    assert inst.ncvt_mis_code == "GU27000616"
    assert inst.district == "Pune"
    assert len(inst.trades) == 10

    normalized = parse_dvet_snapshot(raw_snapshot)
    assert len(normalized) == 1
    norm_inst = normalized[0]
    assert norm_inst.institute_code == "2765211006"
    assert len(norm_inst.record_identity_hash) == 64
    assert len(norm_inst.trades) == 10
    for trade in norm_inst.trades:
        assert len(trade.trade_identity_hash) == 64
        assert trade.district == "Pune"


def test_dvet_snapshot_validation_blank_fields():
    with pytest.raises(ValidationError):
        RawDVETInstituteInput(
            institute_name="   ",
            institute_code="123",
            district="Pune"
        )


def test_dvet_snapshot_validation_invalid_district():
    with pytest.raises(ValidationError):
        RawDVETInstituteInput(
            institute_name="ITI Mumbai",
            institute_code="123",
            district="Mumbai"
        )


def test_dvet_trade_validation_blank_name():
    with pytest.raises(ValidationError):
        RawDVETTradeInput(
            trade_name=""
        )
