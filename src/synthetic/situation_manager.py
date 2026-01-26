"""
SituationManager: Load and assign situations to sources.
"""

import json
import random
from pathlib import Path
from typing import Dict, List, Optional, Any

from .models import Situation, VocabularyPool


class SituationManager:
    """Manages operational situations for synthetic data generation."""

    def __init__(
        self,
        themes_path: Optional[Path] = None,
        vocabulary_path: Optional[Path] = None,
        random_seed: Optional[int] = None,
    ):
        self.rng = random.Random(random_seed)
        self.situations: Dict[str, Situation] = {}
        self.branch_themes: Dict[str, Dict[str, Any]] = {}
        self.situational_terms: Dict[str, List[str]] = {}
        self.assignment_counts: Dict[str, int] = {}

        if themes_path:
            self.load_themes(themes_path)
        if vocabulary_path:
            self.load_vocabulary(vocabulary_path)

        if self.branch_themes and self.situational_terms:
            self._build_situations()

    def load_themes(self, themes_path: Path) -> None:
        """Load themes from JSON file."""
        with open(themes_path, "r") as f:
            data = json.load(f)
        self.branch_themes = data.get("themes", {})

    def load_vocabulary(self, vocabulary_path: Path) -> None:
        """Load vocabulary to seed situation pools."""
        with open(vocabulary_path, "r") as f:
            data = json.load(f)
        self.situational_terms = data.get("situational", {})

    def _build_situations(self) -> None:
        """Create Situation objects per theme."""
        for branch, theme in self.branch_themes.items():
            vocab_pattern = theme.get("vocabulary_pool", "")
            vocab_terms = self._resolve_vocabulary(vocab_pattern)
            pool = VocabularyPool(primary=vocab_terms)

            for situation_id in theme.get("situations", []):
                situation = Situation(
                    situation_id=situation_id,
                    description=f"{branch}:{situation_id}",
                    branch=branch,
                    vocabulary_pool=pool,
                )
                self.situations[situation_id] = situation
                self.assignment_counts[situation_id] = 0

    def _resolve_vocabulary(self, pattern: str) -> List[str]:
        """Resolve a vocabulary pattern into a list of terms."""
        if not pattern:
            return []
        if pattern.endswith("*"):
            prefix = pattern[:-1]
            terms: List[str] = []
            for key, values in self.situational_terms.items():
                if key.startswith(prefix):
                    terms.extend(values)
            return sorted(set(terms))
        return list(self.situational_terms.get(pattern, []))

    def get_situation(self, situation_id: str) -> Optional[Situation]:
        """Get a situation by ID."""
        return self.situations.get(situation_id)

    def list_situations(self) -> List[str]:
        """List all available situation IDs."""
        return list(self.situations.keys())

    def assign_situation(self, branch: str, bias_recent: bool = True) -> Situation:
        """Assign a situation to a source based on branch compatibility."""
        theme = self.branch_themes.get(branch, {})
        candidates = theme.get("situations", [])

        if not candidates:
            raise ValueError(f"No situations available for branch: {branch}")

        if bias_recent and self.assignment_counts:
            used = [sid for sid in candidates if self.assignment_counts.get(sid, 0) > 0]
            if used and self.rng.random() < 0.7:
                weights = [self.assignment_counts[sid] ** 0.5 for sid in used]
                total = sum(weights)
                weights = [w / total for w in weights]
                situation_id = self.rng.choices(used, weights=weights)[0]
            else:
                situation_id = self.rng.choice(candidates)
        else:
            situation_id = self.rng.choice(candidates)

        self.assignment_counts[situation_id] = self.assignment_counts.get(situation_id, 0) + 1
        return self.situations[situation_id]

    def get_archetype_pool(self, branch: str) -> List[str]:
        """Return recommended archetypes for a branch."""
        theme = self.branch_themes.get(branch, {})
        return list(theme.get("clerk_archetypes", []))

    def get_assignment_stats(self) -> Dict[str, Any]:
        """Get statistics about situation assignments."""
        total = sum(self.assignment_counts.values())
        return {
            "total_assignments": total,
            "by_situation": dict(self.assignment_counts),
            "unique_situations_used": sum(1 for c in self.assignment_counts.values() if c > 0),
        }
