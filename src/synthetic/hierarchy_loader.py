"""
HierarchyLoader: Load and query Terraform Combine hierarchy data.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Any

from .models import Branch, CollisionSeverity


class HierarchyLoader:
    """
    Loads and queries branch hierarchy data.

    Provides collision-aware lookups and structural signals.
    """

    def __init__(self, config_path: Optional[Path] = None):
        self.config: Dict[str, Any] = {}
        self.branches: Dict[str, Dict[str, Any]] = {}
        self.collision_index: Dict[str, Dict[str, List[str]]] = {}
        self.structural_signals: Dict[str, Any] = {}

        if config_path:
            self.load_config(config_path)

    def load_config(self, config_path: Path) -> None:
        """Load hierarchy from JSON file."""
        with open(config_path, "r") as f:
            self.config = json.load(f)

        self.branches = self.config.get("branches", {})
        self.collision_index = self.config.get("collision_index", {})
        self.structural_signals = self.config.get("structural_signals", {})

    def get_branch_depth(self, branch: Branch) -> int:
        """Return depth for a branch (3, 4, or 5)."""
        return int(self.branches[branch.value]["depth"])

    def get_branch_levels(self, branch: Branch) -> List[str]:
        """Return ordered level names for a branch."""
        return list(self.branches[branch.value]["levels"])

    def get_level_values(self, branch: Branch, level: str) -> List[str]:
        """Return available designators for a branch level."""
        level_config = self.branches[branch.value]["level_config"]
        return list(level_config.get(level, {}).get("values", []))

    def get_branch_abbreviation(self, branch: Branch) -> str:
        """Return branch abbreviation."""
        return self.branches[branch.value].get("abbreviation", branch.value)

    def get_collision_severity(
        self,
        branch: Branch,
        post_levels: Dict[str, str],
    ) -> CollisionSeverity:
        """
        Determine collision severity for a post.

        Checks each designator against collision index to see how many
        other posts could have the same partial path.
        """
        if not post_levels:
            return CollisionSeverity.NONE

        max_collisions = 0
        cross_branch = False

        for designator in post_levels.values():
            matches = self._get_collisions_for_designator(designator)
            if not matches:
                continue

            max_collisions = max(max_collisions, len(matches))
            if self._has_cross_branch_collision(branch, matches):
                cross_branch = True

        if cross_branch:
            return CollisionSeverity.CROSS_BRANCH
        if max_collisions <= 1:
            return CollisionSeverity.NONE
        if max_collisions == 2:
            return CollisionSeverity.LOW
        if max_collisions == 3:
            return CollisionSeverity.MEDIUM
        return CollisionSeverity.HIGH

    def get_colliding_paths(
        self,
        branch: Branch,
        post_levels: Dict[str, str],
    ) -> List[str]:
        """Return list of other posts this could be confused with."""
        colliding_paths: List[str] = []
        for level, designator in post_levels.items():
            matches = self._get_collisions_for_designator(designator)
            for match in matches:
                match_branch, match_level = self._split_collision_entry(match)
                if match_branch == branch.value and match_level == level:
                    continue
                colliding_paths.append(f"{match_branch}.{match_level}:{designator}")
        return sorted(set(colliding_paths))

    def get_structural_signals_for_branch(self, branch: Branch) -> List[str]:
        """Return level names unique to this branch."""
        branch_terms = self.structural_signals.get("branch_unique_terms", {})
        return [
            term for term, b in branch_terms.items()
            if b == branch.value
        ]

    def _get_collisions_for_designator(self, designator: str) -> List[str]:
        """Return collision index entries for a designator."""
        for section in ("numbers", "letters", "names"):
            matches = self.collision_index.get(section, {}).get(designator)
            if matches:
                return list(matches)
        return []

    def _has_cross_branch_collision(
        self,
        branch: Branch,
        matches: List[str],
    ) -> bool:
        """Check if collision entries include a different branch."""
        for match in matches:
            match_branch, _ = self._split_collision_entry(match)
            if match_branch and match_branch != branch.value:
                return True
        return False

    def _split_collision_entry(self, entry: str) -> (str, str):
        """Split a collision entry into branch and level."""
        if "." not in entry:
            return entry, ""
        branch, level = entry.split(".", 1)
        return branch, level
