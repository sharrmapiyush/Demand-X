# Design.md — Government Labour-Market Intelligence Dashboard

| Field | Value |
|---|---|
| Status | **IMPLEMENTATION READY — v0.2** |
| Primary Device | Desktop/Laptop |
| Frontend | React + TypeScript + Vite |
| MVP District | Pune |
| Primary Users | Government / Skill Planning Officials |
| Companion Docs | PRD.md · Architecture.md · Rules.md · Phases.md |

---

# 1. Design Objective

The dashboard must help a government official:

1. understand the current situation quickly
2. identify a problem
3. inspect the evidence
4. understand why the system produced the insight
5. decide what requires human review

The visual language should communicate:

**trust · evidence · intelligence · government usability**

The interface must not look like a chatbot or consumer AI product.

---

# 2. Design Principles

## 2.1 Evidence First

Every derived insight has an accessible evidence path.

## 2.2 Calm and Professional

Avoid:

- excessive gradients
- glowing AI effects
- animated chat bubbles
- decorative 3D graphics
- marketing hero sections

## 2.3 Data Density With Hierarchy

Use:

- ranked tables
- compact cards
- clear headers
- readable numbers
- restrained charts

## 2.4 Honest Status

Never hide:

- stale data
- missing data
- low evidence
- estimates
- insufficient history

## 2.5 Progressive Disclosure

Show the key answer first.

Let the user open detailed evidence.

## 2.6 Human Control

Recommendations visibly support:

- Accept
- Reject
- Needs Review

---

# 3. Visual Theme

### Primary

Deep institutional navy:

```text
#0B3D66
```

### Secondary

Muted teal:

```text
#0E7C7B
```

### Background

```text
#F5F7F9
```

### Surface

```text
#FFFFFF
```

### Border

```text
#DCE3E8
```

### Primary text

```text
#1A2733
```

### Secondary text

```text
#5B6B79
```

### Semantic states

```text
Success:  #1E8E5A
Warning:  #B7791F
Critical: #B3261E
Info:     #2B6CB0
Estimated/Predicted: #6B4FA0
```

These tokens are implementation defaults and should be checked for accessibility before final lock.

---

# 4. Semantic Color Rules

Semantic colors must communicate meaning.

Do not use:

```text
red = decoration
green = branding
purple = random accent
```

Recommended meaning:

| Color | Meaning |
|---|---|
| Green | healthy/low gap/high coverage |
| Amber | attention/moderate gap |
| Red | critical/high gap/stale/low evidence |
| Purple | ESTIMATED/PREDICTED |
| Blue | informational |

Always pair color with text/icon.

---

# 5. Typography

### UI font

Inter with system fallback.

Recommended:

```text
font-family:
Inter,
system-ui,
sans-serif;
```

### Data/code font

IBM Plex Mono or another monospace family for:

- NCO codes
- IDs
- timestamps
- technical identifiers

### Type scale

```text
12
14
16
20
24
32
```

Default table text: 14px.

Default body text: 16px.

---

# 6. Spacing

Use a 4px base.

```text
4
8
12
16
24
32
48
```

Recommended:

- card padding: 16–24px
- table cells: 8–12px vertical
- section gap: 24–32px
- page margins: 24–40px

---

# 7. Main Navigation

Recommended MVP navigation:

```text
Overview
Demand
Skill Gaps
Recommendations
Sources
```

Optional future:

```text
Future Demand
Institutes
Employers
Settings
```

Do not build unused menu items that return empty pages.

---

# 8. Overview Dashboard

The first screen should answer:

> What is happening in Pune right now?

### Top controls

```text
District: Pune
Sector: All
Period: Current
```

### Summary cards

Example structure:

```text
Top Demand
Software Developer

Demand Score
81/100

Job Signals
124

Top Skill
Python
```

The values must come from actual data.

### Main sections

1. Occupation ranking
2. Skill demand ranking
3. Data freshness summary
4. Highest-priority skill gap
5. Recommendation preview

---

# 9. Demand Table

Columns:

```text
Rank
Occupation
Sector
Job Signals
Apprenticeship Signals
Demand Score
Evidence Strength
Freshness
```

Numeric values right-aligned.

Text left-aligned.

Default sort:

```text
Demand Score DESC
```

---

# 10. Occupation Detail

Header:

```text
Software Developer
IT-ITeS
Pune
```

Show:

```text
Demand Score
Evidence Strength
Job count
Apprenticeship signal
```

### Skill list

```text
Python      High
SQL         High
Power BI    Medium
Git         Medium
```

Clicking a skill opens its evidence.

### Evidence

Show representative:

- source
- job title
- matched phrase
- retrieval date

Avoid flooding the user with every record.

---

# 11. Skill Gap View

The view must make comparison visually obvious.

### Example

```text
Course: Data Analytics

MARKET DEMAND
✓ Python
✓ SQL
✓ Excel
✓ Power BI
✓ Statistics

CURRICULUM
✓ Python
✓ Excel
✓ Statistics

MISSING
✗ SQL
✗ Power BI
```

Then:

```text
Coverage: 60%
Gap Severity: MEDIUM
```

The calculation method should be accessible from the Why panel.

---

# 12. Recommendation View

Each recommendation should show:

```text
Recommendation
Priority
Course / Occupation
Gap
Evidence Strength
Freshness
```

Example:

```text
RECOMMENDATION

Review the curriculum to include SQL.

Why?
SQL appears in 64% of matched relevant postings
for the selected occupation while the selected
course curriculum does not list SQL.

Evidence
[Open Evidence]

Status
[Accept] [Reject] [Needs Review]
```

The percentages must be generated from the actual dataset.

---

# 13. Evidence / Why Panel

This is the central trust feature.

Open it from:

- demand score
- skill
- occupation mapping
- gap
- recommendation

### Panel sections

#### Source

```text
NCS
https://www.ncs.gov.in/
```

#### Records used

```text
42 postings
```

#### Method

```text
skill_frequency_rule_v1
```

#### Freshness

```text
PERIODIC
Retrieved: ...
```

#### Provenance

```text
DERIVED
```

#### Confidence/evidence

Show only fields that have legitimate meaning.

#### Matched evidence

Example:

```text
Posting: Data Analyst
Matched phrase: "SQL and Power BI"
```

---

# 14. Status Badges

### Freshness

```text
LIVE
PERIODIC
HISTORICAL
STATIC
```

### Provenance

```text
OBSERVED
DERIVED
ESTIMATED
PREDICTED
```

### Recommendation

```text
PENDING
ACCEPTED
REJECTED
NEEDS REVIEW
```

---

# 15. Confidence Presentation

Do not display every value as:

```text
92%
```

Instead use the appropriate interpretation:

```text
Match Strength: Strong
Classification Confidence: 0.86
Evidence Strength: High
Data Completeness: 94%
```

Use numeric values only where the backend provides a real calculation.

---

# 16. Charts

Use only useful charts.

Recommended:

- horizontal bar chart for occupation ranking
- horizontal bar chart for skill ranking
- simple line chart only when genuine history exists
- coverage comparison bar

Avoid:

- 3D charts
- decorative donuts
- excessive animations
- chart types that add no decision value

---

# 17. Trend Rules

If historical data is insufficient:

```text
Trend unavailable
Insufficient historical observations
```

Do not draw an artificial flat line.

---

# 18. Filters

MVP filters:

```text
District
Sector
Occupation
Period
```

Initially show:

```text
Pune
IT-ITeS
Automotive/Manufacturing
Electronics
```

Do not show statewide options unless data actually exists.

---

# 19. Empty States

Example:

```text
No job data is available for this filter.

Source:
NCS snapshot

Last checked:
10 September 2026

Try another sector or review the source status.
```

Never use fake data to avoid an empty state.

---

# 20. Loading States

Use skeleton loaders for:

- ranking tables
- summary cards
- evidence panel
- charts

Avoid full-page spinners where only one panel is loading.

---

# 21. Error States

Example:

```text
Unable to load demand data.

The source/analytics service is currently unavailable.

[Retry]
```

Never expose stack traces.

---

# 22. Responsive Behavior

Primary target:

```text
1024px+
```

Tables should remain usable at desktop widths.

Tablet:

```text
768px+
```

can simplify layouts.

Mobile is not a September 15 priority.

---

# 23. Accessibility

Requirements:

- keyboard navigation
- visible focus
- semantic headings
- labels for controls
- color not used as sole meaning
- readable contrast
- chart alternatives through tables/text where practical

---

# 24. Dashboard Trust Pattern

Every major value should visually follow:

```text
VALUE
↓
STATUS
↓
WHY
```

Example:

```text
Demand Score
81/100

DERIVED · Evidence: HIGH

Why →
```

This pattern should be consistent throughout the product.

---

# 25. Future Industrial Signal UI

Optional after the main dashboard is stable.

Example:

```text
Future Industry Signal

Project:
Example Industrial Project

Sector:
Electronics

District:
Pune

Source:
MIDC / IIG / other verified source

Workforce Signal:
Potential technician / production / quality demand

Status:
ESTIMATED
```

Never show an exact future job number unless the methodology genuinely supports it.

---

# 26. What the Dashboard Must Not Become

Do not turn the interface into:

- a chatbot
- a generic analytics template with random charts
- a marketing landing page
- an “AI magic” demo
- a page filled with fake KPI numbers
- a dashboard with unexplained scores

---

# 27. MVP Page Structure

```text
/
  Overview

/demand
  Occupation demand

/occupation/:id
  Occupation detail

/gaps
  Skill-gap analysis

/recommendations
  Recommendation review

/sources
  Source status and freshness
```

Optional:

```text
/future-demand
```

only after the main flow is stable.

---

# 28. Source Status Page

Show:

```text
Source
Access Method
Freshness
Last Verified
Last Retrieved
Status
```

Example:

```text
NCS
SOURCE_SNAPSHOT
PERIODIC
Verified: ...
Retrieved: ...
Healthy
```

This page helps judges understand that the system is designed for continuous source monitoring.

---

# 29. Component Library

At minimum:

```text
PageShell
TopNav
FilterBar
MetricCard
DataTable
RankingTable
StatusBadge
FreshnessBadge
ProvenanceBadge
EvidencePanel
RecommendationCard
RecommendationActions
EmptyState
ErrorState
LoadingSkeleton
ChartCard
```

Keep components reusable but do not create a massive design-system framework.

---

# 30. Final Design Principle

The UI should make one thing obvious:

> **This system is not asking the government to trust an AI. It is helping the government inspect evidence and make a better decision.**
