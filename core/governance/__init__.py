"""Source Governance — Policy, Rate Limiting, Health, Dispatch, Scheduling.

Adapted from reference project's crawlers/ package. Provides the governance
infrastructure that gates all data ingestion in Demand-X.
"""

from core.governance.policy import (
    AuthorizationStatus,
    RobotsStatus,
    PolicyViolationException,
    SourcePolicy,
    PolicyEnforcer,
)
from core.governance.rate_limiter import DomainRateLimiter, RATE_LIMITER
from core.governance.health import SourceHealthTracker
from core.governance.dispatcher import CrawlDispatcher
from core.governance.scheduler import CrawlScheduler, FREQUENCY_MINUTES

__all__ = [
    "AuthorizationStatus",
    "RobotsStatus",
    "PolicyViolationException",
    "SourcePolicy",
    "PolicyEnforcer",
    "DomainRateLimiter",
    "RATE_LIMITER",
    "SourceHealthTracker",
    "CrawlDispatcher",
    "CrawlScheduler",
    "FREQUENCY_MINUTES",
]
