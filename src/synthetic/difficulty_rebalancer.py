"""
Adjust generation to hit target difficulty distribution.
"""

from typing import Dict, List

from .models import DifficultyTier, Soldier


class DifficultyRebalancer:
    """Rebalances generated data to hit target difficulty distribution."""

    TARGET_DISTRIBUTION = {
        DifficultyTier.EASY: 0.50,
        DifficultyTier.MODERATE: 0.30,
        DifficultyTier.HARD: 0.15,
        DifficultyTier.EXTREME: 0.05,
    }
    TOLERANCE = 0.05

    def needs_rebalancing(self, soldiers: List[Soldier]) -> bool:
        """Check if current distribution is outside tolerance."""
        actual = self._compute_distribution(soldiers)
        for tier, target in self.TARGET_DISTRIBUTION.items():
            if abs(actual.get(tier, 0) - target) > self.TOLERANCE:
                return True
        return False

    def identify_adjustments(self, soldiers: List[Soldier]) -> Dict[str, object]:
        """Identify what adjustments are needed."""
        actual = self._compute_distribution(soldiers)

        over = [
            t for t, target in self.TARGET_DISTRIBUTION.items()
            if actual.get(t, 0) > target + self.TOLERANCE
        ]
        under = [
            t for t, target in self.TARGET_DISTRIBUTION.items()
            if actual.get(t, 0) < target - self.TOLERANCE
        ]

        soldiers_to_adjust = [
            s.soldier_id for s in soldiers
            if s.difficulty_tier in over
        ]

        return {
            "over_represented": over,
            "under_represented": under,
            "soldiers_to_adjust": soldiers_to_adjust[: len(soldiers_to_adjust) // 2],
            "adjustment_strategy": self._determine_strategy(over, under),
        }

    def _determine_strategy(
        self,
        over: List[DifficultyTier],
        under: List[DifficultyTier],
    ) -> str:
        """Determine adjustment strategy."""
        if DifficultyTier.EASY in over and DifficultyTier.HARD in under:
            return "move_to_collision_zone"
        if DifficultyTier.HARD in over and DifficultyTier.EASY in under:
            return "add_complementary_records"
        return "regenerate_selected"

    def _compute_distribution(self, soldiers: List[Soldier]) -> Dict[DifficultyTier, float]:
        """Compute actual difficulty distribution."""
        counts = {tier: 0 for tier in DifficultyTier}
        for soldier in soldiers:
            if soldier.difficulty_tier:
                counts[soldier.difficulty_tier] += 1

        total = len(soldiers)
        return {tier: count / max(total, 1) for tier, count in counts.items()}
