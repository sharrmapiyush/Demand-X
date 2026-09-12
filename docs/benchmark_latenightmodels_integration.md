# Benchmark — LatenightModels Capability Integration (Phases 1–21)

| Field | Value |
|---|---|
| Status | **COMPLETE — verified** |
| Completed | 12 September 2026 |
| Verification | 254/254 unit tests pass · TypeScript build clean · DB row counts verified |
| Git | `d949fd4` — "feat: integrate advanced labour intelligence and product layer" |
| Objective | Absorb the best capabilities from LatenightModels into Demand-X **without** copying its flaws |

---

## REFERENCE ANALYSIS

The reference project (LatenightModels) shipped a persuasive-but-unsound labour-intelligence
dashboard: synthetic job feeds, hardcoded analytics arrays, an unverifiable semantic search
placeholder, and "real-time" claims over static data. Its marketable surface (velocity charts,
skill-demand views, occupation intelligence, a modern product layer) was real value; its data
honesty was not.

Demand-X's mandate: keep PostgreSQL + provenance + evidence + verification status + freshness
classes + deterministic demand calculations + the 32-skill canonical ontology as authoritative,
and take only the capabilities that survive contact with real data.

## ADOPTED

Capabilities absorbed and re-implemented on Demand-X's evidence-first substrate:

| Capability | Where | What it does |
|---|---|---|
| Skill velocity | `core/analytics/skill_velocity.py` | Real two-window velocity with explicit thresholds (`MIN_WINDOW_JOBS ≥ 3`, `RISING ≥ 0.25`, `FALLING ≥ 0.20`) |
| Enhanced skill extraction | `core/skills/enhanced_extractor.py` | Multi-signal extraction feeding `skill_evidence` rows |
| **Deduplication (SimHash)** | `core/deduplication/engine.py` | 64-bit LSH, `shingle_size=3`, hamming ≤ 3, exact/near-dup/repost/distinct |
| NCO-2015 mapper | `core/ontology/nco_mapper.py` | DVET NCO-2015 occupation mapping; `NEEDS_REVIEW` when unseeded |
| Maharashtra geo engine | `core/geography/maharashtra.py` | Official 36 districts, aliases, renamed-district resolution |
| Source governance | `core/governance/` | Policy, health checks, `DomainRateLimiter`, autonomous scheduler |
| Ingestion orchestrator | `core/ingestion/` | Source registry + stop-and-report orchestration |
| Local AI fallback | `ai/service/abstraction.py` | Deterministic, evidence-grounded answers without external model dependency |
| RAG assistant | `ai/rag/engine.py` | Retrieval over persisted evidence |
| Exports & reporting | `core/exports/reporter.py` | CSV/JSON demand, sources, occupations, skills exports |
| Product layer | `frontend/` (Vite + React) | Dashboard + skill-gap product views |
| API surface | `api/routers/` (7 new routers) | districts, skills, jobs, search, governance, ai_service, exports |

## IMPROVED

Where Demand-X's version is deliberately stronger than the reference:

- **Conservative dedup.** Word-level edits stay beyond the SimHash threshold (`hamming > 3`).
  The reference collapsed real wording changes as duplicates; Demand-X biases against false
  near-dup merging so duplicate/repost can never inflate demand counts.
- **Honest velocity.** No velocity label is emitted without minimum evidence in both windows
  (`INSUFFICIENT_DATA` / `NO_DATA`), and all thresholds are module constants — no hidden knobs.
- **No fabricated NCO codes.** The mapper emits a numeric code only against an authoritative
  seed; otherwise `NEEDS_REVIEW`. The reference presented invented codes as verified.
- **District correctness.** 36 official districts after the 2023 Aurangabad → Chhatrapati
  Sambhajinagar renaming (alias, not a duplicate row).
- **Evidence-first demand.** Persisted rows carry an evidence dict and `provenance_state =
  DERIVED`; nothing is asserted without the query counts behind it.
- **Freshness labels.** Explicit `LIVE / PERIODIC / HISTORICAL / STATIC` instead of implied
  "real-time".
- **Source filtering end-to-end.** Demand aggregation and exports are source-scoped; the
  reference mixed sources without attribution.

## REJECTED

Reference features examined and **not** adopted — the flaws the mandate names:

- Synthetic job generation (would corrupt every downstream count)
- Hardcoded analytics (dashboard numbers that were not derived)
- Placeholder semantic search presented as real; supply extrapolated to all of Pune
- Unsupported "real-time" claims over static historical data
- Statewide/unresolved geography silently defaulted to Mumbai
- Fabricated numeric NCO codes
- Ungrounded ("hallucinated") AI answers
- Inflated demand counts from duplicates/reposts
- Invented weighted demand scores

## DEFERRED

- **Semantic search as a hard dependency** — abstracted (`core/search/`), never required for MVP.
- **Wired cloud AI adapters** (OpenRouter/Anthropic) — local evidence fallback is the working path.
- **DVET supply verification** — waits for an authoritative directory; the inferred Pune
  fixture is stored under `data/fixtures/dvet_unverified_directory_or_inferred/` and labelled.
- **Backfilled second velocity window** — single snapshot date means velocity currently cannot
  claim RISING/FALLING; the engine is ready and honest.
- **Sector-weighted demand scores** — explicitly kept `NULL` under `mvp-v1-no-score`.

## BACKEND

FastAPI (`api/main.py`, v0.4.0) with 8 registered `/api/v1` routers:
`health`, `districts`, `skills`, `jobs`, `search`, `governance`, `ai_service`, `exports`.
DB-backed endpoints use the `get_db` dependency; the skill-demand endpoint runs the
deterministic engine directly on `db_url`. Governance surface exposes source policies,
health, rate limits, and scheduler state.

## FRONTEND

Vite + React + TypeScript (`frontend/`): dashboard layout, districts view, skill demand /
gap product views wired to the API. `tsc --noEmit` is clean (0 errors). Recharts 3.x for
velocity/gap rendering.

## INTELLIGENCE

Deterministic, evidence-grounded pipeline — no LLM decides labour demand:
skill extraction → 32-skill canonical ontology → per-district occupation demand
(`demand_calculator` + `demand_runner`) → skill velocity → gap product. Provenance is
recorded at every hop (source → evidence → derived demand rows).

## TESTS

- **254 / 254 unit tests pass** (`python -m pytest tests/unit/ -q`, 0 failures).
- `run_tests.py` aggregates the suite.
- Patterns: psycopg2 `sys.modules` mock for the Python 3.14 DLL path, file-based SQLite
  with FK enforcement, FastAPI dependency overrides, monkeypatched `calculate_skill_demand`.
- Covered: governance, ingestion, dedup (SimHash incl. conservative-edits test), Maharashtra
  geo (incl. renamed-district), NCO mapper (incl. authoritative-seed path), enhanced extractor,
  skill velocity (incl. guard rails), demand runner (idempotency, provenance, score-NULL),
  exports, API routers, AI abstraction.

## DATABASE

Verified row counts (Docker PostgreSQL, `demand_x_postgres`):

| Table | Count |
|---|---|
| `job_postings` | **21,910** |
| `demand_calculation_runs` | **1** |
| `district_occupation_demand` | **3** |
| `dvet_institutes` | **1** |
| `dvet_trades` | **10** |
| canonical skills (seed) | **32** |
| canonical occupations (seed) | **7** |

Demand rows are `provenance_state = DERIVED`, `demand_score = NULL`, idempotent on re-run
(same inputs → rows skipped, not duplicated).

## GIT

`d949fd4 feat: integrate advanced labour intelligence and product layer`
— 54 files changed, **7,916 insertions**, 4 deletions. Clean working tree. Commit contains
only project code, tests, and seed fixtures — no `.env`, no temporary artifacts, no
Docker/runtime outputs.