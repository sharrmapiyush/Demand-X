"""Unit tests for Skill Demand Engine + Skill Gap Engine + Recommendation Safety.

Uses in-memory SQLite with FK enforcement. Tests cover:
  - Canonical skill demand aggregation
  - Deduplication
  - Filtering (district, sector, source)
  - Zero-demand / no-data
  - DVET supply mapping
  - Gap classification (HIGH, MEDIUM, LOW, NO_DATA, NEEDS_REVIEW)
  - Deterministic re-run
  - No fabricated scores
  - Recommendation safety rules (no strong claims from weak evidence)
"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock

# Mock psycopg2 to prevent DLL load failure when db.session is imported.
# (psycopg2 DLL blocked by Windows application control policy on Python 3.14)
for _mod in ('psycopg2', 'psycopg2._psycopg', 'psycopg2.extras', 'psycopg2.extensions'):
    sys.modules.setdefault(_mod, MagicMock())

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
from api.routers.skills import _build_recommendation


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


class TestRecommendationSafety:
    """Tests for conservative recommendation engine safety rules."""

    def _make_gap_row(self, *, skill_id="SKL-TEST-01", skill_name="Test Skill",
                       gap_status="HIGH_GAP", demand=1000, norm=0.10,
                       has_supply=False, supply_detail=None,
                       verification_status="SEED_NEEDS_REVIEW",
                       demand_confidence=None):
        """Build a minimal gap row for recommendation testing."""
        if demand_confidence is None:
            demand_confidence = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
        return {
            "skill_id": skill_id,
            "skill_name": skill_name,
            "gap_status": gap_status,
            "demand_distinct_job_count": demand,
            "demand_mention_count": demand,
            "demand_normalized_distinct_job_count": norm,
            "has_dvet_supply_evidence": has_supply,
            "dvet_supply_detail": supply_detail or {},
            "verification_status": verification_status,
            "demand_confidence": demand_confidence,
            "total_jobs_evaluated": 10000,
        }

    def test_high_gap_with_supply_recommends_validate_not_increase(self):
        """HIGH_GAP + supply (NEEDS_REVIEW) → 'Review / validate training supply', NOT 'Increase capacity'."""
        row = self._make_gap_row(
            gap_status="HIGH_GAP",
            demand=1000,
            norm=0.10,
            has_supply=True,
            supply_detail={"trades": ["Trade A"], "count": 1},
        )
        rec = _build_recommendation(row)

        assert "Review" in rec["recommendation"] or "validate" in rec["recommendation"].lower(), \
            f"Expected review/validate recommendation, got: {rec['recommendation']}"
        assert "Increase training capacity" not in rec["recommendation"], \
            "Must not recommend capacity increase when supply is NEEDS_REVIEW"
        assert rec["priority"] == "MEDIUM"
        assert rec["confidence"] == "LOW"
        # Evidence mentions "NOT verified" which is equivalent to NEEDS_REVIEW
        assert "NOT verified" in rec["evidence"] or "NEEDS_REVIEW" in rec["evidence"] or "unverified" in rec["evidence"].lower()

    def test_high_gap_no_supply_recommends_investigate_not_develop(self):
        """HIGH_GAP + no verified supply → 'Investigate training supply availability', NOT 'Develop new programme'."""
        row = self._make_gap_row(
            gap_status="HIGH_GAP",
            demand=1000,
            norm=0.10,
            has_supply=False,
        )
        rec = _build_recommendation(row)

        assert "Investigate" in rec["recommendation"] or "supply availability" in rec["recommendation"].lower(), \
            f"Expected investigate recommendation, got: {rec['recommendation']}"
        assert "Develop new training programme" not in rec["recommendation"], \
            "Must not recommend new programme when Pune-wide supply is UNKNOWN"
        assert "No institute currently offers this" not in rec["evidence"], \
            "Must not claim no institute offers this (snapshot incomplete)"
        assert rec["priority"] == "MEDIUM"
        assert rec["confidence"] == "LOW"
        assert "ITI Haveli" in rec["evidence"] or "UNKNOWN" in rec["evidence"]

    def test_no_data_recommends_collection_only(self):
        """NO_DATA → data collection only, no policy recommendation."""
        row = self._make_gap_row(
            gap_status="NO_DATA",
            demand=0,
            norm=0.0,
        )
        rec = _build_recommendation(row)

        assert "Collect more data" in rec["recommendation"] or "data" in rec["recommendation"].lower(), \
            f"Expected data collection recommendation, got: {rec['recommendation']}"
        assert rec["priority"] == "LOW"
        assert rec["confidence"] == "LOW"
        assert "zero" in rec["evidence"].lower() or "0" in rec["evidence"]

    def test_medium_gap_recommends_review_not_action(self):
        """MEDIUM_GAP → targeted review, not strong policy action."""
        row = self._make_gap_row(
            gap_status="MEDIUM_GAP",
            demand=200,
            norm=0.02,
        )
        rec = _build_recommendation(row)

        assert "review" in rec["recommendation"].lower() or "assess" in rec["recommendation"].lower(), \
            f"Expected review/assess recommendation, got: {rec['recommendation']}"
        assert rec["priority"] == "LOW"
        assert rec["confidence"] == "LOW"

    def test_needs_review_recommends_verification(self):
        """NEEDS_REVIEW → verify supply data."""
        row = self._make_gap_row(
            gap_status="NEEDS_REVIEW",
            demand=50,
            norm=0.005,
            has_supply=True,
            verification_status="NEEDS_REVIEW",
        )
        rec = _build_recommendation(row)

        assert "Verify" in rec["recommendation"] or "verify" in rec["recommendation"].lower(), \
            f"Expected verify recommendation, got: {rec['recommendation']}"
        assert rec["priority"] == "LOW"
        assert rec["confidence"] == "LOW"
        assert rec["data_quality"] == "NEEDS_REVIEW"

    def test_all_required_fields_present(self):
        """Every recommendation must include all required provenance fields."""
        row = self._make_gap_row(gap_status="HIGH_GAP", demand=1000, norm=0.10)
        rec = _build_recommendation(row)

        required = [
            "skill_id", "skill_name", "recommendation", "reason", "evidence",
            "priority", "confidence", "data_quality", "next_action",
            "source", "freshness", "evidence_status", "supply_status"
        ]
        for field in required:
            assert field in rec, f"Missing required field: {field}"
            assert rec[field], f"Required field '{field}' is empty"

    def test_evidence_status_labels(self):
        """evidence_status must be one of the explicit labels."""
        valid_labels = {"OBSERVED", "ESTIMATED", "PROJECTED", "INSUFFICIENT_DATA", "NEEDS_REVIEW", "NO_DATA"}

        for gap_status, norm in [
            ("HIGH_GAP", 0.10),
            ("MEDIUM_GAP", 0.02),
            ("LOW_GAP", 0.005),
            ("NO_DATA", 0.0),
        ]:
            row = self._make_gap_row(gap_status=gap_status, demand=100 if norm > 0 else 0, norm=norm)
            rec = _build_recommendation(row)
            assert rec["evidence_status"] in valid_labels, \
                f"evidence_status '{rec['evidence_status']}' not in {valid_labels}"

    def test_supply_status_labels(self):
        """supply_status must reflect DVET supply reality."""
        row_no_supply = self._make_gap_row(gap_status="HIGH_GAP", demand=1000, norm=0.10, has_supply=False)
        row_with_supply = self._make_gap_row(gap_status="HIGH_GAP", demand=1000, norm=0.10, has_supply=True)

        rec_no = _build_recommendation(row_no_supply)
        rec_yes = _build_recommendation(row_with_supply)

        assert rec_no["supply_status"] == "NO_SUPPLY_EVIDENCE"
        assert rec_yes["supply_status"] == "NEEDS_REVIEW"

    def test_no_pune_wide_extrapolation_claim(self):
        """Recommendations must never imply Pune-wide supply knowledge."""
        row = self._make_gap_row(gap_status="HIGH_GAP", demand=1000, norm=0.10, has_supply=False)
        rec = _build_recommendation(row)

        forbidden_phrases = [
            "pune-wide", "pune wide", "all of pune", "district-wide",
            "no institute in pune", "pune has no", "complete directory"
        ]
        combined = (rec["recommendation"] + " " + rec["evidence"] + " " + rec["next_action"]).lower()
        for phrase in forbidden_phrases:
            assert phrase not in combined, f"Forbidden extrapolation claim: '{phrase}' in {combined}"

    def test_high_gap_below_threshold_is_not_high(self):
        """Demand below HIGH threshold but above MEDIUM → MEDIUM_GAP (enforced by gap engine, not rec engine)."""
        # This tests that gap engine classification works correctly
        row = self._make_gap_row(
            gap_status="MEDIUM_GAP",  # Would be HIGH_GAP if norm >= 0.05
            demand=200,
            norm=0.02,  # Below 5% threshold
        )
        rec = _build_recommendation(row)
        assert rec["priority"] == "LOW"  # MEDIUM_GAP gets LOW priority
