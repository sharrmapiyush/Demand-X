"""Skill Velocity — real demand-change signal over observed evidence windows.

Adapted from reference project's "SKILL_VELOCITY" concept (exported alongside
fabricated seed data) into Demand-X's evidence-first model.

Reference flaw REJECTED:
- The reference's SKILL_VELOCITY lives in memory on seed_data.py (fabricated)
  and is presented as live velocity. Here, velocity is computed strictly from
  persisted observation counts across two windows, carries a freshness class
  and observation period, and is only labeled when minimum evidence thresholds
  are met — otherwise INSUFFICIENT_DATA.

Deterministic, read-only. No invented scores.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

logger = logging.getLogger(__name__)

# ── Explicit thresholds (no hidden knobs) ─────────────────────────────────────

# Minimum distinct jobs per window before any velocity label is attempted.
MIN_WINDOW_JOBS = 3
# Minimum relative change to call a skill RISING / FALLING.
RISING_THRESHOLD = 0.25       # +25% observations
FALLING_THRESHOLD = 0.20      # -20% observations
# Never present a single observation window as a trend.
MIN_WINDOWS = 2

VELOCITY_LABELS = (
    "RISING",
    "STABLE",
    "FALLING",
    "INSUFFICIENT_DATA",
)


def _count_by_skill(
    session: Session,
    source_id: str,
    start: date,
    end: date,
    district: Optional[str] = None,
    sector: Optional[str] = None,
) -> Dict[str, int]:
    """Return {skill_id: distinct_job_count} for a window using persisted evidence.

    There is no persisted skill_evidence table in Demand-X: skill evidence is
    recomputed deterministically from JobPosting rows (source_skills, title,
    description) with the canonical 32-skill matcher — exactly as the
    skill_demand_engine does. This keeps velocity grounded in the same real
    observations and never fabricates counts.
    """
    from core.models.observation import JobPosting
    from core.skills.ontology_matcher import SkillMatcher
    from core.skills.extractor import extract_job_skills

    filters = [JobPosting.source_id == source_id]
    filters.append(
        JobPosting.retrieved_at >= datetime.combine(start, datetime.min.time())
    )
    filters.append(
        JobPosting.retrieved_at <= datetime.combine(end, datetime.max.time())
    )
    if district:
        filters.append(JobPosting.district == district)
    if sector:
        filters.append(JobPosting.sector == sector)

    jobs = session.query(JobPosting).filter(*filters).all()

    matcher = SkillMatcher()
    skill_job_ids: Dict[str, set] = {}
    for job in jobs:
        evidence, _unmatched = extract_job_skills(job, matcher)
        for ev in evidence:
            skill_job_ids.setdefault(ev.canonical_skill_id, set()).add(str(job.id))

    return {skill_id: len(job_ids) for skill_id, job_ids in skill_job_ids.items()}


def compute_skill_velocity(
    db_url: str,
    source_id: str,
    window_start: date,
    window_end: date,
    previous_start: date,
    previous_end: date,
    district: Optional[str] = None,
    sector: Optional[str] = None,
    rule_version: str = "skill-velocity-v1",
) -> Dict[str, Any]:
    """Compute per-skill velocity between two observation windows.

    Parameters
    ----------
    db_url, source_id : connection + source identity.
    window_start / window_end : the recent window (labeled "current").
    previous_start / previous_end : the baseline window.

    Returns a report dict with explicit thresholds, fresh labels, and
    per-skill rows: label, share in each window, delta share, counts.
    """
    engine = create_engine(db_url)
    SessionLocal = sessionmaker(bind=engine)
    session: Session = SessionLocal()

    try:
        current = _count_by_skill(
            session, source_id, window_start, window_end, district, sector
        )
        previous = _count_by_skill(
            session, source_id, previous_start, previous_end, district, sector
        )

        current_jobs = sum(current.values())
        previous_jobs = sum(previous.values())

        if current_jobs == 0 and previous_jobs == 0:
            freshness = "NO_DATA"
        elif previous_jobs == 0:
            freshness = "NEW_WINDOW"
        else:
            freshness = "PERIODIC"

        all_skills = sorted(set(current) | set(previous))
        rows: List[Dict[str, Any]] = []
        for skill_id in all_skills:
            cur = current.get(skill_id, 0)
            prev = previous.get(skill_id, 0)

            if cur < MIN_WINDOW_JOBS or prev < MIN_WINDOW_JOBS:
                label = "INSUFFICIENT_DATA"
            else:
                delta = (cur - prev) / prev
                if delta >= RISING_THRESHOLD:
                    label = "RISING"
                elif delta <= -FALLING_THRESHOLD:
                    label = "FALLING"
                else:
                    label = "STABLE"

            rows.append({
                "skill_id": skill_id,
                "window_distinct_jobs": cur,
                "previous_distinct_jobs": prev,
                "window_job_share": round(cur / current_jobs, 4) if current_jobs else None,
                "previous_job_share": round(prev / previous_jobs, 4) if previous_jobs else None,
                "relative_delta": round((cur - prev) / prev, 4) if prev else None,
                "velocity": label,
            })

        return {
            "rule_version": rule_version,
            "source_id": source_id,
            "district": district,
            "sector": sector,
            "current_window": {"start": window_start.isoformat(), "end": window_end.isoformat()},
            "previous_window": {"start": previous_start.isoformat(), "end": previous_end.isoformat()},
            "freshness": freshness,
            "thresholds": {
                "min_window_jobs": MIN_WINDOW_JOBS,
                "rising_delta_gt": RISING_THRESHOLD,
                "falling_delta_lt": -FALLING_THRESHOLD,
            },
            "total_window_jobs": current_jobs,
            "total_previous_jobs": previous_jobs,
            "skills": rows,
            "labels": list(VELOCITY_LABELS),
        }
    finally:
        session.close()