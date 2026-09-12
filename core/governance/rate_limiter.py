"""Domain Rate Limiter — Token-bucket rate limiting per source/domain.

Adapted from reference project's crawlers/rate_limiter.py.
Thread-safe, with exponential backoff on 429/503 responses.

Not copied from reference:
- No MahaSkill branding in logs.
- Backoff ceiling is 120s (not 60s) for production resilience.
"""

import time
import logging
from typing import Dict
from dataclasses import dataclass, field
import threading

logger = logging.getLogger(__name__)


@dataclass
class DomainBucket:
    """Token bucket for a single source/domain."""
    rate_per_minute: int = 30
    capacity: float = 30.0
    tokens: float = 30.0
    last_updated: float = field(default_factory=time.time)
    backoff_seconds: float = 0.0
    consecutive_errors: int = 0
    lock: threading.Lock = field(default_factory=threading.Lock)


class DomainRateLimiter:
    """Thread-safe per-source rate limiter using token-bucket algorithm."""

    def __init__(self):
        self._buckets: Dict[str, DomainBucket] = {}
        self._global_lock = threading.Lock()

    def get_or_create_bucket(self, source_id: str, rate_per_minute: int = 30) -> DomainBucket:
        with self._global_lock:
            if source_id not in self._buckets:
                cap = float(max(1, rate_per_minute))
                self._buckets[source_id] = DomainBucket(
                    rate_per_minute=rate_per_minute,
                    capacity=cap,
                    tokens=cap,
                    last_updated=time.time(),
                )
            return self._buckets[source_id]

    def acquire(self, source_id: str, rate_per_minute: int = 30, max_wait_seconds: float = 30.0) -> bool:
        """Block until a token is available or timeout."""
        bucket = self.get_or_create_bucket(source_id, rate_per_minute)
        start_wait = time.time()

        while time.time() - start_wait < max_wait_seconds:
            with bucket.lock:
                now = time.time()

                # Check if currently in exponential backoff
                if bucket.backoff_seconds > 0:
                    time_remaining = bucket.backoff_seconds - (now - bucket.last_updated)
                    if time_remaining > 0:
                        # Release lock, sleep briefly, retry
                        pass
                    else:
                        bucket.backoff_seconds = 0.0

                # Replenish tokens
                elapsed = now - bucket.last_updated
                bucket.last_updated = now
                fill_rate = bucket.rate_per_minute / 60.0  # tokens per second
                bucket.tokens = min(bucket.capacity, bucket.tokens + (elapsed * fill_rate))

                if bucket.tokens >= 1.0 and bucket.backoff_seconds <= 0:
                    bucket.tokens -= 1.0
                    return True

            time.sleep(0.1)

        logger.warning("Rate limiter timeout for source: %s", source_id)
        return False

    def record_response(self, source_id: str, status_code: int):
        """Adjust rate limiting based on HTTP response code."""
        if source_id not in self._buckets:
            return

        bucket = self._buckets[source_id]
        with bucket.lock:
            if status_code in (429, 503):
                bucket.consecutive_errors += 1
                # Exponential backoff: 2s, 4s, 8s, ... up to 120s
                bucket.backoff_seconds = min(120.0, 2.0 ** bucket.consecutive_errors)
                logger.warning(
                    "Backing off source %s for %.1fs due to HTTP %d (consecutive: %d)",
                    source_id, bucket.backoff_seconds, status_code, bucket.consecutive_errors,
                )
            elif status_code == 200:
                if bucket.consecutive_errors > 0:
                    bucket.consecutive_errors = max(0, bucket.consecutive_errors - 1)
                bucket.backoff_seconds = 0.0

    def reset(self, source_id: str):
        with self._global_lock:
            self._buckets.pop(source_id, None)

    def get_status(self) -> Dict[str, Dict[str, Any]]:
        """Return current state of all buckets (for health monitoring)."""
        status = {}
        for sid, bucket in self._buckets.items():
            status[sid] = {
                "tokens": round(bucket.tokens, 2),
                "capacity": bucket.capacity,
                "backoff_seconds": round(bucket.backoff_seconds, 2),
                "consecutive_errors": bucket.consecutive_errors,
            }
        return status


# Global rate limiter instance
RATE_LIMITER = DomainRateLimiter()
