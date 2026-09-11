# Rules.md — Coding-Agent Constitution

| Field | Value |
|---|---|
| Status | **IMPLEMENTATION READY — v0.2** |
| Applies to | Every human and AI agent working on the project |
| Priority | Binding |
| Companion Docs | PRD.md · Architecture.md · Phases.md · Design.md |

---

# 1. Source-of-Truth Rule

The coding agent must treat:

- PRD.md
- Architecture.md
- Rules.md
- Phases.md
- Design.md

as the stable project specification.

`Memory.md`, once created, records what is **actually implemented**.

If a stable specification conflicts with Memory.md, flag the conflict instead of silently rewriting history.

---

# 2. Non-Negotiable Integrity Rules

## Rule 1 — Never invent data

If a number, job, course, occupation, skill or project cannot be traced to a source, do not present it as real.

## Rule 2 — Never invent government APIs

Do not assume an API exists because a website exists.

Verify the actual interface first.

## Rule 3 — Never fake an integration

“Integrated with NCS” means an actual tested access path exists.

A source listed in Architecture.md is not automatically integrated.

## Rule 4 — Never claim real-time without evidence

Use:

- LIVE
- PERIODIC
- HISTORICAL
- STATIC

based on actual source evidence.

## Rule 5 — Never fabricate model accuracy

Accuracy, precision, recall or F1 may only appear after an actual documented evaluation.

## Rule 6 — Never fabricate tests

A test that was not run did not pass.

## Rule 7 — Never fabricate screenshots/results

Demo screenshots must represent actual software output.

## Rule 8 — Never silently change architecture

Any architectural deviation must be documented.

## Rule 9 — No unnecessary ML

Start with rules and analytics.

Add ML only where it solves a demonstrated problem.

## Rule 10 — Preserve provenance

Every important transformation must remain traceable to its source.

## Rule 11 — Mark estimates and predictions

`ESTIMATED` and `PREDICTED` must remain visibly distinct from `OBSERVED` and `DERIVED`.

## Rule 12 — Never convert investment directly to job count

Investment/project data may provide future-demand signals but does not automatically establish employment numbers.

## Rule 13 — Human review is mandatory for recommendations

Recommendations must be reviewable.

## Rule 14 — Explainability is mandatory

No important AI/analytical output without evidence.

## Rule 15 — Secrets stay out of source code

Use environment variables or secret stores.

## Rule 16 — No private/authenticated scraping

Never bypass:

- login
- CAPTCHA
- rate limits
- access controls
- robots/access restrictions where applicable

## Rule 17 — No PII in MVP

Do not collect candidate names, resumes, phone numbers or contact information.

## Rule 18 — Preserve reproducibility

The same source snapshot + same rule/model version should produce the same deterministic MVP output.

---

# 3. Agent Operating Rules

## Rule 19 — Inspect before modifying

Before changing a repository area:

1. inspect the relevant files
2. inspect current tests
3. inspect related interfaces
4. understand the current implementation
5. then modify

Never replace a subsystem merely because another implementation is familiar.

## Rule 20 — Small changes

Prefer focused changes.

Avoid combining:

- architecture changes
- dependency changes
- large refactors
- feature additions

without necessity.

## Rule 21 — Preserve working code

Do not rewrite functioning components without a documented reason.

## Rule 22 — Update Memory.md

When implementation begins, Memory.md must be updated with:

- completed work
- current phase
- files changed
- model/rule versions
- known issues
- data sources
- open blockers

## Rule 23 — Do not create speculative systems

Do not build plugin systems, generic frameworks or abstractions that are not currently required.

---

# 4. Architecture Rules

## Rule 24 — Thin API routers

Route handlers only:

- validate
- call service
- return schema

No business logic.

## Rule 25 — AI modules independent of HTTP

`ai/` must not import FastAPI route handlers.

## Rule 26 — Ingestion separated from AI

Source connectors should acquire/prepare data.

AI enrichment runs after normalized data exists.

## Rule 27 — Frontend has no direct DB access

All frontend data comes through FastAPI.

## Rule 28 — Domain logic stays in domain/services

Do not bury rules inside UI components or SQL strings where reusable business logic belongs in Python.

---

# 5. Approved Technology

### Backend

- Python
- FastAPI
- Pydantic
- SQLAlchemy
- Alembic

### Database

- PostgreSQL

### Data

- Pandas

### NLP/ML

- spaCy
- scikit-learn

### Optional future

- sentence-transformers
- PyTorch

Only add future tools when justified.

### Frontend

- React
- TypeScript
- Vite
- one appropriate charting library

### Infra

- Docker
- Docker Compose
- Git

---

# 6. Restricted Technology

Do not add without an ADR:

- Kafka
- Kubernetes
- Airflow
- Elasticsearch
- MLflow
- vector databases
- distributed queues
- additional AI orchestration frameworks

The existence of a future scaling requirement is not enough.

---

# 7. Dependency Rules

Every new package must:

1. have a current requirement
2. fit the architecture
3. be necessary
4. have a pinned compatible version
5. not duplicate an existing dependency

---

# 8. Data Rules

## Rule 29 — Raw data is immutable

Corrections happen through a new ingestion run.

## Rule 30 — Never silently drop invalid records

Quarantine them with a reason.

## Rule 31 — Keep source IDs

Where available, preserve:

- source_id
- source_record_id
- source_url

## Rule 32 — Keep timestamps

At minimum:

- source timestamp when available
- retrieved_at
- ingested_at
- generated_at for derived outputs

## Rule 33 — Snapshot data must be labeled

Use:

```text
access_method = SOURCE_SNAPSHOT
```

when applicable.

## Rule 34 — Manual curation must be visible

Use:

```text
access_method = MANUAL_CURATION
```

and do not describe it as automated ingestion.

---

# 9. Confidence Rules

Confidence is not a decorative field.

Every numeric confidence needs:

- calculation method
- confidence type
- model/rule version

Valid confidence types can include:

```text
MATCH_STRENGTH
CLASSIFICATION_CONFIDENCE
EVIDENCE_STRENGTH
DATA_COMPLETENESS
```

Do not report “92% confidence” when the value is simply an arbitrary score.

For analytical demand ranking, prefer `evidence_strength` if statistical confidence is not meaningful.

---

# 10. AI Rules

## Skill extraction

MVP:

- dictionary
- aliases
- phrase matching
- normalization
- optional spaCy preprocessing

No transformer unless explicitly approved.

## Occupation mapping

MVP:

- verified NCO reference
- deterministic matching
- optional classifier only if enough labeled data exists

No invented NCO codes.

## Demand

MVP:

- analytical score
- reproducible formula
- exposed components

Never call the analytical formula “trained AI”.

## Skill gap

Use deterministic comparison.

## Recommendation

Rule-based and evidence-linked.

LLM generation is not the source of truth for recommendation decisions.

---

# 11. Data Freshness Rules

The UI and API must distinguish:

```text
LIVE
PERIODIC
HISTORICAL
STATIC
```

A source that is checked today is not automatically a LIVE source.

---

# 12. Provenance Rules

Every derived result should be traceable:

```text
result
→ rule/model
→ input records
→ source
```

Recommended provenance states:

```text
OBSERVED
DERIVED
ESTIMATED
PREDICTED
```

---

# 13. Evidence Rules

Every important output should expose a Why/Evidence object.

Minimum evidence information:

```text
source
source URL
records used
method
rule/model version
freshness
provenance
```

If evidence cannot be produced, do not ship the result.

---

# 14. Recommendation Rules

A recommendation must:

- have an evidence basis
- identify the underlying gap
- identify relevant demand evidence
- carry a rule version
- have validation status

Valid MVP statuses:

```text
PENDING
ACCEPTED
REJECTED
NEEDS_REVIEW
```

---

# 15. Error Handling

Errors must be:

- logged
- structured
- reproducible where possible
- safe for users

API errors should use:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Human-readable message"
  }
}
```

Never expose stack traces to end users.

---

# 16. Batch Failure Rules

If one external source fails:

- log it
- continue independent sources
- preserve previous valid snapshots
- clearly mark stale/missing information

Do not fail the entire platform because one connector is unavailable.

---

# 17. Testing Rules

At minimum:

### Unit

- skill matching
- occupation mapping
- demand calculation
- gap calculation
- recommendation rules

### Integration

- database
- ingestion fixtures
- AI pipeline
- API endpoints

### Test data

Use real captured fixtures where legally and technically appropriate.

Never depend on a live website for every test.

---

# 18. API Rules

All APIs:

```text
/api/v1/
```

Breaking changes require:

- additive compatibility, or
- new API version

Every AI response should contain appropriate:

```text
result
evidence
model_version
generated_at
```

Add confidence only where meaningful.

---

# 19. Frontend Rules

The dashboard should:

- display the source
- display freshness
- display provenance
- display evidence access
- never fabricate a chart to fill whitespace
- show clear empty states
- show API errors clearly
- preserve accessibility

---

# 20. Git Rules

Commits should describe:

```text
what changed
why it changed
```

Avoid “misc changes”.

Do not mix unrelated architecture and feature work.

Branches are preferred when practical, but hackathon speed is allowed.

---

# 21. Database Rules

All schema changes require migrations.

Do not manually alter a shared schema without documenting the migration.

Never delete production-like data as a shortcut without explicit approval.

---

# 22. Performance Rules

Do not prematurely optimize.

For MVP:

- small indexed PostgreSQL tables
- simple queries
- batch analytics
- minimal frontend requests

Optimize only after measuring a bottleneck.

---

# 23. Agent Handoff Rules

Before handing work to another agent, update Memory.md with:

```text
current phase
completed tasks
files changed
database migrations
API changes
model/rule versions
tests run
known issues
next recommended task
```

Never make the next agent rediscover project state unnecessarily.

---

# 24. Violation Recovery

If an agent discovers a previous violation:

1. stop relying on the questionable result
2. document the violation
3. fix or quarantine the affected output
4. update Memory.md
5. rerun relevant tests
6. continue only after the state is trustworthy

Do not conceal an error because of demo pressure.
