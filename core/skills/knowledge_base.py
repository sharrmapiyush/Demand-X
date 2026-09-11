"""Skill Knowledge Base & Candidate Discovery engine.

Pulls training-skill demand evidence **directly from persisted Naukri job
observations** (all 21,910), extracts canonical-skill evidence via the
deterministic matcher, aggregates per canonical skill, and discovers NEW
candidate skills from the data itself (never fabricated).

No LLM, no fuzzy matching, no DB persistence — pure deterministic analysis
that emits:

1. ``skill_extraction_report.json``   — full run summary + top-N tables
2. ``skill_extraction_summary.csv``   — one row per canonical skill w/ counts
3. ``naukri_skill_candidates.csv``    — new candidate skills discovered

New candidates are tagged ``NEEDS_REVIEW``; existing canonical skills keep
their seed verification status.  Nothing is "in demand" yet — this step only
extracts and normalizes skill evidence.
"""

from __future__ import annotations

import os
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from core.skills.extractor import extract_job_skills, split_source_skills
from core.skills.models import (
    ExtractionMethod,
    ExtractionSummaryRecord,
    MatchConfidence,
    SkillCandidate,
)
from core.skills.ontology_matcher import SkillMatcher, normalize


# ── Candidate discovery vocabulary ───────────────────────────────────────────

# High-signal tech/functional tokens harvested from the Naukri data reality:
# real skills (Java, SQL, PHP, Android, Python, .NET, ...) live in the TITLES
# and DESCRIPTIONS, while source_skills holds 50 functional-area categories.
# This vocabulary is used ONLY to flag candidate terms for review — it is not
# a "fabricated dictionary" of canonical skills.
TECH_TOKEN_RE = re.compile(
    r"\b("
    r"java|javascript|j2ee|js|python|php|sql|mysql|postgres|oracle|mssql|"
    r"dbms|nosql|mongo|c\+\+|c#|dotnet|\.net|go|rust|ruby|perl|kotlin|swift|"
    r"scala|typescript|html|css|ajax|jquery|angular|angularjs|react|vue|"
    r"node|node\.js|express|django|flask|spring|hibernate|struts|laravel|"
    r"wordpress|salesforce|sap|oracle|sharepoint|servicenow|dynamics|"
    r"android|ios|flutter|react native|xamarin|mobile|"
    r"aws|azure|gcp|cloud|docker|kubernetes|k8s|terraform|ansible|linux|unix|"
    r"windows server|hadoop|spark|kafka|airflow|tableau|power bi|excel|"
    r"ms office|word|outlook|powerpoint|tally|quickbooks|"
    r"machine learning|ml|deep learning|nlp|data science|data engineering|"
    r"sql server|api|rest api|microservices|web services|etl|"
    r"selenium|automation testing|manual testing|qa|devops|git|jenkins|"
    r"autocad|solidworks|cam|catia|creo|ansys|"
    r"adobe|photoshop|illustrator|coreldraw|after effects|premiere|"
    r"stm32|arduino|plc|scada|embedded|vlsi|pcb|"
    r"network|networking|ccna|firewall|cybersecurity|ethical hacking|"
    r"erp|sap fico|sap sd|sap mm|sap abap"
    r")\b",
    re.IGNORECASE,
)

# Words that appear in job titles but are NOT skills — used to suppress noise
# titles like "Java Developer", "Python Engineer".
_TITLE_NOISE = {
    "developer", "engineer", "engineeri", "senior", "junior", "lead", "leadership",
    "se", "smts", "analyst", "analysti", "consultant", "associate", "specialist",
    "manager", "management", "executive", "officer", "professional", "trainee",
    "intern", "internshi", "executive", "coordinator", "supervisor", "head",
    "director", "vp", "chief", "architect", "administrator", "admin", "technical",
    "technician", "technolog", "technology", "software", "applications", "application",
    "systems", "system", "service", "services", "support", "operations", "operation",
    "production", "quality", "testing", "test", "design", "designer", "graphic",
    "content", "campus", "pune", "india", "limited", "private", "company", "ltd",
    "pvt", "model", "numbers", "naukri", "job", "jobs", "vacancy", "walk-in",
    "opening", "positions", "position", "post", "posts", "jobtitle", "role", "roles",
    "account", "sales", "marketing", "business", "client", "customer", "customer",
    "internship", "fulltime", "parttime", "full", "time", "work", "office",
    "immediate", "urgent", "hiring", "required", "requirement", "employee", "staff",
    "field", "site", "sales", "marketing", "sales", "freshers", "fresher", "graduate",
    "graduate", "exe", "exec", "male", "female", "work", "worker",
}


# ── Report / summary helpers ─────────────────────────────────────────────────

def _build_summary_records(
    matcher: SkillMatcher,
    evidence: Sequence[Any],
) -> List[ExtractionSummaryRecord]:
    """Aggregate :class:`SkillEvidence` rows into per-skill summary records.

    Preserves seed ordering (canonical score order from skills_seed.json).
    """
    by_skill: Dict[str, ExtractionSummaryRecord] = {}
    for seed_id in matcher.canonical_ids:
        by_skill[seed_id] = ExtractionSummaryRecord(
            canonical_skill_id=seed_id,
            canonical_skill_name=matcher.get_skill(seed_id)["canonical_skill_name"]
            if matcher.get_skill(seed_id)
            else seed_id,
        )

    for ev in evidence:
        rec = by_skill.get(ev.canonical_skill_id)
        if rec is None:
            # Skill since removed from seed mid-run — keep defensively.
            rec = ExtractionSummaryRecord(ev.canonical_skill_id, ev.canonical_skill_name)
            by_skill[ev.canonical_skill_id] = rec
        rec.mention_count += 1
        if ev.evidence_type == "SOURCE_SKILL":
            rec.source_skill_mentions += 1
        elif ev.evidence_type == "JOB_TITLE":
            rec.title_mentions += 1
        else:
            rec.description_mentions += 1
        if ev.match_confidence == MatchConfidence.HIGH:
            rec.high_confidence_count += 1
        elif ev.match_confidence == MatchConfidence.MEDIUM:
            rec.medium_confidence_count += 1
        else:
            rec.low_confidence_count += 1

    # job_count = distinct job ids per skill
    job_ids_by_skill: Dict[str, set] = defaultdict(set)
    for ev in evidence:
        job_ids_by_skill[ev.canonical_skill_id].add(ev.job_posting_id)
    for skill_id, ids in job_ids_by_skill.items():
        if skill_id in by_skill:
            by_skill[skill_id].job_count = len(ids)

    # Seed-ordered where possible, then any extras
    ordered = [by_skill[sid] for sid in matcher.canonical_ids if sid in by_skill]
    extras = [
        rec for sid, rec in by_skill.items() if sid not in matcher.canonical_ids
    ]
    extras.sort(key=lambda r: (-r.job_count, r.canonical_skill_id))
    return ordered + extras


# ── Candidate discovery ──────────────────────────────────────────────────────

def _token_count_from_text(
    text_list: Sequence[Optional[str]],
    stopwords: Optional[set] = None,
) -> Counter:
    """Count word-level occurrences across a corpus of text lines."""
    counter: Counter = Counter()
    for text in text_list:
        if not text:
            continue
        for tok in re.findall(r"[A-Za-z][A-Za-z0-9.+#-]{1,}", text):
            token = tok.lower()
            if stopwords and token in stopwords:
                continue
            counter[token] += 1
    return counter


def discover_candidates(
    jobs: Sequence[Any],
    matcher: SkillMatcher,
    top_n: int = 30,
    min_mentions: int = 2,
) -> List[SkillCandidate]:
    """Discover NEW candidate skills from the raw data (deterministic).

    Strategy
    --------
    1. ``source_skills`` functional-area categories (split on separators)
       that did NOT resolve to an existing canonical skill become candidates.
       Category is deterministic, observable, and cannot be fabricated.
    2. Tech/functional tokens (from ``TECH_TOKEN_RE``) found in job titles/
       descriptions become candidates, deduped by normalized form, ranked by
       distinct-job count.

    Candidates are NOT canonicalized into the 8-skill ontology — they are
    surfaced for human review with ``NEEDS_REVIEW`` status.
    """
    source_skill_counter: Counter = Counter()
    seen_source_skills: Dict[str, set] = defaultdict(set)  # norm -> job ids
    source_skill_raw_forms: Dict[str, set] = defaultdict(set)  # norm -> raw spellings
    for job in jobs:
        job_id = str(job.id)
        for seg in split_source_skills(getattr(job, "source_skills", None)):
            norm_seg = normalize(seg)
            if not norm_seg or matcher.lookup_skill(norm_seg):
                continue  # skip matched skills, empty, or junk
            source_skill_counter[norm_seg] += 1
            seen_source_skills[norm_seg].add(job_id)
            source_skill_raw_forms[norm_seg].add(seg)

    tech_counter: Counter = Counter()
    seen_tech: Dict[str, set] = defaultdict(set)
    tech_raw_forms: Dict[str, set] = defaultdict(set)
    for job in jobs:
        job_id = str(job.id)
        title = getattr(job, "job_title", None) or ""
        desc = getattr(job, "description", None) or ""
        for m in TECH_TOKEN_RE.finditer(title + " " + desc):
            cand = normalize(m.group(1))
            if not cand or cand in _TITLE_NOISE:
                continue
            if matcher.lookup_skill(cand):
                continue  # already canonical — not a new candidate
            tech_counter[cand] += 1
            seen_tech[cand].add(job_id)
            tech_raw_forms[cand].add(m.group(1))

    # Combine and dedupe by candidate name, preserving observed raw spellings.
    combined: Dict[str, SkillCandidate] = {}
    for norm_seg, count in source_skill_counter.items():
        if count < min_mentions:
            continue
        combined[norm_seg] = SkillCandidate(
            candidate_skill=norm_seg,
            observed_forms=", ".join(sorted(source_skill_raw_forms[norm_seg])[:5])
            or norm_seg,
            job_count=len(seen_source_skills[norm_seg]),
            recommended_action="SOURCE_SKILL_CATEGORY",
        )
    for cand, count in tech_counter.items():
        if count < min_mentions:
            continue
        existing = combined.get(cand)
        if existing:
            existing.job_count = max(existing.job_count, len(seen_tech[cand]))
            existing.mention_count = max(existing.mention_count, count)
            existing.observed_forms = (
                existing.observed_forms
                + " | "
                + ", ".join(sorted(tech_raw_forms[cand])[:5])
            )
            existing.example_source_skills = (
                existing.example_source_skills or ""
            ) + " | title/desc tech token"
        else:
            combined[cand] = SkillCandidate(
                candidate_skill=cand,
                observed_forms=", ".join(sorted(tech_raw_forms[cand])[:5]) or cand,
                job_count=len(seen_tech[cand]),
                mention_count=count,
                example_source_skills="title/desc tech token",
                recommended_action="TITLE_OR_DESC_TOKEN",
            )

    ranked = sorted(
        combined.values(), key=lambda c: (-c.job_count, c.candidate_skill)
    )
    return ranked[:top_n]


# ── Main engine ──────────────────────────────────────────────────────────────

def build_skill_knowledge_base(
    db_url: Optional[str] = None,
    matcher: Optional[SkillMatcher] = None,
    source_id: Optional[str] = None,
    top_candidate_n: int = 30,
    min_candidate_mentions: int = 2,
) -> Dict[str, Any]:
    """Build the skill knowledge base from persisted job observations.

    Returns a report dict; does NOT write files, does NOT modify any job rows.
    """
    # Imported lazily so the module stays importable (and testable) without
    # the full app/DB dependency chain.
    from core.models.observation import JobPosting

    engine = create_engine(db_url or os.environ["DATABASE_URL"])
    SessionLocal = sessionmaker(bind=engine)
    session: Session = SessionLocal()

    try:
        # Query job postings in chunks to bound memory
        all_jobs: List[JobPosting] = []
        query = session.query(
            JobPosting.id,
            JobPosting.job_title,
            JobPosting.description,
            JobPosting.source_skills,
        )
        if source_id:
            query = query.filter(JobPosting.source_id == source_id)
        for row in query.yield_per(1000):
            all_jobs.append(row)

        matcher = matcher or SkillMatcher()
        total_jobs = len(all_jobs)
        jobs_with_evidence = 0
        evidence: List[Any] = []
        unmatched: List[Any] = []

        for job in all_jobs:
            ev, unm = extract_job_skills(job, matcher)
            evidence.extend(ev)
            unmatched.extend(unm)
            if ev:
                jobs_with_evidence += 1

        # ── Aggregate ─────────────────────────────────────────────────────
        summary_records = _build_summary_records(matcher, evidence)

        # Jobs-with-skill caps:
        jobs_with_any = len({ev.job_posting_id for ev in evidence})

        # Confidence distribution: HIGH/MEDIUM/LOW mention counts
        high = sum(1 for ev in evidence if ev.match_confidence == MatchConfidence.HIGH)
        med = sum(1 for ev in evidence if ev.match_confidence == MatchConfidence.MEDIUM)
        low = sum(1 for ev in evidence if ev.match_confidence == MatchConfidence.LOW)

        # STEP-110 source policy: SOURCE_SKILL evidence = source-category
        # evidence (functional area), NOT a technical-skill claim.  JOB_TITLE /
        # JOB_DESCRIPTION are the primary technical-skill signals.
        # The invariant that must hold:
        #   total_mentions_observed == matched_mentions + unmatched_mentions
        matched_mentions = sum(
            1 for ev in evidence if ev.evidence_type in ("JOB_TITLE", "JOB_DESCRIPTION")
        )
        unmatched_mentions = len(unmatched)
        total_mentions_observed = matched_mentions + unmatched_mentions

        # ── Candidate discovery ───────────────────────────────────────────
        candidates = discover_candidates(
            all_jobs,
            matcher,
            top_n=top_candidate_n,
            min_mentions=min_candidate_mentions,
        )

        # ── Unmatched phrases (top 30 by frequency) ───────────────────────
        unmatched_counter = Counter(um.normalized_text for um in unmatched)
        top_unmatched = [
            {"phrase": phrase, "count": count}
            for phrase, count in unmatched_counter.most_common(30)
            if phrase
        ]

        # ── Report ────────────────────────────────────────────────────────
        report: Dict[str, Any] = {
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "engine": "skill-knowledge-base-v1",
            "rule_version": "mvp-v1-no-fuzzy-match",
            "extraction_methods_used": [m.value for m in ExtractionMethod],
            "input": {
                "source_id": source_id,
                "jobs_processed": total_jobs,
                "jobs_with_source_skills": sum(
                    1
                    for j in all_jobs
                    if getattr(j, "source_skills", None)
                    and getattr(j, "source_skills", "").strip()
                ),
                "jobs_with_description": sum(
                    1
                    for j in all_jobs
                    if getattr(j, "description", None)
                    and getattr(j, "description", "").strip()
                ),
            },
            "extraction": {
                "total_evidence_rows": len(evidence),
                "unique_evidence_skills": len({
                    ev.canonical_skill_id for ev in evidence
                }),
                "jobs_with_skill_evidence": jobs_with_any,
                "unmatched_mentions": unmatched_mentions,
                "matched_mentions": matched_mentions,
                "total_mentions_observed": total_mentions_observed,
                "metric_invariant": (
                    "total_mentions_observed == matched_mentions + unmatched_mentions"
                ),
                "mention_confidence": {
                    "HIGH": high,
                    "MEDIUM": med,
                    "LOW": low,
                },
                "source_policy": (
                    "source_skills evidence = SOURCE_CATEGORY (functional area); "
                    "JOB_TITLE / JOB_DESCRIPTION evidence = TECHNICAL_SKILL"
                ),
            },
            "skills": {
                "canonical_seed_count": len(matcher.canonical_ids),
                "skills_with_evidence": len({
                    ev.canonical_skill_id for ev in evidence
                }),
                "new_candidates_discovered": len(candidates),
            },
            "top_skills_by_job_count": [
                {
                    "skill_id": rec.canonical_skill_id,
                    "skill_name": rec.canonical_skill_name,
                    "job_count": rec.job_count,
                    "mention_count": rec.mention_count,
                    "source_skill_mentions": rec.source_skill_mentions,
                    "title_mentions": rec.title_mentions,
                    "description_mentions": rec.description_mentions,
                    "high_confidence": rec.high_confidence_count,
                    "medium_confidence": rec.medium_confidence_count,
                    "low_confidence": rec.low_confidence_count,
                }
                for rec in sorted(
                    summary_records,
                    key=lambda r: (-r.job_count, r.canonical_skill_id),
                )
            ],
            "top_unmatched_phrases": top_unmatched,
            "top_unmatched_technical_phrases": [
                {
                    "phrase": c.candidate_skill,
                    "mention_count": c.mention_count,
                    "distinct_jobs": c.job_count,
                    "observed_forms": c.observed_forms,
                }
                for c in candidates
                if c.recommended_action == "TITLE_OR_DESC_TOKEN"
            ][:30],
            "top_new_candidates": [
                {
                    "candidate_skill": c.candidate_skill,
                    "job_count": c.job_count,
                    "mention_count": c.mention_count,
                    "recommended_action": c.recommended_action,
                    "observed_forms": c.observed_forms,
                    "example_source_skills": c.example_source_skills,
                }
                for c in candidates[:20]
            ],
            "evidence_examples_source_category_vs_technical": {
                "description": (
                    "Demonstrates the source-policy: SOURCE_SKILL evidence "
                    "reports functional-area categories only; TITLE/DESC evidence "
                    "carries the real technical-skill signal."
                ),
                "source_category_examples": [
                    {
                        "job_id": ev.job_posting_id,
                        "source_skill_text": ev.source_skill_text,
                        "canonical_skill_id": ev.canonical_skill_id,
                        "canonical_skill_name": ev.canonical_skill_name,
                        "extraction_method": ev.extraction_method,
                        "match_confidence": ev.match_confidence,
                        "evidence_type": ev.evidence_type,
                        "evidence_text": ev.evidence_text,
                    }
                    for ev in evidence
                    if ev.evidence_type == "SOURCE_SKILL"
                ][:10],
                "technical_skill_examples": [
                    {
                        "job_id": ev.job_posting_id,
                        "source_skill_text": ev.source_skill_text,
                        "canonical_skill_id": ev.canonical_skill_id,
                        "canonical_skill_name": ev.canonical_skill_name,
                        "extraction_method": ev.extraction_method,
                        "match_confidence": ev.match_confidence,
                        "evidence_type": ev.evidence_type,
                        "evidence_text": ev.evidence_text,
                    }
                    for ev in evidence
                    if ev.evidence_type in ("JOB_TITLE", "JOB_DESCRIPTION")
                ][:10],
            },
            "summary": {
                "verification_status_policy": (
                    "existing canonical skills keep seed verification_status; "
                    "new candidates = NEEDS_REVIEW"
                ),
                "demand_score": None,  # NOT computed yet — extraction only
                "metrics_invariant": (
                    f"{total_mentions_observed} total_mentions_observed == "
                    f"{matched_mentions} matched_mentions (JOB_TITLE/JOB_DESCRIPTION) "
                    f"+ {unmatched_mentions} unmatched_mentions (unresolved "
                    f"SOURCE_SKILL categories)"
                ),
                "matched_mentions": matched_mentions,
                "unmatched_mentions": unmatched_mentions,
                "total_mentions_observed": total_mentions_observed,
            },
        }

        return report
    finally:
        session.close()
        engine.dispose()