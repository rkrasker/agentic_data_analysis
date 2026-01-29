# 011: Difficulty-Based Sampling for Resolver Generation

**Status:** active
**Created:** 2026-01-29
**Component:** src/preprocessing/splits/, src/strategies/resolver/generator/

## Context

ADR-009 Decision 1 specifies: "Sample by Soldier Difficulty, Not Record Quality." The current `sampling.py` performs random sampling within collision zones, but doesn't consider soldier difficulty tiers (easy/moderate/hard/extreme).

For resolver training, we want to prioritize hard and extreme cases—soldiers whose records are structurally ambiguous—while maintaining some diversity with moderate/easy cases. This requires:

1. Pre-computing train/test splits with difficulty data joined
2. Stratified sampling that allocates quotas by difficulty tier

See ADR-009 for the full rationale. The difficulty tier schema is defined in ADR-010 and DIFFICULTY_MODEL.md.

## Task

Implement difficulty-based stratified sampling:

1. Create a preprocessing step that outputs `train_with_difficulty.parquet` and `test_with_difficulty.parquet`
2. Update `sampling.py` to perform stratified sampling by `gt_difficulty_tier`
3. Update `generate.py` to consume the pre-computed train split

## Scope

- **Working in:** `src/preprocessing/splits/` (new), `src/strategies/resolver/generator/`
- **Reference:** `DIFFICULTY_MODEL.md`, `docs/architecture/decisions/ADR-009_resolver-generation-alignment.md`
- **Config inputs:** None (uses existing data files)
- **Test location:** `tests/preprocessing/`, `tests/strategies/resolver/generator/`
- **Ignore:** `.project_history/`, LLM phases, prompts

## Inputs

| File | Purpose |
|------|---------|
| `data/synthetic/validation.parquet` | soldier_id, component_id, post labels |
| `data/synthetic/gt_difficulty.parquet` | soldier_id, gt_difficulty_tier, gt_* metrics |
| `data/synthetic/raw.parquet` | Raw text records (passed through to sampling) |

## Outputs

### From preprocessing step

**train_with_difficulty.parquet:**
```
soldier_id: str
component_id: str
state_id: str
branch: str
post_path: str
[level columns]: str
gt_difficulty_tier: str         # easy | moderate | hard | extreme
gt_complementarity_score: float
gt_collision_zone_flag: bool
gt_structural_resolvability: bool
```

**test_with_difficulty.parquet:** Same schema as train.

### From sampling.py

No schema changes to `ComponentSamples` or `CollisionSample`. The change is in *which* soldiers are sampled (stratified by difficulty).

## Implementation Steps

### Phase 1: Create train/test split module

**Location:** `src/preprocessing/splits/prepare_train_split.py`

```python
def prepare_train_test_split(
    validation_path: Path,
    difficulty_path: Path,
    output_dir: Path,
    train_ratio: float = 0.7,
    random_seed: int = 42,
) -> Tuple[Path, Path]:
    """
    Create train/test splits with difficulty labels joined.

    Steps:
    1. Load validation.parquet and gt_difficulty.parquet
    2. Join on soldier_id (left join from validation to difficulty)
    3. Create stratified train/test split (stratify by component_id)
    4. Write train_with_difficulty.parquet and test_with_difficulty.parquet

    Returns:
        Tuple of (train_path, test_path)
    """
```

Add CLI entry point:
```bash
python -m src.preprocessing.splits.prepare_train_split \
    --validation data/synthetic/validation.parquet \
    --difficulty data/synthetic/gt_difficulty.parquet \
    --output-dir data/synthetic/ \
    --train-ratio 0.7
```

Create `src/preprocessing/splits/__init__.py` with module exports.

### Phase 2: Update sampling.py for stratified sampling

**File:** `src/strategies/resolver/generator/sampling.py`

Add parameters to `sample_collisions()`:

```python
def sample_collisions(
    train_df: pd.DataFrame,
    raw_df: pd.DataFrame,
    structure_result: StructureResult,
    thresholds: ThresholdResult,
    samples_per_side: int = 20,
    random_seed: int = 42,
    # NEW parameters
    stratify_by_difficulty: bool = False,
    tier_weights: Optional[Dict[str, float]] = None,
) -> Dict[str, ComponentSamples]:
```

Default tier weights (prioritize hard/extreme):
```python
DEFAULT_TIER_WEIGHTS = {
    "extreme": 0.35,
    "hard": 0.35,
    "moderate": 0.20,
    "easy": 0.10,
}
```

Update `_sample_soldiers()` to support stratified mode:

```python
def _sample_soldiers(
    soldiers: List[str],
    target_size: int,
    rng: np.random.RandomState,
    soldier_tiers: Optional[Dict[str, str]] = None,
    tier_weights: Optional[Dict[str, float]] = None,
) -> Tuple[List[str], bool]:
    """
    When soldier_tiers and tier_weights provided:
    1. Group soldiers by tier
    2. Compute target count per tier based on weights
    3. Sample from each tier up to target
    4. Redistribute quota if a tier has insufficient soldiers
    """
```

Add helper:

```python
def _stratified_sample(
    soldiers_by_tier: Dict[str, List[str]],
    target_size: int,
    tier_weights: Dict[str, float],
    rng: np.random.RandomState,
) -> Tuple[List[str], bool]:
    """Perform stratified sampling across difficulty tiers."""
```

### Phase 3: Update generate.py

**File:** `src/strategies/resolver/generator/generate.py`

Update `generate_all_resolvers()` to accept pre-computed train path:

```python
def generate_all_resolvers(
    # Existing parameters...

    # NEW parameters
    train_split_path: Optional[Path] = None,
    stratify_by_difficulty: bool = True,
    tier_weights: Optional[Dict[str, float]] = None,
) -> Dict[str, ResolverArtifact]:
```

When `train_split_path` is provided:
- Load from path instead of computing train/test split internally
- Pass `stratify_by_difficulty=True` to `sample_collisions()`
- Extract soldier tier mapping from the loaded dataframe

### Phase 4: Backward compatibility

- When `stratify_by_difficulty=False` (default in sampling.py), behavior unchanged
- When `train_split_path=None` (default in generate.py), behavior unchanged
- Log warning if stratification requested but `gt_difficulty_tier` column missing

## Acceptance Criteria

- [ ] `src/preprocessing/splits/prepare_train_split.py` exists and is runnable
- [ ] `train_with_difficulty.parquet` contains all required columns including `gt_difficulty_tier`
- [ ] Train/test split is stratified by component_id (all components in both splits)
- [ ] `sample_collisions()` with `stratify_by_difficulty=True` produces samples following tier_weights distribution
- [ ] When a tier has insufficient soldiers, quota redistributes proportionally to other tiers
- [ ] Undersampling flags are set correctly (reflects per-tier undersampling)
- [ ] `generate_all_resolvers()` works with `train_split_path` parameter
- [ ] Existing behavior preserved when new parameters not used
- [ ] Tests pass in `tests/preprocessing/` and `tests/strategies/resolver/generator/`

## Notes

### Stratification Logic

Quota allocation example with `samples_per_side=20` and default weights:
- extreme: 0.35 * 20 = 7 soldiers
- hard: 0.35 * 20 = 7 soldiers
- moderate: 0.20 * 20 = 4 soldiers
- easy: 0.10 * 20 = 2 soldiers

If extreme only has 3 available soldiers:
1. Sample all 3 extreme
2. Redistribute 4 remaining (7-3) proportionally to hard/moderate/easy
3. Continue until target reached or all soldiers exhausted

### Why preprocessing outputs both train and test

- Train split: Used for resolver generation (sampling, pattern discovery)
- Test split: Used for evaluation (accuracy by difficulty tier)
- Both need difficulty joined for stratified analysis

### No changes to LLM phases

This instruction only changes *which soldiers* are sampled. The downstream LLM phases (pattern discovery, differentiators, etc.) receive the same `CollisionSample` structure—just with different soldier compositions.

## References

- ADR-009: Resolver Generation Alignment (Decision 1: "Sample by Soldier Difficulty")
- ADR-010: Synthetic Metadata Separation (gt_ prefix convention)
- ADR-006: Three-Layer Difficulty Model (tier definitions)
- DIFFICULTY_MODEL.md: Operational difficulty computation
- Current sampling implementation: `src/strategies/resolver/generator/sampling.py`
