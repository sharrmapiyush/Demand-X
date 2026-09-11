# Observation Status Semantics Design

**Date:** 2026-09-10  
**Author:** DemandX Architecture  
**Purpose:** Resolve status semantics for historical Naukri observations  
**Status:** DESIGN ONLY — No implementation

---

## Executive Summary

This document audits the semantic meaning of the canonical `status` field and determines whether DemandX can safely label historical Naukri postings (2015-2017) as `EXPIRED`. The analysis reveals that `status` currently conflates **source-reported state** with **inferred freshness**, violating the "do not fabricate" principle.

**Final Recommendation:** `YES_WITH_EXPLICIT_SOURCE_RULE`

Historical Naukri postings can be labeled `EXPIRED` only if DemandX establishes an explicit source-level rule that historical supplementary datasets receive `status="EXPIRED"` by definition, with freshness represented via `source_type` and `freshness_class`.

---

## 1. Current Status Semantics

### 1.1 Contract Definition

From `ingestion/contracts/observations.py`:

```python
VALID_STATUSES = {"ACTIVE", "INACTIVE", "CLOSED", "EXPIRED", "PENDING"}

class RawJobPostingInput(BaseModel):
    status: str = "ACTIVE"  # Default value
    
    @field_validator("status")
    @classmethod
    def check_status(cls, v: str) -> str:
        cleaned = v.strip().upper()
        if cleaned not in VALID_STATUSES:
            raise ValueError(f"Invalid status '{v}'. Must be one of {VALID_STATUSES}")
        return cleaned
```

**Observations:**
- The contract defines allowed values but provides **no semantic documentation**
- `status` defaults to `"ACTIVE"` when not explicitly set
- No guidance on whether this is source-reported, inferred, or processing state

### 1.2 Model/Schema Definition

From `core/models/observation.py` and migration `003_labour_market_observations.py`:

```python
class JobPosting(Base):
    status = Column(String(50), nullable=False, default="ACTIVE", index=True)
```

```sql
sa.Column('status', sa.String(length=50), nullable=False, server_default='ACTIVE')
```

**Observations:**
- Database defaults to `ACTIVE`
- Indexed for filtering
- No semantic constraint or documentation

### 1.3 Adapter Usage

From `ingestion/adapters/naukri_historical.py`:

```python
raw_input = RawJobPostingInput(
    source_id=SOURCE_ID,
    ...
    status="ACTIVE"  # neutral status per contract rule
)
```

**Observations:**
- Adapter explicitly sets `status="ACTIVE"` with comment "neutral status per contract rule"
- This suggests `ACTIVE` is being used as a **placeholder**, not a semantically meaningful value
- Naukri historical source provides **no explicit status field** in the raw CSV

---

## 2. What Does `status` Mean?

There are four possible interpretations:

### A. State Explicitly Reported by the Source

| Interpretation | Evidence | Problem |
|----------------|----------|---------|
| Source-reported | None — Naukri CSV has no status column | Naukri never reports status; we would be fabricating |

### B. Current State Inferred from Age

| Interpretation | Evidence | Problem |
|----------------|----------|---------|
| Age-inferred | If posting is old → EXPIRED | Requires business logic at query time; conflates observation time with current state |

### C. State of the Observation at Retrieval Time

| Interpretation | Evidence | Problem |
|----------------|----------|---------|
| Retrieval-time | Retrieved 2016 → ACTIVE at that time | Naukri data is historical; retrieval timestamp is fabricated (dataset predates our system) |

### D. Internal Processing State

| Interpretation | Evidence | Problem |
|----------------|----------|---------|
| Processing state | `PENDING` suggests ingest pipeline status | Mixes data state with pipeline state; `ACTIVE`/`EXPIRED` don't fit this model |

**Conclusion:** The current usage of `status="ACTIVE"` for historical Naukri is **semantically undefined**. It serves as a contract-required placeholder with no grounding in source reality.

---

## 3. Problems with ACTIVE for Historical Data

Assigning `status="ACTIVE"` to 2015-2017 Naukri postings causes:

### 3.1 Demand Overstatement

```sql
-- Query: Count active job postings in Pune
SELECT COUNT(*) FROM job_postings 
WHERE district = 'Pune' AND status = 'ACTIVE';
```

**Result:** Returns 1,209 historical Naukri postings that are actually closed/expired, overstating current demand.

### 3.2 Time-Series Contamination

```sql
-- Query: Month-over-month active postings
SELECT DATE_TRUNC('month', posted_date), COUNT(*) 
FROM job_postings 
WHERE status = 'ACTIVE'
GROUP BY 1;
```

**Result:** Historical months (2015-2016) appear to have "active" demand, contaminating time-series analysis.

### 3.3 Dashboard Misrepresentation

Any dashboard filtering by `status='ACTIVE'` will show historical Naukri postings as if they represent current labor market demand, misleading users.

### 3.4 Violation of "Do Not Fabricate" Rule

`ACTIVE` implies the job is currently accepting applications. This is **fabricated information** — the source never reported this state, and reality contradicts it.

---

## 4. Problems with EXPIRED for Historical Data

Assigning `status="EXPIRED"` to all historical Naukri postings avoids the ACTIVE problems but introduces:

### 4.1 Semantic Ambiguity

`EXPIRED` typically means "was active, has passed its end date." For historical data:
- We don't know the original posting duration
- We don't know when it actually expired
- We're inferring expiration from the passage of time

### 4.2 Conflation with Source-Reported Expiration

Future sources (NCS, Mahaswayam) may explicitly report `CLOSED` or `EXPIRED` status. Mixing inferred expiration with source-reported expiration creates semantic confusion.

### 4.3 Query Complexity

```sql
-- Query: Current active postings (excluding historical)
SELECT COUNT(*) FROM job_postings 
WHERE status = 'ACTIVE' 
  AND source_id NOT LIKE '%historical%';
```

Requires filtering by `source_id` pattern rather than using status field correctly.

---

## 5. Recommended Canonical Meaning

### 5.1 Status Should Represent Source-Reported State

**Definition:**
```
status: The employment state of the posting as reported by the source at the time of observation.
```

| Value | Meaning |
|-------|---------|
| `ACTIVE` | Source explicitly reports posting is open/accepting applications |
| `INACTIVE` | Source explicitly reports posting is paused/hidden |
| `CLOSED` | Source explicitly reports posting is filled/cancelled |
| `EXPIRED` | Source explicitly reports posting has passed deadline |
| `PENDING` | Source has not yet published or status is pending validation |

### 5.2 When Source Does Not Report Status

When a source (like historical Naukri) provides no explicit status field:

**Option 1: Use `PENDING`** (neutral, indicates unknown state)  
**Option 2: Use `NULL`** (requires schema change to make status nullable)  
**Option 3: Establish source-level default rule** (documented per source)

**Recommendation:** Option 3 with explicit source rule.

---

## 6. Recommended Naukri Mapping

### 6.1 Source-Level Rule for Historical Naukri

```
RULE: NAUKRI_HISTORICAL_STATUS_DEFAULT

For sources with:
  - source_type = "SUPPLEMENTARY_HISTORICAL"
  - freshness_class = "HISTORICAL"
  - No explicit status field in source

The canonical status SHALL be "EXPIRED".

Rationale: 
- Historical observations represent past labor market state
- The posting period has definitively ended
- This is not fabrication; it is an explicit rule derived from the nature of historical data
- Documented in source adapter and provenance metadata
```

### 6.2 Adapter Change

```python
# Current (problematic)
status="ACTIVE"  # neutral status per contract rule

# Recommended
status="EXPIRED"  # explicit source rule for SUPPLEMENTARY_HISTORICAL
```

### 6.3 Provenance Documentation

```python
# In adapter
SOURCE_METADATA = {
    "source_id": "naukri-historical-promptcloud",
    "source_type": "SUPPLEMENTARY_HISTORICAL",
    "freshness_class": "HISTORICAL",
    "status_derivation_rule": "NAUKRI_HISTORICAL_STATUS_DEFAULT",
    "status_source": "INFERRED_FROM_SOURCE_TYPE",
    "verification_status": "UNVERIFIED_EXTERNAL_DATASET"
}
```

---

## 7. Impact on Future Sources

### 7.1 NCS (National Career Service)

NCS provides explicit status fields:
- Maps directly to `status` (ACTIVE/CLOSED/EXPIRED)
- No inference needed
- `source_type = "PRIMARY_LIVE"` or `"PRIMARY_HISTORICAL"`

### 7.2 Mahaswayam (Maharashtra Employment Exchange)

May provide status or application deadlines:
- If status provided: use source-reported value
- If deadline provided: infer `EXPIRED` if `deadline < now`
- If neither: apply source-level rule

### 7.3 Apprenticeship India

Provides application end dates:
- `status = ACTIVE` if `application_end_date >= now`
- `status = EXPIRED` if `application_end_date < now`
- Documented derivation rule in adapter

### 7.4 Future Generic Rule

```
Status Derivation Priority:
1. Explicit source-reported status → use verbatim
2. Derivable from source dates (deadline/end_date) → compute and document rule
3. No status/dates available → apply source-level default rule based on source_type:
   - SUPPLEMENTARY_HISTORICAL → EXPIRED
   - PRIMARY_LIVE → ACTIVE (with caution flag)
   - PRIMARY_HISTORICAL → EXPIRED
```

---

## 8. Is Schema Change Required?

### 8.1 Current State

```sql
status VARCHAR(50) NOT NULL DEFAULT 'ACTIVE'
```

### 8.2 Option A: Keep NOT NULL with Explicit Rules

- No schema change required
- All adapters must provide status
- Document source-level derivation rules

### 8.3 Option B: Make Nullable

```sql
status VARCHAR(50) NULL DEFAULT NULL
```

- Allows `status = NULL` for sources with no status information
- Query: `WHERE status = 'ACTIVE' OR status IS NULL` (for unknown state)
- More semantically correct but complicates queries

### 8.4 Option C: Add Status Provenance Field

```sql
status VARCHAR(50) NOT NULL,
status_source VARCHAR(50) NOT NULL,  -- 'REPORTED', 'INFERRED_AGE', 'INFERRED_DEADLINE', 'SOURCE_RULE'
```

- Preserves full provenance
- Enables filtering by status reliability

### 8.5 Recommendation

**Option A (No schema change)** with documented source-level rules is sufficient for MVP. Option C should be considered for production scale when query complexity demands status provenance tracking.

---

## 9. Examples

### Example 1: Naukri Historical (This Dataset)

```python
{
  "source_id": "naukri-historical-promptcloud",
  "source_type": "SUPPLEMENTARY_HISTORICAL",
  "freshness_class": "HISTORICAL",
  "posted_date": "2016-05-21",
  "status": "EXPIRED",  # From source rule, not source field
  "status_derivation": "NAUKRI_HISTORICAL_STATUS_DEFAULT"
}
```

### Example 2: NCS Live Feed

```python
{
  "source_id": "ncs-live",
  "source_type": "PRIMARY_LIVE",
  "freshness_class": "FRESH",
  "posted_date": "2026-09-10",
  "status": "ACTIVE",  # Reported by source
  "status_derivation": "REPORTED"
}
```

### Example 3: Apprenticeship India

```python
{
  "source_id": "apprenticeship-india",
  "source_type": "PRIMARY_LIVE",
  "application_end_date": "2026-09-15",
  "status": "ACTIVE",  # Derived: end_date >= now
  "status_derivation": "INFERRED_DEADLINE"
}
```

### Example 4: Same Apprenticeship After Deadline

```python
{
  "application_end_date": "2026-09-01",
  "status": "EXPIRED",  # Derived: end_date < now
  "status_derivation": "INFERRED_DEADLINE"
}
```

---

## 10. Final Recommendation

### Can DemandX safely label historical Naukri postings EXPIRED?

**Answer: `YES_WITH_EXPLICIT_SOURCE_RULE`**

### Rationale

1. **Not Fabrication:** The status is derived from an explicit, documented source-level rule based on the nature of supplementary historical data. This is inference with provenance, not fabrication.

2. **Semantically Correct:** All historical job postings have definitively ended. `EXPIRED` accurately represents reality at query time.

3. **Prevents Demand Overstatement:** Dashboards and queries filtering by `status='ACTIVE'` will correctly exclude historical data.

4. **Scalable:** The same rule applies to any future historical sources (archived NCS data, legacy Mahaswayam exports).

5. **Auditable:** The derivation rule is documented in source metadata and adapter code.

### Required Actions (No Implementation Yet)

1. **Document Rule:** Add `NAUKRI_HISTORICAL_STATUS_DEFAULT` to provenance metadata
2. **Update Adapter:** Change `status="ACTIVE"` to `status="EXPIRED"` with comment referencing rule
3. **Update Design Doc:** Revise persistence design to reflect `status` derivation approach
4. **No Schema Change:** Current NOT NULL constraint is acceptable with documented rules

### Alternative Considered and Rejected

Using `status="ACTIVE"` for historical data and filtering by `source_type` or `freshness_class` was rejected because:
- Requires every query to know about historical sources
- Easily forgotten in ad-hoc analysis
- Violates semantic clarity: "ACTIVE" means active, not "was active 10 years ago"

---

## 11. Summary

| Question | Answer |
|----------|--------|
| Current status semantics | Undefined (placeholder value) |
| Problems with ACTIVE | Overstates demand, contaminates time-series, fabricates state |
| Problems with EXPIRED | Semantic ambiguity if not documented |
| Recommended canonical meaning | Source-reported state at observation time |
| Recommended Naukri mapping | `EXPIRED` via explicit source rule |
| Schema change required | No |
| Safe to label EXPIRED | **YES_WITH_EXPLICIT_SOURCE_RULE** |

---

**Approval Required:** Before implementing the adapter change, this design should be reviewed and approved to ensure the source-level rule aligns with broader DemandX semantic conventions.
