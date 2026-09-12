"""Semantic search abstraction — not an MVP hard dependency.

Adapted from reference project's placeholder semantic search.

Key constraint applied (P14): Semantic search is NEVER a hard dependency for MVP.
This module provides:
1. The provider interface (for future vector search integration).
2. A no-op stub that explicitly returns "not available" — never pretending
   vector search is present when it isn't.
3. An optional keyword-based fallback over persisted observations (not
   vector-based, but provides a deterministic retrieval layer).

The reference project's semantic search was a placeholder using embeddings
that were never actually computed. This module makes the absence explicit
rather than pretending capability exists.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class SemanticSearchProvider(ABC):
    """Provider interface for semantic search.

    Implementations must explicitly declare availability.
    """

    @abstractmethod
    def is_available(self) -> bool:
        """Return True only when a working vector index is connected."""

    @abstractmethod
    def search(
        self,
        query: str,
        *,
        limit: int = 10,
        district: Optional[str] = None,
        sector: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Search for semantically similar observations.

        Returns a list of dicts with: record_type, record_id, title,
        score (0-1.0), snippet. Empty list when not available.
        """


class UnavailableSearchProvider(SemanticSearchProvider):
    """No-op stub that declares itself unavailable.

    This is the DEFAULT for MVP. Vector search integration is DEFERRED.
    """

    def is_available(self) -> bool:
        return False

    def search(
        self,
        query: str,
        *,
        limit: int = 10,
        district: Optional[str] = None,
        sector: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        return []


class KeywordSearchFallback(SemanticSearchProvider):
    """Keyword-based fallback over persisted observations.

    Not true semantic search, but provides deterministic retrieval
    when no vector index is available. Marked as is_available=False
    so callers know this is a non-semantic keyword fallback.
    """

    def __init__(self, db_url: str):
        self.db_url = db_url

    def is_available(self) -> bool:
        return bool(self.db_url)

    def search(
        self,
        query: str,
        *,
        limit: int = 10,
        district: Optional[str] = None,
        sector: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        if not self.db_url:
            return []

        try:
            from sqlalchemy import create_engine, or_
            from sqlalchemy.orm import sessionmaker
            from core.models.observation import JobPosting

            engine = create_engine(self.db_url)
            SessionLocal = sessionmaker(bind=engine)
            session = SessionLocal()

            import re
            tokens = [t for t in re.findall(r"[a-z0-9]{3,}", query.lower()) if t]
            if not tokens:
                return []

            filters = []
            if district:
                filters.append(JobPosting.district == district)
            if sector:
                filters.append(JobPosting.sector == sector)

            jobs = session.query(JobPosting).filter(*filters).limit(limit * 3).all()
            results: List[Dict[str, Any]] = []
            for job in jobs:
                searchable = f"{job.job_title or ''} {job.description or ''}".lower()
                if any(t in searchable for t in tokens):
                    results.append({
                        "record_type": "JOB_POSTING",
                        "record_id": str(job.id),
                        "title": job.job_title or "",
                        "score": 0.5,  # keyword match — not a true semantic score
                        "snippet": (job.description or "")[:200],
                    })
                if len(results) >= limit:
                    break
            return results
        except Exception:
            return []