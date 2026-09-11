"""Skill Demand Engine — per-skill demand from persisted Naukri job observations.

Reads SkillEvidence rows (extracted by the deterministic matcher) and JobPosting
rows, then aggregates per-skill demand metrics:

  - skill_id, skill_name
  - distinct_job_count
  - mention_count
  - district, sector, occupation (when known)
  - period (retrieved_at window)
  - source (source_id)
  - confidence breakdown (HIGH / MEDIUM / LOW)

The demand metric is ``normalized_distinct_job_count`` — the fraction of
source-filtered jobs that carry evidence of each skill.  No invented scoring.

Design principles
-----------------
- Deterministic: same inputs → same output (no LLM, no randomness).
- Read-only on DB: queries JobPosting + SkillEvidence, writes nothing to DB.
- Transparent thresholds: all configuration is explicit at module level.
- No extrapolation: DVET single-institute data is never projected to all of Pune.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from collections import defaultdict
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

logger = logging.getLogger(__name__)

# ── Configuration (transparent, no hidden thresholds) ────────────────────────

DEFAULT_RULE_VERSION = "mvp-v1-no-score"
DEFAULT_SOURCE_ID = "naukri-historical-promptcloud"

# ── Ontology load ────────────────────────────────────────────────────────────

_ONTOLOGY_DIR = os.path.join(os.path.dirname(__file__), "..", "ontology")


def _load_skills_seed() -> Dict[str, Dict[str, Any]]:
    """Load canonical skills seed → {skill_id: {canonical_skill_name, ...}}."""
    path = os.path.join(_ONTOLOGY_DIR, "skills_seed.json")
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return {s["skill_id"]: s for s in data.get("skills", [])}


def _load_occupations_seed() -> Dict[str, Dict[str, Any]]:
    """Load occupations seed → {occupation_id: {...}}."""
    path = os.path.join(_ONTOLOGY_DIR, "occupations_seed.json")
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return {o["occupation_id"]: o for o in data.get("occupations", [])}


def _load_trade_skill_mappings() -> List[Dict[str, Any]]:
    """Load trade→skill mappings (DVET supply side)."""
    path = os.path.join(_ONTOLOGY_DIR, "trade_skill_mapping.json")
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("mappings", [])


def _load_trade_occupation_mappings() -> List[Dict[str, Any]]:
    """Load trade→occupation mappings."""
    path = os.path.join(_ONTOLOGY_DIR, "trade_occupation_mapping.json")
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("mappings", [])


# ── Run ID generation (deterministic) ────────────────────────────────────────

def generate_run_id(
    rule_version: str,
    district: str,
    source_id: str,
    start_date: date,
    end_date: date,
) -> str:
    """Deterministic SHA-256 run_id."""
    raw = (
        f"skill-demand:{rule_version}:{district.lower().strip()}"
        f":{source_id}:{start_date.isoformat()}:{end_date.isoformat()}"
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:64]


# ── Main engine ──────────────────────────────────────────────────────────────

def calculate_skill_demand(
    db_url: str,
    source_id: str = DEFAULT_SOURCE_ID,
    district: Optional[str] = None,
    sector: Optional[str] = None,
    observation_period_start: Optional[date] = None,
    observation_period_end: Optional[date] = None,
    rule_version: str = DEFAULT_RULE_VERSION,
) -> Dict[str, Any]:
    """Calculate per-skill demand from persisted job observations.

    Parameters
    ----------
    db_url : str
        SQLAlchemy connection string.
    source_id : str
        Only observations from this source.
    district : str, optional
        Restrict to a single district.
    sector : str, optional
        Restrict observations to this sector.
    observation_period_start / end : date, optional
        Window compared to ``retrieved_at``.
    rule_version : str
        Calculation rule identifier.

    Returns
    -------
    dict with run metadata, per-skill demand rows, and report counters.
    """
    from core.models.observation import JobPosting

    engine = create_engine(db_url)
    SessionLocal = sessionmaker(bind=engine)
    session: Session = SessionLocal()

    try:
        skills_seed = _load_skills_seed()
        occupations_seed = _load_occupations_seed()
        trade_skill_maps = _load_trade_skill_mappings()
        trade_occ_maps = _load_trade_occupation_mappings()

        # ── Query eligible job postings ──────────────────────────────────────
        filters = [JobPosting.source_id == source_id]
        if district:
            filters.append(JobPosting.district == district)
        if sector:
            filters.append(JobPosting.sector == sector)
        if observation_period_start:
            filters.append(
                JobPosting.retrieved_at
                >= datetime.combine(observation_period_start, datetime.min.time())
            )
        if observation_period_end:
            filters.append(
                JobPosting.retrieved_at
                <= datetime.combine(observation_period_end, datetime.max.time())
            )

        jobs = session.query(JobPosting).filter(*filters).all()
        total_jobs = len(jobs)
        job_ids = {str(j.id) for j in jobs}

        # ── Extract skill evidence from job postings ─────────────────────────
        # Reuse the deterministic matcher directly per job.
        from core.skills.ontology_matcher import SkillMatcher
        from core.skills.extractor import extract_job_skills

        matcher = SkillMatcher()
        evidence_rows: List[Dict[str, Any]] = []

        for job in jobs:
            ev_list, _unmatched = extract_job_skills(job, matcher)
            for ev in ev_list:
                evidence_rows.append({
                    "job_posting_id": ev.job_posting_id,
                    "skill_id": ev.canonical_skill_id,
                    "skill_name": ev.canonical_skill_name,
                    "evidence_type": ev.evidence_type,
                    "match_confidence": ev.match_confidence.value,
                    "extraction_method": ev.extraction_method.value,
                })

        # ── Aggregate per-skill ──────────────────────────────────────────────
        skill_jobs: Dict[str, set] = defaultdict(set)
        skill_mentions: Dict[str, int] = defaultdict(int)
        skill_confidence: Dict[str, Dict[str, int]] = defaultdict(
            lambda: {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
        )
        skill_evidence_type: Dict[str, Dict[str, int]] = defaultdict(
            lambda: {"TITLE": 0, "DESCRIPTION": 0, "SOURCE_SKILL": 0}
        )

        for ev in evidence_rows:
            sid = ev["skill_id"]
            skill_jobs[sid].add(ev["job_posting_id"])
            skill_mentions[sid] += 1
            skill_confidence[sid][ev["match_confidence"]] += 1
            if ev["evidence_type"] == "JOB_TITLE":
                skill_evidence_type[sid]["TITLE"] += 1
            elif ev["evidence_type"] == "JOB_DESCRIPTION":
                skill_evidence_type[sid]["DESCRIPTION"] += 1
            else:
                skill_evidence_type[sid]["SOURCE_SKILL"] += 1

        # ── Build demand rows ────────────────────────────────────────────────
        period_start = observation_period_start or date.min
        period_end = observation_period_end or date.max
        run_id = generate_run_id(
            rule_version, district or "ALL", source_id, period_start, period_end
        )

        demand_rows = []
        for sid in sorted(skills_seed.keys()):
            info = skills_seed[sid]
            distinct_count = len(skill_jobs.get(sid, set()))
            mention_count = skill_mentions.get(sid, 0)
            normalized = (
                round(distinct_count / total_jobs, 6) if total_jobs > 0 else 0.0
            )
            demand_rows.append({
                "skill_id": sid,
                "skill_name": info.get("canonical_skill_name", sid),
                "distinct_job_count": distinct_count,
                "mention_count": mention_count,
                "normalized_distinct_job_count": normalized,
                "confidence": skill_confidence.get(sid, {"HIGH": 0, "MEDIUM": 0, "LOW": 0}),
                "evidence_type_breakdown": skill_evidence_type.get(
                    sid, {"TITLE": 0, "DESCRIPTION": 0, "SOURCE_SKILL": 0}
                ),
                "verification_status": info.get("verification_status", "NEEDS_REVIEW"),
            })

        demand_rows.sort(key=lambda r: (-r["distinct_job_count"], r["skill_id"]))

        # ── DVET supply summary (read-only, no extrapolation) ────────────────
        dvet_supply = _build_dvet_supply_summary(
            trade_skill_maps, trade_occ_maps, skills_seed, occupations_seed
        )

        # ── Report ───────────────────────────────────────────────────────────
        skills_with_evidence = sum(1 for r in demand_rows if r["distinct_job_count"] > 0)

        return {
            "run_id": run_id,
            "rule_version": rule_version,
            "source_id": source_id,
            "district": district,
            "sector": sector,
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
            "status": "COMPLETED",
            "total_jobs_evaluated": total_jobs,
            "jobs_with_skill_evidence": len(
                {ev["job_posting_id"] for ev in evidence_rows}
            ),
            "skills_with_evidence": skills_with_evidence,
            "total_evidence_rows": len(evidence_rows),
            "dvet_supply_summary": dvet_supply,
            "demand_rows": demand_rows,
        }

    finally:
        session.close()
        engine.dispose()


def _build_dvet_supply_summary(
    trade_skill_maps: List[Dict[str, Any]],
    trade_occ_maps: List[Dict[str, Any]],
    skills_seed: Dict[str, Dict[str, Any]],
    occupations_seed: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    """Build DVET supply summary from trade→skill and trade→occupation mappings.

    This is READ-ONLY — reports what the DVET snapshot covers. It does NOT
    extrapolate from the single ITI Haveli institute to all of Pune.
    """
    # Trade→Skill mapping: which canonical skills have DVET supply evidence
    skills_with_supply: Dict[str, List[str]] = defaultdict(list)
    for m in trade_skill_maps:
        skill_id = m.get("skill_id")
        trade = m.get("canonical_trade_name")
        if skill_id and trade:
            skills_with_supply[skill_id].append(trade)

    # Trade→Occupation mapping: which occupations have DVET supply evidence
    occs_with_supply: Dict[str, List[str]] = defaultdict(list)
    for m in trade_occ_maps:
        occ_id = m.get("occupation_id")
        trade = m.get("canonical_trade_name")
        if occ_id and trade:
            occs_with_supply[occ_id].append(trade)

    total_trades = len({m.get("canonical_trade_name") for m in trade_skill_maps})
    total_intake = 0

    # Load raw DVET snapshot for intake numbers
    snapshot_path = os.path.join(
        os.path.dirname(__file__), "..", "..",
        "data", "raw", "dvet_pune", "dvet_pune_haveli_verified_snapshot.json",
    )
    if os.path.exists(snapshot_path):
        with open(snapshot_path, encoding="utf-8") as f:
            snap = json.load(f)
        for inst in snap.get("institutes", []):
            for t in inst.get("trades", []):
                try:
                    total_intake += int(t.get("intake", 0))
                except (ValueError, TypeError):
                    pass

    return {
        "snapshot_source": "dvet-pune-haveli-verified-snapshot",
        "institute_count": 1,
        "institute_name": "Industrial Training Institute, Haveli",
        "total_trades": total_trades,
        "total_intake": total_intake,
        "skills_with_supply_evidence": {
            sid: {"trades": trades, "count": len(trades)}
            for sid, trades in sorted(skills_with_supply.items())
        },
        "occupations_with_supply_evidence": {
            occ_id: {"trades": trades, "count": len(trades)}
            for occ_id, trades in sorted(occs_with_supply.items())
        },
        "extrapolation_note": (
            "Supply data covers ONLY ITI Haveli (1 institute, "
            f"{total_trades} trades, {total_intake} intake). "
            "NOT extrapolated to all of Pune."
        ),
    }
