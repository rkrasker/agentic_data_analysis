# ADR-008: Preprocessing Pipeline Update for Synthetic v4.1

**Status:** Accepted  
**Date:** 2026-01-26  
**Deciders:** Project Lead  
**Context:** Planning session for preprocessing updates following synthetic v4.1 implementation

---

## Context

The synthetic data system was rebuilt in v4.1 (ADR-007) with a complete domain change from WWII military to a fictional "Terraform Combine" interstellar organization. Additionally, ADR-006 introduced a three-layer difficulty model that added new schema columns for tracking record completeness and difficulty.

The preprocessing pipeline needs updating to:
1. Work with the new vocabulary domain
2. Handle new schema columns appropriately
3. Maintain backward compatibility during transition

The preprocessing pipeline has three implemented components:
- `regex_preprocessing.py` — Core extraction engine (domain-agnostic)
- `glossary_generator.py` — Generates term glossary from config files
- `preprocessing_adapter.py` — Bridges synthetic output to extraction

---

## Decisions

### Decision 1: Glossary Generator Full Rewrite

**Choice:** Rewrite `glossary_generator.py` to read from v4.1 config files and extract Terraform Combine vocabulary.

**Rationale:** The entire vocabulary domain has changed. There's no meaningful overlap between WWII terms (Infantry Division, Company, Battalion, phonetics) and Terraform Combine terms (Fleet, Squadron, Colony, District). A rewrite is cleaner than trying to abstract/parameterize the old code.

**What transfers:** The glossary schema format (full term, abbreviations, term type) remains unchanged. Only the source files and extraction logic change.

### Decision 2: Schema Column Routing

**Choice:** Route new v4.1 columns as follows:

| Column | Destination | Rationale |
|--------|-------------|-----------|
| `state_id` | canonical.parquet | Needed for evaluation — states are the unit of resolution |
| `path_completeness` | synthetic_metadata.parquet | Synthetic generation artifact, not present in real data |
| `levels_provided` | synthetic_metadata.parquet | Synthetic generation artifact |
| `extraction_signals` | synthetic_metadata.parquet | Synthetic generation artifact |

**Rationale:** The distinction is between columns that would exist in real data vs. columns that are artifacts of the synthetic generation process. `state_id` is the ground truth for evaluation and must be in canonical. The completeness/signal fields are synthetic-only metadata.

### Decision 3: Pass-Through for Synthetic Fields (No Re-extraction)

**Choice:** Pass `path_completeness`, `levels_provided`, and `extraction_signals` through unchanged. Do not attempt to re-extract or validate them in preprocessing.

**Alternatives considered:**
- **Re-extract independently:** Would allow validation of synthetic generator output
- **Compare and validate:** Extract independently and compare to synthetic values

**Rationale:** These fields are computed by the synthetic generator's `CompletenessAnalyzer` during rendering. Re-extracting them in preprocessing would:
1. Duplicate logic that belongs in generation
2. Require defining the extraction_signals vocabulary (currently bracketed)
3. Add complexity without clear benefit

If we need validation, it should happen in the synthetic generation tests, not preprocessing.

### Decision 4: Explicit Three-Column Join Key

**Choice:** The join key between `canonical.parquet` and `synthetic_metadata.parquet` is `(source_id, soldier_id, state_id)`.

**Alternatives considered:**
- **Two-column key (source_id, soldier_id):** Would work due to source-anchoring (each source captures one state per soldier)

**Rationale:** The three-column key is explicit and unambiguous. It makes the relationship clear even to someone unfamiliar with source-anchoring semantics. The marginal storage cost is negligible.

### Decision 5: Role Terms as Placeholder

**Choice:** The glossary generator outputs an empty Role Terms section with a comment noting it's a placeholder for real data transition.

**Rationale:** The Terraform Combine rank vocabulary was not fully defined in the v4.1 synthetic generator build. Rather than block preprocessing on this, we output an empty placeholder. Ranks will be populated when:
1. The synthetic generator adds rank vocabulary, OR
2. The system transitions to real data with actual military ranks

### Decision 6: Regex Preprocessing Unchanged

**Choice:** No changes to `regex_preprocessing.py`.

**Rationale:** The core extraction engine is domain-agnostic. It operates on whatever glossary it's given. The paired extraction patterns, digit sequence handling, and unicode-safe boundaries all transfer directly. Only the vocabulary (via glossary) changes.

### Decision 7: Component Router Remains Pending

**Choice:** Do not implement `component_router.py` as part of this update.

**Rationale:** The router was pending before v4.1 and requires its own design work given:
- Variable-depth hierarchies (3-5 levels depending on branch)
- Collision zone complexity
- Branch inference from structural signals

This is a separate concern from vocabulary updates. It should be addressed in a dedicated instruction after the basic preprocessing flow works.

### Decision 8: Ignore sources.parquet

**Choice:** Preprocessing does not read or process `sources.parquet`.

**Rationale:** This file contains source-level metadata (`home_unit`, `temporal_anchor`) used for synthetic generation analysis. It's not part of the preprocessing input/output contract.

---

## Consequences

### Positive
- Clean separation: canonical has evaluation-relevant columns, metadata has synthetic artifacts
- Minimal changes to core extraction engine
- Clear upgrade path when rank vocabulary is defined
- Explicit join key prevents ambiguity

### Negative
- No independent validation of synthetic completeness fields in preprocessing
- Role terms not functional until vocabulary defined
- Component routing still pending

### Neutral
- Glossary format unchanged (just different terms)
- Adapter pattern unchanged (just different column routing)

---

## What We Explicitly Decided NOT To Do

| Decision | Reason |
|----------|--------|
| Re-extract `extraction_signals` in preprocessing | Would duplicate generation logic; vocabulary not yet defined |
| Validate synthetic fields against re-extraction | Belongs in generation tests, not preprocessing |
| Use two-column join key | Three-column is more explicit, negligible cost |
| Hardcode vocabulary in glossary generator | Should read from config files for maintainability |
| Process `sources.parquet` | Not part of preprocessing contract |
| Implement component router | Requires separate design work |

---

## Edge Cases Discussed

### Missing columns during transition
If preprocessing runs on older v4.0 data before v4.1 artifacts exist, new columns may be missing. Adapter should check for column existence and handle gracefully (output empty/null for missing columns, don't fail).

### Unexpected columns in raw.parquet
If raw.parquet contains columns not documented in schema, pass them to metadata and log a warning. Don't fail on unexpected columns.

### Collision designators (1, 2, 3, A, B, C)
These should NOT be glossary terms. They're captured by existing digit/alpha extraction patterns. Adding them to the glossary would cause over-matching.

### Abbreviation inference
Don't try to infer abbreviations (e.g., "Squadron" → "Sq"). Only use explicitly defined abbreviations from config files.

---

## Implementation Notes

**Files to change:**
- `src/preprocessing/glossary_generator.py` — Full rewrite
- `src/preprocessing/preprocessing_adapter.py` — Schema updates
- `config/glossaries/synthetic_glossary.json` — Regenerated output

**Files unchanged:**
- `src/preprocessing/regex_preprocessing.py` — Domain-agnostic

**Files out of scope:**
- `src/preprocessing/component_router.py` — Pending
- `src/preprocessing/id_resolver.py` — Deferred

---

## Related Documents

- `ADR-006` — Three-layer difficulty model (introduced completeness fields)
- `ADR-007` — Synthetic data redesign (domain change to Terraform Combine)
- `docs/components/preprocessing/CURRENT.md` — Preprocessing architecture
- `docs/components/synthetic_data_generation/CURRENT.md` — v4.1 schema
- `instructions/active/005_preprocessing-v4.1-terraform-combine.md` — Implementation instruction
