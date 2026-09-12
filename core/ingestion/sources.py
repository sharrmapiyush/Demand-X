"""Source connector interface for raw ingestion.

Adapted from reference project's sources/base.py ABC.

Improvements over reference:
- validate_job() returns typed errors (no silent fabrication).
- generate_content_hash() is SHA256 over the canonical raw JSON payload.
- Connectors never fall back to synthetic row generation.
"""

import hashlib
import json
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from core.governance.policy import SourcePolicy


class SourceRecordError(Exception):
    """Raised when a raw record fails validation."""


class SourceConnector(ABC):
    """Interface every Demand-X source adapter implements.

    Lifecycle (driven by RawIngestionOrchestrator):
      1. pre_ingestion_check()   — readiness / governance preflight
      2. fetch_raw()             — retrieve actual raw evidence
      3. normalize_job()         — one raw row → normalized record dict
      4. validate_job()          — deterministic validation
      5. generate_content_hash() — SHA256 dedup digest
    """

    policy: Optional[SourcePolicy] = None

    @abstractmethod
    def source_id(self) -> str:
        """Return the Source Registry identifier for this connector."""

    @abstractmethod
    def fetch_raw(self, **kwargs) -> List[Dict[str, Any]]:
        """Retrieve raw records from the actual source.

        MUST return only real evidence. Returning an empty list is valid;
        fabricated rows are not.
        """

    def pre_ingestion_check(self) -> List[str]:
        """Return a list of problems that block ingestion. Empty = ready."""
        problems = []
        if self.policy is None:
            problems.append("No SourcePolicy attached; cannot govern ingestion.")
        return problems

    @abstractmethod
    def normalize_job(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        """Map one raw payload into a normalized record dict."""

    def validate_job(self, record: Dict[str, Any]) -> List[str]:
        """Determine whether a normalized record is admissible.

        Returns a list of validation errors (empty = valid).
        """
        errors = []
        if not record.get("job_title"):
            errors.append("missing job_title")
        if not record.get("location_text"):
            errors.append("missing location_text")
        return errors

    @staticmethod
    def generate_content_hash(raw: Dict[str, Any]) -> str:
        """Deterministic SHA256 over the canonical raw payload.

        Used for staging-time deduplication (reference pattern), layered
        alongside the persisted record_identity_hash used by the DB.
        """
        _canonical = json.dumps(
            raw,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        return hashlib.sha256(_canonical.encode("utf-8")).hexdigest()