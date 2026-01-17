# Resolver Strategy

**Status:** Complete - all modules implemented
**Last Updated:** 2026-01-15

## Purpose

Consolidation using raw text + hierarchy + pre-learned heuristics (resolvers). Resolvers are generated from validation data to guide LLM parsing.

**Key distinction from other strategies:** Resolver generation is a separate build-time workflow that produces artifacts (resolver JSON files). These artifacts are then used at consolidation time. This is NOT a parallel routing pipeline — it's a component-centric generation process that uses ground truth data.

## What LLM Receives (at Consolidation Time)

- Raw text records for batch of soldiers
- Component hierarchy document
- Resolver (pre-learned heuristics for this component)
- Consolidation instructions

---

## Resolver Generation Overview

### Information Flow (Inverted from Main Pipeline)

| Pipeline | Direction | Input | Output |
|----------|-----------|-------|--------|
| **Main Routing** | Unknown → Component | Regex signals | Component assignment |
| **Resolver Gen** | Component → Patterns | Ground truth grouping | Learned heuristics |

Resolver generation does NOT require routing — validation.parquet already contains ground truth component assignments. The workflow groups by known component and learns distinguishing patterns.

---

## LLM Batch Statefulness (Decided)

**Decision: Dual-Run Stateful with Hard Case Reconciliation** (ADR-002)

Resolver generation uses a dual-run approach to balance contextual disambiguation (critical for this project) against drift risk from ordering effects.

### Architecture

```
Run 1 (Forward Order):
  Batch A → {patterns, hard_cases: [S12, S45]}
  Batch B → {patterns, hard_cases: [S67]}        (stateful, carrying context)
  Batch C → {patterns, hard_cases: [S89, S91]}
  Output: {final_patterns, all_hard_cases}

Run 2 (Inverted Order):
  Batch C → {patterns, hard_cases: [S91, S23]}
  Batch B → {patterns, hard_cases: [S45]}        (stateful, carrying context)
  Batch A → {patterns, hard_cases: [S12]}
  Output: {final_patterns, all_hard_cases}

Reconciliation:
  - Compare patterns from both runs
  - Validate against hard cases (full records provided)
  - Produce final patterns with validated confidence
```

### Key Principles

1. **Dual-run exposes drift**: Patterns found in both orderings are robust; single-run patterns are order-dependent
2. **Hard case flagging**: LLM identifies ambiguous soldiers during extraction; these become the validation corpus
3. **Hard case agreement is signal**: Cases flagged by both runs are genuinely hard; single-run flags reveal where ordering "helped"
4. **Token-budget batching**: Batches sized by token count, with soldier coherence (all records for a soldier in same batch)

### Applies To

- Phase 4: Pattern Discovery
- Phase 6: Vocabulary Discovery
- Phase 7: Differentiator Generation

### Hard Case Criteria

Flag soldier as hard case if:
- Multiple component indicators present (conflicting signals)
- Key identifiers missing or ambiguous
- Unusual notation not matching known patterns
- Low confidence despite having records
- Transfer indicators present

**Reference:** `docs/architecture/decisions/ADR-002_llm-batching-statefulness.md`

### Implementation Findings (Captured)

- Hard case IDs can be dropped when batch-level `soldier_ids` (per soldier) do not align with per-record `target_texts`, which prevents the LLM from returning valid `hard_cases`.
- Dual-run mode currently runs the single-pass pattern discovery and then overwrites it, which doubles LLM cost and inflates token accounting.
- Hard case record lookup compares string IDs from the LLM to `records_df[soldier_id_col]` directly; if the dataframe column is numeric, reconciliation can see empty hard case records.

### Data Requirements

**Input files:**
- `validation.parquet` — Ground truth assignments (component known)
- `raw.parquet` — Raw text records (joined via soldier_id)
- `config/hierarchies/hierarchy_reference.json` — Structural definitions

**Output files:**
- `config/resolvers/{component}_resolver.json` — Per-component heuristics
- `config/resolvers/resolver_registry.json` — Tracking and rebuild triggers

---

## Relative Threshold System

Rather than absolute sample sizes, tiers are calculated from the validation set distribution:

### Tier Calculation

```python
component_counts = validation_df.groupby("component_id").size()
median = component_counts.median()
p25 = component_counts.quantile(0.25)
p75 = component_counts.quantile(0.75)

# Tier assignment
well_represented:        count >= p75
adequately_represented:  count >= median
under_represented:       count >= p25
sparse:                  count < p25
```

### What Gets Generated Per Tier

| Resolver Section | well_represented | adequately_represented | under_represented | sparse |
|------------------|------------------|------------------------|-------------------|--------|
| **structure** | Full | Full | Full | Full |
| **patterns** | Full | Full | Limited | Not generated |
| **vocabulary** | Full | May be thin | Not generated | Not generated |
| **exclusions.structural** | Full | Full | Full | Full (hierarchy-derived) |
| **exclusions.value_based** | Full | Full | Limited | Not generated |
| **differentiators** | Full | Full | Hierarchy-only | Hierarchy-only |

### Asymmetric Rival Handling

When a **well-represented component** builds differentiators against a **sparse rival**:
- Use the sparse rival's limited data in collision sampling
- Flag differentiator as `rival_undersampled`
- Generate hierarchy-based rules only for that rival

When a **sparse component** builds its own resolver:
- Structure section: Complete (from hierarchy)
- Pattern/vocabulary sections: Explicitly marked `not_generated`
- Differentiators: Hierarchy-only with quality warnings
- Recommendation: Use zero-shot or few-shot strategy instead

---

## Train/Test Split Strategy

### Split Purpose

| Set | Purpose | When Used |
|-----|---------|-----------|
| **Training** | Resolver generation (phases 3-8) | Build time |
| **Test** | Evaluation of consolidation accuracy | After consolidation |

### Split Rules

1. **Stratify by subcomponent** (regiment) within each component
2. **Target ratio:** 75% train / 25% test
3. **Minimum test set:** Configurable, e.g., 10 soldiers per component
4. **Per-stratum minimum:** At least 1 test soldier per regiment (if regiment has ≥4 total)
5. **Leakage policy:** Must comply with ADR-001 (soldier-level disjoint splits, no source overlap)

### Handling Sparse Components

- Components below threshold: No split — all data available for limited resolver or few-shot examples
- Marginal strata: Flag in registry as `evaluation_unreliable`

**Reference policy:** `docs/architecture/decisions/ADR-001_validation-leakage-policy.md`

---

## Resolver Generation Workflow (8 Phases)

### Phase 1: Extract Structural Rules
**Input:** hierarchy_reference.json
**Output:** Valid/invalid designators for regiment, battalion, company
**Data needed:** None (hierarchy only)

### Phase 2: Collision Detection
**Input:** All hierarchy definitions
**Output:** Map of which components share which designators
**Data needed:** None (hierarchy only)
**Uses:** `collision_index` from hierarchy_reference.json

### Phase 3: Collision-Based Sampling
**Input:** Training split of validation.parquet + raw.parquet
**Output:** Head-to-head soldier sets for each collision pair
**Process:**
- For each collision (e.g., regiment 5 shared by 1st ID and 3rd ID)
- Sample N soldiers from each side
- If rival is sparse: use all available, flag as `rival_undersampled`

### Phase 4: Pattern Discovery
**Input:** Collision samples with raw text
**Output:** Text patterns that identify the component
**LLM task:** "What text patterns distinguish {component} from {rival}?"
**Tier requirement:** Skipped for `sparse` components

### Phase 5: Exclusion Mining
**Input:** Cross-component samples
**Output:** Rules for what definitively excludes this component
**Two types:**
- `structural`: From hierarchy (e.g., "PIR mention excludes infantry divisions")
- `value_based`: From data (e.g., "regiment 11 excludes 1st ID")
**Tier requirement:** `value_based` skipped for `sparse` and `under_represented`

### Phase 6: Vocabulary Discovery
**Input:** All training soldiers for target component
**Output:** Characteristic terms with frequency tiers
**LLM task:** Term frequency analysis, tier assignment
**Tier requirement:** Skipped for `sparse` and `under_represented`

### Phase 7: Differentiator Generation
**Input:** Collision analysis + patterns + exclusions + vocabulary
**Output:** Rival-specific disambiguation rules
**Per-rival status:**
- `complete`: Both sides well-sampled
- `rival_undersampled`: Rival is sparse, hierarchy-only rules
- `hierarchy_only`: Target component is sparse

### Phase 8: Tier Assignment
**Input:** All discovered patterns
**Output:** Confidence tier for each pattern
**Tiers:**
- `robust`: >90% reliable in validation sample
- `strong`: 75-90% reliable
- `moderate`: 50-75% reliable
- `tentative`: <50% reliable (tiebreaker only)

---

## Resolver JSON Schema

### Full Resolver (well_represented component)

```json
{
  "meta": {
    "component_id": "1st_infantry_division",
    "generated_utc": "2026-01-15T00:00:00Z",
    "tier": "well_represented",
    "sample_size": 847,
    "pct_of_median": 596.5,
    "generation_mode": "full"
  },

  "structure": {
    "status": "complete",
    "valid_regiments": [1, 5, 7],
    "valid_battalions": [1, 2, 3],
    "valid_companies": ["A", "B", "C", "D", "E", "F", "G", "H", "I", "K", "L", "M"],
    "battalion_designator_type": "numeric"
  },

  "patterns": {
    "status": "complete",
    "entries": {
      "1st Infantry Division": {"means": "component=1st_infantry_division", "tier": "robust"},
      "Big Red One": {"means": "component=1st_infantry_division", "tier": "robust"},
      "2/5": {"means": "battalion=2, regiment=5", "tier": "strong"},
      "5th Inf Regt": {"means": "regiment=5", "tier": "moderate", "note": "needs division signal"}
    }
  },

  "vocabulary": {
    "status": "complete",
    "strong": ["Big Red One", "1st ID", "BRO"],
    "moderate": ["1st Division", "Omaha Beach"],
    "weak": ["Normandy", "ETO"]
  },

  "exclusions": {
    "structural": {
      "status": "complete",
      "rules": [
        {"if": "contains 'PIR' or 'parachute' or 'airborne'", "then": "exclude"},
        {"if": "contains 'Marine' or 'USMC'", "then": "exclude"}
      ]
    },
    "value_based": {
      "status": "complete",
      "rules": [
        {"if": "regiment in [2, 3, 6, 8, 9, 11]", "then": "exclude"},
        {"if": "battalion in ['A', 'B', 'C']", "then": "exclude"}
      ]
    }
  },

  "differentiators": {
    "vs_3rd_infantry_division": {
      "status": "complete",
      "rival_sample_size": 423,
      "rules": [
        "Regiment 11 present → 3rd ID",
        "Regiment 1 present → 1st ID",
        "'Rock of the Marne' vocabulary → 3rd ID",
        "'Big Red One' vocabulary → 1st ID"
      ]
    },
    "vs_36th_infantry_division": {
      "status": "rival_undersampled",
      "rival_sample_size": 23,
      "rival_tier": "sparse",
      "rules": [
        "Regiment 2 or 3 → 36th ID (hierarchy-derived)",
        "Regiment 5 or 7 → 1st ID (hierarchy-derived)"
      ],
      "not_generated": ["vocabulary-based differentiators", "pattern-based rules"]
    }
  }
}
```

### Partial Resolver (sparse component)

```json
{
  "meta": {
    "component_id": "36th_infantry_division",
    "generated_utc": "2026-01-15T00:00:00Z",
    "tier": "sparse",
    "sample_size": 23,
    "pct_of_median": 16.2,
    "generation_mode": "hierarchy_only"
  },

  "structure": {
    "status": "complete",
    "valid_regiments": [1, 2, 3],
    "valid_battalions": [1, 2, 3],
    "valid_companies": ["A", "B", "C", "D", "E", "F", "G", "H", "I", "K", "L", "M"]
  },

  "patterns": {
    "status": "not_generated",
    "reason": "insufficient_sample",
    "rebuild_when": "tier >= under_represented"
  },

  "vocabulary": {
    "status": "not_generated",
    "reason": "insufficient_sample",
    "known_aliases": ["36th ID", "Texas Division"],
    "alias_source": "hierarchy_reference (not validated from data)"
  },

  "exclusions": {
    "structural": {
      "status": "complete",
      "source": "hierarchy",
      "rules": [
        {"if": "contains 'Marine' or 'USMC'", "then": "exclude"},
        {"if": "contains 'airborne' or 'PIR'", "then": "exclude"}
      ]
    },
    "value_based": {
      "status": "not_generated",
      "reason": "insufficient_sample"
    }
  },

  "differentiators": {
    "generation_mode": "hierarchy_only",
    "vs_1st_infantry_division": {
      "status": "hierarchy_only",
      "rules": ["Regiment 2 or 3 → 36th ID", "Regiment 5 or 7 → 1st ID"]
    },
    "vs_2nd_infantry_division": {
      "status": "hierarchy_only",
      "warning": "high_collision_risk",
      "rules": ["Regiment 1, 2, 3 shared — limited disambiguation from structure alone"]
    }
  },

  "quality_notes": [
    "High collision with 2nd_infantry_division — both share regiments 1, 3",
    "Recommend zero-shot or few-shot strategy until more validation data available"
  ]
}
```

---

## Resolver Registry

`config/resolvers/resolver_registry.json` tracks all resolvers and rebuild triggers.

See `docs/data-structures/CURRENT.md` for full schema.

**Key features:**
- Tracks generation status per component
- Records section-level completeness
- Defines rebuild triggers (sample size thresholds)
- Flags quality warnings and recommendations

---

## Key Principles

- **Cross-record context:** Pattern interpretation uses ALL records for soldier
- **Proportional tiers:** Confidence based on proportion of sample, not absolute counts
- **Vocabulary as tiebreaker:** One tier nudge max, never primary evidence
- **Conservative exclusions:** Only incompatible PRESENCE excludes, never absence
- **Graceful degradation:** Sparse components get hierarchy-only resolvers with explicit gaps
- **Rebuild awareness:** Registry tracks when resolvers should be regenerated

---

## Tradeoffs

**Advantages:**
- Focused guidance for LLM
- Pre-learned pattern interpretations
- Explicit disambiguation rules
- Quality-aware (knows its own limitations)

**Disadvantages:**
- Requires generation workflow
- Resolvers must be regenerated if validation data changes
- More complex system
- Sparse components get limited benefit

---

## Key Design Questions (Resolved)

- [x] Resolver token budget (~500-600)? — Yes, target range
- [x] Generation workflow automation level? — Fully automated with LLM phases
- [x] Resolver versioning strategy? — Via resolver_registry.json with rebuild triggers
- [x] How to handle sparse components? — Hierarchy-only resolvers with quality flags

## Key Design Questions (Open)

- [ ] Exact threshold percentiles (p25/median/p75) vs other methods?
- [ ] Minimum per-collision-pair sample size?
- [ ] LLM model selection for generation phases?

---

## Implementation Status

**Harness Foundation (Strategy-Agnostic):**
| Component | Status | Location |
|-----------|--------|----------|
| Base Strategy Interface | ✓ Complete | `src/strategies/base_strategy.py` |
| Train/Test Splitter | ✓ Complete | `src/evaluation/split.py` |
| Batching Manager | ✓ Complete | `src/batching/batch_manager.py` |
| Evaluation Framework | ✓ Complete | `src/evaluation/metrics.py` |
| LLM Infrastructure | ✓ Complete | `src/utils/llm/` (Gemini ready, Claude/OpenAI stubs) |
| Demo/Examples | ✓ Complete | `examples/harness_demo.py` |

**Resolver-Specific Components:**
| Component | Status | Location |
|-----------|--------|----------|
| Threshold Calculator | ✓ Complete | `src/strategies/resolver/generator/thresholds.py` |
| Phase 1-2 (Structure) | ✓ Complete | `src/strategies/resolver/generator/structure.py` |
| Phase 3 (Sampling) | ✓ Complete | `src/strategies/resolver/generator/sampling.py` |
| Phase 4-8 (LLM Phases) | Needs update | `src/strategies/resolver/generator/llm_phases.py` |
| Dual-Run Orchestrator | ✓ Complete | `src/strategies/resolver/generator/dual_run.py` |
| Reconciliation | ✓ Complete | `src/strategies/resolver/generator/reconciliation.py` |
| Registry Manager | ✓ Complete | `src/strategies/resolver/generator/registry.py` |
| Prompts | ✓ Complete | `src/strategies/resolver/generator/prompts.py` |
| Assembler | ✓ Complete | `src/strategies/resolver/generator/assembler.py` |
| Main Orchestrator | Needs update | `src/strategies/resolver/generator/generate.py` |
| Resolver Executor | ✓ Complete | `src/strategies/resolver/executor/strategy.py` |

**Infrastructure (Global Utilities):**
| Component | Status | Location |
|-----------|--------|----------|
| Token Budget Batcher | ✓ Complete | `src/utils/llm/token_batcher.py` |
| LLM Retry Logic | ✓ Complete | `src/utils/llm/base.py` |

---

## Implementation Specification (7 Modules)

The resolver generation workflow is implemented as 7 modules that can be built and tested independently.

**Prerequisites (already built):**
- ✓ Train/Test Splitter (`src/evaluation/split.py`)
- ✓ LLM Infrastructure (`src/utils/llm/`)
- ✓ Cost Tracker (`src/utils/cost_tracker.py`)

### Module 1: Threshold Calculator

**File:** `src/strategies/resolver/generator/thresholds.py`

Computes relative threshold tiers from validation data distribution.

```python
@dataclass
class ThresholdResult:
    thresholds: Dict[str, float]  # p25, median, p75
    component_tiers: Dict[str, str]  # component_id -> tier
    component_counts: Dict[str, int]  # component_id -> count

def compute_thresholds(validation_df: pd.DataFrame) -> ThresholdResult:
    """
    Compute tier thresholds from validation distribution.
    Groups by component, computes p25/median/p75, assigns tiers.
    """
```

### Module 2: Structure Extractor

**File:** `src/strategies/resolver/generator/structure.py`

Extracts valid designators from hierarchy and detects collisions (Phases 1-2).

```python
@dataclass
class ComponentStructure:
    component_id: str
    valid_regiments: List[int]
    valid_battalions: List[Union[int, str]]
    valid_companies: List[str]
    battalion_type: str  # "numeric" or "alphabetic"

@dataclass
class StructureResult:
    structures: Dict[str, ComponentStructure]
    collisions: Dict[Tuple, Set[str]]  # (level, value) -> {component_ids}

def extract_structure(hierarchy_path: Path) -> StructureResult:
    """Extract valid designators and collision map from hierarchy."""
```

### Module 3: Collision Sampler

**File:** `src/strategies/resolver/generator/sampling.py`

Creates head-to-head soldier samples for collision pairs (Phase 3).

```python
@dataclass
class CollisionSample:
    component_a: str
    component_b: str
    soldiers_a: List[str]
    soldiers_b: List[str]
    records_a: pd.DataFrame
    records_b: pd.DataFrame
    undersampled_a: bool
    undersampled_b: bool

def sample_collisions(
    train_df: pd.DataFrame,
    raw_df: pd.DataFrame,
    collisions: Dict[Tuple, Set[str]],
    thresholds: ThresholdResult,
    samples_per_side: int = 20,
) -> Dict[Tuple[str, str], CollisionSample]:
    """Sample soldiers for collision analysis."""
```

### Module 4: LLM Phases Orchestrator

**File:** `src/strategies/resolver/generator/llm_phases.py`

Orchestrates LLM-based discovery phases (Phases 4-8). This is the largest module.

**Phase 4 - Pattern Discovery:**
```python
def discover_patterns(component_id, collision_samples, llm, tier) -> PatternResult:
    """Discover text patterns that identify the component. Skip if sparse."""
```

**Phase 5 - Exclusion Mining:**
```python
def mine_exclusions(component_id, structure, all_structures, collision_samples, llm, tier) -> ExclusionResult:
    """Mine exclusion rules. Structural always generated; value-based skipped for sparse/under_represented."""
```

**Phase 6 - Vocabulary Discovery:**
```python
def discover_vocabulary(component_id, train_df, raw_df, llm, tier) -> VocabularyResult:
    """Discover characteristic vocabulary. Skip for sparse/under_represented."""
```

**Phase 7 - Differentiator Generation:**
```python
def generate_differentiators(component_id, rivals, collision_samples, patterns, exclusions, vocabulary, llm, tier, rival_tiers) -> Dict[str, DifferentiatorResult]:
    """Generate rival-specific disambiguation rules."""
```

**Phase 8 - Tier Assignment:**
```python
def assign_pattern_tiers(patterns, train_df, raw_df) -> Dict[str, Dict]:
    """Assign confidence tiers to patterns based on validation accuracy."""
```

### Module 5: Registry Manager

**File:** `src/strategies/resolver/generator/registry.py`

Tracks resolver generation status and rebuild triggers.

```python
@dataclass
class RegistryEntry:
    component_id: str
    tier: str
    sample_size: int
    pct_of_median: float
    generated_utc: str
    generation_mode: str  # "full", "limited", "hierarchy_only"
    # Section status fields...
    rebuild_when_tier: Optional[str] = None
    rebuild_when_sample_size: Optional[int] = None

class RegistryManager:
    def should_rebuild(self, component_id, current_tier, current_sample) -> bool:
        """Check if resolver should be regenerated."""
```

### Module 6: Resolver Assembler

**File:** `src/strategies/resolver/generator/assembler.py`

Assembles all phase outputs into final resolver JSON.

```python
def assemble_resolver(
    component_id, tier, sample_size, pct_of_median,
    structure, patterns, exclusions, vocabulary, differentiators,
) -> Dict:
    """Assemble resolver JSON from all phase outputs."""
```

### Module 7: Main Orchestrator

**File:** `src/strategies/resolver/generator/generate.py`

Main entry point that orchestrates all modules.

```python
def generate_all_resolvers(
    validation_path: Path,
    raw_path: Path,
    hierarchy_path: Path,
    output_dir: Path,
    split_path: Optional[Path] = None,
    model_name: str = "gemini-2.5-pro",
) -> GenerationSummary:
    """
    Generate resolvers for all components.

    Steps:
    1. Load data and create/load split
    2. Compute thresholds (Module 1)
    3. Extract structure and collisions (Module 2)
    4. Sample collisions (Module 3)
    5. For each component: run dual-run extraction + reconciliation
    6. Assemble, save, update registry
    7. Return summary with cost tracking
    """
```

### Module 8: Dual-Run Orchestrator (NEW)

**File:** `src/strategies/resolver/generator/dual_run.py`

Orchestrates dual-run stateful extraction per ADR-002.

```python
@dataclass
class DualRunResult:
    forward_patterns: PatternResult
    inverted_patterns: PatternResult
    forward_hard_cases: List[HardCase]
    inverted_hard_cases: List[HardCase]
    all_hard_case_ids: Set[str]
    hard_case_agreement: Dict[str, str]  # soldier_id -> "both" | "forward_only" | "inverted_only"

def run_dual_extraction(
    component_id: str,
    batches: List[TokenBatch],
    llm: BaseLLMProvider,
    phase: str,  # "patterns" | "vocabulary" | "differentiators"
) -> DualRunResult:
    """
    Run extraction twice with inverted batch order.

    1. Forward pass: batches in original order, stateful accumulator
    2. Inverted pass: batches reversed, fresh accumulator
    3. Collect hard cases from both runs
    4. Return results for reconciliation
    """
```

### Module 9: Reconciliation (NEW)

**File:** `src/strategies/resolver/generator/reconciliation.py`

Reconciles dual-run results and validates against hard cases.

```python
@dataclass
class ReconciliationResult:
    robust_patterns: List[Dict]      # Found in both runs
    order_dependent: List[Dict]      # Found in one run only (flagged)
    validated_patterns: List[Dict]   # Passed hard case validation
    rejected_patterns: List[Dict]    # Failed hard case validation
    hard_case_analysis: Dict[str, str]  # Per-soldier analysis

def reconcile_patterns(
    dual_run_result: DualRunResult,
    hard_case_records: pd.DataFrame,
    llm: BaseLLMProvider,
) -> ReconciliationResult:
    """
    Reconcile dual-run results.

    1. Identify robust patterns (both runs)
    2. Flag order-dependent patterns (one run only)
    3. Validate all patterns against hard case records
    4. Produce final pattern set with confidence tiers
    """
```

**Reconciliation Prompt Tasks:**
- Compare pattern lists from both runs
- For disagreements: test against hard case records to determine correctness
- For hard cases flagged by one run only: identify what context resolved them
- Assign final confidence tiers based on robustness + hard case performance

### Recommended Build Order

**Phase 1 - Infrastructure (Global Utilities):**
1. Token Budget Batcher (`src/utils/llm/token_batcher.py`)
2. LLM Retry Logic (enhance `src/utils/llm/base.py`)

**Phase 2 - Non-LLM Foundation (already complete):**
1. Module 1: Threshold Calculator ✓
2. Module 2: Structure Extractor ✓
3. Module 3: Collision Sampler ✓
4. Module 5: Registry Manager ✓

**Phase 3 - Prompt Engineering Updates:**
- Update `prompts.py` to include hard case flagging in extraction prompts
- Add reconciliation prompts
- Test prompts manually with LLM infrastructure

**Phase 4 - Dual-Run and Reconciliation:**
- Module 8: Dual-Run Orchestrator (new)
- Module 9: Reconciliation (new)
- Update Module 4: LLM Phases to use token batching + hard case flagging

**Phase 5 - Assembly Updates:**
- Update Module 6: Resolver Assembler (add reconciliation metadata)
- Update Module 7: Main Orchestrator (integrate dual-run workflow)

**Phase 6 - Executor (already complete):**
- `ResolverStrategy(BaseStrategy)` ✓

---

## References

- Architecture: `docs/architecture/CURRENT.md`
- Data Structures: `docs/data-structures/CURRENT.md`
- Hierarchy Reference: `config/hierarchies/hierarchy_reference.json`
- Comparison: `docs/components/strategies/_comparison/CURRENT.md`
