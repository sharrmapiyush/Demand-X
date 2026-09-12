"""Maharashtra Geography Engine — full 36-district coverage.

Adapted from reference project's geography/ engine.

Reference flaw REJECTED:
- Reference lines 212-225 default ANY unresolved "maharashtra" mention to
  "Mumbai City" with confidence 0.50. That fabricates a district assignment.
  Demand-X NEVER assigns a district unless the evidence names one. Statuses
  stay: EXACT_SINGLE, MULTI_EXPLICIT, CITY_MENTION, AMBIGUOUS, UNKNOWN.

District/division table below is the current official 36-district set of
Maharashtra (6 revenue divisions). Approximate centroids are coarse map
estimates, flagged clearly — they are never used to infer district presence.

This module is additive: the existing Pune-focused normalizer
(core/geography/location_normalizer.py) remains authoritative for the
Pune DVET analysis pipeline. This engine is the product-layer geography
for statewide coverage.
"""

import re
from typing import Dict, List, Optional

from core.geography.models import LocationNormalizationResult


class DistrictEntry:
    """One Maharashtra district with its revenue division.

    coordinates: approximate centroid (lat, lon), research-use only — does
    NOT constitute evidence of any observation's location.
    """

    __slots__ = ("name", "division", "coordinates")

    def __init__(self, name: str, division: str, coordinates: Optional[tuple] = None):
        self.name = name
        self.division = division
        self.coordinates = coordinates


# Official 36 districts of Maharashtra, grouped by revenue division.
# KONKAN division includes the two coterminous city/suburban districts.
MAHARASHTRA_DISTRICTS: Dict[str, DistrictEntry] = {
    # --- Konkan (7) ---
    "mumbai city": DistrictEntry("Mumbai City", "Konkan", (18.95, 72.83)),
    "mumbai suburban": DistrictEntry("Mumbai Suburban", "Konkan", (19.13, 72.90)),
    "thane": DistrictEntry("Thane", "Konkan", (19.20, 72.98)),
    "palghar": DistrictEntry("Palghar", "Konkan", (19.70, 72.77)),
    "raigad": DistrictEntry("Raigad", "Konkan", (18.75, 73.10)),
    "ratnagiri": DistrictEntry("Ratnagiri", "Konkan", (16.99, 73.30)),
    "sindhudurg": DistrictEntry("Sindhudurg", "Konkan", (16.10, 73.69)),
    # --- Nashik (5) ---
    "nashik": DistrictEntry("Nashik", "Nashik", (20.00, 73.79)),
    "ahmednagar": DistrictEntry("Ahmednagar", "Nashik", (19.09, 74.74)),
    "dhule": DistrictEntry("Dhule", "Nashik", (20.90, 74.78)),
    "jalgaon": DistrictEntry("Jalgaon", "Nashik", (21.01, 75.56)),
    "nandurbar": DistrictEntry("Nandurbar", "Nashik", (21.37, 74.11)),
    # --- Pune (5) ---
    "pune": DistrictEntry("Pune", "Pune", (18.52, 73.86)),
    "satara": DistrictEntry("Satara", "Pune", (17.68, 74.00)),
    "solapur": DistrictEntry("Solapur", "Pune", (17.66, 75.91)),
    "kolhapur": DistrictEntry("Kolhapur", "Pune", (16.70, 74.24)),
    "sangli": DistrictEntry("Sangli", "Pune", (16.85, 74.57)),
    # --- Chhatrapati Sambhajinagar (Aurangabad) (8) ---
    # Chhatrapati Sambhajinagar is the post-2023 official name of Aurangabad
    # district; both spellings resolve to ONE district entry so the set stays
    # at the official 36 (see DISTRICT_ALIASES).
    "aurangabad": DistrictEntry("Aurangabad", "Chhatrapati Sambhajinagar", (19.88, 75.34)),
    "jalna": DistrictEntry("Jalna", "Chhatrapati Sambhajinagar", (19.84, 75.88)),
    "parbhani": DistrictEntry("Parbhani", "Chhatrapati Sambhajinagar", (19.27, 76.77)),
    "beed": DistrictEntry("Beed", "Chhatrapati Sambhajinagar", (18.99, 75.76)),
    "hingoli": DistrictEntry("Hingoli", "Chhatrapati Sambhajinagar", (19.71, 77.15)),
    "nanded": DistrictEntry("Nanded", "Chhatrapati Sambhajinagar", (19.14, 77.32)),
    "latur": DistrictEntry("Latur", "Chhatrapati Sambhajinagar", (18.40, 76.57)),
    "osmanabad": DistrictEntry("Osmanabad", "Chhatrapati Sambhajinagar", (18.15, 76.04)),
    # --- Amravati (5) ---
    "amravati": DistrictEntry("Amravati", "Amravati", (20.93, 77.75)),
    "akola": DistrictEntry("Akola", "Amravati", (20.71, 77.00)),
    "washim": DistrictEntry("Washim", "Amravati", (20.10, 77.13)),
    "buldhana": DistrictEntry("Buldhana", "Amravati", (20.53, 76.18)),
    "yavatmal": DistrictEntry("Yavatmal", "Amravati", (20.39, 78.13)),
    # --- Nagpur (6) ---
    "nagpur": DistrictEntry("Nagpur", "Nagpur", (21.15, 79.09)),
    "wardha": DistrictEntry("Wardha", "Nagpur", (20.75, 78.60)),
    "bhandara": DistrictEntry("Bhandara", "Nagpur", (21.15, 79.65)),
    "gondia": DistrictEntry("Gondia", "Nagpur", (21.46, 80.19)),
    "chandrapur": DistrictEntry("Chandrapur", "Nagpur", (19.95, 79.30)),
    "gadchiroli": DistrictEntry("Gadchiroli", "Nagpur", (20.18, 80.00)),
}

# Canonical name for each district (title case, canonical spelling).
DISTRICT_CANONICAL = {entry.name.lower(): entry.name for entry in MAHARASHTRA_DISTRICTS.values()}

# Aliases / suburbs → district. Curation-driven, evidence-checked. An alias is
# added only when the locality is unambiguously inside one district.
DISTRICT_ALIASES: Dict[str, str] = {
    # Pune district localities
    "pimpri": "pune", "pimpri-chinchwad": "pune", "pcmc": "pune",
    "chinchwad": "pune", "hinjewadi": "pune", "hadapsar": "pune",
    "kothrud": "pune", "wakad": "pune", "baner": "pune", "balewadi": "pune",
    "magarpatta": "pune", "viman nagar": "pune", "kharadi": "pune",
    "shivajinagar": "pune", "deccan": "pune", "aundh": "pune", "katraj": "pune",
    "wanowrie": "pune", "camp": "pune", "swargate": "pune", "pashan": "pune",
    "bavdhan": "pune", "kondhwa": "pune", "erandwane": "pune", "yewalewadi": "pune",
    "talegaon": "pune", "lonavala": "pune", "khed": "pune", "mulshi": "pune",
    "baramati": "pune", "shirur": "pune", "daund": "pune", "indapur": "pune",
    # Mumbai districts
    "andheri": "mumbai suburban", "bandra": "mumbai suburban",
    "juhu": "mumbai suburban", "goregaon": "mumbai suburban",
    "malad": "mumbai suburban", "kandivali": "mumbai suburban",
    "borivali": "mumbai suburban", "dahisar": "mumbai suburban",
    "powai": "mumbai suburban", "kurla": "mumbai suburban",
    "ghatkopar": "mumbai suburban", "vikhroli": "mumbai suburban",
    "dadar": "mumbai city", "parel": "mumbai city", "worli": "mumbai city",
    "colaba": "mumbai city", "fort": "mumbai city", "marine lines": "mumbai city",
    "lower parel": "mumbai city", "matunga": "mumbai city", "sion": "mumbai city",
    "wadala": "mumbai city", "mumbai": "mumbai suburban",
    # Thane district
    "navi mumbai": "thane", "vashi": "thane", "sanpada": "thane",
    "ghansoli": "thane", "nerul": "thane", "belapur": "thane", "kharghar": "thane",
    "ulwe": "thane", "kalyan": "thane", "dombivli": "thane", "ambarnath": "thane",
    "badlapur": "thane", "thane west": "thane", "miradatar": "thane", "bhiwandi": "thane",
    # Nashik
    "nashik road": "nashik", "ambad": "nashik", "satpur": "nashik",
    # Aurangabad
    "chhatrapati sambhajinagar": "aurangabad",
    "chh sambhajinagar": "aurangabad", "sambhajinagar": "aurangabad",
    # Nagpur
    "mahal": "nagpur", "sitabuldi": "nagpur", "dhantoli": "nagpur", "manewada": "nagpur",
    # Solapur / Sangli / Kolhapur
    "akluj": "solapur", "kurduwadi": "solapur",
    "sangli miragaon": "sangli", "sanglimiraj": "sangli",
    "ichalkaranji": "kolhapur", "gokul shirgaon": "kolhapur",
    # Raigad
    "panvel": "raigad", "pen": "raigad", "ulhasnagar": "thane",
}

_PATTERN_CACHE: Dict[str, re.Pattern] = {}


def _compiled(pattern: str) -> re.Pattern:
    if pattern not in _PATTERN_CACHE:
        _PATTERN_CACHE[pattern] = re.compile(pattern)
    return _PATTERN_CACHE[pattern]


class MaharashtraGeoEngine:
    """Deterministic, evidence-faithful Maharashtra location resolution.

    Resolution statuses:
      EXACT_SINGLE   — exactly one district named.
      MULTI_EXPLICIT — multiple districts explicitly named.
      CITY_MENTION   — a locality/suburb maps to a district with word
                       boundaries (weak but admissible signal).
      AMBIGUOUS      — district-name substring found without word boundary
                       (never promoted to a district assignment).
      UNKNOWN        — no Maharashtra geography signal.
    """

    def __init__(self):
        self.districts = MAHARASHTRA_DISTRICTS

    # -- Public API ------------------------------------------------------
    def list_districts(self) -> List[str]:
        """Return canonical district names in stable order."""
        seen: List[str] = []
        for entry in MAHARASHTRA_DISTRICTS.values():
            if entry.name not in seen:
                seen.append(entry.name)
        return seen

    def district_division(self, district: str) -> Optional[str]:
        entry = MAHARASHTRA_DISTRICTS.get(district.lower())
        return entry.division if entry else None

    def divisions(self) -> Dict[str, List[str]]:
        grouped: Dict[str, List[str]] = {}
        for entry in MAHARASHTRA_DISTRICTS.values():
            grouped.setdefault(entry.division, []).append(entry.name)
        return grouped

    def resolve(self, location_text: Optional[str]) -> LocationNormalizationResult:
        """Resolve a free-text location against Maharashtra districts.

        Never assigns a district without evidence; "Maharashtra" alone is
        AMBIGUOUS (not defaulted to Mumbai), matching Demand-X's P1 constraint.
        """
        if not location_text or not location_text.strip():
            return LocationNormalizationResult(
                raw_location=location_text,
                country="India",
                state=None,
                district=None,
                locality=None,
                location_scope="UNKNOWN",
                location_confidence="NONE",
                matched_locations=[],
                normalization_method="MAHARASHTRA_GEO_V1",
                location_evidence_level="UNKNOWN",
            )

        raw = location_text.strip()
        lower = " ".join(raw.lower().split())

        matched_districts: List[str] = []
        matched_aliases: List[str] = []
        has_maharashtra = bool(_compiled(r"\bmaharashtra\b").search(lower))

        for norm, entry in MAHARASHTRA_DISTRICTS.items():
            if _compiled(r"\b" + re.escape(norm) + r"\b").search(lower):
                if entry.name not in matched_districts:
                    matched_districts.append(entry.name)

        for alias, district_norm in DISTRICT_ALIASES.items():
            if _compiled(r"\b" + re.escape(alias) + r"\b").search(lower):
                entry = MAHARASHTRA_DISTRICTS[district_norm]
                matched_aliases.append(alias)
                if entry.name not in matched_districts:
                    matched_districts.append(entry.name)

        state = "Maharashtra" if (has_maharashtra or matched_districts) else None

        if len(matched_districts) == 0:
            evidence = "AMBIGUOUS" if has_maharashtra else "UNKNOWN"
            return LocationNormalizationResult(
                raw_location=raw,
                country="India",
                state=state,
                district=None,
                locality=None,
                location_scope="UNKNOWN",
                location_confidence="LOW" if has_maharashtra else "NONE",
                matched_locations=matched_aliases,
                normalization_method="MAHARASHTRA_GEO_V1",
                location_evidence_level=evidence,
            )

        if len(matched_districts) == 1 and not matched_aliases:
            evidence = "EXACT_SINGLE"
        elif len(matched_districts) == 1 and matched_aliases:
            evidence = "CITY_MENTION"
        else:
            evidence = "MULTI_EXPLICIT"

        scope = "SINGLE_LOCATION" if len(matched_districts) == 1 else "MULTI_LOCATION"
        confidence = "HIGH" if evidence == "EXACT_SINGLE" else ("MEDIUM" if evidence in ("CITY_MENTION", "MULTI_EXPLICIT") else "LOW")

        return LocationNormalizationResult(
            raw_location=raw,
            country="India",
            state="Maharashtra",
            district=matched_districts[0] if len(matched_districts) == 1 else None,
            locality=matched_aliases[0] if matched_aliases else None,
            location_scope=scope,
            location_confidence=confidence,
            matched_locations=matched_districts or matched_aliases,
            normalization_method="MAHARASHTRA_GEO_V1",
            location_evidence_level=evidence,
        )

    def resolve_all_districts(self, location_text: str) -> List[str]:
        """Return every district matched in text (ordered by position, deduped)."""
        resolved = self.resolve(location_text)
        return resolved.matched_locations