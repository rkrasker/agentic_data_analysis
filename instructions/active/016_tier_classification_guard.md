# 016: Tier Classification Guard

**Status:** active
**Created:** 2026-01-29
**Component:** src/strategies/resolver/generator/thresholds.py

## Context

The tier classification system uses percentile-based thresholds (p25, median, p75) to assign components to quality tiers. However, with small N (e.g., 4 components), quantile math produces pathological results: exactly 1 component per tier regardless of how similar their counts are.

**Example failure**: Colonial Administration has 97% of median count but gets `tier: "sparse"` because with only 4 components, there is exactly 1 below p25 by definition.

**Cascade effect**: Wrong tier triggers `generation_mode: "hierarchy_only"`, which prevents pattern and vocabulary discovery even when the sample is adequate.

Analysis in `.project_history/extracts/raw/2026-01-29_opus_resolver-quality-bugs.md` (Issue 1).

## Task

Add a guard to prevent "sparse" classification when `pct_of_median >= 75%`. A component with 75%+ of the median count should be at least "under_represented", not "sparse".

## Scope

- **Working in:** `src/strategies/resolver/generator/thresholds.py`
- **Reference:** `compute_thresholds` function at lines 48-108
- **Test location:** `tests/strategies/resolver/generator/`
- **Ignore:** `.project_history/`, unrelated components

## Inputs

- `validation_df`: DataFrame with `soldier_id` and `component_id` columns
- Component counts derived from `df.groupby("component_id")["soldier_id"].nunique()`

## Outputs

- `ThresholdResult` with tier assignments that respect the semantic meaning of "sparse" (i.e., genuinely low-data components, not just rank-based assignments)

## Implementation

In `compute_thresholds`, modify the tier assignment loop (lines 92-102). After the percentile-based logic, add a guard that promotes "sparse" to "under_represented" when the component has >= 75% of median:

```python
# Assign tiers
component_tiers: Dict[str, TierName] = {}
for component_id, count in component_counts.items():
    if count >= p75:
        component_tiers[component_id] = "well_represented"
    elif count >= median:
        component_tiers[component_id] = "adequately_represented"
    elif count >= p25:
        component_tiers[component_id] = "under_represented"
    else:
        # Guard: don't mark as sparse if close to median
        pct_of_median = (count / median * 100) if median > 0 else 0
        if pct_of_median >= 75:
            component_tiers[component_id] = "under_represented"
        else:
            component_tiers[component_id] = "sparse"
```

Alternatively, integrate the check into the elif chain:

```python
for component_id, count in component_counts.items():
    pct_of_median = (count / median * 100) if median > 0 else 0

    if count >= p75:
        component_tiers[component_id] = "well_represented"
    elif count >= median:
        component_tiers[component_id] = "adequately_represented"
    elif count >= p25 or pct_of_median >= 75:
        component_tiers[component_id] = "under_represented"
    else:
        component_tiers[component_id] = "sparse"
```

The second form is cleaner and consistent with the existing elif structure.

## Acceptance Criteria

- [ ] Component with >= 75% of median count is never assigned "sparse" tier
- [ ] Component with < p25 and < 75% of median is still assigned "sparse"
- [ ] Existing tests pass
- [ ] Add test case: 4 components with counts [100, 98, 97, 95] should all be "adequately_represented" or better (all >= 95% of median), not one "sparse"
- [ ] Add test case: component with 50% of median and below p25 should be "sparse"

## Notes

- Follow [CODE_STYLE.md](docs/CODE_STYLE.md): keep the fix minimal and integrated into existing code structure
- The 75% threshold is chosen because it means the component has reasonable sample size relative to peers
- This fix prevents cascading errors where adequate components get `generation_mode: "hierarchy_only"`

## References

- Bug analysis: `.project_history/extracts/raw/2026-01-29_opus_resolver-quality-bugs.md` (Issue 1)
- Quality assessment: `landing_zone/resolver_quality_assessment.md`
- Current implementation: `src/strategies/resolver/generator/thresholds.py:92-102`
