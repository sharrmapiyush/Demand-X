"""
Data validation and transformation utilities for job ingestion.

Provides validation rules and transformation functions for the staging layer.
"""
from typing import Optional
import re


VALID_SECTORS = {"IT-ITeS", "Automotive/Manufacturing", "Electronics"}
VALID_DISTRICTS = {"Pune", "Mumbai", "Nashik", "Nagpur", "Aurangabad", "Thane", "Kolhapur", "Solapur", "Ahmednagar"}
VALID_STATES = {"Maharashtra", "Maharashtra "}


def validate_job_record(
    job_title: Optional[str] = None,
    employer_name: Optional[str] = None,
    district: Optional[str] = None,
    sector: Optional[str] = None,
    state: Optional[str] = None,
) -> tuple[bool, list[str]]:
    """
    Validate required fields for a job record.

    Returns:
        (is_valid, list of error messages)
    """
    errors = []

    if not job_title or not job_title.strip():
        errors.append("job_title is required")

    if not employer_name or not employer_name.strip():
        errors.append("employer_name is required")

    if not district or not district.strip():
        errors.append("district is required")
    elif district.strip() not in VALID_DISTRICTS:
        # Allow through but log warning - we might expand districts later
        pass

    if not sector or not sector.strip():
        errors.append("sector is required")
    elif sector.strip() not in VALID_SECTORS:
        errors.append(f"Invalid sector '{sector}'. Must be one of: {', '.join(VALID_SECTORS)}")

    if not state or not state.strip():
        errors.append("state is required")

    return len(errors) == 0, errors


def validate_and_clean_record(raw_record: dict) -> tuple[dict, bool, list[str]]:
    """
    Validate and clean a raw job record.

    Returns:
        (cleaned_record, is_valid, validation_errors)
    """
    cleaned = {}
    errors = []

    # Extract and clean fields
    cleaned["job_title"] = raw_record.get("job_title", "").strip() if raw_record.get("job_title") else ""
    cleaned["employer_name"] = raw_record.get("employer_name", "").strip() if raw_record.get("employer_name") else ""
    cleaned["description"] = raw_record.get("description", "").strip() if raw_record.get("description") else None
    cleaned["location"] = raw_record.get("location", "").strip() if raw_record.get("location") else None
    cleaned["salary"] = raw_record.get("salary", "").strip() if raw_record.get("salary") else None
    cleaned["experience_years"] = raw_record.get("experience_years", "").strip() if raw_record.get("experience_years") else None
    cleaned["min_education"] = raw_record.get("min_education", "").strip() if raw_record.get("min_education") else None

    # Sector - normalize
    raw_sector = raw_record.get("sector", "").strip() if raw_record.get("sector") else ""
    if raw_sector == "IT" or raw_sector == "ITeS" or raw_sector == "IT / ITeS":
        cleaned["sector"] = "IT-ITeS"
    elif raw_sector == "Automotive" or raw_sector == "Manufacturing":
        cleaned["sector"] = "Automotive/Manufacturing"
    elif raw_sector == "Electronics":
        cleaned["sector"] = "Electronics"
    else:
        cleaned["sector"] = raw_sector

    # District - normalize
    raw_district = raw_record.get("district", "").strip() if raw_record.get("district") else ""
    cleaned["district"] = raw_district

    # State - normalize
    raw_state = raw_record.get("state", "").strip() if raw_record.get("state") else ""
    cleaned["state"] = raw_state

    # Posted date
    cleaned["posted_date"] = raw_record.get("posted_date", "").strip() if raw_record.get("posted_date") else None

    # Source record ID - required
    cleaned["source_record_id"] = raw_record.get("source_record_id", "").strip() if raw_record.get("source_record_id") else ""

    # Validate
    is_valid, validation_errors = validate_job_record(
        job_title=cleaned.get("job_title"),
        employer_name=cleaned.get("employer_name"),
        district=cleaned.get("district"),
        sector=cleaned.get("sector"),
        state=cleaned.get("state"),
    )

    return cleaned, is_valid, validation_errors


def get_required_fields() -> list[str]:
    """Return list of required field names for job records."""
    return [
        "job_title",
        "employer_name",
        "state",
        "district",
        "sector",
    ]


def get_optional_fields() -> list[str]:
    """Return list of optional field names for job records."""
    return [
        "description",
        "location_detail",
        "experience_years_min",
        "experience_years_max",
        "min_education",
        "salary_min",
        "salary_max",
        "salary_currency",
        "posted_date",
    ]