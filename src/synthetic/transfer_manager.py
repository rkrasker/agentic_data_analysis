"""
TransferManager: Apply transfers between soldier states.
"""

from typing import Dict, Tuple

import numpy as np

from .hierarchy_loader import HierarchyLoader
from .models import Branch, TransferScope


class TransferManager:
    """Manages transfers for soldier state transitions."""

    def __init__(self, hierarchy: HierarchyLoader, rng: np.random.Generator):
        self.hierarchy = hierarchy
        self.rng = rng

    def apply_transfer(
        self,
        branch: Branch,
        post_levels: Dict[str, str],
        scope: TransferScope,
    ) -> Tuple[Branch, Dict[str, str]]:
        """Apply a transfer to the current post based on scope."""
        depth = self.hierarchy.get_branch_depth(branch)
        levels = self.hierarchy.get_branch_levels(branch)

        if scope == TransferScope.CROSS_BRANCH:
            return self._transfer_cross_branch(branch)

        if scope == TransferScope.WITHIN_LEVEL3 and depth <= 3:
            scope = TransferScope.WITHIN_LEVEL2

        if scope == TransferScope.WITHIN_LEVEL3:
            keep_levels = levels[:3]
        elif scope == TransferScope.WITHIN_LEVEL2:
            keep_levels = levels[:2]
        else:
            keep_levels = levels[:1]

        new_levels = {
            level: post_levels[level]
            for level in keep_levels
            if level in post_levels
        }

        for level in levels[len(keep_levels):]:
            new_levels[level] = self._sample_level_value(
                branch,
                level,
                exclude=post_levels.get(level),
            )

        return branch, new_levels

    def _transfer_cross_branch(self, branch: Branch) -> Tuple[Branch, Dict[str, str]]:
        """Transfer to a different branch and new post."""
        branches = [b for b in Branch if b != branch]
        new_branch = self.rng.choice(branches)
        return new_branch, self._generate_post(new_branch)

    def _generate_post(self, branch: Branch) -> Dict[str, str]:
        """Generate a new post for a branch."""
        post_levels: Dict[str, str] = {}
        for level in self.hierarchy.get_branch_levels(branch):
            post_levels[level] = self._sample_level_value(branch, level)
        return post_levels

    def _sample_level_value(
        self,
        branch: Branch,
        level: str,
        exclude: str = "",
    ) -> str:
        """Sample a value for a level, avoiding an exclude if possible."""
        values = self.hierarchy.get_level_values(branch, level)
        if not values:
            return exclude
        if exclude and exclude in values and len(values) > 1:
            values = [v for v in values if v != exclude]
        return self.rng.choice(values)
