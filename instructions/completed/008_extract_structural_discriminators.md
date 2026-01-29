# Instruction: Build `extract_structural_discriminators()`

**Priority:** High — foundational for difficulty model and resolver Phase 5
**Execution Mode:** Sonnet, thinking on
**Rationale:** Requires understanding domain model; some design decisions embedded in spec

---

## Context and Rationale

### Why This Exists

The disambiguation system needs to answer: **"Given a soldier's extracted values, can we eliminate all but one candidate branch?"**

Two consumers need this:

| Consumer | Question | Uses Output For |
|----------|----------|-----------------|
| **Difficulty Model** | Is this soldier structurally resolvable? | `structural_resolvability` boolean in difficulty assessment |
| **Resolver Phase 5** | What exclusion rules apply to this component? | Deterministic exclusion rules in resolver JSON |

Both depend on knowing which terms, designators, and structural features are unique to which branches. This utility computes that mapping once from the hierarchy definition, avoiding redundant computation and ensuring consistency.

### Where It Fits

```
config/hierarchies/
├── hierarchy_reference.json      # INPUT: Branch definitions (human-authored)
└── structural_discriminators.json # OUTPUT: Derived discrimination rules (computed)
```

The output sits alongside its input because:
1. It's derived deterministically from hierarchy_reference.json
2. It should be regenerated whenever hierarchy_reference.json changes
3. Both are reference data consumed by multiple downstream systems

---

## Input Specification

**File:** `config/hierarchies/hierarchy_reference.json`

**Schema:**
```json
{
  "branch_id": {
    "depth": int,
    "levels": ["level_1", "level_2", ...],
    "valid_designators": {
      "level_1": ["alpha", "beta", ...] | [1, 2, 3, ...],
      "level_2": [...]
    }
  },
  ...
}
```

**Example (Terraform Combine domain):**
```json
{
  "branches": {
    "defense_command": {
      "depth": 5,
      "levels": ["sector", "fleet", "squadron", "wing", "element"],
      "valid_designators": {
        "sector": ["alpha", "beta", "gamma"],
        "fleet": [1, 2, 3, 4, 5, 6, 7],
        "squadron": [1, 2, 3],
        "wing": ["A", "B", "C", "D"],
        "element": [1, 2, 3, 4]
      }
    },
    "resource_directorate": {
      "depth": 4,
      "levels": ["sector", "division", "bureau", "unit"],
      "valid_designators": {
        "sector": ["alpha", "beta", "gamma"],
        "division": [1, 2, 3, 4, 5],
        "bureau": ["logistics", "procurement", "maintenance"],
        "unit": [1, 2, 3]
      }
    },
    "colonial_administration": {
      "depth": 3,
      "levels": ["region", "district", "post"],
      "valid_designators": {
        "region": ["north", "south", "east", "west"],
        "district": [1, 2, 3, 4, 5, 6],
        "post": ["A", "B", "C"]
      }
    }
  },
  "components": [
    "defense_command/alpha/3/2/A/1",
    "defense_command/alpha/3/2/A/2",
    "defense_command/alpha/3/2/B/1",
    "defense_command/alpha/5/1/A/1",
    "defense_command/beta/1/1/A/1",
    "resource_directorate/alpha/3/logistics/1",
    "resource_directorate/alpha/3/logistics/2",
    "resource_directorate/beta/2/procurement/1",
    "colonial_administration/north/1/A",
    "colonial_administration/north/2/B"
  ]
}
```

**Note:** The `components` array contains the full enumeration of actual components. The collision index is built from these actual paths, not just theoretical combinations of valid designators.

---

## Output Specification

**File:** `config/hierarchies/structural_discriminators.json`

**Schema:**
```json
{
  "metadata": {
    "generated_from": "hierarchy_reference.json",
    "generated_at": "ISO timestamp",
    "branches_analyzed": ["branch_1", "branch_2", ...]
  },
  
  "level_name_discriminators": {
    "term": {
      "unique_to": "branch_id" | null,
      "appears_in": ["branch_1", "branch_2", ...]
    }
  },
  
  "designator_discriminators": {
    "value": {
      "type": "alpha" | "numeric" | "word",
      "unique_to_branch": "branch_id" | null,
      "valid_in": {
        "branch_id": ["level_1", "level_2"],
        ...
      },
      "collision_levels": [["branch_1", "level_x"], ["branch_2", "level_y"]]
    }
  },
  
  "depth_discriminators": {
    "depth_value": {
      "branches": ["branch_1", "branch_2"],
      "is_unique": bool
    }
  },
  
  "branch_exclusion_rules": {
    "branch_id": [
      {
        "rule_type": "term_presence" | "designator_invalidity" | "depth_mismatch",
        "condition": "description of what triggers exclusion",
        "excludes_branch": "branch_id",
        "strength": "definitive" | "strong"
      }
    ]
  },
  
  "collision_index": {
    "(level_name, designator_value)": ["component_path_1", "component_path_2"]
  }
}
```

---

## Computation Logic

### Step 1: Parse Hierarchy Reference

Load and validate hierarchy_reference.json. Build internal representation:

```python
@dataclass
class BranchDef:
    branch_id: str
    depth: int
    levels: List[str]
    valid_designators: Dict[str, List[Union[str, int]]]
```

### Step 2: Compute Level Name Discriminators

For each level name across all branches, determine if it's unique:

```
level_names_by_branch = {
    "defense_command": {"sector", "fleet", "squadron", "wing", "element"},
    "resource_directorate": {"sector", "division", "bureau", "unit"},
    "colonial_administration": {"region", "district", "post"}
}

For each unique level name:
    appears_in = [branches where this name appears]
    if len(appears_in) == 1:
        unique_to = appears_in[0]
    else:
        unique_to = null
```

**Example output:**
```json
{
  "squadron": {"unique_to": "defense_command", "appears_in": ["defense_command"]},
  "wing": {"unique_to": "defense_command", "appears_in": ["defense_command"]},
  "bureau": {"unique_to": "resource_directorate", "appears_in": ["resource_directorate"]},
  "sector": {"unique_to": null, "appears_in": ["defense_command", "resource_directorate"]}
}
```

### Step 3: Compute Designator Discriminators

For each unique designator value across all branches:

1. Classify type: `alpha` (single letter), `numeric` (integer), `word` (multi-char string)
2. Find all (branch, level) pairs where this value is valid
3. Determine if unique to one branch

```
For value "A":
    valid_in = {
        "defense_command": ["wing"],
        "colonial_administration": ["post"]
    }
    unique_to_branch = null  # appears in multiple branches
    collision_levels = [["defense_command", "wing"], ["colonial_administration", "post"]]

For value "squadron":  # if appearing as a designator value
    valid_in = {...}
    # Note: This is different from "squadron" as a level NAME

For value 7:
    valid_in = {"defense_command": ["fleet"]}
    unique_to_branch = "defense_command"  # only valid in one branch
```

### Step 4: Compute Depth Discriminators

```
depths = {
    3: ["colonial_administration"],
    4: ["resource_directorate"],
    5: ["defense_command"]
}

For each depth:
    is_unique = len(branches) == 1
```

### Step 5: Generate Branch Exclusion Rules

For each branch, compile what signals would **exclude** it:

```python
def generate_exclusion_rules(branch_id: str, all_branches: Dict) -> List[Dict]:
    rules = []
    
    # Rule type 1: Term presence that excludes this branch
    for term, info in level_name_discriminators.items():
        if info["unique_to"] is not None and info["unique_to"] != branch_id:
            rules.append({
                "rule_type": "term_presence",
                "condition": f"contains term '{term}'",
                "excludes_branch": branch_id,
                "strength": "definitive"
            })
    
    # Rule type 2: Designator invalidity
    # If a value appears that isn't valid in this branch
    for value, info in designator_discriminators.items():
        if branch_id not in info["valid_in"]:
            if info["unique_to_branch"] is not None:
                rules.append({
                    "rule_type": "designator_invalidity",
                    "condition": f"contains designator '{value}' (only valid in {info['unique_to_branch']})",
                    "excludes_branch": branch_id,
                    "strength": "definitive"
                })
    
    # Rule type 3: Depth mismatch
    branch_depth = all_branches[branch_id].depth
    for depth, branches in depth_discriminators.items():
        if depth > branch_depth:
            rules.append({
                "rule_type": "depth_mismatch",
                "condition": f"path has {depth} levels (branch only has {branch_depth})",
                "excludes_branch": branch_id,
                "strength": "definitive"
            })
    
    return rules
```

### Step 6: Build Collision Index

The collision index maps (level, value) pairs to actual component paths where collisions occur:

```python
def build_collision_index(hierarchy: Dict) -> Dict[Tuple, Set[str]]:
    """
    Returns mapping of (level_name, designator_value) -> set of component paths
    where that combination appears.
    
    Only include entries where len(component_paths) > 1 (actual collisions).
    
    Example:
        Given components:
            "defense_command/alpha/3/2/A/1"
            "resource_directorate/alpha/3/logistics/1"
        
        Collision index includes:
            ("sector", "alpha") -> {"defense_command/alpha/3/2/A/1", "resource_directorate/alpha/3/logistics/1", ...}
            ("fleet", 3) -> {"defense_command/alpha/3/2/A/1", ...}  # if only defense_command uses "fleet"
            ("division", 3) -> {"resource_directorate/alpha/3/logistics/1", ...}
        
        The key insight: ("sector", "alpha") with value "3" at the next level
        genuinely collides because both components exist.
    """
    collision_index = defaultdict(set)
    
    for component_path in hierarchy["components"]:
        # Parse path into (branch, level_values...)
        parts = component_path.split("/")
        branch_id = parts[0]
        branch_def = hierarchy["branches"][branch_id]
        
        # Map each (level_name, value) to this component
        for i, level_name in enumerate(branch_def["levels"]):
            value = parts[i + 1]  # +1 because parts[0] is branch_id
            # Coerce to int if numeric
            if value.isdigit():
                value = int(value)
            collision_index[(level_name, value)].add(component_path)
    
    # Filter to only actual collisions (2+ components)
    return {k: v for k, v in collision_index.items() if len(v) > 1}
```

This uses the full component enumeration to identify **actual** collisions — component paths that genuinely share partial path segments and could be confused.

---

## Anti-Patterns

### Don't: Hardcode branch names or level names

The function must work for any hierarchy_reference.json structure, not just the Terraform Combine example. Branch names, level names, and designator values should all be discovered from the input.

### Don't: Assume uniform depth

Branches have different depths (3-5 levels). The logic must handle variable-length level lists.

### Don't: Conflate level names with designator values

"squadron" as a **level name** (in the `levels` array) is different from "squadron" as a **designator value** (in `valid_designators`). Track these separately.

### Don't: Generate rules that exclude based on absence

Exclusion rules should only fire on **presence** of discriminating signals. "Doesn't contain 'squadron'" is NOT a valid exclusion rule — the term might simply not appear in the record.

### Don't: Create circular dependencies

This utility should have no dependencies on:
- `sampling.py` (which consumes this output)
- `llm_phases.py` (which consumes this output)
- Any LLM calls

It's pure computation over the hierarchy definition.

---

## Decision Boundaries

### If hierarchy_reference.json has unexpected structure

Flag and fail gracefully. Don't attempt to guess structure. Required fields:

**Top level:**
- `branches` (dict of branch definitions)
- `components` (list of component path strings)

**Per branch:**
- `depth` (int)
- `levels` (list of strings)
- `valid_designators` (dict mapping level names to value lists)

### If a level name appears in `levels` but not in `valid_designators`

This is a validation error in the input. Log warning, skip that level for designator analysis, but include it for level name analysis.

### If designator values are mixed types (e.g., `[1, 2, "special"]`)

Handle gracefully. Classify each value individually. This is unusual but not invalid.

---

## File Location

```
src/preprocessing/hierarchy/
├── __init__.py
├── structural_discriminators.py   # <-- This module
└── README.md                      # Brief module documentation
```

**Rationale:** This is preprocessing/derivation work on hierarchy data, separate from the resolver strategy. It's consumed by multiple downstream systems.

---

## Function Signature

```python
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, List, Set, Tuple, Union, Optional
from datetime import datetime
import json

@dataclass
class StructuralDiscriminators:
    """Complete structural discrimination data derived from hierarchy."""
    
    metadata: Dict[str, any]
    level_name_discriminators: Dict[str, Dict]
    designator_discriminators: Dict[str, Dict]
    depth_discriminators: Dict[int, Dict]
    branch_exclusion_rules: Dict[str, List[Dict]]
    collision_index: Dict[Tuple[str, Union[str, int]], Set[str]]
    
    def to_json(self) -> Dict:
        """Serialize to JSON-compatible dict."""
        # Handle tuple keys in collision_index
        ...
    
    @classmethod
    def from_json(cls, data: Dict) -> "StructuralDiscriminators":
        """Deserialize from JSON dict."""
        ...


def extract_structural_discriminators(
    hierarchy_path: Path,
    output_path: Optional[Path] = None,
) -> StructuralDiscriminators:
    """
    Extract structural discrimination rules from hierarchy reference.
    
    Args:
        hierarchy_path: Path to hierarchy_reference.json
        output_path: If provided, write results to this path.
                     Defaults to hierarchy_path.parent / "structural_discriminators.json"
    
    Returns:
        StructuralDiscriminators dataclass with all derived rules
    
    Raises:
        ValueError: If hierarchy_reference.json is malformed
        FileNotFoundError: If hierarchy_path doesn't exist
    """
```

---

## Testing Strategy

### Unit Tests

**Test 1: Level name uniqueness**
```python
def test_level_name_discriminators():
    # Given hierarchy with "squadron" only in defense_command
    # When extract_structural_discriminators() runs
    # Then level_name_discriminators["squadron"]["unique_to"] == "defense_command"
```

**Test 2: Shared level names**
```python
def test_shared_level_names():
    # Given hierarchy with "sector" in multiple branches
    # When extract_structural_discriminators() runs
    # Then level_name_discriminators["sector"]["unique_to"] is None
    # And level_name_discriminators["sector"]["appears_in"] contains all branches
```

**Test 3: Actual collision detection from enumerated components**
```python
def test_actual_collisions():
    # Given components:
    #   "defense_command/alpha/3/2/A/1"
    #   "resource_directorate/alpha/3/logistics/1"
    # When extract_structural_discriminators() runs
    # Then collision_index[("sector", "alpha")] contains both component paths
    # And collision_index includes entries only where 2+ components share (level, value)
```

**Test 4: Depth-based exclusion rules**
```python
def test_depth_exclusion_rules():
    # Given colonial_administration has depth 3
    # When checking exclusion rules for colonial_administration
    # Then rule exists excluding it when path has 5 levels
```

**Test 5: Exclusion rule correctness**
```python
def test_exclusion_rules_are_definitive():
    # Given "squadron" unique to defense_command
    # When checking exclusion rules for resource_directorate
    # Then rule exists: if contains "squadron", exclude resource_directorate
    # And rule strength is "definitive"
```

### Integration Test

**Test: Round-trip serialization**
```python
def test_json_serialization():
    # Given extracted discriminators
    # When serialized to JSON and deserialized
    # Then result equals original
```

**Test: Output file generation**
```python
def test_output_file_written():
    # Given valid hierarchy_reference.json
    # When extract_structural_discriminators(path, output_path) runs
    # Then output_path exists and is valid JSON
```

### Test Data

Create a minimal test hierarchy in `tests/fixtures/test_hierarchy_reference.json`:
- `branches` dict with 2-3 branches of different depths
- `components` array with 10-15 enumerated component paths
- Some shared level names across branches, some unique
- Some shared designator values, some unique
- At least one numeric and one alpha designator type
- Components that create actual collisions (shared partial paths across branches)

---

## Acceptance Criteria

1. Function loads hierarchy_reference.json and produces StructuralDiscriminators
2. Level name discriminators correctly identify unique vs shared terms
3. Designator discriminators correctly classify types and find collisions
4. Depth discriminators correctly identify unique depths
5. Branch exclusion rules are generated for all branches
6. Collision index maps (level, value) pairs to component paths
7. Output JSON is written to correct location
8. All unit tests pass
9. No dependencies on sampling.py, llm_phases.py, or LLM calls

---

## References

- **DIFFICULTY_MODEL.md** — Consumer of this output for structural resolvability
- **ADR-009** — Decision that Phase 5 exclusions are deterministic from hierarchy
- **Resolver CURRENT.md** — Module 2 (Structure Extractor) consumes this output
- **GLOSSARY.md** — Term definitions (collision, structural resolvability, etc.)
