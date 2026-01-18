# 003: Synthetic Data Degradation Redesign (Phase 2)

**Status:** code-complete (pending validation)
**Created:** 2026-01-17
**Updated:** 2026-01-17
**Component:** src/synthetic/

## Context

Validation testing of the 82nd Airborne Division resolver revealed that the synthetic data is too explicit to meaningfully test disambiguation capabilities. Even "degraded" tier 3-5 records include unit type indicators (PIR, Infantry, Marine) that make component identification trivial.

**Root cause analysis from session 2026-01-17:**
- Resolver validation showed 70% regiment accuracy but only 25% full unit accuracy
- Ground truth uses letter company codes (K, M, E, F) but raw records show numeric (1, 2, 3, 4)
- Records like `"Pvt Schroeder, Roy Co 4, B Bn, 3rd Inf, 82nd AB"` are explicit even in tier 3
- The resolver can't learn subtle vocabulary signals when explicit identifiers are always present

**Depends on:** Phase 1 (collision-scoped sampling) is complete in `002_collision-sampling-synthetic-fix.md`

## Task

Redesign synthetic data generation to produce realistically ambiguous records that force the resolver to learn vocabulary-based disambiguation rather than relying on explicit unit type indicators.

## Scope

- **Working in:** `src/synthetic/`
- **Reference:** `docs/components/synthetic_data_generation/CURRENT.md`
- **Config inputs:** `config/synthetic/`, `docs/components/synthetic_data_generation/synthetic_style_spec_v3.yaml`
- **Test location:** `tests/test_synthetic/` (create if needed)
- **Ignore:** `src/strategies/`, `.project_history/`

## Inputs

| File | Purpose |
|------|---------|
| `src/synthetic/models.py` | Data models including `UnitFormat` |
| `src/synthetic/renderer.py` | Record text rendering logic |
| `src/synthetic/source_generator.py` | Quality tier distribution |
| `docs/.../synthetic_style_spec_v3.yaml` | Clerk archetype definitions |
| `config/hierarchies/hierarchy_reference.json` | Valid unit structures |

## Outputs

| File | Change |
|------|--------|
| `src/synthetic/models.py` | Add `omit_unit_type` flag to `UnitFormat` |
| `src/synthetic/renderer.py` | Respect `omit_unit_type` in rendering |
| `src/synthetic/source_generator.py` | Rebalance tier weights |
| `src/synthetic/pipeline.py` | Add `COMPONENT_WEIGHTS_82ND_FOCUSED` and CLI support |
| `src/synthetic/clerk_factory.py` | Parse and pass `omit_unit_type` flag |
| `docs/.../synthetic_style_spec_v3.yaml` | Add `field_minimal` archetype |
| `synthetic_generation.ipynb` | Notebook for interactive generation |
| `data/synthetic/*.parquet` | Regenerated with new distribution |

## Implementation Steps

### Step 1: Add `omit_unit_type` Flag to UnitFormat

**File:** `src/synthetic/models.py`

Find the `UnitFormat` dataclass and add:

```python
@dataclass
class UnitFormat:
    # ... existing fields ...
    omit_unit_type: bool = False  # When True, renders "3rd" instead of "3rd PIR"
```

### Step 2: Update Renderer to Respect Flag

**File:** `src/synthetic/renderer.py`

Find `_render_labeled_full()` (around line 276) where unit type is appended:

**Current code:**
```python
elif div_type == "airborne":
    parts.append(f"{reg} PIR")
elif div_type == "infantry":
    parts.append(f"{reg} Inf")
# etc.
```

**Change to:**
```python
if clerk.unit_format.omit_unit_type:
    parts.append(f"{reg}")  # Just "3rd", no type indicator
elif div_type == "airborne":
    parts.append(f"{reg} PIR")
elif div_type == "infantry":
    parts.append(f"{reg} Inf")
# etc.
```

Apply similar changes to:
- `_render_slash_notation()`
- `_render_minimal()`
- Any other rendering methods that add unit type suffixes

### Step 3: Add `field_minimal` Clerk Archetype

**File:** `docs/components/synthetic_data_generation/synthetic_style_spec_v3.yaml`

Add new archetype for maximum ambiguity:

```yaml
field_minimal:
  description: "Field clerk under extreme stress. Writes bare minimum identifiers."
  context_level: "field"
  unit_format:
    style: "minimal"
    include_division: false
    include_regiment: true
    include_battalion: true
    include_company: true
    omit_unit_type: true  # NEW FLAG
  vocabulary_density: "low"
  consistency:
    format_lock: 0.60
  imperfections:
    typo_rate: 0.10
    abbreviation_rate: 0.40
    trailing_off: 0.15
```

### Step 4: Rebalance Quality Tier Weights

**File:** `src/synthetic/source_generator.py`

Find `QUALITY_TIER_WEIGHTS` (around line 26-33):

**Current:**
```python
QUALITY_TIER_WEIGHTS = {
    1: 0.20,  # archival_clean
    2: 0.35,  # standard
    3: 0.25,  # field_worn
    4: 0.15,  # degraded
    5: 0.05,  # fragmentary
}
```

**Change to:**
```python
QUALITY_TIER_WEIGHTS = {
    1: 0.10,  # archival_clean (reduced)
    2: 0.25,  # standard (reduced)
    3: 0.30,  # field_worn (increased)
    4: 0.25,  # degraded (increased)
    5: 0.10,  # fragmentary (increased)
}
```

### Step 5: Wire `field_minimal` to Tier 4-5

**File:** `src/synthetic/source_generator.py`

Find where clerk archetypes are assigned to tiers. Ensure `field_minimal` is used for tier 4-5 sources:

```python
TIER_ARCHETYPE_MAP = {
    1: ["archival_clean"],
    2: ["standard", "archival_clean"],
    3: ["field_worn", "standard"],
    4: ["degraded", "field_minimal"],  # Add field_minimal
    5: ["fragmentary", "field_minimal"],  # Add field_minimal
}
```

### Step 6: Fix Company Code Consistency

**Issue discovered:** Ground truth uses letter codes (K, M, E, F) but raw records use numbers (1, 2, 3, 4).

**File:** Check `src/synthetic/` for where company codes are generated vs rendered.

Ensure consistency between:
- `validation.parquet` company field
- `raw.parquet` rendered text

This may require tracing through:
- `soldier_generator.py` - where assignments are created
- `renderer.py` - where assignments are rendered to text

### Step 7: Regenerate Synthetic Dataset

```bash
# Clear old data
rm -f data/synthetic/*.parquet

# Regenerate with new settings
./venv/bin/python -m src.synthetic.pipeline

# Verify distribution
./venv/bin/python -c "
import pandas as pd
df = pd.read_parquet('data/synthetic/raw.parquet')
print('Quality tier distribution:')
print(df['quality_tier'].value_counts(normalize=True).sort_index())
print()
print('Sample tier 4-5 records:')
print(df[df['quality_tier'] >= 4]['raw_text'].head(10).tolist())
"
```

### Step 8: Re-run Resolver Generation

After regenerating synthetic data:

```bash
# Regenerate 82nd Airborne resolver
./venv/bin/python -c "
from src.strategies.resolver.generator import generate_resolver
result = generate_resolver('82nd_airborne_division')
print('Differentiators vs 101st:')
print(result['differentiators']['vs_101st_airborne_division'])
"
```

### Step 9: Re-run Validation Test

```bash
./venv/bin/python tests/test_resolver_validation.py
```

## Acceptance Criteria

- [x] `omit_unit_type` flag added to `UnitFormat` dataclass
- [x] Renderer respects `omit_unit_type` - no PIR/Inf/Marine suffixes when True
- [x] `field_minimal` archetype added to style spec
- [x] Tier weights rebalanced: tiers 4-5 now >= 35% of output
- [x] Company codes consistent between validation.parquet and raw.parquet (verified: hierarchy defines correct codes)
- [x] Focused component weights added for 82nd resolver validation (9 components)
- [x] Jupyter notebook created for generation (`synthetic_generation.ipynb`)
- [ ] Synthetic data regenerated with new distribution
- [ ] <15% of records have explicit division identification
- [ ] >30% of records omit unit_type (just regiment number)
- [ ] Re-run resolver generation produces vocabulary-based differentiators (not unique regiment rules)
- [ ] Validation test shows improved alignment between predictions and ground truth

## Verification Commands

```bash
# Check tier distribution
./venv/bin/python -c "
import pandas as pd
df = pd.read_parquet('data/synthetic/raw.parquet')
print(df['quality_tier'].value_counts(normalize=True).sort_index())
"

# Check for explicit division mentions
./venv/bin/python -c "
import pandas as pd
df = pd.read_parquet('data/synthetic/raw.parquet')
explicit = df['raw_text'].str.contains('82nd|101st|1st Inf|3rd Mar', case=False, regex=True)
print(f'Explicit division: {explicit.mean():.1%}')
"

# Check for unit type omission
./venv/bin/python -c "
import pandas as pd
df = pd.read_parquet('data/synthetic/raw.parquet')
has_type = df['raw_text'].str.contains('PIR|GIR|Inf|Infantry|Marine|Mar', case=False, regex=True)
print(f'Has unit type: {has_type.mean():.1%}')
print(f'Omits unit type: {(~has_type).mean():.1%}')
"
```

## Notes

### Why This Matters

The resolver should learn subtle vocabulary signals like:
- "jump qual", "silk", "CHK-42" (airborne indicators)
- "amphib", "shore party" (marine indicators)
- Clerk-specific abbreviations and patterns

When explicit identifiers are always present, the resolver learns trivial rules that don't generalize to real degraded records.

### Clerk Fatigue Pattern (Future Enhancement)

Real records show a "clerk fatigue" pattern where explicitness decreases within a source batch:

| Entry | Raw Text |
|-------|----------|
| 1 | "Miller, James R. Pvt - Co 2, Bn A, 3rd PIR, 82nd Abn Div" |
| 2-5 | "Adams, Robert L. Pvt - Co 1, 3rd" |
| 6-20 | "Baker, William F. Pvt - Co 2" |

This is not addressed in Phase 2 but should be considered for future synthetic data improvements.

## References

- Phase 1 instruction: `instructions/active/002_collision-sampling-synthetic-fix.md`
- Thread extract: `.project_history/extracts/raw/2026-01-17_opus_resolver-collision-sampling.md`
- Synthetic spec: `docs/components/synthetic_data_generation/synthetic_style_spec_v3.yaml`
- Validation test: `tests/test_resolver_validation.py`
- Current resolver: `config/resolvers/82nd_airborne_division_resolver.json`
