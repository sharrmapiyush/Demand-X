from sqlalchemy import Column, String, Text, Integer, Date, DateTime, ForeignKey, Index, JSON
from sqlalchemy.orm import relationship
from core.models.base import Base
from datetime import datetime


class JobPosting(Base):
    __tablename__ = "job_postings"

    id = Column(String(64), primary_key=True, index=True)
    source_id = Column(String(64), ForeignKey("sources.source_id"), nullable=False, index=True)
    source_record_id = Column(String(255), nullable=True)
    job_title = Column(String(500), nullable=False)
    employer_name = Column(String(500), nullable=True)
    location_text = Column(String(500), nullable=True)
    district = Column(String(100), nullable=True, index=True)
    state = Column(String(100), nullable=True, index=True)
    sector = Column(String(100), nullable=True, index=True)
    description = Column(Text, nullable=True)
    posted_date = Column(Date, nullable=True)
    retrieved_at = Column(DateTime, nullable=False, index=True)
    source_url = Column(String(1000), nullable=True)
    record_identity_hash = Column(String(64), nullable=False, unique=True)
    status = Column(String(50), nullable=False, default="ACTIVE", index=True)

    # New fields for source evidence and provenance
    source_skills = Column(Text, nullable=True)
    seats = Column(Integer, nullable=True)
    source_type = Column(String(50), nullable=True, index=True)
    freshness_class = Column(String(50), nullable=True, index=True)
    geographic_evidence = Column(JSON, nullable=True)

    # Relationships
    relationships = relationship("ObservationRelationship", back_populates="member_record", foreign_keys="ObservationRelationship.member_record_id")


class ApprenticeshipOpportunity(Base):
    __tablename__ = "apprenticeship_opportunities"

    id = Column(String(64), primary_key=True, index=True)
    source_id = Column(String(64), ForeignKey("sources.source_id"), nullable=False, index=True)
    source_record_id = Column(String(255), nullable=True)
    trade_title = Column(String(500), nullable=False)
    organization_name = Column(String(500), nullable=True)
    location_text = Column(String(500), nullable=True)
    district = Column(String(100), nullable=True, index=True)
    state = Column(String(100), nullable=True, index=True)
    sector = Column(String(100), nullable=True, index=True)
    seats_available = Column(Integer, nullable=True)
    application_start_date = Column(Date, nullable=True)
    application_end_date = Column(Date, nullable=True)
    posted_date = Column(Date, nullable=True)
    retrieved_at = Column(DateTime, nullable=False, index=True)
    source_url = Column(String(1000), nullable=True)
    record_identity_hash = Column(String(64), nullable=False, unique=True)
    status = Column(String(50), nullable=False, default="ACTIVE", index=True)


class ObservationRelationship(Base):
    __tablename__ = "observation_relationships"

    relationship_id = Column(String(64), primary_key=True)
    relationship_type = Column(String(50), nullable=False, index=True)
    group_id = Column(String(64), nullable=False, index=True)
    member_record_id = Column(String(64), ForeignKey("job_postings.id"), nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationship
    member_record = relationship("JobPosting", back_populates="relationships", foreign_keys=[member_record_id])

    __table_args__ = (
        Index('ix_observation_relationships_composite', 'group_id', 'relationship_type'),
    )
