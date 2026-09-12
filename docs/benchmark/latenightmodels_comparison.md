# LatenightModels → Demand‑X — Capability Comparison

| Field | Value |
|---|---|
| Date | 12 September 2026 |
| Phase | Batches 1–3 (governance · ingestion/geography · AI/RAG/exports) |
| Verification | 254/254 unit tests pass · Docker Postgres row counts verified via psql |
| Integration tests | Collection blocked locally by documented psycopg2 DLL policy on Python 3.14; DB verified directly in the container instead |

**Mandate:** absorb the best capabilities from LatenightModels into Demand‑X **without**
copying its flaws. Demand‑X's PostgreSQL + provenance + evidence + verification-status +
freshness architecture stays authoritative.

---

## Adopted capabilities

Capabilities taken from the reference and brought into Demand‑X on its own substrate:

| Capability | Demand‑X location |
|---|---|
| Source governance — policy, health, rate limiting | `core/governance/policy.py`, `core/governance/health.py`, `core/governance/rate_limiter.py` |
| Autonomous scheduling + dispatcher | `core/governance/scheduler.py`, `core/governance/dispatcher.py` |
| Raw ingestion orchestrator + source registry | `core/ingestion/orchestrator.py`, `core/ingestion/sources.py` |
| Deduplication (SimHash, 64-bit, hamming ≤ 3) | `core/deduplication/engine.py` |
| Maharashtra geography engine (official 36 districts) | `core/geography/maharashtra.py` |
| Occupation intelligence (NCO‑2015 mapping) | `core/ontology/nco_mapper.py` |
| Real skill velocity (two‑window, evidence‑gated) | `core/analytics/skill_velocity.py` |
| Enhanced skill extraction | `core/skills/enhanced_extractor.py` |
| AI service abstraction + local evidence fallback | `ai/service/abstraction.py`, `ai/service/*` |
| RAG assistant over persisted evidence | `ai/rag/engine.py` |
| Semantic search abstraction | `core/search/` |
| Exports & reporting (CSV/JSON, source‑scoped) | `core/exports/reporter.py` |
| Product API surface (districts, skills, jobs, search, governance, ai_service, exports routers) | `api/routers/*` |

## Adapted capabilities

Re‑worked to be honest on real data (not copied verbatim):

- **Skill velocity** → not a naive period‑over‑period ratio. Requires minimum evidence in
  **both** windows (`MIN_WINDOW_JOBS ≥ 3`, `RISING ≥ 0.25`, `FALLING ≥ 0.20`); otherwise
  emits `INSUFFICIENT_DATA` / `NO_DATA`. All thresholds are exported constants — no hidden knobs.
- **Deduplication** → SimHash window tuned **conservatively**: genuine word edits flip
  more than the threshold bits, so reposts that merely reformat collapse to
  NEAR_DUPLICATE while real wording changes stay DISTINCT. Demand counts can never be
  inflated by duplicate/merged posts.
- **NCO mapping** → emits a numeric NCO code **only** against an authoritative seed;
  without a seed it returns `NEEDS_REVIEW` / `NO_REFERENCE`. No invented codes.
- **Geography** → the 2023 Aurangabad → Chhatrapati Sambhajinagar renaming resolves to a
  **single** district via alias; unresolved/statewide data is surfaced as unknown, never
  defaulted to Mumbai.
- **AI answers** → `LocalEvidenceFallback.answer_question` answers strictly from persisted
  evidence (DB rows + seed reference); no model‑invented labour statistics.
- **Search** → semantic search is abstracted as an optional backend, **not** a hard
  dependency of the MVP.
- **Supply** → DVET supply stays `dvet_institutes` / `dvet_trades`, stored locally and
  labelled; the inferred Pune reference directory is marked
  `data/fixtures/dvet_unverified_directory_or_inferred/`. Never extrapolated to all of Pune.
- **Demand** → deterministic calculator + runner persist `DERIVED` rows with an evidence
  dict and explicit `data_completeness_status`; `demand_score` stays NULL under
  `mvp-v1-no-score`. No weighted‑score invention.
- **Freshness** → explicit `LIVE / PERIODIC / HISTORICAL / STATIC` classes; no implied
  "real‑time".

## Rejected capabilities

Reference components Demand‑X will **not** take:

- Synthetic/generated job feeds (would corrupt every downstream count).
- Hardcoded analytics (dashboard arrays not derived from the DB).
- The reference's semantic‑search stub as a real product feature.
- Fabricated numeric NCO codes.
- Maharashtra → Mumbai fallback for unresolved/statewide data.
- Unsupported "real‑time" claims over static historical data.
- Ungrounded (model‑hallucinated) AI answers.
- Fabricated supply / extrapolation of small samples to city‑wide totals.
- Duplicate/repost‑inflated demand counts.
- Invented weighted demand scores.

## Deferred capabilities

- Wired cloud AI adapters (OpenRouter/Anthropic) behind `ai/service/abstraction.py` —
  the local evidence fallback is the working path; provider adapters are a drop‑in follow‑up.
- Backfilled second velocity data window — single snapshot date means velocity cannot
  yet claim RISING/FALLING; the engine is ready and stays honest meanwhile.
- DVET supply verification — waits for an authoritative directory; the inferred fixture
  is explicitly labelled unverified.
- Integration test execution on this machine — blocked by the OS Application‑Control
  policy on the psycopg2 DLL; DB verification is performed directly in the Docker
  container instead.

## What Demand‑X does better

1. **Evidence provenance end‑to‑end** — every persisted demand/skill row carries the query
   counts behind it and a `provenance_state`; the reference asserted numbers without
   derivation.
2. **Honest completeness** — `data_completeness_status` (`NO_DATA`, `INSUFFICIENT_DATA`,
   etc.) is a first‑class column; the reference never labelled thin evidence.
3. **Deterministic, auditable guarantees** — no LLM decides labour demand; no weighted
   scores; dedup is conservative; re‑runs are idempotent (`uix` on
   district/occupation/period/run).
4. **Label and gate everything** — freshness classes, seeded‑only NCO codes,
   evidence‑gated velocity labels.
5. **No fabrication, ever** — the explicit constraint list (synthetic jobs, hardcoded
   analytics, invented codes, fake supply) is enforced in the tests and in the report
   artifacts, not just stated.

---

## Verification record

```
job_postings             = 21,910  ✓
demand_calculation_runs  = 1       ✓
district_occupation_demand = 3     ✓  (Pune; DERIVED; INSUFFICIENT_DATA; NULL score)
dvet_institutes          = 1       ✓
dvet_trades              = 10      ✓
canonical skills (seed)  = 32      ✓  (core/ontology/skills_seed.json v3.0.0)
synthetic job markers    = 0       ✓
unit tests               = 254/254 ✓
```

Existing Demand / Supply / Gap results remain valid: persisted demand rows are unchanged,
DVET supply is present, and no gap is claimed where demand is `INSUFFICIENT_DATA`.