---
name: project-foundation-state
description: Phase 0 and Phase 1A implementation state for Maharashtra Labour-Market Intelligence & Curriculum-Alignment Platform with rigorously audited provenance
metadata:
  type: project
---

# Memory.md — Implementation State

- **Project Name:** Maharashtra Labour-Market Intelligence & Curriculum-Alignment Platform
- **Current Phase:** Phase 2A — Ontology Seed (Authoritative Skill Seed & Trade-to-Skill Mappings)
- **Demo Date:** 15 September 2026
- **Pilot District:** Pune
- **Pilot Sectors:** IT-ITeS, Automotive/Manufacturing, Electronics

## What has actually been implemented and verified
- Project specification documents reviewed (PRD.md, Architecture.md, Rules.md, Phases.md, Design.md).
- Root configuration and tooling setup (`pyproject.toml`, `.env.example`, `.gitignore`, `docker-compose.yml`).
- FastAPI backend structure (`api/`, `core/`, `ingestion/`, `ai/`, `db/`, `tests/`) initialized.
- Health check endpoint (`GET /api/v1/health`) implemented and verified.
- Database foundation & Alembic migration configuration with Source Registry schema (`sources` table & `alembic_version`).
- Docker Compose services (`postgres`, `api`) verified running and healthy.
- Alembic database migrations (`alembic upgrade head`) successfully executed against PostgreSQL.
- React + TypeScript + Vite frontend shell structure created.
- **Phase 1A Data Acquisition & Provenance Audit:**
  - **NCS Data:** Unverified 15-record test fixture located at `data/fixtures/ncs_pune_jobs_unverified_fixture.json` classified as `UNVERIFIED_OR_SYNTHETIC`. Live/official export source acquisition remains pending.
  - **DVET Supply Data:** **Partially Verified**. Exactly **1 institute detail page** (`Industrial Training Institute, Haveli`, Institute Code `2765211006`, NCVT MIS Code `GU27000616`) and its **10 observed trade records** with source-faithful intake values are verified and stored at `data/raw/dvet_pune/dvet_pune_haveli_verified_snapshot.json` (verified via manual inspection of the official DVET page).
  - The remaining 15 Pune institutes from the public directory are quarantined as unverified reference data at `data/fixtures/dvet_unverified_directory_or_inferred/dvet_pune_inferred_directory_reference.json`.
- **Phase 2A Ontology Seed (Audited & Corrected):**
  - Skill ontology seed at `core/ontology/skills_seed.json` (V2.0) containing 8 canonical skills mapped from verified DVET Haveli trades.
  - All skills marked `NEEDS_REVIEW` pending empirical syllabus verification (no skills marked VERIFIED without inspected document evidence).
  - Trade-to-skill mapping at `core/ontology/trade_skill_mapping.json` (V2.0) containing 8 canonical trade-to-skill mappings.
  - All mappings marked `NEEDS_REVIEW` (no mappings marked VERIFIED without inspected external syllabus evidence).
  - Invalid `Painter General -> SKL-ADV-01` mapping removed during audit correction.
  - `SKL-ADV-01` (Advanced Emerging Technologies) removed as unsupported placeholder.
  - Mappings represent canonical trade names (7 distinct trade types) rather than duplicate source unit rows (10 DVET rows).
  - Loader and validation utility (`core/ontology/loader.py`) updated to enforce integrity constraints.
  - Comprehensive unit test suite (`tests/unit/test_ontology.py`) updated and passing (7 tests passed).

## Known Environment Issues
- Windows host-to-container HTTP access via `http://localhost:8000/api/v1/health` may experience connection failure depending on host network configuration/Docker Desktop bridge networking, whereas internal container access and health verification (`GET /api/v1/health`) succeed fully. Phase 0 API and database functionality are unaffected.

## What has NOT yet been implemented
- Verified live or official export data acquisition for NCS (Pending)
- Data ingestion pipelines for Apprenticeship India, SIDH, etc. (Phase 1B+)
- NLP skill extraction & NCO occupation mapping (Phases 3-4)
- Demand scoring & analytics views (Phase 5)
- Curriculum skill mapping & skill gap analysis (Phase 6-7)
- Recommendation engine & validation workflows (Phase 8)
- Full government dashboard screens (Phase 10)

## Current Blockers
- Verified NCS source data acquisition is pending genuine verified access or legitimate official public export.

## Next Task
- Await verified source acquisition or instructions before proceeding to Phase 1B or Phase 2.
