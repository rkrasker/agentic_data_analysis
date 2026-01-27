# Difficulty Model

This document specifies how to compute soldier-level difficulty for sampling, stratification, and evaluation. It operationalizes the three-layer framework from [DISAMBIGUATION_MODEL.md](DISAMBIGUATION_MODEL.md).

**See also:** `DISAMBIGUATION_MODEL.md` for conceptual framework, `ADR-006` for the principle that record quality ≠ resolution difficulty, `ADR-009` for resolver generation alignment.

---

## Purpose

The difficulty model answers: **"How hard is this soldier to disambiguate?"**

This is distinct from record quality (Layer 1). A soldier with pristine records in a collision zone may be harder than a soldier with degraded records that are structurally unique.

### Use Cases

| Component | Usage |
|-----------|-------|
| Resolver sampling | Prioritize hard/extreme soldiers in collision-scoped samples |
| Strategy evaluation | Report accuracy by difficulty tier |
| Synthetic data generation | Control difficulty distribution |
| Cross-strategy comparison | Ensure strategies are tested on comparable difficulty mixes |

---

## Inputs

### canonical.parquet

Regex-parsed records with characterized and uncharacterized extractions:

```
soldier_id: str
state_id: str
raw_text: str

# Characterized extractions (regex recognized pattern + value)
Unit_Term_Digit_Term:Pair: array    # e.g., ["Fleet:3"]
Unit_Term_Alpha_Term:Pair: array    # e.g., ["Wing:A"]
Alpha_Digit:Pair: array             # e.g., ["B:3"]
...

# Uncharacterized extractions (value extracted, pattern unknown)
Unchar_Alpha: array                 # e.g., ["A", "E", "B"]
Unchar_Digits: array                # e.g., ["3", "3", "3"]
```

### hierarchy_reference.json

Branch structures with valid designators per level:

```json
{
  "defense_command": {
    "depth": 5,
    "levels": ["sector", "fleet", "squadron", "wing", "element"],
    "valid_designators": {
      "sector": ["alpha", "beta", "gamma"],
      "fleet": [1, 2, 3, 4, 5, 6, 7],
      "squadron": [1, 2, 3],
      "wing": ["A", "B", "C", "D"],
      "element": [1, 2, 3, 4]
    },
    "discriminating_terms": ["squadron", "wing"]
  },
  ...
}
```

### Collision Index

Output from `extract_structure()` — maps (level, value) pairs to component sets:

```python
collisions: Dict[Tuple[str, Any], Set[str]]
# e.g., {("fleet", 3): {"defense_command_alpha_3", "resource_directorate_alpha_3"}}
```

---

## Computed Signals

### 1. Collision Position (Boolean)

**Question:** Is the soldier's extracted partial path ambiguous?

**Computation:** 
1. Extract all (level, value) pairs from characterized columns
2. For uncharacterized values, speculatively assign to levels where valid
3. Check if any extracted pair appears in the collision index
4. Soldier is "in collision" if any pair maps to 2+ components

**Note:** This is based on extracted values, not ground-truth component membership. A soldier in a colliding component whose records contain a discriminating term is not in collision position.

### 2. Complementarity Score (0.0–1.0)

**Question:** How much of the hierarchy path do the soldier's records collectively cover?

#### Confidence Weights

| Extraction Type | Confidence | Example |
|-----------------|------------|---------|
| Characterized | 1.0 | `Unit_Term_Digit_Term:Pair = "Fleet:3"` |
| Uncharacterized, matches exactly one level | 0.75 | `Unchar_Alpha: ["A"]` where "A" valid only at wing |
| Uncharacterized, matches multiple levels | 0.25 | `Unchar_Digits: ["3"]` where "3" valid at fleet/squadron/element |
| Uncharacterized, matches no valid designator | 0.0 | Excluded from calculation |

#### Aggregation

1. **Per-level:** Take max confidence across all records for that soldier
2. **Per-soldier:** Sum level confidences / min(branch_depth, 4)

The denominator cap at 4 prevents penalizing soldiers in deep hierarchies with micro-levels (fire teams, squads) that may not appear in formal records.

#### Multi-Branch Collisions

When a soldier is in a collision spanning multiple branches:
1. Compute complementarity separately for each candidate branch
2. Take the maximum

Rationale: We want the best-case interpretation. If even the most favorable reading has low complementarity, the soldier is genuinely hard.

#### Example

Soldier in 5-level Defense Command branch (denominator = 4):

| Record | Fleet | Squadron | Wing | Element |
|--------|-------|----------|------|---------|
| Record 1: `Unchar_Digits: ["3"]` | 0.25 | 0.25 | — | 0.25 |
| Record 2: `Unit_Term_Digit_Term: "Fleet:3"` | 1.0 | — | — | — |
| Record 3: `Unchar_Alpha: ["A"]` | — | — | 0.75 | — |
| **Aggregated** | **1.0** | **0.25** | **0.75** | **0.25** |

```
complementarity = (1.0 + 0.25 + 0.75 + 0.25) / 4 = 0.5625
```

### 3. Structural Resolvability (Boolean)

**Question:** Do hierarchy constraints eliminate all but one candidate branch?

**TRUE when** extractions eliminate all but one candidate via:

| Mechanism | Example |
|-----------|---------|
| Designator invalidity | "8" extracted but max fleet is 7 in one branch |
| Discriminating terms | "squadron" appears → only Defense Command |
| Depth mismatch | 5 levels extracted → excludes 3-level branches |

The same extraction work that feeds complementarity also feeds structural resolvability.

---

## Difficulty Tiers

```
Not in collision zone        → Easy
In collision + resolvable    → Moderate
In collision + comp ≥ 0.7    → Moderate
In collision + comp 0.4–0.7  → Hard
In collision + comp < 0.4    → Extreme
```

### Decision Tree

```
Is soldier in collision zone?
├── NO → Easy
└── YES → 
    ├── Structurally resolvable?
    │   ├── YES → Moderate
    │   └── NO → Check complementarity
    │       ├── ≥ 0.7  → Moderate
    │       ├── 0.4–0.7 → Hard
    │       └── < 0.4  → Extreme
```

Structural resolvability is a **rescue mechanism**. If the records themselves disambiguate the branch via constraints, that's easier than having high complementarity but remaining in collision.

---

## Edge Cases

| Case | Handling |
|------|----------|
| No extractable values (all arrays empty) | Contributes 0 to complementarity → likely Extreme |
| Records point to different branches | Complementarity = 0 for any single-branch interpretation (contradictory records) |
| Ground-truth component collides but records don't | Not in collision position (extraction-based, not membership-based) |
| Uncharacterized value valid in no branch | Excluded from calculation (confidence = 0) |

---

## Output Schema

```python
@dataclass
class DifficultyAssessment:
    soldier_id: str
    collision_position: bool
    complementarity_score: float  # 0.0–1.0
    structural_resolvability: bool
    difficulty_tier: str  # easy | moderate | hard | extreme
    
    # Diagnostic fields
    candidate_branches: List[str]  # branches not yet eliminated
    level_confidences: Dict[str, float]  # per-level max confidence
    eliminating_constraints: List[str]  # what eliminated branches (if resolvable)
```

---

## Thresholds

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| Complementarity "high" | ≥ 0.7 | ~3 of 4 levels covered with reasonable confidence |
| Complementarity "low" | < 0.4 | Less than 2 levels covered |
| Depth cap | 4 | Prevents micro-level penalty; conservative toward harder tiers |
| Characterized confidence | 1.0 | Regex recognized both pattern and value |
| Single-level unchar confidence | 0.75 | Value unambiguously maps to one level |
| Multi-level unchar confidence | 0.25 | Value could be multiple levels; weak signal |

Thresholds are fixed, not percentile-based. This ensures "extreme" reflects genuinely pathological cases regardless of data distribution.

---

## References

- [DISAMBIGUATION_MODEL.md](DISAMBIGUATION_MODEL.md) — Three-layer conceptual framework
- [GLOSSARY.md](GLOSSARY.md) — Term definitions
- [ADR-006](architecture/decisions/ADR-006_per-record-vs-per-soldier-difficulty.md) — Record quality ≠ resolution difficulty
- [ADR-009](architecture/decisions/ADR-009_resolver-generation-alignment.md) — Resolver alignment with difficulty model
