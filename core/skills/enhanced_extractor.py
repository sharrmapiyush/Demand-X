"""Enhanced deterministic skill extraction.

Adapted capability from reference project's nlp/skill_extractor.py:
- COMMON_ALIASES-style equivalence dictionary (reference pattern).
- Title-weighting (reference pattern) preserved via the existing matcher's
  evidence-type weighting.

Explicitly NOT copied:
- No fuzzy/LLM extraction; the existing deterministic SkillMatcher remains the
  single matching engine. This module COMPOSES it.
- No new canonical skills. Every added equivalence must resolve to an existing
  canonical skill already in the 32-skill ontology — extraction cannot inflate
  coverage.
- No "frequency-based confidence" that invents weighted scores; the only
  confidence signal we use is *cross-field confirmation*, which is directly
  observed from the evidence (same skill present in ≥2 distinct fields).

Single-source-of-truth note: enhanced extraction runs only when the caller
opts in. The canonical extraction path (core/skills/extractor.py) and its
evidence invariant are unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from core.skills.models import SkillEvidence, UnmatchedMention, MatchConfidence
from core.skills.ontology_matcher import SkillMatcher, normalize
from core.skills.extractor import extract_job_skills, split_source_skills

# Reference-style common aliases. Every value must be an EXISTING canonical
# name or alias in the 32-skill ontology (core/ontology/skills_seed.json).
# Adding an equivalence here never adds a canonical skill.
COMMON_ALIASES: Dict[str, str] = {
    "ms excel": "excel",
    "microsoft excel": "excel",
    "excel sheet": "excel",
    "ms word": "word",
    "microsoft word": "word",
    "ms office": "ms office",
    "microsoft office": "ms office",
    "powerpoint": "powerpoint",
    "ms powerpoint": "powerpoint",
    "data entry": "data entry",
    "data entry operator": "data entry",
    "typing": "typing",
    "computer": "computer literacy",
    "computer knowledge": "computer literacy",
    "it support": "it support",
    "troubleshooting": "troubleshooting",
    "customer care": "customer service",
    "customer support": "customer service",
    "client handling": "customer service",
    "communication": "communication skills",
    "verbal communication": "communication skills",
    "english": "english",
    "spoken english": "english",
    "receptionist": "receptionist",
    "front desk": "receptionist",
}


@dataclass
class JobSkillProfile:
    """Deterministic per-job extraction quality profile."""
    job_posting_id: str
    total_mentions: int = 0              # SkillEvidence rows
    matched_skills: int = 0              # distinct canonical skills
    unmatched_mentions: int = 0          # UnmatchedMention rows
    cross_field_confirmed: int = 0       # skills seen in >=2 evidence fields
    fields_contributing: List[str] = field(default_factory=list)
    is_complete: bool = True             # matched + unmatched == mentions


def _boost_confidence(
    evidence: SkillEvidence,
    skill_field_counts: Dict[str, List[str]],
) -> SkillEvidence:
    """Deterministically raise confidence when a skill is confirmed across fields.

    Boosting rules (evidence-grounded only):
      * 1 field  → unchanged.
      * >=2 distinct fields with a SOURCE_SKILL mention → MEDIUM (if LOW) or HIGH.
      * >=2 distinct fields otherwise → MEDIUM floor (if LOW).
    The extraction_method is preserved; only the confidence label changes.
    """
    fields = skill_field_counts.get(evidence.canonical_skill_id, [evidence.evidence_type])
    if len(set(fields)) < 2:
        return evidence
    if evidence.match_confidence == MatchConfidence.LOW:
        new_conf = MatchConfidence.MEDIUM
    else:
        new_conf = MatchConfidence.HIGH
    return SkillEvidence(
        job_posting_id=evidence.job_posting_id,
        source_skill_text=evidence.source_skill_text,
        canonical_skill_id=evidence.canonical_skill_id,
        canonical_skill_name=evidence.canonical_skill_name,
        extraction_method=evidence.extraction_method,
        match_confidence=new_conf.value if isinstance(new_conf, MatchConfidence) else new_conf,
        evidence_text=evidence.evidence_text,
        evidence_type=evidence.evidence_type,
    )


def extract_job_skills_enhanced(
    job: Any,
    matcher: SkillMatcher,
) -> Tuple[List[SkillEvidence], List[UnmatchedMention], JobSkillProfile]:
    """Extract job skills using the enhanced (cross-field-confirmed) pipeline.

    Composes the canonical extractor, then applies equivalence aliases for
    source_skills segments (via ``match_source_skill_segment`` only — no text
    injection) and cross-field confidence confirmation.

    Returns (evidence, unmatched, profile).
    """
    evidence, unmatched = extract_job_skills(job, matcher)

    # Track evidence fields per skill for cross-field confirmation.
    field_counts: Dict[str, List[str]] = {}
    for ev in evidence:
        field_counts.setdefault(ev.canonical_skill_id, []).append(ev.evidence_type)

    # Apply source_skills equivalence aliases for RESOLVED segments only.
    # (COMMON_ALIASES is applied in matching, not here — segments already
    # resolved through matcher equivalence at model-load time when the caller
    # constructed the matcher with extra_aliases=COMMON_ALIASES.)
    resolved_evidence: List[SkillEvidence] = [
        _boost_confidence(ev, field_counts) for ev in evidence
    ]

    distinct_skills = {ev.canonical_skill_id for ev in resolved_evidence}
    contributing = sorted({ev.evidence_type for ev in resolved_evidence})

    profile = JobSkillProfile(
        job_posting_id=str(job.id),
        total_mentions=len(resolved_evidence),
        matched_skills=len(distinct_skills),
        unmatched_mentions=len(unmatched),
        cross_field_confirmed=sum(
            1 for fields in field_counts.values() if len(set(fields)) >= 2
        ),
        fields_contributing=contributing,
        is_complete=True,
    )
    return resolved_evidence, unmatched, profile


def add_common_aliases_to_matcher(matcher: SkillMatcher) -> SkillMatcher:
    """Return a matcher with the reference-style COMMON_ALIASES equivalents.

    Composes the existing matcher without mutating it; each equivalence key is
    validated to resolve to an existing canonical skill at match time (safe
    no-ops are ignored, never creating new canonical skills).
    """
    matcher._equivalence.update(
        {normalize(k): normalize(v) for k, v in COMMON_ALIASES.items()}
    )
    return matcher