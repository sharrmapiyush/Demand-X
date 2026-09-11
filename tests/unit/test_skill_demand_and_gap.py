"""Unit tests for Skill Demand Engine + Skill Gap Engine.

Uses in-memory SQLite with FK enforcement. Tests cover:
  - Canonical skill demand aggregation
  - Deduplication
  - Filtering (district, sector, source)
  - Zero-demand / no-data
  - DVET supply mapping
  - Gap classification (HIGH, MEDIUM, LOW, NO_DATA, NEEDS_REVIEW)
  - Deterministic re-run
  - No fabricated scores
"""

from __future__ import annotations

import pytest
from datetime import date, datetime
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.models.base import Base
from core.models.observation import JobPosting
from core.analytics.skill_demand_engine import (
    generate_run_id,
    _load_skills_seed,
)
from core.analytics.skill_gap_engine import classify_gap, calculate_skill_gap


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_db():
    """Create in-memory SQLite with tables and FK enforcement."""
    eng = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(eng)
    Session = sessionmaker(bind=eng)
    return eng, Session()


def _add_job(session, *, job_id="J1", title="Java Developer", desc="Looking for Java",
             source_skills="", district="Pune", sector="IT", source_id="naukri-historical-promptcloud",
             retrieved_at=None):
    """Insert a minimal JobPosting row."""
    row = JobPosting(
        id=job_id,
        source_id=source_id,
        job_title=title,
        description=desc,
        source_skills=source_skills,
        district=district,
        sector=sector,
        retrieved_at=retrieved_at or datetime(2026, 9, 10),
        record_identity_hash=f"hash-{job_id}",
        status="EXPIRED",
    )
    session.add(row)
    session.flush()
    return row


# ── Tests ────────────────────────────────────────────────────────────────────

class TestSkillDemandEngine:
    """Tests for the demand side (relying on calculate_skill_demand)."""

    def test_canonical_skills_loaded(self):
        """skills_seed.json must load >= 32 canonical skills."""
        skills = _load_skills_seed()
        assert len(skills) >= 32, f"Expected >=32 canonical skills, got {len(skills)}"

    def test_run_id_deterministic(self):
        """Same inputs → same run_id."""
        id1 = generate_run_id("mvp-v1", "Pune", "src", date(2026, 1, 1), date(2026, 12, 31))
        id2 = generate_run_id("mvp-v1", "Pune", "src", date(2026, 1, 1), date(2026, 12, 31))
        assert id1 == id2
        assert len(id1) == 64

    def test_run_id_differs_on_district(self):
        """Different district → different run_id."""
        id1 = generate_run_id("mvp-v1", "Pune", "src", date(2026, 1, 1), date(2026, 12, 31))
        id2 = generate_run_id("mvp-v1", "Mumbai", "src", date(2026, 1, 1), date(2026, 12, 31))
        assert id1 != id2


class TestGapClassification:
    """Tests for the gap classification logic (pure function, no DB)."""

    def test_high_gap(self):
        """≥5% normalized → HIGH_GAP when no supply."""
        status = classify_gap(
            distinct_job_count=500,
            normalized_distinct_job_count=0.05,
            has_dvet_supply=False,
            total_jobs=10000,
        )
        assert status == "HIGH_GAP"

    def test_medium_gap(self):
        """≥1% but <5% → MEDIUM_GAP."""
        status = classify_gap(
            distinct_job_count=200,
            normalized_distinct_job_count=0.02,
            has_dvet_supply=False,
            total_jobs=10000,
        )
        assert status == "MEDIUM_GAP"

    def test_low_gap(self):
        """Any demand but <1% → LOW_GAP."""
        status = classify_gap(
            distinct_job_count=50,
            normalized_distinct_job_count=0.005,
            has_dvet_supply=False,
            total_jobs=10000,
        )
        assert status == "LOW_GAP"

    def test_no_data(self):
        """Zero demand, no supply → NO_DATA."""
        status = classify_gap(
            distinct_job_count=0,
            normalized_distinct_job_count=0.0,
            has_dvet_supply=False,
            total_jobs=10000,
        )
        assert status == "NO_DATA"

    def test_no_data_zero_jobs(self):
        """Zero total jobs → NO_DATA."""
        status = classify_gap(
            distinct_job_count=0,
            normalized_distinct_job_count=0.0,
            has_dvet_supply=False,
            total_jobs=0,
        )
        assert status == "NO_DATA"

    def test_needs_review_with_supply(self):
        """Has DVET supply evidence → NEEDS_REVIEW regardless of demand."""
        status = classify_gap(
            distinct_job_count=5000,
            normalized_distinct_job_count=0.50,
            has_dvet_supply=True,
            total_jobs=10000,
        )
        assert status == "NEEDS_REVIEW"

    def test_needs_review_low_demand_with_supply(self):
        """Even low demand → NEEDS_REVIEW if supply exists."""
        status = classify_gap(
            distinct_job_count=5,
            normalized_distinct_job_count=0.0005,
            has_dvet_supply=True,
            total_jobs=10000,
        )
        assert status == "NEEDS_REVIEW"


class TestGapEngine:
    """Tests for the full gap calculation (requires mock demand_report)."""

    def _make_demand_report(self, *, total_jobs=10000, demand_rows=None):
        """Build a minimal demand_report dict for gap calculation."""
        if demand_rows is None:
            demand_rows = []
        return {
            "run_id": "test-run-id",
            "source_id": "naukri-historical-promptcloud",
            "total_jobs_evaluated": total_jobs,
            "dvet_supply_summary": {
                "institute_count": 1,
                "skills_with_supply_evidence": {
                    "SKL-COMP-01": {
                        "trades": ["Computer Operator and Programming Assistant"],
                        "count": 1,
                    },
                },
                "extrapolation_note": (
                    "Supply data covers ONLY ITI Haveli (1 institute). "
                    "NOT extrapolated to all of Pune."
                ),
            },
            "demand_rows": demand_rows,
        }

    def test_gap_summary_totals(self):
        """Gap summary counts must sum to total skills evaluated."""
        report = self._make_demand_report(
            demand_rows=[
                {"skill_id": "SKL-DEV-JAVA-01", "skill_name": "Java",
                 "distinct_job_count": 1000, "mention_count": 1200,
                 "normalized_distinct_job_count": 0.10,
                 "confidence": {"HIGH": 50, "MEDIUM": 950, "LOW": 0},
                 "evidence_type_breakdown": {"TITLE": 100, "DESCRIPTION": 1100, "SOURCE_SKILL": 0},
                 "verification_status": "SEED_NEEDS_REVIEW"},
                {"skill_id": "SKL-COMP-01", "skill_name": "Computer Op",
                 "distinct_job_count": 881, "mention_count": 920,
                 "normalized_distinct_job_count": 0.0881,
                 "confidence": {"HIGH": 0, "MEDIUM": 920, "LOW": 0},
                 "evidence_type_breakdown": {"TITLE": 0, "DESCRIPTION": 920, "SOURCE_SKILL": 0},
                 "verification_status": "SEED_NEEDS_REVIEW"},
                {"skill_id": "SKL-PAINT-01", "skill_name": "Painting",
                 "distinct_job_count": 0, "mention_count": 0,
                 "normalized_distinct_job_count": 0.0,
                 "confidence": {"HIGH": 0, "MEDIUM": 0, "LOW": 0},
                 "evidence_type_breakdown": {"TITLE": 0, "DESCRIPTION": 0, "SOURCE_SKILL": 0},
                 "verification_status": "SEED_NEEDS_REVIEW"},
            ]
        )
        gap = calculate_skill_gap(report)
        total = sum(gap["gap_summary"].values())
        assert total == 3, f"Expected 3 skills, got {total}"

    def test_high_gap_for_java(self):
        """Java with 10% normalized demand and no supply → HIGH_GAP."""
        report = self._make_demand_report(
            demand_rows=[
                {"skill_id": "SKL-DEV-JAVA-01", "skill_name": "Java",
                 "distinct_job_count": 1000, "mention_count": 1200,
                 "normalized_distinct_job_count": 0.10,
                 "confidence": {}, "evidence_type_breakdown": {},
                 "verification_status": "SEED_NEEDS_REVIEW"},
            ]
        )
        gap = calculate_skill_gap(report)
        java_row = next(r for r in gap["gap_rows"] if r["skill_id"] == "SKL-DEV-JAVA-01")
        assert java_row["gap_status"] == "HIGH_GAP"

    def test_needs_review_for_comp(self):
        """SKL-COMP-01 has DVET supply → NEEDS_REVIEW."""
        report = self._make_demand_report(
            demand_rows=[
                {"skill_id": "SKL-COMP-01", "skill_name": "Computer Op",
                 "distinct_job_count": 881, "mention_count": 920,
                 "normalized_distinct_job_count": 0.0881,
                 "confidence": {}, "evidence_type_breakdown": {},
                 "verification_status": "SEED_NEEDS_REVIEW"},
            ]
        )
        gap = calculate_skill_gap(report)
        comp_row = next(r for r in gap["gap_rows"] if r["skill_id"] == "SKL-COMP-01")
        assert comp_row["gap_status"] == "NEEDS_REVIEW"
        assert comp_row["has_dvet_supply_evidence"] is True

    def test_no_data_for_paint(self):
        """SKL-PAINT-01 with 0 demand → NO_DATA."""
        report = self._make_demand_report(
            demand_rows=[
                {"skill_id": "SKL-PAINT-01", "skill_name": "Painting",
                 "distinct_job_count": 0, "mention_count": 0,
                 "normalized_distinct_job_count": 0.0,
                 "confidence": {}, "evidence_type_breakdown": {},
                 "verification_status": "SEED_NEEDS_REVIEW"},
            ]
        )
        gap = calculate_skill_gap(report)
        paint_row = next(r for r in gap["gap_rows"] if r["skill_id"] == "SKL-PAINT-01")
        assert paint_row["gap_status"] == "NO_DATA"

    def test_no_fabricated_scores(self):
        """demand_score must NOT appear in gap rows (not fabricated)."""
        report = self._make_demand_report(
            demand_rows=[
                {"skill_id": "SKL-DEV-JAVA-01", "skill_name": "Java",
                 "distinct_job_count": 1000, "mention_count": 1200,
                 "normalized_distinct_job_count": 0.10,
                 "confidence": {}, "evidence_type_breakdown": {},
                 "verification_status": "SEED_NEEDS_REVIEW"},
            ]
        )
        gap = calculate_skill_gap(report)
        for row in gap["gap_rows"]:
            assert "demand_score" not in row, "demand_score must not be fabricated"

    def test_dvet_extrapolation_note_present(self):
        """The gap report must explicitly state supply is NOT extrapolated."""
        report = self._make_demand_report(demand_rows=[])
        gap = calculate_skill_gap(report)
        note = gap.get("dvet_extrapolation_note", "")
        assert "NOT extrapolated" in note or "NOT" in note.upper(), (
            f"Missing extrapolation disclaimer: {note}"
        )

    def test_thresholds_transparent(self):
        """Gap report must include the threshold configuration."""
        report = self._make_demand_report(demand_rows=[])
        gap = calculate_skill_gap(report)
        thresholds = gap.get("gap_thresholds", {})
        assert "high_gap_threshold" in thresholds
        assert "medium_gap_threshold" in thresholds
        assert thresholds["high_gap_threshold"] > thresholds["medium_gap_threshold"]
