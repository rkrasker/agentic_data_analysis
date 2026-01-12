# Data Structures

**Last Updated:** YYYY-MM-DD

## Overview

This document describes the data structures used throughout the pipeline.

## Primary Dataframes

### validation.parquet
**Purpose:** Ground truth with verified unit assignments

| Field | Type | Description |
|-------|------|-------------|
| primary_id | string | Unique soldier identifier |
| name | string | Soldier name |
| division | string | Division assignment |
| regiment | int | Regiment number |
| battalion | int | Battalion number |
| company | string | Company letter |

**Usage:** Source of truth for evaluation; training data for resolver generation

---

### raw.parquet
**Purpose:** Historical records (multiple rows per soldier)

| Field | Type | Description |
|-------|------|-------------|
| source_id | string | Unique record identifier |
| soldier_id | string | Links to primary_id |
| raw_text | string | Original record text |

**Usage:** Primary input to LLM parsing stage

---

### canonical.parquet
**Purpose:** Regex-extracted fragments (for routing only)

| Field | Type | Description |
|-------|------|-------------|
| source_id | string | Links to raw.parquet |
| primary_id | string | Soldier identifier |
| division | string | Extracted division (nullable) |
| regiment | int | Extracted regiment (nullable) |
| battalion | int | Extracted battalion (nullable) |
| company | string | Extracted company (nullable) |
| digit_digit_pair | list | Ambiguous patterns like "3/505" |
| alpha_digit_pair | list | Ambiguous patterns like "C/3" |

**Usage:** Component routing and batching only — NOT LLM input

---

### consolidated.parquet
**Purpose:** Canonical with ID resolution applied

Same as canonical.parquet plus:

| Field | Type | Description |
|-------|------|-------------|
| alt_id | string | Old ID that was converted (if any) |

**Usage:** Same as canonical plus corr table validation

---

## Supporting Files

### corr.parquet
**Purpose:** Maps old IDs to current IDs

| Field | Type | Description |
|-------|------|-------------|
| old_id | string | Previous identifier |
| new_id | string | Current identifier |

---

### unit_changes.parquet
**Purpose:** Documents known unit transfers

| Field | Type | Description |
|-------|------|-------------|
| soldier_id | string | Links to primary_id |
| original_assignment | object | Previous unit path |
| new_assignment | object | Current unit path |
| change_date | date | When transfer occurred |
| change_type | string | Level of change (company/battalion/etc) |

---

### soldier_component_mapping.parquet
**Purpose:** Component identification from regex signals

| Field | Type | Description |
|-------|------|-------------|
| soldier_id | string | Links to primary_id |
| likely_component | string | Identified component |
| confidence | string | high/medium/low/ambiguous |
| signals | list | What signals led to identification |

**Usage:** Drives batching decisions

---

## Configuration Files

### hierarchy/{component}.json
**Purpose:** Per-component structural schema

```json
{
  "component_id": "82nd_airborne_division",
  "levels": ["division", "regiment", "battalion", "company"],
  "valid_regiments": [325, 504, 505, 507, 508],
  "valid_battalions": [1, 2, 3],
  "valid_companies": ["A", "B", "C", "D", "E", "F", "G", "H", "I"],
  "org_terms": ["airborne division", "parachute infantry"],
  "naming_conventions": {...}
}
```

---

### resolvers/{component}_resolver.json
**Purpose:** Pre-learned heuristics (resolver strategy only)

See `docs/components/strategies/resolver/CURRENT.md` for structure.

---

## Adding New Structures

Use namespace pattern: `data/[name]-[format]`

Examples:
- `data/pattern-cache-json`
- `data/batch-log-parquet`

Document new structures in this file when added.
