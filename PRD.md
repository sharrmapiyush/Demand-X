# PRD.md — Maharashtra Labour-Market Intelligence & Curriculum-Alignment Platform

| Field | Value |
|---|---|
| Status | **IMPLEMENTATION READY — v0.2** |
| Owner | Piyush Sharma / SIH Team |
| Problem Statement | SIH 26134 — Challenges in aligning skill development programs with industry requirements and emerging job market demands |
| Organization | Government of Maharashtra — Department of Skills, Employment, Entrepreneurship and Innovation / Maharashtra State Innovation Society |
| Internal Demo | **15 September 2026** |
| Scope Lock | **MVP vertical slice** |
| Pilot District | **Pune** |
| Pilot Sectors | **IT-ITeS, Automotive/Manufacturing, Electronics** |
| Companion Docs | Architecture.md · Rules.md · Phases.md · Design.md |
| Live Project Status | Code is not assumed to exist until recorded in Memory.md |

---

## 1. Product Vision

Build a labour-market intelligence and curriculum-alignment platform that connects labour demand, skills, occupations, training supply and curriculum evidence so that government stakeholders can identify gaps and make evidence-backed workforce-development decisions.

The platform is a **decision-support system**, not a chatbot and not a replacement for government decision-making.

Core loop:

**Observe → Understand → Measure → Compare → Recommend → Human Validate → Learn**

For the 15 September 2026 internal SIH demonstration, the system will prove this loop for a constrained Pune pilot instead of attempting statewide coverage.

---

## 2. Problem

Skill-development planning can lag changes in employer demand, occupations and required skills. The project addresses the missing connective layer between:

- current labour-market demand
- apprenticeship demand
- demanded skills
- standard occupations
- available training
- curriculum coverage
- skill gaps
- actionable recommendations
- future industrial signals

The product should make these relationships inspectable rather than hiding them behind a single opaque AI score.

---

## 3. Primary Users

| User | Need | MVP |
|---|---|---|
| Government / Policy Official | Demand, skill gaps, course gaps, recommendations, evidence | **Primary** |
| Skill Planning Official | Sector/occupation analysis and curriculum alignment | **Primary** |
| Training Institute | Course-to-market alignment | **Secondary read/review** |
| Employer | Demand submission and validation | Future |
| Candidate | Career/skill guidance | Future |

The MVP does not provide an LLM chat interface.

---

## 4. MVP Goal — 15 September 2026

The MVP must demonstrate one complete path:

**Official/publicly sourced labour data**
→ **normalized data**
→ **skill extraction**
→ **occupation mapping**
→ **labour demand score**
→ **course/curriculum comparison**
→ **skill gap**
→ **recommendation**
→ **FastAPI**
→ **government-style dashboard**

A successful demo does not require statewide coverage, production authentication, automated access to every portal, advanced forecasting, or transformer-based models.

---

## 5. MVP Scope Lock

### 5.1 Geography

**Pune district**

The application must not hardcode Pune into business logic. Pune is the initial dataset scope; all domain logic must remain reusable for another district later.

### 5.2 Sectors

1. IT-ITeS
2. Automotive/Manufacturing
3. Electronics

The implementation should load only the occupations and courses actually supported by the available data.

### 5.3 MVP occupation scope

Start with approximately **5–10 occupations total**. Exact occupations are selected from verified source availability during Phase 1.

Examples of candidate occupations:

- Software Developer
- Data Analyst
- IT Support / Systems Support
- CNC / Machine Operator
- Automobile Technician
- Industrial / Maintenance Technician
- Electronics Technician
- Production / Quality Technician

**Important:** NCO codes must never be invented. Final occupation names and codes must be verified against the actual NCO reference data before being stored as official mappings.

---

## 6. Data Source Strategy

### Primary MVP sources

| Source | Link | Purpose | MVP role |
|---|---|---|---|
| National Career Service (NCS) | https://www.ncs.gov.in/ | Jobs | Primary demand |
| Apprenticeship India | https://www.apprenticeshipindia.gov.in/ | Apprenticeships | Secondary demand |
| Skill India Digital Hub (SIDH) | https://www.skillindiadigital.gov.in/ | Training | Supply |
| Mahaswayam / MSSDS | https://kaushalya.mahaswayam.gov.in/ | Maharashtra skilling | Supply/support |
| NCO | https://labour.gov.in/ | Occupation taxonomy | Reference |
| NQR | https://nqr.gov.in/ | Qualifications | Curriculum/reference |
| NSDC | https://www.nsdcindia.org/ | QP/NOS/standards | Skills/curriculum |
| DGT | https://dgt.gov.in/ | ITI trades/curriculum | Curriculum |
| DVET Maharashtra | https://www.dvet.gov.in/ | ITIs/institutes | Supply |
| MSBTE | https://www.msbte.ac.in/ | Diploma/curriculum | Supply/curriculum |

### Future-demand sources

| Source | Link | Purpose |
|---|---|---|
| MIDC | https://midc.maharashtra.gov.in/ | Industrial areas/projects |
| India Investment Grid | https://indiainvestmentgrid.gov.in/ | Investment/project pipeline |
| MAITRI | https://maitri.mahaonline.gov.in/ | Investment facilitation/projects |
| PARIVESH | https://parivesh.nic.in/ | Environmental/project approvals |
| Maharashtra Industries Department | https://industry.maharashtra.gov.in/ | Policies/GRs |
| Maharashtra State Data Bank | https://www.mahasdb.maharashtra.gov.in/ | District economic context |
| PLFS | https://mospi.gov.in/plfs | Labour-market context |
| AISHE | https://aishe.gov.in/ | Higher-education supply context |
| Udyam | https://udyamregistration.gov.in/ | MSME context |

### Supplementary private sources

LinkedIn, Naukri, Indeed, Foundit and employer career pages may be added later only through legitimate, permitted access.

No private-source integration is required for the 15 September MVP if it creates delivery risk.

---

## 7. Data Freshness Policy

The product uses source-specific freshness classes:

- **LIVE** — genuinely near-current with verified frequent updates
- **PERIODIC** — refreshed on a recurring but non-continuous cycle
- **HISTORICAL** — primarily useful for baseline/context
- **STATIC** — reference/taxonomy/curriculum data not expected to change frequently

The system must never label a source LIVE merely because it is an online website.

The MVP must remain functional if a portal is temporarily unavailable.

A legitimate downloaded/exported/public snapshot may be used as a **SOURCE_SNAPSHOT** / **MANUAL_CURATION** input for the demo. It must retain the original source URL, retrieval date and access method.

---

## 8. Core Product Features

### 8.1 Source Registry

Tracks:

- source_id
- source_name
- organization
- URL
- category
- access_method
- freshness_class
- last_verified_at
- last_fetched_at
- coverage
- notes

### 8.2 Job Demand Intelligence

Collect and normalize:

- job title
- description
- employer
- location
- district
- sector
- posted date
- salary when legitimately available
- source
- source record ID
- retrieval timestamp

### 8.3 Skill Intelligence

Extract canonical skills from job text.

The first implementation is deterministic:

**ontology + aliases + dictionary/phrase matching + text preprocessing**

### 8.4 Occupation Intelligence

Map a job to a verified NCO occupation.

The MVP begins with rules/keyword matching. A simple classifier may be introduced only if enough labeled data exists and time permits.

### 8.5 Demand Intelligence

Produce:

- occupation demand ranking
- skill demand ranking
- demand score
- component evidence
- freshness
- evidence strength

This is an **analytical score**, not a trained forecast model.

### 8.6 Training/Curriculum Intelligence

Map courses/curricula to skills.

Compare:

**Market-required skills VS course-covered skills**

### 8.7 Skill Gap

Produce:

- required skills
- covered skills
- missing skills
- coverage percentage
- demand-weighted gap where supported
- gap severity
- evidence

### 8.8 Recommendation Engine

Initial recommendations are rule-based.

Examples:

- add missing skill to curriculum
- review course alignment
- consider increasing training capacity
- consider trainer/equipment intervention
- consider new course exploration

A recommendation is not a government order. It is a reviewable decision-support suggestion.

### 8.9 Evidence / Why Panel

Every derived result must explain:

- source(s)
- records used
- transformation/rule
- freshness
- provenance
- model/rule version
- confidence or evidence strength where applicable

---

## 9. Provenance Model

Every important record is classified as:

| State | Meaning |
|---|---|
| OBSERVED | Directly sourced/parsed information |
| DERIVED | Deterministic computation from observed data |
| ESTIMATED | Computation requiring material assumptions |
| PREDICTED | Forecast/model output |

Future industrial workforce signals are ESTIMATED unless validated independently.

Investment amount must never be directly converted into an exact job count.

---

## 10. Confidence / Evidence Policy

The project must not use one generic number to imply false statistical certainty.

Use `confidence_type` where a numeric confidence is meaningful.

Examples:

- `MATCH_STRENGTH`
- `CLASSIFICATION_CONFIDENCE`
- `EVIDENCE_STRENGTH`
- `DATA_COMPLETENESS`

For analytical demand outputs, prefer **Evidence Strength** when appropriate rather than pretending that a demand score is a probability.

Never use placeholder values such as `0.90` just to fill a schema.

---

## 11. Functional Requirements

### FR-01 — Source ingestion
The system shall ingest at least one real/officially sourced demand dataset and at least one real/officially sourced training/curriculum dataset for the pilot slice.

### FR-02 — Raw preservation
Original source records shall be preserved before transformation.

### FR-03 — Normalization
The system shall normalize records to canonical entities.

### FR-04 — Skill extraction
The system shall extract canonical skills with evidence.

### FR-05 — Occupation mapping
The system shall map supported jobs to verified NCO occupations.

### FR-06 — Demand score
The system shall calculate an inspectable occupation/skill demand score.

### FR-07 — Supply/curriculum mapping
The system shall identify skills taught by selected courses/curricula.

### FR-08 — Skill gap
The system shall identify missing market-relevant skills.

### FR-09 — Recommendation
The system shall produce at least one evidence-linked recommendation.

### FR-10 — API
The backend shall expose the intelligence through versioned FastAPI endpoints.

### FR-11 — Dashboard
The frontend shall visualize the complete pilot flow.

### FR-12 — Human validation
Recommendations shall support:

- ACCEPTED
- REJECTED
- NEEDS_REVIEW

### FR-13 — Traceability
Derived outputs shall trace to their underlying data and rule/model version.

---

## 12. Non-Functional Requirements

### NFR-01 — Explainability
No important AI/analytical result ships without an evidence trail.

### NFR-02 — Honest freshness
No unsupported “real-time” claims.

### NFR-03 — Reproducibility
Given the same input snapshot and rule/model version, deterministic MVP outputs should be reproducible.

### NFR-04 — Modularity
Data ingestion, AI, analytics, API and frontend concerns remain separable.

### NFR-05 — Rapid development
The MVP must run on a developer machine using simple infrastructure.

### NFR-06 — Security
No credentials in source code; no bypass of access controls.

### NFR-07 — Privacy
No candidate PII is required for the MVP.

---

## 13. MVP Dashboard Journeys

### Journey A — District demand

Pune → occupation ranking → demand score → evidence.

### Journey B — Occupation intelligence

Occupation → demanded skills → representative jobs → skill evidence.

### Journey C — Curriculum gap

Course → covered skills → demanded skills → missing skills → gap severity.

### Journey D — Recommendation

Skill gap → recommendation → evidence → Accept/Reject/Needs Review.

### Optional Journey E — Future industrial signal

Selected project → source → sector → district → potential occupations/skills → **ESTIMATED** label.

This is optional for 15 September and must never block the core demo.

---

## 14. MVP Success Criteria — 15 September 2026

The internal demo is successful when the team can demonstrate:

1. Real/officially sourced job or apprenticeship records with provenance.
2. Skill extraction with visible evidence.
3. Occupation mapping using verified NCO data.
4. Ranked occupation demand for Pune.
5. At least one real course/curriculum comparison.
6. At least one concrete skill gap.
7. At least one evidence-linked recommendation.
8. FastAPI serving the results.
9. Dashboard rendering the end-to-end flow.
10. Freshness/provenance labels visible in the UI.
11. No fabricated source/API/model/test claims.

---

## 15. Explicit Non-Goals for 15 September

Do not build:

- statewide coverage
- all occupations
- all government portals
- all private job portals
- custom LLM/chatbot
- transformer skill extraction
- full semantic occupation model
- demand forecasting
- production government SSO
- complex workflow/approval systems
- Kafka
- Kubernetes
- Airflow
- Elasticsearch
- MLflow
- automated future-project workforce forecasting

---

## 16. Future Scope

After the internal demo:

- statewide expansion
- more sectors
- semantic embeddings
- transformer-based extraction/classification
- calibrated demand prediction
- time-series forecasting
- employer demand portal
- placement outcomes
- candidate guidance
- full future-industrial-demand intelligence
- human feedback-driven model improvement
- advanced optimization
- production monitoring and governance

---

## 17. Product Decision Principle

The platform **assists** government decision-makers.

It does not autonomously decide:

- which course must be launched
- how many seats must be approved
- which trainer must be hired
- which institute must be funded
- which policy must be adopted

Those remain human decisions supported by evidence.

---

## 18. Open Decisions

Only decisions genuinely requiring implementation-time verification may remain open:

| Decision | Status |
|---|---|
| Pune pilot | **LOCKED** |
| 3 sectors | **LOCKED** |
| Frontend | **LOCKED: React + TypeScript + Vite** |
| Backend | **LOCKED: FastAPI + PostgreSQL** |
| MVP AI | **LOCKED: rules/analytics first** |
| NCS access method | **VERIFY ACTUAL ACCESS BEFORE CODING** |
| Apprenticeship access method | **VERIFY ACTUAL ACCESS BEFORE CODING** |
| Exact MVP occupations | **SELECT FROM VERIFIED DATA IN PHASE 1** |
| Private job sources | **NOT REQUIRED FOR MVP** |
| Production authentication | **FUTURE** |

---

## 19. Source of Truth Hierarchy

When documents conflict:

1. Rules.md
2. PRD.md
3. Architecture.md
4. Phases.md
5. Design.md
6. Memory.md records implementation reality once it exists

If a conflict is discovered, stop and resolve it rather than silently choosing a path.
