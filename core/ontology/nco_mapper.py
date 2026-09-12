"""NCO-2015 Mapper — token-similarity crosswalk to canonical occupations.

Adapted from reference project's nlp/nco_mapper.py (token similarity, weighted
70% title / 30% skills).

Reference flaws REJECTED:
- The reference hardcodes fallback NCO assignments for common job titles.
  Demand-X NEVER invents numeric NCO codes: a mapping is only VERIFIED when an
  authoritative source record provides the code; otherwise the result carries
  verification_status NEEDS_REVIEW and nco_code=None.
- No reference table is coined in code — the mapper loads a seed file provided
  by the platform (expected at data/reference/nco_occupations_seed.csv). When
  no authoritative seed is present, matches resolve as NEEDS_REVIEW and no code
  is emitted.
"""

import json
import logging
import os
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Token similarity weights (mirrors reference weighting).
TITLE_WEIGHT = 0.7
SKILLS_WEIGHT = 0.3

# Match quality thresholds.
MIN_CONFIDENCE = 0.35


@dataclass
class NCOMappingResult:
    canonical_occupation_id: Optional[str] = None
    canonical_occupation_name: Optional[str] = None
    nco_code: Optional[str] = None        # numeric code, only when authoritative
    nco_title: Optional[str] = None
    nco_division: Optional[str] = None
    nco_group: Optional[str] = None
    confidence: float = 0.0
    method: str = "NONE"
    verification_status: str = "NEEDS_REVIEW"
    matched_on: Optional[str] = None
    source_reference: Optional[str] = None

    def as_dict(self) -> Dict[str, Optional[str]]:
        return {
            "canonical_occupation_id": self.canonical_occupation_id,
            "canonical_occupation_name": self.canonical_occupation_name,
            "nco_code": self.nco_code,
            "nco_title": self.nco_title,
            "nco_division": self.nco_division,
            "nco_group": self.nco_group,
            "confidence": round(self.confidence, 4) if self.confidence is not None else None,
            "method": self.method,
            "verification_status": self.verification_status,
            "matched_on": self.matched_on,
            "source_reference": self.source_reference,
        }


def _norm(text: Optional[str]) -> str:
    if not text:
        return ""
    return " ".join(text.lower().split())


def _tokens(text: str) -> set:
    return set(re.findall(r"[a-z0-9]+", text))


def _jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


class NCOMapper:
    """Resolves occupation titles against a reference NCO seed.

    Pipeline:
      1. Build a reference index from the seed file (nco_code, occupation_title,
         division, group_name, and optional mapping to a canonical occupation).
      2. Score each reference entry against the query via weighted token Jaccard
         similarity (title 70%, skills 30%).
      3. Accept the best match above MIN_CONFIDENCE.
      4. verification_status is VERIFIED only when the seed entry carries an
         authoritative reference; otherwise NEEDS_REVIEW and no code is emitted.
    """

    def __init__(
        self,
        nco_reference_path: Optional[str] = None,
        canonical_occupations_path: Optional[str] = None,
    ):
        self.reference_path = nco_reference_path or os.path.join(
            os.path.dirname(__file__), "..", "..", "data", "reference", "nco_occupations_seed.csv"
        )
        self.canonical_occupations_path = canonical_occupations_path or os.path.join(
            os.path.dirname(__file__), "occupations_seed.json"
        )
        self._reference: List[Dict[str, object]] = []
        self._canonical: Dict[str, Dict[str, object]] = {}
        self.load()

    @property
    def seeded(self) -> bool:
        """True when an authoritative reference table was loaded."""
        return len(self._reference) > 0

    def load(self) -> None:
        """Load the canonical occupations and the NCO reference seed."""
        # Canonical occupations (always present).
        try:
            with open(self.canonical_occupations_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for occ in data.get("occupations", []):
                self._canonical[occ["occupation_id"]] = occ
        except Exception as exc:
            logger.warning("Could not load canonical occupations seed: %s", exc)

        # NCO reference seed (authoritative table; optional).
        if os.path.exists(self.reference_path):
            try:
                self._load_csv(self.reference_path)
            except Exception as exc:
                logger.warning("Could not load NCO reference CSV: %s", exc)
        else:
            logger.warning(
                "No authoritative NCO reference seed found at %s — mapper runs "
                "in NEEDS_REVIEW mode and will NOT emit numeric NCO codes.",
                self.reference_path,
            )

    def _load_csv(self, path: str) -> None:
        import csv

        with open(path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if not (row.get("nco_code") or "").strip():
                    continue
                code = row["nco_code"].strip()
                title = (row.get("occupation_title") or "").strip()
                if not title:
                    continue
                entry: Dict[str, object] = {
                    "nco_code": code,
                    "occupation_title": title,
                    "division": (row.get("division") or "").strip(),
                    "group_name": (row.get("group_name") or "").strip(),
                    # authoritative only if the seed declares an authoritative source
                    "source_reference": (row.get("source_reference") or "").strip(),
                    "is_authoritative": (row.get("authoritative") or "").strip().lower() in ("true", "1", "yes"),
                }
                self._reference.append(entry)
        logger.info("Loaded %d NCO reference entries from %s", len(self._reference), path)

    # -- Core scoring ----------------------------------------------------
    def _score(self, entry: Dict[str, object], title_tokens: set, skills_tokens: set) -> float:
        ref_tokens = _tokens(_norm(str(entry.get("occupation_title"))))
        title_sim = _jaccard(title_tokens, ref_tokens)
        skills_sim = 0.0
        if skills_tokens and entry.get("group_name"):
            skills_sim = _jaccard(skills_tokens, _tokens(_norm(str(entry.get("group_name")))))
        return TITLE_WEIGHT * title_sim + SKILLS_WEIGHT * skills_sim

    def map_title(
        self,
        title: Optional[str],
        skills: Optional[str] = None,
        canonical_occupation_id: Optional[str] = None,
    ) -> NCOMappingResult:
        """Map a job/trade title (optionally with skills) to an NCO entry.

        Args:
            title: occupation title string.
            skills: optional skill keywords used for the 30% scoring component.
            canonical_occupation_id: optional canonical occupation to constrain
                the search (e.g. OCC-BEAUTY-01).

        Returns:
            NCOMappingResult. nco_code is None unless the reference table is
            authoritative; verification_status reflects evidence quality.
        """
        if not title:
            return NCOMappingResult(method="NONE", verification_status="NEEDS_REVIEW")

        title_tokens = _tokens(_norm(title))
        skills_tokens = _tokens(_norm(skills))

        candidates = self._reference
        if canonical_occupation_id:
            occ = self._canonical.get(canonical_occupation_id)
            if occ:
                scope_tokens = _tokens(
                    _norm(occ.get("canonical_occupation_name"))
                    + " " + " ".join(occ.get("aliases") or [])
                    + " " + _norm(occ.get("source_reference"))
                )
                filtered = []
                for entry in candidates:
                    ref_tokens = _tokens(_norm(str(entry.get("occupation_title")))
                                         + " " + _norm(str(entry.get("group_name"))))
                    if ref_tokens & scope_tokens:
                        filtered.append(entry)
                if filtered:
                    candidates = filtered

        if not candidates:
            return NCOMappingResult(
                canonical_occupation_id=canonical_occupation_id,
                method="NO_REFERENCE",
                verification_status="NEEDS_REVIEW",
            )

        best: Optional[Dict[str, object]] = None
        best_score = 0.0
        for entry in candidates:
            score = self._score(entry, title_tokens, skills_tokens)
            if score > best_score:
                best = entry
                best_score = score

        if best is None or best_score < MIN_CONFIDENCE:
            return NCOMappingResult(
                canonical_occupation_id=canonical_occupation_id,
                method="LOW_CONFIDENCE",
                verification_status="NEEDS_REVIEW",
                confidence=round(best_score, 4) if best else 0.0,
                matched_on=title,
            )

        is_authoritative = bool(best.get("is_authoritative"))
        default_canonical = None
        canonical_name = None
        default_source = ""
        if canonical_occupation_id:
            default_canonical = canonical_occupation_id
            occ = self._canonical.get(canonical_occupation_id)
            if occ:
                canonical_name = occ.get("canonical_occupation_name")
                default_source = f"{occ.get('name','')}: {occ.get('source_reference','')}"

        return NCOMappingResult(
            canonical_occupation_id=default_canonical,
            canonical_occupation_name=canonical_name,
            nco_code=str(best.get("nco_code")) if is_authoritative else None,
            nco_title=str(best.get("occupation_title")),
            nco_division=str(best.get("division")) or None,
            nco_group=str(best.get("group_name")) or None,
            confidence=round(best_score, 4),
            method="TOKEN_SIMILARITY",
            verification_status="VERIFIED" if is_authoritative else "NEEDS_REVIEW",
            matched_on=title,
            source_reference=default_source or str(best.get("source_reference")) or None,
        )

    def crosswalk_canonical_occupations(self) -> List[Dict[str, Optional[str]]]:
        """Best-effort NCO crosswalk for every canonical occupation."""
        results: List[Dict[str, Optional[str]]] = []
        for occ_id in self._canonical:
            occ = self._canonical[occ_id]
            res = self.map_title(
                occ.get("canonical_occupation_name"),
                skills=occ.get("sector"),
                canonical_occupation_id=occ_id,
            )
            results.append(res.as_dict())
        return results