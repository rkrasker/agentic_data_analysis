"""
Analyze record path coverage for complementarity computation.
"""

from typing import Dict, List, Set

from .hierarchy_loader import HierarchyLoader
from .models import Entry, Soldier


class CompletenessAnalyzer:
    """Analyzes path coverage across records for a soldier."""

    def __init__(self, hierarchy: HierarchyLoader):
        self.hierarchy = hierarchy

    def analyze_soldier_records(
        self,
        soldier: Soldier,
        entries: List[Entry],
    ) -> Dict[str, object]:
        """
        Analyze all records for a soldier.

        Returns:
            {
                "coverage_by_state": Dict[state_id, Set[str]],
                "redundancy_count": Dict[state_id, Dict[str, int]],
                "complementarity_score": float,
            }
        """
        entries_by_state = self._group_by_state(entries)

        results: Dict[str, object] = {
            "coverage_by_state": {},
            "redundancy_count": {},
        }

        for state_id, state_entries in entries_by_state.items():
            state = self._get_state(soldier, state_id)
            if not state:
                continue

            covered_levels: Set[str] = set()
            level_counts: Dict[str, int] = {}

            for entry in state_entries:
                for level in entry.levels_provided:
                    covered_levels.add(level)
                    level_counts[level] = level_counts.get(level, 0) + 1

            results["coverage_by_state"][state_id] = covered_levels
            results["redundancy_count"][state_id] = level_counts

        results["complementarity_score"] = self._compute_complementarity(
            soldier, results
        )

        return results

    def _compute_complementarity(self, soldier: Soldier, analysis: Dict[str, object]) -> float:
        """
        Compute complementarity score (0.0-1.0).

        High score = records cover different levels (complementary)
        Low score = records cover same levels (redundant)
        """
        total_coverage = 0.0
        total_redundancy = 0.0

        for state in soldier.states:
            state_id = state.state_id
            branch_depth = self.hierarchy.get_branch_depth(state.branch)

            covered = analysis["coverage_by_state"].get(state_id, set())
            counts = analysis["redundancy_count"].get(state_id, {})

            coverage = len(covered) / max(branch_depth, 1)

            if counts:
                avg_count = sum(counts.values()) / len(counts)
                redundancy = max(0, avg_count - 1) / avg_count
            else:
                redundancy = 0.0

            total_coverage += coverage
            total_redundancy += redundancy

        n_states = max(len(soldier.states), 1)
        avg_coverage = total_coverage / n_states
        avg_redundancy = total_redundancy / n_states

        return avg_coverage / (1 + avg_redundancy)

    def _group_by_state(self, entries: List[Entry]) -> Dict[str, List[Entry]]:
        """Group entries by state_id."""
        grouped: Dict[str, List[Entry]] = {}
        for entry in entries:
            grouped.setdefault(entry.state_id, []).append(entry)
        return grouped

    def _get_state(self, soldier: Soldier, state_id: str):
        """Find a state for a soldier by state_id."""
        for state in soldier.states:
            if state.state_id == state_id:
                return state
        return None
