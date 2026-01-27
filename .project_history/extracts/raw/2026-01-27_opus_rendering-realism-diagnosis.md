# Rendering Realism Diagnosis: Synthetic Records Too Clean

**Date:** 2026-01-27
**Agent:** Opus 4.5 (session 2)
**Topic:** Why synthetic records look nothing like real clerk data, even at low quality tiers

---

## Key Finding

After instruction 006 fixed *which levels appear* in rendered records (path completeness), the remaining problem is *how those levels are rendered*. Even tier-3 ("field_worn") records are structurally pristine — full level-type labels, consistent delimiters, unabbreviated designator values. A tier-3 record reading `Spec-2 Alden, A.W. Sector Alpha, Colony Amber, District 8, Settlement Landfall CA` would be a *high tier-1* in actual historical data.

The rendering layer has no mechanism to degrade structural clarity independently of level count.

---

## Five Rendering Gaps Identified

### Gap 1: Level-Type Labels Always Present (Critical)

**Observation:** For all archetypes using labeled styles (LABELED_HIERARCHICAL, LABELED_FULL, LABELED_MICRO), every included level gets its type label. "Sector Alpha, Colony Amber, District 8, Settlement Landfall."

**Reality:** Real clerks rarely write level-type labels. "3/A/7" is far more common than "Squadron 3, Wing A, Element 7". Labels are primarily found on formal sector-level documents for unfamiliar units.

**Code location:** `renderer.py:359-368`, `_format_labeled()`. The `omit_level_names` flag is binary — either all labels or no labels. Only `field_minimal` sets it to `true`.

**Impact:** Labeled records are trivially parseable because each value is explicitly typed.

### Gap 2: Designator Values Never Abbreviated (Important)

**Observation:** Named designators render exactly as stored: "Alpha", "Amber", "Landfall", "Kestrel". Numbers and letters are inherently short, but names are always full.

**Reality:** Clerks abbreviate names they write dozens of times per day. "Amber" → "Amb", "Landfall" → "Lf" or "Lndfl". This abbreviation varies by clerk and even by entry.

**Code location:** `renderer.py:327-357`, `_format_unit()`. Values pass through from `state.post_levels` to the format functions without any abbreviation step.

**Impact:** Named designators are unambiguous, eliminating a major source of real-world parsing difficulty.

### Gap 3: Delimiter Locked Per Clerk (Moderate)

**Observation:** Each clerk has a single `separator` on their UnitFormat (", " or "/" or "-" or " "). Every level boundary in every entry uses the same delimiter.

**Reality:** Real records frequently mix delimiters within a single entry: "Alpha, Amber/8 Landfall". Inconsistency increases with clerk fatigue, stress, or low formality.

**Code location:** `models.py:105` (`separator` field), used uniformly in all format methods.

**Impact:** Uniform delimiters make it trivial to tokenize records into level components.

### Gap 4: No Per-Level Label Graduation (Critical)

**Observation:** `omit_level_names` is a boolean. Either every level gets a label or none do. There's no middle ground where some levels are labeled and others aren't.

**Reality:** A clerk might write "Sector Alpha, Amber, 8, Landfall" — labeling the unfamiliar top level but omitting labels for contextually obvious lower levels.

**Code location:** `models.py:111` (`omit_level_names: bool`), `renderer.py:363` (binary check).

**Impact:** Creates a bimodal distribution — fully labeled or fully bare — instead of the realistic gradient.

### Gap 5: Familiarity Doesn't Affect Label Presence (Important)

**Observation:** Familiarity controls *which levels appear* (via `_select_levels()`), but NOT *whether included levels have type labels*. A SAME_L2 clerk who includes "squadron" and "element" still writes "Squadron 3, Element 7" rather than "3, 7".

**Reality:** Familiarity affects notation style as much as content. A familiar clerk omits labels because context is shared; an unfamiliar clerk includes labels because the reader needs them.

**Code location:** `renderer.py:177-191` (`render_unit` determines familiarity but only passes it to `_select_levels`, not to formatting).

**Impact:** Even familiar-context records look formally structured.

---

## Decisions Made

### Decision 1: Per-Level Stochastic Label Omission

**Choice:** Add `label_omission_rate` (float 0.0-1.0) to UnitFormat. Each level independently drops its type label with probability = base_rate + echelon_bonus + familiarity_boost.

**Alternatives considered:**
- **More archetypes with `omit_level_names: true`:** Would increase the fraction of label-free records but wouldn't create the graduated middle ground. Rejected because it preserves the bimodal problem.
- **New format styles:** Could add "LABELED_PARTIAL" style. Rejected as over-engineering — the stochastic approach is simpler and more flexible.
- **Per-level label config in the style spec:** Could specify which levels get labels per archetype. Rejected because it's deterministic — the same clerk would always produce the same pattern.

**Rationale:** Stochastic per-level omission creates natural variation. The echelon bonus means lower levels (settlement, element, crew) lose labels before higher levels (sector, fleet, colony), matching real behavior. The familiarity boost means the same clerk produces different label density for familiar vs. unfamiliar units.

### Decision 2: Designator Value Abbreviation

**Choice:** Add `value_abbreviation_rate` (float 0.0-1.0) to UnitFormat. Named designators are stochastically abbreviated using truncation or consonant skeleton.

**Alternatives considered:**
- **Fixed abbreviation lookup table:** Map each name to its canonical abbreviation ("Amber" → "Amb"). Rejected because real abbreviation is inconsistent — the same clerk might write "Amb", "Ambr", or "Am" on different entries.
- **Character-level corruption only (via imperfections):** The existing `_apply_imperfections()` does character-level damage but doesn't structurally abbreviate. Rejected because abbreviation is intentional behavior, not degradation.

**Rationale:** Stochastic abbreviation with variable length (2-4 chars) and two styles (truncation vs. consonant skeleton) produces realistic variety. Greek letters get special handling (less aggressive) since they're already short sector designators.

### Decision 3: Within-Entry Delimiter Mixing

**Choice:** Low-consistency clerks stochastically swap delimiters at level boundaries, keyed to `1.0 - format_lock`.

**Alternatives considered:**
- **Per-clerk random separator assignment:** Give each clerk a random separator. Rejected because it doesn't create *inconsistency* — just variety across clerks.
- **No delimiter mixing:** Focus only on labels and abbreviation. Considered but rejected because uniform delimiters are a strong parsability signal that real data lacks.

**Rationale:** Tying mixing probability to `format_lock` reuses existing consistency infrastructure. High-formality clerks (format_lock ≥ 0.95) almost never mix; stressed field clerks (format_lock ≤ 0.70) frequently do.

### Decision 4: Familiarity-Driven Label Omission Boost

**Choice:** Familiarity level adds 0.0-0.70 to the effective label omission rate, additive with the base rate.

**Boost values:**
- SAME_L3: +0.70 (very familiar — almost never labels)
- SAME_L2: +0.45 (familiar — often drops labels)
- SAME_BRANCH: +0.20 (same branch — sometimes drops)
- DIFFERENT_BRANCH: +0.00 (unfamiliar — no extra omission)

**Alternatives considered:**
- **Familiarity controls style selection (e.g., switch to MINIMAL for SAME_L3):** Would override the clerk's locked format. Rejected because clerks have persistent habits — a formal clerk writing about their own unit still uses their labeled style, just with fewer labels.
- **Only affect level count, not label presence:** Already done by instruction 006. Insufficient alone.

**Rationale:** Additive boost preserves the clerk's base personality while allowing familiarity to increase label dropping. The cap at 1.0 prevents over-driving. Clerks with `familiarity_override: "ignore"` get DIFFERENT_BRANCH from `_get_familiarity_level()`, so they receive 0.0 boost — correct for formal clerks who always use full notation.

---

## Implications for Implementation

1. **Two new fields on UnitFormat:** `label_omission_rate` and `value_abbreviation_rate` must propagate through models.py → clerk_factory.py → renderer.py. Default 0.0 preserves backward compatibility.

2. **Familiarity must flow to format methods:** Currently `render_unit()` determines familiarity and passes it to `_select_levels()` only. It must also pass through `_format_unit()` → `_format_labeled()`.

3. **Extraction signals are correctly affected:** `_extract_structural_signals()` searches rendered text for branch-unique terms like "Squadron". If label omission or abbreviation removes these terms, the signal correctly disappears. This makes records harder to disambiguate structurally — which is the point.

4. **`levels_provided` and `path_completeness` are NOT affected:** These reflect which hierarchy levels the clerk intended to include, not how they rendered them. A record with "3" (dropped label "Squadron") still has "squadron" in `levels_provided`.

5. **Missing archetypes need definition:** `colonial_district` and `defense_operations` are referenced in quality tier biases but not fully defined in the style spec. Instruction 007 includes stubs.

---

## Warnings and Pitfalls

1. **Calibration risk:** The `label_omission_rate` and `value_abbreviation_rate` values in the instruction are estimates based on code analysis, not empirical tuning. The first pipeline run after implementation needs visual inspection. If output is still too clean, rates need to increase. If output becomes unreadable noise, rates are too high.

2. **Abbreviation consistency within clerk:** The instruction specifies stochastic abbreviation per-entry, but a real clerk might consistently write "Amb" for "Amber". This is a fidelity detail that can be addressed later if needed (by caching abbreviation choices per clerk per value).

3. **Interaction with imperfections:** Value abbreviation happens in `_format_unit()` *before* `_apply_imperfections()`. A value abbreviated to "Lndf" might then get a typo applied, producing "Lnf" or "Lndf1". This double-degradation is realistic but could be excessive for some records. Monitor.

4. **The echelon bonus in label omission assumes a consistent part ordering.** If `orientation: "child_over_parent"` reverses the display order, the position index in `_format_labeled()` might not correspond to echelon rank. The implementation should use the level's position in the *full hierarchy*, not its position in the `parts` list.

5. **Delimiter mixing must not break `_drop_unit_component()` in imperfections.** That method splits on known separators to drop components. If mixed delimiters introduce separators it doesn't expect, the drop logic might fail silently. Verify these interact correctly.
