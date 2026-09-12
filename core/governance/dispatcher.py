"""Crawl Dispatcher — Governance-gated source execution.

Adapted from reference project's crawlers/dispatcher.py.
Coordinates the execution of source connectors with pre-flight policy
verification, rate limiting, fault isolation, and health recording.

Not copied from reference:
- No MahaSkill branding.
- Does NOT execute actual crawlers (no real sources in MVP).
- Acts as the dispatch framework that future source adapters plug into.
"""

import time
import logging
from typing import Dict, Any, List, Optional, Callable
from sqlalchemy.orm import Session

from core.governance.policy import PolicyEnforcer, PolicyViolationException, SourcePolicy
from core.governance.rate_limiter import RATE_LIMITER
from core.governance.health import SourceHealthTracker

logger = logging.getLogger(__name__)


class CrawlDispatcher:
    """Executes source ingestion with strict governance and isolation."""

    def __init__(self, db: Optional[Session] = None):
        self.db = db
        self._registered_sources: Dict[str, Any] = {}

    def register_source(self, source_id: str, connector: Any):
        """Register a source connector instance."""
        self._registered_sources[source_id] = connector

    def register_callable(self, source_id: str, policy: SourcePolicy, fetch_fn: Callable):
        """Register a simple callable source (no full connector needed).

        fetch_fn should be () -> List[Dict[str, Any]]
        """
        self._registered_sources[source_id] = {"policy": policy, "fetch_fn": fetch_fn}

    def dispatch_source(self, source_id: str, **kwargs) -> Dict[str, Any]:
        """Execute a single source with governance and isolation."""
        start_time = time.time()
        connector = self._registered_sources.get(source_id)
        if not connector:
            return {
                "source_id": source_id,
                "status": "NOT_FOUND",
                "error": f"No connector registered for source_id '{source_id}'",
                "jobs_found": 0,
                "jobs_new": 0,
            }

        # Get policy
        if isinstance(connector, dict):
            policy = connector.get("policy")
        else:
            policy = getattr(connector, "policy", None)

        if not policy:
            return {
                "source_id": source_id,
                "status": "UNGOVERNED",
                "error": f"Connector '{source_id}' has no SourcePolicy attached.",
                "jobs_found": 0,
            }

        # 1. Pre-flight governance check
        try:
            PolicyEnforcer.verify(policy)
        except PolicyViolationException as pve:
            latency = (time.time() - start_time) * 1000
            SourceHealthTracker.record_crawl_result(
                db=self.db,
                source_id=source_id,
                status="BLOCKED",
                response_time_ms=latency,
                error_message=str(pve),
                robots_status=policy.robots_status.value,
                authorization_status=policy.authorization_status.value,
            )
            return {
                "source_id": source_id,
                "status": "BLOCKED_BY_POLICY",
                "reason": str(pve),
                "authorization_status": policy.authorization_status.value,
            }

        # 2. Rate limiter acquisition
        acquired = RATE_LIMITER.acquire(source_id, rate_per_minute=policy.rate_limit)
        if not acquired:
            latency = (time.time() - start_time) * 1000
            return {
                "source_id": source_id,
                "status": "RATE_LIMITED",
                "error": "Rate limiter acquisition timed out.",
            }

        # 3. Isolated execution
        try:
            if isinstance(connector, dict) and "fetch_fn" in connector:
                raw_records = connector["fetch_fn"](**kwargs)
            else:
                raw_records = connector.fetch_raw(**kwargs)

            latency = (time.time() - start_time) * 1000
            RATE_LIMITER.record_response(source_id, 200)

            SourceHealthTracker.record_crawl_result(
                db=self.db,
                source_id=source_id,
                status="ONLINE",
                response_time_ms=latency,
                jobs_found=len(raw_records),
                jobs_new=len(raw_records),
                robots_status=policy.robots_status.value,
                authorization_status=policy.authorization_status.value,
            )

            return {
                "source_id": source_id,
                "status": "SUCCESS",
                "jobs_found": len(raw_records),
                "duration_ms": round(latency, 2),
                "records": raw_records,
            }

        except Exception as e:
            latency = (time.time() - start_time) * 1000
            RATE_LIMITER.record_response(source_id, 500)
            logger.error("Error executing source %s: %s", source_id, e)

            SourceHealthTracker.record_crawl_result(
                db=self.db,
                source_id=source_id,
                status="DEGRADED",
                response_time_ms=latency,
                jobs_found=0,
                error_message=str(e),
                robots_status=policy.robots_status.value,
                authorization_status=policy.authorization_status.value,
            )

            return {
                "source_id": source_id,
                "status": "ERROR",
                "error": str(e),
                "duration_ms": round(latency, 2),
            }

    def dispatch_all(self, source_ids: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Dispatch all registered sources (or a subset)."""
        targets = source_ids or list(self._registered_sources.keys())
        results = []
        for sid in targets:
            result = self.dispatch_source(sid)
            results.append(result)
        return results
