from sqlalchemy import Column, String, Text, Integer, Date, DateTime, Numeric, ForeignKey, Index
from sqlalchemy.orm import relationship
from core.models.base import Base


class Job(Base):
    __tablename__ = "jobs"

    job_id = Column(String(64), primary_key=True, index=True)
    source_id = Column(String(64), ForeignKey("sources.source_id"), nullable=False, index=True)
    source_record_id = Column(String(128), nullable=False)

    # Core fields
    job_title = Column(String(255), nullable=False)
    employer_name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    # Location
    state = Column(String(100), nullable=False)
    district = Column(String(100), nullable=False, index=True)
    location_detail = Column(String(255), nullable=True)

    # Classification
    sector = Column(String(100), nullable=False, index=True)

    # Employment details
    experience_years_min = Column(Integer, nullable=True)
    experience_years_max = Column(Integer, nullable=True)
    min_education = Column(String(255), nullable=True)
    salary_min = Column(Numeric(12, 2), nullable=True)
    salary_max = Column(Numeric(12, 2), nullable=True)
    salary_currency = Column(String(3), default="INR", nullable=False)

    # Timestamps
    posted_date = Column(Date, nullable=True)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=True)

    # Deduplication
    job_identity_hash = Column(String(64), nullable=False, index=True)

    # Provenance
    raw_json = Column(Text, nullable=True)

    # Relationships
    source = relationship("Source", backref="jobs")


class JobStaging(Base):
    __tablename__ = "jobs_staging"

    staging_id = Column(String(64), primary_key=True, index=True)
    source_id = Column(String(64), nullable=False, index=True)
    source_record_id = Column(String(128), nullable=False)

    # Raw fields as received
    raw_title = Column(String(255), nullable=False)
    raw_employer = Column(String(255), nullable=False)
    raw_description = Column(Text, nullable=True)
    raw_location = Column(String(255), nullable=True)
    raw_salary = Column(String(255), nullable=True)
    raw_experience = Column(String(255), nullable=True)
    raw_education = Column(String(255), nullable=True)
    raw_sector = Column(String(100), nullable=False)
    raw_district = Column(String(100), nullable=False)
    raw_state = Column(String(100), nullable=False)
    raw_posted_date = Column(String(50), nullable=True)

    # Raw JSON payload
    raw_json = Column(Text, nullable=True)

    # Validation status
    is_valid = Column(String(20), nullable=False, default="pending")
    validation_errors = Column(Text, nullable=True)

    # Processing status
    processing_status = Column(String(20), nullable=False, default="pending")
    job_identity_hash = Column(String(64), nullable=True, index=True)

    created_at = Column(DateTime, nullable=False)
    processed_at = Column(DateTime, nullable=True)