from sqlalchemy import Column, String, Text, Boolean, DateTime
from core.models.base import Base


class Source(Base):
    __tablename__ = "sources"

    source_id = Column(String(64), primary_key=True, index=True)
    source_name = Column(String(255), nullable=False)
    organization = Column(String(255), nullable=False)
    url = Column(String(512), nullable=False)
    category = Column(String(100), nullable=False)
    access_method = Column(String(50), nullable=False)  # VERIFIED_API, VERIFIED_EXPORT, PUBLIC_PAGE, SOURCE_SNAPSHOT, MANUAL_CURATION
    freshness_class = Column(String(50), nullable=False)  # LIVE, PERIODIC, HISTORICAL, STATIC
    last_verified_at = Column(DateTime, nullable=True)
    last_fetched_at = Column(DateTime, nullable=True)
    coverage = Column(String(255), nullable=True)
    historical_depth = Column(String(255), nullable=True)
    reliability_notes = Column(Text, nullable=True)
    legal_access_notes = Column(Text, nullable=True)
    enabled = Column(Boolean, default=True, nullable=False)

    # Source-level provenance (added 007_source_provenance)
    # source_type: e.g. "SUPPLEMENTARY_HISTORICAL", "PRIMARY_LIVE"
    source_type = Column(String(50), nullable=True)
    # official_government_source: True if published by government authority
    official_government_source = Column(Boolean, nullable=True)
    # verification_status: e.g. "UNVERIFIED_EXTERNAL_DATASET", "VERIFIED"
    verification_status = Column(String(50), nullable=True)
