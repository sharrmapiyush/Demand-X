import pytest
from core.ontology.loader import (
    load_occupations_seed,
    load_trade_occupation_mappings,
    validate_occupation_ontology,
    get_occupation_by_id
)


def test_unique_occupation_ids():
    occupations = load_occupations_seed()
    occ_ids = [o["occupation_id"] for o in occupations]
    assert len(occ_ids) == len(set(occ_ids)), "Occupation IDs must be unique across ontology seed"


def test_non_empty_occupation_names():
    occupations = load_occupations_seed()
    for o in occupations:
        name = o.get("canonical_occupation_name")
        assert name is not None and len(name.strip()) > 0, f"Occupation {o.get('occupation_id')} must have non-empty canonical name"


def test_valid_occupation_verification_status():
    occupations = load_occupations_seed()
    for o in occupations:
        assert o.get("verification_status") is not None, f"Occupation {o.get('occupation_id')} must have verification_status"


def test_no_unsupported_verified_occupation_status():
    occupations = load_occupations_seed()
    for o in occupations:
        assert o.get("verification_status") != "VERIFIED", f"Occupation {o['occupation_id']} cannot be VERIFIED without inspected document evidence"


def test_mappings_reference_existing_occupations():
    occupations = load_occupations_seed()
    occ_ids = {o["occupation_id"] for o in occupations}
    mappings = load_trade_occupation_mappings()
    for m in mappings:
        oid = m.get("occupation_id")
        assert oid in occ_ids, f"Mapping references non-existent occupation_id: {oid}"


def test_mapping_provenance_presence():
    mappings = load_trade_occupation_mappings()
    for m in mappings:
        src = m.get("evidence_source")
        assert src is not None and len(src.strip()) > 0, f"Mapping for {m.get('canonical_trade_name')} must have non-empty evidence_source"


def test_valid_mapping_status_needs_review():
    mappings = load_trade_occupation_mappings()
    for m in mappings:
        assert m.get("mapping_status") == "NEEDS_REVIEW", f"Mapping for {m.get('canonical_trade_name')} must be NEEDS_REVIEW"


def test_duplicate_occupation_mapping_prevention():
    mappings = load_trade_occupation_mappings()
    seen = set()
    for m in mappings:
        key = (m.get("canonical_trade_name"), m.get("occupation_id"))
        assert key not in seen, f"Duplicate occupation mapping detected for {key}"
        seen.add(key)


def test_nco_codes_not_required():
    occupations = load_occupations_seed()
    for o in occupations:
        # Verify that NCO code absence is fully supported and does not cause schema errors
        assert "nco_code" not in o or o.get("nco_code") is None or isinstance(o.get("nco_code"), str)


def test_occupation_ontology_validation_function():
    result = validate_occupation_ontology()
    assert result["valid"] is True, f"Occupation ontology validation failed with errors: {result.get('errors')}"
    assert result["occupations_count"] == 7
    assert result["mappings_count"] == 7
