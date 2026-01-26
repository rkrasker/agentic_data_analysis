"""
SourceGenerator: Create source documents with assigned clerks and situations.
"""

import random
from typing import Dict, Optional

from .models import Branch, Clerk, Situation, Source
from .clerk_factory import ClerkFactory
from .situation_manager import SituationManager


QUALITY_TIER_WEIGHTS = {
    1: 0.20,
    2: 0.35,
    3: 0.25,
    4: 0.15,
    5: 0.05,
}

ARCHETYPE_BIAS = {
    1: ["sector_formal", "sector_efficient", "processing_intake"],
    2: ["fleet_methodical", "transport_shuttle", "sector_efficient"],
    3: ["fleet_rushed", "field_medevac", "defense_squadron"],
    4: ["field_exhausted", "expeditionary_field"],
    5: ["field_exhausted", "field_minimal"],
}


class SourceGenerator:
    """Generates source documents for synthetic data."""

    def __init__(
        self,
        clerk_factory: ClerkFactory,
        situation_manager: SituationManager,
        random_seed: Optional[int] = None,
    ):
        self.rng = random.Random(random_seed)
        self.clerk_factory = clerk_factory
        self.situation_manager = situation_manager
        self._source_counter = 0
        self.sources: Dict[str, Source] = {}

    def _generate_source_id(self) -> str:
        """Generate a unique source ID."""
        self._source_counter += 1
        return f"SRC{self._source_counter:05d}"

    def _select_quality_tier(self) -> int:
        """Select a quality tier based on distribution weights."""
        tiers = list(QUALITY_TIER_WEIGHTS.keys())
        weights = [QUALITY_TIER_WEIGHTS[t] for t in tiers]
        return self.rng.choices(tiers, weights=weights)[0]

    def _select_archetype_for_tier(self, tier: int, branch: Branch) -> str:
        """Select an archetype biased by quality tier and branch."""
        biased = ARCHETYPE_BIAS.get(tier, [])
        available = set(self.clerk_factory.list_archetypes())
        allowed = [
            archetype for archetype in self.situation_manager.get_archetype_pool(branch.value)
            if archetype in available
        ]
        biased = [archetype for archetype in biased if archetype in available]

        if biased and self.rng.random() < 0.7:
            candidates = [a for a in biased if not allowed or a in allowed]
            if candidates:
                return self.rng.choice(candidates)

        if allowed:
            return self.rng.choice(allowed)

        return self.clerk_factory.get_random_archetype()

    def create_source(
        self,
        branch: Branch,
        home_unit: str,
        temporal_anchor: Optional[int] = None,
        quality_tier: Optional[int] = None,
        clerk: Optional[Clerk] = None,
        situation: Optional[Situation] = None,
    ) -> Source:
        """Create a new source document."""
        source_id = self._generate_source_id()

        if quality_tier is None:
            quality_tier = self._select_quality_tier()

        if clerk is None:
            archetype_id = self._select_archetype_for_tier(quality_tier, branch)
            clerk = self.clerk_factory.create_clerk(archetype_id)

        if situation is None:
            situation = self.situation_manager.assign_situation(branch.value)

        if temporal_anchor is None:
            temporal_anchor = self.rng.choice([1, 2, 3])

        source = Source(
            source_id=source_id,
            clerk_id=clerk.clerk_id,
            situation_id=situation.situation_id,
            quality_tier=quality_tier,
            home_unit=home_unit,
            temporal_anchor=int(temporal_anchor),
        )

        self.sources[source_id] = source
        return source

    def get_source(self, source_id: str) -> Optional[Source]:
        """Get a source by ID."""
        return self.sources.get(source_id)
