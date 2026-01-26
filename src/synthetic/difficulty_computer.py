"""
Compute soldier-level difficulty from three layers.
"""

from typing import List

from .completeness_analyzer import CompletenessAnalyzer
from .models import (
    CollisionSeverity,
    DifficultyTier,
    Entry,
    Soldier,
)


class DifficultyComputer:
    """Computes soldier-level difficulty tier."""

    def __init__(self, completeness_analyzer: CompletenessAnalyzer):
        self.completeness_analyzer = completeness_analyzer

    def compute_difficulty(self, soldier: Soldier, entries: List[Entry]) -> Soldier:
        """Compute difficulty metrics and tier for a soldier."""
        collision_zone = any(state.collision_zone_flag for state in soldier.states)
        max_collision_severity = self._max_collision_severity(soldier)

        analysis = self.completeness_analyzer.analyze_soldier_records(soldier, entries)
        complementarity_score = analysis["complementarity_score"]

        structural_resolvability = self._check_structural_resolvability(entries)

        any_complete = any(entry.path_completeness >= 0.95 for entry in entries)

        difficulty_tier = self._assign_tier(
            any_complete=any_complete,
            collision_zone=collision_zone,
            collision_severity=max_collision_severity,
            complementarity_score=complementarity_score,
            structural_resolvability=structural_resolvability,
        )

        soldier.difficulty_tier = difficulty_tier
        soldier.complementarity_score = complementarity_score
        soldier.structural_resolvability = structural_resolvability

        return soldier

    def _max_collision_severity(self, soldier: Soldier) -> CollisionSeverity:
        """Return max collision severity for a soldier."""
        order = {
            CollisionSeverity.NONE: 0,
            CollisionSeverity.LOW: 1,
            CollisionSeverity.MEDIUM: 2,
            CollisionSeverity.HIGH: 3,
            CollisionSeverity.CROSS_BRANCH: 4,
        }
        return max(
            (state.collision_severity for state in soldier.states),
            key=lambda sev: order.get(sev, 0),
            default=CollisionSeverity.NONE,
        )

    def _check_structural_resolvability(self, entries: List[Entry]) -> bool:
        """Check if structural signals can resolve ambiguity."""
        for entry in entries:
            for signal in entry.extraction_signals:
                if signal.startswith("branch_unique:"):
                    return True
                if signal == "depth:5":
                    return True
        return False

    def _assign_tier(
        self,
        any_complete: bool,
        collision_zone: bool,
        collision_severity: CollisionSeverity,
        complementarity_score: float,
        structural_resolvability: bool,
    ) -> DifficultyTier:
        """Assign difficulty tier based on three layers."""
        if any_complete:
            return DifficultyTier.EASY
        if complementarity_score > 0.8 and not collision_zone:
            return DifficultyTier.EASY
        if structural_resolvability and complementarity_score > 0.5:
            return DifficultyTier.EASY

        if not collision_zone and complementarity_score > 0.5:
            return DifficultyTier.MODERATE
        if collision_zone and complementarity_score > 0.6:
            return DifficultyTier.MODERATE
        if structural_resolvability:
            return DifficultyTier.MODERATE

        if collision_severity == CollisionSeverity.CROSS_BRANCH:
            if complementarity_score < 0.3:
                return DifficultyTier.EXTREME
        if collision_zone and complementarity_score < 0.3:
            return DifficultyTier.EXTREME

        return DifficultyTier.HARD
