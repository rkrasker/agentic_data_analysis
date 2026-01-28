Instruction 009: Implement compute_soldier_difficulty()
Priority: High — unblocks sampling.py updates and resolver Phase 5 wiring
Estimated scope: New module with ~200-300 lines + tests

Context
The three-layer difficulty model (ADR-006, DIFFICULTY_MODEL.md) distinguishes record quality from resolution difficulty. A soldier with pristine records in a collision zone may be harder to disambiguate than one with degraded but structurally unique records.
This function operationalizes the difficulty model for sampling workflows. It computes three signals per soldier and assigns a difficulty tier (easy/moderate/hard/extreme).
Key references:

DIFFICULTY_MODEL.md — authoritative specification for signals, thresholds, edge cases
ADR-009 — alignment rationale and DifficultyAssessment schema
config/hierarchies/structural_discriminators.json — pre-computed collision index and branch exclusion rules


Task
Implement a difficulty computation module at src/preprocessing/difficulty/.
Module Structure
src/preprocessing/difficulty/
├── __init__.py
├── compute.py          # Core computation logic
└── loader.py           # Load structural_discriminators.json, canonical.parquet
Public Interface
Single-soldier function:
pythondef compute_soldier_difficulty(
    soldier_id: str,
    records: pd.DataFrame,  # All records for this soldier
    structural_discriminators: dict,  # Loaded from JSON
    hierarchy_reference: dict,  # Loaded from hierarchy_reference.json
) -> DifficultyAssessment
Batch function:
pythondef compute_all_soldier_difficulties(
    canonical_df: pd.DataFrame,  # Full canonical.parquet
    structural_discriminators: dict,
    hierarchy_reference: dict,
) -> pd.DataFrame  # One row per soldier with difficulty fields
```

Batch function groups by `soldier_id` and calls single-soldier function internally.

---

## Computed Signals

Implement exactly as specified in DIFFICULTY_MODEL.md:

### 1. Collision Position (bool)

- Extract all (level, value) pairs from the soldier's records
- Check each pair against the collision index in `structural_discriminators.json`
- Return `True` if any pair maps to 2+ components

**Column discovery:** Inspect `canonical.parquet` to identify characterized columns (pattern:value pairs) and uncharacterized columns (raw extractions). The conceptual names in DIFFICULTY_MODEL.md are illustrative; actual column names may differ.

### 2. Complementarity Score (float, 0.0–1.0)

Apply confidence weights:

| Extraction Type | Confidence |
|-----------------|------------|
| Characterized (regex matched pattern + value) | 1.0 |
| Uncharacterized, valid at exactly one level | 0.75 |
| Uncharacterized, valid at multiple levels | 0.25 |
| Uncharacterized, valid at no level | 0.0 (exclude) |

Aggregation:
1. Per-level: max confidence across all records for that soldier
2. Per-soldier: sum of level confidences / min(branch_depth, 4)

**Multi-branch collisions:** When soldier could belong to multiple branches, compute complementarity for each candidate branch, take maximum.

### 3. Structural Resolvability (bool)

Return `True` if extractions eliminate all but one candidate branch via:
- Designator invalidity (value doesn't exist in branch)
- Discriminating terms (term unique to one branch)
- Depth mismatch (extracted depth excludes branches)

Use `branch_exclusion_rules` from `structural_discriminators.json`.

---

## Difficulty Tiers

Implement the decision tree from DIFFICULTY_MODEL.md:
```
Is soldier in collision zone?
├── NO → Easy
└── YES → 
    ├── Structurally resolvable? YES → Moderate
    └── NO → Check complementarity
        ├── ≥ 0.7  → Moderate
        ├── 0.4–0.7 → Hard
        └── < 0.4  → Extreme

Output Schema
python@dataclass
class DifficultyAssessment:
    soldier_id: str
    collision_position: bool
    complementarity_score: float
    structural_resolvability: bool
    difficulty_tier: str  # "easy" | "moderate" | "hard" | "extreme"
    
    # Diagnostics
    candidate_branches: List[str]
    level_confidences: Dict[str, float]
    eliminating_constraints: List[str]  # Empty if not resolvable
For batch output, flatten to DataFrame columns.

Edge Cases
Handle per DIFFICULTY_MODEL.md:
CaseHandlingNo extractable valuescomplementarity = 0.0 → likely ExtremeRecords point to contradictory branchescomplementarity = 0.0 for any single-branch interpretationGround-truth component collides but extracted values don'tNot in collision position (extraction-based)Uncharacterized value valid in no branchExclude from calculation

File Dependencies
Inputs:

data/processed/canonical.parquet — soldier records with extractions
config/hierarchies/structural_discriminators.json — collision index, exclusion rules
config/hierarchies/hierarchy_reference.json — branch structures, valid designators

Outputs:

DifficultyAssessment objects (single) or DataFrame (batch)


Testing Requirements
Create tests/test_difficulty_compute.py:

Easy case: Soldier with extractions not in collision index
Moderate (resolvable): Soldier in collision but discriminating term present
Moderate (high complementarity): Soldier in collision, complementarity ≥ 0.7
Hard: Soldier in collision, complementarity 0.4–0.7, not resolvable
Extreme: Soldier in collision, complementarity < 0.4
Edge — no extractions: Returns Extreme
Edge — multi-branch collision: Uses max complementarity across candidates
Batch function: Correctly groups and processes multiple soldiers

Use test fixtures with minimal synthetic data, not full canonical.parquet.

Anti-Patterns

Don't filter by record quality tier. Include all records for the soldier regardless of quality.
Don't hardcode column names. Discover characterized vs uncharacterized columns from the parquet schema.
Don't recompute the collision index. Load from structural_discriminators.json.
Don't use percentile-based thresholds. Use fixed thresholds (0.7, 0.4) as specified.


Decision Boundaries
If you encounter:

Column names that don't clearly map to "characterized" vs "uncharacterized" — flag for review, document assumptions
structural_discriminators.json missing expected keys — fail loudly, don't assume defaults
Ambiguity about which branch depth to use for denominator — use candidate branches' depths, take max complementarity


Success Criteria

 Module structure created at src/preprocessing/difficulty/
 Single-soldier function implements all three signals correctly
 Batch function returns DataFrame suitable for sampling workflows
 All 8+ test cases pass
 No hardcoded column names
 Loads pre-computed collision index (doesn't recompute)


References

DIFFICULTY_MODEL.md — primary specification
ADR-006 — three-layer model rationale
ADR-009 — alignment with resolver generation
src/preprocessing/hierarchy/structural_discriminators.py — produces the JSON this consumes
SESSION_STATE.md — task dependency context