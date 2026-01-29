# 013: Branch-Aware Structural Encoding

**Status:** active
**Created:** 2026-01-29
**Component:** src/strategies/resolver/generator/

## Context

ADR-009 Decision 2 specifies that Phase 1 (structure extraction) must produce branch-specific structural constraints. The current implementation assumes uniform hierarchy (Division → Regiment → Battalion → Company), but the Terraform Combine domain has 4 branches with depths 3-5:

| Branch | Depth | Level Names |
|--------|-------|-------------|
| Defense Command | 5 | sector, fleet, squadron, wing, element |
| Colonial Administration | 4 | region, district, office, post |
| Resource Directorate | 4 | division, bureau, section, unit |
| Expeditionary Corps | 3 | force, group, team |

The resolver needs to understand these heterogeneous structures to generate correct exclusion rules and differentiators.

## Task

Rewrite structure.py to handle heterogeneous branch structures with variable depths and branch-specific level names.

## Scope

- **Working in:** `src/strategies/resolver/generator/structure.py`, `src/strategies/resolver/generator/assembler.py`
- **Reference:** `docs/architecture/decisions/ADR-009_resolver-generation-alignment.md`, `config/hierarchies/hierarchy_reference.json`
- **Config inputs:** `config/hierarchies/hierarchy_reference.json`, `config/hierarchies/structural_discriminators.json`
- **Test location:** `tests/strategies/resolver/generator/`
- **Ignore:** `.project_history/`, LLM phases, sampling logic

## Inputs

| File | Purpose |
|------|---------|
| `config/hierarchies/hierarchy_reference.json` | Full branch structures, valid designators per level |
| `config/hierarchies/structural_discriminators.json` | Branch-unique terms, collision index |

## Outputs

### Updated ComponentStructure Dataclass

```python
@dataclass
class ComponentStructure:
    component_id: str
    component_name: str
    branch: str                          # NEW: defense_command, colonial_admin, etc.
    depth: int                           # NEW: 3-5 depending on branch
    level_names: List[str]               # NEW: ["sector", "fleet", "squadron", "wing", "element"]
    valid_designators: Dict[str, List]   # NEW: {level_name: [valid_values]}
    structural_discriminators: List[Dict] # NEW: terms unique to this branch

    # DEPRECATED (remove or keep for backward compat):
    # valid_regiments, valid_battalions, valid_companies
```

### Updated Resolver JSON Schema

```json
{
  "structure": {
    "status": "complete",
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

## Implementation Steps

### Step 1: Update ComponentStructure dataclass

In `structure.py`, update the dataclass:

```python
@dataclass
class ComponentStructure:
    """Structure information for a single component.

    Supports heterogeneous branches with variable depths (ADR-009).
    """
    component_id: str
    component_name: str

    # Branch-aware fields (ADR-009)
    branch: str
    depth: int
    level_names: List[str]
    valid_designators: Dict[str, List[Union[str, int]]]
    structural_discriminators: List[Dict[str, str]]

    # Legacy fields - keep for backward compatibility during transition
    # Remove in future cleanup
    battalion_designator_type: str = "unknown"
```

### Step 2: Rewrite extract_structure()

The current function assumes regiment/battalion/company. Rewrite to:

```python
def extract_structure(
    component_id: str,
    hierarchy_reference: dict,
    structural_discriminators: dict,
) -> ComponentStructure:
    """
    Extract branch-aware structure for a component.

    Args:
        component_id: The component to extract structure for
        hierarchy_reference: Full hierarchy from hierarchy_reference.json
        structural_discriminators: From structural_discriminators.json

    Returns:
        ComponentStructure with branch-specific level names and valid designators
    """
    # 1. Find this component in hierarchy
    component_data = find_component(component_id, hierarchy_reference)

    # 2. Determine branch
    branch = component_data["branch"]

    # 3. Get branch structure (depth, level names)
    branch_structure = hierarchy_reference["branches"][branch]
    depth = branch_structure["depth"]
    level_names = branch_structure["levels"]  # e.g., ["sector", "fleet", ...]

    # 4. Extract valid designators per level for this component
    valid_designators = {}
    for level_name in level_names:
        valid_designators[level_name] = extract_valid_values_for_level(
            component_id, level_name, hierarchy_reference
        )

    # 5. Get structural discriminators for this branch
    branch_discriminators = [
        d for d in structural_discriminators.get("branch_exclusion_rules", [])
        if d.get("implies_branch") == branch
    ]

    return ComponentStructure(
        component_id=component_id,
        component_name=component_data["name"],
        branch=branch,
        depth=depth,
        level_names=level_names,
        valid_designators=valid_designators,
        structural_discriminators=branch_discriminators,
    )
```

### Step 3: Add helper functions

```python
def find_component(component_id: str, hierarchy: dict) -> dict:
    """Find component data in hierarchy, return with branch info."""
    # Implementation depends on hierarchy_reference.json structure
    # Should return {"name": "...", "branch": "...", "path": [...], ...}

def extract_valid_values_for_level(
    component_id: str,
    level_name: str,
    hierarchy: dict,
) -> List[Union[str, int]]:
    """Extract valid designator values for a specific level within this component's subtree."""
    # Walk the component's children to find valid values at this level
```

### Step 4: Update extract_all_structures()

```python
def extract_all_structures(
    hierarchy_path: Path = None,
    discriminators_path: Path = None,
) -> StructureResult:
    """
    Extract structures for all components in hierarchy.

    Returns StructureResult with:
    - structures: Dict[component_id, ComponentStructure]
    - collision_map: loaded from structural_discriminators.json
    """
    hierarchy = load_hierarchy_reference(hierarchy_path)
    discriminators = load_structural_discriminators(discriminators_path)

    structures = {}
    for component_id in get_all_component_ids(hierarchy):
        structures[component_id] = extract_structure(
            component_id, hierarchy, discriminators
        )

    # Collision map comes from precomputed discriminators
    collision_map = discriminators.get("collision_index", {})

    return StructureResult(
        structures=structures,
        collision_map=collision_map,
    )
```

### Step 5: Update StructureResult if needed

```python
@dataclass
class StructureResult:
    structures: Dict[str, ComponentStructure]
    collision_map: Dict[Tuple[str, str], Set[str]]  # (level, value) -> component_ids

    # NEW: branch metadata for cross-branch operations
    branches: Dict[str, Dict]  # branch_name -> {depth, levels, ...}
```

### Step 6: Update assembler.py

In `_build_structure_section()`:

```python
def _build_structure_section(structure: ComponentStructure) -> dict:
    """Build structure section for resolver JSON.

    New schema (ADR-009): Branch-aware with variable depth.
    """
    return {
        "status": "complete",
        "branch": structure.branch,
        "depth": structure.depth,
        "levels": structure.level_names,
        "valid_designators": structure.valid_designators,
        "structural_discriminators": structure.structural_discriminators,
    }
```

### Step 7: Update get_structural_exclusions()

This function needs to work with the new structure:

```python
def get_structural_exclusions(
    component_id: str,
    structure: ComponentStructure,
    all_structures: Dict[str, ComponentStructure],
) -> List[Dict]:
    """
    Generate exclusion rules based on branch structure.

    Rules:
    - Branch mismatch: terms unique to other branches
    - Depth mismatch: paths of wrong depth
    - Service type (if applicable)
    """
    rules = []

    # Branch-unique term exclusions
    for other_id, other_struct in all_structures.items():
        if other_struct.branch != structure.branch:
            for disc in other_struct.structural_discriminators:
                rules.append({
                    "if_contains": disc["term"],
                    "then": "exclude",
                    "reason": f"term unique to {other_struct.branch}"
                })

    # Depth mismatch exclusions
    for other_id, other_struct in all_structures.items():
        if other_struct.depth != structure.depth:
            rules.append({
                "if_depth": other_struct.depth,
                "then": "exclude",
                "reason": f"branch depth is {structure.depth}"
            })

    return rules
```

### Step 8: Update any callers

Search for usages of:
- `structure.valid_regiments`
- `structure.valid_battalions`
- `structure.valid_companies`
- `structure.battalion_designator_type`

Update to use the new `valid_designators[level_name]` pattern.

## Acceptance Criteria

- [ ] `ComponentStructure` has branch, depth, level_names, valid_designators fields
- [ ] `extract_structure()` correctly parses hierarchy_reference.json for any branch
- [ ] Defense Command components have depth=5, correct level names
- [ ] Colonial Administration components have depth=4, correct level names
- [ ] Expeditionary Corps components have depth=3, correct level names
- [ ] `structural_discriminators` populated from structural_discriminators.json
- [ ] Resolver JSON uses new schema with branch-aware structure
- [ ] `get_structural_exclusions()` generates branch/depth mismatch rules
- [ ] Tests pass in `tests/strategies/resolver/generator/`
- [ ] No regressions in collision detection

## Notes

### Code Style

Follow `docs/CODE_STYLE.md`:
- Keep `ComponentStructure` as a dataclass (it holds structured data)
- Helper functions should be module-level, not class methods
- Don't create a `BranchStructure` class unless needed—dict is fine

### Hierarchy Reference Format

Before implementing, inspect `config/hierarchies/hierarchy_reference.json` to understand its actual structure. The implementation above assumes a format like:

```json
{
  "branches": {
    "defense_command": {
      "depth": 5,
      "levels": ["sector", "fleet", "squadron", "wing", "element"]
    }
  },
  "components": {
    "alpha_sector_fleet_1": {
      "branch": "defense_command",
      "path": ["alpha", 1, null, null, null]
    }
  }
}
```

Adapt the implementation to match the actual format.

### Backward Compatibility

- Keep `battalion_designator_type` temporarily for any code that still uses it
- Old resolvers in `config/resolvers/` will have the old schema—they'll be regenerated
- If prompts reference "regiment/battalion/company", they may need updates (out of scope for this instruction, but note it)

### Testing Strategy

Create test cases for:
1. Defense Command component (5-level)
2. Expeditionary Corps component (3-level)
3. Component in collision zone
4. Cross-branch exclusion generation

Use fixtures, not full hierarchy_reference.json.

## References

- ADR-009: `docs/architecture/decisions/ADR-009_resolver-generation-alignment.md` (Decision 2)
- Hierarchy reference: `config/hierarchies/hierarchy_reference.json`
- Structural discriminators: `config/hierarchies/structural_discriminators.json`
- Current structure.py: `src/strategies/resolver/generator/structure.py`
