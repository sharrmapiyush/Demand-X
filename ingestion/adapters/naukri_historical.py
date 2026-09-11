import os
import csv
import logging
from datetime import datetime, date
from typing import Dict, Any, List, Tuple, Optional

from core.geography.location_normalizer import normalize_location
from ingestion.contracts.observations import (
    RawJobPostingInput,
    NormalizedJobPostingObservation
)

logger = logging.getLogger(__name__)

SOURCE_ID = "naukri-historical-promptcloud"
SOURCE_TYPE = "SUPPLEMENTARY_HISTORICAL"
FRESHNESS_CLASS = "HISTORICAL"
VERIFICATION_STATUS = "UNVERIFIED_EXTERNAL_DATASET"

def parse_date(date_str: Any) -> Tuple[Optional[date], bool]:
    """
    Parses a date string from Naukri format (e.g. '2016-05-21 19:30:00 +0000').
    Returns (parsed_date, is_malformed).
    """
    if not date_str or not str(date_str).strip():
        return None, False

    val_str = str(date_str).strip()
    # Try parsing common formats
    formats = [
        "%Y-%m-%d %H:%M:%S %z",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d"
    ]

    for fmt in formats:
        try:
            dt = datetime.strptime(val_str, fmt)
            return dt.date(), False
        except ValueError:
            continue

    # If it failed all known formats, it's malformed
    return None, True

def parse_seats(seats_str: Any) -> Tuple[Optional[int], bool]:
    """
    Parses numberofpositions. Returns (parsed_int, is_malformed).
    """
    if seats_str is None or str(seats_str).strip() == "":
        return None, False

    val_str = str(seats_str).strip()
    try:
        # Sometimes seats might contain float or string representation of numbers
        val_float = float(val_str)
        if val_float < 0:
            return None, True
        return int(val_float), False
    except (ValueError, TypeError):
        return None, True

def normalize_naukri_row(row: Dict[str, Any], retrieved_at: datetime) -> Tuple[Optional[NormalizedJobPostingObservation], List[str], Dict[str, bool]]:
    """
    Normalizes a single Naukri row into a NormalizedJobPostingObservation.
    Returns (observation, rejection_reasons, flags).
    """
    rejection_reasons = []
    flags = {
        "missing_title": False,
        "missing_company": False,
        "missing_location": False,
        "malformed_date": False,
        "malformed_seats": False
    }

    # Extract raw fields
    job_title = row.get("jobtitle")
    company = row.get("company")
    location_addr = row.get("joblocation_address")
    industry = row.get("industry")
    description = row.get("jobdescription")
    postdate_raw = row.get("postdate")
    jobid = row.get("jobid")
    uniq_id = row.get("uniq_id")
    num_positions = row.get("numberofpositions")

    # Validate title
    if not job_title or not str(job_title).strip():
        rejection_reasons.append("Missing job title")
        flags["missing_title"] = True

    # Validate company
    if not company or not str(company).strip():
        flags["missing_company"] = True
        # Company is optional contract-wise, but let's note it

    # Validate location
    if not location_addr or not str(location_addr).strip():
        flags["missing_location"] = True

    # Parse date
    posted_date, malformed_date = parse_date(postdate_raw)
    if malformed_date:
        rejection_reasons.append(f"Malformed postdate: {postdate_raw}")
        flags["malformed_date"] = True

    # Parse seats (numberofpositions)
    seats, malformed_seats = parse_seats(num_positions)
    if malformed_seats:
        rejection_reasons.append(f"Malformed numberofpositions: {num_positions}")
        flags["malformed_seats"] = True

    if rejection_reasons:
        return None, rejection_reasons, flags

    # Normalize location via geography normalizer
    loc_text = str(location_addr).strip() if location_addr and str(location_addr).strip() else None
    geo_res = normalize_location(loc_text)

    # Prepare source record ID: prefer jobid if present, else uniq_id
    source_record_id = None
    if jobid and str(jobid).strip():
        source_record_id = str(jobid).strip()
    elif uniq_id and str(uniq_id).strip():
        source_record_id = str(uniq_id).strip()

    # Construct RawJobPostingInput
    # Note: RawJobPostingInput does not take sector or description in some versions,
    # let's check contracts/observations.py. RawJobPostingInput has:
    # source_id, source_record_id, job_title, employer_name, location_text, district, state, sector, description, posted_date, retrieved_at, source_url, status
    try:
        raw_input = RawJobPostingInput(
            source_id=SOURCE_ID,
            source_record_id=source_record_id,
            job_title=str(job_title).strip(),
            employer_name=str(company).strip() if company and str(company).strip() else None,
            location_text=loc_text,
            district=geo_res.district,
            state=geo_res.state,
            sector=str(industry).strip() if industry and str(industry).strip() else None,
            description=str(description).strip() if description and str(description).strip() else None,
            posted_date=posted_date,
            retrieved_at=retrieved_at,
            source_url=None,
            status="ACTIVE"  # neutral status per contract rule
        )

        observation = NormalizedJobPostingObservation.from_raw(raw_input)
        return observation, [], flags
    except Exception as e:
        rejection_reasons.append(f"Validation error: {str(e)}")
        return None, rejection_reasons, flags

def load_naukri_historical(csv_path: str) -> List[Dict[str, Any]]:
    """
    Loads raw CSV rows from the Naukri historical dataset.
    """
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Naukri historical dataset not found at {csv_path}")

    rows = []
    with open(csv_path, mode="r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows

def adapt_naukri_dataset(csv_path: Optional[str] = None) -> Tuple[List[NormalizedJobPostingObservation], Dict[str, Any]]:
    """
    Adapts the entire Naukri historical dataset into canonical observations.
    Returns (observations, profile_metrics).
    """
    if csv_path is None:
        csv_path = "data/raw/naukri_historical/naukri_com-job_sample.csv"

    retrieved_at = datetime.utcnow()
    raw_rows = load_naukri_historical(csv_path)

    total_input_rows = len(raw_rows)
    normalized_observations = []
    rejected_rows = 0
    rejection_reasons_counter = {}

    duplicate_identity_count = 0
    missing_title_count = 0
    missing_company_count = 0
    missing_location_count = 0
    malformed_date_count = 0
    malformed_seat_count = 0

    pune_exclusive_count = 0
    pune_shared_count = 0
    pune_mentioned_count = 0
    pune_total_evidence_count = 0

    seen_identities = set()

    for row in raw_rows:
        obs, reasons, flags = normalize_naukri_row(row, retrieved_at)

        if flags["missing_title"]:
            missing_title_count += 1
        if flags["missing_company"]:
            missing_company_count += 1
        if flags["missing_location"]:
            missing_location_count += 1
        if flags["malformed_date"]:
            malformed_date_count += 1
        if flags["malformed_seats"]:
            malformed_seat_count += 1

        if obs is None:
            rejected_rows += 1
            for r in reasons:
                rejection_reasons_counter[r] = rejection_reasons_counter.get(r, 0) + 1
            continue

        # Check duplicate identity hash
        if obs.record_identity_hash in seen_identities:
            duplicate_identity_count += 1
        else:
            seen_identities.add(obs.record_identity_hash)

        # Check Pune evidence via location normalizer on location_text
        geo_res = normalize_location(obs.location_text)
        if geo_res.has_pune_evidence:
            pune_total_evidence_count += 1
            if geo_res.pune_exclusivity == "EXCLUSIVE":
                pune_exclusive_count += 1
            elif geo_res.pune_exclusivity == "SHARED":
                pune_shared_count += 1
            elif geo_res.pune_exclusivity == "MENTIONED":
                pune_mentioned_count += 1

        normalized_observations.append(obs)

    profile_data = {
        "input_rows": total_input_rows,
        "normalized_rows": len(normalized_observations),
        "rejected_rows": rejected_rows,
        "rejection_reasons": rejection_reasons_counter,
        "duplicate_identity_count": duplicate_identity_count,
        "missing_title_count": missing_title_count,
        "missing_company_count": missing_company_count,
        "missing_location_count": missing_location_count,
        "malformed_date_count": malformed_date_count,
        "malformed_seat_count": malformed_seat_count,
        "pune_exclusive_count": pune_exclusive_count,
        "pune_shared_count": pune_shared_count,
        "pune_mentioned_count": pune_mentioned_count,
        "pune_total_evidence_count": pune_total_evidence_count
    }

    return normalized_observations, profile_data
