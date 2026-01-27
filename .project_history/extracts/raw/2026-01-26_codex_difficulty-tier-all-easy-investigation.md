# Session Extract: Difficulty Tier Saturation (All Easy) Investigation

**Date:** 2026-01-26
**Participants:** Human (Project Lead), Codex (GPT-5)
**Purpose:** Diagnose why v4.1 synthetic difficulty tiers collapsed to 100% easy
**Duration:** ~30 minutes

---

## Summary

All soldiers were labeled **easy** because every soldier had at least one **fully complete** record
(`path_completeness >= 0.95`). The difficulty assignment short-circuits to `easy` when any complete
record exists, so the distribution saturates. The completeness saturation comes from rendering logic
that emits full paths for many clerks (familiarity defaults to different-branch) and from unused
path completeness tendencies defined in the style spec.

---

## Evidence (from regenerated artifacts)

From `data/synthetic/raw.parquet`:
- **100% of soldiers** have at least one record with `path_completeness >= 0.95`.
- **71.3% of all records** have `path_completeness == 1.0` (142,511 / 200,000).
- Per-soldier **median completeness** ~1.0; per-soldier **max completeness** is always 1.0.

From `data/synthetic/validation.parquet`:
- Difficulty tiers: `easy = 100%` (all 1,000 soldiers).
- Collision zones exist for ~93% of soldiers, but are overridden by `any_complete = True`.

---

## Root Causes (code-level)

1. **DifficultyComputer short-circuits to EASY**
   - `src/synthetic/difficulty_computer.py` assigns EASY if `any_complete` is true.
   - With universal full-path records, this always fires.

2. **Renderer emits full paths too often**
   - `src/synthetic/renderer.py::_select_levels()` includes full levels when familiarity is
     `DIFFERENT_BRANCH`.
   - Many archetypes have `familiarity_override: ignore` or `familiarity_applies: false`, so
     familiarity becomes `DIFFERENT_BRANCH` for most records.

3. **Path completeness tendencies unused**
   - `path_completeness_tendency` and `structural_signals_tendency` exist in archetypes but are
     never used in level selection or signal generation.

4. **Structural signals are effectively empty** (secondary)
   - `_extract_structural_signals()` checks only full labels (e.g., "Squadron"), while many clerks
     use abbreviations ("Sq", "Sec", etc.), so structural resolvability is often false.

5. **Difficulty rebalancer is non-mutating**
   - `DifficultyRebalancer` identifies needed adjustments but never alters or re-renders records.

---

## Proposed Fix Directions

- **Use `path_completeness_tendency` in `_select_levels()`** to stochastically drop levels even for
  different-branch clerks, preventing universal full-path entries.
- **Reduce full-path archetype exposure** in `src/synthetic/source_generator.py` (tighten
  `ARCHETYPE_BIAS` for tier 1/2).
- **Implement actual rebalancing** in `DifficultyRebalancer` (re-render selected soldiers).
- **Expand structural signal detection** to recognize abbreviated labels ("Sq", "Sec", etc.).

---

## Files Implicated

- `src/synthetic/difficulty_computer.py`
- `src/synthetic/renderer.py`
- `src/synthetic/clerk_factory.py`
- `src/synthetic/source_generator.py`
- `src/synthetic/difficulty_rebalancer.py`
- `data/synthetic/raw.parquet`
- `data/synthetic/validation.parquet`

---

## References

- `SESSION_STATE.md` (issues section)
- `docs/components/synthetic_data_generation/CURRENT.md`
