# Thread Extract: Resolver Collision Sampling & Synthetic Degradation

Date: 2026-01-17
Source: Claude Code (Opus 4.5) session

## Context

Session analyzed why the 82nd Airborne Division resolver (`config/resolvers/82nd_airborne_division_resolver.json`) produced trivial output that merely restated what's derivable from `hierarchy_reference.json`. The resolver's patterns, vocabulary, and differentiators added no value beyond the hierarchy.

Two root causes identified, both relating to how the LLM "sees" the data during resolver generation.

## Key Findings

### 1. Collision Sampling Bug (Critical)

**Location**: `src/strategies/resolver/generator/sampling.py` lines 176-186

**Problem**: When comparing 82nd Airborne vs 101st Airborne (collision only on regiment 3), the sampler pulls from ALL soldiers in each division:

```python
# Current (buggy)
sample_a = _sample_soldiers(all_soldiers, ...)      # ALL 82nd soldiers (regiments 3,5,7)
sample_b = _sample_soldiers(rival_soldiers, ...)    # ALL 101st soldiers (regiments 1,3,6)
```

The LLM sees soldiers from non-overlapping regiments (1,5,6,7) and produces trivial rules:
- "Regiment 5 or 7 → 82nd Airborne Division"
- "Regiment 1 or 6 → 101st Airborne Division"

These rules are derivable from the hierarchy alone - no pattern discovery required.

**Root cause**: `collision_levels` is passed to prompts as informational context, but actual record sampling ignores it.

**Fix**: Filter soldiers to only those in colliding sub-units before sampling:

```python
def _filter_to_collision(soldiers, train_df, collision_levels):
    """Filter to soldiers in colliding sub-units (e.g., regiment=3 only)."""
    # For regiment 3 collision, return only regiment 3 soldiers from both sides
```

**Expected outcome**: When both samples contain only regiment 3 soldiers, the LLM must find OTHER signals (PIR vs GIR, vocabulary, etc.) to disambiguate.

### 2. Synthetic Data Too Explicit

**Problem**: Even "degraded" synthetic entries include unit type indicators that make disambiguation trivial.

**renderer.py** issue (line 276):
```python
# In _render_labeled_full()
elif div_type == "airborne":
    parts.append(f"{reg} PIR")  # Always adds "PIR" - trivially identifiable
```

There's no option to render ambiguous entries like:
- "A/3" (battalion A, regiment 3 - no type, no division)
- "3rd" (just regiment number - massive collision)

**Tier distribution issue** (`source_generator.py`):
- Tiers 1-2 (55% of output): Include explicit division
- Tiers 4-5 (20%): Omit division but still include unit_type labels

**Result**: The resolver never sees the hard cases that require vocabulary-based disambiguation.

### 3. Multi-Entry Aggregation Gap

User observation: In realistic data, a clerk logging 20 consecutive soldiers from the same unit may start with explicit identification, then degrade to company-only:

| Entry | Raw Text |
|-------|----------|
| 1 | "Miller, James R. Pvt - Co 2, Bn A, 3rd PIR, 82nd Abn Div" |
| 2-5 | "Adams, Robert L. Pvt - Co 1, 3rd" |
| 6-20 | "Baker, William F. Pvt - Co 2" |

The resolver should learn to chain context: explicit anchor (entry 1) → inherited regiment (entries 2-5) → inherited battalion (entries 6-20).

Current synthetic generation doesn't model this "clerk fatigue" pattern where explicitness decreases within a source batch.

## Resolution Path

### Phase 1: Collision-Scoped Sampling

**Minimum viable fix** - implement `_filter_to_collision()` in `sampling.py`:
1. Accept `collision_levels` from `get_collision_levels()`
2. Filter `all_soldiers` to only those matching colliding designators
3. Re-run resolver generation
4. Verify differentiators now reference vocabulary signals, not unique regiments

### Phase 2: Synthetic Degradation Redesign (if needed)

If Phase 1 is insufficient due to data quality:
1. Add `omit_unit_type` flag to renderer
2. Create `field_minimal` archetype for maximum ambiguity
3. Rebalance tier weights toward degraded (4-5)
4. Regenerate synthetic dataset
5. Re-run resolver generation

## Code References

| Location | Issue |
|----------|-------|
| `sampling.py:176-186` | Sampling bug - doesn't filter to collision |
| `sampling.py:174` | `collision_levels` fetched but unused for filtering |
| `llm_phases.py:219-222` | `collision_levels` passed to prompt (informational only) |
| `renderer.py:276` | "PIR" always appended for airborne |
| `source_generator.py:26-33` | Tier weights favor explicit entries |
| `prompts.py:81-83` | Collision context in prompt template |

## User Insights

On realistic data degradation:
> "a clerk who has logged 20 consecutive members of single entity may just start listing them by company designator alone ('A'). this is probably a common scenario: no unit type term specified AND designators that exist so far down the hierarchy as to have very little cardinality."

On subtle vocabulary signals:
> "'screaming eagles' etc is ludicrously explicit" - resolver should learn subtle signals like "jump qual", "silk", "CHK-42" that aren't obvious division nicknames.

## Related Files

- Resolver output: `config/resolvers/82nd_airborne_division_resolver.json`
- Hierarchy reference: `config/hierarchies/hierarchy_reference.json`
- Synthetic spec: `docs/components/synthetic_data_generation/synthetic_style_spec_v3.yaml`
- Vocabulary config: `config/synthetic/synthetic_vocabulary.json`
