"""Deterministic skill ontology matcher.

Loads the canonical skills seed (``core/ontology/skills_seed.json``) and
builds:

1. A **canonical-name** lookup (normalized → skill record).
2. An **alias** lookup (normalized alias → skill record).
3. A compiled ``re.Regex`` that finds any canonical name or alias inside
   an arbitrary text block (title / description), with word-boundary
   protection to prevent spurious substring matches (e.g. "Java" inside
   "JavaScript").

No LLM, no ML, no fuzzy matching thresholds — only exact normalized
phrase matches under word boundaries.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional, Tuple

from core.skills.models import ExtractionMethod, MatchConfidence


# ── helpers ──────────────────────────────────────────────────────────────────

_SKILLS_SEED_PATH = os.path.join(
    os.path.dirname(__file__), "..", "ontology", "skills_seed.json"
)


def normalize(text: Optional[str]) -> str:
    """Collapse whitespace, lowercase, strip.  Deterministic."""
    if not text:
        return ""
    return " ".join(text.strip().lower().split())


def _word_boundary_pat(term: str) -> str:
    """Escape *term* for regex and wrap in word-boundary assertions.

    Uses look-behind / look-ahead for ASCII word characters
    (letters, digits, underscore) so that "Java" does NOT match
    inside "JavaScript", and "C++" does NOT match inside "C++Builder"
    (the trailing ``+`` is non-word, so ``\\b`` works; but for safety we
    also use negative look-ahead for word chars).
    """
    escaped = re.escape(term)
    # \b handles most cases; additionally guard with negative lookbehind/lookahead
    # for ASCII alphanum/underscore to be robust against edge cases.
    return rf"(?<!\w){escaped}(?!\w)"


def _load_seeds(path: Optional[str] = None) -> List[Dict[str, Any]]:
    seed_path = path or _SKILLS_SEED_PATH
    with open(seed_path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    return data.get("skills", [])


# ── SkillMatcher ─────────────────────────────────────────────────────────────

class SkillMatcher:
    """Deterministic phrase matcher against the canonical skill ontology.

    Parameters
    ----------
    seed_path : str | None
        Override the default ``skills_seed.json`` path (useful for tests).
    extra_aliases : dict[str, str] | None
        Additional equivalences of the form ``{observed_form: canonical_alias}``
        used only by ``normalize_equivalent``.  Each key must resolve (after
        normalization) to the same canonical skill as its value.
    """

    def __init__(
        self,
        seed_path: Optional[str] = None,
        extra_aliases: Optional[Dict[str, str]] = None,
    ):
        seeds = _load_seeds(seed_path)

        # canonical_name (normalized) → skill record
        self._canonical: Dict[str, Dict[str, Any]] = {}
        # alias (normalized) → skill record
        self._aliases: Dict[str, Dict[str, Any]] = {}

        self._seeds_by_id: Dict[str, Dict[str, Any]] = {
            s["skill_id"]: s for s in seeds
        }

        for skill in seeds:
            norm_canonical = normalize(skill["canonical_skill_name"])
            self._canonical[norm_canonical] = skill
            for alias in skill.get("aliases", []):
                self._aliases[normalize(alias)] = skill

        # Build extra equivalence map (optional)
        self._equivalence: Dict[str, str] = {}
        if extra_aliases:
            for obs, canonical_alias in extra_aliases.items():
                self._equivalence[normalize(obs)] = normalize(canonical_alias)

        # Build one combined regex for fast in-text phrase search.
        # Order: longest phrases first to avoid partial prefix matches.
        all_phrases = sorted(
            set(self._canonical.keys()) | set(self._aliases.keys()),
            key=len,
            reverse=True,
        )
        if all_phrases:
            alts = "|".join(_word_boundary_pat(p) for p in all_phrases)
            self._text_re = re.compile(alts, re.IGNORECASE)
        else:
            self._text_re = None

        # Cache skill lookup by normalized phrase (canonical + alias)
        self._phrase_to_skill: Dict[str, Dict[str, Any]] = {}
        for phrase, skill in self._canonical.items():
            self._phrase_to_skill[phrase] = skill
        for phrase, skill in self._aliases.items():
            if phrase not in self._phrase_to_skill:
                self._phrase_to_skill[phrase] = skill

    # ── public API ────────────────────────────────────────────────────────

    def lookup_skill(self, normalized_phrase: str) -> Optional[Dict[str, Any]]:
        """Return skill record if *normalized_phrase* is a canonical name or alias."""
        return self._phrase_to_skill.get(normalized_phrase)

    def match_source_skill_segment(
        self, segment: str
    ) -> Optional[Tuple[str, str, str, str, str]]:
        """Match a single source_skills segment against the ontology.

        Returns
        -------
        (skill_id, canonical_name, method, confidence, normalized_observed) | None
        """
        norm = normalize(segment)
        if not norm:
            return None

        # 1. Direct equivalence via extra_aliases map
        equiv = self._equivalence.get(norm)
        if equiv is not None:
            skill = self._phrase_to_skill.get(equiv)
            if skill:
                return (
                    skill["skill_id"],
                    skill["canonical_skill_name"],
                    ExtractionMethod.SOURCE_SKILL_ALIAS,
                    MatchConfidence.MEDIUM,
                    norm,
                )

        # 2. Exact canonical name match
        skill = self._canonical.get(norm)
        if skill is not None:
            return (
                skill["skill_id"],
                skill["canonical_skill_name"],
                ExtractionMethod.SOURCE_SKILL_EXACT,
                MatchConfidence.HIGH,
                norm,
            )

        # 3. Exact alias match
        skill = self._aliases.get(norm)
        if skill is not None:
            return (
                skill["skill_id"],
                skill["canonical_skill_name"],
                ExtractionMethod.SOURCE_SKILL_ALIAS,
                MatchConfidence.MEDIUM,
                norm,
            )

        return None

    def find_matches_in_text(
        self, text: str, evidence_type: str
    ) -> List[Tuple[str, str, str, str, str, str]]:
        """Find all canonical/alias phrases in *text* (title or description).

        Returns a list of
        (skill_id, canonical_name, method, confidence, matched_phrase, evidence_text)
        tuples.  ``evidence_text`` is the surrounding context snippet.

        Matching rules
        ──────────────
        * Word-boundary protected phrase match (``\\b``).
        * If the matched phrase equals the skill's canonical name → EXACT / HIGH.
        * If the matched phrase equals an alias               → ALIAS / MEDIUM.
        * Longest-match-wins when a canonical and alias overlap
          (canonical takes priority).
        """
        if self._text_re is None or not text:
            return []

        method_prefix = "DESCRIPTION" if evidence_type == "JOB_DESCRIPTION" else "TITLE"
        results: List[Tuple[str, str, str, str, str, str]] = []
        seen_skills: set = set()  # one match per skill per text

        for m in self._text_re.finditer(text):
            phrase = normalize(m.group(0))
            if not phrase:
                continue

            # Determine which skill this phrase maps to
            skill = self._canonical.get(phrase) or self._aliases.get(phrase)
            if skill is None:
                continue

            skill_id = skill["skill_id"]
            if skill_id in seen_skills:
                continue
            seen_skills.add(skill_id)

            # Method = EXACT if phrase matches canonical; ALIAS if alias
            is_canonical = phrase in self._canonical
            if is_canonical:
                method = getattr(ExtractionMethod, f"{method_prefix}_EXACT")
                confidence = MatchConfidence.HIGH
            else:
                method = getattr(ExtractionMethod, f"{method_prefix}_ALIAS")
                confidence = MatchConfidence.MEDIUM

            # Evidence snippet: ±40 chars around match
            start = max(m.start() - 40, 0)
            end = min(m.end() + 40, len(text))
            snippet = text[start:end].strip()
            # Collapse whitespace in snippet for cleanliness
            snippet = " ".join(snippet.split())

            results.append((
                skill_id,
                skill["canonical_skill_name"],
                method,
                confidence,
                phrase,
                snippet,
            ))

        return results

    # ── helpers for candidate analysis ────────────────────────────────────

    @property
    def canonical_ids(self) -> List[str]:
        return sorted(self._seeds_by_id.keys())

    def get_skill(self, skill_id: str) -> Optional[Dict[str, Any]]:
        return self._seeds_by_id.get(skill_id)
