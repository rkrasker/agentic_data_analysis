# -*- coding: utf-8 -*-
"""
Extract structural discrimination rules from hierarchy reference.

This module computes discrimination rules that identify which structural features
(level names, designator values, depths) are unique to specific branches. These
rules enable:

1. Difficulty Model: Determining if a soldier is structurally resolvable
2. Resolver Phase 5: Deterministic exclusion rules

The output is derived deterministically from hierarchy_reference.json and should
be regenerated whenever that file changes.
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Union


@dataclass
class StructuralDiscriminators:
    """Complete structural discrimination data derived from hierarchy."""

    metadata: Dict[str, any]
    level_name_discriminators: Dict[str, Dict]
    designator_discriminators: Dict[str, Dict]
    depth_discriminators: Dict[int, Dict]
    branch_exclusion_rules: Dict[str, List[Dict]]
    collision_index: Dict[Tuple[str, Union[str, int]], Set[str]] = field(
        default_factory=dict
    )

    def to_json(self) -> Dict:
        """Serialize to JSON-compatible dict."""
        # Convert tuple keys in collision_index to string representation
        collision_index_json = {}
        for (level_name, value), components in self.collision_index.items():
            key = f"({level_name}, {json.dumps(value)})"
            collision_index_json[key] = sorted(components)

        # Convert int keys in depth_discriminators to strings for JSON
        depth_discriminators_json = {
            str(k): v for k, v in self.depth_discriminators.items()
        }

        return {
            "metadata": self.metadata,
            "level_name_discriminators": self.level_name_discriminators,
            "designator_discriminators": self.designator_discriminators,
            "depth_discriminators": depth_discriminators_json,
            "branch_exclusion_rules": self.branch_exclusion_rules,
            "collision_index": collision_index_json,
        }

    @classmethod
    def from_json(cls, data: Dict) -> "StructuralDiscriminators":
        """Deserialize from JSON dict."""
        # Parse collision_index keys back to tuples
        collision_index = {}
        for key, components in data.get("collision_index", {}).items():
            # Parse "(level_name, value)" format
            # Key format: "(level_name, "value")" or "(level_name, 123)"
            key = key.strip("()")
            parts = key.split(", ", 1)
            if len(parts) == 2:
                level_name = parts[0]
                value = json.loads(parts[1])
                collision_index[(level_name, value)] = set(components)

        # Parse int keys in depth_discriminators
        depth_discriminators = {
            int(k): v for k, v in data.get("depth_discriminators", {}).items()
        }

        return cls(
            metadata=data.get("metadata", {}),
            level_name_discriminators=data.get("level_name_discriminators", {}),
            designator_discriminators=data.get("designator_discriminators", {}),
            depth_discriminators=depth_discriminators,
            branch_exclusion_rules=data.get("branch_exclusion_rules", {}),
            collision_index=collision_index,
        )


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
    hierarchy = _load_hierarchy(hierarchy_path)
    branches = _parse_branches(hierarchy)

    # Compute discriminators
    level_name_discriminators = _compute_level_name_discriminators(branches)
    designator_discriminators = _compute_designator_discriminators(branches)
    depth_discriminators = _compute_depth_discriminators(branches)

    # Build collision index from components (if available) or from designators
    components = hierarchy.get("components", [])
    if components:
        collision_index = _build_collision_index_from_components(hierarchy, branches)
    else:
        collision_index = _build_collision_index_from_designators(branches)

    # Generate exclusion rules
    branch_exclusion_rules = _generate_all_exclusion_rules(
        branches,
        level_name_discriminators,
        designator_discriminators,
        depth_discriminators,
    )

    # Build metadata
    metadata = {
        "generated_from": hierarchy_path.name,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "branches_analyzed": sorted(branches.keys()),
    }

    result = StructuralDiscriminators(
        metadata=metadata,
        level_name_discriminators=level_name_discriminators,
        designator_discriminators=designator_discriminators,
        depth_discriminators=depth_discriminators,
        branch_exclusion_rules=branch_exclusion_rules,
        collision_index=collision_index,
    )

    # Write output
    if output_path is None:
        output_path = hierarchy_path.parent / "structural_discriminators.json"

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result.to_json(), f, indent=2)

    return result


def _load_hierarchy(path: Path) -> Dict:
    """Load and validate hierarchy reference JSON."""
    if not path.exists():
        raise FileNotFoundError(f"Hierarchy file not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Validate required top-level keys
    if "branches" not in data:
        raise ValueError("hierarchy_reference.json missing required 'branches' key")

    return data


@dataclass
class BranchDef:
    """Internal representation of a branch definition."""

    branch_id: str
    depth: int
    levels: List[str]
    valid_designators: Dict[str, List[Union[str, int]]]


def _parse_branches(hierarchy: Dict) -> Dict[str, BranchDef]:
    """Parse branch definitions from hierarchy, handling schema variations."""
    branches = {}

    for branch_id, branch_data in hierarchy["branches"].items():
        depth = branch_data.get("depth")
        levels = branch_data.get("levels", [])

        if depth is None:
            raise ValueError(f"Branch '{branch_id}' missing required 'depth' field")
        if not levels:
            raise ValueError(f"Branch '{branch_id}' missing required 'levels' field")

        # Handle schema variations for designators
        valid_designators = {}

        # Try 'valid_designators' first (spec format)
        if "valid_designators" in branch_data:
            valid_designators = branch_data["valid_designators"]
        # Fall back to 'level_config' (actual hierarchy_reference.json format)
        elif "level_config" in branch_data:
            for level_name, config in branch_data["level_config"].items():
                values = config.get("values", [])
                # Convert string numbers to integers where appropriate
                valid_designators[level_name] = _normalize_values(values)
        else:
            # Log warning but continue - level names still useful
            print(
                f"Warning: Branch '{branch_id}' has no 'valid_designators' or 'level_config'"
            )

        # Validate that levels match designator keys
        for level in levels:
            if level not in valid_designators:
                print(
                    f"Warning: Level '{level}' in branch '{branch_id}' has no designators defined"
                )

        branches[branch_id] = BranchDef(
            branch_id=branch_id,
            depth=depth,
            levels=levels,
            valid_designators=valid_designators,
        )

    return branches


def _normalize_values(values: List) -> List[Union[str, int]]:
    """Normalize designator values, converting numeric strings to ints."""
    result = []
    for v in values:
        if isinstance(v, int):
            result.append(v)
        elif isinstance(v, str) and v.isdigit():
            result.append(int(v))
        else:
            result.append(v)
    return result


def _classify_value_type(value: Union[str, int]) -> str:
    """Classify a designator value as alpha, numeric, or word."""
    if isinstance(value, int):
        return "numeric"
    if len(value) == 1 and value.isalpha():
        return "alpha"
    return "word"


def _compute_level_name_discriminators(
    branches: Dict[str, BranchDef],
) -> Dict[str, Dict]:
    """
    Compute which level names are unique to which branches.

    Returns dict mapping level_name -> {unique_to, appears_in}
    """
    # Collect all level names by branch
    level_names_by_branch: Dict[str, Set[str]] = {}
    for branch_id, branch in branches.items():
        level_names_by_branch[branch_id] = set(branch.levels)

    # Invert: for each level name, which branches have it?
    branches_by_level_name: Dict[str, List[str]] = defaultdict(list)
    for branch_id, level_names in level_names_by_branch.items():
        for name in level_names:
            branches_by_level_name[name].append(branch_id)

    # Build discriminators
    result = {}
    for level_name, branch_list in branches_by_level_name.items():
        branch_list_sorted = sorted(branch_list)
        result[level_name] = {
            "unique_to": branch_list_sorted[0] if len(branch_list) == 1 else None,
            "appears_in": branch_list_sorted,
        }

    return result


def _compute_designator_discriminators(
    branches: Dict[str, BranchDef],
) -> Dict[str, Dict]:
    """
    Compute which designator values are valid in which branches/levels.

    Returns dict mapping value (as string) -> {type, unique_to_branch, valid_in, collision_levels}
    """
    # Collect all (branch, level, value) tuples
    value_locations: Dict[Union[str, int], List[Tuple[str, str]]] = defaultdict(list)

    for branch_id, branch in branches.items():
        for level_name, values in branch.valid_designators.items():
            for value in values:
                value_locations[value].append((branch_id, level_name))

    # Build discriminators
    result = {}
    for value, locations in value_locations.items():
        # Group by branch
        valid_in: Dict[str, List[str]] = defaultdict(list)
        for branch_id, level_name in locations:
            valid_in[branch_id].append(level_name)

        # Sort levels within each branch
        valid_in = {k: sorted(v) for k, v in valid_in.items()}

        branches_present = sorted(valid_in.keys())
        unique_to_branch = branches_present[0] if len(branches_present) == 1 else None

        # Collision levels: all (branch, level) pairs where this value appears
        collision_levels = sorted(locations)

        # Use string key for JSON compatibility
        value_key = str(value)
        result[value_key] = {
            "type": _classify_value_type(value),
            "unique_to_branch": unique_to_branch,
            "valid_in": valid_in,
            "collision_levels": collision_levels,
        }

    return result


def _compute_depth_discriminators(branches: Dict[str, BranchDef]) -> Dict[int, Dict]:
    """
    Compute which depths are unique to which branches.

    Returns dict mapping depth -> {branches, is_unique}
    """
    # Group branches by depth
    branches_by_depth: Dict[int, List[str]] = defaultdict(list)
    for branch_id, branch in branches.items():
        branches_by_depth[branch.depth].append(branch_id)

    # Build discriminators
    result = {}
    for depth, branch_list in branches_by_depth.items():
        branch_list_sorted = sorted(branch_list)
        result[depth] = {
            "branches": branch_list_sorted,
            "is_unique": len(branch_list) == 1,
        }

    return result


def _generate_all_exclusion_rules(
    branches: Dict[str, BranchDef],
    level_name_discriminators: Dict[str, Dict],
    designator_discriminators: Dict[str, Dict],
    depth_discriminators: Dict[int, Dict],
) -> Dict[str, List[Dict]]:
    """Generate exclusion rules for all branches."""
    result = {}
    for branch_id in branches:
        result[branch_id] = _generate_exclusion_rules_for_branch(
            branch_id,
            branches,
            level_name_discriminators,
            designator_discriminators,
            depth_discriminators,
        )
    return result


def _generate_exclusion_rules_for_branch(
    branch_id: str,
    branches: Dict[str, BranchDef],
    level_name_discriminators: Dict[str, Dict],
    designator_discriminators: Dict[str, Dict],
    depth_discriminators: Dict[int, Dict],
) -> List[Dict]:
    """
    Generate exclusion rules for a specific branch.

    Exclusion rules describe what signals would EXCLUDE this branch.
    Only presence-based rules (not absence-based).
    """
    rules = []
    branch = branches[branch_id]

    # Rule type 1: Term presence that excludes this branch
    # If a level name is unique to another branch, its presence excludes this branch
    for term, info in level_name_discriminators.items():
        unique_to = info["unique_to"]
        if unique_to is not None and unique_to != branch_id:
            rules.append(
                {
                    "rule_type": "term_presence",
                    "condition": f"contains term '{term}'",
                    "excludes_branch": branch_id,
                    "implies_branch": unique_to,
                    "strength": "definitive",
                }
            )

    # Rule type 2: Designator invalidity
    # If a value is unique to another branch, its presence excludes this branch
    for value_str, info in designator_discriminators.items():
        unique_to = info["unique_to_branch"]
        if unique_to is not None and unique_to != branch_id:
            rules.append(
                {
                    "rule_type": "designator_invalidity",
                    "condition": f"contains designator '{value_str}' (only valid in {unique_to})",
                    "excludes_branch": branch_id,
                    "implies_branch": unique_to,
                    "strength": "definitive",
                }
            )

    # Rule type 3: Depth mismatch
    # If path has more levels than this branch supports, exclude it
    for depth, info in depth_discriminators.items():
        if depth > branch.depth:
            other_branches = [b for b in info["branches"] if b != branch_id]
            rules.append(
                {
                    "rule_type": "depth_mismatch",
                    "condition": f"path has {depth} levels (branch only has {branch.depth})",
                    "excludes_branch": branch_id,
                    "possible_branches": other_branches,
                    "strength": "definitive",
                }
            )

    return rules


def _build_collision_index_from_components(
    hierarchy: Dict,
    branches: Dict[str, BranchDef],
) -> Dict[Tuple[str, Union[str, int]], Set[str]]:
    """
    Build collision index from enumerated component paths.

    Maps (level_name, value) -> set of component paths where that pair appears.
    Only includes entries with 2+ components (actual collisions).
    """
    collision_index: Dict[Tuple[str, Union[str, int]], Set[str]] = defaultdict(set)

    for component_path in hierarchy["components"]:
        parts = component_path.split("/")
        if not parts:
            continue

        branch_id = parts[0]
        if branch_id not in branches:
            continue

        branch = branches[branch_id]

        # Map each (level_name, value) to this component
        for i, level_name in enumerate(branch.levels):
            if i + 1 >= len(parts):
                break
            value = parts[i + 1]
            # Normalize to int if numeric
            if value.isdigit():
                value = int(value)
            collision_index[(level_name, value)].add(component_path)

    # Filter to actual collisions (2+ components)
    return {k: v for k, v in collision_index.items() if len(v) > 1}


def _build_collision_index_from_designators(
    branches: Dict[str, BranchDef],
) -> Dict[Tuple[str, Union[str, int]], Set[str]]:
    """
    Build collision index from valid designators when no components array exists.

    This identifies theoretical collisions: (level_name, value) pairs that appear
    in multiple branches.

    Returns mapping of (level_name, value) -> set of "branch.level" strings
    """
    collision_index: Dict[Tuple[str, Union[str, int]], Set[str]] = defaultdict(set)

    for branch_id, branch in branches.items():
        for level_name, values in branch.valid_designators.items():
            for value in values:
                collision_index[(level_name, value)].add(f"{branch_id}.{level_name}")

    # Filter to actual collisions (2+ locations)
    return {k: v for k, v in collision_index.items() if len(v) > 1}


# CLI entry point
def main():
    """CLI entry point for extracting structural discriminators."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Extract structural discriminators from hierarchy reference"
    )
    parser.add_argument(
        "--input",
        "-i",
        type=Path,
        default=Path("config/hierarchies/hierarchy_reference.json"),
        help="Path to hierarchy_reference.json",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=None,
        help="Path for output (default: same directory as input)",
    )

    args = parser.parse_args()

    result = extract_structural_discriminators(args.input, args.output)
    print(f"Extracted discriminators for {len(result.metadata['branches_analyzed'])} branches")
    print(f"  Level name discriminators: {len(result.level_name_discriminators)}")
    print(f"  Designator discriminators: {len(result.designator_discriminators)}")
    print(f"  Depth discriminators: {len(result.depth_discriminators)}")
    print(f"  Collision index entries: {len(result.collision_index)}")
    total_rules = sum(len(rules) for rules in result.branch_exclusion_rules.values())
    print(f"  Total exclusion rules: {total_rules}")


if __name__ == "__main__":
    main()
