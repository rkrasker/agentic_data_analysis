"""
Module 2: Structure Extractor

Extracts valid designators from hierarchy and detects collisions (Phases 1-2).
Provides structural information needed for resolver generation.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Set, Tuple, Union, Any, Optional


@dataclass
class ComponentStructure:
    """Structure information for a single component.

    Supports heterogeneous branches with variable depths (ADR-009).
    """
    component_id: str
    component_name: str
    branch: str
    depth: int
    level_names: List[str]
    valid_designators: Dict[str, List[Union[str, int]]]
    structural_discriminators: List[Dict[str, str]]

    # Legacy fields - kept for backward compatibility during transition
    canonical_name: str = ""
    aliases: List[str] = field(default_factory=list)
    battalion_designator_type: str = "unknown"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = {
            "component_id": self.component_id,
            "component_name": self.component_name,
            "branch": self.branch,
            "depth": self.depth,
            "levels": self.level_names,
            "valid_designators": self.valid_designators,
            "structural_discriminators": self.structural_discriminators,
        }
        if self.aliases:
            result["aliases"] = self.aliases
        if self.battalion_designator_type != "unknown":
            result["battalion_designator_type"] = self.battalion_designator_type
        return result

    def get_level_designators(self, level: str) -> List[str]:
        """Get valid designators for a specific level."""
        return self.valid_designators.get(level, [])


@dataclass
class StructureResult:
    """Result of structure extraction."""
    structures: Dict[str, ComponentStructure]  # component_id -> structure
    collisions: Dict[Tuple[str, str], Set[str]]  # (level, value) -> {component_ids}
    branches: Dict[str, Dict] = field(default_factory=dict)

    # Pre-computed collision pairs for sampling
    collision_pairs: Dict[Tuple[str, str], Set[Tuple[str, str]]] = field(default_factory=dict)
    # (level, value) -> {(comp_a, comp_b)} where comp_a < comp_b alphabetically

    def get_rivals(self, component_id: str) -> Set[str]:
        """Get all components that share any designator with this component."""
        rivals = set()
        for (level, value), components in self.collisions.items():
            if component_id in components:
                rivals.update(components - {component_id})
        return rivals

    def get_collision_levels(self, comp_a: str, comp_b: str) -> List[Tuple[str, str]]:
        """Get all (level, value) pairs where two components collide."""
        collisions = []
        for (level, value), components in self.collisions.items():
            if comp_a in components and comp_b in components:
                collisions.append((level, value))
        return collisions

    def list_all_collision_pairs(self) -> List[Tuple[str, str]]:
        """Get all unique collision pairs across all levels."""
        pairs = set()
        for (level, value), components in self.collisions.items():
            comp_list = sorted(components)
            for i, comp_a in enumerate(comp_list):
                for comp_b in comp_list[i + 1:]:
                    pairs.add((comp_a, comp_b))
        return sorted(pairs)


def extract_structure(hierarchy_path: Path) -> StructureResult:
    """
    Extract branch-aware structure and collision map from hierarchy.

    Args:
        hierarchy_path: Path to hierarchy_reference.json

    Returns:
        StructureResult with structures and collision maps
    """
    hierarchy = load_hierarchy_reference(hierarchy_path)
    discriminators = load_structural_discriminators()

    structures: Dict[str, ComponentStructure] = {}
    for component_id in _get_component_ids(hierarchy):
        structures[component_id] = _extract_component_structure(
            component_id=component_id,
            hierarchy=hierarchy,
            structural_discriminators=discriminators,
        )

    collisions = discriminators.get("collision_index", {})
    structure_collisions = _detect_collisions_from_structures(structures)
    for key, comps in structure_collisions.items():
        if key in collisions:
            collisions[key].update(comps)
        else:
            collisions[key] = comps

    collision_pairs = _compute_collision_pairs(collisions)

    return StructureResult(
        structures=structures,
        collisions=collisions,
        collision_pairs=collision_pairs,
        branches=hierarchy.get("branches", {}),
    )


def load_hierarchy_reference(path: Path = None) -> Dict[str, Any]:
    """Load hierarchy_reference.json for deterministic resolver logic."""
    hierarchy_path = path or Path("config/hierarchies/hierarchy_reference.json")
    with open(hierarchy_path) as f:
        return json.load(f)


def _parse_collision_key(raw_key: str) -> Optional[Tuple[str, str]]:
    """Parse collision_index keys like '(level, \"value\")' into tuples."""
    if not raw_key:
        return None
    key = raw_key.strip()
    if key.startswith("(") and key.endswith(")"):
        key = key[1:-1]
    parts = [p.strip() for p in key.split(",", 1)]
    if len(parts) != 2:
        return None
    level = parts[0].strip("'\"")
    value = parts[1].strip().strip("'\"")
    if not level or not value:
        return None
    return level, value


def load_structural_discriminators(path: Path = None) -> Dict[str, Any]:
    """Load precomputed structural discriminators from JSON."""
    discriminators_path = path or Path("config/hierarchies/structural_discriminators.json")
    with open(discriminators_path) as f:
        data = json.load(f)

    collision_index_raw = data.get("collision_index", {})
    collision_index: Dict[Tuple[str, str], Set[str]] = {}
    for raw_key, components in collision_index_raw.items():
        key = _parse_collision_key(raw_key)
        if not key:
            continue
        mapped_components = set()
        if isinstance(components, list):
            for comp in components:
                if isinstance(comp, str) and "." in comp:
                    mapped_components.add(comp.split(".", 1)[0])
                elif comp:
                    mapped_components.add(str(comp))
        collision_index[key] = mapped_components

    depth_by_branch: Dict[str, int] = {}
    for depth_str, info in data.get("depth_discriminators", {}).items():
        try:
            depth_val = int(depth_str)
        except (TypeError, ValueError):
            continue
        for branch in info.get("branches", []):
            if branch not in depth_by_branch:
                depth_by_branch[branch] = depth_val

    return {
        "collision_index": collision_index,
        "branch_exclusion_rules": data.get("branch_exclusion_rules", {}),
        "depth_by_branch": depth_by_branch,
        "depth_discriminators": data.get("depth_discriminators", {}),
        "level_name_discriminators": data.get("level_name_discriminators", {}),
        "designator_discriminators": data.get("designator_discriminators", {}),
    }


def _resolve_component_branch(
    component_id: str,
    structure: ComponentStructure,
    hierarchy: Dict[str, Any],
) -> Optional[str]:
    """Resolve the component's branch from hierarchy or structure."""
    components = hierarchy.get("components", {})
    if component_id in components:
        return components.get(component_id, {}).get("branch") or components.get(component_id, {}).get("service_branch")

    if structure.branch in hierarchy.get("branches", {}):
        return structure.branch

    if component_id in hierarchy.get("branches", {}):
        return component_id

    return None


def _dedupe_rules(rules: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Deduplicate rules by their key/value signature."""
    seen = set()
    unique = []
    for rule in rules:
        if "if_contains" in rule:
            signature = ("if_contains", rule.get("if_contains"))
        elif "if_depth" in rule:
            signature = ("if_depth", rule.get("if_depth"))
        elif "if_invalid_designator" in rule:
            signature = ("if_invalid_designator", rule.get("if_invalid_designator"))
        else:
            signature = tuple(sorted(rule.items()))
        if signature in seen:
            continue
        seen.add(signature)
        unique.append(rule)
    return unique


def compute_exclusions(
    component_id: str,
    structure: ComponentStructure,
    structural_discriminators: Dict[str, Any],
    hierarchy: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """
    Derive exclusion rules deterministically from hierarchy.
    No LLM required.
    """
    branch = _resolve_component_branch(component_id, structure, hierarchy)
    if not branch:
        return []

    rules: List[Dict[str, Any]] = []

    # Branch-unique terms
    for term, info in structural_discriminators.get("level_name_discriminators", {}).items():
        unique_to = info.get("unique_to")
        if unique_to and unique_to != branch:
            rules.append({
                "if_contains": term,
                "then": "exclude",
                "reason": f"term unique to {unique_to}",
            })

    # Depth mismatches
    branch_depth = hierarchy.get("branches", {}).get(branch, {}).get("depth")
    if branch_depth is None:
        branch_depth = structural_discriminators.get("depth_by_branch", {}).get(branch)
    if branch_depth is not None:
        for depth_str in structural_discriminators.get("depth_discriminators", {}).keys():
            try:
                depth_val = int(depth_str)
            except (TypeError, ValueError):
                continue
            if depth_val != branch_depth:
                rules.append({
                    "if_depth": depth_val,
                    "then": "exclude",
                    "reason": f"branch depth is {branch_depth}",
                })

    # Invalid designators
    for designator, info in structural_discriminators.get("designator_discriminators", {}).items():
        valid_in = info.get("valid_in", {})
        if branch not in valid_in:
            unique_to = info.get("unique_to_branch")
            reason = f"designator not valid in {branch}"
            if unique_to and unique_to != branch:
                reason = f"designator unique to {unique_to}"
            rules.append({
                "if_invalid_designator": designator,
                "then": "exclude",
                "reason": reason,
            })

    return _dedupe_rules(rules)


def _get_component_ids(hierarchy: Dict[str, Any]) -> List[str]:
    """Get all component IDs from hierarchy, falling back to branch IDs."""
    components = hierarchy.get("components", {})
    if isinstance(components, dict) and components:
        return sorted(components.keys())
    return sorted(hierarchy.get("branches", {}).keys())


def _find_component_data(component_id: str, hierarchy: Dict[str, Any]) -> Dict[str, Any]:
    """Find component data in hierarchy (supports branch-only hierarchies)."""
    components = hierarchy.get("components", {})
    if isinstance(components, dict) and component_id in components:
        return components[component_id]
    # Fallback: treat branch as component
    return hierarchy.get("branches", {}).get(component_id, {})


def _extract_valid_values_for_level(
    component_data: Dict[str, Any],
    branch_data: Dict[str, Any],
    level_name: str,
) -> List[Union[str, int]]:
    """Extract valid designators for a specific level."""
    # Branch-aware format: values live under branch level_config
    level_config = branch_data.get("level_config", {}).get(level_name, {})
    if "values" in level_config:
        return _normalize_designator_values(level_config.get("values", []))

    # Legacy format: component organizational_structure -> levels -> designators
    org_structure = component_data.get("organizational_structure", {})
    levels = org_structure.get("levels", {})
    level_data = levels.get(level_name, {})
    return _normalize_designator_values(level_data.get("designators", []))


def _collect_branch_discriminators(
    hierarchy: Dict[str, Any],
    discriminators: Dict[str, Any],
    branch: str,
) -> List[Dict[str, str]]:
    """Collect structural discriminator terms for a branch."""
    results: List[Dict[str, str]] = []

    # From hierarchy structural signals
    branch_terms = hierarchy.get("structural_signals", {}).get("branch_unique_terms", {})
    for term, implied in branch_terms.items():
        if implied == branch:
            results.append({
                "term": term,
                "implies_branch": implied,
                "strength": "definitive",
            })

    # From structural discriminators (scan for implies_branch)
    for rules in discriminators.get("branch_exclusion_rules", {}).values():
        for rule in rules:
            if rule.get("implies_branch") != branch:
                continue
            term = _parse_discriminator_term(rule.get("condition", ""))
            if not term:
                continue
            results.append({
                "term": term,
                "implies_branch": branch,
                "strength": rule.get("strength", "definitive"),
            })

    # Deduplicate by term
    seen = set()
    unique = []
    for entry in results:
        term = entry.get("term")
        if not term or term in seen:
            continue
        seen.add(term)
        unique.append(entry)
    return unique


def _parse_discriminator_term(condition: str) -> Optional[str]:
    """Extract the term/designator from a discriminator condition string."""
    if "'" not in condition:
        return None
    parts = condition.split("'")
    if len(parts) < 2:
        return None
    return parts[1].strip()


def _normalize_designator_values(values: List[Any]) -> List[Union[str, int]]:
    """Normalize designators into stable primitives."""
    normalized: List[Union[str, int]] = []
    for value in values:
        if isinstance(value, int):
            normalized.append(value)
            continue
        if isinstance(value, str):
            stripped = value.strip()
            if stripped.isdigit():
                normalized.append(int(stripped))
            else:
                normalized.append(stripped)
            continue
        normalized.append(str(value))
    return normalized


def _extract_component_structure(
    component_id: str,
    hierarchy: Dict[str, Any],
    structural_discriminators: Dict[str, Any],
) -> ComponentStructure:
    """Extract branch-aware structure for a component."""
    component_data = _find_component_data(component_id, hierarchy)

    # Determine branch
    branch = component_data.get("branch") or component_data.get("service_branch") or component_id
    if branch not in hierarchy.get("branches", {}):
        # Fallback: use component_id as branch if we don't recognize it
        branch = component_id

    branch_data = hierarchy.get("branches", {}).get(branch, {})
    level_names = branch_data.get("levels", [])
    depth = int(branch_data.get("depth", len(level_names)))

    if not level_names:
        # Legacy component-level structure
        org_structure = component_data.get("organizational_structure", {})
        level_names = list(org_structure.get("levels", {}).keys())
        depth = len(level_names)

    valid_designators = {
        level_name: _extract_valid_values_for_level(component_data, branch_data, level_name)
        for level_name in level_names
    }

    component_name = component_data.get("canonical_name") or component_data.get("name") or component_id
    aliases = component_data.get("aliases", [])
    if isinstance(aliases, list):
        aliases = [a.get("alias_name", a) if isinstance(a, dict) else a for a in aliases]
        aliases = [str(a) for a in aliases if a]
    else:
        aliases = []
    if not aliases:
        branch_aliases = branch_data.get("unique_identifiers", [])
        if isinstance(branch_aliases, list):
            aliases = [str(a) for a in branch_aliases if a]

    return ComponentStructure(
        component_id=component_id,
        component_name=component_name,
        branch=branch,
        depth=depth,
        level_names=level_names,
        valid_designators=valid_designators,
        structural_discriminators=_collect_branch_discriminators(hierarchy, structural_discriminators, branch),
        canonical_name=component_name,
        aliases=aliases,
        battalion_designator_type=component_data.get("battalion_designator_type", "unknown"),
    )


def _detect_collisions_from_structures(
    structures: Dict[str, ComponentStructure]
) -> Dict[Tuple[str, str], Set[str]]:
    """Detect collisions by comparing structure designators."""
    collisions: Dict[Tuple[str, str], Set[str]] = {}
    levels_to_check: Set[str] = set()
    for structure in structures.values():
        levels_to_check.update(structure.level_names)

    for level in sorted(levels_to_check):
        value_to_components: Dict[str, Set[str]] = {}
        for comp_id, structure in structures.items():
            designators = structure.get_level_designators(level)
            for value in designators:
                value_str = str(value)
                if value_str not in value_to_components:
                    value_to_components[value_str] = set()
                value_to_components[value_str].add(comp_id)

        for value, components in value_to_components.items():
            if len(components) > 1:
                key = (level, value)
                if key in collisions:
                    collisions[key].update(components)
                else:
                    collisions[key] = components

    return collisions


def _compute_collision_pairs(
    collisions: Dict[Tuple[str, str], Set[str]]
) -> Dict[Tuple[str, str], Set[Tuple[str, str]]]:
    """Pre-compute unique collision pairs per (level, value)."""
    collision_pairs: Dict[Tuple[str, str], Set[Tuple[str, str]]] = {}

    for (level, value), components in collisions.items():
        pairs = set()
        comp_list = sorted(components)
        for i, comp_a in enumerate(comp_list):
            for comp_b in comp_list[i + 1:]:
                pairs.add((comp_a, comp_b))
        collision_pairs[(level, value)] = pairs

    return collision_pairs


def get_structural_exclusions(
    component_id: str,
    structure: ComponentStructure,
    all_structures: Dict[str, ComponentStructure],
) -> List[Dict[str, str]]:
    """
    Generate structural exclusion rules for a component.

    Args:
        component_id: Target component
        structure: Target component's structure
        all_structures: All component structures

    Returns:
        List of exclusion rule dicts
    """
    exclusions: List[Dict[str, str]] = []

    # Branch-unique term exclusions
    for other_struct in all_structures.values():
        if other_struct.branch == structure.branch:
            continue
        for disc in other_struct.structural_discriminators:
            term = disc.get("term")
            if not term:
                continue
            exclusions.append({
                "if_contains": term,
                "then": "exclude",
                "reason": f"term unique to {other_struct.branch}",
            })

    # Depth mismatch exclusions
    other_depths = {
        other_struct.depth
        for other_struct in all_structures.values()
        if other_struct.depth != structure.depth
    }
    for depth in sorted(other_depths):
        exclusions.append({
            "if_depth": depth,
            "then": "exclude",
            "reason": f"branch depth is {structure.depth}",
        })

    return _dedupe_rules(exclusions)


def get_invalid_designators(
    component_id: str,
    structure: ComponentStructure,
    all_structures: Dict[str, ComponentStructure],
) -> Dict[str, List[str]]:
    """
    Get designators that are invalid for this component.

    Args:
        component_id: Target component
        structure: Target component's structure
        all_structures: All component structures

    Returns:
        Dict mapping level -> list of invalid designators
    """
    invalid: Dict[str, List[str]] = {}
    # Collect all valid designators across all components per level
    all_by_level: Dict[str, Set[str]] = {}
    for comp_structure in all_structures.values():
        for level, values in comp_structure.valid_designators.items():
            all_by_level.setdefault(level, set()).update(str(v) for v in values)

    for level, all_values in all_by_level.items():
        valid_values = set(str(v) for v in structure.valid_designators.get(level, []))
        invalid_values = sorted(all_values - valid_values)
        if invalid_values:
            invalid[level] = invalid_values

    return invalid
