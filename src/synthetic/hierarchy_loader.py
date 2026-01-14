"""
HierarchyLoader: Load and query unit hierarchy data.

Provides collision-aware lookups and designator resolution
per component conventions.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Any, Set


class HierarchyLoader:
    """
    Loads and queries unit hierarchy data.

    Handles collision-aware lookups - the same regiment number
    can belong to multiple components.
    """

    def __init__(
        self,
        hierarchy_path: Optional[Path] = None,
    ):
        """
        Initialize the loader.

        Args:
            hierarchy_path: Path to hierarchy_reference.json
        """
        self.components: Dict[str, Dict[str, Any]] = {}
        self.collision_index: Dict[str, Any] = {}

        # Quick lookups
        self._regiments_by_component: Dict[str, List[str]] = {}
        self._divisions_by_branch: Dict[str, List[str]] = {}

        if hierarchy_path:
            self.load_hierarchy(hierarchy_path)

    def load_hierarchy(self, hierarchy_path: Path) -> None:
        """Load hierarchy from JSON file."""
        with open(hierarchy_path, "r") as f:
            data = json.load(f)

        self.components = data.get("components", {})
        self.collision_index = data.get("collision_index", {})

        self._build_indexes()

    def _build_indexes(self) -> None:
        """Build quick-lookup indexes."""
        self._regiments_by_component = {}
        self._divisions_by_branch = {}

        for comp_id, comp_data in self.components.items():
            # Index regiments
            org = comp_data.get("organizational_structure", {})
            levels = org.get("levels", {})

            if "regiment" in levels:
                self._regiments_by_component[comp_id] = levels["regiment"].get(
                    "designators", []
                )

            # Index by service branch
            branch = comp_data.get("service_branch", "unknown")
            if branch not in self._divisions_by_branch:
                self._divisions_by_branch[branch] = []
            self._divisions_by_branch[branch].append(comp_id)

    def get_component(self, component_id: str) -> Optional[Dict[str, Any]]:
        """Get a component by ID."""
        return self.components.get(component_id)

    def list_components(self) -> List[str]:
        """List all component IDs."""
        return list(self.components.keys())

    def get_components_by_branch(self, branch: str) -> List[str]:
        """Get component IDs for a service branch."""
        return self._divisions_by_branch.get(branch, [])

    def get_regiments(self, component_id: str) -> List[str]:
        """Get regiment designators for a component."""
        return self._regiments_by_component.get(component_id, [])

    def get_battalions(self, component_id: str) -> List[str]:
        """Get battalion designators for a component."""
        comp = self.components.get(component_id, {})
        org = comp.get("organizational_structure", {})
        levels = org.get("levels", {})
        return levels.get("battalion", {}).get("designators", [])

    def get_companies(self, component_id: str) -> List[str]:
        """Get company designators for a component."""
        comp = self.components.get(component_id, {})
        org = comp.get("organizational_structure", {})
        levels = org.get("levels", {})
        return levels.get("company", {}).get("designators", [])

    def get_hierarchy_pattern(self, component_id: str) -> str:
        """Get the hierarchy pattern for a component."""
        comp = self.components.get(component_id, {})
        org = comp.get("organizational_structure", {})
        return org.get("hierarchy_pattern", "")

    def is_collision(self, designator: str, level: str = "regiment") -> bool:
        """
        Check if a designator has collisions across components.

        Args:
            designator: The designator to check
            level: The level (regiment, battalion)

        Returns:
            True if multiple components use this designator
        """
        collision_key = f"{level}_collisions"
        collisions = self.collision_index.get(collision_key, {})
        components_with_designator = collisions.get(designator, [])
        return len(components_with_designator) > 1

    def get_colliding_components(
        self,
        designator: str,
        level: str = "regiment",
    ) -> List[str]:
        """
        Get components that share a designator.

        Args:
            designator: The designator to check
            level: The level (regiment, battalion)

        Returns:
            List of component IDs that use this designator
        """
        collision_key = f"{level}_collisions"
        collisions = self.collision_index.get(collision_key, {})
        return collisions.get(designator, [])

    def get_canonical_name(self, component_id: str) -> str:
        """Get the canonical name for a component."""
        comp = self.components.get(component_id, {})
        return comp.get("canonical_name", component_id)

    def get_component_type(self, component_id: str) -> str:
        """Get the component type (division, air_force, etc.)."""
        comp = self.components.get(component_id, {})
        return comp.get("component_type", "unknown")

    def get_division_type(self, component_id: str) -> str:
        """
        Get the division type for rendering (infantry, airborne, etc.).

        Returns type based on canonical name analysis.
        """
        name = self.get_canonical_name(component_id).lower()

        if "airborne" in name:
            return "airborne"
        elif "armored" in name:
            return "armored"
        elif "mountain" in name:
            return "mountain"
        elif "marine" in name:
            return "marine"
        elif "air force" in name:
            return "air_force"
        else:
            return "infantry"

    def get_subordinate_units(
        self,
        component_id: str,
        unit_type: str,
    ) -> List[Dict[str, Any]]:
        """
        Get subordinate units of a specific type.

        Args:
            component_id: The parent component
            unit_type: Type of units (regiments, battalions, etc.)

        Returns:
            List of subordinate unit data
        """
        comp = self.components.get(component_id, {})
        subs = comp.get("known_subordinate_units", {})
        return subs.get(unit_type, [])

    def resolve_regiment_name(
        self,
        component_id: str,
        regiment_designator: str,
    ) -> str:
        """
        Resolve a regiment designator to its canonical name.

        Args:
            component_id: The division component
            regiment_designator: The regiment number/designator

        Returns:
            Canonical regiment name or formatted string
        """
        regiments = self.get_subordinate_units(component_id, "regiments")
        for reg in regiments:
            if reg.get("designator") == regiment_designator:
                return reg.get("canonical_name", f"{regiment_designator} Regiment")

        # Fallback
        div_type = self.get_division_type(component_id)
        if div_type == "marine":
            return f"{regiment_designator} Marine Regiment"
        elif div_type == "airborne":
            return f"{regiment_designator} Parachute Infantry Regiment"
        elif div_type == "mountain":
            return f"{regiment_designator} Mountain Infantry Regiment"
        else:
            return f"{regiment_designator} Infantry Regiment"

    def get_all_divisions(self) -> List[str]:
        """Get all division component IDs."""
        return [
            cid for cid, comp in self.components.items()
            if comp.get("component_type") == "division"
        ]

    def get_all_air_forces(self) -> List[str]:
        """Get all air force component IDs."""
        return [
            cid for cid, comp in self.components.items()
            if comp.get("component_type") == "air_force"
        ]
