# Instruction 005: Preprocessing Pipeline Update for Synthetic v4.1

**Created:** 2026-01-26
**Status:** Active
**Depends on:** Completed synthetic v4.1 implementation (Instruction 004)
**Blocks:** Synthetic data generation, evaluation pipeline updates

---

## Objective

Update the preprocessing pipeline to handle the new v4.1 synthetic data schema and Terraform Combine domain vocabulary. This is primarily a vocabulary swap and schema passthrough update—the core regex extraction architecture remains sound.

---

## Context and Rationale

### Why This Change Is Needed

The synthetic data system was rebuilt in v4.1 with:

1. **Complete domain change:** WWII military → Terraform Combine (fictional interstellar org)
2. **New schema columns:** `state_id`, `path_completeness`, `levels_provided`, `extraction_signals`
3. **Variable-depth hierarchies:** 4 branches with depths 3-5 (vs. fixed military hierarchy)
4. **Explicit state tracking:** States are first-class objects with `state_id`

The preprocessing pipeline's glossary and adapter were built for the old WWII vocabulary. They need updating to work with the new domain.

### What's NOT Changing

The core `regex_preprocessing.py` architecture is domain-agnostic and sound:
- Factorize-extract-broadcast optimization
- Unicode-safe boundaries
- Paired category extraction
- Graceful degradation with sentinel values

We're swapping vocabulary, not rewriting extraction logic.

### Scoping Decision: Synthetic-Only Fields

The v4.1 schema includes fields computed during synthetic generation that won't exist in real data:
- `path_completeness` (float)
- `levels_provided` (list[str])
- `extraction_signals` (list[str])

**Decision:** Pass these through to `synthetic_metadata.parquet` for testing/analysis. Do NOT attempt to re-extract or validate them in preprocessing. They are synthetic artifacts, not preprocessing outputs.

---

## Files to Modify

| File | Change Type | Effort |
|------|-------------|--------|
| `src/preprocessing/glossary_generator.py` | **Rewrite** | High |
| `src/preprocessing/preprocessing_adapter.py` | Update | Medium |
| `config/glossaries/synthetic_glossary.json` | Regenerate | Auto |
| `regex_preprocessing.py` | None | — |

---

## Task 1: Rewrite glossary_generator.py

### Current State

The current generator reads from:
- `docs/components/synthetic_data_generation/synthetic_style_spec_v3.yaml`
- `config/hierarchies/hierarchy_reference.json`
- `config/synthetic/synthetic_vocabulary.json`

And extracts WWII terms: Infantry Division, Company, Battalion, phonetics (Easy, Fox), ranks (Sgt, Cpl).

### New Source Files

Read from:
- `docs/components/synthetic_data_generation/synthetic_style_spec_v4.1.yaml`
- `config/hierarchies/hierarchy_reference.json` (now contains Terraform Combine branches)
- `config/synthetic/synthetic_vocabulary.json` (now contains new domain vocabulary)

### Term Types to Extract

| Term Type | Source | Examples |
|-----------|--------|----------|
| **Branch Terms** | hierarchy_reference.json | Colonial Administration/CA, Defense Command/DC, Expeditionary Corps/EC, Resource Directorate/RD |
| **Level Terms** | hierarchy_reference.json per branch | Sector, Fleet, Squadron, Wing, Element, Colony, District, Settlement, Expedition, Team, Operation, Facility, Crew |
| **Designator Names** | hierarchy_reference.json or vocabulary.json | Greek letters (Alpha, Beta, Gamma...), Named units (Kestrel, Talon, Verdant, Pathfinder, Deepcore...) |
| **Role Terms** | style_spec or vocabulary.json | **PLACEHOLDER: empty list** (ranks TBD—will be populated for real data transition) |

### Branch-Specific Level Terms

```
Colonial Administration (depth 4): Sector → Colony → District → Settlement
Defense Command (depth 5):         Sector → Fleet → Squadron → Wing → Element
Expeditionary Corps (depth 3):     Sector → Expedition → Team
Resource Directorate (depth 4):    Sector → Operation → Facility → Crew
```

### Abbreviation Handling

For each term, extract both full form and abbreviations. The v4.1 config uses patterns like:
- Branch: "Colonial Administration" / "CA"
- Level: "Squadron" / "Sq" / "SQ"
- Names: Some have abbreviations, some don't

Preserve the existing glossary schema:
```json
{
  "full term": "Squadron",
  "abbreviations": ["Sq", "SQ", "Sqn"],
  "term type": "Level Term"
}
```

### Implementation Notes

1. Parse YAML for branch definitions and level structures
2. Parse JSON for hierarchy details and vocabulary pools
3. Handle the name pools: shared names (appear across branches) and branch-unique names
4. **Role Terms: Output an empty list with a comment noting this is a placeholder**

### Anti-Patterns to Avoid

❌ **Don't hardcode the term lists.** Read from config files so vocabulary changes don't require code changes.

❌ **Don't try to infer abbreviations.** Only use explicitly defined abbreviations in the configs. If a term has no listed abbreviations, it gets an empty abbreviation list.

❌ **Don't include collision designators (1, 2, 3, A, B, C) as glossary terms.** These are captured by the existing digit/alpha extraction patterns, not the glossary-driven term extraction.

### Decision Boundary

If you encounter vocabulary in the configs that doesn't fit cleanly into Branch Term / Level Term / Role Term categories, **flag it in code comments** and make a reasonable choice. Don't block on edge cases.

---

## Task 2: Update preprocessing_adapter.py

### Current State

Reads `data/synthetic/raw.parquet`, adapts schema, runs extraction, outputs:
- `data/synthetic/canonical.parquet` (universal schema)
- `data/synthetic/synthetic_metadata.parquet` (synthetic-specific fields)

### Schema Changes

**Input (`raw.parquet`) new columns:**
- `state_id` (string) — NEW in v4.1
- `path_completeness` (float) — NEW in v4.1
- `levels_provided` (list[str]) — NEW in v4.1
- `extraction_signals` (list[str]) — NEW in v4.1

**Output routing:**

| Column | Destination | Notes |
|--------|-------------|-------|
| `source_id` | canonical | Existing |
| `soldier_id` | canonical | Existing |
| `state_id` | **canonical** | NEW — needed for evaluation |
| `raw_text` | canonical (as Name) | Existing |
| `clerk_id` | metadata | Existing |
| `situation_id` | metadata | Existing |
| `quality_tier` | metadata | Existing |
| `path_completeness` | **metadata** | NEW — synthetic only |
| `levels_provided` | **metadata** | NEW — synthetic only |
| `extraction_signals` | **metadata** | NEW — synthetic only |

### Join Key Update

The `synthetic_metadata.parquet` join key should be `(source_id, soldier_id, state_id)` — explicit and unambiguous.

Note: Due to source-anchoring in v4.1, a (source_id, soldier_id) pair has exactly one state. But using the explicit three-column key is safer and clearer.

### Implementation Notes

1. Check for new columns; handle gracefully if missing (backward compatibility during transition)
2. Update docstrings to reflect v4.1 schema
3. Log which columns were found/routed for debugging

### Anti-Patterns to Avoid

❌ **Don't attempt to validate or re-compute `path_completeness`, `levels_provided`, or `extraction_signals`.** These are synthetic generation artifacts. Pass them through unchanged.

❌ **Don't fail if new columns are missing.** The adapter may be run on older data during transition. Check for column existence and handle gracefully.

❌ **Don't process `sources.parquet`.** This file exists for synthetic generation analysis only. Preprocessing doesn't need it.

### Decision Boundary

If `raw.parquet` contains columns not documented here, **pass them to metadata** and log a warning. Don't fail on unexpected columns.

---

## Task 3: Regenerate Glossary

After updating `glossary_generator.py`, run it to produce the new glossary:

```bash
python3.11 -m src.preprocessing.glossary_generator
```

**Expected output:** `config/glossaries/synthetic_glossary.json`

### Validation Checks

After generation, verify:
1. Glossary contains Branch Terms (should be 4 branches × 2 forms = ~8 entries)
2. Glossary contains Level Terms (should be ~15-20 unique level names with abbreviations)
3. Glossary contains named units (shared + branch-unique, ~20-30 names)
4. Role Terms section exists but is empty (placeholder)
5. No WWII terms remain (Infantry, Battalion, Company, etc.)

---

## Task 4: Integration Test

After all changes, run the full preprocessing flow:

```bash
python3.11 -m src.preprocessing.preprocessing_adapter --timing
```

### Expected Behavior

1. Loads `raw.parquet` (v4.1 schema)
2. Loads new glossary
3. Extracts using new vocabulary
4. Outputs `canonical.parquet` with `state_id` column
5. Outputs `synthetic_metadata.parquet` with new columns

### Validation Checks

1. `canonical.parquet` has `state_id` column
2. `synthetic_metadata.parquet` has `path_completeness`, `levels_provided`, `extraction_signals`
3. Join on `(source_id, soldier_id, state_id)` between canonical and metadata is 1:1
4. Extraction categories show reasonable match rates (will differ from WWII baseline)

---

## Out of Scope

The following are explicitly NOT part of this instruction:

| Item | Reason |
|------|--------|
| `component_router.py` | Was pending before v4.1, remains pending. Needs separate design given collision complexity. |
| `id_resolver.py` | Deferred — not needed for synthetic data |
| Difficulty column handling | These live in `validation.parquet`, not preprocessing's concern |
| Defining `extraction_signals` vocabulary | Bracketed for later design decision |
| Test data generation | Will be created after synthetic artifacts are produced |

---

## Files to Read Before Starting

1. `docs/components/synthetic_data_generation/CURRENT.md` — v4.1 schema and philosophy
2. `docs/components/preprocessing/CURRENT.md` — current preprocessing architecture
3. `docs/architecture/decisions/ADR-008-preprocessing-v4.1-update.md` — decision record for this change
4. `config/hierarchies/hierarchy_reference.json` — new Terraform Combine structure
5. `config/synthetic/synthetic_vocabulary.json` — new vocabulary pools

---

## Success Criteria

- [ ] `glossary_generator.py` reads from v4.1 config files
- [ ] Generated glossary contains Terraform Combine vocabulary, no WWII terms
- [ ] `preprocessing_adapter.py` routes `state_id` to canonical
- [ ] `preprocessing_adapter.py` routes completeness fields to metadata
- [ ] Metadata join key is `(source_id, soldier_id, state_id)`
- [ ] Full pipeline runs without error on v4.1 synthetic data
- [ ] Role Terms placeholder documented for future population

---

## Changelog

### v1.0.0 (2026-01-26)
- Initial instruction for v4.1 preprocessing update
