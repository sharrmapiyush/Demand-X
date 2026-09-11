from pydantic import BaseModel, Field
from typing import Optional, List

class LocationNormalizationResult(BaseModel):
    raw_location: Optional[str] = None
    country: Optional[str] = "India"
    state: Optional[str] = None
    district: Optional[str] = None
    locality: Optional[str] = None
    location_scope: str = "UNKNOWN" # SINGLE_LOCATION, MULTI_LOCATION, UNKNOWN
    location_confidence: str = "NONE" # HIGH, MEDIUM, LOW, NONE
    matched_locations: List[str] = Field(default_factory=list)
    normalization_method: str = "DETERMINISTIC_RULE_V1"

    # New fields for evidence level and Pune analysis
    location_evidence_level: str = "UNKNOWN" # EXACT_SINGLE, MULTI_EXPLICIT, CITY_MENTION, AMBIGUOUS, UNKNOWN
    has_pune_evidence: bool = False
    pune_exclusivity: str = "UNKNOWN" # EXCLUSIVE, SHARED, MENTIONED, UNKNOWN
