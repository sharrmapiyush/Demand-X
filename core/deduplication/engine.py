"""Near-duplicate detection engine.

Implements:
- SimHash: 64-bit locality-sensitive hash over token shingles.
- Hamming distance for near-duplicate comparison.
- DeduplicationEngine: canonical-key (SHA256) dedup plus SimHash
  near-duplicate/repost classification.

Examples
--------
>>> sh = SimHash()
>>> f1 = sh.fingerprint("Software Engineer - Pune")
>>> f2 = sh.fingerprint("Software Engineer  - Pune")
>>> sh.hamming_distance(f1, f2)
0
"""

import hashlib
import logging
import re
from enum import Enum
from typing import Dict, List, Optional, Sequence, Tuple

logger = logging.getLogger(__name__)

# Maximum Hamming distance at which two fingerprints are near-duplicates.
NEAR_DUPLICATE_HAMMING = 3


class DuplicateStatus(str, Enum):
    """Classification of a candidate observation against existing records."""
    EXACT_MATCH = "EXACT_MATCH"        # identical canonical key already seen
    NEAR_DUPLICATE = "NEAR_DUPLICATE"  # same underlying opportunity, alt repr
    REPOST = "REPOST"                  # same posting announced again
    DISTINCT = "DISTINCT"              # genuinely different observation


class SimHash:
    """64-bit locality-sensitive hash for similarity estimation."""

    TOKEN_RE = re.compile(r"[a-z0-9]+")

    def __init__(self, fingerprint_bits: int = 64, shingle_size: int = 3):
        self.fingerprint_bits = fingerprint_bits
        self.shingle_size = shingle_size

    def _tokenize(self, text: str) -> List[str]:
        return self.TOKEN_RE.findall(text.lower())

    def _shingles(self, tokens: List[str]) -> List[Tuple[str, ...]]:
        if len(tokens) < self.shingle_size:
            return [tuple(tokens)]
        return [
            tuple(tokens[i : i + self.shingle_size])
            for i in range(len(tokens) - self.shingle_size + 1)
        ]

    @staticmethod
    def _hash64(value: str) -> int:
        """Deterministic 64-bit digest of a string."""
        return int.from_bytes(hashlib.md5(value.encode("utf-8")).digest()[:8], "big")

    def fingerprint(self, text: str) -> int:
        """Compute the SimHash fingerprint of a text string."""
        if not text:
            return 0
        tokens = self._tokenize(text)
        shingles = self._shingles(tokens)
        if not shingles:
            return 0

        vector = [0] * self.fingerprint_bits
        for shingle in shingles:
            h = self._hash64("|".join(shingle))
            for bit in range(self.fingerprint_bits):
                if (h >> bit) & 1:
                    vector[bit] += 1
                else:
                    vector[bit] -= 1

        fingerprint = 0
        for bit in range(self.fingerprint_bits):
            if vector[bit] > 0:
                fingerprint |= 1 << bit
        return fingerprint & ((1 << self.fingerprint_bits) - 1)

    def hamming_distance(self, a: int, b: int) -> int:
        """Number of differing bits between two fingerprints."""
        return (a ^ b).bit_count()

    def are_near_duplicates(self, a: int, b: int, threshold: int = NEAR_DUPLICATE_HAMMING) -> bool:
        return self.hamming_distance(a, b) <= threshold


def canonical_key(record: Dict[str, object], fields: Sequence[str]) -> str:
    """Deterministic SHA256 over selected normalized fields."""
    parts: List[str] = []
    for field in fields:
        value = record.get(field)
        if value is None:
            parts.append(field + "::")
        else:
            parts.append(f"{field}::{str(value).strip().lower()}")
    payload = "\x1f".join(parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class DeduplicationEngine:
    """Detects exact, near-duplicate, and repost observations.

    Not copied from reference:
    - No monthly-bucket key; reposts are matched against the full history,
      so a repost cannot inflate demand counts regardless of month.
    - `near_duplicate` must be confirmed against an existing canonical record
      before the producing pipeline may skip/merge; never deletes DB rows.
    """

    def __init__(self, sh: Optional[SimHash] = None):
        self.sh = sh or SimHash()
        self._known_canonical_keys: Dict[str, str] = {}   # key -> record_id
        self._known_fingerprints: Dict[int, List[str]] = {}  # fp -> [record_id]

    def seed(self, record_id: str, canonical: str, fingerprint: int) -> None:
        """Register an existing observation for future comparisons."""
        self._known_canonical_keys[canonical] = record_id
        self._known_fingerprints.setdefault(fingerprint, []).append(record_id)

    def evaluate_duplicate_status(
        self,
        canonical: str,
        fingerprint: int,
        posting_token: Optional[str] = None,
    ) -> DuplicateStatus:
        """Classify a candidate against everything already seeded."""
        if canonical in self._known_canonical_keys:
            return DuplicateStatus.EXACT_MATCH

        # Look for near-duplicates among known fingerprints.  A hash map of
        # fingerprints only catches fingerprints stored at *exactly* the same
        # value; for real near-duplicate detection we compare within a window.
        found = self._find_near_duplicate(fingerprint)
        if found is not None:
            if posting_token is not None and found == posting_token:
                return DuplicateStatus.REPOST
            return DuplicateStatus.NEAR_DUPLICATE

        return DuplicateStatus.DISTINCT

    def _find_near_duplicate(self, fingerprint: int, threshold: int = NEAR_DUPLICATE_HAMMING) -> Optional[str]:
        """Return the record_id of a stored fingerprint within threshold, if any."""
        # Exact fingerprint bucket first (O(1)).
        exact = self._known_fingerprints.get(fingerprint)
        if exact:
            return exact[0]
        # Otherwise scan fallback. In a production scale-out this can be a
        # bucketed index; MVP holds ordered signatures instead.
        for fp, record_ids in self._known_fingerprints.items():
            if self.sh.are_near_duplicates(fingerprint, fp, threshold):
                return record_ids[0]
        return None

    def record(self, record_id: str, canonical: str, fingerprint: int) -> None:
        """Add the candidate to the known set (idempotent)."""
        self.seed(record_id, canonical, fingerprint)

    def analyze(
        self,
        record: Dict[str, object],
        record_id: str,
        key_fields: Sequence[str],
    ) -> Dict[str, object]:
        """Full pipeline for one record: key, fingerprint, status decision."""
        canonical = canonical_key(record, key_fields)
        fp = self.sh.fingerprint(
            " ".join(str(record.get(f, "") or "") for f in key_fields)
        )
        status = self.evaluate_duplicate_status(canonical, fp)
        self.record(record_id, canonical, fp)
        return {
            "record_id": record_id,
            "canonical_key": canonical,
            "fingerprint": fp,
            "status": status.value,
        }