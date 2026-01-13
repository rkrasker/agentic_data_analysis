# Agent Instructions: Build Synthetic Raw Generator from Style Spec + Ground Truth

## Goal
Implement a *renderer* that converts rows from `validation.parquet` (ground truth per soldier) into manifest-like `raw.parquet` records, using the config in `synthetic_style_spec_v2.yaml`.

This document is **reusable**: it describes the architecture and responsibilities, not a one-off patch.

## Inputs
- Ground truth: `validation.parquet` (schema matches the existing generator)
- Optional truth dynamics:
  - `corr.parquet` (old_id/new_id mapping)
  - `unit_changes.parquet` (rare transfers; for “manifest-only” you may keep transfers rare)
- Reference hierarchy:
  - `hierarchy_json.json` (component definitions + subordinate units)
- Style/spec:
  - `synthetic_style_spec_v1.yaml`

## Output (must be schema-compatible)
Write `raw.parquet` with these columns:
- `source_id`, `soldier_id`, `raw_text`, `quality_tier`, `pattern_tier`, `has_error`, `has_confounding`

(You may also create an *internal* debug output mapping `record_id -> source_profile_id -> truth fields used`, but do not change the required `raw.parquet` schema unless downstream code is updated.)

## Core architecture
Split generation into two separable layers:

### A) Truth selection (per record)
Responsibilities:
- choose which ID appears (`primary_id` vs `old_id`) using `corr.parquet` logic
- choose which unit assignment is active (normally baseline; optionally pre-transfer vs post-transfer using `unit_changes.parquet`)
- decide “record completeness” and which truth fields to expose (company only vs company+bn vs bn+regt, etc.)
Outputs:
- a `TruthSlice` object (in-memory) containing the chosen truth attributes for rendering

### B) Rendering (surface text)
Responsibilities:
- create `source_id` and choose a `source_profile` (clustered clerk style)
- choose a `template` (NAME/UNIT/EXTRA ordering)
- render:
  - name (format + truncation) according to spec and quality tier
  - rank (variants + placement) according to spec and profile
  - unit shorthand (family A/B/C/D/E) with orientation handling
  - extra text snippets:
    - from domain_context
    - from component affinities (signal)
    - from confounders
- apply noise transforms (typewriter/OCR) per noise_profile and quality tier
- inject occasional errors per spec

## Required behaviors (for realism + learnability)
1. **Cluster by source**:
   - A `source_id` represents a “page/manifest batch.”
   - A source has one `source_profile` that governs:
     - shorthand family weights
     - slash orientation (normal vs reversed)
     - label usage rate
     - caps and separator preferences
     - extra text density and label rate
2. **Compressed shorthand is default**:
   - For most sources, `B_slash_positional` and/or `C_runon` should dominate.
3. **Reversal confounder is source-specific**:
   - Only a small share of sources use reversed orientation.
   - Within those sources, most slash expressions follow the reversed convention.
4. **Extra text must be informative but non-deterministic**:
   - Implement `component_affinities` as weighted tendencies with leak-through.
   - Ensure no single snippet family perfectly predicts a component.
5. **No “division + company only” patterns** (unless the spec explicitly adds them later):
   - Avoid unit strings that jump echelons without intermediate levels.

## Implementation checklist (non-code)
- Create a `SpecLoader` that parses YAML and exposes:
  - distributions
  - templates
  - source_profiles
  - snippet families + affinity map
  - noise profiles
- Create a `SourceContextManager`:
  - samples `source_id` batches
  - assigns/reuses a `source_profile` for each source
- Create a `Renderer`:
  - `render_name(truth, quality_tier, profile)`
  - `render_rank(truth, profile)`
  - `render_unit(truth, profile, component_type)`
  - `render_extra(truth.component_id, profile.domain_context)`
  - `apply_noise(text, profile.noise_profile, quality_tier)`
- Wire it into the existing Phase 5 raw generation step.

## Calibration / quick validation (recommended)
Use `seed_set_v1.jsonl` as a “does it look right?” sanity check:
- ensure your renderer can produce lines similar in character (not exact)
- verify the reversal sources are recognizable as a clustered dialect
- compute simple counts:
  - rate of extra text insertion matches `extra_text_density`
  - per-component snippet family rates reflect `component_affinities` with leak-through

