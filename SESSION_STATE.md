# Current Session State

**Last Updated:** 2026-01-27 (Opus 4.5, session 2)

## Active Task

Fix rendering realism gap where even lowest-quality synthetic records are structurally pristine (full level-type labels, consistent delimiters, clean designator values), making tier-3 output indistinguishable from tier-1.

## What We Accomplished This Session

### Instruction 006 implemented (by prior agent)
The difficulty saturation fix from `instructions/active/006_fix-difficulty-saturation.md` was implemented:
- `path_completeness_tendency` wired into `_select_levels()` with stochastic level dropping
- `_assign_tier()` collision-zone short-circuit softened
- Confounder injection made independent of clutter gate
- Imperfection/OCR simulation implemented in `_apply_imperfections()`

### Diagnosed rendering realism gap
Inspected canonical output and identified that even after instruction 006 fixes, records are far too clean. A tier-3 record like `Spec-2 Alden, A.W. Sector Alpha, Colony Amber, District 8, Settlement Landfall CA` would be a *high* tier-1 in actual data. Five specific gaps identified:

1. **Level-type labels always present for labeled styles** — "Sector Alpha, Colony Amber" instead of "Alpha, Amber" or just "Alpha Amber"
2. **Designator values never abbreviated** — "Landfall" never becomes "Lndfl" or "Lf"
3. **Delimiter locked per clerk** — uniform ", , , " instead of mixed "/, , "
4. **`omit_level_names` is binary** — all labels or no labels, no per-level graduation
5. **Familiarity doesn't affect label presence** — familiar clerk still writes "Settlement Landfall" not just "Landfall"

### Wrote Instruction 007
Created `instructions/active/007_rendering-realism-overhaul.md` with five implementation tasks:
1. Per-level stochastic label omission (new `label_omission_rate` on UnitFormat)
2. Designator value abbreviation (new `value_abbreviation_rate` on UnitFormat)
3. Within-entry delimiter mixing (driven by clerk `format_lock`)
4. Familiarity-driven label omission boost (additive with base rate)
5. Style spec archetype updates (rates per archetype + missing archetype definitions)

## Where I Left Off

Instruction 007 is written and ready for implementation. No code changes were made this session — the instruction document is the deliverable. The next agent should:
1. Read `instructions/active/007_rendering-realism-overhaul.md`
2. Implement the five tasks in order
3. Run existing tests to confirm no regressions
4. Run pipeline and visually inspect output for realism improvement

## Open Questions

1. **Are the `label_omission_rate` values correctly calibrated?** The rates in the instruction are estimates. After implementation, the pipeline output needs visual inspection — if records are still too clean, rates need to increase; if records become unreadable, rates are too high.
2. **Should value abbreviation be consistent within a clerk?** The instruction says stochastic per-entry, but a real clerk might consistently abbreviate "Amber" as "Amb" across all their entries. This is a fidelity question that can be deferred.
3. **Missing archetypes (`colonial_district`, `defense_operations`)** are referenced in quality tier biases but not fully defined in the style spec. Instruction 007 includes stubs, but these may need tuning.
4. **Does the familiarity boost interact correctly with `familiarity_override: "ignore"`?** The instruction says it should — `_get_familiarity_level()` returns DIFFERENT_BRANCH for those clerks, giving 0.0 boost — but this needs verification after implementation.

## Current State of Project

The v4.1 synthetic data system has the difficulty computation fixed (instruction 006) but the rendering layer still produces unrealistically clean output. Instruction 007 targets the rendering gap. After 007 is implemented, the synthetic pipeline should produce records that are visually distinguishable by quality tier and require the same parsing effort as real-world data.

## Pending Active Instructions

- `instructions/active/006_fix-difficulty-saturation.md` — Implemented, awaiting pipeline re-run verification
- `instructions/active/007_rendering-realism-overhaul.md` — Written, awaiting implementation

## Recent Context

- **This session's extract:** `.project_history/extracts/raw/2026-01-27_opus_rendering-realism-diagnosis.md`
- **Prior session extract:** `.project_history/extracts/raw/2026-01-27_opus_difficulty-saturation-diagnosis.md`
- **Codex investigation:** `.project_history/extracts/raw/2026-01-26_codex_difficulty-tier-all-easy-investigation.md`
- **ADR-006:** `docs/architecture/decisions/ADR-006_per-record-vs-per-soldier-difficulty.md`
- **ADR-007:** `docs/architecture/decisions/ADR-007-synthetic-data-redesign.md`
- **Style spec:** `docs/components/synthetic_data_generation/synthetic_style_spec_v4.1.yaml`
- **Key insight:** Instruction 006 fixed *which levels appear* (path completeness). Instruction 007 fixes *how those levels are rendered* (labels, abbreviation, delimiters). Both are needed for realistic output.
