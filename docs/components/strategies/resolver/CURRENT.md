# Resolver Strategy

**Status:** Requires update for ADR-009 alignment
**Last Updated:** 2026-01-27

## Purpose

Consolidation using raw text + hierarchy + pre-learned heuristics (resolvers). Resolvers are generated from validation data to guide LLM parsing.

**Key distinction from other strategies:** Resolver generation is a separate build-time workflow that produces artifacts (resolver JSON files). These artifacts are then used at consolidation time. This is NOT a parallel routing pipeline — it's a component-centric generation process that uses ground truth data.

**Scope limitation:** Resolvers help discriminate components and parse notation. They do NOT:
- Discover how many states a soldier has
- Group records to states
- Orchestrate full consolidation

State discovery and record grouping are upstream orchestration problems that *use* resolvers.

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

## LLM Batch Statefulness (ADR-002)

**Decision: Dual-Run Stateful with Hard Case Reconciliation**

Resolver generation uses a dual-run approach to balance contextual disambiguation against drift risk from ordering effects.

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

### Hard Case Criteria (ADR-009 Aligned)

Flag soldier as hard case based on three-layer model:

| Criterion | Layer | Description |
|-----------|-------|-------------|
| Collision position | 2 | Soldier's partial path is non-unique across components |
| Non-complementary records | 2 | All records provide same ambiguous partial path |
| Structural ambiguity | 3 | Designators don't resolve structurally (e.g., "3rd" without level context) |

Hard case output should include which layer caused difficulty, enabling layer-specific analysis in reconciliation.

**Reference:** `docs/architecture/decisions/ADR-002_llm-batching-statefulness.md`

---

## Sampling Strategy (ADR-009)

### Soldier Difficulty, Not Record Quality

**Old approach (removed):** Filter records by quality tier (tiers 3-5) to "force subtle signal discovery."

**Current approach:** Sample soldiers by assignment difficulty (Layers 2-3), then include ALL their records regardless of quality tier.

**Rationale (ADR-006):** Record quality (Layer 1) is orthogonal to assignment difficulty. A soldier with pristine records in a collision zone is exactly what differentiator training needs.

### Difficulty Assessment

```python
def compute_soldier_difficulty(
    soldier_id: str,
    records: pd.DataFrame,
    collisions: Dict[Tuple, Set[str]],
    hierarchy: HierarchyReference,
) -> DifficultyAssessment:
    """
    Returns:
    - collision_position: bool
    - complementarity_score: float (0.0-1.0)
    - structural_resolvability: bool
    - difficulty_tier: easy | moderate | hard | extreme
    """
```

### Collision-Scoped Sampling

Phase 3 sampling filters soldiers to those in colliding sub-units:
- Example: If Sector Alpha has Fleet 3 in both Defense Command and Resource Directorate, only soldiers from Fleet 3 are sampled
- Prevents LLM from learning trivial rules based on non-overlapping designators
- Falls back to all soldiers with warning if filter returns empty
- **NEW**: Within collision scope, prioritize soldiers where `difficulty_tier in ['hard', 'extreme']`

---

## Data Requirements

**Input files:**
- `validation.parquet` — Ground truth assignments (component known, state_id included)
- `raw.parquet` — Raw text records (joined via soldier_id, state_id included)
- `config/hierarchies/hierarchy_reference.json` — Structural definitions (heterogeneous branches)

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
| **exclusions** | Full | Full | Full | Full (hierarchy-derived) |
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
| **Training** | Resolver generation (phases 3-7) | Build time |
| **Test** | Evaluation of consolidation accuracy | After consolidation |

### Split Rules

1. **Stratify by subcomponent** within each component
2. **Target ratio:** 75% train / 25% test
3. **Minimum test set:** Configurable, e.g., 10 soldiers per component
4. **Per-stratum minimum:** At least 1 test soldier per subcomponent (if subcomponent has ≥4 total)
5. **Leakage policy:** Must comply with ADR-001 (soldier-level disjoint splits, no source overlap)

### Handling Sparse Components

- Components below threshold: No split — all data available for limited resolver or few-shot examples
- Marginal strata: Flag in registry as `evaluation_unreliable`

**Reference policy:** `docs/architecture/decisions/ADR-001_validation-leakage-policy.md`

---

## Resolver Generation Workflow (7 Phases)

### Phase 1: Extract Structural Rules
**Input:** hierarchy_reference.json (heterogeneous branches)
**Output:** Branch-aware structural constraints
**Data needed:** None (hierarchy only)

Extracts per-branch:
- Level names and depth
- Valid designators per level
- Structural discriminators (terms unique to branch)

### Phase 2: Collision Detection
**Input:** All hierarchy definitions
**Output:** Map of which components share which designators
**Data needed:** None (hierarchy only)
**Uses:** `collision_index` from hierarchy_reference.json

### Phase 3: Collision-Based Sampling
**Input:** Training split of validation.parquet + raw.parquet
**Output:** Head-to-head soldier sets for each collision pair
**Process:**
- For each collision (e.g., Fleet 3 shared by Defense Command and Resource Directorate)
- Filter to soldiers in collision zone
- Compute soldier difficulty scores
- Sample N soldiers prioritizing `hard` and `extreme` difficulty tiers
- Include ALL records for sampled soldiers (regardless of quality tier)
- If rival is sparse: use all available, flag as `rival_undersampled`

### Phase 4: Pattern Discovery
**Input:** Collision samples with raw text
**Output:** Text patterns that identify the component
**LLM task:** "What text patterns distinguish {component} from {rival}?"
**Tier requirement:** Skipped for `sparse` components

### Phase 5: Exclusion Derivation (Deterministic)
**Input:** Hierarchy reference
**Output:** Rules for what definitively excludes this component
**NO LLM CALL** — computed deterministically from hierarchy

Derives:
- Branch-unique term exclusions ("squadron" excludes Colonial Administration)
- Depth mismatch exclusions (5-level path excludes 3-level branches)
- Invalid designator exclusions (Fleet 8 doesn't exist)

**Rationale (ADR-009):** With synthetic data where hierarchy is complete by construction, structural facts are known — mining them from data is redundant.

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

### Full Resolver (well_represented component, Terraform Combine domain)

```json
{
  "meta": {
    "component_id": "defense_command_fleet_7",
    "generated_utc": "2026-01-27T00:00:00Z",
    "tier": "well_represented",
    "sample_size": 847,
    "pct_of_median": 596.5,
    "generation_mode": "full"
  },

  "structure": {
    "status": "complete",
    "branch": "defense_command",
    "depth": 5,
    "levels": ["sector", "fleet", "squadron", "wing", "element"],
    "valid_designators": {
      "sector": ["alpha", "beta", "gamma"],
      "fleet": [7],
      "squadron": [1, 2, 3],
      "wing": ["A", "B", "C", "D"],
      "element": [1, 2, 3, 4]
    },
    "structural_discriminators": [
      {"term": "squadron", "implies_branch": "defense_command", "strength": "definitive"},
      {"term": "wing", "implies_branch": "defense_command", "strength": "strong"},
      {"term": "element", "implies_branch": "defense_command", "strength": "moderate"}
    ]
  },

  "patterns": {
    "status": "complete",
    "observed": {
      "Fleet 7": {
        "means": "fleet=7",
        "tier": "robust",
        "example_records": ["CHEN SGT Fleet 7 Sq-2 Wing-A"]
      },
      "F7": {
        "means": "fleet=7",
        "tier": "strong",
        "example_records": ["MARTINEZ PFC F7/Sq1/B"]
      },
      "Sq-2": {
        "means": "squadron=2",
        "tier": "strong",
        "example_records": ["WONG CPL Sq-2"]
      }
    },
    "inferred": {
      "Seventh Fleet": {
        "means": "fleet=7",
        "tier": "moderate",
        "note": "Formal designation, not seen in examples"
      }
    },
    "ambiguous": {
      "3rd": "Could be squadron or element depending on context"
    }
  },

  "vocabulary": {
    "status": "complete",
    "observed": {
      "strong": ["Fleet 7", "F7", "Seventh"],
      "moderate": ["DefCom", "DC"],
      "weak": []
    },
    "inferred": {
      "strong": [],
      "moderate": ["patrol", "intercept"],
      "weak": ["perimeter", "defense grid"]
    }
  },

  "exclusions": {
    "status": "complete",
    "source": "hierarchy_derived",
    "rules": [
      {"if_contains": "laboratory", "then": "exclude", "reason": "term unique to resource_directorate"},
      {"if_contains": "settlement", "then": "exclude", "reason": "term unique to colonial_administration"},
      {"if_contains": "expedition", "then": "exclude", "reason": "term unique to expeditionary_corps"},
      {"if_depth": 3, "then": "exclude", "reason": "branch depth is 5"},
      {"if_contains": "Fleet 8", "then": "exclude", "reason": "designator does not exist in hierarchy"}
    ]
  },

  "differentiators": {
    "vs_resource_directorate_operation_7": {
      "status": "complete",
      "rival_sample_size": 423,
      "collision_point": "designator '7' shared at level 2",
      "positive_signals": [
        {
          "if_contains": "squadron or wing or element",
          "then": "increase_confidence",
          "target": "defense_command_fleet_7",
          "strength": "strong",
          "provenance": "structural"
        },
        {
          "if_contains": "facility or crew or laboratory",
          "then": "increase_confidence",
          "target": "resource_directorate_operation_7",
          "strength": "strong",
          "provenance": "structural"
        }
      ],
      "structural_rules": [
        {
          "if_depth": 5,
          "then": "identifies",
          "target": "defense_command_fleet_7",
          "strength": "definitive",
          "note": "Resource Directorate has depth 4"
        }
      ],
      "ambiguous_when": {
        "condition": "Only '7' present without level indicators or branch vocabulary",
        "example_patterns": ["assigned 7", "unit 7"],
        "recommendation": "cannot_determine"
      }
    },
    "vs_colonial_administration_district_7": {
      "status": "rival_undersampled",
      "rival_sample_size": 23,
      "rival_tier": "sparse",
      "structural_rules": [
        {
          "if_contains": "squadron or wing",
          "then": "identifies",
          "target": "defense_command_fleet_7",
          "strength": "definitive",
          "note": "Terms unique to Defense Command"
        },
        {
          "if_contains": "settlement or district",
          "then": "identifies",
          "target": "colonial_administration_district_7",
          "strength": "definitive",
          "note": "Terms unique to Colonial Administration"
        }
      ],
      "ambiguous_when": {
        "condition": "Only '7' present without branch-specific terms",
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
    "component_id": "expeditionary_corps_expedition_kestrel",
    "generated_utc": "2026-01-27T00:00:00Z",
    "tier": "sparse",
    "sample_size": 23,
    "pct_of_median": 16.2,
    "generation_mode": "hierarchy_only"
  },

  "structure": {
    "status": "complete",
    "branch": "expeditionary_corps",
    "depth": 3,
    "levels": ["sector", "expedition", "team"],
    "valid_designators": {
      "sector": ["alpha", "beta", "gamma"],
      "expedition": ["kestrel"],
      "team": ["A", "B", "C", "D"]
    },
    "structural_discriminators": [
      {"term": "expedition", "implies_branch": "expeditionary_corps", "strength": "definitive"},
      {"term": "team", "implies_branch": "expeditionary_corps", "strength": "moderate"}
    ]
  },

  "patterns": {
    "status": "not_generated",
    "reason": "insufficient_sample",
    "rebuild_when": "tier >= under_represented"
  },

  "vocabulary": {
    "status": "not_generated",
    "reason": "insufficient_sample",
    "known_aliases": ["Kestrel Expedition", "Exp-K"],
    "alias_source": "hierarchy_reference (not validated from data)"
  },

  "exclusions": {
    "status": "complete",
    "source": "hierarchy_derived",
    "rules": [
      {"if_contains": "squadron or wing or element", "then": "exclude", "reason": "terms unique to defense_command"},
      {"if_contains": "facility or crew or laboratory", "then": "exclude", "reason": "terms unique to resource_directorate"},
      {"if_contains": "settlement or district", "then": "exclude", "reason": "terms unique to colonial_administration"},
      {"if_depth": 4, "then": "exclude", "reason": "branch depth is 3"},
      {"if_depth": 5, "then": "exclude", "reason": "branch depth is 3"}
    ]
  },

  "differentiators": {
    "generation_mode": "hierarchy_only",
    "vs_defense_command_fleet_3": {
      "status": "hierarchy_only",
      "structural_rules": [
        {
          "if_contains": "expedition or team",
          "then": "identifies",
          "target": "expeditionary_corps_expedition_kestrel",
          "strength": "definitive",
          "note": "Terms unique to Expeditionary Corps"
        },
        {
          "if_contains": "squadron or wing or element",
          "then": "identifies",
          "target": "defense_command_fleet_3",
          "strength": "definitive",
          "note": "Terms unique to Defense Command"
        },
        {
          "if_depth": 5,
          "then": "identifies",
          "target": "defense_command_fleet_3",
          "strength": "definitive",
          "note": "Expeditionary Corps has depth 3"
        }
      ],
      "ambiguous_when": {
        "condition": "Only shared designator present without branch-specific terms or depth indicators",
        "recommendation": "cannot_determine"
      }
    }
  },

  "quality_notes": [
    "Sparse component - patterns and vocabulary not generated",
    "Structural disambiguation available via branch-unique terms and depth",
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

Resolver generation enforces grounded inference with provenance tracking to prevent LLM knowledge leakage:

### Core Principles

**1. Absence is NOT evidence** — Records lacking a term are uninformative, not negative signals. Clerks abbreviate; absence means nothing.

**2. Grounded claims only** — All patterns/vocabulary must be cited from example records OR explicitly marked as `inferred` (from LLM training knowledge).

**3. Ambiguity is valid** — Some records cannot be disambiguated. "Cannot determine" is an acceptable outcome. Do not force classification.

**4. Positive signals only** — Rules based on PRESENCE of terms, never ABSENCE:
- ✓ "Contains 'squadron'" → positive signal FOR Defense Command
- ✗ "Does NOT contain 'squadron'" → INVALID
- ✓ "Contains 'expedition'" (when expecting Defense Command) → conflict signal

### Provenance Tracking

**Observed** — Term appears in provided example records, can be cited
**Inferred** — Term from LLM training knowledge
**Structural** — Derived from hierarchy definition (branch-unique terms, depth constraints)

Downstream code can weight: `structural` (highest trust) > `observed` (high trust) > `inferred` (hint only)

### Confidence-Based Signals (Not Deterministic Rules)

```json
"positive_signals": [
  {"if_contains": "squadron or wing", "then": "increase_confidence", "target": "defense_command", "strength": "strong"}
],
"ambiguous_when": {
  "condition": "Only shared designator, no branch-specific terms",
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
- **Three-layer alignment:** Sampling and hard case criteria align with ADR-006 difficulty model
- **Branch-aware structure:** Heterogeneous hierarchy constraints encoded per ADR-007

---

## Tradeoffs

**Advantages:**
- Focused guidance for LLM
- Pre-learned pattern interpretations
- Explicit disambiguation rules via branch structure
- Quality-aware (knows its own limitations)
- Deterministic exclusions reduce LLM cost

**Disadvantages:**
- Requires generation workflow
- Resolvers must be regenerated if validation data changes
- More complex system
- Sparse components get limited benefit

---

## Key Design Questions (Resolved)

- [x] Resolver token budget (~500-600)? — Yes, target range
- [x] Generation workflow automation level? — Fully automated with LLM phases (except Phase 5)
- [x] Resolver versioning strategy? — Via resolver_registry.json with rebuild triggers
- [x] How to handle sparse components? — Hierarchy-only resolvers with quality flags
- [x] Quality tier filtering? — Removed; sample by soldier difficulty instead (ADR-009)
- [x] Value-based exclusions? — Removed; exclusions are deterministic from hierarchy (ADR-009)

## Key Design Questions (Open)

- [ ] Exact threshold percentiles (p25/median/p75) vs other methods?
- [ ] Minimum per-collision-pair sample size?
- [ ] LLM model selection for generation phases?
- [ ] Soldier difficulty computation specifics (complementarity formula)?

---

## Implementation Status

**Requires Updates for ADR-009:**

| Component | Status | Change Needed |
|-----------|--------|---------------|
| `sampling.py` | Needs update | Add `compute_soldier_difficulty()`, remove quality tier filtering |
| `structure.py` | Needs rewrite | Heterogeneous branches, structural discriminators |
| `llm_phases.py` | Needs update | Remove Phase 5 LLM call, remove quality tier filtering |
| `prompts.py` | Needs update | Three-layer hard case criteria |
| `assembler.py` | Needs update | New schema for structure/exclusions |

**Unchanged Components:**
| Component | Status | Location |
|-----------|--------|----------|
| Threshold Calculator | ✓ Complete | `src/strategies/resolver/generator/thresholds.py` |
| Dual-Run Orchestrator | ✓ Complete | `src/strategies/resolver/generator/dual_run.py` |
| Reconciliation | ✓ Complete | `src/strategies/resolver/generator/reconciliation.py` |
| Registry Manager | ✓ Complete | `src/strategies/resolver/generator/registry.py` |
| Main Orchestrator | ✓ Complete | `src/strategies/resolver/generator/generate.py` |
| Resolver Executor | ✓ Complete | `src/strategies/resolver/executor/strategy.py` |
| Token Budget Batcher | ✓ Complete | `src/utils/llm/token_batcher.py` |

---

## Module Specifications

### Module 1: Threshold Calculator

**File:** `src/strategies/resolver/generator/thresholds.py`
**Status:** Complete (no changes needed)

### Module 2: Structure Extractor

**File:** `src/strategies/resolver/generator/structure.py`
**Status:** Needs rewrite for ADR-009

```python
@dataclass
class BranchStructure:
    branch_id: str
    depth: int
    levels: List[str]  # e.g., ["sector", "fleet", "squadron", "wing", "element"]
    valid_designators: Dict[str, List[Union[int, str]]]  # level -> valid values

@dataclass
class ComponentStructure:
    component_id: str
    branch: BranchStructure
    path: Dict[str, Union[int, str]]  # level -> assigned value
    structural_discriminators: List[Dict]  # terms unique to this branch

@dataclass
class StructureResult:
    structures: Dict[str, ComponentStructure]
    branch_structures: Dict[str, BranchStructure]
    collisions: Dict[Tuple, Set[str]]  # (level, value) -> {component_ids}
    exclusion_rules: Dict[str, List[Dict]]  # component_id -> exclusion rules

def extract_structure(hierarchy_path: Path) -> StructureResult:
    """
    Extract branch-aware structures, collisions, and exclusion rules.
    Handles heterogeneous hierarchy depths (3-5 levels).
    """
```

### Module 3: Collision Sampler

**File:** `src/strategies/resolver/generator/sampling.py`
**Status:** Needs update for ADR-009

```python
@dataclass
class DifficultyAssessment:
    soldier_id: str
    collision_position: bool
    complementarity_score: float  # 0.0-1.0
    structural_resolvability: bool
    difficulty_tier: str  # easy | moderate | hard | extreme

def compute_soldier_difficulty(
    soldier_id: str,
    records: pd.DataFrame,
    collisions: Dict[Tuple, Set[str]],
    hierarchy: StructureResult,
) -> DifficultyAssessment:
    """Assess soldier's assignment difficulty across layers."""

@dataclass
class CollisionSample:
    component_a: str
    component_b: str
    soldiers_a: List[str]
    soldiers_b: List[str]
    records_a: pd.DataFrame  # ALL records for sampled soldiers
    records_b: pd.DataFrame
    difficulty_distribution_a: Dict[str, int]  # tier -> count
    difficulty_distribution_b: Dict[str, int]
    undersampled_a: bool
    undersampled_b: bool

def sample_collisions(
    train_df: pd.DataFrame,
    raw_df: pd.DataFrame,
    collisions: Dict[Tuple, Set[str]],
    thresholds: ThresholdResult,
    samples_per_side: int = 20,
    prioritize_difficulty: List[str] = ["hard", "extreme"],
) -> Dict[Tuple[str, str], CollisionSample]:
    """
    Sample soldiers for collision analysis.
    Prioritizes soldiers with high assignment difficulty.
    Includes ALL records for sampled soldiers (no quality tier filtering).
    """
```

### Module 4: LLM Phases Orchestrator

**File:** `src/strategies/resolver/generator/llm_phases.py`
**Status:** Needs update for ADR-009

**Changes:**
- Remove `_filter_records_by_quality()`
- Phase 5 becomes non-LLM (calls `structure.compute_exclusions()`)
- Update hard case flagging to three-layer criteria

```python
def discover_patterns(component_id, collision_samples, llm, tier) -> PatternResult:
    """Discover text patterns. Records not filtered by quality tier."""

def compute_exclusions(component_id, structure_result) -> ExclusionResult:
    """
    Derive exclusion rules deterministically from hierarchy.
    NO LLM CALL.
    """

def discover_vocabulary(component_id, train_df, raw_df, llm, tier) -> VocabularyResult:
    """Discover characteristic vocabulary. Records not filtered by quality tier."""

def generate_differentiators(...) -> Dict[str, DifferentiatorResult]:
    """Generate rival-specific disambiguation rules."""
```

### Module 5: Registry Manager

**File:** `src/strategies/resolver/generator/registry.py`
**Status:** Complete (no changes needed)

### Module 6: Resolver Assembler

**File:** `src/strategies/resolver/generator/assembler.py`
**Status:** Needs update for new schema

### Module 7: Main Orchestrator

**File:** `src/strategies/resolver/generator/generate.py`
**Status:** Complete (workflow unchanged, modules updated)

---

## References

- Architecture: `docs/architecture/CURRENT.md`
- ADR-002: LLM Batching Statefulness
- ADR-005: Grounded Inference
- ADR-006: Three-Layer Difficulty Model
- ADR-007: Synthetic Data Redesign (Terraform Combine domain)
- ADR-009: Resolver Generation Alignment
- Hierarchy Reference: `config/hierarchies/hierarchy_reference.json`
- Comparison: `docs/components/strategies/_comparison/CURRENT.md`
