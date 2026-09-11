import re
from typing import Optional, List
from core.geography.models import LocationNormalizationResult

# Recognized Maharashtra districts and key cities/localities
MAHARASHTRA_DISTRICTS = {
    "pune", "mumbai", "thane", "nagpur", "nashik", "aurangabad", "solapur",
    "kolhapur", "amravati", "sangli", "jalgaon", "akola", "latur", "dhule",
    "ahmednagar", "chandrapur", "parbhani", "jalna", "bhiwandi", "nanded",
    "satara", "beed", "yavatmal", "gondia", "ratnagiri", "sindhudurg"
}

# Locality mappings for Pune
PUNE_LOCALITIES = {
    "pimpri-chinchwad", "pimpri chinchwad", "pcmc", "hinjewadi", "hadapsar",
    "kothrud", "wakad", "baner", "magarpatta", "viman nagar", "kharadi",
    "shivajinagar", "deccan", "aundh", "katraj", "wanowrie", "camp", "swargate"
}

# Known major cities in India often found in multi-location strings
MAJOR_CITIES = {
    "pune", "mumbai", "bengaluru", "bangalore", "chennai", "hyderabad",
    "secunderabad", "delhi", "ncr", "ahmedabad", "kolkata", "surat",
    "gurgaon", "noida", "ghaziabad", "faridabad", "jaipur", "chandigarh",
    "kochi", "cochin", "thiruvananthapuram", "trivandrum", "bhubaneswar",
    "patna", "indore", "bhopal", "lucknow", "kanpur", "visakhapatnam",
    "vizag", "vadodara", "rajkot", "nagpur", "nashik", "goa", "mysore", "mangalore"
}

def normalize_location(location_text: Optional[str]) -> LocationNormalizationResult:
    """
    Deterministically normalizes a raw location string according to MVP rules.
    Source-agnostic and maintains original raw_location.
    """
    if not location_text or not isinstance(location_text, str) or not location_text.strip():
        return LocationNormalizationResult(
            raw_location=location_text,
            country=None,
            state=None,
            district=None,
            locality=None,
            location_scope="UNKNOWN",
            location_confidence="NONE",
            matched_locations=[],
            normalization_method="DETERMINISTIC_RULE_V1"
        )

    raw = location_text.strip()
    norm_lower = raw.lower()

    # Split potential multi-location text by common delimiters: comma, slash, pipe, semicolon
    # e.g., "Pune / Mumbai", "Bengaluru , Mumbai , Chennai , Pune"
    parts = re.split(r'[,/|;]+', raw)
    cleaned_parts = [p.strip() for p in parts if p.strip()]

    # Extract all recognized cities/localities present in the parts or text
    matched_cities = []
    found_locality = None
    found_district = None
    found_state = None

    # Check for state references
    has_maharashtra = "maharashtra" in norm_lower or "mh" in [p.lower() for p in cleaned_parts]
    if has_maharashtra:
        found_state = "Maharashtra"

    # Evaluate parts
    for part in cleaned_parts:
        part_lower = part.lower()
        # Check localities
        for loc in PUNE_LOCALITIES:
            if loc in part_lower:
                found_locality = part # preserve formatting or clean up
                found_district = "Pune"
                found_state = "Maharashtra"
                if "pune" not in [c.lower() for c in matched_cities]:
                    matched_cities.append("Pune")
                break

        # Check cities/districts
        for city in MAJOR_CITIES:
            # Match whole word or exact part token
            # To avoid partial false matches, check word boundaries or exact containment in part
            pattern = r'\b' + re.escape(city) + r'\b'
            if re.search(pattern, part_lower):
                canonical_city = "Pune" if city in ["pune"] else ("Bengaluru" if city in ["bengaluru", "bangalore"] else part.title())
                if canonical_city not in matched_cities and canonical_city not in [m.title() for m in matched_cities]:
                    matched_cities.append(canonical_city)

                if city == "pune" and not found_district:
                    found_district = "Pune"
                    found_state = "Maharashtra"

    # If no major cities found via parts, do a broader search across the whole string
    if not matched_cities:
        for city in MAJOR_CITIES:
            pattern = r'\b' + re.escape(city) + r'\b'
            if re.search(pattern, norm_lower):
                canonical_city = "Pune" if city in ["pune"] else ("Bengaluru" if city in ["bengaluru", "bangalore"] else city.title())
                if canonical_city not in matched_cities:
                    matched_cities.append(canonical_city)
                if city == "pune" and not found_district:
                    found_district = "Pune"
                    found_state = "Maharashtra"

    # Determine location scope and confidence
    if len(matched_cities) == 0:
        # Check if Maharashtra state is mentioned alone
        if has_maharashtra:
            result = LocationNormalizationResult(
                raw_location=raw,
                country="India",
                state="Maharashtra",
                district=None,
                locality=None,
                location_scope="UNKNOWN",
                location_confidence="LOW",
                matched_locations=[],
                normalization_method="DETERMINISTIC_RULE_V1"
            )
        else:
            result = LocationNormalizationResult(
                raw_location=raw,
                country="India",
                state=None,
                district=None,
                locality=None,
                location_scope="UNKNOWN",
                location_confidence="NONE",
                matched_locations=[],
                normalization_method="DETERMINISTIC_RULE_V1"
            )
    elif len(matched_cities) == 1:
        single_city = matched_cities[0]
        is_pune = single_city.lower() == "pune"
        dist = "Pune" if is_pune else None
        st = "Maharashtra" if (is_pune or found_state) else found_state

        result = LocationNormalizationResult(
            raw_location=raw,
            country="India",
            state=st,
            district=dist,
            locality=found_locality,
            location_scope="SINGLE_LOCATION",
            location_confidence="HIGH" if is_pune else "MEDIUM",
            matched_locations=matched_cities,
            normalization_method="DETERMINISTIC_RULE_V1"
        )
    else:
        # Multiple matched cities -> MULTI_LOCATION
        is_pune_included = any(c.lower() == "pune" for c in matched_cities)
        dist = "Pune" if is_pune_included else None
        st = "Maharashtra" if (is_pune_included or found_state) else found_state

        result = LocationNormalizationResult(
            raw_location=raw,
            country="India",
            state=st,
            district=dist,
            locality=found_locality,
            location_scope="MULTI_LOCATION",
            location_confidence="MEDIUM",
            matched_locations=matched_cities,
            normalization_method="DETERMINISTIC_RULE_V1"
        )

    # Add Evidence Level
    # CITY_MENTION heuristic: irregular spacing pattern like "PUNE Mumbai, Chennai Kolkata" where
    # multiple city tokens are grouped without proper comma/slash separators.
    # Note: Ensure standard multi-city lists separated by commas/slashes (like "Bengaluru/Bangalore , Mumbai , Chennai , Pune") remain MULTI_EXPLICIT.
    has_irregular_spacing = False
    if "," in raw and not any(sep in raw for sep in ["/", "|", ";"]):
        # Check if any comma-separated segment contains multiple capitalized words without internal comma
        segments = raw.split(",")
        for seg in segments:
            tokens = seg.strip().split()
            if len(tokens) > 1 and all(t[0].isupper() for t in tokens if t):
                has_irregular_spacing = True
                break

    if result.location_scope == "SINGLE_LOCATION":
        result.location_evidence_level = "EXACT_SINGLE"
    elif result.location_scope == "MULTI_LOCATION":
        if has_irregular_spacing:
            result.location_evidence_level = "CITY_MENTION"
        else:
            result.location_evidence_level = "MULTI_EXPLICIT"
    else:
        # UNKNOWN scope
        if "pune" in norm_lower:
            result.location_evidence_level = "CITY_MENTION"
        else:
            result.location_evidence_level = "UNKNOWN"

    # Add Pune specific analysis
    if "pune" in [c.lower() for c in result.matched_locations] or (result.location_evidence_level == "CITY_MENTION" and "pune" in norm_lower):
        result.has_pune_evidence = True
        if result.location_evidence_level == "EXACT_SINGLE":
            result.pune_exclusivity = "EXCLUSIVE"
        elif result.location_evidence_level == "MULTI_EXPLICIT":
            result.pune_exclusivity = "SHARED"
        elif result.location_evidence_level == "CITY_MENTION":
            result.pune_exclusivity = "MENTIONED"
        else:
            result.pune_exclusivity = "UNKNOWN"
    else:
        result.has_pune_evidence = False
        result.pune_exclusivity = "UNKNOWN"

    return result
