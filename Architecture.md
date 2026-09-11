# Architecture.md — Maharashtra Labour-Market Intelligence & Curriculum-Alignment Platform

| Field | Value |
|---|---|
| Status | **IMPLEMENTATION READY — v0.2** |
| Pilot | **Pune district** |
| Sectors | **IT-ITeS · Automotive/Manufacturing · Electronics** |
| Demo | **15 September 2026** |
| Backend | Python + FastAPI |
| Database | PostgreSQL |
| Frontend | React + TypeScript + Vite |
| AI/ML | Python, spaCy, scikit-learn where justified |
| Infrastructure | Docker Compose |
| Companion Docs | PRD.md · Rules.md · Phases.md · Design.md |

---

## 1. Architecture Goal

The architecture must support a complete labour-market intelligence loop with the smallest practical technology footprint.

The architecture is designed for two horizons:

### Horizon A — 15 September MVP

A local, demoable, evidence-backed vertical slice.

### Horizon B — Post-demo platform

A scalable Maharashtra-wide data and intelligence platform.

The MVP must not be delayed by infrastructure intended for Horizon B.

---

## 2. Core Architecture Principles

1. **Evidence first.**
2. **Source provenance is preserved.**
3. **Rules/analytics before ML.**
4. **AI and API are separate concerns.**
5. **Logical data layers are required; separate infrastructure services are not.**
6. **External source access must be verified before connector implementation.**
7. **A legitimate source snapshot can keep the MVP reproducible when live access is unavailable.**
8. **No investment-to-job-count shortcut.**
9. **Human review remains possible.**
10. **Every derived output is versioned.**
11. **Every important insight has a Why/Evidence object.**
12. **Agents may extend the architecture but must not silently replace it.**

---

## 3. High-Level System

```text
                    EXTERNAL SOURCE ECOSYSTEM
                               |
                               v
                    +----------------------+
                    | Source Registry      |
                    | Access Verification  |
                    +----------+-----------+
                               |
                               v
                    +----------------------+
                    | INGESTION             |
                    | API / Export / Public |
                    | Page / Snapshot       |
                    +----------+-----------+
                               |
                               v
                    +----------------------+
                    | RAW DATA              |
                    | Source-shaped         |
                    +----------+-----------+
                               |
                               v
                    +----------------------+
                    | STAGING               |
                    | Parse / Validate /    |
                    | Deduplicate / Clean   |
                    +----------+-----------+
                               |
                               v
                    +----------------------+
                    | NORMALIZED DOMAIN     |
                    | Jobs / Skills /       |
                    | Occupations / Courses |
                    +----------+-----------+
                               |
              +----------------+----------------+
              |                |                |
              v                v                v
       Skill Intelligence  Occupation       Supply/
                           Intelligence      Curriculum
              |                |                |
              +----------------+----------------+
                               |
                               v
                    +----------------------+
                    | DEMAND INTELLIGENCE  |
                    +----------+-----------+
                               |
                               v
                    +----------------------+
                    | SKILL GAP ENGINE     |
                    +----------+-----------+
                               |
                               v
                    +----------------------+
                    | RECOMMENDATION       |
                    +----------+-----------+
                               |
                               v
                    +----------------------+
                    | FASTAPI /api/v1      |
                    +----------+-----------+
                               |
                               v
                    +----------------------+
                    | GOVERNMENT DASHBOARD  |
                    +----------+-----------+
                               |
                               v
                    HUMAN VALIDATION
```

---

## 4. Logical Data Layers

The layers are **logical boundaries**, not mandatory separate servers.

| Layer | Purpose | MVP implementation |
|---|---|---|
| Raw | Preserve source-shaped records | PostgreSQL JSON/text or files |
| Staging | Validate, clean, deduplicate | Python + PostgreSQL |
| Normalized | Canonical domain entities | PostgreSQL tables |
| Analytics | Demand/gap/recommendation views | PostgreSQL tables/views |
| Evidence | Explain derived values | Reusable evidence records/objects |

The MVP does not require a separate data lake, warehouse, stream processor or orchestration platform.

---

## 5. Source Registry

Every source receives a registry record.

Recommended fields:

```text
source_id
source_name
organization
url
category
access_method
freshness_class
last_verified_at
last_fetched_at
coverage
historical_depth
reliability_notes
legal/access_notes
enabled
```

### Access methods

Allowed values:

- VERIFIED_API
- VERIFIED_EXPORT
- PUBLIC_PAGE
- SOURCE_SNAPSHOT
- MANUAL_CURATION

Do not use `API` when the API has not been verified.

---

## 6. Source Families

### Demand

- NCS
- Apprenticeship India
- future private sources

### Skills/Occupations

- NCO
- NQR
- NSDC QP/NOS

### Training Supply

- SIDH
- Mahaswayam
- DVET
- DGT
- MSBTE

### Future Industrial Signals

- MIDC
- India Investment Grid
- MAITRI
- PARIVESH
- Maharashtra Industries Department

### Context

- PLFS
- Maharashtra State Data Bank
- AISHE
- Udyam

---

## 7. Connector Architecture

Each connector must implement a common conceptual interface:

```python
class SourceConnector(Protocol):
    source_id: str
    freshness_class: str
    access_method: str

    def fetch(self) -> Iterable[RawRecord]:
        ...

    def validate_access(self) -> AccessStatus:
        ...
```

The actual implementation may be synchronous.

A connector can be:

1. programmatic
2. export-based
3. public-page based
4. snapshot-based
5. manual curation

The connector must record what method was actually used.

---

## 8. Snapshot Strategy

A source snapshot is allowed for the MVP when:

- the information came from a legitimate public/official source
- the original URL is recorded
- retrieval date is recorded
- the access method is recorded
- the dataset is not presented as live

Example:

```text
source_name = NCS
access_method = SOURCE_SNAPSHOT
freshness_class = PERIODIC
source_url = https://www.ncs.gov.in/
retrieved_at = 2026-09-10T...
```

This is a reproducibility mechanism, not fabricated data.

---

## 9. Core Domain Entities

### `source`

Source registry.

### `ingestion_run`

One acquisition attempt.

Fields:

```text
run_id
source_id
started_at
completed_at
status
records_seen
records_loaded
records_failed
error_summary
```

### `raw_record`

Exact source payload.

```text
raw_id
source_id
source_record_id
payload
retrieved_at
source_timestamp
run_id
```

### `job_posting`

```text
job_id
source_id
source_record_id
title
description
employer
location
district
state
sector
posted_at
salary_min
salary_max
source_url
retrieved_at
```

### `skill`

```text
skill_id
canonical_name
description
category
parent_skill_id
ontology_version
```

### `skill_alias`

```text
alias_id
skill_id
alias
```

### `occupation`

```text
occupation_id
nco_code
title
description
sector
nco_version
```

### `course`

```text
course_id
name
provider
qualification
nsqf_level
sector
district
duration
source_id
```

### `institute`

```text
institute_id
name
type
district
affiliation
capacity
source_id
```

### `curriculum_skill_map`

```text
course_id
skill_id
coverage_level
evidence
source_id
provenance_state
```

### `job_posting_skill`

```text
job_id
skill_id
match_strength
confidence_type
evidence
model_version
generated_at
```

### `job_posting_occupation`

```text
job_id
occupation_id
confidence
confidence_type
evidence
model_version
generated_at
```

### `district_occupation_demand`

```text
district
sector
occupation_id
period_start
period_end
job_count
apprenticeship_count
recency_score
demand_score
evidence
provenance_state = DERIVED
model_version
generated_at
```

### `district_skill_demand`

Same pattern, aggregated for skills.

### `skill_gap`

```text
gap_id
district
occupation_id
course_id
required_skill_ids
covered_skill_ids
missing_skill_ids
coverage_percent
gap_severity
evidence
provenance_state = DERIVED
model_version
generated_at
```

### `recommendation`

```text
recommendation_id
district
course_id
gap_id
type
title
description
priority
evidence
validation_status
provenance_state = DERIVED
rule_version
generated_at
```

### `validation_record`

```text
validation_id
recommendation_id
status
reviewer_label
reviewed_at
comment
```

### `future_project_signal`

```text
project_id
project_name
source
source_url
sector
district
project_stage
expected_operation_date
investment_value
potential_occupations
potential_skills
provenance_state = ESTIMATED
methodology
```

---

## 10. Provenance Model

Every derived/estimated/predicted output must preserve:

```text
source_id
source_url
source_record_id
retrieved_at
source_timestamp
ingested_at
freshness_class
provenance_state
model_version / rule_version
generated_at
evidence
```

### Provenance states

```text
OBSERVED
DERIVED
ESTIMATED
PREDICTED
```

---

## 11. Evidence / Why Object

Create one standard evidence representation for the whole system.

Conceptual shape:

```json
{
  "evidence_id": "EV-001",
  "sources": [
    {
      "source_id": "NCS",
      "source_url": "https://www.ncs.gov.in/",
      "record_ids": ["..."]
    }
  ],
  "method": "skill_frequency_rule_v1",
  "records_used": 42,
  "matched_items": ["SQL", "Power BI"],
  "freshness_class": "PERIODIC",
  "provenance_state": "DERIVED",
  "rule_version": "demand_v1.0"
}
```

Every important dashboard insight should be able to open a Why panel from an evidence object.

---

## 12. Ontology Architecture

### Skill ontology

Canonical skills plus aliases.

Example:

```text
Microsoft Excel
 ├── MS Excel
 ├── Excel
 └── MS-Excel
```

Recommended skill fields:

```text
skill_id
canonical_name
category
parent_skill
description
ontology_version
```

### Occupation ontology

NCO reference data.

Never create or modify official NCO codes without verified reference data.

---

## 13. Deduplication

Duplicate jobs must not inflate labour-demand counts.

Preferred identity signals:

1. source-native source_record_id
2. normalized title
3. employer
4. location
5. posting date

The exact deduplication policy may use a deterministic hash for MVP.

Example conceptual key:

```text
hash(
 normalized_title +
 normalized_employer +
 normalized_location +
 posting_date
)
```

The system should preserve the source identity even when records are deduplicated.

---

## 14. AI Architecture

The MVP contains five intelligence components but only **two are true NLP/ML-style components**.

| Component | MVP | Future |
|---|---|---|
| Skill Extraction | Ontology + aliases + phrase matching | Transformer NER |
| Occupation Mapping | Rules/keywords; classifier only if justified | Semantic/transformer classification |
| Demand Intelligence | Analytical score | Calibrated ML / forecasting |
| Skill Gap | Set/coverage calculation | Weighted semantic gap |
| Recommendation | Deterministic rules | Optimization/learned ranking |

---

## 15. Skill Extraction

### Input

```text
title
description
```

### Output

```json
{
  "skills": [
    {
      "skill_id": "SK-001",
      "name": "Python",
      "evidence": ["Python"],
      "confidence": 1.0,
      "confidence_type": "MATCH_STRENGTH"
    }
  ],
  "model_version": "skill_rules_v1.0"
}
```

The numeric value must be computed from actual matching logic, not fabricated.

---

## 16. Occupation Mapping

### Input

Job title + description.

### Output

Verified occupation candidate(s):

```json
{
  "occupation": {
    "nco_code": "VERIFIED_CODE",
    "title": "VERIFIED_TITLE"
  },
  "confidence": 0.86,
  "confidence_type": "CLASSIFICATION_CONFIDENCE",
  "evidence": [
    "title keyword match",
    "description keyword match"
  ],
  "model_version": "occupation_rules_v1.0"
}
```

No unsupported NCO code examples should be hardcoded into production/demo data.

---

## 17. Demand Intelligence

MVP demand intelligence is analytical.

Recommended initial components:

```text
job volume
+
recency
+
apprenticeship signal when available
```

Example normalized conceptual formula:

```text
Demand Score =
    0.50 * Job Volume Signal
  + 0.30 * Recency Signal
  + 0.20 * Apprenticeship Signal
```

These weights are **MVP design constants, not empirical truth**. They must be documented and can be recalibrated after historical validation.

The score must expose its components.

Do not call it ML.

Example:

```text
Demand Score: 81/100
Job Volume Signal: High
Recency Signal: High
Apprenticeship Signal: Medium
Evidence Strength: High
```

If a component is unavailable, the implementation must either use a documented fallback or omit the component. It must not silently substitute fabricated values.

---

## 18. Skill-Demand Weight

For gap analysis, skill frequency can be converted into a normalized demand weight.

Example:

```text
skill_demand_weight =
frequency(skill among relevant postings)
/
maximum_skill_frequency
```

This is an analytical ranking weight, not a probability of employment.

---

## 19. Skill Gap

Basic MVP calculation:

```text
coverage =
number of demanded skills taught by course
/
number of demanded skills
```

Output:

```text
covered skills
missing skills
coverage_percent
gap_severity
evidence
```

MVP gap severity can be threshold-based, for example:

```text
HIGH    < 50%
MEDIUM  50%–79%
LOW     >= 80%
```

These thresholds are implementation defaults and should be documented in Memory.md once implemented.

---

## 20. Recommendation Rules

Examples:

### Curriculum update

```text
IF
skill is demanded above threshold
AND
course does not cover skill

THEN
recommend curriculum review
```

### Capacity review

```text
IF
occupation demand = HIGH
AND
training supply is low

THEN
recommend training-capacity review
```

### New course exploration

```text
IF
strong demand exists
AND
no relevant training coverage exists

THEN
recommend new-course exploration
```

Recommendations must cite evidence.

---

## 21. Future Industrial Demand

Post-MVP module:

```text
Industrial Project
      ↓
Sector
      ↓
District
      ↓
Project Stage
      ↓
Relevant occupations
      ↓
Relevant skills
```

Potential sources:

- MIDC
- India Investment Grid
- MAITRI
- PARIVESH
- Maharashtra Industries Department
- relevant GRs/policies

All project-derived workforce signals are:

```text
provenance_state = ESTIMATED
```

The system must not say:

> ₹X crore investment = Y jobs

unless a separately justified methodology exists.

---

## 22. API Architecture

All APIs use:

```text
/api/v1/
```

### Health

```http
GET /api/v1/health
```

### References

```http
GET /api/v1/reference/districts
GET /api/v1/reference/sectors
GET /api/v1/reference/occupations
```

### AI

```http
POST /api/v1/ai/skills
POST /api/v1/ai/occupation
GET  /api/v1/ai/demand/{district}
GET  /api/v1/ai/gaps/{occupation}
GET  /api/v1/ai/recommendations/{district}
```

### Validation

```http
POST /api/v1/recommendations/{id}/validate
```

---

## 23. Standard AI Response Envelope

Where applicable:

```json
{
  "result": {},
  "evidence": [],
  "confidence": 0.86,
  "confidence_type": "MATCH_STRENGTH",
  "model_version": "skill_rules_v1.0",
  "generated_at": "2026-09-10T10:00:00Z"
}
```

For analytical results where numeric confidence is misleading, use:

```json
{
  "result": {},
  "evidence_strength": "HIGH",
  "model_version": "demand_v1.0",
  "generated_at": "..."
}
```

---

## 24. Backend Structure

```text
api/
  main.py
  config.py
  routers/
  schemas/
  services/

core/
  models/
  ontology/
  provenance/
  evidence/

ingestion/
  sources/
  pipelines/
  fixtures/

ai/
  skill_extraction/
  occupation_mapping/
  demand_intelligence/
  skill_gap/
  recommendation/

db/
  migrations/
  seed/

dashboard/

tests/
  unit/
  integration/
  fixtures/

scripts/

docs/
  adr/

data/
  raw/
  staging/
  normalized/
  analytics/
```

---

## 25. Layer Responsibilities

### `ingestion/`

Only source acquisition and raw/staging processing.

### `core/`

Domain entities, ontology, evidence and provenance.

### `ai/`

Pure/callable intelligence modules. No FastAPI dependency.

### `api/`

HTTP contracts and orchestration.

### `dashboard/`

Presentation only. No direct database access.

---

## 26. Backend–AI Boundary

The AI layer must not know about HTTP.

The API layer calls service functions.

Example:

```text
POST /api/v1/ai/skills
        ↓
router
        ↓
service
        ↓
skill_extraction.extract(...)
        ↓
response schema
```

---

## 27. Batch vs Online Inference

### Batch

Use for:

- ingestion
- skill extraction across stored jobs
- occupation mapping across stored jobs
- demand aggregation
- skill-gap calculation
- recommendation generation

### Online

Use for:

- testing one job posting
- dashboard drill-down calculations that are cheap
- previewing skill extraction from text

Do not run large external ingestion jobs synchronously inside dashboard requests.

---

## 28. Database Access

API reads normalized/analytics tables.

AI modules may receive domain objects/dataframes from services.

Ingestion does not call AI directly during source fetch.

The pipeline can run:

```text
ingest
→ normalize
→ AI enrichment
→ analytics
```

as a local batch command for the MVP.

---

## 29. Frontend Architecture

Locked stack:

```text
React
TypeScript
Vite
```

The frontend talks only to FastAPI.

MVP views:

1. Overview
2. Occupation Detail
3. Skill Gap
4. Recommendations

Optional:

5. Future Project Signal

---

## 30. Deployment

### MVP

Docker Compose:

```text
api
postgres
```

Frontend may run separately using Vite during development/demo.

No mandatory scheduler container.

A simple Python CLI or scheduled script is sufficient for MVP ingestion.

### Later

Optional additions only after a concrete bottleneck is demonstrated.

---

## 31. Testing Architecture

### Unit

- skill extraction
- occupation mapping
- demand formula
- gap calculation
- recommendation rules
- normalization utilities

### Integration

- ingestion fixture → DB
- AI → DB
- API → DB
- recommendation validation

### No live-network dependency

Default tests use fixtures/snapshots.

---

## 32. Monitoring

MVP:

- ingestion log
- application logs
- source freshness information
- API error logging

Post-MVP:

- ingestion alerts
- freshness alerts
- model/data drift
- pipeline dashboards
- operational metrics

---

## 33. Security Boundaries

- No direct DB access from frontend.
- Secrets in environment variables.
- No credentials in Git.
- No bypass of CAPTCHAs/rate limits.
- No access to authenticated sources without permission.
- No real government SSO in MVP.

---

## 34. Scalability Path

The MVP architecture scales primarily by:

- adding source connectors
- loading more districts
- extending ontology
- expanding normalized data
- refreshing analytics

Do not add distributed infrastructure merely because statewide scaling is planned.

---

## 35. Failure Strategy

If one source fails:

```text
Source A fails
        ↓
log failure
        ↓
Source B continues
        ↓
dashboard marks missing/stale data
```

The entire platform should not fail because one external source is unavailable.

---

## 36. Architecture Decision Rules

Any proposed addition of:

- Kafka
- Kubernetes
- Airflow
- Elasticsearch
- MLflow
- vector database
- external orchestration
- new AI framework

requires:

1. concrete problem
2. measured limitation of current architecture
3. ADR
4. Architecture.md update

---

## 37. MVP Architecture Principle

**Build the smallest system that proves the intelligence loop.**

The architecture must never become an excuse for not reaching:

**Data → AI → Demand → Gap → Recommendation → API → Dashboard**
