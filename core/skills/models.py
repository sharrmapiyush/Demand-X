"""Data models for skill extraction results.

Defines the SkillEvidence object (one per matched skill–source–job triple),
UnmatchedMention (unmapped raw phrases for downstream analysis), and
summary/candidate record types used by the extraction report.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Optional


# ── Allowed values (per spec) ────────────────────────────────────────────────

class ExtractionMethod(str, enum.Enum):
    SOURCE_SKILL_EXACT = "SOURCE_SKILL_EXACT"
    SOURCE_SKILL_ALIAS = "SOURCE_SKILL_ALIAS"
    DESCRIPTION_EXACT = "DESCRIPTION_EXACT"
    DESCRIPTION_ALIAS = "DESCRIPTION_ALIAS"
    TITLE_EXACT = "TITLE_EXACT"
    TITLE_ALIAS = "TITLE_ALIAS"


class MatchConfidence(str, enum.Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


# ── Core extraction objects ──────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class SkillEvidence:
    """One piece of evidence that a job requested / listed a canonical skill.

    The same canonical skill may appear from multiple evidence sources
    (source_skills, title, description); each appearance is a separate
    ``SkillEvidence`` record.  ``extraction_method`` encodes which source
    field was used and whether the match was on the canonical name itself
    (EXACT) or an alias (ALIAS).
    """
    job_posting_id: str
    source_skill_text: str               # raw text that triggered the match
    canonical_skill_id: str
    canonical_skill_name: str
    extraction_method: str                # ExtractionMethod value
    match_confidence: str                 # MatchConfidence value
    evidence_text: str                    # context where the match was found
    evidence_type: str                    # SOURCE_SKILL | JOB_TITLE | JOB_DESCRIPTION


@dataclass(frozen=True, slots=True)
class UnmatchedMention:
    """A raw skill phrase that did not resolve to any canonical skill.

    Retained so downstream analysis can count unmatched mentions and
    feed the new-candidate discovery pipeline.
    """
    job_posting_id: str
    source_field: str                     # SOURCE_SKILL | JOB_TITLE | JOB_DESCRIPTION
    raw_text: str                         # the original segment / phrase
    normalized_text: str


# ── Report / CSV record types ───────────────────────────────────────────────

@dataclass
class ExtractionSummaryRecord:
    """One row of ``skill_extraction_summary.csv``."""
    canonical_skill_id: str
    canonical_skill_name: str
    job_count: int = 0                    # distinct jobs with ≥1 mention
    mention_count: int = 0                # total SkillEvidence rows
    source_skill_mentions: int = 0
    description_mentions: int = 0
    title_mentions: int = 0
    high_confidence_count: int = 0
    medium_confidence_count: int = 0
    low_confidence_count: int = 0


@dataclass
class SkillCandidate:
    """One row of ``naukri_skill_candidates.csv``."""
    candidate_skill: str                  # best normalized form
    observed_forms: str                   # comma-separated distinct raw forms
    job_count: int                        # distinct jobs mentioning this
    mention_count: int = 0                # raw token occurrences (tech candidates)
    example_source_skills: str = ""       # example raw source_skills values
    verification_status: str = "NEEDS_REVIEW"
    recommended_action: str = "NEEDS_REVIEW"
