# Phases.md — Implementation Roadmap

| Field | Value |
|---|---|
| Status | **IMPLEMENTATION READY — v0.2** |
| Current Date | 9 September 2026 |
| Internal Demo | **15 September 2026** |
| Pilot | **Pune** |
| Sectors | **IT-ITeS · Automotive/Manufacturing · Electronics** |
| Development Mode | **Parallel agent workstreams** |

---

# 1. Execution Philosophy

The September 15 objective is a **working vertical slice**, not a production platform.

Agents may work in parallel, but all work must obey:

```text
PRD.md
Architecture.md
Rules.md
Phases.md
Design.md
```

The daily priority is:

**integrate early → test early → demo early**

Do not wait until September 14 to discover that data, AI and frontend contracts do not fit together.

---

# 2. Critical Path

The minimum path is:

```text
Source/Data
   ↓
Normalized jobs
   ↓
Skills
   ↓
Occupations
   ↓
Demand
   ↓
Curriculum
   ↓
Gap
   ↓
Recommendation
   ↓
API
   ↓
Dashboard
```

If time is running out, cut breadth, not the end-to-end path.

---

# 3. Workstreams

Agents may work on four parallel tracks:

### Workstream A — Data

- source verification
- source registry
- collectors
- snapshots
- normalization
- ontology seed

### Workstream B — AI

- skill extraction
- occupation mapping
- demand
- skill gap
- recommendation

### Workstream C — Backend

- database
- models
- migrations
- FastAPI
- integration tests

### Workstream D — Dashboard

- overview
- occupation
- skill gap
- recommendations
- evidence panel

All workstreams integrate against shared contracts.

---

# 4. Phase 0 — Foundation

**Target: 9 September**

### Objective

Make the repository runnable and eliminate architectural ambiguity.

### Tasks

- create repository structure
- create project environment
- PostgreSQL setup
- FastAPI skeleton
- React/Vite skeleton
- environment configuration
- migrations
- source registry schema
- health endpoint
- initial Memory.md

### Decisions locked

```text
Pune
IT-ITeS
Automotive/Manufacturing
Electronics
FastAPI
PostgreSQL
React + TypeScript + Vite
```

### Acceptance

```text
docker compose up
→ API runs
→ PostgreSQL runs
→ /api/v1/health works
→ frontend runs
```

### Do not build

- advanced AI
- forecasting
- private-source connectors
- future-demand automation

---

# 5. Phase 1 — Data Acquisition

**Target: 9–10 September**

### Objective

Get the first trustworthy data snapshot into the system.

### Priority sources

1. NCS
2. Apprenticeship India
3. One supply source: SIDH / Mahaswayam / DVET / MSBTE
4. NCO reference
5. NSDC/NQR/DGT curriculum reference as available

### Source rule

Before building a programmatic connector:

```text
verify access
→ record method
→ test access
→ then code
```

If programmatic access is unavailable:

```text
public/official snapshot
OR
manual curated CSV
```

with explicit provenance.

### Minimum target

Enough records to make the demo meaningful.

Suggested initial target:

```text
100–500 job records
20–100 apprenticeship/course records as available
5–10 occupations
10–30 canonical skills initially
```

These are operational targets, not fabricated claims of current source volume.

### Acceptance

Every record has:

- source
- URL
- retrieval date
- raw payload/reference

### Do not build

- all Maharashtra sources
- every private job board
- future-project automation

---

# 6. Phase 2 — Normalization + Ontology

**Target: 10 September**

### Objective

Convert raw data into stable domain entities.

### Tasks

- parse source records
- normalize text
- normalize district
- normalize sector
- deduplicate jobs
- create skills
- create aliases
- import verified NCO reference data
- map initial courses/institutes

### Acceptance

Every normalized record can be traced back to raw source data.

### Do not build

- ontology auto-learning
- transformer models
- semantic clustering

---

# 7. Phase 3 — Skill Intelligence

**Target: 10 September**

### Objective

Turn job text into canonical skills.

### MVP method

```text
normalize text
→ alias matching
→ phrase matching
→ skill evidence
```

spaCy may be used for preprocessing if useful.

### Output

```json
{
  "skills": [
    {
      "skill_id": "SK001",
      "name": "Python",
      "evidence": ["Python"],
      "confidence": 1.0,
      "confidence_type": "MATCH_STRENGTH"
    }
  ],
  "model_version": "skill_rules_v1.0"
}
```

### Acceptance

A real posting generates visible skill evidence.

### Do not build

- transformer NER
- LLM extraction
- automatic ontology generation

---

# 8. Phase 4 — Occupation Intelligence

**Target: 10–11 September**

### Objective

Map supported jobs to verified NCO occupations.

### MVP method

1. normalize title
2. rules/keywords
3. optional simple classifier only if data is sufficient

### Acceptance

At least the demo occupations have verified NCO mappings.

Every mapping has evidence.

### Do not build

- full NCO classifier
- nationwide occupation mapping

---

# 9. Phase 5 — Demand Intelligence

**Target: 11 September**

### Objective

Produce a ranked demand view.

### MVP score

Use:

```text
50% job-volume signal
30% recency signal
20% apprenticeship signal
```

Normalize each component.

Expose the components.

### Output

```text
Occupation
Job Count
Apprenticeship Count
Recency
Demand Score
Evidence Strength
```

### Trend

Only show a trend if there is genuine historical/periodic data.

Otherwise:

```text
Trend: Insufficient history
```

### Acceptance

Same data snapshot + same rule version = same score.

### Do not build

- forecasting
- XGBoost
- deep learning
- fake historical trend lines

---

# 10. Phase 6 — Training + Curriculum

**Target: 11–12 September**

### Objective

Map selected courses/curricula to skills.

### Tasks

- collect real curriculum descriptions/syllabi
- extract/curate skills
- create curriculum_skill_map
- associate courses with occupations where supported

Manual curation is acceptable for a limited MVP.

### Acceptance

At least one course has a traceable skill map.

### Do not build

- statewide curriculum mapper
- semantic curriculum transformer

---

# 11. Phase 7 — Skill Gap

**Target: 12 September**

### Objective

Compare market demand against training coverage.

### MVP logic

```text
required skills
        MINUS
covered skills
        =
missing skills
```

Calculate:

```text
coverage_percent
gap_severity
```

Optional demand weighting:

```text
skill_demand_weight
```

### Acceptance

At least one genuine gap can be traced from:

```text
job evidence
→ skill demand
→ course curriculum
→ missing skill
```

---

# 12. Phase 8 — Recommendation Engine

**Target: 12 September**

### Objective

Turn a validated gap into an actionable suggestion.

### Example rules

```text
High skill demand
+
course missing skill
=
Curriculum Review
```

```text
High occupation demand
+
low training supply
=
Capacity Review
```

```text
High demand
+
no relevant course
=
New Course Exploration
```

### Acceptance

At least one recommendation has:

- title
- rationale
- evidence
- source
- rule version
- validation status

### Do not build

- autonomous government decisions
- LLM-generated policy
- optimization engine

---

# 13. Phase 9 — FastAPI Integration

**Target: 12–13 September**

### Endpoints

```http
GET  /api/v1/health

GET  /api/v1/reference/districts
GET  /api/v1/reference/sectors
GET  /api/v1/reference/occupations

POST /api/v1/ai/skills
POST /api/v1/ai/occupation

GET /api/v1/ai/demand/{district}
GET /api/v1/ai/gaps/{occupation}
GET /api/v1/ai/recommendations/{district}

POST /api/v1/recommendations/{id}/validate
```

### Acceptance

Dashboard can retrieve actual data through API.

### Do not build

- production auth
- distributed services
- public API gateway

---

# 14. Phase 10 — Dashboard

**Target: 13–14 September**

### Screen 1 — Overview

Show:

- district
- top occupations
- demand
- top skills
- data freshness

### Screen 2 — Occupation

Show:

- occupation
- demand score
- job volume
- top skills
- evidence

### Screen 3 — Skill Gap

Show:

- course
- required skills
- covered skills
- missing skills
- coverage
- severity

### Screen 4 — Recommendations

Show:

- recommendation
- why
- evidence
- confidence/evidence strength
- Accept
- Reject
- Needs Review

### Acceptance

The full vertical slice can be demonstrated live.

---

# 15. Phase 11 — Demo Hardening

**Target: 14 September**

### Tasks

- freeze source snapshot
- run all data pipelines
- run tests
- verify all API endpoints
- test empty/error states
- remove fake placeholders
- verify all source labels
- verify all model/rule versions
- verify no fabricated numbers
- prepare demo dataset backup
- prepare offline fallback

### Critical

Create a backup path:

```text
database snapshot
+
source snapshots
+
frontend build
+
API running locally
```

Do not depend on the internet during the presentation.

---

# 16. Phase 12 — Presentation Readiness

**Target: 15 September**

Demo sequence:

```text
1. Choose Pune
2. Show current demand
3. Open occupation
4. Show required skills
5. Open course/curriculum
6. Show skill gap
7. Show recommendation
8. Open evidence
9. Show human validation
10. Explain future industrial-demand extension
```

---

# 17. Stretch Feature — Future Industrial Signal

Only attempt after core demo is stable.

Possible sources:

- MIDC
- India Investment Grid
- MAITRI
- PARIVESH
- Maharashtra Industries Department

Use one or two manually verified examples only.

Label:

```text
ESTIMATED
PROJECT-DERIVED SIGNAL
```

Do not build automated future-project ingestion before the core demo is reliable.

---

# 18. Parallel Agent Assignment

### Agent A — Data

Own:

```text
ingestion/
data/
ontology seed
source registry
```

### Agent B — AI

Own:

```text
ai/skill_extraction
ai/occupation_mapping
ai/demand_intelligence
ai/skill_gap
ai/recommendation
```

### Agent C — Backend

Own:

```text
core/models
db/migrations
api/
tests/integration
```

### Agent D — Dashboard

Own:

```text
dashboard/
```

Agents must not edit each other's areas without coordination.

---

# 19. Integration Checkpoints

At least once per day:

### Checkpoint A

Data → database

### Checkpoint B

Database → AI

### Checkpoint C

AI → API

### Checkpoint D

API → dashboard

### Checkpoint E

Full demo

Do not allow integration to happen only at the end.

---

# 20. Definition of Done — September 15

```text
[ ] Real/official source data exists
[ ] Source metadata exists
[ ] Raw snapshot exists
[ ] Normalized jobs exist
[ ] Skills exist
[ ] Occupations exist
[ ] Demand ranking works
[ ] Course/curriculum data exists
[ ] Skill gap works
[ ] Recommendation works
[ ] Evidence works
[ ] FastAPI works
[ ] Dashboard works
[ ] Human validation works
[ ] Tests have actually run
[ ] Backup snapshot exists
[ ] Demo works offline/local
```

---

# 21. Post-Demo Phases

## Phase 13 — Source Expansion

Add more government/private sources.

## Phase 14 — Semantic Intelligence

Embeddings and transformer models.

## Phase 15 — Forecasting

Historical time-series demand forecasting.

## Phase 16 — Future Workforce Intelligence

Automated project → occupation → skill signals.

## Phase 17 — Employer Validation

Employer demand submission and validation.

## Phase 18 — Placement Intelligence

Use actual placement/outcome data.

## Phase 19 — Statewide Scale

Add districts and sectors.

## Phase 20 — Governance and Production

Monitoring, security, access control, audit, operational SLAs.
