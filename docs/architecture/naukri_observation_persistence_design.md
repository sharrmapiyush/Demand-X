# Naukri Historical: Canonical Observation Persistence Design

**Date:** 2026-09-10  
**Author:** DemandX Architecture  
**Purpose:** Design document for persisting Naukri historical canonical observations into PostgreSQL  
**Status:** DESIGN ONLY — No implementation

---

## Executive Summary

This document outlines how the 22,000 canonical `NormalizedJobPostingObservation` records produced by the Naukri historical adapter should map into the existing PostgreSQL schema. It evaluates field-level coverage, identifies data loss risks, and recommends schema changes to support geographic evidence, source skills, reposting detection, and provenance metadata.

**Key Finding:** The existing `job_postings` table covers most canonical fields but has **gaps in geographic evidence, source skills, reposting metadata, and provenance classification** that require consideration before bulk persistence.

---

## 1. Can the Existing JobPosting Model Represent All Fields Produced by NormalizedJobPostingObservation?

**Short Answer: PARTIAL**

The `core/models/observation.py::JobPosting` model and its corresponding `job_postings` table (migration 003) support:

| Canonical Field | DB Field | Status |
|-----------------|----------|--------|
| source_id | source_id | ✅ Direct |
| source_record_id | source_record_id | ✅ Direct |
| job_title | job_title | ✅ Direct |
| employer_name | employer_name | ✅ Direct |
| location_text | location_text | ✅ Direct |
| district | district | ✅ Direct |
| state | state | ✅ Direct |
| sector | sector | ✅ Direct |
| description | description | ✅ Direct |
| posted_date | posted_date | ✅ Direct |
| retrieved_at | retrieved_at | ✅ Direct |
| source_url | source_url | ✅ Direct |
| record_identity_hash | record_identity_hash | ✅ Direct |
| status | status | ✅ Direct |

**Missing from JobPosting model/table:**

1. **Geographic evidence layer:** `location_scope`, `location_confidence`, `matched_locations`, `location_evidence_level`, `has_pune_evidence`, `pune_exclusivity`, `locality`
2. **Source skills:** Raw `skills` field from Naukri (required for future skill extraction)
3. **Reposting detection:** No field to link observations in the same collision group
4. **Provenance classification:** No fields for `source_type`, `freshness_class`, `verification_status`
5. **Seats/numberofpositions:** Not applicable to job_postings (exists in apprenticeship_opportunities)

---

## 2. Which Canonical Fields Currently Have No Database Destination?

| Canonical Field | DB Destination | Gap Severity |
|-----------------|----------------|--------------|
| `locality` (geography) | None | MEDIUM |
| `location_scope` (geography) | None | MEDIUM |
| `location_confidence` (geography) | None | LOW |
| `matched_locations` (geography) | None | MEDIUM |
| `location_evidence_level` | None | MEDIUM |
| `has_pune_evidence` | None | LOW |
| `pune_exclusivity` | None | LOW |
| Raw `skills` (source evidence) | None | **HIGH** |
| Reposting group ID | None | **HIGH** |
| `source_type` (provenance) | None | MEDIUM |
| `freshness_class` (provenance) | None | MEDIUM |
| `verification_status` (provenance) | None | MEDIUM |

---

## 3. Which Source Evidence Fields Need Persistence for Future Skill Extraction?

| Field | Purpose | Recommended Persistence |
|-------|---------|------------------------|
| Raw `skills` (Naukri `skills` column) | Future ontology mapping | **Required** — store in `source_metadata` JSONB column or dedicated table |
| Raw `industry` | Sector evidence backup | Already in `sector` field |
| Raw `jobdescription` | Future NLP/skill extraction | Already in `description` field |

---

## 4. How Should Geographic Evidence Be Persisted?

The geography normalizer produces the following evidence fields:

```python
LocationNormalizationResult:
  - raw_location: str          # Already in location_text
  - district: str              # Already in district
  - state: str                 # Already in state
  - locality: str              # MISSING - should persist
  - location_scope: str        # MISSING - should persist (SINGLE_LOCATION/MULTI_LOCATION)
  - location_confidence: str   # MISSING - should persist (HIGH/MEDIUM/LOW/NONE)
  - matched_locations: List    # MISSING - should persist (JSON array)
  - location_evidence_level: str    # MISSING - should persist (EXACT_SINGLE/MULTI_EXPLICIT/CITY_MENTION/AMBIGUOUS)
  - has_pune_evidence: bool    # MISSING - can derive from district="Pune" or filter
  - pune_exclusivity: str      # MISSING - should persist for analytics filter
```

**Recommendation:** Add a JSONB column `geographic_evidence` to `job_postings` to store the full geography normalization result as structured evidence. This preserves the full fidelity for analytics without adding 8+ new columns.

---

## 5. Collision/Reposting Requirement Evaluation

### Alternative A: Add reposting_group_id to JobPosting

```sql
ALTER TABLE job_postings ADD COLUMN reposting_group_id VARCHAR(64);
CREATE INDEX ix_job_postings_reposting_group ON job_postings(reposting_group_id);
```

**Pros:** Simple, direct, fast queries  
**Cons:** Null for non-collisions, requires careful handling of unique constraint on identity_hash

### Alternative B: Separate observation_relationships table

```sql
CREATE TABLE observation_relationships (
  relationship_id VARCHAR(64) PRIMARY KEY,
  relationship_type VARCHAR(50) NOT NULL, -- 'REPOSTING', 'MULTI_LOCATION', etc.
  member_record_id VARCHAR(64) REFERENCES job_postings(id),
  group_id VARCHAR(64) NOT NULL,
  created_at TIMESTAMP DEFAULT NOW()
);
```

**Pros:** Scalable to any relationship type, supports NCS/Mahaswayam/etc.  
**Cons:** Additional join for simple reposting queries

### Alternative C: Store collision metadata in evidence/provenance JSON

Add JSONB column `observation_metadata` containing:
```json
{
  "reposting_group_id": "0018bd44f091e375",
  "collision_type": "REPOSTING",
  "collision_confidence": "HIGH",
  "collision_size": 2
}
```

**Pros:** Schema-flexible, single table, easy to extend  
**Cons:** Cannot index inside JSON efficiently for large-scale analytics

### Recommendation: **Alternative B (Observation Relationships Table)**

**Rationale:**
1. **Future-proofing:** NCS, Mahaswayam, Apprenticeship India will have their own collision patterns (multi-location, expired/active, etc.)
2. **Query flexibility:** Can query `SELECT * FROM observation_relationships WHERE relationship_type = 'REPOSTING'`
3. **Referential integrity:** FK to `job_postings` ensures consistency
4. **Extensibility:** Add new relationship types without schema changes
5. **Analytics:** Aggregate by relationship type, count group sizes, weight first vs. reposted

---

## 6. Source Status Evaluation

**Current Adapter Behavior:** Uses `status = "ACTIVE"` as neutral status per contract requirement.

**Problem:** "ACTIVE" implies the job is currently open and accepting applications. For historical Naukri data (2015-2017), all postings are inherently **closed/expired** — the posting period has long passed.

**Semantically Unsafe:** Labeling 2016-expired postings as "ACTIVE" will:
- Overstate current demand
- Break time-series queries filtering by status
- Mislead dashboard consumers

**Recommendation:** Use `status = "EXPIRED"` for all Naukri historical records.

**Implementation:**
- Adapter change: `status="EXPIRED"` for historical sources
- Contract-level: Introduce `source_type` to distinguish live vs. historical, default `status` based on source

---

## 7. Seats Evaluation

Naukri provides `numberofpositions` (number of openings). The current `job_postings` table has **no seats field**.

**Current State:**
- `ApprenticeshipOpportunity` model has `seats_available` (Integer)
- `JobPosting` model has **no seats field**

**Options:**

1. Add `seats` to `job_postings` — simple, direct
2. Ignore for Naukri — many postings don't specify positions
3. Store in `source_metadata` JSONB

**Recommendation:** Add `seats INTEGER` column to `job_postings` (nullable). Position count is a valid job posting attribute and aligns with the apprenticeship schema pattern.

---

## 8. Source Skills Evaluation

Naukri provides raw skills in a comma-separated string (`skills` column). This **must be preserved** for the future skill extraction stage.

**Current State:** No persistence for raw skills anywhere in the schema.

**Recommendation:** Add `source_skills TEXT` column to `job_postings`. Alternative: store in `source_metadata` JSONB.

**Rationale:** The skill extraction stage (future) needs raw source evidence, not just normalized sector. Storing as dedicated column enables:
- Full-text search on raw skills
- Easy export for skill ontology mapping
- Analytics on skill-demand correlation

---

## 9. Provenance Evaluation

Naukri historical source classification:

| Provenance Field | Value | Must Persist? |
|------------------|-------|---------------|
| source_type | SUPPLEMENTARY_HISTORICAL | ✅ Yes |
| freshness_class | HISTORICAL | ✅ Yes |
| verification_status | UNVERIFIED_EXTERNAL_DATASET | ✅ Yes |
| source_id | naukri-historical-promptcloud | ✅ Yes (source_id FK) |

**Current State:** No provenance classification columns in `job_postings`.

**Recommendation:** Add `source_type VARCHAR(50)` and `freshness_class VARCHAR(50)` columns to `job_postings`. `verification_status` can live in a source registry table referenced by `source_id`, or as part of a `source_metadata` JSONB column.

---

## 10. Proposed Database Mapping Table

| Source/Canonical Field | DB Field | Transformation | Required? | Data Loss? | Notes |
|------------------------|----------|----------------|-----------|------------|-------|
| source_id | source_id | Direct | YES | NO | FK to sources |
| source_record_id | source_record_id | Direct | NO | NO | Nullable |
| job_title | job_title | Trim, validate non-empty | YES | NO | Primary identifier |
| employer_name | employer_name | Trim | NO | NO | Nullable |
| location_text | location_text | Direct | NO | NO | Raw location string |
| district | district | From geography normalizer | NO | NO | Nullable |
| state | state | From geography normalizer | NO | NO | Nullable |
| sector | sector | Direct | NO | NO | Naukri industry |
| description | description | Direct | NO | NO | Nullable |
| posted_date | posted_date | Parse to date | NO | NO | Nullable |
| retrieved_at | retrieved_at | Adapter timestamp | YES | NO | |
| source_url | source_url | Direct | NO | NO | Nullable |
| record_identity_hash | record_identity_hash | SHA-256 | YES | NO | Unique constraint |
| status | status | Map to EXPIRED | YES | NO | Historical → EXPIRED |
| — | locality | From geography | NO | NO | In geographic_evidence JSONB |
| — | location_scope | From geography | NO | NO | In geographic_evidence JSONB |
| — | location_confidence | From geography | NO | NO | In geographic_evidence JSONB |
| — | matched_locations | From geography → JSON | NO | NO | In geographic_evidence JSONB |
| — | location_evidence_level | From geography | NO | NO | In geographic_evidence JSONB |
| — | has_pune_evidence | From geography | NO | NO | Derivable from district |
| — | pune_exclusivity | From geography | NO | NO | In geographic_evidence JSONB |
| raw skills | source_skills TEXT | Direct | **YES** | **YES** | **Currently lost** |
| numberofpositions | seats INTEGER | Parse int | NO | NO | New column |
| — | source_type VARCHAR(50) | From provenance | **YES** | **YES** | **Currently lost** |
| — | freshness_class VARCHAR(50) | From provenance | **YES** | **YES** | **Currently lost** |
| — | observation_metadata JSONB | Collision group | NO | NO | Reposting/uncertain groups |

---

## 11. Proposed Minimal Schema Change List (DO NOT IMPLEMENT)

1. **Add columns to `job_postings`:**
   ```sql
   ALTER TABLE job_postings ADD COLUMN source_skills TEXT;
   ALTER TABLE job_postings ADD COLUMN seats INTEGER;
   ALTER TABLE job_postings ADD COLUMN source_type VARCHAR(50);
   ALTER TABLE job_postings ADD COLUMN freshness_class VARCHAR(50);
   ALTER TABLE job_postings ADD COLUMN geographic_evidence JSONB;
   ALTER TABLE job_postings ADD COLUMN observation_metadata JSONB;
   ```

2. **Create relationship table:**
   ```sql
   CREATE TABLE observation_relationships (
     relationship_id VARCHAR(64) PRIMARY KEY,
     relationship_type VARCHAR(50) NOT NULL,
     member_record_id VARCHAR(64) REFERENCES job_postings(id),
     group_id VARCHAR(64) NOT NULL,
     created_at TIMESTAMP DEFAULT NOW()
   );
   CREATE INDEX ix_obs_rel_group ON observation_relationships(group_id);
   CREATE INDEX ix_obs_rel_type ON observation_relationships(relationship_type);
   ```

3. **Optional:** Add `verification_status` to sources table or as part of `observation_metadata`.

---

## 12. Schema Sufficiency Determination

| Question | Answer |
|----------|--------|
| **Is existing DB schema sufficient for persisting canonical Naukri observations without loss?** | **NO** |
| Fields requiring new persistence | source_skills, seats, source_type, freshness_class, geographic_evidence, observation_metadata |
| Recommended reposting representation | Alternative B: Separate `observation_relationships` table |
| Recommended historical status | `EXPIRED` (not ACTIVE) |
| Recommended handling of seats | Add `seats INTEGER` column to `job_postings` |
| Recommended handling of source skills | Add `source_skills TEXT` column to `job_postings` |

---

## Summary

The existing `job_postings` table handles 14 of ~25 canonical + evidence fields without loss. Critical gaps are:

1. **source_skills** — required for future skill extraction (HIGH priority)
2. **reposting detection** — 90 collision groups must be linkable for demand weighting
3. **provenance classification** — source_type/freshness_class needed for analytics filtering
4. **status semantics** — historical data should be EXPIRED, not ACTIVE
5. **geographic evidence** — full location normalization evidence preserved in JSONB

These gaps require schema additions before bulk persistence. The recommended approach uses JSONB columns for flexible evidence storage and a separate relationship table for collision/reposting metadata, ensuring scalability to NCS, Mahaswayam, and Apprenticeship India sources.