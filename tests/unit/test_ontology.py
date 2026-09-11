import pytest
from core.ontology.loader import (
    load_skills_seed,
    load_trade_skill_mappings,
    normalize_skill_name,
    validate_ontology
)


def test_unique_skill_ids():
    skills = load_skills_seed()
    skill_ids = [s["skill_id"] for s in skills]
    assert len(skill_ids) == len(set(skill_ids)), "Skill IDs must be unique across ontology seed"


def test_alias_normalization():
    assert normalize_skill_name("  Skin Care  ") == "skin care"
    assert normalize_skill_name("COMPUTER   FUNDAMENTALS") == "computer fundamentals"
    assert normalize_skill_name("") == ""

    skills = load_skills_seed()
    for s in skills:
        for alias in s.get("aliases", []):
            normalized = normalize_skill_name(alias)
            assert len(normalized) > 0


def test_duplicate_mapping_prevention():
    mappings = load_trade_skill_mappings()
    seen = set()
    for m in mappings:
        key = (m.get("canonical_trade_name"), m.get("skill_id"))
        assert key not in seen, f"Duplicate mapping detected for {key}"
        seen.add(key)


def test_provenance_presence():
    mappings = load_trade_skill_mappings()
    for m in mappings:
        assert m.get("evidence_source") is not None
        assert len(m.get("evidence_source").strip()) > 0, "Mapping must have non-empty evidence_source (provenance)"


def test_no_verified_status_without_evidence():
    skills = load_skills_seed()
    for s in skills:
        assert s.get("verification_status") != "VERIFIED", f"Skill {s['skill_id']} cannot be VERIFIED without inspected document evidence"

    mappings = load_trade_skill_mappings()
    for m in mappings:
        assert m.get("mapping_status") == "NEEDS_REVIEW", f"Mapping for {m['canonical_trade_name']} must be NEEDS_REVIEW without explicit verified evidence"


def test_invalid_painter_general_advanced_tech_absent():
    mappings = load_trade_skill_mappings()
    for m in mappings:
        if m.get("canonical_trade_name") == "Painter General":
            assert m.get("skill_id") != "SKL-ADV-01", "Invalid Painter General -> SKL-ADV-01 mapping must be absent"


def test_ontology_validation_function():
    result = validate_ontology()
    assert result["valid"] is True, f"Ontology validation failed with errors: {result.get('errors')}"
    assert result["skills_count"] == 32  # 8 DVET + 24 Naukri expansion
    assert result["mappings_count"] == 8
