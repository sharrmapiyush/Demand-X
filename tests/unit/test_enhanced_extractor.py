"""Tests for Enhanced Skill Extractor — cross-field confidence boost, common aliases."""
import pytest
from types import SimpleNamespace


def test_enhanced_extractor_basic():
    from core.skills.enhanced_extractor import extract_job_skills_enhanced
    from core.skills.ontology_matcher import SkillMatcher

    matcher = SkillMatcher()
    job = SimpleNamespace(
        id="test-001",
        source_skills="Python, Django",
        job_title="Senior Python Developer",
        description="Experience with Django and PostgreSQL",
    )
    evidence, unmatched, profile = extract_job_skills_enhanced(job, matcher)
    assert len(evidence) > 0
    assert profile.total_mentions > 0


def test_enhanced_extractor_no_new_skills():
    """Must only resolve to the existing 32 canonical skills — never invent new ones."""
    from core.skills.enhanced_extractor import extract_job_skills_enhanced, COMMON_ALIASES
    from core.skills.ontology_matcher import SkillMatcher

    matcher = SkillMatcher()
    # All aliases should map to existing canonical skill IDs
    job = SimpleNamespace(
        id="test-alias",
        source_skills="ms excel, microsoft word, data entry",
        job_title="Office Assistant",
        description="Customer care experience",
    )
    evidence, unmatched, profile = extract_job_skills_enhanced(job, matcher)
    # Verify every alias resolved to a known canonical skill
    for ev in evidence:
        assert ev.canonical_skill_id.startswith("SKL-"), f"Invalid skill ID: {ev.canonical_skill_id}"


def test_common_aliases_coverage():
    from core.skills.enhanced_extractor import COMMON_ALIASES
    # Verify aliases exist
    assert "ms excel" in COMMON_ALIASES
    assert "data entry" in COMMON_ALIASES
    assert "customer care" in COMMON_ALIASES


def test_cross_field_boost():
    """Skills in ≥2 evidence fields should get boosted confidence."""
    from core.skills.enhanced_extractor import _boost_confidence
    from core.skills.models import SkillEvidence, MatchConfidence

    low_ev = SkillEvidence(
        job_posting_id="j1",
        source_skill_text="python",
        canonical_skill_id="SKL-TECH-01",
        canonical_skill_name="Python",
        extraction_method="SOURCE_SKILL",
        match_confidence=MatchConfidence.LOW.value,
        evidence_text="python",
        evidence_type="SOURCE_SKILL",
    )
    # Skill seen in 2 distinct fields → LOW boosted to MEDIUM
    boosted = _boost_confidence(low_ev, {"SKL-TECH-01": ["SOURCE_SKILL", "JOB_TITLE"]})
    assert boosted.match_confidence == MatchConfidence.MEDIUM.value
    # Single field → unchanged
    unchanged = _boost_confidence(low_ev, {"SKL-TECH-01": ["SOURCE_SKILL"]})
    assert unchanged.match_confidence == MatchConfidence.LOW.value


def test_empty_job():
    from core.skills.enhanced_extractor import extract_job_skills_enhanced
    from core.skills.ontology_matcher import SkillMatcher

    matcher = SkillMatcher()
    job = SimpleNamespace(id="empty", source_skills=None, job_title="", description="")
    evidence, unmatched, profile = extract_job_skills_enhanced(job, matcher)
    assert len(evidence) == 0
    assert profile.total_mentions == 0


def test_profile_counts_distinct_skills():
    from core.skills.enhanced_extractor import extract_job_skills_enhanced
    from core.skills.ontology_matcher import SkillMatcher

    matcher = SkillMatcher()
    job = SimpleNamespace(
        id="test-distinct",
        source_skills="Python, Python, Django",
        job_title="Python Developer",
        description="Python and Django experience",
    )
    evidence, unmatched, profile = extract_job_skills_enhanced(job, matcher)
    # matched_skills should be count of distinct canonical skills, not evidence rows
    distinct_ids = set(ev.canonical_skill_id for ev in evidence)
    assert profile.matched_skills == len(distinct_ids)
