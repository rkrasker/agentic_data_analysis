# 010: Separate Synthetic Metadata from Core Schema

**Status:** active
**Created:** 2026-01-29
**Component:** src/synthetic/, src/preprocessing/difficulty/

## Context

The current synthetic data pipeline conflates three distinct concepts in its output schemas:

1. **Core data** — fields that would exist in production (source_id, soldier_id, raw_text)
2. **Ground-truth labels** — state assignments and post paths (validation data)
3. **Synthetic generation metadata** — artifacts of how data was generated (clerk_id, quality_tier, path_completeness, etc.)

Additionally, difficulty metrics are computed in two places with identical column names but different semantics:
- `src/synthetic/difficulty_computer.py` — computes metrics WITH ground truth during generation
- `src/preprocessing/difficulty/compute.py` — computes metrics WITHOUT ground truth from raw records

This conflation causes confusion about data provenance and prevents a clean common post-processing stage for both synthetic and production data.

See ADR-010 for the architectural decision.

## Task

Refactor the synthetic data generation and preprocessing pipelines to cleanly separate:

1. **Core data** (production-equivalent) from **synthetic metadata** (generation artifacts)
2. **Ground-truth difficulty** (computed from labels) from **inferred difficulty** (computed from raw records)
3. **Generation-control metrics** (used to control what's generated) from **post-hoc metrics** (computed after generation)

## Scope

- **Working in:** `src/synthetic/`, `src/preprocessing/difficulty/`
- **Reference:** `docs/components/synthetic_data_generation/CURRENT.md`, `DIFFICULTY_MODEL.md`
- **Config inputs:** `config/hierarchies/`
- **Test location:** `tests/synthetic/`, `tests/preprocessing/`
- **Ignore:** `.project_history/`, strategy components

## Inputs

Current synthetic pipeline outputs:
- `data/synthetic/raw.parquet` — mixed core + synthetic metadata
- `data/synthetic/validation.parquet` — mixed labels + difficulty metrics
- `data/synthetic/sources.parquet` — source metadata

## Outputs

New schema with clear separation:

### Core Data (production-equivalent)

**raw.parquet** — only fields that would exist in production:
```
source_id: str
soldier_id: str
raw_text: str
```

**validation.parquet** — only ground-truth labels (no difficulty metrics):
```
soldier_id: str
state_id: str
state_order: int
branch: str
post_path: str
[branch-specific level columns]: str
```

### Synthetic Generation Metadata

**synthetic_records.parquet** — per-record generation artifacts:
```
source_id: str          # join key
soldier_id: str         # join key
state_id: str           # ground-truth state assignment for this record
clerk_id: str
situation_id: str
quality_tier: int
path_completeness: float
levels_provided: list[str]
extraction_signals: list[str]
```

**synthetic_soldiers.parquet** — per-soldier generation control metrics:
```
soldier_id: str
gen_difficulty_tier: str        # tier used to CONTROL generation
gen_complementarity_score: float
gen_structural_resolvability: bool
target_state_count: int         # how many states were targeted
```

### Computed Difficulty (common post-processing)

**gt_difficulty.parquet** — ground-truth difficulty computed from validation labels:
```
soldier_id: str
state_id: str (optional, for per-state metrics)
gt_collision_zone_flag: bool
gt_collision_severity: str
gt_complementarity_score: float
gt_structural_resolvability: bool
gt_difficulty_tier: str
```

**inferred_difficulty.parquet** — difficulty inferred from raw records alone:
```
soldier_id: str
inferred_collision_position: bool
inferred_complementarity_score: float
inferred_structural_resolvability: bool
inferred_difficulty_tier: str
```

## Implementation Steps

### Phase 1: Extract shared difficulty computation

1. Create `src/difficulty/` module (new top-level module)
2. Move ground-truth difficulty logic from `src/synthetic/difficulty_computer.py` to `src/difficulty/ground_truth.py`
3. This module should:
   - Take validation.parquet + raw.parquet as inputs
   - Compute collision_zone_flag, collision_severity from validation labels + hierarchy
   - Compute complementarity_score from raw records + validation state assignments
   - Compute structural_resolvability from raw records + hierarchy constraints
   - Output gt_difficulty.parquet
4. Works identically for synthetic and production data (given labeled validation file)

### Phase 2: Update preprocessing difficulty computation

1. Rename outputs in `src/preprocessing/difficulty/compute.py` to use `inferred_` prefix
2. Ensure output file is named `inferred_difficulty.parquet`
3. Update any downstream consumers of these column names

### Phase 3: Refactor synthetic pipeline outputs

1. Update `src/synthetic/pipeline.py` to output separated files:
   - `raw.parquet` — core fields only
   - `validation.parquet` — labels only (remove difficulty columns)
   - `synthetic_records.parquet` — per-record metadata
   - `synthetic_soldiers.parquet` — per-soldier generation metrics with `gen_` prefix

2. Update `src/synthetic/models.py` dataclasses if needed to reflect separation

3. The synthetic DifficultyComputer should:
   - Still compute metrics for generation rebalancing
   - Store results in synthetic_soldiers.parquet with `gen_` prefix
   - NOT write to validation.parquet

### Phase 4: Add ground-truth difficulty to pipeline

1. After synthetic generation, call the new `src/difficulty/ground_truth.py` module
2. This computes gt_difficulty.parquet from the generated validation + raw files
3. For synthetic data, gt_* metrics should match gen_* metrics (sanity check)

### Phase 5: Update preprocessing adapter

1. Update `src/preprocessing/preprocessing_adapter.py` to handle new schema
2. Ensure it correctly routes synthetic metadata when present
3. Gracefully handle production data (no synthetic_* files)

## Acceptance Criteria

- [ ] `raw.parquet` contains only: source_id, soldier_id, raw_text
- [ ] `validation.parquet` contains only labels: soldier_id, state_id, state_order, branch, post_path, level columns
- [ ] `synthetic_records.parquet` contains per-record generation metadata with state_id for record-to-state linking
- [ ] `synthetic_soldiers.parquet` contains per-soldier metrics with `gen_` prefix
- [ ] `gt_difficulty.parquet` is produced by common module, contains `gt_` prefixed columns
- [ ] `inferred_difficulty.parquet` is produced by preprocessing, contains `inferred_` prefixed columns
- [ ] Existing tests pass or are updated to reflect new schema
- [ ] No regressions in difficulty computation logic (values should match, just reorganized)
- [ ] Documentation updated (CURRENT.md, DIFFICULTY_MODEL.md)

## Notes

### Naming Convention

| Prefix | Meaning | Source |
|--------|---------|--------|
| `gen_` | Used to **control** generation | synthetic_soldiers.parquet |
| `gt_` | Computed **from** ground-truth labels | gt_difficulty.parquet |
| `inferred_` | Computed **from** raw records only | inferred_difficulty.parquet |

### Backward Compatibility

This is a breaking schema change. Downstream notebooks and scripts that read the old schema will need updates. Consider:
- Adding a migration script or clear error messages
- Documenting the mapping from old to new column locations

### Per-State vs Per-Soldier Metrics

- `collision_zone_flag` and `collision_severity` are per-STATE (a state's post may or may not be in a collision zone)
- `complementarity_score`, `structural_resolvability`, `difficulty_tier` are per-SOLDIER (aggregate across all records)
- The gt_difficulty.parquet should include state_id for per-state metrics, soldier_id for per-soldier metrics

### Production Data Path

For production (real WWII) data:
1. Ingest raw records → raw.parquet (same schema as synthetic)
2. Human annotation → validation.parquet (same schema as synthetic)
3. No synthetic_*.parquet files exist
4. Ground-truth difficulty module computes gt_difficulty.parquet
5. Preprocessing computes inferred_difficulty.parquet
6. Evaluation compares inferred to ground-truth

## References

- Design doc: `docs/components/synthetic_data_generation/CURRENT.md`
- Difficulty model: `DIFFICULTY_MODEL.md`
- Architecture: `docs/architecture/CURRENT.md`
- ADR-006: Three-layer difficulty model
- ADR-010: Synthetic metadata separation (this decision)
