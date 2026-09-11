from datetime import date, datetime
from typing import Optional, Any
from pydantic import BaseModel, Field, field_validator
from core.provenance.identity import (
    generate_job_identity_hash,
    generate_apprenticeship_identity_hash
)

VALID_STATUSES = {"ACTIVE", "INACTIVE", "CLOSED", "EXPIRED", "PENDING"}


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


class RawJobPostingInput(BaseModel):
    source_id: str
    source_record_id: Optional[str] = None
    job_title: str
    employer_name: Optional[str] = None
    location_text: Optional[str] = None
    district: Optional[str] = None
    state: Optional[str] = None
    sector: Optional[str] = None
    description: Optional[str] = None
    posted_date: Optional[date] = None
    retrieved_at: datetime
    source_url: Optional[str] = None
    status: str = "ACTIVE"

    @field_validator("source_id", "job_title", "status")
    @classmethod
    def check_required(cls, v: str) -> str:
        return validate_required_non_blank_string(v)

    @field_validator(
        "source_record_id",
        "employer_name",
        "location_text",
        "district",
        "state",
        "sector",
        "description",
        "source_url",
        mode="before"
    )
    @classmethod
    def check_optional(cls, v: Optional[str]) -> Optional[str]:
        return validate_non_blank_string(v)

    @field_validator("status")
    @classmethod
    def check_status(cls, v: str) -> str:
        cleaned = v.strip().upper()
        if cleaned not in VALID_STATUSES:
            raise ValueError(f"Invalid status '{v}'. Must be one of {VALID_STATUSES}")
        return cleaned


class NormalizedJobPostingObservation(BaseModel):
    source_id: str
    source_record_id: Optional[str] = None
    job_title: str
    employer_name: Optional[str] = None
    location_text: Optional[str] = None
    district: Optional[str] = None
    state: Optional[str] = None
    sector: Optional[str] = None
    description: Optional[str] = None
    posted_date: Optional[date] = None
    retrieved_at: datetime
    source_url: Optional[str] = None
    status: str
    record_identity_hash: str

    @classmethod
    def from_raw(cls, raw: RawJobPostingInput) -> "NormalizedJobPostingObservation":
        identity_hash = generate_job_identity_hash(
            source_id=raw.source_id,
            source_record_id=raw.source_record_id,
            job_title=raw.job_title,
            employer_name=raw.employer_name,
            location_text=raw.location_text,
            posted_date=raw.posted_date
        )
        return cls(
            source_id=raw.source_id,
            source_record_id=raw.source_record_id,
            job_title=raw.job_title,
            employer_name=raw.employer_name,
            location_text=raw.location_text,
            district=raw.district,
            state=raw.state,
            sector=raw.sector,
            description=raw.description,
            posted_date=raw.posted_date,
            retrieved_at=raw.retrieved_at,
            source_url=raw.source_url,
            status=raw.status,
            record_identity_hash=identity_hash
        )


class RawApprenticeshipInput(BaseModel):
    source_id: str
    source_record_id: Optional[str] = None
    trade_title: str
    organization_name: Optional[str] = None
    location_text: Optional[str] = None
    district: Optional[str] = None
    state: Optional[str] = None
    sector: Optional[str] = None
    seats_available: Optional[int] = None
    application_start_date: Optional[date] = None
    application_end_date: Optional[date] = None
    posted_date: Optional[date] = None
    retrieved_at: datetime
    source_url: Optional[str] = None
    status: str = "ACTIVE"

    @field_validator("source_id", "trade_title", "status")
    @classmethod
    def check_required(cls, v: str) -> str:
        return validate_required_non_blank_string(v)

    @field_validator(
        "source_record_id",
        "organization_name",
        "location_text",
        "district",
        "state",
        "sector",
        "source_url",
        mode="before"
    )
    @classmethod
    def check_optional(cls, v: Optional[str]) -> Optional[str]:
        return validate_non_blank_string(v)

    @field_validator("seats_available")
    @classmethod
    def check_seats(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v < 0:
            raise ValueError("seats_available must be >= 0")
        return v

    @field_validator("status")
    @classmethod
    def check_status(cls, v: str) -> str:
        cleaned = v.strip().upper()
        if cleaned not in VALID_STATUSES:
            raise ValueError(f"Invalid status '{v}'. Must be one of {VALID_STATUSES}")
        return cleaned


class NormalizedApprenticeshipObservation(BaseModel):
    source_id: str
    source_record_id: Optional[str] = None
    trade_title: str
    organization_name: Optional[str] = None
    location_text: Optional[str] = None
    district: Optional[str] = None
    state: Optional[str] = None
    sector: Optional[str] = None
    seats_available: Optional[int] = None
    application_start_date: Optional[date] = None
    application_end_date: Optional[date] = None
    posted_date: Optional[date] = None
    retrieved_at: datetime
    source_url: Optional[str] = None
    status: str
    record_identity_hash: str

    @classmethod
    def from_raw(cls, raw: RawApprenticeshipInput) -> "NormalizedApprenticeshipObservation":
        identity_hash = generate_apprenticeship_identity_hash(
            source_id=raw.source_id,
            source_record_id=raw.source_record_id,
            trade_title=raw.trade_title,
            organization_name=raw.organization_name,
            location_text=raw.location_text,
            application_start_date=raw.application_start_date,
            application_end_date=raw.application_end_date
        )
        return cls(
            source_id=raw.source_id,
            source_record_id=raw.source_record_id,
            trade_title=raw.trade_title,
            organization_name=raw.organization_name,
            location_text=raw.location_text,
            district=raw.district,
            state=raw.state,
            sector=raw.sector,
            seats_available=raw.seats_available,
            application_start_date=raw.application_start_date,
            application_end_date=raw.application_end_date,
            posted_date=raw.posted_date,
            retrieved_at=raw.retrieved_at,
            source_url=raw.source_url,
            status=raw.status,
            record_identity_hash=identity_hash
        )
