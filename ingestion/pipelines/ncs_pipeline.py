import json
import hashlib
from datetime import datetime, date
from decimal import Decimal
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from core.models.source import Source
from core.models.job import Job, JobStaging


def register_unverified_ncs_fixture_source(db: Session) -> Source:
    """Ensure NCS unverified fixture source is registered in the Source Registry with explicit warning."""
    source_id = "ncs-pune-job-snapshot-unverified"
    source = db.query(Source).filter(Source.source_id == source_id).first()
    if not source:
        source = Source(
            source_id=source_id,
            source_name="National Career Service (NCS) Pune Unverified Fixture Source",
            organization="Ministry of Labour and Employment, Government of India (Unverified)",
            url="https://www.ncs.gov.in/",
            category="Demand",
            access_method="UNVERIFIED_FIXTURE",
            freshness_class="STATIC",
            last_verified_at=None,
            last_fetched_at=datetime.utcnow(),
            coverage="Pune district (Unverified test fixture)",
            historical_depth="Test fixture (September 2026)",
            reliability_notes="UNVERIFIED_OR_SYNTHETIC. Must not be used as production or official source data.",
            legal_access_notes="Test fixture data. Live acquisition could not be verified.",
            enabled=False  # Disabled for production use
        )
        db.add(source)
        db.commit()
        db.refresh(source)
    return source


def calculate_job_hash(source_id: str, source_record_id: str, title: str, employer: str) -> str:
    """Calculate deterministic deduplication identity hash."""
    raw_str = f"{source_id}:{source_record_id}:{title.strip().lower()}:{employer.strip().lower()}"
    return hashlib.sha256(raw_str.encode("utf-8")).hexdigest()


def parse_experience(exp_str: Optional[str]) -> tuple[Optional[int], Optional[int]]:
    """Parse experience string like '2-4 years' or '3-6 years' into min/max integers."""
    if not exp_str:
        return None, None
    import re
    numbers = re.findall(r'\d+', exp_str)
    if len(numbers) >= 2:
        return int(numbers[0]), int(numbers[1])
    elif len(numbers) == 1:
        return int(numbers[0]), int(numbers[0])
    return None, None


def parse_salary(salary_str: Optional[str]) -> tuple[Optional[Decimal], Optional[Decimal]]:
    """Parse salary string like '₹6,00,000 - ₹9,00,000 PA' into min/max Decimal values."""
    if not salary_str:
        return None, None
    import re
    cleaned = salary_str.replace(',', '').replace('₹', '').replace('Rs.', '')
    numbers = re.findall(r'\d+(?:\.\d+)?', cleaned)
    if len(numbers) >= 2:
        try:
            return Decimal(numbers[0]), Decimal(numbers[1])
        except Exception:
            return None, None
    elif len(numbers) == 1:
        try:
            val = Decimal(numbers[0])
            return val, val
        except Exception:
            return None, None
    return None, None


def ingest_snapshot(db: Session, snapshot_path: str = "data/fixtures/ncs_pune_jobs_unverified_fixture.json") -> Dict[str, Any]:
    """Execute end-to-end ingestion pipeline for test fixture with explicit unverified marking."""
    # 1. Register unverified fixture source
    source = register_unverified_ncs_fixture_source(db)

    # 2. Load fixture file
    with open(snapshot_path, "r", encoding="utf-8") as f:
        snapshot_data = json.load(f)

    # Enforce classification check
    if snapshot_data.get("classification") != "UNVERIFIED_OR_SYNTHETIC":
        raise ValueError("Production ingestion error: Attempted to ingest data not classified as UNVERIFIED_OR_SYNTHETIC through the unverified pipeline.")

    records = snapshot_data.get("records", [])
    staged_count = 0
    normalized_count = 0
    errors_count = 0

    for raw in records:
        source_record_id = raw.get("source_record_id")
        title = raw.get("job_title")
        employer = raw.get("employer_name")
        district = raw.get("district", "Pune")
        sector = raw.get("sector")

        staging_id = hashlib.sha256(f"{source.source_id}:{source_record_id}".encode("utf-8")).hexdigest()

        # Validation
        validation_errors = []
        if not source_record_id:
            validation_errors.append("Missing source_record_id")
        if not title:
            validation_errors.append("Missing job_title")
        if not employer:
            validation_errors.append("Missing employer_name")
        if not district:
            validation_errors.append("Missing district")
        if not sector:
            validation_errors.append("Missing sector")

        is_valid = "valid" if not validation_errors else "invalid"
        error_str = "; ".join(validation_errors) if validation_errors else None

        job_hash = calculate_job_hash(source.source_id, source_record_id, title, employer) if is_valid == "valid" else None

        existing_staging = db.query(JobStaging).filter(JobStaging.staging_id == staging_id).first()
        if not existing_staging:
            staging_rec = JobStaging(
                staging_id=staging_id,
                source_id=source.source_id,
                source_record_id=source_record_id,
                raw_title=title or "",
                raw_employer=employer or "",
                raw_description=raw.get("description"),
                raw_location=raw.get("location"),
                raw_salary=raw.get("salary"),
                raw_experience=raw.get("experience_years"),
                raw_education=raw.get("min_education"),
                raw_sector=sector or "Unknown",
                raw_district=district or "Pune",
                raw_state=raw.get("state", "Maharashtra"),
                raw_posted_date=raw.get("posted_date"),
                raw_json=json.dumps(raw),
                is_valid=is_valid,
                validation_errors=error_str,
                processing_status="staged" if is_valid == "valid" else "failed",
                job_identity_hash=job_hash,
                created_at=datetime.utcnow()
            )
            db.add(staging_rec)
            staged_count += 1
        else:
            staging_rec = existing_staging

        db.commit()

        if is_valid == "valid":
            existing_job = db.query(Job).filter(Job.job_identity_hash == job_hash).first()
            if not existing_job:
                min_exp, max_exp = parse_experience(raw.get("experience_years"))
                min_sal, max_sal = parse_salary(raw.get("salary"))

                posted_dt = None
                if raw.get("posted_date"):
                    try:
                        posted_dt = datetime.strptime(raw.get("posted_date"), "%Y-%m-%d").date()
                    except ValueError:
                        posted_dt = date.today()

                job_rec = Job(
                    job_id=staging_id,
                    source_id=source.source_id,
                    source_record_id=source_record_id,
                    job_title=title,
                    employer_name=employer,
                    description=raw.get("description"),
                    state=raw.get("state", "Maharashtra"),
                    district=district,
                    location_detail=raw.get("location"),
                    sector=sector,
                    experience_years_min=min_exp,
                    experience_years_max=max_exp,
                    min_education=raw.get("min_education"),
                    salary_min=min_sal,
                    salary_max=max_sal,
                    salary_currency="INR",
                    posted_date=posted_dt,
                    created_at=datetime.utcnow(),
                    job_identity_hash=job_hash,
                    raw_json=json.dumps(raw)
                )
                db.add(job_rec)
                staging_rec.processing_status = "normalized"
                staging_rec.processed_at = datetime.utcnow()
                db.commit()
                normalized_count += 1
        else:
            errors_count += 1

    return {
        "status": "success",
        "source_id": source.source_id,
        "classification": "UNVERIFIED_OR_SYNTHETIC",
        "total_records_processed": len(records),
        "staged": staged_count,
        "normalized": normalized_count,
        "errors": errors_count
    }
