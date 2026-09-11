# Maharashtra Labour-Market Intelligence & Curriculum-Alignment Platform

**Status:** Phase 0 — Project Foundation Complete  
**Demo Date:** 15 September 2026  
**Pilot District:** Pune  
**Pilot Sectors:** IT-ITeS, Automotive/Manufacturing, Electronics

---

## Project Overview

This platform connects labour demand, skills, occupations, training supply and curriculum evidence to help Government of Maharashtra stakeholders identify gaps and make evidence-backed workforce-development decisions.

**Core Loop:** Observe → Understand → Measure → Compare → Recommend → Human Validate → Learn

---

## Phase 0 Foundation

The current implementation provides:

- ✅ FastAPI backend with health check endpoint
- ✅ PostgreSQL database configuration
- ✅ Alembic migration framework with Source Registry schema
- ✅ React + TypeScript + Vite frontend shell
- ✅ Docker Compose development environment
- ✅ Project structure aligned with Architecture.md
- ✅ Environment configuration
- ✅ Test framework setup

---

## Quick Start

### Prerequisites

- Docker & Docker Compose
- Python 3.11+
- Node.js 18+ (for frontend development)

### 1. Environment Setup

```bash
# Copy environment template
cp .env.example .env

# Edit .env with your configuration if needed
```

### 2. Start Backend Services

```bash
# Start PostgreSQL and API
docker compose up -d

# Check service health
curl http://localhost:8000/api/v1/health
```

### 3. Run Database Migrations

```bash
# Inside the API container or with local Python environment
alembic upgrade head
```

### 4. Start Frontend (Development)

```bash
cd frontend
npm install
npm run dev
```

The frontend will be available at `http://localhost:3000`

---

## Project Structure

```
Demand-X/
├── api/                    # FastAPI application
│   ├── main.py            # Application entry point
│   ├── config.py          # Settings management
│   ├── routers/           # API route handlers
│   ├── schemas/           # Pydantic schemas
│   └── services/          # Business logic services
├── core/                   # Domain models and logic
│   ├── models/            # SQLAlchemy models
│   ├── ontology/          # Skills and occupation ontology
│   ├── provenance/        # Data provenance tracking
│   └── evidence/          # Evidence and explanation objects
├── ingestion/              # Data acquisition
│   ├── sources/           # Source-specific connectors
│   ├── pipelines/         # ETL pipelines
│   └── fixtures/          # Test fixtures
├── ai/                     # Intelligence modules
│   ├── skill_extraction/  # Skill extraction from job text
│   ├── occupation_mapping/# Job to NCO mapping
│   ├── demand_intelligence/# Demand scoring
│   ├── skill_gap/         # Gap analysis
│   └── recommendation/    # Recommendation engine
├── db/                     # Database management
│   ├── migrations/        # Alembic migrations
│   ├── session.py         # Database session management
│   └── seed/              # Seed data scripts
├── frontend/               # React frontend
│   └── src/
│       ├── App.tsx        # Main application component
│       └── main.tsx       # Entry point
├── tests/                  # Test suite
│   ├── unit/              # Unit tests
│   ├── integration/       # Integration tests
│   └── fixtures/          # Test fixtures
├── data/                   # Data storage
│   ├── raw/               # Raw source data
│   ├── staging/           # Staged/cleaned data
│   ├── normalized/        # Normalized domain entities
│   └── analytics/         # Analytics outputs
├── docs/                   # Documentation
│   └── adr/               # Architecture Decision Records
└── scripts/                # Utility scripts
```

---

## API Endpoints

### Health Check

```http
GET /api/v1/health
```

Returns system status, database connectivity, and pilot configuration.

**Response:**
```json
{
  "status": "healthy",
  "app_name": "Maharashtra Labour-Market Intelligence & Curriculum-Alignment Platform",
  "environment": "development",
  "database": "healthy",
  "pilot_district": "Pune",
  "sectors": ["IT-ITeS", "Automotive/Manufacturing", "Electronics"]
}
```

---

## Source Registry

The Source Registry tracks all data sources with:

- **source_id**: Unique identifier
- **source_name**: Human-readable name
- **organization**: Source organization
- **url**: Source URL
- **category**: Data category (demand/supply/reference)
- **access_method**: One of `VERIFIED_API`, `VERIFIED_EXPORT`, `PUBLIC_PAGE`, `SOURCE_SNAPSHOT`, `MANUAL_CURATION`
- **freshness_class**: One of `LIVE`, `PERIODIC`, `HISTORICAL`, `STATIC`
- **last_verified_at**: Last verification timestamp
- **last_fetched_at**: Last fetch timestamp
- **coverage**: Coverage description
- **historical_depth**: Historical data availability
- **reliability_notes**: Reliability observations
- **legal_access_notes**: Access restrictions/permissions
- **enabled**: Whether source is active

---

## Development Workflow

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=api --cov=core --cov=ai --cov=ingestion

# Run specific test file
pytest tests/unit/test_health.py
```

### Database Migrations

```bash
# Create a new migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1

# View migration history
alembic history
```

### Code Quality

```bash
# Format code
black .

# Lint code
ruff check .
```

---

## Key Architecture Principles

1. **Evidence First** — Every derived insight has a traceable evidence path
2. **Source Provenance Preserved** — Original source records are immutable
3. **Rules/Analytics Before ML** — Start with deterministic logic
4. **AI and API Separated** — Intelligence modules are HTTP-independent
5. **Human Review Required** — Recommendations support Accept/Reject/Needs Review

---

## Data Integrity Rules

- ❌ Never invent data
- ❌ Never invent government APIs
- ❌ Never fake integrations
- ❌ Never claim real-time without evidence
- ❌ Never fabricate model accuracy
- ❌ Never fabricate test results
- ✅ Always preserve provenance
- ✅ Always mark estimates and predictions
- ✅ Always require human review for recommendations
- ✅ Always provide explainability

---

## Phase 1 Status

**Important**: Phase 1A ingestion pipeline architecture has been implemented and tested using **unverified fixture data**. No verified NCS source data has been acquired yet.

- ✅ Ingestion pipeline architecture implemented
- ✅ Staging and normalized models with provenance
- ✅ **DVET Supply Data (Partially Verified)**: ITI Haveli verified snapshot (`data/raw/dvet_pune/dvet_pune_haveli_verified_snapshot.json` with 1 institute, Institute Code `2765211006`, NCVT MIS Code `GU27000616`, and 10 verified trade rows)
- ⏸️ Verified NCS source acquisition **PENDING**
- ⚠️ Test fixture at `data/fixtures/ncs_pune_jobs_unverified_fixture.json` is classified as `UNVERIFIED_OR_SYNTHETIC` and must NOT be used as production data

## Next Steps

1. **Verified Source Acquisition** — Acquire legitimate NCS data via verified API, export, or official snapshot
2. **Additional Sources** — Apprenticeship India, SIDH / Mahaswayam / DVET / MSBTE
3. **Normalization** — Build data cleaning and normalization pipelines
4. **Ontology Seed** — Create initial skill taxonomy with aliases
5. **Skill Extraction** — Implement deterministic skill extraction
6. **Occupation Mapping** — Map jobs to verified NCO codes

---

## Documentation

- **PRD.md** — Product requirements and scope
- **Architecture.md** — Technical architecture and design decisions
- **Rules.md** — Coding agent constitution and integrity rules
- **Phases.md** — Implementation roadmap and milestones
- **Design.md** — UI/UX design system and guidelines
- **Memory.md** — Live implementation state tracking

---

## Technology Stack

### Backend
- Python 3.11+
- FastAPI
- SQLAlchemy
- Alembic
- PostgreSQL
- Pydantic

### Frontend
- React 18
- TypeScript
- Vite

### Infrastructure
- Docker
- Docker Compose

### Future (Post-MVP)
- spaCy (NLP preprocessing)
- scikit-learn (classification where justified)
- sentence-transformers (semantic similarity)

---

## License

Government of Maharashtra — Department of Skills, Employment, Entrepreneurship and Innovation

---

## Contact

**Project Owner:** Piyush Sharma / SIH Team  
**Problem Statement:** SIH 26134  
**Organization:** Maharashtra State Innovation Society
