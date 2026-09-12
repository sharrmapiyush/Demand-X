"""Tests for NCO-2015 Mapper — token similarity, NEVER fabricates numeric codes.

Demand-X rule (P7): a numeric NCO code is only emitted when an authoritative
source record provides it. Without a seed the mapper runs in NEEDS_REVIEW mode
and every result has nco_code=None.
"""
import csv
import pytest


@pytest.fixture
def authoritative_seed(tmp_path):
    """A minimal authoritative NCO reference table, supplied by the platform.
    This validates the VERIFIED path: codes come from the seed, not invention."""
    seed = tmp_path / "nco_occupations_seed.csv"
    with open(seed, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "nco_code", "occupation_title", "division", "group_name",
            "source_reference", "authoritative",
        ])
        writer.writeheader()
        writer.writerow({
            "nco_code": "5241", "occupation_title": "Beautician",
            "division": "Personal Services Workers", "group_name": "Beauty care",
            "source_reference": "DVET NCO-2015 Verify", "authoritative": "true",
        })
        writer.writerow({
            "nco_code": "7223", "occupation_title": "Lathe machine setter-operator",
            "division": "Metal, Machinery Workers", "group_name": "Machinists",
            "source_reference": "DVET NCO-2015 Verify", "authoritative": "false",
        })
    return str(seed)


def test_nco_mapper_loads_canonical_occupations():
    """Canonical occupations seed always loads; only the NCO reference is optional."""
    from core.ontology.nco_mapper import NCOMapper
    mapper = NCOMapper()
    assert len(mapper._canonical) > 0
    assert mapper.canonical_occupations_path.endswith("occupations_seed.json")


def test_nco_mapper_no_seed_runs_needs_review():
    """Without an authoritative seed, mapper.seeded is False and rules run."""
    from core.ontology.nco_mapper import NCOMapper
    mapper = NCOMapper()
    assert mapper.seeded is False


def test_nco_mapper_never_emits_code_without_seed():
    """CRITICAL (P7): no seed -> no fabricated numeric NCO code, ever."""
    from core.ontology.nco_mapper import NCOMapper
    mapper = NCOMapper()
    result = mapper.map_title("cosmetologist", canonical_occupation_id="OCC-BEAUTY-01")
    assert result.nco_code is None
    assert result.verification_status == "NEEDS_REVIEW"
    assert result.method in ("NO_REFERENCE", "LOW_CONFIDENCE")


def test_nco_mapper_authoritative_seed_emits_code(authoritative_seed):
    """When the platform seed provides an authoritative code, VERIFIED + code."""
    from core.ontology.nco_mapper import NCOMapper
    mapper = NCOMapper(nco_reference_path=authoritative_seed)
    assert mapper.seeded is True
    result = mapper.map_title("beautician", canonical_occupation_id="OCC-BEAUTY-01")
    assert result.nco_code == "5241"
    assert result.verification_status == "VERIFIED"
    assert result.method == "TOKEN_SIMILARITY"
    assert result.matched_on == "beautician"


def test_nco_mapper_non_authoritative_seed_holds_code(authoritative_seed):
    """Seed entries flagged non-authoritative must NOT emit a numeric code."""
    from core.ontology.nco_mapper import NCOMapper
    mapper = NCOMapper(nco_reference_path=authoritative_seed)
    result = mapper.map_title(
        "lathe machine operator", canonical_occupation_id="OCC-MACH-01"
    )
    assert result.nco_code is None
    assert result.verification_status == "NEEDS_REVIEW"


def test_nco_mapper_crosswalk_covers_all_canonical():
    from core.ontology.nco_mapper import NCOMapper
    mapper = NCOMapper()
    results = mapper.crosswalk_canonical_occupations()
    assert len(results) == len(mapper._canonical)
    for row in results:
        assert row["verification_status"] == "NEEDS_REVIEW"
        assert row["nco_code"] is None


def test_nco_mapper_empty_title():
    from core.ontology.nco_mapper import NCOMapper
    mapper = NCOMapper()
    result = mapper.map_title("")
    assert result.canonical_occupation_id is None
    assert result.confidence == 0.0