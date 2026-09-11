from datetime import date, datetime
from typing import Optional, List, Any
import json
import hashlib
from pydantic import BaseModel, Field, field_validator


def validate_non_blank_string(v: Optional[str]) -> Optional[str]:
    if v is None:
        return None
    if not isinstance(v, str):
        raise ValueError("Must be a string")
    cleaned = v.strip()
    if not cleaned:
        raise ValueError("Field cannot be blank or whitespace-only")
    return cleaned


def validate_required_non_blank_string(v: str) -> str:
    res = validate_non_blank_string(v)
    if res is None:
        raise ValueError("Field is required and cannot be None")
    return res


class RawDVETTradeInput(BaseModel):
    trade_name: str
    unit_category: Optional[str] = None
    intake: Optional[str] = None

    @field_validator("trade_name")
    @classmethod
    def check_trade_name(cls, v: str) -> str:
        return validate_required_non_blank_string(v)

    @field_validator("unit_category", "intake", mode="before")
    @classmethod
    def check_optional(cls, v: Optional[str]) -> Optional[str]:
        return validate_non_blank_string(v)


class RawDVETInstituteInput(BaseModel):
    institute_name: str
    institute_code: str
    ncvt_mis_code: Optional[str] = None
    institute_category: Optional[str] = None
    address: Optional[str] = None
    establishment_year: Optional[str] = None
    establishment_gr: Optional[str] = None
    hostel_capacity: Optional[str] = None
    financial_scheme_for_iti: Optional[str] = None
    district: str = "Pune"
    state: str = "Maharashtra"
    source_url: Optional[str] = None
    trades: List[RawDVETTradeInput] = Field(default_factory=list)

    @field_validator("institute_name", "institute_code", "district", "state")
    @classmethod
    def check_required(cls, v: str) -> str:
        return validate_required_non_blank_string(v)

    @field_validator(
        "ncvt_mis_code",
        "institute_category",
        "address",
        "establishment_year",
        "establishment_gr",
        "hostel_capacity",
        "financial_scheme_for_iti",
        "source_url",
        mode="before"
    )
    @classmethod
    def check_optional(cls, v: Optional[str]) -> Optional[str]:
        return validate_non_blank_string(v)

    @field_validator("district")
    @classmethod
    def check_district(cls, v: str) -> str:
        cleaned = validate_required_non_blank_string(v)
        if cleaned != "Pune":
            raise ValueError(f"District must be 'Pune' for verified pilot snapshot, got '{cleaned}'")
        return cleaned


class RawDVETSnapshotInput(BaseModel):
    source_id: str
    source_name: str
    publisher: str
    url: str
    access_method: str
    freshness_class: str
    retrieval_date: str
    coverage: str
    verification_status: str
    total_institutes: int
    institutes: List[RawDVETInstituteInput] = Field(default_factory=list)

    @field_validator("source_id", "source_name", "publisher", "url", "access_method", "freshness_class", "retrieval_date", "coverage", "verification_status")
    @classmethod
    def check_required(cls, v: str) -> str:
        return validate_required_non_blank_string(v)


class NormalizedDVETTradeObservation(BaseModel):
    institute_code: str
    institute_name: str
    trade_name: str
    unit_category: Optional[str] = None
    intake: Optional[str] = None
    district: str
    state: str
    source_id: str
    trade_identity_hash: str


class NormalizedDVETInstituteObservation(BaseModel):
    institute_code: str
    ncvt_mis_code: Optional[str] = None
    institute_name: str
    institute_category: Optional[str] = None
    district: str
    state: str
    address: Optional[str] = None
    establishment_year: Optional[str] = None
    establishment_gr: Optional[str] = None
    hostel_capacity: Optional[str] = None
    source_id: str
    record_identity_hash: str
    trades: List[NormalizedDVETTradeObservation] = Field(default_factory=list)


def load_dvet_snapshot_file(file_path: str) -> RawDVETSnapshotInput:
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return RawDVETSnapshotInput(**data)


def parse_dvet_snapshot(raw: RawDVETSnapshotInput) -> List[NormalizedDVETInstituteObservation]:
    normalized_institutes = []
    for inst in raw.institutes:
        inst_identity_string = f"{inst.institute_code}:{inst.institute_name}:{inst.district}"
        inst_hash = hashlib.sha256(inst_identity_string.encode("utf-8")).hexdigest()

        norm_trades = []
        for idx, trade in enumerate(inst.trades):
            trade_identity_string = f"{inst.institute_code}:{trade.trade_name}:{trade.unit_category}:{trade.intake}:{idx}"
            trade_hash = hashlib.sha256(trade_identity_string.encode("utf-8")).hexdigest()
            norm_trades.append(
                NormalizedDVETTradeObservation(
                    institute_code=inst.institute_code,
                    institute_name=inst.institute_name,
                    trade_name=trade.trade_name,
                    unit_category=trade.unit_category,
                    intake=trade.intake,
                    district=inst.district,
                    state=inst.state,
                    source_id=raw.source_id,
                    trade_identity_hash=trade_hash
                )
            )

        normalized_institutes.append(
            NormalizedDVETInstituteObservation(
                institute_code=inst.institute_code,
                ncvt_mis_code=inst.ncvt_mis_code,
                institute_name=inst.institute_name,
                institute_category=inst.institute_category,
                district=inst.district,
                state=inst.state,
                address=inst.address,
                establishment_year=inst.establishment_year,
                establishment_gr=inst.establishment_gr,
                hostel_capacity=inst.hostel_capacity,
                source_id=raw.source_id,
                record_identity_hash=inst_hash,
                trades=norm_trades
            )
        )
    return normalized_institutes
