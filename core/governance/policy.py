"""Source Policy & Governance Engine.

Adapted from reference project's crawlers/policy.py pattern. Provides
machine-readable governance records that gate all ingestion attempts.

Every source must have a valid SourcePolicy before any crawl or API call
is attempted. PolicyEnforcer.verify() raises PolicyViolationException
if governance criteria are not met.

NOT copied from reference:
- No fabricated government impersonation in headers or user-agent.
- No hardcoded permissions. All statuses must be explicitly set.
- PolicyViolationException does NOT silently succeed.
"""

from enum import Enum
from typing import Dict, Any, Optional, Set
from pydantic import BaseModel, Field
import logging

logger = logging.getLogger(__name__)


class AuthorizationStatus(str, Enum):
    """Legal authorization status of the data source."""
    AUTHORIZED_API = "AUTHORIZED_API"
    AUTHORIZED_FEED = "AUTHORIZED_FEED"
    LICENSED_DATA = "LICENSED_DATA"
    PERMITTED_PUBLIC_CRAWL = "PERMITTED_PUBLIC_CRAWL"
    USER_PROVIDED_DATA = "USER_PROVIDED_DATA"
    PARTNER_WEBHOOK = "PARTNER_WEBHOOK"
    REQUIRES_PERMISSION = "REQUIRES_PERMISSION"
    NOT_PERMITTED = "NOT_PERMITTED"
    UNKNOWN = "UNKNOWN"


class RobotsStatus(str, Enum):
    """robots.txt compliance status."""
    ALLOWED = "ALLOWED"
    DISALLOWED = "DISALLOWED"
    RESPECTED = "RESPECTED"


class PolicyViolationException(Exception):
    """Raised when a crawl attempt violates platform governance rules."""

    def __init__(self, source_id: str, reason: str, status: str):
        self.source_id = source_id
        self.reason = reason
        self.status = status
        super().__init__(f"Policy Violation [{source_id}]: {reason} (Status: {status})")


class SourcePolicy(BaseModel):
    """Machine-readable governance record for an external data source.

    This wraps the governance fields that already exist on the Source DB model
    (access_method, source_type, verification_status, enabled) and adds
    runtime crawl governance fields that are not persisted but enforced at
    dispatch time.
    """
    source_id: str
    source_name: str
    base_url: str = ""
    source_category: str = "general"   # government, company_career, ats, industry_body, gig
    source_type: str = "official_api"  # official_api, rss_feed, permitted_crawler, partner_webhook, snapshot
    access_method: str = "REST_API"    # REST_API, ATOM_FEED, PERMITTED_GET, WEBHOOK, SNAPSHOT

    authorization_status: AuthorizationStatus = AuthorizationStatus.UNKNOWN
    terms_url: Optional[str] = None
    robots_status: RobotsStatus = RobotsStatus.RESPECTED
    api_available: bool = False
    api_documentation_url: Optional[str] = None

    crawl_allowed: bool = False
    crawl_frequency: str = "hourly"    # hourly, 2h, 4h, 6h, 12h, daily, weekly
    rate_limit: int = 30               # Max requests per minute

    data_license: str = "Open Data / Fair Use"
    commercial_use_allowed: bool = True
    full_description_storage_allowed: bool = True
    source_priority: int = 1           # 1=Highest (Govt/API), 2=Company, 3=Aggregators
    enabled: bool = True

    user_agent: str = (
        "DemandX/1.0 (+https://github.com/sharrmapiyush/Demand-X; "
        "Labour-Market Intelligence Research Platform)"
    )

    # Permitted statuses where ingestion is allowed
    PERMITTED_STATUSES: Set[str] = {
        AuthorizationStatus.AUTHORIZED_API.value,
        AuthorizationStatus.AUTHORIZED_FEED.value,
        AuthorizationStatus.LICENSED_DATA.value,
        AuthorizationStatus.PERMITTED_PUBLIC_CRAWL.value,
        AuthorizationStatus.USER_PROVIDED_DATA.value,
        AuthorizationStatus.PARTNER_WEBHOOK.value,
    }

    def validate_ingestion_eligibility(self) -> Dict[str, Any]:
        """Validates if the source is permitted to be ingested."""
        if not self.enabled:
            return {
                "eligible": False,
                "reason": f"Source '{self.source_id}' is administratively disabled.",
                "action": "HALT",
            }

        if self.authorization_status.value not in self.PERMITTED_STATUSES:
            return {
                "eligible": False,
                "reason": (
                    f"Source '{self.source_id}' authorization status "
                    f"'{self.authorization_status.value}' prohibits automated ingestion."
                ),
                "action": "REJECT",
            }

        if self.robots_status == RobotsStatus.DISALLOWED:
            return {
                "eligible": False,
                "reason": f"Source '{self.source_id}' is explicitly DISALLOWED by robots.txt.",
                "action": "RESPECT_ROBOTS",
            }

        if not self.crawl_allowed and not self.api_available:
            return {
                "eligible": False,
                "reason": (
                    f"Source '{self.source_id}' has neither crawl_allowed=True "
                    f"nor api_available=True."
                ),
                "action": "DENIED",
            }

        return {
            "eligible": True,
            "reason": "Source meets all governance criteria.",
            "action": "PROCEED",
        }


class PolicyEnforcer:
    """Enforces governance rules before any source interaction."""

    @staticmethod
    def verify(policy: SourcePolicy) -> bool:
        """Verify source policy. Raises PolicyViolationException if not eligible."""
        check = policy.validate_ingestion_eligibility()
        if not check["eligible"]:
            logger.warning("GOVERNANCE REJECTION: %s -> %s", policy.source_id, check["reason"])
            raise PolicyViolationException(
                source_id=policy.source_id,
                reason=check["reason"],
                status=policy.authorization_status.value,
            )
        return True

    @staticmethod
    def get_standard_headers(policy: SourcePolicy) -> Dict[str, str]:
        """Returns compliant HTTP headers identifying the platform."""
        return {
            "User-Agent": policy.user_agent,
            "Accept": "application/json, text/html, application/xml;q=0.9",
            "Accept-Language": "en-US,en;q=0.9",
        }

    @staticmethod
    def build_policy_from_source_record(source_record: Any) -> SourcePolicy:
        """Build a SourcePolicy from an existing Source DB model instance.

        Maps the DB model's governance fields to the Pydantic policy model.
        """
        auth_status = AuthorizationStatus.UNKNOWN
        if hasattr(source_record, "verification_status"):
            vs = (source_record.verification_status or "").upper()
            if vs == "VERIFIED":
                auth_status = AuthorizationStatus.AUTHORIZED_API
            elif vs == "PERMITTED":
                auth_status = AuthorizationStatus.PERMITTED_PUBLIC_CRAWL

        access = getattr(source_record, "access_method", "SOURCE_SNAPSHOT")
        is_api = access in ("VERIFIED_API", "REST_API")
        is_snapshot = access in ("SOURCE_SNAPSHOT", "MANUAL_CURATION")

        return SourcePolicy(
            source_id=source_record.source_id,
            source_name=source_record.source_name,
            base_url=getattr(source_record, "url", ""),
            access_method=access,
            authorization_status=auth_status,
            api_available=is_api,
            crawl_allowed=not is_snapshot,
            source_priority=1 if getattr(source_record, "official_government_source", False) else 2,
            enabled=getattr(source_record, "enabled", True),
        )
