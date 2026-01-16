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
    """Structural information for a single component."""
    component_id: str
    component_type: str  # "division", "air_force", etc.
    canonical_name: str
    service_branch: str  # "army", "marines", "army_air_forces"
    aliases: List[str] = field(default_factory=list)

    # Valid designators at each level
    valid_regiments: List[str] = field(default_factory=list)
    valid_battalions: List[str] = field(default_factory=list)
    valid_companies: List[str] = field(default_factory=list)

    # For non-standard hierarchies (armored, air force)
    valid_combat_commands: List[str] = field(default_factory=list)
    valid_bomb_groups: List[str] = field(default_factory=list)
    valid_squadrons: List[str] = field(default_factory=list)

    # Designator type info
    battalion_type: str = "numeric"  # "numeric", "alphabetic"
    hierarchy_pattern: str = "division -> regiment -> battalion -> company"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = {
            "component_id": self.component_id,
            "component_type": self.component_type,
            "canonical_name": self.canonical_name,
            "service_branch": self.service_branch,
            "aliases": self.aliases,
            "hierarchy_pattern": self.hierarchy_pattern,
            "battalion_designator_type": self.battalion_type,
        }

        # Add non-empty designator lists
        if self.valid_regiments:
            result["valid_regiments"] = self.valid_regiments
        if self.valid_battalions:
            result["valid_battalions"] = self.valid_battalions
        if self.valid_companies:
            result["valid_companies"] = self.valid_companies
        if self.valid_combat_commands:
            result["valid_combat_commands"] = self.valid_combat_commands
        if self.valid_bomb_groups:
            result["valid_bomb_groups"] = self.valid_bomb_groups
        if self.valid_squadrons:
            result["valid_squadrons"] = self.valid_squadrons

        return result

    def get_level_designators(self, level: str) -> List[str]:
        """Get valid designators for a specific level."""
        level_map = {
            "regiment": self.valid_regiments,
            "battalion": self.valid_battalions,
            "company": self.valid_companies,
            "combat_command": self.valid_combat_commands,
            "bomb_group": self.valid_bomb_groups,
            "squadron": self.valid_squadrons,
        }
        return level_map.get(level, [])


@dataclass
class StructureResult:
    """Result of structure extraction."""
    structures: Dict[str, ComponentStructure]  # component_id -> structure
    collisions: Dict[Tuple[str, str], Set[str]]  # (level, value) -> {component_ids}

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
    Extract valid designators and collision map from hierarchy.

    This implements Phases 1-2 of resolver generation:
    - Phase 1: Extract structural rules (valid designators per component)
    - Phase 2: Collision detection (which components share which designators)

    Args:
        hierarchy_path: Path to hierarchy_reference.json

    Returns:
        StructureResult with structures and collision maps
    """
    with open(hierarchy_path) as f:
        hierarchy = json.load(f)

    components = hierarchy.get("components", {})
    collision_index = hierarchy.get("collision_index", {})

    structures: Dict[str, ComponentStructure] = {}
    collisions: Dict[Tuple[str, str], Set[str]] = {}

    # Extract structure for each component
    for component_id, comp_data in components.items():
        structure = _extract_component_structure(component_id, comp_data)
        structures[component_id] = structure

    # Build collision map from collision_index
    collisions = _build_collision_map(collision_index)

    # Also detect collisions from structure data (in case index is incomplete)
    structure_collisions = _detect_collisions_from_structures(structures)
    for key, comps in structure_collisions.items():
        if key in collisions:
            collisions[key].update(comps)
        else:
            collisions[key] = comps

    # Pre-compute collision pairs
    collision_pairs = _compute_collision_pairs(collisions)

    return StructureResult(
        structures=structures,
        collisions=collisions,
        collision_pairs=collision_pairs,
    )


def _extract_component_structure(component_id: str, comp_data: Dict) -> ComponentStructure:
    """Extract structure for a single component."""
    # Get aliases
    aliases = []
    for alias_entry in comp_data.get("aliases", []):
        if isinstance(alias_entry, dict):
            aliases.append(alias_entry.get("alias_name", ""))
        else:
            aliases.append(str(alias_entry))
    aliases = [a for a in aliases if a]  # Filter empty

    # Get organizational structure
    org_structure = comp_data.get("organizational_structure", {})
    hierarchy_pattern = org_structure.get("hierarchy_pattern", "")
    levels = org_structure.get("levels", {})

    # Extract designators for each level
    valid_regiments = _get_designators(levels, "regiment")
    valid_battalions = _get_designators(levels, "battalion")
    valid_companies = _get_designators(levels, "company")
    valid_combat_commands = _get_designators(levels, "combat_command")
    valid_bomb_groups = _get_designators(levels, "bomb_group")
    valid_squadrons = _get_designators(levels, "squadron")

    # Determine battalion type
    battalion_level = levels.get("battalion", {})
    battalion_convention = battalion_level.get("designator_convention", "numeric_sequential")
    battalion_type = "alphabetic" if "alpha" in battalion_convention else "numeric"

    return ComponentStructure(
        component_id=component_id,
        component_type=comp_data.get("component_type", "division"),
        canonical_name=comp_data.get("canonical_name", component_id),
        service_branch=comp_data.get("service_branch", "army"),
        aliases=aliases,
        valid_regiments=valid_regiments,
        valid_battalions=valid_battalions,
        valid_companies=valid_companies,
        valid_combat_commands=valid_combat_commands,
        valid_bomb_groups=valid_bomb_groups,
        valid_squadrons=valid_squadrons,
        battalion_type=battalion_type,
        hierarchy_pattern=hierarchy_pattern,
    )


def _get_designators(levels: Dict, level_name: str) -> List[str]:
    """Extract designators for a specific level."""
    level_data = levels.get(level_name, {})
    designators = level_data.get("designators", [])
    # Convert all to strings for consistency
    return [str(d) for d in designators]


def _build_collision_map(collision_index: Dict) -> Dict[Tuple[str, str], Set[str]]:
    """Build collision map from hierarchy collision_index."""
    collisions: Dict[Tuple[str, str], Set[str]] = {}

    # Regiment collisions
    for designator, components in collision_index.get("regiment_collisions", {}).items():
        key = ("regiment", str(designator))
        collisions[key] = set(components)

    # Battalion collisions
    for designator, components in collision_index.get("battalion_collisions", {}).items():
        key = ("battalion", str(designator))
        collisions[key] = set(components)

    # Cross-branch collisions (extract component lists)
    for collision_name, branch_data in collision_index.get("cross_branch_collisions", {}).items():
        if isinstance(branch_data, dict):
            # Collect all components from all branches
            all_components = set()
            for branch, comps in branch_data.items():
                if isinstance(comps, list):
                    all_components.update(comps)
            if len(all_components) > 1:
                # Extract level and value from collision name (e.g., "regiment_1")
                parts = collision_name.rsplit("_", 1)
                if len(parts) == 2:
                    level, value = parts
                    key = (level, value)
                    if key in collisions:
                        collisions[key].update(all_components)
                    else:
                        collisions[key] = all_components

    return collisions


def _detect_collisions_from_structures(
    structures: Dict[str, ComponentStructure]
) -> Dict[Tuple[str, str], Set[str]]:
    """Detect collisions by comparing structure designators."""
    collisions: Dict[Tuple[str, str], Set[str]] = {}

    levels_to_check = ["regiment", "battalion", "company", "combat_command", "bomb_group"]

    for level in levels_to_check:
        # Build value -> components map
        value_to_components: Dict[str, Set[str]] = {}

        for comp_id, structure in structures.items():
            designators = structure.get_level_designators(level)
            for value in designators:
                if value not in value_to_components:
                    value_to_components[value] = set()
                value_to_components[value].add(comp_id)

        # Add collisions (values shared by 2+ components)
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

    These are hierarchy-derived rules that definitively exclude this component.
    For example, "contains 'PIR' or 'parachute'" excludes infantry divisions.

    Args:
        component_id: Target component
        structure: Target component's structure
        all_structures: All component structures

    Returns:
        List of exclusion rule dicts with 'if' and 'then' keys
    """
    exclusions = []

    # Service branch exclusions
    if structure.service_branch == "army":
        exclusions.append({
            "if": "contains 'Marine' or 'USMC' or 'MarDiv'",
            "then": "exclude",
            "source": "branch_mismatch"
        })

    if structure.service_branch == "marines":
        exclusions.append({
            "if": "contains 'Airborne' or 'PIR' or 'Parachute'",
            "then": "exclude",
            "source": "branch_mismatch"
        })
        exclusions.append({
            "if": "contains 'Armored' or 'Tank Battalion' (without Marine context)",
            "then": "exclude",
            "source": "branch_mismatch"
        })

    # Component type exclusions
    if structure.component_type == "division":
        if "infantry" in component_id and "airborne" not in component_id:
            exclusions.append({
                "if": "contains 'PIR' or 'parachute' or 'airborne' or 'glider'",
                "then": "exclude",
                "source": "unit_type_mismatch"
            })
        if "armored" not in component_id:
            exclusions.append({
                "if": "contains 'Combat Command' or 'CCA' or 'CCB' or 'CCR'",
                "then": "exclude",
                "source": "unit_type_mismatch"
            })

    if structure.component_type == "air_force":
        exclusions.append({
            "if": "contains 'Infantry' or 'Regiment' (ground unit context)",
            "then": "exclude",
            "source": "unit_type_mismatch"
        })

    return exclusions


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

    # Collect all valid designators across all components
    all_regiments: Set[str] = set()
    all_battalions: Set[str] = set()

    for comp_id, comp_structure in all_structures.items():
        all_regiments.update(comp_structure.valid_regiments)
        all_battalions.update(comp_structure.valid_battalions)

    # Invalid regiments for this component
    valid_regiments = set(structure.valid_regiments)
    invalid_regiments = sorted(all_regiments - valid_regiments, key=lambda x: (len(x), x))
    if invalid_regiments:
        invalid["regiment"] = invalid_regiments

    # Invalid battalions (only if component uses standard battalion designators)
    if structure.valid_battalions:
        valid_battalions = set(structure.valid_battalions)
        # Only compare within same type (numeric vs alphabetic)
        same_type_battalions = {
            b for b in all_battalions
            if (b.isalpha() == structure.valid_battalions[0].isalpha())
        }
        invalid_battalions = sorted(same_type_battalions - valid_battalions)
        if invalid_battalions:
            invalid["battalion"] = invalid_battalions

    return invalid
