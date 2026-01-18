# Resolver Strategy

**Status:** Complete - all modules implemented
**Last Updated:** 2026-01-17

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

### Collision-Scoped Sampling (2026-01-17)

Phase 3 sampling now filters soldiers to only those in colliding sub-units before sampling:
- Example: If 82nd and 101st both have regiment 3, only soldiers from regiment 3 are sampled
- Prevents LLM from learning trivial rules based on non-overlapping designators
- Falls back to all soldiers with warning if filter returns empty
- Implemented in `sampling.py:_filter_to_collision()`

### Quality Tier Filtering (2026-01-17)

LLM phases now filter records by quality tier to force discovery of subtle signals:

| Phase | Mode | Tier 1 | Tier 2 | Tiers 3-5 |
|-------|------|--------|--------|-----------|
| Vocabulary (40 records) | vocab | 0% | 0% | 100% |
| Patterns (20 records) | differentiator | 0% | 0% | 100% |
| Exclusions (30 records) | differentiator | 0% | ≤20% | ≥80% |

**Rationale:** High-quality records (tier 1-2) often have explicit unit identifiers (e.g., "3rd PIR" instead of just "3rd"), making disambiguation trivial. Filtering toward lower-quality records forces the LLM to find vocabulary signals rather than relying on explicit identifiers.

Implemented in `llm_phases.py:_filter_records_by_quality()`

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
    "observed": {
      "1st Infantry Division": {
        "means": "component=1st_infantry_division",
        "tier": "robust",
        "example_records": ["MURPHY SGT 1st Infantry Division E2-16"]
      },
      "1st ID": {
        "means": "component=1st_infantry_division",
        "tier": "strong",
        "example_records": ["JONES PFC 1st ID A/1/5"]
      },
      "2/5": {
        "means": "battalion=2, regiment=5",
        "tier": "strong",
        "example_records": ["SMITH CPL 2/5"]
      }
    },
    "inferred": {
      "Big Red One": {
        "means": "component=1st_infantry_division",
        "tier": "moderate",
        "note": "Known nickname, not seen in examples"
      }
    },
    "ambiguous": {
      "5th": "Appears in multiple units without division context"
    }
  },

  "vocabulary": {
    "status": "complete",
    "observed": {
      "strong": ["1st ID", "1ID"],
      "moderate": ["1st Division"],
      "weak": []
    },
    "inferred": {
      "strong": ["Big Red One", "BRO"],
      "moderate": ["Omaha Beach"],
      "weak": ["Normandy", "ETO"]
    }
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
      "positive_signals": [
        {
          "if_contains": "Rock of the Marne or ROTM",
          "then": "increase_confidence",
          "target": "3rd Infantry Division",
          "strength": "strong",
          "provenance": "observed"
        },
        {
          "if_contains": "1st ID or 1ID",
          "then": "increase_confidence",
          "target": "1st Infantry Division",
          "strength": "strong",
          "provenance": "observed"
        }
      ],
      "structural_rules": [
        {
          "if_contains": "Regiment 11",
          "then": "identifies",
          "target": "3rd Infantry Division",
          "strength": "strong",
          "note": "Unique regiment designation"
        },
        {
          "if_contains": "Regiment 1 or 5 or 7",
          "then": "identifies",
          "target": "1st Infantry Division",
          "strength": "strong",
          "note": "Unique regiment designation"
        }
      ],
      "ambiguous_when": {
        "condition": "Only shared battalion/company, no regiment or division identifier",
        "example_patterns": ["A/2", "B Co"],
        "recommendation": "cannot_determine"
      }
    },
    "vs_36th_infantry_division": {
      "status": "rival_undersampled",
      "rival_sample_size": 23,
      "rival_tier": "sparse",
      "structural_rules": [
        {
          "if_contains": "Regiment 2 or 3",
          "then": "identifies",
          "target": "36th Infantry Division",
          "strength": "strong",
          "note": "Hierarchy-derived (unique to 36th)"
        },
        {
          "if_contains": "Regiment 5 or 7",
          "then": "identifies",
          "target": "1st Infantry Division",
          "strength": "strong",
          "note": "Hierarchy-derived (unique to 1st)"
        }
      ],
      "ambiguous_when": {
        "condition": "Only regiment 1 present (shared by both units)",
        "recommendation": "cannot_determine"
      },
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
      "structural_rules": [
        {
          "if_contains": "Regiment 2 or 3",
          "then": "identifies",
          "target": "36th Infantry Division",
          "strength": "strong",
          "note": "Unique regiment designation"
        },
        {
          "if_contains": "Regiment 5 or 7",
          "then": "identifies",
          "target": "1st Infantry Division",
          "strength": "strong",
          "note": "Unique regiment designation"
        }
      ],
      "ambiguous_when": {
        "condition": "Only shared regiment 1 present",
        "recommendation": "cannot_determine"
      }
    },
    "vs_2nd_infantry_division": {
      "status": "hierarchy_only",
      "structural_rules": [],
      "ambiguous_when": {
        "condition": "Regiments 1, 2, 3 shared — no structural disambiguation possible",
        "recommendation": "flag_for_review"
      },
      "notes": "High collision risk - both share all three regiments"
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

## Grounded Inference Philosophy (ADR-005)

**Updated:** 2026-01-18

Resolver generation now enforces grounded inference with provenance tracking to prevent LLM knowledge leakage:

### Core Principles

**1. Absence is NOT evidence** - Records lacking a term (e.g., no "ABN") are uninformative, not negative signals. Clerks often abbreviate; absence means nothing.

**2. Grounded claims only** - All patterns/vocabulary must be cited from example records OR explicitly marked as `inferred` (from LLM training knowledge).

**3. Ambiguity is valid** - Some records cannot be disambiguated. "Cannot determine" is an acceptable outcome. Do not force classification.

**4. Positive signals only** - Rules based on PRESENCE of terms, never ABSENCE:
- ✓ "Contains 'ABN'" → positive signal FOR airborne
- ✗ "Does NOT contain 'ABN'" → INVALID
- ✓ "Contains 'Marine'" (when expecting Army) → conflict signal

### Provenance Tracking

**Observed** - Term appears in provided example records, can be cited
**Inferred** - Term from LLM training knowledge (e.g., unit nicknames, historical campaigns)

Downstream code can weight: `observed` (high trust) > `inferred` (hint only)

### Confidence-Based Signals (Not Deterministic Rules)

Old approach (deterministic):
```
"Contains ABN → 101st Airborne"
"LACKS ABN → 2nd Infantry"  // ❌ Invalid
```

New approach (confidence-based):
```json
"positive_signals": [
  {"if_contains": "ABN or PIR", "then": "increase_confidence", "target": "101st", "strength": "strong"}
],
"ambiguous_when": {
  "condition": "Only regiment number, no type modifiers",
  "recommendation": "cannot_determine"
}
```

**Reference:** `docs/architecture/decisions/ADR-005_grounded-inference-provenance.md`

---

## Key Principles

- **Cross-record context:** Pattern interpretation uses ALL records for soldier
- **Proportional tiers:** Confidence based on proportion of sample, not absolute counts
- **Vocabulary as tiebreaker:** One tier nudge max, never primary evidence
- **Conservative exclusions:** Only incompatible PRESENCE excludes, never absence
- **Graceful degradation:** Sparse components get hierarchy-only resolvers with explicit gaps
- **Rebuild awareness:** Registry tracks when resolvers should be regenerated
- **Grounded inference:** Patterns grounded in examples; provenance tracked (ADR-005)

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
| Phase 3 (Sampling) | ✓ Complete | `src/strategies/resolver/generator/sampling.py` (+ collision-scoped filtering) |
| Phase 4-8 (LLM Phases) | ✓ Complete | `src/strategies/resolver/generator/llm_phases.py` (+ quality tier filtering) |
| Dual-Run Orchestrator | ✓ Complete | `src/strategies/resolver/generator/dual_run.py` |
| Reconciliation | ✓ Complete | `src/strategies/resolver/generator/reconciliation.py` |
| Registry Manager | ✓ Complete | `src/strategies/resolver/generator/registry.py` |
| Prompts | ✓ Complete | `src/strategies/resolver/generator/prompts.py` |
| Assembler | ✓ Complete | `src/strategies/resolver/generator/assembler.py` |
| Main Orchestrator | ✓ Complete | `src/strategies/resolver/generator/generate.py` |
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

## Performance Optimizations (2026-01-17)

### Timeout Configuration Fix

**Problem:** LLM calls to Gemini API were timing out after 30-45 minutes instead of the configured 2 minutes, causing resolver generation to hang indefinitely.

**Root Cause:** The `timeout` parameter in `ChatGoogleGenerativeAI` was not being properly enforced. Passing a custom `httpx.Client` object caused validation errors.

**Solution:**
- Pass `timeout` parameter directly to `ChatGoogleGenerativeAI` (line 54 in `gemini.py`)
- Increased default timeout from 120s to 300s (5 minutes) to allow complex differentiator calls to complete
- Reduced retry attempts from 3 to 1 to fail fast on persistent issues
- Location: `src/utils/llm/providers/gemini.py`

**Impact:**
- Maximum time per LLM call: 10 minutes (5 min timeout × 2 attempts)
- Phase 7 (Differentiator Generation) now completes or fails predictably instead of hanging
- Failed calls now surface quickly for debugging

### Lazy Import Optimization

**Problem:** Importing any function from `src.strategies.resolver.generator` was taking 5-10 seconds due to eager loading of LangChain and Google GenAI SDK.

**Root Cause:** Package `__init__.py` files imported all modules eagerly, including heavy dependencies:
- `src/strategies/resolver/__init__.py` imported `ResolverStrategy` (which imports LangChain)
- `src/strategies/resolver/generator/__init__.py` imported `generate.py` (which imports LLM providers)

**Solution:**
- Converted both `__init__.py` files to use lazy imports via `__getattr__`
- Lightweight modules (thresholds, structure, sampling, registry, assembler) import eagerly
- Heavy modules (llm_phases, generate, executor) import only when accessed
- Location: `src/strategies/resolver/__init__.py`, `src/strategies/resolver/generator/__init__.py`

**Impact:**
- Import time reduced from ~5-10s to ~0.5-1s for lightweight utilities
- Notebook startup significantly faster
- Generator functions (generate_single_component, etc.) only load LangChain when actually called

### Progress Callback Support

**Problem:** No visibility into which phase of resolver generation was running, making it difficult to diagnose hangs.

**Solution:**
- Added `progress_callback` parameter to generation pipeline:
  - `generate_all_resolvers()`
  - `generate_single_component()`
  - `_generate_single_resolver()`
  - `_run_dual_mode()`
  - `run_all_phases()`
- Callback invoked at each phase transition with phase name
- Integrated with tqdm in `resolver_generation.ipynb` for visual progress bar
- Location: `src/strategies/resolver/generator/generate.py`, `src/strategies/resolver/generator/llm_phases.py`

**Impact:**
- Real-time visibility into current phase (Pattern Discovery, Exclusion Mining, etc.)
- Progress bar shows completion percentage and estimated time remaining
- Easier to identify which phase is slow or stuck

**Example Usage (Notebook):**
```python
from tqdm.auto import tqdm

pbar = tqdm(total=6, desc=f"Generating {COMPONENT_ID}", unit="phase")

def update_progress(phase_name: str):
    pbar.set_postfix_str(phase_name)
    pbar.update(1)

resolver = generate_single_component(
    component_id=COMPONENT_ID,
    progress_callback=update_progress,
    ...
)
```

### Retry Configuration

**Change:** Reduced maximum retry attempts from 3 to 1 for faster failure on persistent issues.

**Rationale:**
- With 5-minute timeouts, 3 retries meant 20 minutes wasted on a failing call
- Differentiator generation has 9 rivals, so one bad call could waste hours
- Better to fail fast and surface the error for debugging

**Configuration:** `src/strategies/resolver/generator/generate.py:241-249`

```python
retry_config = RetryConfig(
    max_retries=1,  # Reduced from 3
    initial_delay=2.0,
    max_delay=10.0,
    retry_on_timeout=True,
    retry_on_rate_limit=True,
)
```

---

## References

- Architecture: `docs/architecture/CURRENT.md`
- Data Structures: `docs/data-structures/CURRENT.md`
- Hierarchy Reference: `config/hierarchies/hierarchy_reference.json`
- Comparison: `docs/components/strategies/_comparison/CURRENT.md`
