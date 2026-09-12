"""Crawl Scheduler — Determines which sources are due for processing.

Adapted from reference project's crawlers/scheduler.py.
Operates only on actual registered sources, never fabricates observations
when a source returns nothing.

Not copied from reference:
- No MahaSkill branding.
- Does NOT trigger any actual crawl (framework only).
- Never fabricates observations when source returns nothing.
"""

from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

# Frequency → minutes mapping
FREQUENCY_MINUTES = {
    "hourly": 60,
    "2h": 120,
    "4h": 240,
    "6h": 360,
    "12h": 720,
    "daily": 1440,
    "weekly": 10080,
}


class CrawlScheduler:
    """Manages scheduling calculation and dispatch timings for all configured sources."""

    @staticmethod
    def calculate_next_run(frequency: str, from_time: Optional[datetime] = None) -> datetime:
        """Calculate the next run time based on frequency string."""
        base = from_time or datetime.utcnow()
        minutes = FREQUENCY_MINUTES.get(frequency.lower(), 60)
        return base + timedelta(minutes=minutes)

    @staticmethod
    def is_source_due(
        last_run: Optional[datetime],
        next_run: Optional[datetime],
        frequency: str = "hourly",
        current_time: Optional[datetime] = None,
    ) -> bool:
        """Evaluate whether a source is due for processing."""
        now = current_time or datetime.utcnow()

        # If never run or next_run is not set, it's due
        if last_run is None or next_run is None:
            return True

        return now >= next_run

    @classmethod
    def get_due_sources(
        cls,
        sources: List[Dict[str, Any]],
        current_time: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """Filter sources to those that are enabled, permitted, and due.

        Each source dict must have:
            enabled, authorization_status, last_successful_run,
            next_scheduled_run, crawl_frequency, source_priority
        """
        now = current_time or datetime.utcnow()
        due_sources = []

        for s in sources:
            if not s.get("enabled", True):
                continue
            if s.get("authorization_status") in ("REQUIRES_PERMISSION", "NOT_PERMITTED"):
                continue

            last_run = s.get("last_successful_run")
            next_run = s.get("next_scheduled_run")
            freq = s.get("crawl_frequency", "hourly")

            if cls.is_source_due(last_run, next_run, freq, now):
                due_sources.append(s)

        # Sort by source_priority (1=Highest first)
        due_sources.sort(key=lambda x: x.get("source_priority", 10))
        return due_sources
