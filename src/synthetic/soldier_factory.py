"""
SoldierFactory: Generate soldier truth records for Terraform Combine.
"""

from typing import Dict, List, Tuple

import numpy as np

from .hierarchy_loader import HierarchyLoader
from .models import (
    Branch,
    CollisionSeverity,
    Soldier,
    State,
    TransferScope,
)
from .transfer_manager import TransferManager


FIRST_NAMES = [
    "Avery", "Cass", "Dylan", "Emery", "Jules", "Kai", "Logan", "Mira",
    "Nico", "Orion", "Parker", "Quinn", "Rhea", "Sable", "Taryn", "Vera",
    "Wren", "Zane", "Arden", "Brynn", "Corin", "Elias", "Finn", "Galen",
    "Hayes", "Iris", "Kellan", "Lyra", "Maren", "Noel",
]

LAST_NAMES = [
    "Alden", "Baxter", "Calder", "Darrow", "Ellis", "Fenn", "Greer",
    "Hale", "Ivers", "Jarro", "Kade", "Lang", "Morrow", "Nash", "Orin",
    "Pryce", "Quill", "Rowan", "Soren", "Toll", "Ulrich", "Vale", "Wex",
    "Yarrow", "Zev",
]

MIDDLE_INITIALS = list("ABCDEFGHJKLMNOPRSTW")

RANKS = [
    ("Spec-1", 0.22),
    ("Spec-2", 0.20),
    ("Spec-3", 0.16),
    ("Tech-1", 0.14),
    ("Tech-2", 0.10),
    ("Tech-3", 0.06),
    ("Cmdr", 0.05),
    ("Lt", 0.04),
    ("Capt", 0.02),
    ("Chief", 0.01),
]


class SoldierFactory:
    """Factory for generating soldier truth records."""

    def __init__(self, hierarchy: HierarchyLoader, rng: np.random.Generator):
        self.hierarchy = hierarchy
        self.rng = rng
        self.transfer_manager = TransferManager(hierarchy, rng)

        self.rank_names = [r[0] for r in RANKS]
        self.rank_weights = [r[1] for r in RANKS]

    def create_soldier(self, soldier_id: str) -> Soldier:
        """Create a soldier with 1-3 states."""
        name_first, name_middle, name_last = self._generate_name()
        rank = self._generate_rank()

        state_count = self._sample_state_count()
        states = self._generate_states(soldier_id, state_count)

        return Soldier(
            soldier_id=soldier_id,
            name_first=name_first,
            name_middle=name_middle,
            name_last=name_last,
            rank=rank,
            states=states,
        )

    def _generate_name(self) -> Tuple[str, str, str]:
        """Generate a name tuple."""
        first = self.rng.choice(FIRST_NAMES)
        last = self.rng.choice(LAST_NAMES)
        if self.rng.random() < 0.70:
            middle = self.rng.choice(MIDDLE_INITIALS)
        else:
            middle = ""
        return first, middle, last

    def _generate_rank(self) -> str:
        """Sample a rank."""
        return self.rng.choice(self.rank_names, p=self.rank_weights)

    def _sample_state_count(self) -> int:
        """Sample state count: 65% one, 28% two, 7% three."""
        return int(self.rng.choice([1, 2, 3], p=[0.65, 0.28, 0.07]))

    def _sample_branch(self) -> Branch:
        """Sample a branch uniformly."""
        return self.rng.choice(list(Branch))

    def _sample_transfer_scope(self) -> TransferScope:
        """Sample transfer scope for a new state."""
        scopes = [
            TransferScope.WITHIN_LEVEL3,
            TransferScope.WITHIN_LEVEL2,
            TransferScope.WITHIN_BRANCH,
            TransferScope.CROSS_BRANCH,
        ]
        weights = [0.20, 0.30, 0.35, 0.15]
        return self.rng.choice(scopes, p=weights)

    def _generate_states(self, soldier_id: str, state_count: int) -> List[State]:
        """Generate 1-3 states with transfers."""
        states: List[State] = []

        branch = self._sample_branch()
        post_levels = self._generate_post(branch)
        states.append(self._create_state(soldier_id, 1, branch, post_levels))

        for i in range(1, state_count):
            transfer_scope = self._sample_transfer_scope()
            branch, post_levels = self.transfer_manager.apply_transfer(
                states[-1].branch,
                states[-1].post_levels,
                transfer_scope,
            )
            states.append(self._create_state(soldier_id, i + 1, branch, post_levels))

        return states

    def _generate_post(self, branch: Branch) -> Dict[str, str]:
        """Generate a post path for a branch."""
        post_levels: Dict[str, str] = {}
        for level in self.hierarchy.get_branch_levels(branch):
            values = self.hierarchy.get_level_values(branch, level)
            post_levels[level] = self.rng.choice(values)
        return post_levels

    def _build_post_path(self, branch: Branch, post_levels: Dict[str, str]) -> str:
        """Build a full post path string."""
        ordered_levels = self.hierarchy.get_branch_levels(branch)
        parts = [post_levels[level] for level in ordered_levels if level in post_levels]
        return "/".join(parts)

    def _create_state(
        self,
        soldier_id: str,
        state_order: int,
        branch: Branch,
        post_levels: Dict[str, str],
    ) -> State:
        """Create a state with collision zone tagging."""
        post_path = self._build_post_path(branch, post_levels)

        collision_severity = self.hierarchy.get_collision_severity(branch, post_levels)
        collision_zone_flag = collision_severity != CollisionSeverity.NONE
        colliding_paths = self.hierarchy.get_colliding_paths(branch, post_levels)

        return State(
            state_id=f"{soldier_id}-{state_order}",
            soldier_id=soldier_id,
            state_order=state_order,
            branch=branch,
            post_path=post_path,
            post_levels=post_levels,
            collision_zone_flag=collision_zone_flag,
            collision_severity=collision_severity,
            colliding_paths=colliding_paths,
        )
