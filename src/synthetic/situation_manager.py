"""
SituationManager: Load and assign operational situations to sources.

Situations drive vocabulary selection - all entries in a source share
situational vocabulary because they're from the same event.
"""

import random
from pathlib import Path
from typing import Dict, List, Optional, Any

import yaml

from .models import Situation, VocabularyPool


class SituationManager:
    """
    Manages operational situations for synthetic data generation.

    Each source is assigned ONE situation. Vocabulary comes from that
    situation's pool, providing the signal layer for disambiguation.
    """

    def __init__(
        self,
        style_spec_path: Optional[Path] = None,
        random_seed: Optional[int] = None,
    ):
        """
        Initialize the manager.

        Args:
            style_spec_path: Path to synthetic_style_spec_v3.yaml
            random_seed: Seed for reproducibility
        """
        self.rng = random.Random(random_seed)
        self.situations: Dict[str, Situation] = {}

        # Track which situations have been assigned for distribution modeling
        self.assignment_counts: Dict[str, int] = {}

        if style_spec_path:
            self.load_situations(style_spec_path)

    def load_situations(self, style_spec_path: Path) -> None:
        """Load situations from the style spec YAML."""
        with open(style_spec_path, "r") as f:
            spec = yaml.safe_load(f)

        situations_data = spec.get("situations", {})

        for situation_id, sit_data in situations_data.items():
            situation = self._parse_situation(situation_id, sit_data)
            self.situations[situation_id] = situation
            self.assignment_counts[situation_id] = 0

    def _parse_situation(self, situation_id: str, data: Dict[str, Any]) -> Situation:
        """Parse a situation from YAML data."""
        # Parse vocabulary pool
        vocab_data = data.get("vocabulary_pool", {})
        vocabulary_pool = VocabularyPool(
            primary=vocab_data.get("primary", []),
            secondary=vocab_data.get("secondary", []),
            rare=vocab_data.get("rare", []),
        )

        # Parse applies_to - can be a list or "any"
        applies_to = data.get("applies_to", [])
        if applies_to == "any":
            applies_to = ["any"]
        elif isinstance(applies_to, str):
            applies_to = [applies_to]

        return Situation(
            situation_id=situation_id,
            description=data.get("description", ""),
            theater=data.get("theater", ""),
            operation_type=data.get("operation_type", ""),
            applies_to=applies_to,
            vocabulary_pool=vocabulary_pool,
            date_range=data.get("date_range", []),
        )

    def get_situation(self, situation_id: str) -> Optional[Situation]:
        """Get a situation by ID."""
        return self.situations.get(situation_id)

    def list_situations(self) -> List[str]:
        """List all available situation IDs."""
        return list(self.situations.keys())

    def get_situations_for_component(self, component_id: str) -> List[str]:
        """
        Get situations that apply to a specific component.

        Args:
            component_id: The component ID to filter by

        Returns:
            List of situation IDs that apply to this component
        """
        applicable = []
        for sit_id, situation in self.situations.items():
            if "any" in situation.applies_to or component_id in situation.applies_to:
                applicable.append(sit_id)
        return applicable

    def assign_situation(
        self,
        component_id: str,
        bias_recent: bool = True,
    ) -> Situation:
        """
        Assign a situation to a source based on component compatibility.

        Args:
            component_id: The component the source is associated with
            bias_recent: If True, bias toward recently-used situations (clustering)

        Returns:
            The assigned Situation
        """
        applicable = self.get_situations_for_component(component_id)

        if not applicable:
            # Fall back to generic situations
            applicable = [
                sid for sid, sit in self.situations.items()
                if "any" in sit.applies_to
            ]

        if not applicable:
            raise ValueError(f"No situations available for component: {component_id}")

        if bias_recent and self.assignment_counts:
            # Bias toward situations already used (creates realistic clustering)
            # But with some probability of introducing new ones
            used_situations = [
                sid for sid in applicable
                if self.assignment_counts.get(sid, 0) > 0
            ]

            if used_situations and self.rng.random() < 0.7:
                # Weight by usage count (power law clustering)
                weights = [
                    self.assignment_counts[sid] ** 0.5
                    for sid in used_situations
                ]
                total = sum(weights)
                weights = [w / total for w in weights]

                situation_id = self.rng.choices(used_situations, weights=weights)[0]
            else:
                situation_id = self.rng.choice(applicable)
        else:
            situation_id = self.rng.choice(applicable)

        self.assignment_counts[situation_id] = (
            self.assignment_counts.get(situation_id, 0) + 1
        )

        return self.situations[situation_id]

    def sample_vocabulary(
        self,
        situation: Situation,
        count: int = 1,
        tier: str = "primary",
    ) -> List[str]:
        """
        Sample vocabulary terms from a situation's pool.

        Args:
            situation: The situation to sample from
            count: Number of terms to sample
            tier: Which tier to sample from (primary, secondary, rare)

        Returns:
            List of sampled vocabulary terms
        """
        pool = getattr(situation.vocabulary_pool, tier, [])
        if not pool:
            return []

        count = min(count, len(pool))
        return self.rng.sample(pool, count)

    def sample_vocabulary_weighted(
        self,
        situation: Situation,
        count: int = 1,
    ) -> List[str]:
        """
        Sample vocabulary with weighted tier selection.

        Primary terms are most likely, secondary less so, rare rarely.

        Args:
            situation: The situation to sample from
            count: Number of terms to sample

        Returns:
            List of sampled vocabulary terms
        """
        terms = []
        for _ in range(count):
            r = self.rng.random()
            if r < 0.60:
                tier = "primary"
            elif r < 0.90:
                tier = "secondary"
            else:
                tier = "rare"

            sampled = self.sample_vocabulary(situation, 1, tier)
            if sampled:
                terms.extend(sampled)

        return terms

    def get_assignment_stats(self) -> Dict[str, Any]:
        """Get statistics about situation assignments."""
        total = sum(self.assignment_counts.values())
        return {
            "total_assignments": total,
            "by_situation": dict(self.assignment_counts),
            "unique_situations_used": sum(
                1 for c in self.assignment_counts.values() if c > 0
            ),
        }
