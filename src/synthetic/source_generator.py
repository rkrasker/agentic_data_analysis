"""
SourceGenerator: Create source documents with assigned clerks and situations.

A source represents a physical manifest page or list, produced by one clerk
in one situation. All entries share the clerk's locked format and
situational vocabulary.
"""

import random
import uuid
from typing import Dict, List, Optional, Any, Tuple

from .models import (
    Clerk,
    Situation,
    Soldier,
    Source,
    Entry,
    VocabularyDensity,
)
from .clerk_factory import ClerkFactory
from .situation_manager import SituationManager
from .vocabulary_injector import VocabularyInjector


# Quality tier distribution
QUALITY_TIER_WEIGHTS = {
    1: 0.20,  # archival_clean
    2: 0.35,  # standard
    3: 0.25,  # field_worn
    4: 0.15,  # degraded
    5: 0.05,  # fragmentary
}

# Archetype bias by quality tier
ARCHETYPE_BIAS = {
    1: ["hq_formal", "hq_efficient", "repldep_intake"],
    2: ["battalion_methodical", "transport_ship", "marine_fmf"],
    3: ["battalion_rushed", "field_medevac", "aaf_operations"],
    4: ["field_exhausted"],
    5: ["field_exhausted"],
}


class SourceGenerator:
    """
    Generates source documents for synthetic data.

    Each source has:
    - One assigned clerk (locked format)
    - One assigned situation (vocabulary pool)
    - Multiple entries with within-source consistency
    """

    def __init__(
        self,
        clerk_factory: ClerkFactory,
        situation_manager: SituationManager,
        vocabulary_injector: VocabularyInjector,
        random_seed: Optional[int] = None,
    ):
        """
        Initialize the generator.

        Args:
            clerk_factory: Factory for creating clerks
            situation_manager: Manager for situations
            vocabulary_injector: Injector for vocabulary
            random_seed: Seed for reproducibility
        """
        self.rng = random.Random(random_seed)
        self.clerk_factory = clerk_factory
        self.situation_manager = situation_manager
        self.vocabulary_injector = vocabulary_injector

        self._source_counter = 0
        self._entry_counter = 0

        self.sources: Dict[str, Source] = {}
        self.entries: Dict[str, Entry] = {}

    def _generate_source_id(self) -> str:
        """Generate a unique source ID."""
        self._source_counter += 1
        return f"SRC{self._source_counter:05d}"

    def _generate_entry_id(self) -> str:
        """Generate a unique entry ID."""
        self._entry_counter += 1
        return f"ENT{self._entry_counter:06d}"

    def _select_quality_tier(self) -> int:
        """Select a quality tier based on distribution weights."""
        tiers = list(QUALITY_TIER_WEIGHTS.keys())
        weights = [QUALITY_TIER_WEIGHTS[t] for t in tiers]
        return self.rng.choices(tiers, weights=weights)[0]

    def _select_archetype_for_tier(self, tier: int) -> str:
        """Select an archetype biased by quality tier."""
        biased = ARCHETYPE_BIAS.get(tier, [])
        available = self.clerk_factory.list_archetypes()

        # Mix of biased and random selection
        if biased and self.rng.random() < 0.7:
            candidates = [a for a in biased if a in available]
            if candidates:
                return self.rng.choice(candidates)

        return self.clerk_factory.get_random_archetype()

    def create_source(
        self,
        component_id: str,
        quality_tier: Optional[int] = None,
        clerk: Optional[Clerk] = None,
        situation: Optional[Situation] = None,
    ) -> Source:
        """
        Create a new source document.

        Args:
            component_id: The component this source is associated with
            quality_tier: Optional quality tier (1-5), random if None
            clerk: Optional clerk to assign, creates new if None
            situation: Optional situation to assign, selects if None

        Returns:
            A new Source instance
        """
        source_id = self._generate_source_id()

        # Select quality tier
        if quality_tier is None:
            quality_tier = self._select_quality_tier()

        # Create or use clerk
        if clerk is None:
            archetype_id = self._select_archetype_for_tier(quality_tier)
            clerk = self.clerk_factory.create_clerk(archetype_id)

        # Assign situation
        if situation is None:
            situation = self.situation_manager.assign_situation(component_id)

        # Pre-select vocabulary for within-source consistency
        selected_vocabulary = self.vocabulary_injector.select_source_vocabulary(
            situation, count=3
        )

        source = Source(
            source_id=source_id,
            clerk_id=clerk.clerk_id,
            situation_id=situation.situation_id,
            quality_tier=quality_tier,
            entry_ids=[],
            selected_vocabulary=selected_vocabulary,
        )

        self.sources[source_id] = source
        return source

    def generate_entries(
        self,
        source: Source,
        soldiers: List[Soldier],
        render_func: callable,
    ) -> List[Entry]:
        """
        Generate entries for a source.

        Args:
            source: The source document
            soldiers: List of soldiers to include
            render_func: Function to render soldier data to text

        Returns:
            List of Entry objects
        """
        clerk = self.clerk_factory.get_clerk(source.clerk_id)
        situation = self.situation_manager.get_situation(source.situation_id)

        if not clerk or not situation:
            raise ValueError(f"Invalid source state: {source.source_id}")

        entries = []
        total = len(soldiers)

        for i, soldier in enumerate(soldiers):
            position_ratio = i / max(total, 1)

            # Render base entry using clerk's format
            base_text = render_func(soldier, clerk)

            # Inject vocabulary
            final_text, injected = self.vocabulary_injector.inject_vocabulary(
                base_text,
                clerk,
                situation,
                situational_terms=source.selected_vocabulary,
            )

            # Apply within-source consistency and fatigue
            final_text = self._apply_consistency(
                final_text, clerk, position_ratio
            )

            entry_id = self._generate_entry_id()

            # Track which assignment was rendered for transferred soldiers
            is_original = soldier.has_transfer and soldier.original_assignment is not None
            is_new = soldier.has_transfer

            entry = Entry(
                entry_id=entry_id,
                source_id=source.source_id,
                soldier_id=soldier.primary_id,
                raw_text=final_text,
                is_original_assignment=is_original and self.rng.random() < 0.5,
                is_new_assignment=is_new and self.rng.random() >= 0.5,
                clutter_terms=injected.get("clutter", []),
                confounder_terms=injected.get("confounder", []),
                situational_terms=injected.get("situational", []),
            )

            entries.append(entry)
            source.entry_ids.append(entry_id)
            self.entries[entry_id] = entry

            clerk.entry_count += 1

        return entries

    def _apply_consistency(
        self,
        text: str,
        clerk: Clerk,
        position_ratio: float,
    ) -> str:
        """
        Apply within-source consistency and fatigue effects.

        Args:
            text: The entry text
            clerk: The clerk producing the entry
            position_ratio: Position in batch (0.0 to 1.0)

        Returns:
            Modified text with consistency/fatigue applied
        """
        # Determine format consistency
        r = self.rng.random()

        if r < clerk.consistency.format_lock:
            # Identical format - no changes
            return text
        elif r < clerk.consistency.format_lock + clerk.consistency.minor_drift:
            # Minor drift - spacing or capitalization changes
            return self._apply_minor_drift(text)
        else:
            # Major variation - rare format switch
            return self._apply_major_variation(text, clerk)

        # Apply fatigue for late-batch entries
        if position_ratio > 0.8:
            text = self._apply_fatigue(text, clerk)

        return text

    def _apply_minor_drift(self, text: str) -> str:
        """Apply minor formatting drift."""
        # Random spacing changes
        if self.rng.random() < 0.3:
            text = text.replace(", ", ",  ")
        if self.rng.random() < 0.2:
            text = text.replace(" ", "  ", 1)
        return text

    def _apply_major_variation(self, text: str, clerk: Clerk) -> str:
        """Apply major format variation (rare)."""
        # For now, just add some variation
        if self.rng.random() < 0.5:
            # Capitalization change
            return text.upper() if text[0].islower() else text.lower()
        return text

    def _apply_fatigue(self, text: str, clerk: Clerk) -> str:
        """Apply fatigue effects for late-batch entries."""
        # Increase typo rate
        if self.rng.random() < clerk.imperfections.typo_rate * 2:
            # Simple typo: duplicate character
            if len(text) > 5:
                pos = self.rng.randint(2, len(text) - 2)
                text = text[:pos] + text[pos] + text[pos:]

        # Trailing off
        if self.rng.random() < clerk.imperfections.trailing_off * 1.5:
            # Truncate at a comma or space
            parts = text.rsplit(",", 1)
            if len(parts) > 1:
                text = parts[0]

        return text

    def get_entries_per_source_count(self) -> int:
        """
        Get a random entry count for a source.

        Based on normal distribution from spec:
        mean=35, std=15, min=8, max=80
        """
        count = int(self.rng.gauss(35, 15))
        return max(8, min(80, count))

    def get_source(self, source_id: str) -> Optional[Source]:
        """Get a source by ID."""
        return self.sources.get(source_id)

    def get_entry(self, entry_id: str) -> Optional[Entry]:
        """Get an entry by ID."""
        return self.entries.get(entry_id)

    def get_stats(self) -> Dict[str, Any]:
        """Get generation statistics."""
        entries_by_source = {}
        for entry in self.entries.values():
            entries_by_source[entry.source_id] = (
                entries_by_source.get(entry.source_id, 0) + 1
            )

        return {
            "total_sources": len(self.sources),
            "total_entries": len(self.entries),
            "avg_entries_per_source": (
                sum(entries_by_source.values()) / max(len(self.sources), 1)
            ),
            "by_quality_tier": self._count_by_tier(),
        }

    def _count_by_tier(self) -> Dict[int, int]:
        """Count sources by quality tier."""
        counts: Dict[int, int] = {}
        for source in self.sources.values():
            counts[source.quality_tier] = counts.get(source.quality_tier, 0) + 1
        return counts
