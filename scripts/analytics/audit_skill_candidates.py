"""STEP 1+2 — Audit Naukri skill candidates and emit an ontology-review CSV.

Reads the persisted Naukri job observations and the existing canonical skill
ontology, re-discovers candidate technical tokens (same deterministic
vocabulary as the extraction engine, this time over the FULL token set so
Python / C# / .NET / Android / ... can be evaluated even below the top-30
threshold), classifies each candidate against a hand-validated decision
table, and writes:

    data/analytics/skill_ontology_review.csv

Columns (per task spec):
    candidate_skill, observed_forms, distinct_jobs, mention_count,
    current_status, recommended_action, canonical_skill_name, canonical_skill_id,
    reason, confidence

Classification vocabulary (deterministic, evidence-first):
    CREATE_CANONICAL_SKILL   → becomes a new canonical skill (NEEDS_REVIEW)
    MAP_TO_EXISTING_SKILL    → collapses into an existing canonical skill
    KEEP_SEPARATE            → real competency but intentionally NOT merged
    NOT_A_SKILL              → functional-area tag / business function / noise
    NEEDS_REVIEW             → plausible but requires human confirmation

Read-only: never modifies job_postings / demand tables / the seed ontology.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import logging

logging.basicConfig(level=logging.INFO)

from sqlalchemy import create_engine

from core.skills.ontology_matcher import SkillMatcher, normalize
from core.skills.extractor import split_source_skills

# Reuse the extraction engine's tech vocabulary so the audit is consistent
# with what the engine already reports.
from core.skills.knowledge_base import TECH_TOKEN_RE, _TITLE_NOISE


# ── Classification decision table ────────────────────────────────────────────
# Every entry is a (normalized candidate → decision) record.  `confidence` is
# the strength of the EVIDENCE (HIGH = many distinct jobs + safe normalization),
# not a model probability.
#
# CREATE_CANONICAL_SKILL entries carry the new canonical skill id + name and
# the safe alias set to fold into skills_seed.json.
CREATE_DECISIONS: Dict[str, Dict[str, Any]] = {
    "java": {
        "action": "CREATE_CANONICAL_SKILL",
        "canonical_skill_id": "SKL-DEV-JAVA-01",
        "canonical_skill_name": "Java Programming",
        "aliases": ["Java", "Core Java", "Java SE", "J2SE"],
        "confidence": "HIGH",
        "reason": (
            "2,433 distinct jobs / 6,230 mentions; unambiguous programming "
            "language; observed forms normalize safely (Java, JAVA, java). "
            "Distinct from JavaScript — NEVER merged."
        ),
    },
    "javascript": {
        "action": "CREATE_CANONICAL_SKILL",
        "canonical_skill_id": "SKL-DEV-JAVASCRIPT-01",
        "canonical_skill_name": "JavaScript",
        "aliases": ["Javascript", "JavaScript", "ES6", "ECMAScript"],
        "confidence": "HIGH",
        "reason": (
            "1,693 distinct jobs / 3,217 mentions; distinct language from Java "
            "(word-boundary protected in matcher). Safe casing normalization."
        ),
    },
    "j2ee": {
        "action": "CREATE_CANONICAL_SKILL",
        "canonical_skill_id": "SKL-DEV-J2EE-01",
        "canonical_skill_name": "Java EE / J2EE",
        "aliases": ["J2EE", "Java EE", "Enterprise Java"],
        "confidence": "MEDIUM",
        "reason": (
            "784 distinct jobs / 1,515 mentions; enterprise-Java platform. "
            "Kept as a distinct competency from Java Programming for demand "
            "granularity; human review recommended (could later fold into Java)."
        ),
    },
    "php": {
        "action": "CREATE_CANONICAL_SKILL",
        "canonical_skill_id": "SKL-DEV-PHP-01",
        "canonical_skill_name": "PHP Programming",
        "aliases": ["PHP", "Php", "PHP5", "PHP 7"],
        "confidence": "HIGH",
        "reason": (
            "1,069 distinct jobs / 2,588 mentions; unambiguous web language; "
            "casing normalization safe."
        ),
    },
    "sql": {
        "action": "CREATE_CANONICAL_SKILL",
        "canonical_skill_id": "SKL-DB-SQL-01",
        "canonical_skill_name": "SQL & Query Languages",
        "aliases": ["SQL", "Structured Query Language", "Sql"],
        "confidence": "HIGH",
        "reason": (
            "2,330 distinct jobs / 4,886 mentions; the query LANGUAGE itself. "
            "Never merged with specific DBMS products (Oracle/MySQL)."
        ),
    },
    "oracle": {
        "action": "CREATE_CANONICAL_SKILL",
        "canonical_skill_id": "SKL-DB-ORACLE-01",
        "canonical_skill_name": "Oracle Database",
        "aliases": ["Oracle", "Oracle DB", "Oracle Database", "OracleSQL"],
        "confidence": "HIGH",
        "reason": (
            "1,453 distinct jobs / 4,319 mentions; DBMS product, distinct from "
            "SQL-the-language. Casing normalization safe."
        ),
    },
    "mysql": {
        "action": "CREATE_CANONICAL_SKILL",
        "canonical_skill_id": "SKL-DB-MYSQL-01",
        "canonical_skill_name": "MySQL",
        "aliases": ["MySQL", "MySql", "MYSQL", "MySQL Server"],
        "confidence": "MEDIUM",
        "reason": (
            "748 distinct jobs / 1,345 mentions; DBMS product, distinct from "
            "both SQL and Oracle."
        ),
    },
    "html": {
        "action": "CREATE_CANONICAL_SKILL",
        "canonical_skill_id": "SKL-WEB-HTML-01",
        "canonical_skill_name": "HTML",
        "aliases": ["HTML5", "Html"],
        "confidence": "HIGH",
        "reason": (
            "1,395 distinct jobs / 2,483 mentions; markup language. Split from "
            "CSS — different concern (structure vs presentation)."
        ),
    },
    "css": {
        "action": "CREATE_CANONICAL_SKILL",
        "canonical_skill_id": "SKL-WEB-CSS-01",
        "canonical_skill_name": "CSS",
        "aliases": ["CSS3", "Css", "Cascading Style Sheets"],
        "confidence": "HIGH",
        "reason": (
            "1,096 distinct jobs / 1,767 mentions; stylesheet language. Split "
            "from HTML — different concern."
        ),
    },
    "jquery": {
        "action": "CREATE_CANONICAL_SKILL",
        "canonical_skill_id": "SKL-WEB-JQUERY-01",
        "canonical_skill_name": "jQuery",
        "aliases": ["JQuery", "Jquery"],
        "confidence": "MEDIUM",
        "reason": (
            "1,073 distinct jobs / 1,900 mentions; JS library with strong "
            "independent job-market signal. Distinct from JavaScript core; "
            "human review recommended (could later fold into JavaScript)."
        ),
    },
    "ajax": {
        "action": "CREATE_CANONICAL_SKILL",
        "canonical_skill_id": "SKL-WEB-AJAX-01",
        "canonical_skill_name": "AJAX",
        "aliases": ["Ajax", "Ajax JavaScript"],
        "confidence": "MEDIUM",
        "reason": (
            "727 distinct jobs / 1,207 mentions; real-time web technique. "
            "Distinct from JavaScript core; NEEDS_REVIEW on long-term placement."
        ),
    },
    "excel": {
        "action": "CREATE_CANONICAL_SKILL",
        "canonical_skill_id": "SKL-OFFICE-EXCEL-01",
        "canonical_skill_name": "Microsoft Excel",
        "aliases": ["Excel", "MS Excel", "Advanced Excel"],
        "confidence": "HIGH",
        "reason": (
            "1,302 distinct jobs / 1,663 mentions; high-value spreadsheet "
            "competency. Kept distinct from generic Office Productivity so Excel "
            "demand is measurable on its own."
        ),
    },
    "erp": {
        "action": "CREATE_CANONICAL_SKILL",
        "canonical_skill_id": "SKL-OFFICE-ERP-01",
        "canonical_skill_name": "Enterprise Resource Planning (ERP)",
        "aliases": ["ERP", "Erp"],
        "confidence": "MEDIUM",
        "reason": (
            "1,088 distinct jobs / 1,628 mentions; real functional competency. "
            "Broad label — product-level skills (SAP, Oracle) stay separate."
        ),
    },
    "sap": {
        "action": "CREATE_CANONICAL_SKILL",
        "canonical_skill_id": "SKL-SAP-01",
        "canonical_skill_name": "SAP",
        "aliases": ["SAP ERP", "Sap"],
        "confidence": "HIGH",
        "reason": (
            "847 distinct jobs / 3,956 mentions; dominant ERP product in the "
            "dataset. Distinct from generic ERP."
        ),
    },
    "linux": {
        "action": "CREATE_CANONICAL_SKILL",
        "canonical_skill_id": "SKL-INFRA-LINUX-01",
        "canonical_skill_name": "Linux",
        "aliases": ["Linux Admin", "Linux Administration", "GNU/Linux"],
        "confidence": "HIGH",
        "reason": (
            "1,186 distinct jobs / 2,238 mentions; server OS competency. Kept "
            "separate from Unix (same OS family but distinct ecosystems)."
        ),
    },
    "unix": {
        "action": "CREATE_CANONICAL_SKILL",
        "canonical_skill_id": "SKL-INFRA-UNIX-01",
        "canonical_skill_name": "Unix",
        "aliases": ["UNIX", "Unix Shell", "Solaris"],
        "confidence": "MEDIUM",
        "reason": (
            "802 distinct jobs / 1,357 mentions; distinct from Linux. Human "
            "review recommended on whether Unix/Linux should eventually share a "
            "family — kept separate for now."
        ),
    },
    "cloud": {
        "action": "CREATE_CANONICAL_SKILL",
        "canonical_skill_id": "SKL-INFRA-CLOUD-01",
        "canonical_skill_name": "Cloud Computing",
        "aliases": ["Cloud", "Cloud Computing", "Cloud Platforms"],
        "confidence": "MEDIUM",
        "reason": (
            "1,040 distinct jobs / 2,090 mentions; real competency but broad "
            "label. Human review recommended — product-level (AWS/Azure/GCP) "
            "stay separate."
        ),
    },
    "network": {
        "action": "CREATE_CANONICAL_SKILL",
        "canonical_skill_id": "SKL-INFRA-NETWORK-01",
        "canonical_skill_name": "Computer Networking",
        "aliases": ["Network", "Networking", "Computer Networking",
                    "Network Administration", "LAN", "WAN"],
        "confidence": "MEDIUM",
        "reason": (
            "network (2,036 jobs) + networking (1,445 jobs) are the same "
            "competency family and merge SAFELY into one canonical skill — "
            "unlike technologies in different families."
        ),
    },
    "web services": {
        "action": "CREATE_CANONICAL_SKILL",
        "canonical_skill_id": "SKL-INFRA-WEBSERVICES-01",
        "canonical_skill_name": "Web Services & APIs",
        "aliases": ["Web Services", "Web Service", "webservice"],
        "confidence": "MEDIUM",
        "reason": (
            "1,009 distinct jobs / 1,491 mentions; inter-system communication "
            "competency. Distinct from REST API (unobserved at threshold). "
            "NEEDS_REVIEW on scope."
        ),
    },
    "qa": {
        "action": "CREATE_CANONICAL_SKILL",
        "canonical_skill_id": "SKL-QA-01",
        "canonical_skill_name": "Software Testing & QA",
        "aliases": ["QA", "Quality Assurance", "Software Testing",
                    "Qa Testing"],
        "confidence": "MEDIUM",
        "reason": (
            "872 distinct jobs / 1,657 mentions; testing competency cluster. "
            "Human review recommended — 'QA' token is role-ambiguous; automation/"
            "manual-testing sub-skills stay in the same cluster."
        ),
    },
}


# Candidates that conceptually belong under an EXISTING canonical skill.
MAP_DECISIONS: Dict[str, Dict[str, Any]] = {
    "word": {
        "action": "MAP_TO_EXISTING_SKILL",
        "canonical_skill_id": "SKL-COMP-01",
        "canonical_skill_name": "Computer Operation & Office Productivity",
        "confidence": "LOW",
        "reason": (
            "726 distinct jobs / 840 mentions of keyword 'word' = MS Word, an "
            "office-productivity tool for SKL-COMP-01. Do NOT add bare 'word' "
            "as an alias — the token is too ambiguous inside free text and "
            "would flood the matcher with false positives."
        ),
    },
}


# Task-required languages — evaluated on the FULL probe; low-frequency but
# explicit skill-demand targets (STEP 3 / STEP 7 of the task).
TASK_REQUIRED_CREATE_DECISIONS: Dict[str, Dict[str, Any]] = {
    "python": {
        "action": "CREATE_CANONICAL_SKILL",
        "canonical_skill_id": "SKL-DEV-PYTHON-01",
        "canonical_skill_name": "Python Programming",
        "aliases": ["Python", "Python3", "Python 3"],
        "confidence": "MEDIUM",
        "reason": (
            "Observed in titles/descriptions (below top-30 threshold); "
            "unambiguous language, explicit skill-demand target."
        ),
    },
    "dotnet": {
        "action": "CREATE_CANONICAL_SKILL",
        "canonical_skill_id": "SKL-DEV-DOTNET-01",
        "canonical_skill_name": ".NET Development",
        "aliases": [".NET", "Dot Net", "dotnet", "Microsoft .NET", "MS .NET"],
        "confidence": "MEDIUM",
        "reason": (
            "Observed as 'dotnet'/'.NET' variants; explicit skill-demand "
            "target. Casing/format variants normalize safely."
        ),
    },
    "c#": {
        "action": "CREATE_CANONICAL_SKILL",
        "canonical_skill_id": "SKL-DEV-CSHARP-01",
        "canonical_skill_name": "C# Programming",
        "aliases": ["C Sharp", "Csharp", "C#"],
        "confidence": "MEDIUM",
        "reason": "Observed in titles/descriptions; distinct from C++ — never merged.",
    },
    "c++": {
        "action": "CREATE_CANONICAL_SKILL",
        "canonical_skill_id": "SKL-DEV-CPP-01",
        "canonical_skill_name": "C++ Programming",
        "aliases": ["C Plus Plus", "Cpp", "C++"],
        "confidence": "MEDIUM",
        "reason": "Observed in titles/descriptions; distinct from C# — never merged.",
    },
}


# Task-required low-frequency skills still needing evidence grounding before
# a CREATE decision (probed, left NEEDS_REVIEW).
NEEDS_EVIDENCE: List[str] = ["android", "aws", "azure", "tally", "go"]


# Real competencies observed but deliberately NOT merged into one another, or
# kept as analysis dimensions rather than canonical skills.
KEEP_SEPARATE_DECISIONS: Dict[str, Dict[str, Any]] = {
    "mobile": {
        "action": "KEEP_SEPARATE",
        "canonical_skill_id": "",
        "canonical_skill_name": "(platform dimension)",
        "confidence": "LOW",
        "reason": (
            "2,076 distinct jobs / 4,301 mentions but 'mobile' is a platform/"
            "context, not one skill (Android, iOS, Flutter, React Native are "
            "distinct competencies). Represented as dedicated skills or a "
            "classification dimension, not a single canonical skill."
        ),
    },
}


# Functional-area tags / business functions / noise that must NOT become skills.
NOT_A_SKILL_DECISIONS: Dict[str, Dict[str, Any]] = {
    "it software - application programming": {
        "action": "NOT_A_SKILL",
        "confidence": "HIGH",
        "reason": (
            "Functional-area tag from source_skills ('IT Software - Application "
            "Programming'), not a technical competency. Cited 5,969 jobs but "
            "says nothing about WHICH skill is needed."
        ),
    },
    "sales": {
        "action": "NOT_A_SKILL",
        "confidence": "HIGH",
        "reason": "Business function from source_skills; not a technical skill.",
    },
    "ites": {
        "action": "NOT_A_SKILL",
        "confidence": "HIGH",
        "reason": (
            "Industry abbreviation (IT Enabled Services) from source_skills; "
            "not a technical skill."
        ),
    },
    "teaching": {
        "action": "NOT_A_SKILL",
        "confidence": "HIGH",
        "reason": "Education profession label from source_skills; not a technical skill.",
    },
}


# ── Probe: full technical-token landscape (all TECH_TOKEN_RE tokens) ──────────

def _probe_full_tokens(jobs: List[Any], matcher: SkillMatcher):
    """Count every TECH_TOKEN_RE token + unmatched source categories, so the
    audit can evaluate low-threshold skills (Python, C#, .NET, Android ...)."""
    tech_counter: Counter = Counter()
    tech_jobs: Dict[str, set] = defaultdict(set)
    tech_raw: Dict[str, set] = defaultdict(set)
    cat_counter: Counter = Counter()
    cat_jobs: Dict[str, set] = defaultdict(set)
    cat_raw: Dict[str, set] = defaultdict(set)

    for job in jobs:
        job_id = str(job.id)
        title = getattr(job, "job_title", None) or ""
        desc = getattr(job, "description", None) or ""
        for m in TECH_TOKEN_RE.finditer(title + " " + desc):
            tok = normalize(m.group(1))
            if not tok or tok in _TITLE_NOISE or matcher.lookup_skill(tok):
                continue
            tech_counter[tok] += 1
            tech_jobs[tok].add(job_id)
            tech_raw[tok].add(m.group(1))

        for seg in split_source_skills(getattr(job, "source_skills", None)):
            ns = normalize(seg)
            if not ns or matcher.lookup_skill(ns):
                continue
            cat_counter[ns] += 1
            cat_jobs[ns].add(job_id)
            cat_raw[ns].add(seg)

    return tech_counter, tech_jobs, tech_raw, cat_counter, cat_jobs, cat_raw


def _build_rows(
    tech_counter, tech_jobs, tech_raw,
    cat_counter, cat_jobs, cat_raw,
    need_evidence: List[str],
):
    """Merge probe output + classification tables into review rows."""
    # Start with candidates seen by the standard engine (cat + tech combined),
    # then append low-frequency task-required skills we still want to evaluate.
    seen: Dict[str, Dict[str, Any]] = {}

    all_decisions: Dict[str, Dict[str, Any]] = {}
    for d in (CREATE_DECISIONS, TASK_REQUIRED_CREATE_DECISIONS, MAP_DECISIONS,
              KEEP_SEPARATE_DECISIONS, NOT_A_SKILL_DECISIONS):
        all_decisions.update(d)

    def seed(candidate, jobs, mentions, forms, source_kind):
        if candidate in seen:
            return
        decision = all_decisions.get(candidate)
        action = decision["action"] if decision else "NEEDS_REVIEW"
        confidence = decision["confidence"] if decision else "NEEDS_REVIEW"
        cid = decision.get("canonical_skill_id", "") if decision else ""
        cname = decision.get("canonical_skill_name", "") if decision else ""
        reason = decision["reason"] if decision else ""
        seen[candidate] = {
            "candidate_skill": candidate,
            "observed_forms": ", ".join(sorted(forms)[:8]) or candidate,
            "distinct_jobs": jobs,
            "mention_count": mentions,
            "source_kind": source_kind,
            "current_status": "NEEDS_REVIEW",
            "recommended_action": action,
            "canonical_skill_name": cname,
            "canonical_skill_id": cid,
            "reason": reason,
            "confidence": confidence,
        }

    for cand in tech_counter:
        seed(cand, len(tech_jobs[cand]), tech_counter[cand], tech_raw[cand],
             "TITLE_OR_DESC_TOKEN")
    for cand in cat_counter:
        seed(cand, len(cat_jobs[cand]), cat_counter[cand], cat_raw[cand],
             "SOURCE_SKILL_CATEGORY")

    # Task-required candidates absent from the top-N, evaluated from the FULL
    # probe (python, dotnet, c#, c++, android, ...) — each must have real
    # evidence to even appear in the review.
    task_rows = []
    for cand in need_evidence:
        if cand in seen:
            continue
        jobs = len(tech_jobs[cand]) if cand in tech_jobs else 0
        mentions = tech_counter[cand] if cand in tech_counter else 0
        forms = tech_raw.get(cand, set()) or {cand}
        if jobs == 0:
            continue  # no observed evidence -> do not add to review
        seed(cand, jobs, mentions, forms, "TITLE_OR_DESC_TOKEN")

    rows = list(seen.values())
    rows.sort(key=lambda r: (-r["distinct_jobs"], r["candidate_skill"]))
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--source-id", default="naukri-historical-promptcloud")
    parser.add_argument("--db-url", default=None)
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    db_url = args.db_url or (
        os.environ.get("DATABASE_URL")
        or "postgresql://postgres:postgres@127.0.0.1:5432/demand_x"
    )

    from core.models.observation import JobPosting
    engine = create_engine(db_url)
    matcher = SkillMatcher()
    with engine.connect() as conn:
        query = (
            "SELECT id, job_title, description, source_skills "
            "FROM job_postings"
        )
        if args.source_id:
            query += f" {('WHERE source_id = %s')}"
            rows = conn.exec_driver_sql(
                query,
                (args.source_id,),
            ).mappings().all()
        else:
            rows = conn.exec_driver_sql(query).mappings().all()

    print(f"[audit] probed {len(rows)} job rows")
    tech_counter, tech_jobs, tech_raw, cat_counter, cat_jobs, cat_raw = \
        _probe_full_tokens(rows, matcher)

    review = _build_rows(
        tech_counter, tech_jobs, tech_raw,
        cat_counter, cat_jobs, cat_raw,
        NEEDS_EVIDENCE,
    )

    out_path = args.out or os.path.join(
        PROJECT_ROOT, "data", "analytics", "skill_ontology_review.csv"
    )
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "candidate_skill", "observed_forms", "distinct_jobs", "mention_count",
            "current_status", "recommended_action", "canonical_skill_name",
            "canonical_skill_id", "reason", "confidence",
        ])
        for r in review:
            writer.writerow([
                r["candidate_skill"], r["observed_forms"], r["distinct_jobs"],
                r["mention_count"], r["current_status"], r["recommended_action"],
                r["canonical_skill_name"], r["canonical_skill_id"],
                r["reason"], r["confidence"],
            ])
    print(f"[audit] reviewed {len(review)} candidates -> {out_path}")

    # Print a compact classification summary for the terminal
    by_action: Dict[str, int] = defaultdict(int)
    for r in review:
        by_action[r["recommended_action"]] += 1
    print("[audit] classification:", dict(by_action))
    for r in review:
        if r["recommended_action"] == "CREATE_CANONICAL_SKILL":
            print(f"  CREATE {r['canonical_skill_id']:28s} "
                  f"{r['candidate_skill']:16s} jobs={r['distinct_jobs']:5d} "
                  f"mentions={r['mention_count']:5d}")


if __name__ == "__main__":
    main()