from sqlalchemy import Column, String, Text, Integer, JSON, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship
from core.models.base import Base


class DVETInstitute(Base):
    __tablename__ = "dvet_institutes"

    institute_id = Column(String(64), primary_key=True, index=True)
    institute_code = Column(String(64), index=True, nullable=True)
    ncvt_mis_code = Column(String(64), index=True, nullable=True)
    institute_name = Column(String(255), nullable=False)
    institute_category = Column(String(100), nullable=True)
    district = Column(String(100), default="Pune", nullable=False)
    state = Column(String(100), default="Maharashtra", nullable=False)
    address = Column(Text, nullable=True)
    establishment_year = Column(String(50), nullable=True)
    establishment_gr = Column(String(255), nullable=True)
    hostel_capacity = Column(String(100), nullable=True)
    source_id = Column(String(64), ForeignKey("sources.source_id"), nullable=False, index=True)
    raw_json = Column(JSON, nullable=True)
    record_identity_hash = Column(String(64), unique=True, index=True, nullable=False)

    # Relationship to trades (optional, for relational completeness)
    trades = relationship("DVETTrade", back_populates="institute", foreign_keys="DVETTrade.institute_id")


class DVETTrade(Base):
    __tablename__ = "dvet_trades"

    trade_id = Column(String(64), primary_key=True, index=True)
    institute_code = Column(String(64), index=True, nullable=False)
    institute_name = Column(String(255), nullable=True)
    trade_name = Column(String(255), nullable=False)
    unit_category = Column(String(100), nullable=True)
    intake = Column(String(50), nullable=True)
    district = Column(String(100), default="Pune", nullable=False)
    state = Column(String(100), default="Maharashtra", nullable=False)
    source_id = Column(String(64), ForeignKey("sources.source_id"), nullable=False, index=True)
    institute_id = Column(String(64), ForeignKey("dvet_institutes.institute_id"), nullable=True, index=True)
    raw_json = Column(JSON, nullable=True)
    trade_identity_hash = Column(String(64), unique=True, index=True, nullable=False)

    # Relationship to institute
    institute = relationship("DVETInstitute", back_populates="trades", foreign_keys=[institute_id])
