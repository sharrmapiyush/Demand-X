"""Tests for Deduplication — SimHash and DeduplicationEngine (real module API)."""
import pytest
from core.deduplication.engine import (
    SimHash,
    DeduplicationEngine,
    DuplicateStatus,
    canonical_key,
    NEAR_DUPLICATE_HAMMING,
)


def test_simhash_fingerprint_deterministic():
    sh = SimHash()
    text = "Senior Python Developer with Django and PostgreSQL experience"
    h1 = sh.fingerprint(text)
    h2 = sh.fingerprint(text)
    assert h1 == h2
    assert isinstance(h1, int)
    assert 0 <= h1 < (1 << 64)


def test_simhash_near_duplicate():
    # The engine's docstring example: pure formatting drift (whitespace /
    # punctuation that the tokenizer strips) keeps shingles aligned and lands
    # within the tuned threshold.
    sh = SimHash()
    t1 = "Software Engineer - Pune"
    t2 = "Software Engineer  - Pune"
    h1 = sh.fingerprint(t1)
    h2 = sh.fingerprint(t2)
    dist = sh.hamming_distance(h1, h2)
    assert dist <= NEAR_DUPLICATE_HAMMING, f"Near-duplicates should be close: hamming={dist}"


def test_simhash_word_edit_is_conservatively_distinct():
    # A genuine word-level edit flips more than the tuned threshold bits.
    # The engine is deliberately conservative: it will NOT collapse two jobs
    # that differ by real wording, biasing against false near-dup merging.
    sh = SimHash()
    t1 = "Senior Python Developer with Django and PostgreSQL experience"
    t2 = "Senior Python Developer with Django and PostgreSQL experiences"
    dist = sh.hamming_distance(sh.fingerprint(t1), sh.fingerprint(t2))
    assert dist > NEAR_DUPLICATE_HAMMING, f"Word edits are beyond threshold: hamming={dist}"


def test_simhash_different_texts():
    sh = SimHash()
    t1 = "Senior Python Developer with Django and PostgreSQL experience"
    t2 = "Junior Marketing Manager for FMCG brand launches and media planning"
    h1 = sh.fingerprint(t1)
    h2 = sh.fingerprint(t2)
    dist = sh.hamming_distance(h1, h2)
    assert dist > NEAR_DUPLICATE_HAMMING, f"Different texts should be far apart: hamming={dist}"


def test_simhash_hamming_distance_range():
    sh = SimHash()
    h1 = sh.fingerprint("hello world test")
    h2 = sh.fingerprint("goodbye world test")
    dist = sh.hamming_distance(h1, h2)
    assert 0 <= dist <= 64


def test_simhash_empty_text_zero():
    sh = SimHash()
    assert sh.fingerprint("") == 0


def test_duplicate_status_enum():
    values = {s.value for s in DuplicateStatus}
    assert "EXACT_MATCH" in values
    assert "NEAR_DUPLICATE" in values
    assert "REPOST" in values
    assert "DISTINCT" in values


def test_canonical_key_sha256():
    rec1 = {"title": "Python Dev", "company": "TechCorp", "location": "Pune"}
    rec2 = {"title": "python dev", "company": "  TechCorp ", "location": "pune"}
    k1 = canonical_key(rec1, ["title", "company", "location"])
    k2 = canonical_key(rec2, ["title", "company", "location"])
    assert k1 == k2
    assert len(k1) == 64  # SHA256 hex


def test_dedup_engine_evaluate_exact():
    engine = DeduplicationEngine()
    rec = {"title": "Senior Python Developer", "company": "TechCorp", "location": "Pune"}
    canonical = canonical_key(rec, ["title", "company", "location"])
    fp = engine.sh.fingerprint(" ".join(str(rec[f]) for f in ["title", "company", "location"]))
    engine.record("job-001", canonical, fp)
    status = engine.evaluate_duplicate_status(canonical, fp)
    assert status is DuplicateStatus.EXACT_MATCH


def test_dedup_engine_near_duplicate_not_inflated():
    """A repost/near-duplicate must not be treated as a distinct observation.

    The engine's conservative SimHash window catches formatting-drift reposts:
    fingerprints collide (hamming 0) while the canonical keys differ, so the
    status is NEAR_DUPLICATE — it never adds a fresh distinct observation.
    """
    engine = DeduplicationEngine()
    rec1 = {"title": "Senior Python Developer with Django and PostgreSQL experience", "company": "TechCorp", "location": "Pune"}
    rec2 = {"title": "Senior  Python Developer with Django and PostgreSQL experience", "company": "TechCorp", "location": "Pune"}
    def _fp(rec):
        return engine.sh.fingerprint(" ".join(str(rec[f]) for f in ["title", "company", "location"]))

    canonical1 = canonical_key(rec1, ["title", "company", "location"])
    engine.record("job-001", canonical1, _fp(rec1))
    # Formatting drift: different canonical key, identical fingerprint.
    assert canonical_key(rec2, ["title", "company", "location"]) != canonical1
    canonical2 = canonical_key(rec2, ["title", "company", "location"])
    status2 = engine.evaluate_duplicate_status(canonical2, _fp(rec2))
    assert status2 is DuplicateStatus.NEAR_DUPLICATE


def test_dedup_engine_evaluate_distinct():
    engine = DeduplicationEngine()
    rec1 = {"title": "Senior Python Developer with Django and PostgreSQL", "company": "TechCorp", "location": "Pune"}
    rec2 = {"title": "Junior Marketing Manager for FMCG brand launches", "company": "OtherCorp", "location": "Nashik"}
    def _fp(rec):
        return engine.sh.fingerprint(" ".join(str(rec[f]) for f in ["title", "company", "location"]))

    engine.record("job-001", canonical_key(rec1, ["title", "company", "location"]), _fp(rec1))
    status2 = engine.evaluate_duplicate_status(
        canonical_key(rec2, ["title", "company", "location"]), _fp(rec2)
    )
    assert status2 is DuplicateStatus.DISTINCT


def test_dedup_engine_analyze_pipeline():
    engine = DeduplicationEngine()
    result = engine.analyze(
        {"title": "Software Engineer", "company": "Acme", "location": "Pune"},
        "job-001",
        ["title", "company", "location"],
    )
    assert result["record_id"] == "job-001"
    assert result["status"] in ("EXACT_MATCH", "NEAR_DUPLICATE", "REPOST", "DISTINCT")
    assert len(result["canonical_key"]) == 64
    assert isinstance(result["fingerprint"], int)