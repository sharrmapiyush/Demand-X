"""Deterministic skill extractor for a single JobPosting.

Orchestrates the matcher across the three evidence sources (source_skills,
job_title, job_description) in priority order, producing :class:`SkillEvidence`
and :class:`UnmatchedMention` records.  One extraction call per job; no DB
persistence — pure function of input data.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from core.skills.models import SkillEvidence, UnmatchedMention
from core.skills.ontology_matcher import SkillMatcher, normalize


# ── Segment splitting ────────────────────────────────────────────────────────

_SOURCE_SKILL_SEPS = re.compile(r"[,;/|]+")


def split_source_skills(raw: Optional[str]) -> List[str]:
    """Split a ``source_skills`` string into individual segments.

    Handles comma, semicolon, slash, pipe separators. Ampersand is *not* a
    separator — canonical skill names use it as a conjunction
    ("Machine Tool Operation & Precision Measurement").
    Returns non-empty segments with whitespace stripped.
    """
    if not raw:
        return []
    segments = _SOURCE_SKILL_SEPS.split(raw)
    return [s.strip() for s in segments if s.strip()]


# ── Extraction ───────────────────────────────────────────────────────────────

def extract_job_skills(
    job: Any,
    matcher: SkillMatcher,
) -> Tuple[List[SkillEvidence], List[UnmatchedMention]]:
    """Extract skill evidence from a single job posting.

    Parameters
    ----------
    job
        Must expose ``id``, ``source_skills``, ``job_title``, ``description``
        attributes (SQLAlchemy ``JobPosting`` or compatible namedtuple/dataclass).
    matcher
        Loaded :class:`SkillMatcher` instance.

    Returns
    -------
    (evidence_list, unmatched_list)

    Processing rules
    ─────────────────
    1. ``source_skills`` → split on separators → each segment matched via
       ``matcher.match_source_skill_segment()`` → EXACT or ALIAS.
    2. ``job_title`` → regex scan via ``matcher.find_matches_in_text()``.
    3. ``description`` → regex scan via ``matcher.find_matches_in_text()``.
    4. Duplicate (job_id, skill_id, source_family) tuples are deduplicated:
       only the first occurrence is kept.
    5. Unmatched segments (no canonical resolution) become
       :class:`UnmatchedMention` records.
    """
    job_id = str(job.id)
    evidence: List[SkillEvidence] = []
    unmatched: List[UnmatchedMention] = []
    seen: set = set()  # (skill_id, source_family)

    # ── 1. source_skills ──────────────────────────────────────────────────
    for segment in split_source_skills(getattr(job, "source_skills", None)):
        result = matcher.match_source_skill_segment(segment)
        if result is None:
            unmatched.append(UnmatchedMention(
                job_posting_id=job_id,
                source_field="SOURCE_SKILL",
                raw_text=segment,
                normalized_text=normalize(segment),
            ))
            continue

        skill_id, canonical_name, method, confidence, norm_observed = result
        dedup_key = (skill_id, "SOURCE_SKILL")
        if dedup_key in seen:
            continue
        seen.add(dedup_key)

        evidence.append(SkillEvidence(
            job_posting_id=job_id,
            source_skill_text=segment,
            canonical_skill_id=skill_id,
            canonical_skill_name=canonical_name,
            extraction_method=method,
            match_confidence=confidence,
            evidence_text=segment,
            evidence_type="SOURCE_SKILL",
        ))

    # ── 2. job_title ──────────────────────────────────────────────────────
    title = getattr(job, "job_title", None)
    if title:
        for (
            skill_id, canonical_name, method, confidence, phrase, snippet
        ) in matcher.find_matches_in_text(title, "JOB_TITLE"):
            dedup_key = (skill_id, "JOB_TITLE")
            if dedup_key in seen:
                continue
            seen.add(dedup_key)

            evidence.append(SkillEvidence(
                job_posting_id=job_id,
                source_skill_text=phrase,
                canonical_skill_id=skill_id,
                canonical_skill_name=canonical_name,
                extraction_method=method,
                match_confidence=confidence,
                evidence_text=snippet,
                evidence_type="JOB_TITLE",
            ))

    # ── 3. description ────────────────────────────────────────────────────
    desc = getattr(job, "description", None)
    if desc:
        for (
            skill_id, canonical_name, method, confidence, phrase, snippet
        ) in matcher.find_matches_in_text(desc, "JOB_DESCRIPTION"):
            dedup_key = (skill_id, "JOB_DESCRIPTION")
            if dedup_key in seen:
                continue
            seen.add(dedup_key)

            evidence.append(SkillEvidence(
                job_posting_id=job_id,
                source_skill_text=phrase,
                canonical_skill_id=skill_id,
                canonical_skill_name=canonical_name,
                extraction_method=method,
                match_confidence=confidence,
                evidence_text=snippet,
                evidence_type="JOB_DESCRIPTION",
            ))

    return evidence, unmatched
