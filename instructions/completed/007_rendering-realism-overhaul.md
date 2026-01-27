# Instruction 007: Rendering Realism Overhaul

**Created:** 2026-01-27
**Status:** Active
**Depends on:** Instruction 006 (difficulty saturation fix, completed)
**Blocks:** Resolver strategy rebuild, evaluation pipeline
**Model:** Sonnet, thinking on

---

## Objective

Close the realism gap between synthetic rendered records and actual clerk data. Currently, even the lowest-quality synthetic records are structurally pristine: full level-type labels, consistent delimiters, clean designator values. A tier-3 record reads like a high tier-1. Five rendering-layer changes are required across two files (`renderer.py`, `models.py`) plus style spec updates.

After the fix, a tier-3 record like:

```
Spec-2 Alden, A.W. Sector Alpha, Colony Amber, District 8, Settlement Landfall CA
```

should instead look something like:

```
Alden AW Amb/8/Landfall
```

or:

```
Spec-2 Alden, A.W. Alpha, Amber, Dist 8, Landfall CA
```

or at the extreme end:

```
Alden Landfall 8
```

---

## Context and Rationale

### The Problem

Instruction 006 fixed the difficulty tier *computation* — level dropping, tendency wiring, difficulty assignment. But the *rendering layer* still produces structurally clean output regardless of quality tier or clerk archetype. The five specific gaps:

| # | Gap | Impact | Severity |
|---|-----|--------|----------|
| 1 | Level-type labels always present for labeled styles | "Sector Alpha, Colony Amber" instead of "Alpha, Amber" | Critical |
| 2 | Designator values never abbreviated | "Landfall" never becomes "Lndfl" or "Lf" | Important |
| 3 | Delimiter is locked per clerk, never varies within entry | Uniform "/, /, /" instead of mixed "/ , " | Moderate |
| 4 | `omit_level_names` is binary (all-or-nothing) | No graduated label omission per level | Critical |
| 5 | No "bare designator" rendering for familiar contexts | Familiar clerk still writes "Settlement Landfall" not just "Landfall" | Important |

### What Makes Real Records Hard to Parse

Real clerk handwriting has these properties that our synthetic data lacks:

1. **Level-type labels are the exception, not the rule.** A clerk writing "3/A/7" is far more common than "Squadron 3, Wing A, Element 7". Labels appear primarily on formal/unfamiliar records.

2. **Designator values are abbreviated by context.** "Amber" becomes "Amb", "Landfall" becomes "Lf" or "Lndfl". Clerks don't spell out names they write dozens of times per day.

3. **Delimiters are inconsistent within entries.** A single record might mix commas, slashes, spaces, and dashes: "Alpha, Amb/8 Landfall".

4. **Name/unit boundaries are ambiguous.** "Alden AW Landfall 8 Amb CA" — where does the name end? Is "AW" a middle initial pair or a unit abbreviation?

5. **Familiar context = radical omission.** A clerk in Colony Amber doesn't write "Colony Amber" — they write nothing, or at most "Amb".

### Reference Documents

- **Style spec:** `docs/components/synthetic_data_generation/synthetic_style_spec_v4.1.yaml`
- **Renderer:** `src/synthetic/renderer.py`
- **Models:** `src/synthetic/models.py`
- **Clerk factory:** `src/synthetic/clerk_factory.py`
- **Instruction 006:** `instructions/active/006_fix-difficulty-saturation.md`

---

## Scope

### In Scope

| File | Change |
|------|--------|
| `src/synthetic/models.py` | Add `label_omission_rate` to `UnitFormat`; add `value_abbreviation_rate` to `UnitFormat` |
| `src/synthetic/renderer.py` | Implement per-level stochastic label omission in `_format_labeled()` |
| `src/synthetic/renderer.py` | Implement designator value abbreviation in `_format_unit()` |
| `src/synthetic/renderer.py` | Implement within-entry delimiter mixing |
| `src/synthetic/renderer.py` | Wire familiarity into label omission (more familiar = more labels dropped) |
| `src/synthetic/clerk_factory.py` | Parse new UnitFormat fields from style spec |
| `docs/components/synthetic_data_generation/synthetic_style_spec_v4.1.yaml` | Add `label_omission_rate` and `value_abbreviation_rate` to each archetype |

### Out of Scope

- Difficulty computation changes (done in 006)
- Path completeness tendency changes (done in 006)
- Imperfection/OCR simulation changes (done in 006)
- New clerk archetypes (existing set is sufficient)
- Vocabulary injection changes
- Config file changes (hierarchy, vocabulary, themes)

---

## Task 1: Per-Level Stochastic Label Omission

**Files:** `src/synthetic/models.py`, `src/synthetic/renderer.py`, `src/synthetic/clerk_factory.py`

### Current Behavior

```python
# renderer.py:359-368
def _format_labeled(self, parts, clerk, micro=False):
    formatted = []
    for level, value in parts:
        if clerk.unit_format.omit_level_names:   # <-- Binary: all or nothing
            formatted.append(value)
            continue
        label = self._level_label(level, clerk, micro)
        formatted.append(f"{label} {value}".strip())
    return clerk.unit_format.separator.join(formatted)
```

When `omit_level_names` is `False` (the vast majority of archetypes), EVERY level gets its type label: "Sector Alpha, Colony Amber, District 8, Settlement Landfall". This is the single biggest source of unrealistic cleanliness.

### Required Behavior

Each level independently has a chance of dropping its type label, controlled by `label_omission_rate` on the UnitFormat. The probability of omission increases for lower echelons (clerks are more likely to label unfamiliar higher echelons like "Sector" than obvious lower ones like "Settlement").

### Implementation

**Step 1: Add field to UnitFormat** (`models.py:101-114`)

```python
@dataclass
class UnitFormat:
    """How a clerk formats unit hierarchy."""
    style: UnitFormatStyle
    separator: str = ", "
    orientation: str = "child_over_parent"
    include_sector: bool = True
    include_branch: bool = False
    include_level2: bool = True
    include_lowest_levels: bool = True
    omit_level_names: bool = False
    label_style: str = "abbreviated"
    branch_suffix: bool = False
    phonetic_letters: bool = False
    label_omission_rate: float = 0.0       # NEW: per-level label drop probability
    value_abbreviation_rate: float = 0.0   # NEW: designator value abbreviation probability
```

**Step 2: Parse in clerk_factory.py** (`clerk_factory.py:83-96`)

Add to the `unit_data` parsing block:

```python
unit_format = UnitFormat(
    # ... existing fields ...
    label_omission_rate=unit_data.get("label_omission_rate", 0.0),
    value_abbreviation_rate=unit_data.get("value_abbreviation_rate", 0.0),
)
```

Also copy these fields through in `_vary_unit_format()` (lines 206-220):

```python
def _vary_unit_format(self, base: UnitFormat) -> UnitFormat:
    return UnitFormat(
        # ... existing fields ...
        label_omission_rate=self._vary_rate(base.label_omission_rate, 0.10),
        value_abbreviation_rate=self._vary_rate(base.value_abbreviation_rate, 0.10),
    )
```

**Step 3: Implement in renderer.py** (`_format_labeled`, lines 359-368)

```python
def _format_labeled(self, parts, clerk, micro=False):
    formatted = []
    omit_all = clerk.unit_format.omit_level_names
    base_omission = clerk.unit_format.label_omission_rate

    for i, (level, value) in enumerate(parts):
        if omit_all:
            formatted.append(value)
            continue

        # Per-level omission: higher index = lower echelon = more likely to drop label
        # Echelon weight: lowest levels get +0.2 bonus to omission rate
        echelon_bonus = 0.0
        if len(parts) > 1:
            position_ratio = i / (len(parts) - 1)  # 0.0 for highest, 1.0 for lowest
            echelon_bonus = position_ratio * 0.2

        effective_rate = min(1.0, base_omission + echelon_bonus)

        if effective_rate > 0 and self.rng.random() < effective_rate:
            formatted.append(value)
        else:
            label = self._level_label(level, clerk, micro)
            formatted.append(f"{label} {value}".strip())

    return clerk.unit_format.separator.join(formatted)
```

**Step 4: Set per-archetype values in style spec**

Update `synthetic_style_spec_v4.1.yaml` clerk archetypes:

| Archetype | `label_omission_rate` | Rationale |
|-----------|-----------------------|-----------|
| `sector_formal` | `0.05` | Very formal, almost never omits labels |
| `sector_efficient` | `0.15` | N/A — uses slash_positional (no labels), but set for consistency |
| `fleet_methodical` | `0.25` | Micro labels, sometimes drops them entirely |
| `fleet_rushed` | `0.0` | N/A — uses runon_compact (no labels) |
| `field_exhausted` | `0.0` | N/A — uses phonetic_informal (no labels) |
| `field_medevac` | `0.0` | N/A — uses minimal (no labels) |
| `field_minimal` | `0.0` | Already has `omit_level_names: true` |
| `transport_shuttle` | `0.10` | N/A — uses slash_positional (no labels), but set for consistency |
| `processing_intake` | `0.10` | Very formal but occasionally drops obvious labels |
| `defense_squadron` | `0.30` | Context-aware, drops labels for own-branch levels |
| `resource_facility` | `0.30` | Same |
| `expeditionary_field` | `0.0` | N/A — uses minimal or similar |
| `colonial_district` | `0.35` | Familiar context, frequently drops labels |

Note: archetypes using non-labeled styles (slash_positional, runon_compact, minimal, phonetic_informal) already produce label-free output. The `label_omission_rate` only affects `_format_labeled()`, used by LABELED_HIERARCHICAL, LABELED_FULL, and LABELED_MICRO styles.

### Key Constraints

- `omit_level_names: true` still overrides everything (full omission)
- `label_omission_rate: 0.0` preserves current behavior (no omission)
- Higher echelons (sector, fleet/colony) are less likely to lose labels than lower echelons
- The RNG must be the renderer's `self.rng` for reproducibility
- `levels_provided` is NOT affected — it reflects which levels were included, not whether they had labels

---

## Task 2: Designator Value Abbreviation

**File:** `src/synthetic/renderer.py`

### Current Behavior

Designator values are always rendered exactly as stored: "Alpha", "Amber", "Landfall", "Kestrel". Real clerks abbreviate frequently-used names.

### Required Behavior

Based on `value_abbreviation_rate` on the UnitFormat, stochastically abbreviate named designators (not numbers or single letters). Abbreviation takes the first 2-4 characters of the name.

### Implementation

Add an abbreviation method to the Renderer class:

```python
GREEK_LETTERS = {"Alpha", "Beta", "Gamma", "Delta", "Epsilon", "Zeta",
                 "Eta", "Theta", "Iota", "Kappa", "Lambda", "Omega"}

def _abbreviate_value(self, value: str) -> str:
    """Abbreviate a named designator value."""
    # Don't abbreviate numbers or single characters
    if len(value) <= 2 or value.isdigit():
        return value

    # Greek letters (sector designators): abbreviate less aggressively
    if value in GREEK_LETTERS:
        if self.rng.random() < 0.5:
            return value[:2]  # "Alpha" -> "Al"
        return value  # Keep full

    # Named designators: truncate to 2-4 chars
    if len(value) <= 4:
        return value[:2]

    # Pick abbreviation length
    abbrev_len = self.rng.choice([2, 3, 4])

    # Two styles: simple truncation or consonant skeleton
    if self.rng.random() < 0.5:
        # Simple truncation: "Landfall" -> "Land" or "Lan"
        return value[:abbrev_len]
    else:
        # Consonant skeleton: "Landfall" -> "Lndf", "Kestrel" -> "Kstrl"
        skeleton = value[0] + "".join(c for c in value[1:] if c.lower() not in "aeiou")
        if len(skeleton) >= 2:
            return skeleton[:abbrev_len + 1]
        return value[:abbrev_len]
```

Wire this into `_format_unit()` after parts are built but before style dispatch (around line 329-332):

```python
def _format_unit(self, state, levels, clerk):
    parts = [(lvl, state.post_levels.get(lvl, "")) for lvl in levels]

    if clerk.unit_format.phonetic_letters:
        parts = [(lvl, self._phoneticize(value)) for lvl, value in parts]

    # NEW: Stochastic value abbreviation
    if clerk.unit_format.value_abbreviation_rate > 0:
        abbreviated_parts = []
        for lvl, value in parts:
            if self.rng.random() < clerk.unit_format.value_abbreviation_rate:
                abbreviated_parts.append((lvl, self._abbreviate_value(value)))
            else:
                abbreviated_parts.append((lvl, value))
        parts = abbreviated_parts

    # ... rest of existing style dispatch
```

**Set per-archetype values in style spec:**

| Archetype | `value_abbreviation_rate` | Rationale |
|-----------|---------------------------|-----------|
| `sector_formal` | `0.0` | Formal, spells everything out |
| `sector_efficient` | `0.15` | Efficient but systematic |
| `fleet_methodical` | `0.20` | Careful but uses shorthand for known names |
| `fleet_rushed` | `0.50` | Abbreviates aggressively |
| `field_exhausted` | `0.60` | Writes what they hear, shortened |
| `field_medevac` | `0.40` | Abbreviated for speed |
| `field_minimal` | `0.70` | Maximum abbreviation |
| `transport_shuttle` | `0.10` | Systematic, minimal abbreviation |
| `processing_intake` | `0.0` | Full names always |
| `defense_squadron` | `0.30` | Context-dependent |
| `resource_facility` | `0.30` | Context-dependent |
| `expeditionary_field` | `0.55` | Field conditions |
| `colonial_district` | `0.35` | District clerk, abbreviates colony names |

### Key Constraints

- Numbers and single letters are NEVER abbreviated (they're already minimal)
- Greek letters (sector designators) are rarely abbreviated and only to 2 chars
- Abbreviation affects `raw_text` only — `levels_provided` and `extraction_signals` reflect the intended value
- The abbreviation is applied BEFORE format style dispatch so it affects all styles
- `path_completeness` is NOT affected (it measures level count, not value quality)
- Use the renderer's `self.rng` for reproducibility
- Never produce an empty string — fall back to original value if abbreviation would be empty

### Important: extraction_signals must use original values

The `_extract_structural_signals()` method searches for branch-unique terms in the unit string. After abbreviation, "Squadron" might not appear in the rendered text even though the level was included. This is **correct and intentional** — abbreviated records genuinely have fewer structural signals. However, `levels_provided` must still list the full level name (e.g., "squadron") because the level was *included* even though its label was dropped or abbreviated.

---

## Task 3: Within-Entry Delimiter Mixing

**File:** `src/synthetic/renderer.py`

### Current Behavior

Each clerk has a single locked `separator` (e.g., `", "` or `"/"` or `"-"`). Every level boundary in every entry uses this same separator. Result: perfectly uniform delimiters.

### Required Behavior

Low-consistency clerks should occasionally mix delimiters within a single entry. A clerk whose primary separator is `", "` might produce: "Sector Alpha, Amber/8 Landfall" — mixing comma, slash, and space.

### Implementation

Add a post-formatting step that introduces delimiter mixing based on the clerk's consistency rates. This should fire AFTER the unit string is formatted but BEFORE it's combined with name/rank.

```python
ALTERNATIVE_SEPARATORS = {
    ", ": [" ", "/", "/ ", " - "],
    "/": [" ", ", ", "-"],
    "-": [" ", "/"],
    " ": ["/", ", ", "-"],
}

def _mix_delimiters(self, unit_text: str, clerk: Clerk) -> str:
    """Stochastically replace some delimiters in the unit string."""
    # Only mix for low-consistency clerks
    mix_rate = 1.0 - clerk.consistency.format_lock  # e.g., 0.15 for format_lock=0.85
    if mix_rate <= 0 or self.rng.random() > mix_rate:
        return unit_text

    sep = clerk.unit_format.separator
    alternatives = ALTERNATIVE_SEPARATORS.get(sep, [])
    if not alternatives:
        return unit_text

    # Split on the primary separator and rejoin with mixed separators
    parts = unit_text.split(sep)
    if len(parts) <= 1:
        return unit_text

    result_parts = [parts[0]]
    for part in parts[1:]:
        if self.rng.random() < 0.4:  # 40% chance each boundary gets a different delimiter
            new_sep = self.rng.choice(alternatives)
            result_parts.append(new_sep + part.lstrip())
        else:
            result_parts.append(sep + part)

    return "".join(result_parts)
```

Wire into `_format_unit()` after the style dispatch and before branch suffix (around line 349):

```python
def _format_unit(self, state, levels, clerk):
    # ... existing parts building and style dispatch ...

    unit_text = ...  # result from style dispatch

    # NEW: delimiter mixing
    unit_text = self._mix_delimiters(unit_text, clerk)

    # existing branch suffix logic
    if clerk.unit_format.include_branch:
        branch_abbrev = self.hierarchy.get_branch_abbreviation(state.branch)
        unit_text = f"{unit_text} {branch_abbrev}".strip()
    # ...
```

### Key Constraints

- High-consistency clerks (format_lock >= 0.95) should almost never mix delimiters
- Low-consistency clerks (format_lock <= 0.70) should frequently mix
- The mixing is per-entry, not per-clerk — the same clerk might produce clean entries and mixed entries
- This does NOT affect `levels_provided` or `path_completeness`
- Use `self.rng` for reproducibility

---

## Task 4: Familiarity-Driven Label Omission Boost

**File:** `src/synthetic/renderer.py`

### Current Behavior

Familiarity controls *which levels are included* (`_select_levels()`), but NOT *whether included levels have type labels*. A SAME_L2 clerk who includes "squadron" and "element" still writes "Squadron 3, Element 7" rather than "3, 7" or "3/7".

### Required Behavior

Familiarity should boost the effective `label_omission_rate`. Higher familiarity = more label omission. This is additive with the base rate from the clerk archetype.

### Implementation

Add a familiarity boost mapping:

```python
FAMILIARITY_LABEL_OMISSION_BOOST = {
    FamiliarityLevel.SAME_L3: 0.70,        # Very familiar — almost never labels
    FamiliarityLevel.SAME_L2: 0.45,        # Familiar — often drops labels
    FamiliarityLevel.SAME_BRANCH: 0.20,    # Same branch — sometimes drops labels
    FamiliarityLevel.DIFFERENT_BRANCH: 0.0, # Unfamiliar — no extra omission
}
```

The `render_unit()` method already knows the familiarity level. Pass it through to `_format_unit()` and then to `_format_labeled()`:

```python
def render_unit(self, state, source, clerk):
    levels = self.hierarchy.get_branch_levels(state.branch)
    familiarity = self._get_familiarity_level(source, state, clerk)
    include_levels = self._select_levels(levels, familiarity, clerk)
    levels_provided = [lvl for lvl in levels if lvl in include_levels]

    unit_text = self._format_unit(
        state,
        levels_provided,
        clerk,
        familiarity,        # NEW parameter
    )
    return unit_text, levels_provided
```

Update `_format_unit()` signature and pass familiarity to `_format_labeled()`:

```python
def _format_unit(self, state, levels, clerk, familiarity=FamiliarityLevel.DIFFERENT_BRANCH):
    # ... existing parts building ...

    style = clerk.unit_format.style
    if style in (UnitFormatStyle.LABELED_HIERARCHICAL, UnitFormatStyle.LABELED_FULL):
        unit_text = self._format_labeled(parts, clerk, familiarity=familiarity)
    elif style == UnitFormatStyle.LABELED_MICRO:
        unit_text = self._format_labeled(parts, clerk, micro=True, familiarity=familiarity)
    # ... other styles unchanged (they don't use labels) ...
```

Update `_format_labeled()` to incorporate familiarity boost:

```python
def _format_labeled(self, parts, clerk, micro=False,
                    familiarity=FamiliarityLevel.DIFFERENT_BRANCH):
    formatted = []
    omit_all = clerk.unit_format.omit_level_names
    base_omission = clerk.unit_format.label_omission_rate
    familiarity_boost = FAMILIARITY_LABEL_OMISSION_BOOST.get(familiarity, 0.0)

    for i, (level, value) in enumerate(parts):
        if omit_all:
            formatted.append(value)
            continue

        echelon_bonus = 0.0
        if len(parts) > 1:
            position_ratio = i / (len(parts) - 1)
            echelon_bonus = position_ratio * 0.2

        effective_rate = min(1.0, base_omission + echelon_bonus + familiarity_boost)

        if effective_rate > 0 and self.rng.random() < effective_rate:
            formatted.append(value)
        else:
            label = self._level_label(level, clerk, micro)
            formatted.append(f"{label} {value}".strip())

    return clerk.unit_format.separator.join(formatted)
```

### Key Constraints

- `familiarity_override: "ignore"` clerks still get DIFFERENT_BRANCH familiarity from `_get_familiarity_level()`, so the boost is 0.0 — correct behavior for formal clerks
- The familiarity boost is additive with the base `label_omission_rate`
- The total effective rate is capped at 1.0
- This only affects labeled styles (LABELED_HIERARCHICAL, LABELED_FULL, LABELED_MICRO)

---

## Task 5: Style Spec Archetype Updates

**File:** `docs/components/synthetic_data_generation/synthetic_style_spec_v4.1.yaml`

### Required Changes

Add `label_omission_rate` and `value_abbreviation_rate` to each archetype's `unit_format` block. Only archetypes using labeled styles need `label_omission_rate`; all archetypes can benefit from `value_abbreviation_rate`.

**For each fully-defined archetype**, add to the `unit_format:` block:

```yaml
sector_formal:
    unit_format:
      # ... existing fields ...
      label_omission_rate: 0.05
      value_abbreviation_rate: 0.0

sector_efficient:
    unit_format:
      # ... existing fields ...
      label_omission_rate: 0.0    # Uses slash_positional, no labels to omit
      value_abbreviation_rate: 0.15

fleet_rushed:
    unit_format:
      # ... existing fields ...
      label_omission_rate: 0.0    # Uses runon_compact, no labels
      value_abbreviation_rate: 0.50

fleet_methodical:
    unit_format:
      # ... existing fields ...
      label_omission_rate: 0.25
      value_abbreviation_rate: 0.20

field_exhausted:
    unit_format:
      # ... existing fields ...
      label_omission_rate: 0.0    # Uses phonetic_informal, no labels
      value_abbreviation_rate: 0.60

field_medevac:
    unit_format:
      # ... existing fields ...
      label_omission_rate: 0.0    # Uses minimal
      value_abbreviation_rate: 0.40

field_minimal:
    unit_format:
      # ... existing fields ...
      label_omission_rate: 0.0    # Already has omit_level_names: true
      value_abbreviation_rate: 0.70

transport_shuttle:
    unit_format:
      # ... existing fields ...
      label_omission_rate: 0.0    # Uses slash_positional
      value_abbreviation_rate: 0.10

processing_intake:
    unit_format:
      # ... existing fields ...
      label_omission_rate: 0.10
      value_abbreviation_rate: 0.0
```

For the abbreviated branch-specific archetypes (`defense_squadron`, `expeditionary_field`, `resource_facility`), add these fields to their `unit_format` block. If they don't have a full `unit_format` definition yet, provide reasonable defaults based on their `path_completeness_tendency`:

| Archetype | `label_omission_rate` | `value_abbreviation_rate` |
|-----------|-----------------------|---------------------------|
| `defense_squadron` | `0.30` | `0.30` |
| `expeditionary_field` | `0.0` (uses minimal/similar) | `0.55` |
| `resource_facility` | `0.30` | `0.30` |

### Missing Archetype: `colonial_district`

The style spec references `colonial_district` in the quality tier biases (tier 2) but does not define it as a full archetype. If it doesn't already exist as a fully-defined archetype, add it under `clerk_archetypes:`:

```yaml
colonial_district:
    description: |
      District-level clerk in Colonial Administration. Processes settlement
      records daily. Familiar with local settlements, abbreviates heavily.
    context_level: "level3"
    applicable_branches: ["colonial_administration"]

    name_format:
      template: "{LAST}, {FI}."

    rank_format:
      style: "prefix"
      form: "caps_abbrev"

    unit_format:
      style: "labeled_hierarchical"
      separator: ", "
      include_sector: false
      label_style: "abbreviated"
      label_omission_rate: 0.35
      value_abbreviation_rate: 0.35

    vocabulary_density: "medium"
    familiarity_applies: true

    path_completeness_tendency: "medium"
    structural_signals_tendency: "medium"

    consistency:
      format_lock: 0.85
      minor_drift: 0.12
      major_variation: 0.03

    imperfections:
      typo_rate: 0.03
      abbreviation_inconsistency: 0.08
```

Similarly check for `defense_operations` (referenced in tier 3 bias). If missing, add a similar stub:

```yaml
defense_operations:
    description: |
      Operations-level clerk in Defense Command. Tracks patrol and
      intercept assignments. Uses compact notation, moderate abbreviation.
    context_level: "level2"
    applicable_branches: ["defense_command"]

    name_format:
      template: "{LAST} {FI}"

    rank_format:
      style: "suffix"
      form: "caps_abbrev"

    unit_format:
      style: "slash_compact"
      separator: "/"
      orientation: "child_over_parent"
      include_sector: false
      label_omission_rate: 0.0    # Uses slash style, no labels
      value_abbreviation_rate: 0.40

    vocabulary_density: "medium"
    vocabulary_bias: ["defense_ops_code"]
    familiarity_applies: true

    path_completeness_tendency: "low"
    structural_signals_tendency: "medium"

    consistency:
      format_lock: 0.80
      minor_drift: 0.15
      major_variation: 0.05

    imperfections:
      typo_rate: 0.04
      abbreviation_inconsistency: 0.10
      trailing_off: 0.03
```

---

## Acceptance Criteria

### Rendering Realism

After running the pipeline with these changes:

- [ ] Labeled-style records frequently omit some level-type labels (at least 30% of labeled entries should have at least one label-free level)
- [ ] Named designators (non-number, non-letter values) are abbreviated in at least 20% of records
- [ ] At least 10% of entries from low-consistency clerks have mixed delimiters
- [ ] SAME_L3 familiarity records with labeled styles produce mostly label-free output
- [ ] Tier-3 records are visually distinguishable from tier-1 records (not just by level count)

### Functional Checks

- [ ] `_format_labeled()` checks `label_omission_rate` per level
- [ ] `_abbreviate_value()` never abbreviates numbers or single letters
- [ ] `_abbreviate_value()` never returns an empty string
- [ ] `_mix_delimiters()` respects `format_lock` — high-consistency clerks don't mix
- [ ] Familiarity boost is additive with base omission rate, capped at 1.0
- [ ] `levels_provided` still reflects which levels were included (unaffected by label omission or value abbreviation)
- [ ] `path_completeness` unchanged (still = len(levels_provided) / branch_depth)
- [ ] `extraction_signals` computed from the rendered text (abbreviation reduces signals — this is correct)

### Regression Checks

- [ ] All existing tests in `tests/synthetic/test_difficulty_saturation_fix.py` still pass
- [ ] Pipeline completes without error
- [ ] Output schema unchanged (same columns in raw.parquet, validation.parquet, sources.parquet)
- [ ] Clerks with `label_omission_rate: 0.0` and `value_abbreviation_rate: 0.0` produce identical output to pre-change behavior

---

## Warnings and Pitfalls

### DO NOT change `levels_provided` or `path_completeness`

These fields reflect which hierarchy levels the clerk **intended** to include, not how they rendered them. Label omission and value abbreviation are rendering-layer changes. A record with "3" (dropped label "Squadron") still has "squadron" in its `levels_provided`.

### DO NOT change `extraction_signals` computation

`extraction_signals` is computed from the rendered unit string by `_extract_structural_signals()`. If abbreviation causes "Squadron" to not appear in the text, the signal correctly disappears. This is intentional — abbreviated records genuinely have fewer structural signals.

### DO NOT make abbreviations deterministic per name

"Amber" should NOT always abbreviate to the same thing. Different clerks (and even the same clerk on different entries) should produce different abbreviations: "Amb", "Ambr", "Am". Use stochastic abbreviation length.

### Watch for empty values

If `_abbreviate_value()` somehow produces an empty string, fall back to the original value. Never render an empty designator.

### Greek letter special case

Sector designators are Greek letters (Alpha, Beta, Gamma). These should be abbreviated less aggressively than colony/fleet/settlement names because they're short and commonly used. The implementation should handle this explicitly.

### Backward compatibility for existing tests

The existing test `_make_clerk()` helper creates clerks with default `UnitFormat()` which will have `label_omission_rate=0.0` and `value_abbreviation_rate=0.0`. This means existing tests should pass unchanged because the defaults preserve pre-change behavior.

---

## Test Strategy

### Unit Tests

Add to `tests/synthetic/test_difficulty_saturation_fix.py` or create a new `tests/synthetic/test_rendering_realism.py`:

1. **Label omission with rate=1.0:** Test that `_format_labeled()` with `label_omission_rate=1.0` produces label-free output (values only)
2. **Label omission with rate=0.0:** Test that `_format_labeled()` with `label_omission_rate=0.0` produces fully-labeled output (same as current)
3. **Value abbreviation:** Test that `_abbreviate_value()` returns shorter strings for named values and passes through numbers/letters unchanged
4. **Delimiter mixing:** Test that `_mix_delimiters()` modifies output for low-consistency clerks and preserves output for high-consistency clerks
5. **Familiarity boost:** Test that SAME_L3 familiarity produces more label omission than DIFFERENT_BRANCH for the same clerk

### Integration Test

Run pipeline with 100 soldiers, verify:
- Labeled-style records show a mix of labeled and unlabeled levels
- Named designators sometimes appear abbreviated
- Some entries have mixed delimiters
- Visual inspection confirms tier-3 records look more degraded than tier-1

### Statistical Verification

```python
import pandas as pd
df = pd.read_parquet("data/synthetic/raw.parquet")

# Check that raw_text contains fewer level-type labels than before
label_terms = ["Sector", "Colony", "District", "Settlement", "Fleet",
               "Squadron", "Wing", "Element", "Expedition", "Team",
               "Operation", "Facility", "Crew",
               "Sec", "Col", "Dist", "Set", "Flt", "Sq", "Wg", "El",
               "Exp", "Tm", "Op", "Fac", "Cr"]
label_count = sum(df["raw_text"].str.contains(term).sum() for term in label_terms)
total_records = len(df)
label_density = label_count / total_records
print(f"Label density: {label_density:.2f} labels per record")
# Should be well below 2.0 (was ~3-4 before)

# Check abbreviated values
full_names = ["Amber", "Kestrel", "Landfall", "Haven", "Prospect",
              "Talon", "Sentinel", "Horizon", "Pathfinder", "Deepcore"]
full_name_count = sum(df["raw_text"].str.contains(name).sum() for name in full_names)
print(f"Full name occurrences: {full_name_count}")
# Should be noticeably lower than pre-change
```

---

## References

- **Diagnosis:** User observation that tier-3 records read as "high tier 1"
- **Renderer:** `src/synthetic/renderer.py` (main implementation target)
- **Models:** `src/synthetic/models.py` (UnitFormat changes)
- **Clerk factory:** `src/synthetic/clerk_factory.py` (parsing changes)
- **Style spec:** `docs/components/synthetic_data_generation/synthetic_style_spec_v4.1.yaml`
- **Instruction 006:** `instructions/active/006_fix-difficulty-saturation.md` (prerequisite, addresses level dropping and difficulty computation)
