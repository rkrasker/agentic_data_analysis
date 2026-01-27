# ADR-009: Resolver Generation Alignment with Disambiguation Model

**Date:** 2026-01-27
**Status:** Accepted
**Scope:** architecture
**Supersedes:** Portions of ADR-002 (batching statefulness remains valid; sampling rationale updated)

## Context

The resolver generation process was designed before the three-layer disambiguation model (ADR-006) and domain decontamination (ADR-007) were adopted. Several assumptions in the original design conflict with the current conceptual framework:

1. **Quality tier filtering**: The old process filtered records by quality tier (favoring tiers 3-5) to "force subtle signal discovery." ADR-006 establishes that record quality (Layer 1) is orthogonal to assignment difficulty (Layers 2-3).

2. **Homogeneous hierarchy**: The old process assumed WWII-style uniform hierarchy (Division → Regiment → Battalion → Company). ADR-007 introduces heterogeneous branch structures with varying depths (3-5 levels).

3. **Value-based exclusion mining**: Phase 5 used LLM calls to mine "value-based" exclusions from data (e.g., "regiment 11 excludes 1st ID"). With synthetic data where hierarchy is complete by construction, these facts are deterministically derivable.

4. **Hard case criteria**: The old criteria were symptomatic ("transfer indicators present," "unusual notation") rather than structural (collision position, complementarity, structural ambiguity).

This ADR aligns resolver generation with the current disambiguation model while preserving resolver scope: **component discrimination and parsing aids**, not full-stack consolidation orchestration.

## Decision Drivers

1. **Resolvers have limited scope** — They help discriminate components and parse notation, not discover states or group records.

2. **Three-layer model is authoritative** — Difficulty is measured by collision position (Layer 2) and structural ambiguity (Layer 3), not record degradation (Layer 1).

3. **Hierarchy is ground truth** — In synthetic data, structural facts are known; mining them from data is redundant.

4. **Heterogeneous branches are real** — Terraform Combine has 4 branches with depths 3-5; structural encoding must handle this.

## Decisions

### Decision 1: Sample by Soldier Difficulty, Not Record Quality

**Old approach**: Filter to degraded records (tiers 3-5) assuming this surfaces subtle signals.

**New approach**: Sample soldiers by assignment difficulty (Layer 2-3), then include ALL their records regardless of quality tier.

**Assignment difficulty criteria**:
- **Collision position**: Soldier's component shares designators with other components
- **Non-complementary records**: Records provide overlapping (not additive) partial paths
- **Structural ambiguity**: Key designators don't resolve structurally (e.g., "3rd" could be battalion or regiment)

**Rationale**: A soldier with three pristine records all saying "3rd Regiment" in a collision zone is exactly what differentiator training needs. The old sampling would exclude those records because they're tier 1-2.

**Impact**:
- Remove `_filter_records_by_quality()` logic from `llm_phases.py`
- Add `compute_soldier_difficulty()` to `sampling.py`
- Sample soldiers where `difficulty_tier in ['hard', 'extreme']` for collision training
- Include all records for sampled soldiers

### Decision 2: Branch-Aware Structural Encoding

**Old approach**: Phase 1 extracted uniform hierarchy constraints (valid regiments, battalions, companies).

**New approach**: Phase 1 produces branch-specific structural constraints:

| Constraint Type | Example |
|-----------------|---------|
| Level names | "Squadron" only in Defense Command |
| Depth | 5-level path excludes Expeditionary Corps (depth 3) |
| Designator conventions | Letters at level 4 → constrains branch possibilities |
| Cross-branch exclusions | "Laboratory" → must be Resource Directorate |

**Schema change** — `structure` section gains branch awareness:

```json
{
  "structure": {
    "branch": "defense_command",
    "depth": 5,
    "levels": ["sector", "fleet", "squadron", "wing", "element"],
    "valid_designators": {
      "sector": ["alpha", "beta", "gamma"],
      "fleet": [1, 2, 3, 4, 5, 6, 7],
      "squadron": [1, 2, 3],
      "wing": ["A", "B", "C", "D"],
      "element": [1, 2, 3, 4]
    },
    "structural_discriminators": [
      {"term": "squadron", "implies_branch": "defense_command", "strength": "definitive"},
      {"term": "wing", "implies_branch": "defense_command", "strength": "strong"}
    ]
  }
}
```

**Impact**:
- Rewrite `structure.py` to parse heterogeneous hierarchy
- Add `structural_discriminators` extraction (terms unique to branch)
- Update `ComponentStructure` dataclass for variable depth

### Decision 3: Deterministic Exclusions (Phase 5 Simplification)

**Old approach**: Phase 5 had two sub-phases:
- `structural`: Derived from hierarchy (kept)
- `value_based`: Mined from data via LLM (removed)

**New approach**: Phase 5 becomes a deterministic computation with no LLM calls.

**Rationale**: "Regiment 11 isn't in 1st ID" is a structural fact derivable from `hierarchy_reference.json`. With synthetic data where hierarchy is complete by construction, mining this from data is backwards—if it's true, it's in the structure; if it's not in the structure, it shouldn't be in the data.

**What remains**:
- Branch-level exclusions: "Contains 'squadron' → excludes Colonial Administration"
- Depth exclusions: "5-level path → excludes 3-level branches"
- Designator exclusions: "Fleet 8 doesn't exist → excludes if present"

**Schema change** — `exclusions` section simplifies:

```json
{
  "exclusions": {
    "status": "complete",
    "source": "hierarchy_derived",
    "rules": [
      {"if_contains": "squadron", "then": "exclude", "reason": "term unique to defense_command"},
      {"if_contains": "laboratory", "then": "exclude", "reason": "term unique to resource_directorate"},
      {"if_depth": 5, "then": "exclude", "reason": "branch depth is 4"}
    ]
  }
}
```

**Impact**:
- Remove LLM call from Phase 5
- Remove `value_based` section from exclusions schema
- Implement `compute_exclusions()` as pure function over hierarchy

### Decision 4: Three-Layer Hard Case Criteria

**Old criteria** (symptomatic):
- Multiple component indicators present
- Key identifiers missing or ambiguous
- Unusual notation not matching known patterns
- Transfer indicators present

**New criteria** (structural, aligned with ADR-006):

| Criterion | Layer | Description |
|-----------|-------|-------------|
| Collision position | 2 | Soldier's partial path is non-unique across components |
| Non-complementary records | 2 | All records provide same ambiguous partial path |
| Structural ambiguity | 3 | Designators don't resolve structurally (e.g., "3rd" without context) |

**Removed**: "Transfer indicators present" — this is a state discovery problem, not component discrimination. Resolvers don't need to flag transfers; they need to flag "I can't tell which component this is."

**Impact**:
- Update hard case flagging prompts in `prompts.py`
- Hard case output should include which layer caused difficulty
- Reconciliation analyzes hard cases by layer, not symptom

## Consequences

### What Changes

| Component | Change |
|-----------|--------|
| `sampling.py` | Add `compute_soldier_difficulty()`, remove quality tier filtering |
| `structure.py` | Rewrite for heterogeneous branches, add structural discriminators |
| `llm_phases.py` | Remove Phase 5 LLM call, remove `_filter_records_by_quality()` |
| `prompts.py` | Update hard case criteria to three-layer model |
| `assembler.py` | Update schema for new structure/exclusions format |
| Resolver JSON schema | Branch-aware structure, simplified exclusions |

### What Stays the Same

- Resolvers remain component-centric artifacts
- Phase structure: 1 (structure), 2 (collisions), 3 (sampling), 4 (patterns), 6 (vocabulary), 7 (differentiators), 8 (tiers)
- Dual-run reconciliation for robustness (ADR-002)
- Collision-scoped sampling (correct in principle)
- Grounded inference philosophy (ADR-005)
- Registry and rebuild trigger system

### New Capabilities

- Resolvers can discriminate by branch structure, not just component vocabulary
- Depth mismatches are now explicit exclusion signals
- Hard case analysis reveals which disambiguation layer is failing
- Sampling targets genuinely hard soldiers, not just degraded records

## Implementation Notes

### Phase 5 Becomes Deterministic

```python
def compute_exclusions(
    component_id: str,
    hierarchy: HierarchyReference,
) -> ExclusionResult:
    """
    Derive exclusion rules from hierarchy structure.
    No LLM call required.
    
    Returns rules for:
    - Branch-unique terms that exclude this component
    - Depth mismatches
    - Invalid designators for this component
    """
```

### Soldier Difficulty Computation

```python
def compute_soldier_difficulty(
    soldier_id: str,
    records: pd.DataFrame,
    collisions: Dict[Tuple, Set[str]],
    hierarchy: HierarchyReference,
) -> DifficultyAssessment:
    """
    Assess soldier's assignment difficulty across layers.
    
    Returns:
    - collision_position: bool (is partial path in collision zone?)
    - complementarity_score: float (do records cover different path segments?)
    - structural_resolvability: bool (do constraints disambiguate?)
    - difficulty_tier: str (easy/moderate/hard/extreme)
    """
```

## References

- ADR-002: LLM Batching Statefulness (dual-run architecture preserved)
- ADR-005: Grounded Inference (provenance tracking preserved)
- ADR-006: Three-Layer Difficulty Model (source of Layer 1/2/3 framework)
- ADR-007: Synthetic Data Redesign (source of heterogeneous branches)
- CLAUDE.md: Core problem definition (state resolution scope)
- DISAMBIGUATION_MODEL.md: Three-layer analytical framework
