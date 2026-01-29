# Session Extract: Synthetic Metadata Separation and Difficulty Computation Contexts

**Date:** 2026-01-29
**Session Type:** Opus 4.5 architecture session
**Topic:** Disambiguating difficulty column provenance and separating synthetic generation artifacts from core data

---

## Context

Investigation into `validation.parquet` columns revealed confusion about where difficulty-related metrics originate. The columns `collision_zone_flag`, `collision_severity`, `soldier_difficulty_tier`, `complementarity_score`, and `structural_resolvability` exist but their provenance was unclear.

Two separate implementations compute similarly-named metrics:
- `src/synthetic/difficulty_computer.py` — during generation, WITH ground truth
- `src/preprocessing/difficulty/compute.py` — during preprocessing, WITHOUT ground truth

This conflation caused confusion and prevented a clean common pipeline for both synthetic and production data.

---

## Key Insight: Three Computation Contexts

Difficulty metrics are computed in **three distinct contexts** with different purposes:

| Context | When | Ground Truth? | Purpose |
|---------|------|---------------|---------|
| **Generation control** | During synthetic generation | Yes | Hit target difficulty distribution |
| **Ground-truth difficulty** | Post-generation from labels | Yes | Evaluation stratification |
| **Inferred difficulty** | Preprocessing from raw only | No | Production routing/prioritization |

For synthetic data: generation-control and ground-truth should match (same information).
For production data: only ground-truth (from human labels) and inferred exist.

---

## Architecture Decision: Schema Separation

**Decision (ADR-010):** Separate core data from synthetic metadata, use prefix convention for difficulty.

### New File Schema

**Core files (production-equivalent):**

| File | Contents |
|------|----------|
| `raw.parquet` | source_id, soldier_id, raw_text |
| `validation.parquet` | Labels only (state_id, post_path, branch, level columns) |

**Synthetic-only metadata:**

| File | Contents |
|------|----------|
| `synthetic_records.parquet` | Per-record: clerk_id, situation_id, quality_tier, state_id linkage, path_completeness, levels_provided, extraction_signals |
| `synthetic_soldiers.parquet` | Per-soldier: gen_difficulty_tier, gen_complementarity_score, gen_structural_resolvability, target_state_count |

**Computed difficulty (common post-processing):**

| File | Contents |
|------|----------|
| `gt_difficulty.parquet` | gt_collision_zone_flag, gt_collision_severity, gt_complementarity_score, gt_structural_resolvability, gt_difficulty_tier |
| `inferred_difficulty.parquet` | inferred_collision_position, inferred_complementarity_score, inferred_structural_resolvability, inferred_difficulty_tier |

---

## Naming Convention: Prefixes

| Prefix | Meaning | Source |
|--------|---------|--------|
| `gen_` | Used to **control** generation | `synthetic_soldiers.parquet` |
| `gt_` | Computed **from** ground-truth labels | `gt_difficulty.parquet` |
| `inferred_` | Computed **from** raw records only | `inferred_difficulty.parquet` |

**Rationale:** Column names should be self-documenting. Anyone reading a dataframe can immediately understand provenance.

---

## Key Decision: state_id Moves Out of raw.parquet

In production, we don't know which state a record belongs to — that's what we're trying to infer. The `state_id` is ground-truth metadata, not a raw record attribute.

- `raw.parquet`: No state_id (production-equivalent)
- `synthetic_records.parquet`: Contains state_id for record-to-state linkage
- `validation.parquet`: Contains state_id as part of ground-truth labels

---

## Why Two Levels of Synthetic Metadata?

Per-record and per-soldier generation metadata serve different purposes:

| Level | Purpose | Cardinality |
|-------|---------|-------------|
| Per-record (`synthetic_records.parquet`) | Track how each record was generated (clerk, quality, completeness) | One per record |
| Per-soldier (`synthetic_soldiers.parquet`) | Track generation control decisions (difficulty tier targets) | One per soldier |

---

## Sanity Check for Synthetic Data

After running both generation and ground-truth difficulty computation:
- `gen_difficulty_tier` should equal `gt_difficulty_tier`
- `gen_complementarity_score` should equal `gt_complementarity_score`
- `gen_structural_resolvability` should equal `gt_structural_resolvability`

Any mismatch indicates a bug in one of the computation paths.

---

## Production Data Path

For production (real WWII) data:

1. Ingest raw records → `raw.parquet` (same schema as synthetic core)
2. Human annotation → `validation.parquet` (same schema as synthetic)
3. No `synthetic_*.parquet` files exist
4. Ground-truth difficulty module computes `gt_difficulty.parquet`
5. Preprocessing computes `inferred_difficulty.parquet`
6. Evaluation compares inferred to ground-truth

---

## Artifacts Produced

### New Files

1. **Instruction file:** `instructions/010_separate_synthetic_metadata_schema.md`
   - 5-phase implementation plan
   - Full schema specifications
   - Acceptance criteria

2. **ADR:** `docs/architecture/decisions/ADR-010-synthetic-metadata-separation.md`
   - Architectural rationale
   - Migration path from old to new column locations
   - Sanity check specification

### Updated Documentation

3. **DIFFICULTY_MODEL.md** — Added "Computation Contexts" section explaining the three prefixes

4. **docs/components/synthetic_data_generation/CURRENT.md** — Added note about pending ADR-010 schema refactoring

5. **docs/components/preprocessing/CURRENT.md** — Added ADR-010 references, difficulty submodule, inferred_difficulty.parquet output

6. **docs/ADR_INDEX.md** — Added ADR-010 entry

7. **CLAUDE.md** — Added ADR-010 to Key ADRs table

### Updated Context Packets

8. **docs/context-packets/full-bootstrap.md**
   - Updated examples to Terraform Combine domain
   - Expanded Data Structures section with new schema
   - Updated "What's Currently In Flux" section

9. **docs/context-packets/planning-synthetic.md** — Added ADR-010 and DIFFICULTY_MODEL.md references

10. **docs/context-packets/planning-resolver.md** — Added ADR-009 and DIFFICULTY_MODEL.md references

---

## Open Questions Resolved

| Question | Resolution |
|----------|------------|
| Which function computes difficulty columns? | Two separate implementations with different contexts |
| How to distinguish generation-time from evaluation-time difficulty? | Prefix convention: gen_, gt_, inferred_ |
| How to handle both synthetic and production data? | Same core schema; synthetic metadata in separate files |
| Where does state_id belong? | Not in raw.parquet; in synthetic_records.parquet and validation.parquet |

---

## Next Steps

1. Implement ADR-010 schema separation (instruction 010)
2. Create `src/difficulty/ground_truth.py` module for common gt_ computation
3. Rename preprocessing difficulty outputs to use `inferred_` prefix
4. Update downstream consumers of old column names

---

## References

- `ADR-006` — Three-layer difficulty model
- `ADR-008` — Preprocessing v4.1 update (established synthetic_metadata pattern)
- `ADR-009` — Resolver generation alignment (sample by soldier difficulty)
- `ADR-010` — Synthetic metadata separation (this decision)
- `DIFFICULTY_MODEL.md` — Now includes computation contexts section
