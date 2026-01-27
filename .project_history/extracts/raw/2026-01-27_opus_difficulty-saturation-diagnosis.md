# Session Extract: Difficulty Tier Saturation — Root Cause Diagnosis

**Date:** 2026-01-27
**Participants:** Human (Project Lead), Claude (Opus 4.5)
**Purpose:** Diagnose why v4.1 difficulty tiers collapsed to 100% easy and define the fix
**Duration:** ~30 minutes
**Outputs:** Instruction 006, SESSION_STATE update

---

## Session Summary

Following a Codex (GPT-5) investigation that identified the all-easy symptom and surface-level causes, this session performed a code-level root cause analysis of the difficulty saturation bug. We traced the problem through the renderer, clerk factory, difficulty computer, and vocabulary injector, identifying four specific code-level issues and defining a comprehensive fix instruction.

---

## Documents Reviewed

1. `.project_history/extracts/raw/2026-01-26_codex_difficulty-tier-all-easy-investigation.md` (Codex diagnosis)
2. `docs/architecture/decisions/ADR-007-synthetic-data-redesign.md`
3. `docs/architecture/decisions/ADR-006_per-record-vs-per-soldier-difficulty.md`
4. `docs/components/synthetic_data_generation/synthetic_style_spec_v4.1.yaml`
5. `instructions/completed/004_synthetic-v4.1-terraform-combine.md`
6. `src/synthetic/renderer.py` (full read)
7. `src/synthetic/vocabulary_injector.py` (full read)
8. `src/synthetic/clerk_factory.py` (partial read)
9. `src/synthetic/models.py` (searched for familiarity fields)

---

## Key Findings

### Finding 1: Familiarity Defaults Create Universal Full-Path Records

**Code path:** `renderer.py:186-187` → `_get_familiarity_level()`

```python
if clerk.familiarity_override == "ignore" or not clerk.familiarity_applies:
    return FamiliarityLevel.DIFFERENT_BRANCH
```

Combined with `clerk_factory.py:130`:
```python
familiarity_applies=data.get("familiarity_applies", False),
```

**Impact chain:**
1. `familiarity_applies` defaults to `False`
2. Any archetype without explicit `familiarity_applies: true` gets `DIFFERENT_BRANCH`
3. Four high-frequency formal archetypes (`sector_formal`, `sector_efficient`, `transport_shuttle`, `processing_intake`) have `familiarity_override: "ignore"` — always `DIFFERENT_BRANCH`
4. `DIFFERENT_BRANCH` in `_select_levels()` (line 247) means `include = list(levels)` — ALL levels
5. Every soldier appears in at least one source with a formal or cross-branch clerk
6. That record gets `path_completeness >= 0.95`
7. `difficulty_computer.py::_assign_tier()` short-circuits: `any_complete → EASY`

**Conclusion:** The architecture correctly models familiarity but the parameter defaults and tier assignment logic conspire to make every soldier trivially resolvable.

### Finding 2: `path_completeness_tendency` Is a Dead Field

Every clerk archetype in the style spec defines `path_completeness_tendency` (values: `very_low`, `low`, `medium`, `high`, `very_high`). This field is:
- Parsed and stored in `ClerkArchetype` (`clerk_factory.py:131`)
- Never read by `_select_levels()` or any other rendering method

**This was the intended fix mechanism.** The style spec anticipated that even different-branch clerks would stochastically omit levels based on their completeness tendency. The implementation never wired it.

### Finding 3: Confounders Are Gated Behind Clutter

In `vocabulary_injector.py:111`:
```python
if self.rng.random() < CONFOUNDER_RATE:  # 8% of clutter insertions
```

Confounders only fire when clutter has already fired (nested inside the clutter `if` block). Effective confounder rate = `clutter_rate * 0.08` ≈ 0.4-2.4% of records.

The confounders are specifically designed to look like unit designators ("A", "C-4", "7") — exactly the noise that would make disambiguation harder. Their near-absence means the synthetic data lacks realistic ambiguity from non-unit text.

### Finding 4: OCR/Imperfection Application Uncertain

The `Imperfections` dataclass exists with per-archetype rates (`typo_rate`, `abbreviation_inconsistency`, `trailing_off`, `mid_entry_corrections`, `incomplete_unit`, `column_bleed`). The style spec defines these rates. Whether the renderer actually applies character-level corruption (OCR-like errors, misspellings) to rendered text was not fully traced in this session — flagged for verification during the fix.

---

## Decisions Made

### Decision 1: Wire `path_completeness_tendency` into Level Selection

**Choice:** Modify `_select_levels()` to consult the clerk's `path_completeness_tendency` and stochastically drop levels, even for `DIFFERENT_BRANCH` familiarity.

**Rationale:** This is the mechanism the style spec already anticipated. It respects the archetype model (formal clerks still tend toward completeness, field clerks tend toward incompleteness) while preventing universal full-path records.

**Mapping:**
| Tendency | Max levels to include (fraction of branch depth) |
|----------|--------------------------------------------------|
| `very_low` | 20-40% |
| `low` | 30-50% |
| `medium` | 50-70% |
| `high` | 70-90% |
| `very_high` | 90-100% |

**Alternatives rejected:**
- *Remove formal archetypes entirely:* Unrealistic — formal clerks exist and should produce detailed records
- *Change familiarity_applies default to True:* Would affect all archetypes, including ones where ignoring familiarity is correct
- *Only fix difficulty_computer logic:* Treats symptom, not cause — the data itself should have varied completeness

### Decision 2: Soften `any_complete` Short-Circuit

**Choice:** Modify `_assign_tier()` so that `any_complete` alone only guarantees EASY if the soldier is NOT in a collision zone. In collision zones, require complementarity or structural resolution.

**Rationale:** A complete record in a collision zone is NOT easy — the record says "3rd Squadron" but doesn't say which Fleet. The current logic ignores collision context when a complete record exists.

**Alternative rejected:**
- *Remove any_complete check entirely:* Too aggressive — a genuinely complete non-collision record IS easy

### Decision 3: Give Confounders Independent Injection Gate

**Choice:** Move confounder injection out of the clutter `if` block. Give confounders their own probability gate (~5-8% of records).

**Rationale:** Confounders and clutter serve different purposes. Clutter is environmental noise (bed numbers, queue positions). Confounders are deliberately ambiguous terms that resemble unit designators. They should fire independently.

### Decision 4: Verify and Wire OCR/Imperfection Simulation

**Choice:** Instruction 006 includes a task to verify whether imperfections are applied to rendered text and, if not, implement character-level corruption (typos, OCR-like substitutions, truncation).

**Rationale:** Real historical records contain OCR artifacts, clerk misspellings, and handwriting misreads. The style spec defines per-archetype rates; they should produce actual text corruption.

---

## Implications for Implementation

### Files Requiring Changes

| File | Change | Severity |
|------|--------|----------|
| `src/synthetic/renderer.py` | Wire `path_completeness_tendency` into `_select_levels()` | **Critical** |
| `src/synthetic/difficulty_computer.py` | Soften `any_complete` short-circuit for collision zones | **Critical** |
| `src/synthetic/vocabulary_injector.py` | Independent confounder gate | **Important** |
| `src/synthetic/renderer.py` | Verify/implement imperfection application | **Important** |

### Expected Outcome After Fix

- Difficulty distribution should approach targets: ~50% easy, ~30% moderate, ~15% hard, ~5% extreme (±5%)
- `path_completeness` distribution should spread from current 71.3% at 1.0 to a realistic range
- Confounders should appear in ~5-8% of records
- Rendered text should include character-level corruption matching archetype rates

### Risks

- Over-correction could make too many soldiers HARD/EXTREME, requiring rebalancer tuning
- Level-dropping logic must not produce empty unit strings (need minimum 1 level)
- Imperfection application must not corrupt the ground-truth `levels_provided` tracking (corruption is rendering-only)

---

## Warnings and Pitfalls

1. **Do NOT change the style spec** — the spec is correct; the implementation failed to honor it
2. **`path_completeness_tendency` affects rendering, NOT difficulty computation** — difficulty is still computed post-generation from actual record content
3. **Imperfections are rendering-layer only** — `levels_provided` and `extraction_signals` must reflect what was *intended*, not what was *corrupted*
4. **The rebalancer (`difficulty_rebalancer.py`) is already non-mutating** — it identifies adjustments but never re-renders. This is a known pre-existing issue that is out of scope for this fix.

---

## References

- Codex investigation: `.project_history/extracts/raw/2026-01-26_codex_difficulty-tier-all-easy-investigation.md`
- Instruction 006: `instructions/active/006_fix-difficulty-saturation.md`
- ADR-006: `docs/architecture/decisions/ADR-006_per-record-vs-per-soldier-difficulty.md`
- ADR-007: `docs/architecture/decisions/ADR-007-synthetic-data-redesign.md`
- Style spec: `docs/components/synthetic_data_generation/synthetic_style_spec_v4.1.yaml`
