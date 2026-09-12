"""Tests for Maharashtra Geography Engine — 36 districts, 6 divisions, explicit statuses."""
import pytest


def test_engine_has_36_districts():
    from core.geography.maharashtra import MaharashtraGeoEngine
    engine = MaharashtraGeoEngine()
    districts = engine.list_districts()
    assert len(districts) == 36


def test_engine_has_6_divisions():
    from core.geography.maharashtra import MaharashtraGeoEngine
    engine = MaharashtraGeoEngine()
    divisions = engine.divisions()
    assert len(divisions) == 6
    assert "Konkan" in divisions
    assert "Pune" in divisions
    assert "Nashik" in divisions
    # Aurangabad district is part of the Chhatrapati Sambhajinagar division
    # (post-2023 official name of the Aurangabad revenue division).
    assert "Chhatrapati Sambhajinagar" in divisions
    assert "Aurangabad" in divisions["Chhatrapati Sambhajinagar"]
    assert "Amravati" in divisions
    assert "Nagpur" in divisions


def test_resolve_exact_single():
    from core.geography.maharashtra import MaharashtraGeoEngine
    engine = MaharashtraGeoEngine()
    result = engine.resolve("Pune")
    assert result.district == "Pune"
    assert result.location_evidence_level == "EXACT_SINGLE"
    assert result.state == "Maharashtra"


def test_resolve_maharashtra_ambigous():
    from core.geography.maharashtra import MaharashtraGeoEngine
    engine = MaharashtraGeoEngine()
    result = engine.resolve("Maharashtra")
    assert result.district is None
    assert result.location_evidence_level == "AMBIGUOUS"
    assert result.state == "Maharashtra"


def test_renamed_district_resolves_to_single_entry():
    """Aurangabad ↔ Chhatrapati Sambhajinagar is ONE district — both spellings
    must resolve to a single entry, never two (keeps the official 36)."""
    from core.geography.maharashtra import MaharashtraGeoEngine
    engine = MaharashtraGeoEngine()
    assert len(engine.districts) == 36
    result = engine.resolve("Chhatrapati Sambhajinagar")
    assert result.district == "Aurangabad"
    assert result.district != "Chhatrapati Sambhajinagar"
    assert engine.district_division("Aurangabad") == "Chhatrapati Sambhajinagar"


def test_resolve_never_defaults_to_mumbai():
    """CRITICAL: 'Maharashtra' alone must NEVER default to Mumbai."""
    from core.geography.maharashtra import MaharashtraGeoEngine
    engine = MaharashtraGeoEngine()
    result = engine.resolve("Maharashtra")
    assert result.district != "Mumbai City"
    assert result.district != "Mumbai Suburban"
    assert result.location_evidence_level == "AMBIGUOUS"


def test_resolve_city_mention():
    from core.geography.maharashtra import MaharashtraGeoEngine
    engine = MaharashtraGeoEngine()
    result = engine.resolve("Andheri, Maharashtra")
    assert result.district is not None
    assert result.location_evidence_level == "CITY_MENTION"


def test_resolve_multi_explicit():
    from core.geography.maharashtra import MaharashtraGeoEngine
    engine = MaharashtraGeoEngine()
    result = engine.resolve("Pune and Nashik")
    assert result.location_evidence_level == "MULTI_EXPLICIT"
    assert len(result.matched_locations) >= 2


def test_resolve_unknown():
    from core.geography.maharashtra import MaharashtraGeoEngine
    engine = MaharashtraGeoEngine()
    result = engine.resolve("Bangalore")
    assert result.district is None
    assert result.location_evidence_level == "UNKNOWN"


def test_resolve_empty():
    from core.geography.maharashtra import MaharashtraGeoEngine
    engine = MaharashtraGeoEngine()
    result = engine.resolve("")
    assert result.district is None
    assert result.location_evidence_level == "UNKNOWN"


def test_district_division():
    from core.geography.maharashtra import MaharashtraGeoEngine
    engine = MaharashtraGeoEngine()
    assert engine.district_division("Pune") == "Pune"
    assert engine.district_division("Mumbai City") == "Konkan"
    assert engine.district_division("Nagpur") == "Nagpur"
    assert engine.district_division("Nonexistent") is None


def test_divisions_grouping():
    from core.geography.maharashtra import MaharashtraGeoEngine
    engine = MaharashtraGeoEngine()
    divs = engine.divisions()
    # Konkan includes Mumbai City, Mumbai Suburban, Thane, Palghar, Raigad, Ratnagiri, Sindhudurg
    assert len(divs["Konkan"]) == 7
    assert "Pune" in divs["Pune"]
    assert len(divs["Pune"]) == 5


def test_resolve_all_districts():
    from core.geography.maharashtra import MaharashtraGeoEngine
    engine = MaharashtraGeoEngine()
    result = engine.resolve_all_districts("Pune and Nashik and Thane")
    assert "Pune" in result
    assert "Nashik" in result
    assert "Thane" in result
