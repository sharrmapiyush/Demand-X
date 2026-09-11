import hashlib
from typing import Optional, Any


def normalize_field(val: Any) -> str:
    if val is None:
        return ""
    if hasattr(val, "isoformat"):
        return val.isoformat()
    return " ".join(str(val).lower().strip().split())


def generate_job_identity_hash(
    source_id: str,
    source_record_id: Optional[str] = None,
    job_title: Optional[str] = None,
    employer_name: Optional[str] = None,
    location_text: Optional[str] = None,
    posted_date: Optional[Any] = None
) -> str:
    if source_record_id and str(source_record_id).strip():
        raw_str = f"{normalize_field(source_id)}:{normalize_field(source_record_id)}"
    else:
        parts = [
            normalize_field(source_id),
            normalize_field(job_title),
            normalize_field(employer_name),
            normalize_field(location_text),
            normalize_field(posted_date)
        ]
        raw_str = "|".join(parts)

    return hashlib.sha256(raw_str.encode("utf-8")).hexdigest()


def generate_apprenticeship_identity_hash(
    source_id: str,
    source_record_id: Optional[str] = None,
    trade_title: Optional[str] = None,
    organization_name: Optional[str] = None,
    location_text: Optional[str] = None,
    application_start_date: Optional[Any] = None,
    application_end_date: Optional[Any] = None
) -> str:
    if source_record_id and str(source_record_id).strip():
        raw_str = f"{normalize_field(source_id)}:{normalize_field(source_record_id)}"
    else:
        parts = [
            normalize_field(source_id),
            normalize_field(trade_title),
            normalize_field(organization_name),
            normalize_field(location_text),
            normalize_field(application_start_date),
            normalize_field(application_end_date)
        ]
        raw_str = "|".join(parts)

    return hashlib.sha256(raw_str.encode("utf-8")).hexdigest()
