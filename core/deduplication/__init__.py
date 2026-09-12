"""Deduplication — near-duplicate and repost detection for job observations.

Adapted from reference project's deduplication/ package.

Reference flaws NOT copied:
- The reference buckets duplicates into monthly keys, so a genuine repost in a
  different month is treated as DISTINCT and re-counted. Demand-X treats
  reposts as the SAME underlying opportunity (they must NOT inflate demand).
- No reference to a hardcoded DEDUP config wholesale.
"""

from core.deduplication.engine import (
    SimHash,
    DeduplicationEngine,
    DuplicateStatus,
)

__all__ = ["SimHash", "DeduplicationEngine", "DuplicateStatus"]