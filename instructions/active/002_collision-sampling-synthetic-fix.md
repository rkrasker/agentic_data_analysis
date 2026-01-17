# 002: Collision Sampling + Synthetic Degradation Fix

**Created:** 2026-01-17
**Status:** Pending
**Components:** resolver, synthetic
**Depends on:** `src/strategies/resolver/generator/sampling.py`, `src/synthetic/renderer.py`

---

## Objective

Fix two issues causing resolver generation to produce trivial output:
1. **Collision sampling bug**: Sampler doesn't filter to colliding sub-units
2. **Synthetic data too explicit**: Unit type indicators make disambiguation trivial

---

## Context

Analysis of 82nd Airborne resolver showed it learned nothing beyond what's derivable from `hierarchy_reference.json`. Root causes identified in session 2026-01-17.

See: `.project_history/extracts/raw/2026-01-17_opus_resolver-collision-sampling.md`

---

## Phase 1: Collision-Scoped Sampling (Priority)

### Problem

`sampling.py` lines 176-186 sample from ALL soldiers, not just those in colliding sub-units:

```python
# Current (buggy) - samples regiment 3,5,7 from 82nd, regiment 1,3,6 from 101st
sample_a = _sample_soldiers(all_soldiers, ...)
sample_b = _sample_soldiers(rival_soldiers, ...)
```

LLM sees non-overlapping regiments and produces trivial rules.

### Tasks

1. [ ] **Add `_filter_to_collision()` helper** in `sampling.py`
   ```python
   def _filter_to_collision(
       soldiers: List[str],
       train_df: pd.DataFrame,
       collision_levels: List[Tuple[str, str]],
   ) -> List[str]:
       """Filter to soldiers in colliding sub-units (e.g., regiment=3 only)."""
       if not collision_levels:
           return soldiers

       df = train_df[train_df["soldier_id"].isin(soldiers)]
       masks = [df[level] == value for level, value in collision_levels if level in df.columns]

       if not masks:
           return soldiers

       combined = masks[0]
       for m in masks[1:]:
           combined |= m

       return df[combined]["soldier_id"].unique().tolist()
   ```

2. [ ] **Modify `sample_collisions()`** to use the filter (around line 169)
   ```python
   for rival_id in rivals:
       collision_levels = structure_result.get_collision_levels(component_id, rival_id)

       # NEW: Filter to colliding sub-units
       soldiers_in_collision_a = _filter_to_collision(
           all_soldiers, train_df, collision_levels
       )
       soldiers_in_collision_b = _filter_to_collision(
           rival_soldiers, train_df, collision_levels
       )

       sample_a, undersampled_a = _sample_soldiers(
           soldiers_in_collision_a, samples_per_side, rng
       )
       sample_b, undersampled_b = _sample_soldiers(
           soldiers_in_collision_b, samples_per_side, rng
       )
   ```

3. [ ] **Handle empty collision case** - if filter returns no soldiers, fall back to all soldiers with warning

4. [ ] **Add logging** to verify filtering works:
   ```python
   logger.info(f"Collision filter: {len(all_soldiers)} -> {len(soldiers_in_collision_a)} for {component_id}")
   ```

### Acceptance Criteria

- [ ] Filter reduces sample size for collisions (e.g., 82nd vs 101st should sample ~1/3 of soldiers)
- [ ] Re-run resolver for 82nd Airborne
- [ ] 82nd vs 101st differentiators should NOT reference unique regiments (5, 7 for 82nd; 1, 6 for 101st)
- [ ] Differentiators should reference vocabulary signals (PIR vs GIR, airborne terminology)

---

## Phase 2: Synthetic Degradation Redesign (If Needed)

Only proceed if Phase 1 validation shows data quality issues.

### Problem

Even "degraded" entries include unit type indicators (PIR, Infantry, Marine):

```python
# renderer.py line 276
elif div_type == "airborne":
    parts.append(f"{reg} PIR")  # Always explicit
```

### Tasks

1. [ ] **Add `omit_unit_type` flag** to `UnitFormat` in `models.py`
   ```python
   @dataclass
   class UnitFormat:
       # existing fields...
       omit_unit_type: bool = False
   ```

2. [ ] **Update renderer** to respect flag in `_render_labeled_full()` and similar
   ```python
   if assignment.regiment and clerk.unit_format.include_regiment:
       reg = self._ordinal(assignment.regiment)
       if clerk.unit_format.omit_unit_type:
           parts.append(f"{reg}")  # Just "3rd", no "PIR"
       elif div_type == "airborne":
           parts.append(f"{reg} PIR")
       # ...
   ```

3. [ ] **Add `field_minimal` archetype** in `synthetic_style_spec_v3.yaml`
   ```yaml
   field_minimal:
     description: "Field clerk under extreme stress. Writes bare minimum."
     context_level: "field"
     unit_format:
       style: "minimal"
       include_division: false
       include_regiment: true
       omit_unit_type: true
     vocabulary_density: "low"
     consistency:
       format_lock: 0.60
     imperfections:
       typo_rate: 0.10
       trailing_off: 0.15
   ```

4. [ ] **Rebalance tier weights** in `source_generator.py`
   ```python
   QUALITY_TIER_WEIGHTS = {
       1: 0.10,  # archival_clean (was 0.20)
       2: 0.25,  # standard (was 0.35)
       3: 0.30,  # field_worn (was 0.25)
       4: 0.25,  # degraded (was 0.15)
       5: 0.10,  # fragmentary (was 0.05)
   }
   ```

5. [ ] **Regenerate synthetic dataset**
   ```bash
   python3.11 -m src.synthetic.pipeline
   ```

### Acceptance Criteria

- [ ] <15% of entries have explicit division identification
- [ ] >30% of entries omit unit_type (just regiment number)
- [ ] >35% of sources in degraded/fragmentary tiers (4-5)
- [ ] Re-run full resolver generation
- [ ] Resolver differentiators reference vocabulary signals

---

## Key Files

### Phase 1
| File | Change |
|------|--------|
| `src/strategies/resolver/generator/sampling.py` | Add `_filter_to_collision()`, modify `sample_collisions()` |

### Phase 2
| File | Change |
|------|--------|
| `src/synthetic/models.py` | Add `omit_unit_type` to UnitFormat |
| `src/synthetic/renderer.py` | Respect `omit_unit_type` flag |
| `src/synthetic/source_generator.py` | Rebalance tier weights |
| `docs/.../synthetic_style_spec_v3.yaml` | Add `field_minimal` archetype |

---

## Verification

### Phase 1 Verification
```bash
# Run resolver generation for test component
python -c "
from src.strategies.resolver.generator import generate_resolver
result = generate_resolver('82nd_airborne_division')
print(result['differentiators']['vs_101st_airborne_division'])
"
```

Check that differentiators reference vocabulary, not unique regiments.

### Phase 2 Verification
```bash
# Check synthetic distribution after regeneration
python -c "
import pandas as pd
df = pd.read_parquet('data/synthetic/raw.parquet')
# Analyze explicit_division rate, unit_type presence, tier distribution
"
```

---

## References

- Thread extract: `.project_history/extracts/raw/2026-01-17_opus_resolver-collision-sampling.md`
- Hierarchy reference: `config/hierarchies/hierarchy_reference.json`
- Synthetic spec: `docs/components/synthetic_data_generation/synthetic_style_spec_v3.yaml`
