"""Unit tests for the deterministic skill extraction engine.

These tests exercise the matcher + extractor + knowledge-base candidate
discovery against lightweight job stubs — no DB access, no network, no LLM.
All inputs are deterministic fixtures derived from the real Naukri data
reality (source_skills = functional-area categories; real skills live in
titles/descriptions).
"""

from __future__ import annotations

import pytest

from core.skills.extractor import extract_job_skills, split_source_skills
from core.skills.knowledge_base import discover_candidates
from core.skills.models import (
    ExtractionMethod,
    ExtractionSummaryRecord,
    MatchConfidence,
    SkillCandidate,
    SkillEvidence,
    UnmatchedMention,
)
from core.skills.ontology_matcher import SkillMatcher, normalize


# ── Fixtures ────────────────────────────────────────────────────────────────

class _Job:
    """Minimal stand-in for JobPosting exposing the fields the extractor reads."""

    def __init__(self, job_id, title=None, description=None, source_skills=None):
        self.id = job_id
        self.job_title = title or ""
        self.description = description or ""
        self.source_skills = source_skills


@pytest.fixture(scope="module")
def matcher():
    return SkillMatcher()


# ── 1. normalize() ───────────────────────────────────────────────────────────

def test_normalize_collapses_and_lowercases(matcher):
    assert normalize("  Skin   Care  ") == "skin care"
    assert normalize("MS OFFICE") == "ms office"
    assert normalize(None) == ""
    assert normalize("") == ""


# ── 2. source_skills split ───────────────────────────────────────────────────

def test_split_source_skills_separators(matcher):
    raw = "IT Software - Application Programming, Sales;ITES | Telecalling/Banking"
    parts = split_source_skills(raw)
    assert "IT Software - Application Programming" in parts
    assert "Sales" in parts
    assert "ITES" in parts
    assert "Telecalling" in parts
    assert "Banking" in parts


# ── 3. canonical-name exact match (HIGH) ─────────────────────────────────────

def test_source_skill_canonical_exact_match_high_confidence(matcher):
    job = _Job("j1", source_skills="Machine Tool Operation & Precision Measurement")
    ev, _ = extract_job_skills(job, matcher)
    assert len(ev) == 1
    assert ev[0].canonical_skill_id == "SKL-MACH-01"
    assert ev[0].extraction_method == ExtractionMethod.SOURCE_SKILL_EXACT
    assert ev[0].match_confidence == MatchConfidence.HIGH


# ── 4. alias match in source_skills (MEDIUM) ────────────────────────────────

def test_source_skill_alias_match_medium_confidence(matcher):
    job = _Job("j2", source_skills="MS Office")
    ev, _ = extract_job_skills(job, matcher)
    assert len(ev) == 1
    assert ev[0].canonical_skill_id == "SKL-COMP-01"
    assert ev[0].extraction_method == ExtractionMethod.SOURCE_SKILL_ALIAS
    assert ev[0].match_confidence == MatchConfidence.MEDIUM


# ── 5. multi-source evidence is preserved ────────────────────────────────────

def test_same_skill_from_source_title_and_description_preserved(matcher):
    job = _Job(
        "j3",
        title="Data Entry Operator",
        description="We need a Data Entry specialist with MS Office skills.",
        source_skills="Data Entry",
    )
    ev, _ = extract_job_skills(job, matcher)
    methods = {(e.evidence_type, e.extraction_method) for e in ev}
    source_fams = {e.evidence_type for e in ev}
    assert source_fams == {"SOURCE_SKILL", "JOB_TITLE", "JOB_DESCRIPTION"}
    assert (("SOURCE_SKILL", ExtractionMethod.SOURCE_SKILL_ALIAS) in methods)  # Data Entry alias
    assert (("JOB_TITLE", ExtractionMethod.TITLE_ALIAS) in methods)
    assert (("JOB_DESCRIPTION", ExtractionMethod.DESCRIPTION_ALIAS) in methods)
    # Same skill from 3 sources -> 3 evidence rows, not collapsed
    assert len(ev) == 3


# ── 6. duplicate skill mention in same text deduplicated ─────────────────────

def test_duplicate_mention_in_same_text_deduped(matcher):
    job = _Job(
        "j4",
        description="MS Office required. Advanced MS Office strongly preferred.",
    )
    ev, _ = extract_job_skills(job, matcher)
    assert len(ev) == 1  # "MS Office" twice -> one evidence row per (job, skill, source)
    assert ev[0].canonical_skill_id == "SKL-COMP-01"


# ── 7. word boundary prevents substring false positives ──────────────────────

def test_word_boundary_no_substring_false_positive(matcher):
    job = _Job("j5", title="JavaScript Developer")
    ev, _ = extract_job_skills(job, matcher)
    # "java" must NOT match inside "JavaScript" — word boundary prevents it.
    # JavaScript IS now a canonical skill, so SKL-DEV-JAVASCRIPT-01 matches
    # via its own canonical name, but SKL-DEV-JAVA-01 must NOT match.
    java_ev = [e for e in ev if e.canonical_skill_id == "SKL-DEV-JAVA-01"]
    js_ev = [e for e in ev if e.canonical_skill_id == "SKL-DEV-JAVASCRIPT-01"]
    assert len(java_ev) == 0  # Java must NOT match inside "JavaScript"
    assert len(js_ev) == 1    # JavaScript matches its own skill


# ── 8. unmatched source_skills → UnmatchedMention ────────────────────────────

def test_unmatched_source_skill_becomes_mention(matcher):
    job = _Job("j6", source_skills="Unknown Functional Area XYZ")
    ev, unm = extract_job_skills(job, matcher)
    assert len(ev) == 0
    assert len(unm) == 1
    assert unm[0].source_field == "SOURCE_SKILL"
    assert unm[0].normalized_text == "unknown functional area xyz"


# ── 9. Evidence can be aggregated into a summary record ─────────────────────

def test_evidence_aggregates_into_summary_counts(matcher):
    jobs = [
        _Job("a1", source_skills="MS Office"),
        _Job(
            "a2",
            title="Data Entry Operator",
            source_skills="Sales, Data Entry",
        ),
    ]
    evidence = []
    for job in jobs:
        ev, _ = extract_job_skills(job, matcher)
        evidence.extend(ev)

    comp_rows = [e for e in evidence if e.canonical_skill_id == "SKL-COMP-01"]
    # a1: MS Office (SOURCE_SKILL). a2: Data Entry (SOURCE_SKILL) + title (JOB_TITLE).
    assert len(comp_rows) == 3
    assert {e.job_posting_id for e in comp_rows} == {"a1", "a2"}

    rec = ExtractionSummaryRecord(
        canonical_skill_id="SKL-COMP-01",
        canonical_skill_name="Computer Operation & Office Productivity",
    )
    for e in comp_rows:
        rec.mention_count += 1
        if e.evidence_type == "SOURCE_SKILL":
            rec.source_skill_mentions += 1
        elif e.evidence_type == "JOB_TITLE":
            rec.title_mentions += 1
        else:
            rec.description_mentions += 1
        if e.match_confidence == MatchConfidence.HIGH:
            rec.high_confidence_count += 1
        elif e.match_confidence == MatchConfidence.MEDIUM:
            rec.medium_confidence_count += 1
        else:
            rec.low_confidence_count += 1
    rec.job_count = len({e.job_posting_id for e in comp_rows})

    assert rec.job_count == 2
    assert rec.mention_count == 3
    assert rec.source_skill_mentions == 2   # MS Office + Data Entry both in source_skills
    assert rec.title_mentions == 1          # "Data Entry Operator"
    assert rec.description_mentions == 0
    assert rec.high_confidence_count == 0   # all aliases -> MEDIUM
    assert rec.medium_confidence_count == 3
    assert rec.low_confidence_count == 0


# ── 10. discover_candidates returns NEEDS_REVIEW, no fabrication ─────────────

def test_discover_candidates_only_from_real_data_matcher(matcher):
    jobs = [
        _Job("c1", title="Java Developer with SQL", source_skills="IT Software - Application Programming"),
        _Job("c2", title="Java + Spring Boot Backend", source_skills="IT Software - Application Programming"),
        _Job("c3", title="Java Engineer", source_skills="Sales"),
    ]
    cands = discover_candidates(jobs, matcher, top_n=30, min_mentions=2)
    names = {c.candidate_skill for c in cands}
    # "java" is now a canonical skill — discover_candidates skips canonicals
    assert "java" not in names  # already canonical, not a new candidate
    # Functional category remains a candidate (not a technical skill)
    assert "it software - application programming" in names
    # Below min_mentions -> not a candidate
    assert "sales" not in names
    # Every candidate is NEEDS_REVIEW by default
    assert all(c.verification_status == "NEEDS_REVIEW" for c in cands)


# ═════════════════════════════════════════════════════════════════════════════
# STEP 111 — Ontology expansion tests (v3.0 seed, 32 canonical skills)
# ═════════════════════════════════════════════════════════════════════════════

# ── 11. Java aliases match (HIGH for canonical, MEDIUM for alias) ─────────────

def test_java_canonical_name_in_title(matcher):
    """'Java' in title matches SKL-DEV-JAVA-01.

    Canonical name is 'Java Programming'; 'Java' is an alias, so the
    title match resolves via the alias path → MEDIUM (alias) confidence.
    """
    job = _Job("j11", title="Java Developer Pune")
    ev, _ = extract_job_skills(job, matcher)
    java_ev = [e for e in ev if e.canonical_skill_id == "SKL-DEV-JAVA-01"]
    assert len(java_ev) == 1
    assert java_ev[0].match_confidence == MatchConfidence.MEDIUM


def test_java_alias_core_java_in_description(matcher):
    """'Core Java' is an alias of SKL-DEV-JAVA-01 (MEDIUM)."""
    job = _Job("j12", description="Must know Core Java and J2SE concepts.")
    ev, _ = extract_job_skills(job, matcher)
    java_ev = [e for e in ev if e.canonical_skill_id == "SKL-DEV-JAVA-01"]
    assert len(java_ev) == 1
    assert java_ev[0].match_confidence == MatchConfidence.MEDIUM


def test_java_canonical_programming_name_in_title_high(matcher):
    """'Java Programming' is the CANONICAL name of SKL-DEV-JAVA-01.

    Unlike the short alias 'Java' (MEDIUM), the canonical full name
    resolves via the exact path → TITLE_EXACT / HIGH.
    """
    job = _Job("j12b", title="Java Programming Expert")
    ev, _ = extract_job_skills(job, matcher)
    java_ev = [e for e in ev if e.canonical_skill_id == "SKL-DEV-JAVA-01"]
    assert len(java_ev) == 1
    assert java_ev[0].match_confidence == MatchConfidence.HIGH
    assert java_ev[0].extraction_method == ExtractionMethod.TITLE_EXACT


# ── 12. SQL aliases match ────────────────────────────────────────────────────

def test_sql_canonical_name_in_title(matcher):
    """'SQL' in title matches SKL-DB-SQL-01.

    Canonical name is 'SQL & Query Languages'; 'SQL' is an alias, so the
    title match resolves via the alias path → MEDIUM confidence.
    """
    job = _Job("j13", title="SQL Developer")
    ev, _ = extract_job_skills(job, matcher)
    sql_ev = [e for e in ev if e.canonical_skill_id == "SKL-DB-SQL-01"]
    assert len(sql_ev) == 1
    assert sql_ev[0].match_confidence == MatchConfidence.MEDIUM


def test_sql_alias_structured_query_language(matcher):
    """'Structured Query Language' is an alias of SKL-DB-SQL-01 (MEDIUM)."""
    job = _Job("j14", description="Knowledge of Structured Query Language required.")
    ev, _ = extract_job_skills(job, matcher)
    sql_ev = [e for e in ev if e.canonical_skill_id == "SKL-DB-SQL-01"]
    assert len(sql_ev) == 1
    assert sql_ev[0].match_confidence == MatchConfidence.MEDIUM


# ── 13. Oracle Database matches (distinct from SQL) ─────────────────────────

def test_oracle_canonical_name_in_title(matcher):
    """'Oracle' matches SKL-DB-ORACLE-01 (MEDIUM via alias), NOT SKL-DB-SQL-01."""
    job = _Job("j15", title="Oracle DBA")
    ev, _ = extract_job_skills(job, matcher)
    oracle_ev = [e for e in ev if e.canonical_skill_id == "SKL-DB-ORACLE-01"]
    sql_ev = [e for e in ev if e.canonical_skill_id == "SKL-DB-SQL-01"]
    assert len(oracle_ev) == 1
    assert oracle_ev[0].match_confidence == MatchConfidence.MEDIUM
    assert len(sql_ev) == 0  # Oracle is NOT SQL


def test_oracle_database_canonical_name_in_title_high(matcher):
    """'Oracle Database' is the canonical name → TITLE_EXACT / HIGH."""
    job = _Job("j15b", title="Oracle Database Administrator")
    ev, _ = extract_job_skills(job, matcher)
    oracle_ev = [e for e in ev if e.canonical_skill_id == "SKL-DB-ORACLE-01"]
    sql_ev = [e for e in ev if e.canonical_skill_id == "SKL-DB-SQL-01"]
    assert len(oracle_ev) == 1
    assert oracle_ev[0].match_confidence == MatchConfidence.HIGH
    assert oracle_ev[0].extraction_method == ExtractionMethod.TITLE_EXACT
    assert len(sql_ev) == 0


# ── 14. Python aliases match ─────────────────────────────────────────────────

def test_python_canonical_in_title(matcher):
    """'Python' matches SKL-DEV-PYTHON-01 (MEDIUM via alias)."""
    job = _Job("j16", title="Python Developer")
    ev, _ = extract_job_skills(job, matcher)
    py_ev = [e for e in ev if e.canonical_skill_id == "SKL-DEV-PYTHON-01"]
    assert len(py_ev) == 1
    assert py_ev[0].match_confidence == MatchConfidence.MEDIUM


def test_python_in_description(matcher):
    """'Python' in description matches SKL-DEV-PYTHON-01."""
    job = _Job("j17", description="Experience with Python and data pipelines.")
    ev, _ = extract_job_skills(job, matcher)
    py_ev = [e for e in ev if e.canonical_skill_id == "SKL-DEV-PYTHON-01"]
    assert len(py_ev) == 1


def test_python3_versioned_form_matches(matcher):
    """'Python 3' — the word boundary after 'Python' lets the alias match the
    versioned form (MEDIUM via alias)."""
    job = _Job("j17b", title="Python 3 Backend Developer")
    ev, _ = extract_job_skills(job, matcher)
    py_ev = [e for e in ev if e.canonical_skill_id == "SKL-DEV-PYTHON-01"]
    assert len(py_ev) == 1
    assert py_ev[0].match_confidence == MatchConfidence.MEDIUM


# ── 15. .NET variants match ──────────────────────────────────────────────────

def test_dotnet_bare_alias_in_title(matcher):
    """'.NET' bare alias matches SKL-DEV-DOTNET-01."""
    job = _Job("j18", title=".NET Developer")
    ev, _ = extract_job_skills(job, matcher)
    dotnet_ev = [e for e in ev if e.canonical_skill_id == "SKL-DEV-DOTNET-01"]
    assert len(dotnet_ev) == 1


def test_dotnet_word_boundary_inside_aspnet_not_matched(matcher):
    """'ASP.NET' is a single token — the dot is internal, not at a word
    boundary, so '.NET' must NOT match inside it (same boundary principle
    as Java ≠ JavaScript).  '.NET' matches at start-of-text / after a space
    (tests 18 and 20)."""
    job = _Job("j19", title="ASP.NET Senior Developer")
    ev, _ = extract_job_skills(job, matcher)
    dotnet_ev = [e for e in ev if e.canonical_skill_id == "SKL-DEV-DOTNET-01"]
    assert len(dotnet_ev) == 0


def test_dotnet_alias_microsoft_dotnet(matcher):
    """'Microsoft .NET' alias matches SKL-DEV-DOTNET-01."""
    job = _Job("j20", description="Microsoft .NET Framework 4.8 required.")
    ev, _ = extract_job_skills(job, matcher)
    dotnet_ev = [e for e in ev if e.canonical_skill_id == "SKL-DEV-DOTNET-01"]
    assert len(dotnet_ev) == 1


def test_dotnet_alias_dotnet_in_description(matcher):
    """'dotnet' alias matches SKL-DEV-DOTNET-01."""
    job = _Job("j21", description="dotnet core experience preferred.")
    ev, _ = extract_job_skills(job, matcher)
    dotnet_ev = [e for e in ev if e.canonical_skill_id == "SKL-DEV-DOTNET-01"]
    assert len(dotnet_ev) == 1


def test_dotnet_alias_dot_net_words(matcher):
    """'Dot Net' (two spaced words) alias matches SKL-DEV-DOTNET-01."""
    job = _Job("j21b", title="Dot Net Developer")
    ev, _ = extract_job_skills(job, matcher)
    dotnet_ev = [e for e in ev if e.canonical_skill_id == "SKL-DEV-DOTNET-01"]
    assert len(dotnet_ev) == 1
    assert dotnet_ev[0].match_confidence == MatchConfidence.MEDIUM


# ── 16. C# / C Sharp aliases ────────────────────────────────────────────────

def test_csharp_alias_in_title(matcher):
    """'C#' in title matches SKL-DEV-CSHARP-01 (MEDIUM via alias)."""
    job = _Job("j22", title="C# Developer")
    ev, _ = extract_job_skills(job, matcher)
    cs_ev = [e for e in ev if e.canonical_skill_id == "SKL-DEV-CSHARP-01"]
    assert len(cs_ev) == 1
    assert cs_ev[0].match_confidence == MatchConfidence.MEDIUM


def test_csharp_alias_c_sharp_text(matcher):
    """'C Sharp' matches SKL-DEV-CSHARP-01 (MEDIUM alias)."""
    job = _Job("j23", description="C Sharp programming skills required.")
    ev, _ = extract_job_skills(job, matcher)
    cs_ev = [e for e in ev if e.canonical_skill_id == "SKL-DEV-CSHARP-01"]
    assert len(cs_ev) == 1
    assert cs_ev[0].match_confidence == MatchConfidence.MEDIUM


def test_csharp_alias_csharp_text(matcher):
    """'Csharp' (no space) matches SKL-DEV-CSHARP-01."""
    job = _Job("j24", description="Csharp .NET experience required.")
    ev, _ = extract_job_skills(job, matcher)
    cs_ev = [e for e in ev if e.canonical_skill_id == "SKL-DEV-CSHARP-01"]
    assert len(cs_ev) == 1


# ── 17. C++ / C Plus Plus aliases ────────────────────────────────────────────

def test_cpp_alias_bare_in_title(matcher):
    """'C++' in title matches SKL-DEV-CPP-01 (MEDIUM via alias)."""
    job = _Job("j25", title="C++ Developer")
    ev, _ = extract_job_skills(job, matcher)
    cpp_ev = [e for e in ev if e.canonical_skill_id == "SKL-DEV-CPP-01"]
    assert len(cpp_ev) == 1
    assert cpp_ev[0].match_confidence == MatchConfidence.MEDIUM


def test_cpp_alias_c_plus_plus(matcher):
    """'C Plus Plus' matches SKL-DEV-CPP-01 (MEDIUM)."""
    job = _Job("j26", description="Proficiency in C Plus Plus programming.")
    ev, _ = extract_job_skills(job, matcher)
    cpp_ev = [e for e in ev if e.canonical_skill_id == "SKL-DEV-CPP-01"]
    assert len(cpp_ev) == 1
    assert cpp_ev[0].match_confidence == MatchConfidence.MEDIUM


def test_cpp_alias_cpp_no_space(matcher):
    """'Cpp' (no punctuation) matches SKL-DEV-CPP-01."""
    job = _Job("j27", description="Strong Cpp skills required.")
    ev, _ = extract_job_skills(job, matcher)
    cpp_ev = [e for e in ev if e.canonical_skill_id == "SKL-DEV-CPP-01"]
    assert len(cpp_ev) == 1


# ── 18. Java ≠ JavaScript (MUST remain separate) ────────────────────────────

def test_java_does_not_match_javascript_text(matcher):
    """'JavaScript' must NOT match SKL-DEV-JAVA-01 (Java != JavaScript)."""
    job = _Job("j28", title="JavaScript Frontend Developer")
    ev, _ = extract_job_skills(job, matcher)
    java_ev = [e for e in ev if e.canonical_skill_id == "SKL-DEV-JAVA-01"]
    assert len(java_ev) == 0  # Java must NOT match inside "JavaScript"


def test_javascript_matches_its_own_skill(matcher):
    """'JavaScript' MUST match SKL-DEV-JAVASCRIPT-01."""
    job = _Job("j29", title="JavaScript Frontend Developer")
    ev, _ = extract_job_skills(job, matcher)
    js_ev = [e for e in ev if e.canonical_skill_id == "SKL-DEV-JAVASCRIPT-01"]
    assert len(js_ev) == 1


def test_java_and_javascript_both_match_in_text(matcher):
    """'Java and JavaScript' in one job should match BOTH skills separately."""
    job = _Job("j30", description="Must know Java and JavaScript both.")
    ev, _ = extract_job_skills(job, matcher)
    java_ev = [e for e in ev if e.canonical_skill_id == "SKL-DEV-JAVA-01"]
    js_ev = [e for e in ev if e.canonical_skill_id == "SKL-DEV-JAVASCRIPT-01"]
    assert len(java_ev) == 1
    assert len(js_ev) == 1
    assert len(ev) == 2


# ── 19. SQL ≠ Oracle (must remain separate) ──────────────────────────────────

def test_sql_and_oracle_both_match_separately(matcher):
    """'SQL and Oracle' should produce two distinct evidence records."""
    job = _Job("j31", description="Must know SQL and Oracle Database.")
    ev, _ = extract_job_skills(job, matcher)
    sql_ev = [e for e in ev if e.canonical_skill_id == "SKL-DB-SQL-01"]
    ora_ev = [e for e in ev if e.canonical_skill_id == "SKL-DB-ORACLE-01"]
    assert len(sql_ev) == 1
    assert len(ora_ev) == 1


# ── 20. C# ≠ C++ (must remain separate) ──────────────────────────────────────

def test_csharp_and_cpp_both_match_separately(matcher):
    """'C# and C++' should produce two distinct evidence records."""
    job = _Job("j32", description="Experience in C# and C++ required.")
    ev, _ = extract_job_skills(job, matcher)
    cs_ev = [e for e in ev if e.canonical_skill_id == "SKL-DEV-CSHARP-01"]
    cpp_ev = [e for e in ev if e.canonical_skill_id == "SKL-DEV-CPP-01"]
    assert len(cs_ev) == 1
    assert len(cpp_ev) == 1


# ── 21. Generic business-function terms do NOT match any skill ───────────────

def test_generic_business_function_not_a_skill(matcher):
    """'Hiring' (business function) must not match any canonical skill."""
    job = _Job("j33", title="Hiring Manager", description="Immediate hiring requirement.")
    ev, _ = extract_job_skills(job, matcher)
    assert len(ev) == 0  # no canonical skill matches generic terms


def test_seniority_not_a_skill(matcher):
    """'Senior' (seniority term) must not match any canonical skill."""
    job = _Job("j34", title="Senior Executive", description="Senior role with 5+ years experience.")
    ev, _ = extract_job_skills(job, matcher)
    assert len(ev) == 0  # no canonical skill matches seniority terms


# ── 22. Provenance retained in skills_seed.json ──────────────────────────────

def test_all_new_skills_have_source_basis(matcher):
    """Every v3.0 skill carries provenance attesting Naukri dataset origin.

    Two fields encode provenance:
    - source_reference: names the dataset ("Naukri historical dataset …").
    - source_basis: records the empirical evidence that grounded the skill
      (job/mention counts, separation rationale) — may not contain the
      literal word 'Naukri' but must be present and non-empty.
    """
    from core.skills.ontology_matcher import _load_seeds
    seeds = _load_seeds()
    v3_skills = [s for s in seeds if s.get("version") == "3.0"]
    assert len(v3_skills) == 24  # exactly 24 new skills in v3.0 expansion
    for s in v3_skills:
        assert "source_reference" in s, f"{s['skill_id']} missing source_reference"
        assert "Naukri" in s["source_reference"], (
            f"{s['skill_id']} source_reference must reference Naukri dataset"
        )
        assert s.get("source_basis"), (
            f"{s['skill_id']} missing or empty source_basis (provenance field)"
        )
        assert s["verification_status"] == "NEEDS_REVIEW", (
            f"{s['skill_id']} must be NEEDS_REVIEW"
        )


def test_original_seeds_unchanged(matcher):
    """The 8 original DVET-derived seed skills are preserved unchanged."""
    from core.skills.ontology_matcher import _load_seeds
    seeds = _load_seeds()
    seed_ids = {s["skill_id"] for s in seeds}
    for orig in ["SKL-BEAUTY-01", "SKL-COMP-01", "SKL-PROG-01", "SKL-FASHION-01",
                 "SKL-ICT-01", "SKL-MACH-01", "SKL-AUTO-01", "SKL-PAINT-01"]:
        assert orig in seed_ids, f"Original seed {orig} missing"


# ── 23. Deterministic rerun produces identical results ───────────────────────

def test_deterministic_extraction_same_inputs_same_outputs(matcher):
    """Same job inputs → same evidence records (frozen dataclass, deterministic matcher)."""
    job = _Job("j35", title="Java SQL Developer", description="Oracle and Python experience.")
    ev1, unm1 = extract_job_skills(job, matcher)
    ev2, unm2 = extract_job_skills(job, matcher)
    # Frozen dataclasses → identical content
    assert ev1 == ev2
    assert unm1 == unm2
    # Skills found: Java (HIGH), SQL (HIGH), Oracle (HIGH), Python (HIGH)
    skill_ids = {e.canonical_skill_id for e in ev1}
    assert "SKL-DEV-JAVA-01" in skill_ids
    assert "SKL-DB-SQL-01" in skill_ids
    assert "SKL-DB-ORACLE-01" in skill_ids
    assert "SKL-DEV-PYTHON-01" in skill_ids
    assert len(ev1) == 4


def test_deterministic_matcher_same_seed_same_index(matcher):
    """Two SkillMatcher instances from the same seed produce identical regex indices."""
    m2 = SkillMatcher()
    assert sorted(matcher.canonical_ids) == sorted(m2.canonical_ids)
    assert matcher._text_re.pattern == m2._text_re.pattern