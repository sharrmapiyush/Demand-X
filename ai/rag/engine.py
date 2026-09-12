"""Local RAG Assistant — deterministic retrieval-augmented generation.

Adapted from reference project's ai/local_counselor.py.

Key improvements over reference:
- NEVER uses seed_data.py fabricated data; queries real persisted observations.
- NEVER claims to be a government AI or fabricates statistics.
- Structured evidence-grounded responses with explicit provenance fields.
- Provides a text-search retrieval interface (no vector DB required for MVP);
  when no vector index is available, falls back to keyword search against
  persisted records.

Reference flaws rejected:
- GeminiEngine's "Government of Maharashtra" impersonation.
- Hardcoded salary charts and demand scores.
- Stub dummy LLM responses.
- claim "NEVER mention Gemini/OpenAI" while pretending to be government.

Design:
- RAGEngine retrieves relevant records via keyword search over persisted
  observations (JobPosting, SkillEvidence, DistrictOccupationDemand).
- A "generation" step formats the evidence into a structured answer.
- The generation step uses deterministic templates; no external LLM is called
  in MVP. Future versions may call an LLM via AIAbstraction with grounding
  constraints.
"""

from __future__ import annotations

import re
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from sqlalchemy import create_engine, or_
from sqlalchemy.orm import Session, sessionmaker

logger = logging.getLogger(__name__)


@dataclass
class RAGRecord:
    """One retrieved record with provenance."""
    record_type: str
    record_id: str
    title: str
    relevance_snippet: str
    source_id: Optional[str] = None
    observation_period: Optional[str] = None
    source_freshness: Optional[str] = None


class LocalRAGEngine:
    """Deterministic RAG engine grounded in real persisted observations.

    Retrieval is keyword-based (no vector index required). Generation
    is template-based in MVP (no external LLM). Every answer exposes
    explicit provenance and freshness labels.
    """

    def __init__(self, db_url: str):
        self.db_url = db_url

    def retrieve(
        self,
        query: str,
        *,
        district: Optional[str] = None,
        sector: Optional[str] = None,
        source_id: Optional[str] = None,
        limit: int = 20,
    ) -> List[RAGRecord]:
        """Keyword-retrieve relevant persisted observations."""
        engine = create_engine(self.db_url)
        SessionLocal = sessionmaker(bind=engine)
        session: Session = SessionLocal()

        try:
            records: List[RAGRecord] = []
            tokens = [t for t in re.findall(r"[a-z0-9]{3,}", query.lower()) if t]

            # 1. Job postings
            from core.models.observation import JobPosting
            job_filters = []
            if district:
                job_filters.append(JobPosting.district == district)
            if sector:
                job_filters.append(JobPosting.sector == sector)
            if source_id:
                job_filters.append(JobPosting.source_id == source_id)

            jobs = session.query(JobPosting).filter(*job_filters).limit(limit).all()
            for job in jobs:
                searchable = f"{job.job_title or ''} {job.description or ''}".lower()
                if tokens and not any(t in searchable for t in tokens):
                    continue
                records.append(RAGRecord(
                    record_type="JOB_POSTING",
                    record_id=str(job.id),
                    title=job.job_title or "",
                    relevance_snippet=(job.description or "")[:300],
                    source_id=job.source_id,
                    observation_period=str(job.retrieved_at.date()) if job.retrieved_at else None,
                    source_freshness="HISTORICAL",
                ))

            # 2. Skill evidence — computed deterministically from persisted
            #    JobPosting rows (there is no skill_evidence table in Demand-X).
            from core.skills.ontology_matcher import SkillMatcher
            from core.skills.extractor import extract_job_skills

            if tokens:
                # Limit to in-window jobs that likely match (title/desc), then extract.
                matcher = SkillMatcher()
                for job in jobs[:limit]:
                    evidence, _unmatched = extract_job_skills(job, matcher)
                    for ev in evidence:
                        searchable = f"{ev.canonical_skill_name} {ev.source_skill_text} {ev.evidence_text}".lower()
                        if any(t in searchable for t in tokens):
                            records.append(RAGRecord(
                                record_type="SKILL_EVIDENCE",
                                record_id=ev.job_posting_id,
                                title=ev.canonical_skill_name,
                                relevance_snippet=(ev.evidence_text or "")[:300],
                                source_id=getattr(job, "source_id", None),
                                source_freshness="HISTORICAL",
                            ))

            # 3. District occupation demand
            from core.models.demand import DistrictOccupationDemand
            demand_rows = session.query(DistrictOccupationDemand).limit(limit).all()
            for row in demand_rows:
                searchable = f"{row.district} {row.occupation_id}".lower()
                if district and row.district and row.district.lower() != district.lower():
                    continue
                records.append(RAGRecord(
                    record_type="DISTRICT_OCCUPATION_DEMAND",
                    record_id=row.id,
                    title=f"{row.district} — {row.occupation_id}",
                    relevance_snippet=f"job_count={row.job_count}, apprenticeship_count={row.apprenticeship_count}",
                    observation_period=f"{row.observation_period_start} to {row.observation_period_end}" if row.observation_period_start else None,
                    source_freshness="HISTORICAL",
                ))

            return records[:limit]

        finally:
            session.close()

    def generate_answer(
        self,
        query: str,
        records: List[RAGRecord],
    ) -> Dict[str, Any]:
        """Deterministic template-based generation from retrieved evidence.

        No external LLM is called. Every answer exposes provenance.
        """
        if not records:
            return {
                "answer": (
                    f"No relevant persisted observations found for '{query}'. "
                    "This does NOT mean there is no data in the system — only "
                    "that no records matched the retrieval query."
                ),
                "confidence": "LOW",
                "source_freshness": "NO_DATA",
                "evidence_count": 0,
                "records": [],
                "disclaimer": (
                    "Evidence-grounded response from Demand-X local RAG. "
                    "No data has been fabricated. Skill shares are NOT demand scores."
                ),
            }

        grouped: Dict[str, List[RAGRecord]] = {}
        for r in records:
            grouped.setdefault(r.record_type, []).append(r)

        summary_parts: List[str] = []
        if "JOB_POSTING" in grouped:
            summary_parts.append(
                f"{len(grouped['JOB_POSTING'])} job posting(s) matched."
            )
        if "SKILL_EVIDENCE" in grouped:
            summary_parts.append(
                f"{len(grouped['SKILL_EVIDENCE'])} skill evidence record(s) matched."
            )
        if "DISTRICT_OCCUPATION_DEMAND" in grouped:
            summary_parts.append(
                f"{len(grouped['DISTRICT_OCCUPATION_DEMAND'])} district-occupation demand record(s) matched."
            )

        evidence_records = []
        for r in records[:10]:
            evidence_records.append({
                "type": r.record_type,
                "id": r.record_id,
                "title": r.title,
                "snippet": r.relevance_snippet,
                "source_freshness": r.source_freshness,
            })

        confidence = "MEDIUM" if len(records) >= 3 else "LOW"

        return {
            "answer": (
                f"Retrieved {len(records)} evidence record(s) for '{query}': "
                + "; ".join(summary_parts)
            ),
            "confidence": confidence,
            "source_freshness": "HISTORICAL",
            "evidence_count": len(records),
            "evidence": evidence_records,
            "records": evidence_records,
            "disclaimer": (
                "Evidence-grounded response from Demand-X local RAG. "
                "All data comes from persisted observations only. "
                "No statistics, supply figures, or salary data have been fabricated."
            ),
        }

    def query(
        self,
        question: str,
        *,
        district: Optional[str] = None,
        sector: Optional[str] = None,
        source_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """End-to-end retrieve + generate."""
        records = self.retrieve(
            question,
            district=district,
            sector=sector,
            source_id=source_id,
        )
        return self.generate_answer(question, records)