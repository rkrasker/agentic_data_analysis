# Data Structures

**Last Updated:** 2026-01-15

## Overview

This document describes the data structures used throughout the pipeline.

## Primary Dataframes

### validation.parquet
**Purpose:** Ground truth with verified unit assignments

| Field | Type | Description |
|-------|------|-------------|
| primary_id | string | Unique soldier identifier |
| name | string | Soldier name |
| component_id | string | Component identifier (e.g., "1st_infantry_division") |
| division | string | Division assignment |
| regiment | int | Regiment number |
| battalion | int | Battalion number |
| company | string | Company letter |

**Usage:**
- Source of truth for evaluation
- Training data for resolver generation (grouped by component_id)
- Basis for train/test split in resolver workflow

**Note:** `component_id` must match keys in `hierarchy_reference.json` for resolver generation to work correctly.

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
**Purpose:** Regex-extracted fragments (for routing and LLM context)

**Core Columns:**
| Field | Type | Description |
|-------|------|-------------|
| source_id | string | Document identifier |
| soldier_id | string | Soldier identifier (links to validation.primary_id) |
| raw_text | string | Original record text |

**Extraction Columns (19 total):**

*Term Extractions (5):*
- Org_Terms (list) - Organization identifiers (AB, MAR, ID, INF, etc.)
- Unit_Terms (list) - Unit type labels (CO, BN, REGT, DIV, etc.)
- Role_Terms (list) - Rank/role identifiers (PVT, SGT, CPL, etc.)
- Unchar_Alpha (list) - Standalone letters not paired with terms
- Unchar_Digits (list) - Standalone numbers not paired with terms

*Paired Extractions (12):*
- Org_Term_Digit_Term:Pair, :Org, :Digit (e.g., 'MAR:1', 'AB:101')
- Unit_Term_Digit_Term:Pair, :Unit, :Digit (e.g., 'CO:2', 'BN:3')
- Unit_Term_Alpha_Term:Pair, :Unit, :Alpha (e.g., 'BN:A', 'CO:E')
- Alpha_Digit:Pair, :Alpha, :Digit (e.g., 'E:2', 'C:116')

*Special Patterns (2):*
- Special_Numbers (list) - Exact-length patterns (e.g., 4-digit years)
- Digit_Sequences (list) - Slash/dash notation (e.g., '2/116' → '2:116')

**Usage:** Component routing, batching, and LLM context enrichment

**Note:** This is a universal schema - works for both synthetic and production data.

---

### synthetic_metadata.parquet
**Purpose:** Synthetic-specific debugging metadata

| Field | Type | Description |
|-------|------|-------------|
| source_id | string | Links to canonical.parquet |
| soldier_id | string | Links to canonical.parquet |
| clerk_id | string | Which clerk archetype created this |
| situation_id | string | Operational context (normandy_airborne, etc.) |
| quality_tier | int | Text quality (1=pristine, 2=good, 3=degraded) |

**Usage:** Analysis and debugging of synthetic data generation only

**Note:** This file only exists for synthetic data. Join to canonical on (source_id, soldier_id).

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

### corr.parquet *(deferred)*
**Purpose:** Maps old IDs to current IDs

**Status:** Not currently produced by the synthetic generator. Deferred for future implementation if ID change simulation is needed.

| Field | Type | Description |
|-------|------|-------------|
| old_id | string | Previous identifier |
| new_id | string | Current identifier |

---

### unit_changes.parquet
**Purpose:** Documents known unit transfers (25% of soldiers)

| Field | Type | Description |
|-------|------|-------------|
| soldier_id | string | Links to primary_id |
| transfer_type | string | Level: company_level/battalion_level/regiment_level/division_level |
| original_component_id | string | Previous component |
| original_regiment | int | Previous regiment |
| original_battalion | int | Previous battalion |
| original_company | string | Previous company |
| new_component_id | string | Current component |
| new_regiment | int | Current regiment |
| new_battalion | int | Current battalion |
| new_company | string | Current company |

**Transfer Type Distribution:**
| Type | Frequency | Example |
|------|-----------|---------|
| company_level | 50% | E Co → F Co within 2nd Bn |
| battalion_level | 30% | 2nd Bn → 3rd Bn within 16th Inf |
| regiment_level | 15% | 16th Inf → 18th Inf within 1st ID |
| division_level | 5% | 1st ID → 29th ID via replacement |

**Notes:**
- Documents are undated; no temporal consistency to rely on
- Both assignments are valid "truth" for disambiguation purposes
- Creates hardest disambiguation cases: same soldier, different units
- Cross-branch transfers (Army ↔ Marines) not modeled

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

**Generation:** Produced by resolver generation workflow, not manually created.

**Schema varies by component tier:**
- `well_represented` / `adequately_represented`: Full resolver with all sections
- `under_represented`: Partial resolver (limited patterns, no vocabulary)
- `sparse`: Hierarchy-only resolver (structure + structural exclusions only)

**Core structure:**
```json
{
  "meta": {
    "component_id": "string",
    "generated_utc": "ISO timestamp",
    "tier": "well_represented|adequately_represented|under_represented|sparse",
    "sample_size": "int",
    "pct_of_median": "float",
    "generation_mode": "full|partial|hierarchy_only"
  },
  "structure": {
    "status": "complete",
    "valid_regiments": ["list"],
    "valid_battalions": ["list"],
    "valid_companies": ["list"]
  },
  "patterns": {
    "status": "complete|not_generated",
    "entries": {"pattern": {"means": "interpretation", "tier": "robust|strong|moderate|tentative"}}
  },
  "vocabulary": {
    "status": "complete|not_generated",
    "strong": ["list"],
    "moderate": ["list"],
    "weak": ["list"]
  },
  "exclusions": {
    "structural": {"status": "complete", "rules": ["list"]},
    "value_based": {"status": "complete|not_generated", "rules": ["list"]}
  },
  "differentiators": {
    "vs_{rival_component}": {
      "status": "complete|rival_undersampled|hierarchy_only",
      "rules": ["list"]
    }
  },
  "quality_notes": ["list of warnings/recommendations"]
}
```

See `docs/components/strategies/resolver/CURRENT.md` for full schema with examples.

---

### resolvers/resolver_registry.json
**Purpose:** Tracks all resolver generation status, quality, and rebuild triggers

**Generated by:** Resolver generation workflow

**Schema:**
```json
{
  "meta": {
    "generated_utc": "ISO timestamp",
    "validation_source": "path to validation.parquet used",
    "validation_row_count": "int",
    "thresholds": {
      "median": "int - component count at 50th percentile",
      "p25": "int - component count at 25th percentile",
      "p75": "int - component count at 75th percentile"
    },
    "tier_definitions": {
      "well_represented": "description",
      "adequately_represented": "description",
      "under_represented": "description",
      "sparse": "description"
    }
  },

  "resolvers": {
    "{component_id}": {
      "sample_size": "int",
      "tier": "well_represented|adequately_represented|under_represented|sparse",
      "pct_of_median": "float",
      "resolver_path": "path to resolver JSON",
      "generation_status": "complete|partial|hierarchy_only",
      "generated_utc": "ISO timestamp",

      "sections": {
        "structure": {"status": "complete"},
        "patterns": {"status": "complete|not_generated", "pattern_count": "int"},
        "vocabulary": {"status": "complete|not_generated", "term_count": "int"},
        "exclusions": {
          "structural": {"status": "complete", "rule_count": "int"},
          "value_based": {"status": "complete|not_generated", "rule_count": "int"}
        },
        "differentiators": {
          "vs_{rival}": {"status": "complete|rival_undersampled|hierarchy_only"}
        }
      },

      "subcomponent_coverage": {
        "{regiment}": {
          "train": "int",
          "test": "int",
          "status": "adequate|marginal|weak"
        }
      },

      "rebuild_triggers": [
        {
          "condition": "sample_size >= N",
          "action": "regenerate_as_{tier}",
          "unlocks": ["list of sections that become available"]
        }
      ],

      "quality_notes": ["list of warnings/recommendations"]
    }
  },

  "summary": {
    "total_components": "int",
    "by_tier": {
      "well_represented": "int",
      "adequately_represented": "int",
      "under_represented": "int",
      "sparse": "int"
    },
    "generation_status": {
      "complete": "int",
      "partial": "int",
      "hierarchy_only": "int"
    },
    "rebuild_candidates": [
      {"component": "id", "current": "int", "next_threshold": "int"}
    ]
  }
}
```

**Usage:**
- Check resolver quality before using resolver strategy
- Identify components that need different strategy (zero-shot/few-shot)
- Track when resolvers should be regenerated after validation data updates
- Generate rebuild reports when new validation data arrives

---

### resolvers/train_test_split.json
**Purpose:** Records the train/test split used for resolver generation

**Generated by:** Resolver generation workflow (split phase)

**Schema:**
```json
{
  "meta": {
    "generated_utc": "ISO timestamp",
    "validation_source": "path to validation.parquet",
    "split_ratio": {"train": 0.75, "test": 0.25},
    "stratify_by": "regiment",
    "random_seed": "int"
  },

  "splits": {
    "{component_id}": {
      "total": "int",
      "train_count": "int",
      "test_count": "int",
      "train_ids": ["list of soldier_ids in training set"],
      "test_ids": ["list of soldier_ids in test set"],
      "by_stratum": {
        "{regiment}": {"train": "int", "test": "int"}
      }
    }
  },

  "exclusions": [
    {
      "component": "id",
      "count": "int",
      "reason": "below minimum threshold"
    }
  ]
}
```

**Usage:**
- Ensure evaluation uses held-out test set (no data leakage)
- Reproducible splits via random_seed
- Track which soldiers were used for training vs evaluation

---

## Adding New Structures

Use namespace pattern: `data/[name]-[format]`

Examples:
- `data/pattern-cache-json`
- `data/batch-log-parquet`

Document new structures in this file when added.
