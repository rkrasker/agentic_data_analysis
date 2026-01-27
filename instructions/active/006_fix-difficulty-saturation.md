# Instruction 006: Fix Difficulty Tier Saturation (All Easy)

**Created:** 2026-01-27
**Status:** Active
**Depends on:** Completed synthetic v4.1 implementation (Instruction 004)
**Blocks:** Resolver strategy rebuild, evaluation pipeline
**Model:** Sonnet, thinking on

---

## Objective

Fix the difficulty tier saturation bug where 100% of soldiers are classified EASY. Four code-level changes are required across three files. After the fix, the difficulty distribution should approximate the style spec targets: ~50% easy, ~30% moderate, ~15% hard, ~5% extreme (±5%).

---

## Context and Rationale

### The Bug

The Codex investigation (`.project_history/extracts/raw/2026-01-26_codex_difficulty-tier-all-easy-investigation.md`) found:
- **100% of soldiers** have at least one record with `path_completeness >= 0.95`
- **71.3% of all records** have `path_completeness == 1.0`
- Difficulty tiers: `easy = 100%` (all 1,000 soldiers)

### Root Causes (diagnosed by Opus 4.5)

See `.project_history/extracts/raw/2026-01-27_opus_difficulty-saturation-diagnosis.md` for full analysis.

| # | Root Cause | Location | Severity |
|---|-----------|----------|----------|
| 1 | `DIFFERENT_BRANCH` familiarity includes ALL levels | `renderer.py::_select_levels()` line 247 | Critical |
| 2 | `path_completeness_tendency` defined on every archetype but never used | `renderer.py` — not wired | Critical |
| 3 | `any_complete` short-circuits to EASY even in collision zones | `difficulty_computer.py::_assign_tier()` line 938 | Critical |
| 4 | Confounders gated behind clutter (effective rate ~1%) | `vocabulary_injector.py` line 111 | Important |
| 5 | Imperfections (typos, OCR errors) may not be applied to rendered text | `renderer.py` — unverified | Important |

### Reference Documents

- **Style spec:** `docs/components/synthetic_data_generation/synthetic_style_spec_v4.1.yaml`
- **ADR-006:** `docs/architecture/decisions/ADR-006_per-record-vs-per-soldier-difficulty.md`
- **Instruction 004:** `instructions/completed/004_synthetic-v4.1-terraform-combine.md`

---

## Scope

### In Scope

| File | Change |
|------|--------|
| `src/synthetic/renderer.py` | Wire `path_completeness_tendency` into `_select_levels()` |
| `src/synthetic/difficulty_computer.py` | Soften `any_complete` short-circuit for collision zones |
| `src/synthetic/vocabulary_injector.py` | Independent confounder injection gate |
| `src/synthetic/renderer.py` | Verify and implement imperfection/OCR simulation on rendered text |

### Out of Scope

- Style spec changes (the spec is correct; implementation must honor it)
- `difficulty_rebalancer.py` mutation logic (pre-existing non-mutating design, separate issue)
- Pipeline re-run (will be done manually after code changes)
- Config file changes (vocabulary, themes, hierarchy are fine)

---

## Task 1: Wire `path_completeness_tendency` into Level Selection

**File:** `src/synthetic/renderer.py`
**Method:** `_select_levels()` (currently lines 233-259)

### Current Behavior

```python
def _select_levels(self, levels, familiarity, clerk):
    if familiarity == FamiliarityLevel.SAME_L3:
        include = [levels[-1]]
    elif familiarity == FamiliarityLevel.SAME_L2:
        include = levels[2:]
    elif familiarity == FamiliarityLevel.SAME_BRANCH:
        include = levels[1:]
    else:  # DIFFERENT_BRANCH
        include = list(levels)       # <-- ALL levels, always
    # ... format flags filter further
```

`DIFFERENT_BRANCH` always returns all levels. No stochastic dropping.

### Required Behavior

After selecting the initial level set based on familiarity, apply `path_completeness_tendency` to stochastically drop levels. The tendency determines what fraction of available levels to keep.

**Tendency-to-retention mapping:**

| `path_completeness_tendency` | Target retention (fraction of branch depth) | Description |
|------------------------------|---------------------------------------------|-------------|
| `very_high` | 0.90 - 1.00 | Almost always full path |
| `high` | 0.70 - 0.90 | Usually most levels |
| `medium` | 0.50 - 0.70 | About half |
| `low` | 0.30 - 0.50 | Often incomplete |
| `very_low` | 0.20 - 0.40 | Usually fragmentary |

### Implementation Approach

```python
TENDENCY_RETENTION = {
    "very_high": (0.90, 1.00),
    "high": (0.70, 0.90),
    "medium": (0.50, 0.70),
    "low": (0.30, 0.50),
    "very_low": (0.20, 0.40),
}

def _select_levels(self, levels, familiarity, clerk):
    # Step 1: Determine candidate levels from familiarity (existing logic)
    if familiarity == FamiliarityLevel.SAME_L3:
        candidates = [levels[-1]]
    elif familiarity == FamiliarityLevel.SAME_L2:
        candidates = levels[2:]
    elif familiarity == FamiliarityLevel.SAME_BRANCH:
        candidates = levels[1:]
    else:
        candidates = list(levels)

    # Step 2: Apply path_completeness_tendency to stochastically drop levels
    tendency = getattr(clerk, 'path_completeness_tendency', 'medium')
    lo, hi = TENDENCY_RETENTION.get(tendency, (0.50, 0.70))
    target_retention = self.rng.uniform(lo, hi)
    target_count = max(1, round(len(levels) * target_retention))

    if len(candidates) > target_count:
        # Drop levels, preferring to keep the lowest (most specific) levels
        # since clerks are more likely to omit higher echelons
        candidates = self._drop_levels_to_target(candidates, levels, target_count)

    # Step 3: Apply format flags (existing logic)
    if not clerk.unit_format.include_sector and levels:
        candidates = [lvl for lvl in candidates if lvl != levels[0]]
    if not clerk.unit_format.include_level2 and len(levels) > 1:
        candidates = [lvl for lvl in candidates if lvl != levels[1]]
    if not clerk.unit_format.include_lowest_levels and len(levels) > 3:
        candidates = [lvl for lvl in candidates if levels.index(lvl) <= 2]

    if not candidates and levels:
        candidates = [levels[-1]]

    return candidates

def _drop_levels_to_target(self, candidates, all_levels, target_count):
    """Drop levels to reach target count, preferring to drop higher echelons."""
    if len(candidates) <= target_count:
        return candidates

    # Higher levels (sector, fleet/colony) are dropped first
    # Lower levels (element, crew, team) are kept
    droppable = list(candidates)
    while len(droppable) > target_count and len(droppable) > 1:
        # Drop the highest-echelon remaining level
        droppable.pop(0)

    return droppable
```

### Key Constraints

- **Minimum 1 level:** Never return an empty list
- **Prefer dropping higher echelons:** Clerks omit "Sector Alpha, Fleet Kestrel" before they omit "Element 7"
- **The RNG must be the renderer's RNG** (not a new one) for reproducibility
- **`path_completeness_tendency` is accessed from the clerk archetype**, already stored via `clerk_factory.py:131`

### Verification

After this change, run the pipeline and check:
```python
import pandas as pd
df = pd.read_parquet("data/synthetic/raw.parquet")
print(df["path_completeness"].describe())
# Should show mean well below 1.0 and significant variance
print((df["path_completeness"] >= 0.95).mean())
# Should be well below 71.3% (was 71.3% before fix)
```

---

## Task 2: Soften `any_complete` Short-Circuit in Difficulty Computation

**File:** `src/synthetic/difficulty_computer.py`
**Method:** `_assign_tier()` (currently lines 926-961)

### Current Behavior

```python
def _assign_tier(self, any_complete, collision_zone, ...):
    if any_complete:
        return DifficultyTier.EASY    # <-- Always EASY if any record is complete
```

### Required Behavior

A complete record is only automatically EASY if the soldier is NOT in a collision zone. In collision zones, even a complete record requires additional checks.

```python
def _assign_tier(self, any_complete, collision_zone, collision_severity,
                 complementarity_score, structural_resolvability):
    # EASY: Complete record outside collision zone
    if any_complete and not collision_zone:
        return DifficultyTier.EASY

    # EASY: Complete record in collision zone BUT structurally resolvable
    if any_complete and collision_zone and structural_resolvability:
        return DifficultyTier.EASY

    # EASY: High complementarity outside collision zone
    if complementarity_score > 0.8 and not collision_zone:
        return DifficultyTier.EASY
    if structural_resolvability and complementarity_score > 0.5:
        return DifficultyTier.EASY

    # MODERATE: Complete record in collision zone (resolvable with effort)
    if any_complete and collision_zone:
        return DifficultyTier.MODERATE

    # MODERATE: Combination works
    if not collision_zone and complementarity_score > 0.5:
        return DifficultyTier.MODERATE
    if collision_zone and complementarity_score > 0.6:
        return DifficultyTier.MODERATE
    if structural_resolvability:
        return DifficultyTier.MODERATE

    # EXTREME: Worst case
    if collision_severity == CollisionSeverity.CROSS_BRANCH:
        if complementarity_score < 0.3:
            return DifficultyTier.EXTREME
    if collision_zone and complementarity_score < 0.3:
        return DifficultyTier.EXTREME

    # HARD: Default for collision + low complementarity
    return DifficultyTier.HARD
```

### Key Constraints

- The `any_complete` check still exists but is no longer a universal short-circuit
- Collision zone soldiers with complete records are now MODERATE (not EASY)
- Collision zone soldiers with complete records AND structural resolution are still EASY

---

## Task 3: Independent Confounder Injection

**File:** `src/synthetic/vocabulary_injector.py`
**Method:** `inject_vocabulary()` (currently lines 82-117)

### Current Behavior

```python
# Confounders only fire inside clutter block (line 111)
clutter_rate = CLUTTER_RATES.get(clerk.archetype_id, 0.15)
if self.rng.random() < clutter_rate:
    clutter_term = self._sample_clutter(clerk)
    if clutter_term:
        result = self._append_term(result, clutter_term)
        injected["clutter"].append(clutter_term)

        if self.rng.random() < CONFOUNDER_RATE:    # <-- Nested inside clutter
            confounder = self._sample_confounder()
```

### Required Behavior

Give confounders their own independent gate. Raise effective rate from ~1% to ~5-8%.

```python
def inject_vocabulary(self, entry_text, clerk, situation):
    injected = {"situational": [], "clutter": [], "confounder": []}
    result = entry_text

    # Layer 1: Situational vocabulary (unchanged)
    situational_rate = SITUATIONAL_DENSITY.get(clerk.vocabulary_density, 0.35)
    if self.rng.random() < situational_rate:
        term = self._sample_situational(situation)
        if term:
            result = self._append_term(result, term)
            injected["situational"].append(term)

    # Layer 2: Clutter (unchanged, but confounders removed from here)
    clutter_rate = CLUTTER_RATES.get(clerk.archetype_id, 0.15)
    if self.rng.random() < clutter_rate:
        clutter_term = self._sample_clutter(clerk)
        if clutter_term:
            result = self._append_term(result, clutter_term)
            injected["clutter"].append(clutter_term)

    # Layer 3: Confounders (NOW INDEPENDENT)
    if self.rng.random() < CONFOUNDER_RATE:
        confounder = self._sample_confounder()
        if confounder:
            result = self._append_term(result, confounder)
            injected["confounder"].append(confounder)

    return result, injected
```

Also update the rate constant:

```python
CONFOUNDER_RATE = 0.08  # Now independent — effective rate ~8% of all records
```

### Key Constraints

- Confounders are terms that look like unit designators ("A", "C-4", "7") — they create realistic ambiguity
- The rate should be high enough to matter (~5-8%) but not so high that most records are confounded
- Confounders must NOT affect `levels_provided` or `extraction_signals` — they are noise, not signal

---

## Task 4: Verify and Implement Imperfection/OCR Simulation

**File:** `src/synthetic/renderer.py`

### Context

The `Imperfections` dataclass in `models.py` defines per-archetype rates:
- `typo_rate` (0.01-0.10)
- `abbreviation_inconsistency` (0.02-0.25)
- `trailing_off` (0.0-0.15)
- `mid_entry_corrections` (0.0-0.08)
- `incomplete_unit` (0.0-0.25)
- `column_bleed` (0.0-0.08)

### Task

1. **Verify:** Check whether the renderer currently applies these imperfections to rendered text. Search for where `clerk.imperfections` is referenced in the rendering pipeline.

2. **If NOT applied:** Implement an `_apply_imperfections()` method that corrupts rendered text based on the clerk's imperfection rates. This should run AFTER unit rendering and vocabulary injection but BEFORE the entry is finalized.

### Imperfection Types to Implement

| Imperfection | Effect | Example |
|-------------|--------|---------|
| `typo_rate` | Random character substitution, transposition, or omission | "Squadron" → "Sqaudron", "Kestrel" → "Kestrl" |
| `abbreviation_inconsistency` | Switch between abbreviation styles mid-entry | "Sq-3" in one place, "Squadron 3" in another within same entry |
| `trailing_off` | Truncate entry after a random point | "Martinez A/Sq-3/Fleet-" (incomplete) |
| `mid_entry_corrections` | Strikethrough-like corrections | "Martinez A/Sq-~~2~~3" or "Martinez A/Sq-2 3" |
| `incomplete_unit` | Drop one or more unit components entirely | "Martinez Kestrel" (missing squadron/wing/element) |
| `column_bleed` | Merge adjacent column text | "Martinez ASpec-3" (rank bleeds into name) |

### Key Constraints

- Imperfections are **rendering-layer only** — `levels_provided` and `extraction_signals` must reflect what was INTENDED, not what was corrupted
- `path_completeness` should reflect the intended path, not the corrupted one
- The imperfection is applied to `raw_text` only
- Each imperfection type fires independently at its archetype-specific rate
- Use the renderer's RNG for reproducibility

### Implementation Sketch

```python
def _apply_imperfections(self, text: str, clerk: Clerk) -> str:
    """Apply character-level imperfections to rendered text."""
    result = text
    imp = clerk.imperfections

    # Trailing off (check first — may truncate before other effects)
    if self.rng.random() < imp.trailing_off:
        cut_point = self.rng.randint(len(result) // 2, len(result) - 1)
        result = result[:cut_point]

    # Typos: random character operations
    if self.rng.random() < imp.typo_rate:
        result = self._inject_typo(result)

    # Incomplete unit: drop a unit component
    if self.rng.random() < imp.incomplete_unit:
        result = self._drop_unit_component(result)

    # Column bleed: merge adjacent fields
    if self.rng.random() < imp.column_bleed:
        result = self._apply_column_bleed(result)

    return result
```

Implement `_inject_typo()` with realistic OCR-like errors:
- Character transposition ("Sq" → "Qs")
- Character substitution (OCR-like: "l" → "1", "O" → "0", "rn" → "m")
- Character omission ("Squadron" → "Squadon")
- Character doubling ("Fleet" → "Fleeet")

---

## Acceptance Criteria

### Distribution Targets

After running the pipeline with these changes:

- [ ] `path_completeness` distribution has mean < 0.70 (was 0.71 at 1.0 alone)
- [ ] Fewer than 40% of records have `path_completeness >= 0.95` (was 71.3%)
- [ ] Difficulty distribution within ±10% of targets: ~50% easy, ~30% moderate, ~15% hard, ~5% extreme
- [ ] NOT 100% easy — this is the critical check

### Functional Checks

- [ ] `_select_levels()` consults `path_completeness_tendency` for all familiarity levels
- [ ] No empty level lists returned (minimum 1 level always)
- [ ] `_assign_tier()` does NOT short-circuit to EASY for collision-zone soldiers with complete records
- [ ] Confounders have independent injection gate at ~8% rate
- [ ] Imperfections applied to `raw_text` only (not to `levels_provided` or `extraction_signals`)
- [ ] At least some rendered entries contain typos/OCR-like errors

### Regression Checks

- [ ] All existing tests still pass
- [ ] Pipeline completes without error
- [ ] Output schema unchanged (same columns in raw.parquet, validation.parquet, sources.parquet)
- [ ] `levels_provided` still reflects intended levels (not corrupted text)

---

## Warnings and Pitfalls

### DO NOT change the style spec
The spec is correct. The implementation failed to honor `path_completeness_tendency`. Fix the code, not the spec.

### DO NOT make `path_completeness_tendency` deterministic
Use stochastic sampling within the retention range. A `high` tendency clerk should USUALLY include most levels but occasionally omit some. Don't make it a fixed threshold.

### DO NOT corrupt ground-truth fields
`levels_provided`, `extraction_signals`, and `path_completeness` reflect what the clerk INTENDED to write. Imperfections affect the rendered text only. Think of it as: the clerk wrote the right thing, but the document degraded.

### DO NOT over-correct
If the first run produces >80% hard/extreme, the retention ranges are too aggressive. The goal is a spread, not an inversion. Tune the `TENDENCY_RETENTION` mapping if needed.

### Minimum 1 level constraint
`_select_levels()` must ALWAYS return at least one level. The existing fallback (`if not include and levels: include = [levels[-1]]`) must remain.

### RNG consistency
Use the renderer's existing RNG (`self.rng`), not `random.random()` or a new RNG. This ensures reproducibility with `random_seed`.

---

## Test Strategy

### Unit Tests

1. **`_select_levels()` with tendency:** Test that `very_low` tendency produces fewer levels than `very_high`
2. **`_assign_tier()` collision logic:** Test that `any_complete + collision_zone` returns MODERATE, not EASY
3. **Confounder independence:** Test that confounders fire without clutter
4. **Imperfection application:** Test that `_apply_imperfections()` modifies text at expected rates

### Integration Test

Run pipeline with 100 soldiers, verify:
- Difficulty distribution is NOT 100% easy
- `path_completeness` has variance
- Some records contain confounders
- Some records contain typos/OCR errors

---

## References

- **Diagnosis extract:** `.project_history/extracts/raw/2026-01-27_opus_difficulty-saturation-diagnosis.md`
- **Codex investigation:** `.project_history/extracts/raw/2026-01-26_codex_difficulty-tier-all-easy-investigation.md`
- **Style spec:** `docs/components/synthetic_data_generation/synthetic_style_spec_v4.1.yaml`
- **ADR-006:** `docs/architecture/decisions/ADR-006_per-record-vs-per-soldier-difficulty.md`
- **Instruction 004:** `instructions/completed/004_synthetic-v4.1-terraform-combine.md`
