"""AI Service Abstraction — evidence-grounded, provider-agnostic layer.

Adapted from reference project's ai/gemini_engine.py and ai/local_counselor.py.

Key improvements over reference:
- No LLM decides labour demand, fabricates statistics, supplies, NCO codes,
  companies, or salary data.
- Every response is grounded in real evidence retrieved from the database.
- Each response explicitly exposes: evidence sources, observation period,
  source freshness label, and a confidence level.

Reference anti-patterns rejected:
- "Government of Maharashtra" impersonation — Demand-X brand only.
- Hardcoded salary charts and demand scores — never used.
- seed_data.py fabricated fallbacks — never used.
"""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ── AI Response model ──────────────────────────────────────────────────────────

@dataclass
class AIResponse:
    """Structured, evidence-grounded AI response.

    Every field is explicit; nothing is fabricated. When evidence is
    insufficient, ``answer`` says so and ``confidence`` is LOW.
    """
    answer: str
    confidence: str = "LOW"                    # HIGH / MEDIUM / LOW
    evidence: List[Dict[str, Any]] = field(default_factory=list)
    observation_period: Optional[str] = None
    source_freshness: Optional[str] = None     # LIVE | PERIODIC | HISTORICAL | STATIC | NO_DATA
    provider: str = "local_evidence_fallback"
    disclaimer: str = (
        "This response is evidence-grounded from persisted observations only. "
        "No statistics, supply figures, or salary data have been fabricated."
    )

    def as_dict(self) -> Dict[str, Any]:
        return {
            "answer": self.answer,
            "confidence": self.confidence,
            "evidence": self.evidence,
            "observation_period": self.observation_period,
            "source_freshness": self.source_freshness,
            "provider": self.provider,
            "disclaimer": self.disclaimer,
        }


# ── Abstract provider interface ────────────────────────────────────────────────

class AIAbstraction(ABC):
    """Provider-agnostic AI interface.

    Implementations must never fabricate data. Every answer is grounded
    in evidence retrieved from persisted observations.
    """

    @abstractmethod
    def answer_question(
        self,
        question: str,
        *,
        db_url: Optional[str] = None,
        source_id: Optional[str] = None,
        district: Optional[str] = None,
        sector: Optional[str] = None,
    ) -> AIResponse:
        """Answer a labour-market question grounded in real evidence."""


# ── Local evidence-grounded fallback ───────────────────────────────────────────

class LocalEvidenceFallback(AIAbstraction):
    """Deterministic fallback that queries real DB records.

    Does NOT use any LLM. Evidence is drawn directly from the skill
    demand engine and source metadata. When data is insufficient,
    the response says so explicitly.
    """

    def answer_question(
        self,
        question: str,
        *,
        db_url: Optional[str] = None,
        source_id: Optional[str] = None,
        district: Optional[str] = None,
        sector: Optional[str] = None,
    ) -> AIResponse:
        """Answer grounded in persisted skill demand evidence only."""
        if not db_url:
            return AIResponse(
                answer="No database connection provided; cannot answer without real evidence.",
                confidence="LOW",
                source_freshness="NO_DATA",
                provider="local_evidence_fallback",
            )

        try:
            from core.analytics.skill_demand_engine import calculate_skill_demand
            from datetime import date
            from sqlalchemy import create_engine
            from sqlalchemy.orm import sessionmaker
            from core.models.source import Source

            engine = create_engine(db_url)
            SessionLocal = sessionmaker(bind=engine)
            session = SessionLocal()

            sources = session.query(Source).all()
            source_freshness = "NO_DATA"
            latest_fetched = None
            for s in sources:
                if s.last_fetched_at:
                    if latest_fetched is None or s.last_fetched_at > latest_fetched:
                        latest_fetched = s.last_fetched_at
            if latest_fetched:
                source_freshness = "HISTORICAL"

            today = date.today()
            window_start = date(today.year - 1, today.month, today.day)
            window_end = today

            result = calculate_skill_demand(
                db_url=db_url,
                source_id=source_id or "naukri-historical-promptcloud",
                district=district,
                sector=sector,
                observation_period_start=window_start,
                observation_period_end=window_end,
            )

            total_skills = len(result.get("skill_demand", []))
            top_skills = sorted(
                result.get("skill_demand", []),
                key=lambda r: r.get("normalized_distinct_job_count", 0) or 0,
                reverse=True,
            )[:5]
            top_names = [s.get("canonical_skill_name", "unknown") for s in top_skills]
            top_shares = [
                round((s.get("normalized_distinct_job_count", 0) or 0) * 100, 2)
                for s in top_skills
            ]
            total_evaluated = result.get("evidence", {}).get("total_job_postings_evaluated", 0)
            total_matched = result.get("evidence", {}).get("matched_job_postings", 0)

            period_label = f"{window_start.isoformat()} to {window_end.isoformat()}"

            if total_skills == 0:
                answer = (
                    f"No skill evidence found for {district or 'all districts'} "
                    f"from source {source_id or 'default'}. "
                    "This does NOT mean there is no demand — only that no persisted "
                    "observations contained extractable skill evidence for this query."
                )
            else:
                top_list = ", ".join(
                    f"{name} ({share}%)" for name, share in zip(top_names, top_shares)
                )
                answer = (
                    f"From {total_evaluated} job observations in {period_label}, "
                    f"{total_matched} carried extractable skill evidence across "
                    f"{total_skills} canonical skills. "
                    f"Top skills: {top_list}. "
                    "Skill share is the fraction of observations carrying each skill "
                    "— NOT a demand score or weighted metric."
                )

            evidence = [
                {
                    "source": source_id or "naukri-historical-promptcloud",
                    "observation_period": period_label,
                    "total_observations": total_evaluated,
                    "matched_observations": total_matched,
                    "skills_extracted": total_skills,
                }
            ]

            confidence = "MEDIUM" if total_evaluated >= 100 else "LOW"

            return AIResponse(
                answer=answer,
                confidence=confidence,
                evidence=evidence,
                observation_period=period_label,
                source_freshness=source_freshness,
                provider="local_evidence_fallback",
            )

        except Exception as exc:
            logger.error("Local evidence fallback failed: %s", exc)
            return AIResponse(
                answer=(
                    f"Local evidence query failed: {exc}. "
                    "No data has been fabricated — the query returned no result."
                ),
                confidence="LOW",
                source_freshness="NO_DATA",
                provider="local_evidence_fallback",
            )