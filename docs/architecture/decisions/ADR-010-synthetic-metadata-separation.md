# ADR-010: Synthetic Metadata Separation and Difficulty Computation Contexts

**Status:** Accepted
**Date:** 2026-01-29
**Deciders:** Project Lead
**Context:** Investigation into difficulty column provenance revealed conflation of distinct computation contexts

---

## Context

Investigation into the difficulty-related columns in `validation.parquet` revealed that the current schema conflates three distinct concepts:

1. **Core data** — fields that would exist in production (source_id, soldier_id, raw_text)
2. **Ground-truth labels** — state assignments and post paths
3. **Synthetic generation metadata** — artifacts of how data was generated

Additionally, difficulty metrics are computed in two separate locations with **identical column names but different semantics**:

| Location | Ground Truth Access | Purpose |
|----------|---------------------|---------|
| `src/synthetic/difficulty_computer.py` | Yes (during generation) | Control difficulty distribution |
| `src/preprocessing/difficulty/compute.py` | No (from raw records) | Production-equivalent inference |

This conflation causes:
- Confusion about which columns come from where
- Inability to distinguish generation-control metrics from post-hoc analysis
- No clean path for production data to use the same post-processing pipeline

### The Three Computation Contexts

| Context | When | Ground Truth? | Purpose |
|---------|------|---------------|---------|
| **Generation control** | During synthetic generation | Yes | Hit target difficulty distribution |
| **Ground-truth difficulty** | Post-generation from labels | Yes | Evaluation stratification |
| **Inferred difficulty** | Preprocessing from raw only | No | Production routing/prioritization |

For synthetic data, generation-control and ground-truth difficulty should produce identical values (they use the same information). But they serve different purposes and should be stored separately.

For production data, only ground-truth (from human labels) and inferred (from raw records) exist.

---

## Decisions

### Decision 1: Separate Core Data from Synthetic Metadata

**Choice:** Split synthetic pipeline output into four files:

| File | Contents | Production Equivalent |
|------|----------|----------------------|
| `raw.parquet` | source_id, soldier_id, raw_text | Yes — identical schema |
| `validation.parquet` | Labels only (state assignments, post paths) | Yes — identical schema |
| `synthetic_records.parquet` | Per-record generation metadata | No — synthetic only |
| `synthetic_soldiers.parquet` | Per-soldier generation metrics | No — synthetic only |

**Rationale:** Clean separation allows the same downstream pipeline to process both synthetic and production data. The core files have identical schemas; synthetic-specific metadata is clearly isolated.

### Decision 2: Remove Difficulty Columns from validation.parquet

**Choice:** The `validation.parquet` file should contain **only ground-truth labels**, not computed difficulty metrics.

Remove from validation.parquet:
- `collision_zone_flag`
- `collision_severity`
- `soldier_difficulty_tier`
- `complementarity_score`
- `structural_resolvability`

**Rationale:** These are derived metrics, not ground-truth labels. They should be computed by a dedicated module that works identically for synthetic and production data.

### Decision 3: Create Unified Ground-Truth Difficulty Module

**Choice:** Create `src/difficulty/ground_truth.py` that computes difficulty metrics from validation labels + raw records.

**Inputs:**
- `validation.parquet` (ground-truth state/post assignments)
- `raw.parquet` (records for complementarity analysis)
- `hierarchy_reference.json` (for collision detection)

**Output:** `gt_difficulty.parquet` with columns:
- `gt_collision_zone_flag`
- `gt_collision_severity`
- `gt_complementarity_score`
- `gt_structural_resolvability`
- `gt_difficulty_tier`

**Rationale:** This module works identically for synthetic and production data. Given any labeled validation file, it computes difficulty metrics for evaluation stratification.

### Decision 4: Prefix Convention for Difficulty Metrics

**Choice:** Use consistent prefixes to indicate provenance:

| Prefix | Meaning | Source File |
|--------|---------|-------------|
| `gen_` | Used to **control** generation | `synthetic_soldiers.parquet` |
| `gt_` | Computed **from** ground-truth labels | `gt_difficulty.parquet` |
| `inferred_` | Computed **from** raw records only | `inferred_difficulty.parquet` |

**Rationale:** Column names should be self-documenting. Anyone reading a dataframe can immediately understand where the values came from.

### Decision 5: Synthetic Generation Metadata Schema

**Choice:** Per-record and per-soldier synthetic metadata in separate files:

**synthetic_records.parquet** (per-record):
```
source_id, soldier_id, state_id    # join keys
clerk_id, situation_id             # generation parameters
quality_tier                       # extraction difficulty (Layer 1)
path_completeness                  # how much path was rendered
levels_provided                    # which levels appear
extraction_signals                 # structural signals present
```

**synthetic_soldiers.parquet** (per-soldier):
```
soldier_id                         # join key
gen_difficulty_tier                # tier used for generation control
gen_complementarity_score          # complementarity at generation time
gen_structural_resolvability       # resolvability at generation time
target_state_count                 # how many states were targeted
```

**Rationale:** Two levels of generation metadata (per-record, per-soldier) serve different analysis purposes and have different cardinalities.

### Decision 6: Move state_id Out of raw.parquet

**Choice:** The `state_id` column moves from `raw.parquet` to `synthetic_records.parquet`.

**Rationale:** In production, we don't know which state a record belongs to — that's what we're trying to infer. The `state_id` is ground-truth metadata, not a raw record attribute. For synthetic data, the record-to-state linkage is captured in `synthetic_records.parquet`.

**Note:** `validation.parquet` still contains state_id as part of the ground-truth labels (defining what states exist for each soldier).

### Decision 7: Preprocessing Outputs Use inferred_ Prefix

**Choice:** Update `src/preprocessing/difficulty/compute.py` to output columns with `inferred_` prefix and write to `inferred_difficulty.parquet`.

**Rationale:** Consistency with the prefix convention. Makes clear these values are computed without ground-truth access.

---

## Consequences

### Positive
- Clear provenance for all difficulty metrics via naming convention
- Same pipeline works for synthetic and production data
- Evaluation can compare `inferred_*` to `gt_*` metrics directly
- Synthetic generation artifacts clearly isolated
- No confusion about which function computed which value

### Negative
- Breaking schema change requires updating downstream consumers
- More output files to manage (4 synthetic files + 2 difficulty files)
- Migration effort for existing code

### Neutral
- Total information unchanged (just reorganized)
- Difficulty computation logic unchanged (just where it runs and output names)

---

## Migration Path

### Old → New Column Locations

| Old Location | Old Column | New Location | New Column |
|--------------|------------|--------------|------------|
| raw.parquet | state_id | synthetic_records.parquet | state_id |
| raw.parquet | clerk_id | synthetic_records.parquet | clerk_id |
| raw.parquet | situation_id | synthetic_records.parquet | situation_id |
| raw.parquet | quality_tier | synthetic_records.parquet | quality_tier |
| raw.parquet | path_completeness | synthetic_records.parquet | path_completeness |
| raw.parquet | levels_provided | synthetic_records.parquet | levels_provided |
| raw.parquet | extraction_signals | synthetic_records.parquet | extraction_signals |
| validation.parquet | collision_zone_flag | gt_difficulty.parquet | gt_collision_zone_flag |
| validation.parquet | collision_severity | gt_difficulty.parquet | gt_collision_severity |
| validation.parquet | soldier_difficulty_tier | gt_difficulty.parquet | gt_difficulty_tier |
| validation.parquet | complementarity_score | gt_difficulty.parquet | gt_complementarity_score |
| validation.parquet | structural_resolvability | gt_difficulty.parquet | gt_structural_resolvability |

### Sanity Check for Synthetic Data

For synthetic data, after running both generation and ground-truth difficulty computation:
- `gen_difficulty_tier` should equal `gt_difficulty_tier`
- `gen_complementarity_score` should equal `gt_complementarity_score`
- `gen_structural_resolvability` should equal `gt_structural_resolvability`

Any mismatch indicates a bug in one of the computation paths.

---

## Related Documents

- `ADR-006` — Three-layer difficulty model (extraction, aggregation, structural)
- `ADR-008` — Preprocessing v4.1 update (established synthetic_metadata pattern)
- `DIFFICULTY_MODEL.md` — Operational difficulty computation spec
- `docs/components/synthetic_data_generation/CURRENT.md` — Synthetic data schemas
- `instructions/010_separate_synthetic_metadata_schema.md` — Implementation instruction
