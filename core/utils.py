import json
import hashlib
from typing import Optional, Dict, Any, List
from datetime import datetime
from decimal import Decimal, InvalidOperation
import re


def compute_deterministic_hash(data: str) -> str:
    """
    Compute a SHA-256 hash of the input string.
    Used for creating deterministic identity hashes for deduplication.
    """
    return hashlib.sha256(data.encode('utf-8')).hexdigest()


def generate_job_identity_hash(
    title: str,
    employer: str,
    district: str,
    sector: str,
    posted_date: Optional[str] = None
) -> str:
    """
    Generate a deterministic identity hash for a job based on core fields.
    This is used for deduplication across sources.
    """
    components = [
        title.strip().lower(),
        employer.strip().lower(),
        district.strip().lower(),
        sector.strip().lower()
    ]
    if posted_date:
        components.append(posted_date.strip())

    normalized_string = "|".join(components)
    return compute_deterministic_hash(normalized_string)


def clean_salary(salary_str: Optional[str]) -> tuple[Optional[Decimal], Optional[Decimal], Optional[str]]:
    """
    Parse salary string into min and max numeric values.

    Expected formats:
    - "₹6,00,000 - ₹9,00,000 PA"
    - "₹10,00,000 PA"
    - "₹5,00,000"

    Returns: (min_salary, max_salary, currency)
    """
    if not salary_str:
        return None, None, None

    currency = "INR"
    # Remove currency symbols, commas, and "PA" / "per annum" / " annum"
    cleaned = salary_str.replace("₹", "").replace(",", "").replace("PA", "").replace("per annum", "").replace(" annum", "").strip()

    # Extract numbers
    numbers = re.findall(r'\d+(?:\.\d+)?', cleaned)
    if not numbers:
        return None, None, currency

    # Convert to Decimal
    values = []
    for n in numbers:
        try:
            values.append(Decimal(n))
        except InvalidOperation:
            continue

    if not values:
        return None, None, currency

    if len(values) == 1:
        return values[0], values[0], currency
    elif len(values) >= 2:
        min_val = min(values)
        max_val = max(values)
        return min_val, max_val, currency

    return None, None, currency


def clean_experience(experience_str: Optional[str]) -> tuple[Optional[int], Optional[int]]:
    """
    Parse experience string into min and max years.

    Expected formats:
    - "2-4 years"
    - "3 years"
    - "5+ years"
    """
    if not experience_str:
        return None, None

    # Remove "years", "year", "yrs", "yr"
    cleaned = experience_str.lower().replace("years", "").replace("year", "").replace("yrs", "").replace("yr", "").strip()

    # Check for "X+ years" format
    plus_match = re.match(r'(\d+)\+\s*', cleaned)
    if plus_match:
        min_exp = int(plus_match.group(1))
        return min_exp, None

    # Check for "X-Y" format
    range_match = re.match(r'(\d+)\s*[-–]\s*(\d+)', cleaned)
    if range_match:
        return int(range_match.group(1)), int(range_match.group(2))

    # Single number
    try:
        val = int(cleaned.strip())
        return val, val
    except ValueError:
        return None, None


def normalize_text(text: Optional[str]) -> Optional[str]:
    """Normalize text by stripping whitespace and converting to title case."""
    if not text:
        return None
    return text.strip()


def generate_staging_id(source_record_id: str, attempt: int = 1) -> str:
    """Generate a unique staging ID."""
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    return f"STAGE-{source_record_id}-{timestamp}-{attempt:03d}"


def generate_job_id(source_id: str, source_record_id: str) -> str:
    """Generate a unique job ID based on source and source record."""
    hash_input = f"{source_id}:{source_record_id}"
    hash_digest = compute_deterministic_hash(hash_input)[:16]
    return f"JOB-{hash_digest.upper()}"


def parse_date(date_str: Optional[str]) -> Optional[datetime]:
    """Parse date string into datetime object."""
    if not date_str:
        return None

    formats = [
        "%Y-%m-%d",
        "%d-%m-%Y",
        "%d/%m/%Y",
        "%Y/%m/%d",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(date_str.strip(), fmt)
        except ValueError:
            continue

    return None