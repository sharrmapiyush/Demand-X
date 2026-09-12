"""Source Health Tracking & Telemetry.

Adapted from reference project's crawlers/health.py.
Records crawl outcomes per source: status, response time, jobs found, error counts.
Integrates with the existing Source model rather than creating a separate table.

Not copied from reference:
- Does NOT create a separate SourceHealth table (adapted to Source model fields).
- Does NOT impersonate government agencies.
- Statuses: ONLINE, DEGRADED, OFFLINE, BLOCKED — no fabrication of health metrics.
"""

from datetime import datetime
from typing import Dict, Any, Optional
import logging
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class SourceHealthTracker:
    """Records and queries health telemetry across all data sources.

    Uses the existing Source model's fields (last_fetched_at, last_verified_at,
    reliability_notes) rather than creating a separate health table.
    """

    @staticmethod
    def record_crawl_result(
        db: Optional[Session],
        source_id: str,
        status: str,              # ONLINE, DEGRADED, OFFLINE, BLOCKED
        response_time_ms: float,
        jobs_found: int = 0,
        jobs_new: int = 0,
        jobs_updated: int = 0,
        error_message: Optional[str] = None,
        robots_status: str = "ALLOWED",
        authorization_status: str = "AUTHORIZED_API",
    ) -> Dict[str, Any]:
        """Record crawl outcome. Returns health record dict."""
        now = datetime.utcnow()
        is_success = status in ("ONLINE", "DEGRADED")

        health_data: Dict[str, Any] = {
            "source_id": source_id,
            "status": status,
            "last_success": now.isoformat() if is_success else None,
            "last_failure": None if is_success else now.isoformat(),
            "response_time_ms": round(response_time_ms, 2),
            "jobs_found": jobs_found,
            "jobs_new": jobs_new,
            "jobs_updated": jobs_updated,
            "robots_status": robots_status,
            "authorization_status": authorization_status,
        }

        if db:
            try:
                from core.models.source import Source

                src = db.query(Source).filter(Source.source_id == source_id).first()
                if src:
                    if is_success:
                        src.last_fetched_at = now
                        src.reliability_notes = (
                            f"Last OK: {now.isoformat()}, "
                            f"found={jobs_found}, new={jobs_new}, "
                            f"latency={round(response_time_ms, 1)}ms"
                        )
                    else:
                        src.reliability_notes = (
                            f"Last FAIL: {now.isoformat()}, "
                            f"status={status}, error={error_message or 'unknown'}"
                        )
                    db.commit()
                else:
                    logger.warning("Source %s not found in registry; health not persisted.", source_id)
            except Exception as e:
                db.rollback()
                logger.error("Failed to persist health record for %s: %s", source_id, e)

        return health_data
