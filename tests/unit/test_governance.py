"""Tests for Source Governance — Policy, Rate Limiter, Health Tracker."""
import pytest
from datetime import datetime, timedelta


def test_authorization_status_values():
    from core.governance.policy import AuthorizationStatus
    values = {s.value for s in AuthorizationStatus}
    assert "AUTHORIZED_API" in values
    assert "NOT_PERMITTED" in values
    assert "UNKNOWN" in values
    assert len(values) == 9


def test_robots_status_values():
    from core.governance.policy import RobotsStatus
    values = {s.value for s in RobotsStatus}
    assert "ALLOWED" in values
    assert "DISALLOWED" in values


def test_source_policy_validate_eligible():
    from core.governance.policy import SourcePolicy, AuthorizationStatus, RobotsStatus
    sp = SourcePolicy(
        source_id="test-source",
        source_name="Test Source",
        base_url="https://example.com",
        authorization_status=AuthorizationStatus.AUTHORIZED_API,
        robots_status=RobotsStatus.ALLOWED,
        enabled=True,
        api_available=True,
    )
    result = sp.validate_ingestion_eligibility()
    assert result["eligible"] is True
    assert result["action"] == "PROCEED"


def test_source_policy_disabled_rejects():
    from core.governance.policy import SourcePolicy, AuthorizationStatus
    sp = SourcePolicy(
        source_id="disabled-source",
        source_name="Disabled",
        authorization_status=AuthorizationStatus.AUTHORIZED_API,
        enabled=False,
    )
    result = sp.validate_ingestion_eligibility()
    assert result["eligible"] is False
    assert "disabled" in result["reason"].lower()
    assert result["action"] == "HALT"


def test_source_policy_blocked_robots_rejects():
    from core.governance.policy import SourcePolicy, RobotsStatus, AuthorizationStatus
    sp = SourcePolicy(
        source_id="blocked-source",
        source_name="Blocked",
        authorization_status=AuthorizationStatus.AUTHORIZED_API,
        robots_status=RobotsStatus.DISALLOWED,
        enabled=True,
        api_available=True,
    )
    result = sp.validate_ingestion_eligibility()
    assert result["eligible"] is False
    assert result["action"] == "RESPECT_ROBOTS"


def test_source_policy_not_permitted_rejects():
    from core.governance.policy import SourcePolicy, RobotsStatus, AuthorizationStatus
    sp = SourcePolicy(
        source_id="unauth-source",
        source_name="Unauth",
        authorization_status=AuthorizationStatus.NOT_PERMITTED,
        robots_status=RobotsStatus.ALLOWED,
        enabled=True,
        api_available=True,
    )
    result = sp.validate_ingestion_eligibility()
    assert result["eligible"] is False
    assert result["action"] == "REJECT"


def test_policy_enforcer_verify_raises():
    from core.governance.policy import SourcePolicy, AuthorizationStatus, PolicyEnforcer
    from core.governance.policy import PolicyViolationException
    sp = SourcePolicy(
        source_id="bad-source",
        source_name="Bad",
        authorization_status=AuthorizationStatus.NOT_PERMITTED,
        enabled=True,
    )
    with pytest.raises(PolicyViolationException):
        PolicyEnforcer.verify(sp)


def test_rate_limiter_basic():
    from core.governance.rate_limiter import DomainRateLimiter
    limiter = DomainRateLimiter()
    # Fresh bucket starts full; first acquire should succeed immediately
    assert limiter.acquire("example.com", rate_per_minute=60) is True
    assert limiter.acquire("example.com", rate_per_minute=60) is True


def test_rate_limiter_separate_domains():
    from core.governance.rate_limiter import DomainRateLimiter
    limiter = DomainRateLimiter()
    assert limiter.acquire("a.com") is True
    assert limiter.acquire("b.com") is True
    assert limiter.acquire("a.com") is True
    assert limiter.acquire("b.com") is True
    status = limiter.get_status()
    assert set(status.keys()) == {"a.com", "b.com"}


def test_rate_limiter_backoff_on_429():
    from core.governance.rate_limiter import DomainRateLimiter
    limiter = DomainRateLimiter()
    limiter.acquire("x.com")
    limiter.record_response("x.com", 429)
    status = limiter.get_status()["x.com"]
    assert status["backoff_seconds"] == 2.0
    assert status["consecutive_errors"] == 1


def test_health_tracker_record_crawl_result():
    from unittest.mock import MagicMock
    from core.governance.health import SourceHealthTracker
    mock_session = MagicMock()
    mock_session.query.return_value.filter.return_value.first.return_value = MagicMock(
        source_id="test-src"
    )
    result = SourceHealthTracker.record_crawl_result(
        db=mock_session,
        source_id="test-src",
        status="ONLINE",
        response_time_ms=120.5,
        jobs_found=10,
        jobs_new=5,
    )
    assert result["source_id"] == "test-src"
    assert result["status"] == "ONLINE"
    assert result["response_time_ms"] == 120.5
    assert result["jobs_found"] == 10
    assert result["last_success"] is not None
    assert result["last_failure"] is None


def test_health_tracker_failure_status():
    from unittest.mock import MagicMock
    from core.governance.health import SourceHealthTracker
    mock_session = MagicMock()
    result = SourceHealthTracker.record_crawl_result(
        db=mock_session,
        source_id="test-src",
        status="OFFLINE",
        response_time_ms=5000.0,
        error_message="Connection refused",
    )
    assert result["status"] == "OFFLINE"
    assert result["last_failure"] is not None
    assert result["last_success"] is None