from sqlalchemy import Column, String, Text, Integer, Float, DateTime, Date, ForeignKey, UniqueConstraint, Index, JSON
from core.models.base import Base
import datetime

class DemandCalculationRun(Base):
    __tablename__ = "demand_calculation_runs"

    run_id = Column(String(64), primary_key=True, index=True)
    started_at = Column(DateTime, nullable=False, index=True)
    completed_at = Column(DateTime, nullable=True)
    input_data_start_date = Column(Date, nullable=True)
    input_data_end_date = Column(Date, nullable=True)
    rule_version = Column(String(100), nullable=False)
    status = Column(String(50), nullable=False, index=True) # RUNNING, COMPLETED, FAILED

class DistrictOccupationDemand(Base):
    __tablename__ = "district_occupation_demand"

    id = Column(String(64), primary_key=True, index=True)
    run_id = Column(String(64), ForeignKey("demand_calculation_runs.run_id"), nullable=False, index=True)
    district = Column(String(100), nullable=False, index=True)
    occupation_id = Column(String(64), nullable=False, index=True)
    sector = Column(String(100), nullable=True)
    observation_period_start = Column(Date, nullable=False, index=True)
    observation_period_end = Column(Date, nullable=False, index=True)
    job_count = Column(Integer, nullable=False)
    apprenticeship_count = Column(Integer, nullable=False)
    demand_score = Column(Float, nullable=True)
    data_completeness_status = Column(String(50), nullable=False, index=True) # TRUE_ZERO, NO_DATA, INSUFFICIENT_DATA
    source_coverage_summary = Column(JSON, nullable=True)
    evidence = Column(JSON, nullable=True)
    provenance_state = Column(String(50), nullable=False, default="DERIVED") # OBSERVED, DERIVED, ESTIMATED, PREDICTED
    rule_version = Column(String(100), nullable=False)

    __table_args__ = (
        UniqueConstraint('district', 'occupation_id', 'observation_period_start', 'observation_period_end', 'run_id', name='uix_occupation_demand_composite'),
    )

class DistrictSkillDemand(Base):
    __tablename__ = "district_skill_demand"

    id = Column(String(64), primary_key=True, index=True)
    run_id = Column(String(64), ForeignKey("demand_calculation_runs.run_id"), nullable=False, index=True)
    district = Column(String(100), nullable=False, index=True)
    skill_id = Column(String(64), nullable=False, index=True)
    sector = Column(String(100), nullable=True)
    observation_period_start = Column(Date, nullable=False, index=True)
    observation_period_end = Column(Date, nullable=False, index=True)
    normalized_count = Column(Float, nullable=False)
    demand_score = Column(Float, nullable=True)
    data_completeness_status = Column(String(50), nullable=False, index=True) # TRUE_ZERO, NO_DATA, INSUFFICIENT_DATA
    source_coverage_summary = Column(JSON, nullable=True)
    evidence = Column(JSON, nullable=True)
    provenance_state = Column(String(50), nullable=False, default="DERIVED") # OBSERVED, DERIVED, ESTIMATED, PREDICTED
    rule_version = Column(String(100), nullable=False)

    __table_args__ = (
        UniqueConstraint('district', 'skill_id', 'observation_period_start', 'observation_period_end', 'run_id', name='uix_skill_demand_composite'),
    )
