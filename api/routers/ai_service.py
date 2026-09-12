"""AI Service Router — Evidence-grounded AI and RAG endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Query
from typing import Optional

from api.config import settings

router = APIRouter(prefix="/api/v1/ai", tags=["ai_service"])


@router.get("/ask")
def ask_question(
    q: str = Query(..., min_length=3, description="Natural language question"),
    district: Optional[str] = Query(None),
    sector: Optional[str] = Query(None),
    source_id: str = Query("naukri-historical-promptcloud"),
):
    """Answer a question using the local evidence-grounded RAG engine.

    Every response exposes observation period, source freshness, confidence,
    and evidence sources. No external LLM is called; no statistics are
    fabricated.
    """
    from ai.rag.engine import LocalRAGEngine
    from ai.service.abstraction import LocalEvidenceFallback

    rag = LocalRAGEngine(db_url=settings.DATABASE_URL)
    rag_response = rag.query(q, district=district, sector=sector, source_id=source_id)

    fallback = LocalEvidenceFallback(db_url=settings.DATABASE_URL)
    ai_response = fallback.answer_question(q, db_url=settings.DATABASE_URL, source_id=source_id, district=district)

    return {
        "rag": rag_response,
        "ai": {
            "answer": ai_response.answer,
            "confidence": ai_response.confidence,
            "evidence_count": len(ai_response.evidence),
            "observation_period": ai_response.observation_period,
            "source_freshness": ai_response.source_freshness,
            "provider": ai_response.provider,
            "disclaimer": ai_response.disclaimer,
        },
    }


@router.post("/ask")
def ask_question_post(payload: dict):
    """Answer a question via POST (larger payloads)."""
    q = payload.get("question", "")
    if not q or len(q) < 3:
        return {"error": "Provide a question with at least 3 characters."}

    return ask_question(
        q=q,
        district=payload.get("district"),
        sector=payload.get("sector"),
        source_id=payload.get("source_id", "naukri-historical-promptcloud"),
    )


@router.get("/rag")
def rag_query(
    q: str = Query(..., min_length=3),
    district: Optional[str] = Query(None),
    sector: Optional[str] = Query(None),
    source_id: Optional[str] = Query(None),
):
    """Direct RAG retrieval and generation (evidence-grounded, no fabricated data)."""
    from ai.rag.engine import LocalRAGEngine

    rag = LocalRAGEngine(db_url=settings.DATABASE_URL)
    response = rag.query(q, district=district, sector=sector, source_id=source_id)
    return response