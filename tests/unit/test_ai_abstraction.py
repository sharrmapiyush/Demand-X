"""Tests for AI Service Abstraction — AIResponse structure, LocalEvidenceFallback."""
import pytest


def test_ai_response_dataclass():
    from ai.service.abstraction import AIResponse
    resp = AIResponse(
        answer="Test answer",
        confidence="HIGH",
        evidence=[{"type": "JOB_POSTING", "id": "123"}],
        observation_period="2026-01-01 to 2026-09-10",
        source_freshness="HISTORICAL",
        provider="local_evidence_fallback",
        disclaimer="Evidence-grounded response.",
    )
    assert resp.answer == "Test answer"
    assert resp.confidence == "HIGH"
    assert len(resp.evidence) == 1
    assert resp.provider == "local_evidence_fallback"


def test_ai_response_default_confidence():
    from ai.service.abstraction import AIResponse
    resp = AIResponse(answer="Test")
    assert resp.confidence == "LOW"
    assert resp.evidence == []
    assert resp.provider == "local_evidence_fallback"


def test_local_evidence_fallback_no_db():
    from ai.service.abstraction import LocalEvidenceFallback
    fallback = LocalEvidenceFallback()
    resp = fallback.answer_question("What skills are in demand?", db_url="")
    assert resp.confidence == "LOW"
    assert resp.source_freshness == "NO_DATA"
    assert resp.provider == "local_evidence_fallback"


def test_local_evidence_fallback_bad_db():
    """A failing DB connection must degrade honestly, never fabricate."""
    from ai.service.abstraction import LocalEvidenceFallback
    fallback = LocalEvidenceFallback()
    resp = fallback.answer_question("What skills are in demand?", db_url="sqlite:///no/such/dir/x.db")
    assert resp.confidence == "LOW"
    assert resp.source_freshness == "NO_DATA"
    assert "fabricated" in resp.disclaimer
