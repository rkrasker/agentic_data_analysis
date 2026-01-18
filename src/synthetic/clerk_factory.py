"""
ClerkFactory: Instantiate clerks from archetypes with locked habits.

Each clerk is a persistent character whose style never changes.
"""

import json
import random
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Any

import yaml

from .models import (
    Clerk,
    ClerkArchetype,
    NameFormat,
    RankFormat,
    UnitFormat,
    Consistency,
    Imperfections,
    RankStyle,
    RankForm,
    UnitFormatStyle,
    VocabularyDensity,
)


# Clerk names for generating realistic clerk instances
CLERK_FIRST_NAMES = [
    "Helen", "Margaret", "Dorothy", "Ruth", "Virginia", "Mary", "Elizabeth",
    "Robert", "James", "William", "John", "Richard", "Thomas", "Charles",
    "Edward", "Frank", "George", "Harold", "Joseph", "Paul", "Walter",
]

CLERK_LAST_NAMES = [
    "Marchetti", "Trane", "Hollis", "Delacroix", "Wojcik", "Calabrese",
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Miller", "Davis",
    "Garcia", "Rodriguez", "Wilson", "Martinez", "Anderson", "Taylor",
    "Thomas", "Moore", "Jackson", "Martin", "Lee", "Thompson", "White",
    "Harris", "Clark", "Lewis", "Robinson", "Walker", "Young", "Allen",
]

CLERK_RANKS = ["Pvt.", "Pfc.", "Cpl.", "T/5", "Sgt.", "S/Sgt.", "T/Sgt."]


class ClerkFactory:
    """
    Factory for creating clerk instances from archetypes.

    Clerks are instantiated with their habits locked - they never change
    their formatting style within a session.
    """

    def __init__(
        self,
        style_spec_path: Optional[Path] = None,
        random_seed: Optional[int] = None,
    ):
        """
        Initialize the factory.

        Args:
            style_spec_path: Path to synthetic_style_spec_v3.yaml
            random_seed: Seed for reproducibility
        """
        self.rng = random.Random(random_seed)
        self.archetypes: Dict[str, ClerkArchetype] = {}
        self.clerks: Dict[str, Clerk] = {}
        self._clerk_counter = 0

        if style_spec_path:
            self.load_archetypes(style_spec_path)

    def load_archetypes(self, style_spec_path: Path) -> None:
        """Load clerk archetypes from the style spec YAML."""
        with open(style_spec_path, "r") as f:
            spec = yaml.safe_load(f)

        clerk_archetypes = spec.get("clerk_archetypes", {})

        for archetype_id, arch_data in clerk_archetypes.items():
            archetype = self._parse_archetype(archetype_id, arch_data)
            self.archetypes[archetype_id] = archetype

    def _parse_archetype(self, archetype_id: str, data: Dict[str, Any]) -> ClerkArchetype:
        """Parse an archetype from YAML data."""
        # Parse name format
        name_data = data.get("name_format", {})
        name_format = NameFormat(
            template=name_data.get("template", "{LAST}, {FIRST}"),
            drop_middle_rate=name_data.get("drop_middle_rate", 0.0),
        )

        # Parse rank format
        rank_data = data.get("rank_format", {})
        rank_format = RankFormat(
            style=RankStyle(rank_data.get("style", "prefix")),
            form=RankForm(rank_data.get("form", "proper_abbrev")),
            omit_rate=rank_data.get("omit_rate", 0.0),
        )

        # Parse unit format
        unit_data = data.get("unit_format", {})
        unit_format = UnitFormat(
            style=UnitFormatStyle(unit_data.get("style", "labeled_hierarchical")),
            separator=unit_data.get("separator", ", "),
            orientation=unit_data.get("orientation", "child_over_parent"),
            include_division=unit_data.get("include_division", True),
            include_regiment=unit_data.get("include_regiment", True),
            include_company=unit_data.get("include_company", True),
            division_suffix=unit_data.get("division_suffix", False),
            label_style=unit_data.get("label_style", "abbreviated"),
            phonetic_companies=unit_data.get("phonetic_companies", False),
            marine_regiment_style=unit_data.get("marine_regiment_style", "Mar"),
            include_air_force=unit_data.get("include_air_force", True),
            omit_unit_type=unit_data.get("omit_unit_type", False),
        )

        # Parse consistency
        consistency_data = data.get("consistency", {})
        consistency = Consistency(
            format_lock=consistency_data.get("format_lock", 0.85),
            minor_drift=consistency_data.get("minor_drift", 0.12),
            major_variation=consistency_data.get("major_variation", 0.03),
        )

        # Parse imperfections
        imp_data = data.get("imperfections", {})
        imperfections = Imperfections(
            typo_rate=imp_data.get("typo_rate", 0.02),
            abbreviation_inconsistency=imp_data.get("abbreviation_inconsistency", 0.05),
            trailing_off=imp_data.get("trailing_off", 0.0),
            mid_entry_corrections=imp_data.get("mid_entry_corrections", 0.0),
            incomplete_unit=imp_data.get("incomplete_unit", 0.0),
            column_bleed=imp_data.get("column_bleed", 0.0),
        )

        # Parse vocabulary
        vocab_density_str = data.get("vocabulary_density", "medium")
        vocabulary_density = VocabularyDensity(vocab_density_str)
        vocabulary_bias = data.get("vocabulary_bias", [])

        return ClerkArchetype(
            archetype_id=archetype_id,
            description=data.get("description", ""),
            context_level=data.get("context_level", "unknown"),
            name_format=name_format,
            rank_format=rank_format,
            unit_format=unit_format,
            vocabulary_density=vocabulary_density,
            vocabulary_bias=vocabulary_bias,
            consistency=consistency,
            imperfections=imperfections,
        )

    def create_clerk(
        self,
        archetype_id: str,
        clerk_name: Optional[str] = None,
        context: Optional[str] = None,
    ) -> Clerk:
        """
        Create a new clerk instance from an archetype.

        Args:
            archetype_id: The archetype to instantiate from
            clerk_name: Optional name for the clerk (auto-generated if None)
            context: Optional context description

        Returns:
            A new Clerk instance with locked habits
        """
        if archetype_id not in self.archetypes:
            raise ValueError(f"Unknown archetype: {archetype_id}")

        archetype = self.archetypes[archetype_id]
        self._clerk_counter += 1

        # Generate clerk ID
        clerk_id = f"CLK{self._clerk_counter:04d}"

        # Generate clerk name if not provided
        if clerk_name is None:
            rank = self.rng.choice(CLERK_RANKS)
            first = self.rng.choice(CLERK_FIRST_NAMES)
            last = self.rng.choice(CLERK_LAST_NAMES)
            clerk_name = f"{rank} {first} {last}"

        # Generate context if not provided
        if context is None:
            context = f"{archetype.description.strip().split('.')[0]}."

        # Apply minor individual variation to habits
        name_format = self._vary_name_format(archetype.name_format)
        rank_format = self._vary_rank_format(archetype.rank_format)
        unit_format = self._vary_unit_format(archetype.unit_format)
        consistency = self._vary_consistency(archetype.consistency)
        imperfections = self._vary_imperfections(archetype.imperfections)

        clerk = Clerk(
            clerk_id=clerk_id,
            archetype_id=archetype_id,
            name=clerk_name,
            context=context,
            name_format=name_format,
            rank_format=rank_format,
            unit_format=unit_format,
            vocabulary_density=archetype.vocabulary_density,
            vocabulary_bias=list(archetype.vocabulary_bias),
            consistency=consistency,
            imperfections=imperfections,
            used_vocabulary=[],
            entry_count=0,
        )

        self.clerks[clerk_id] = clerk
        return clerk

    def _vary_name_format(self, base: NameFormat) -> NameFormat:
        """Apply minor individual variation to name format."""
        # Name format is typically locked - only vary drop rate slightly
        return NameFormat(
            template=base.template,
            drop_middle_rate=self._vary_rate(base.drop_middle_rate, 0.05),
        )

    def _vary_rank_format(self, base: RankFormat) -> RankFormat:
        """Apply minor individual variation to rank format."""
        return RankFormat(
            style=base.style,
            form=base.form,
            omit_rate=self._vary_rate(base.omit_rate, 0.03),
        )

    def _vary_unit_format(self, base: UnitFormat) -> UnitFormat:
        """Apply minor individual variation to unit format."""
        # Unit format is typically locked - minimal variation
        return UnitFormat(
            style=base.style,
            separator=base.separator,
            orientation=base.orientation,
            include_division=base.include_division,
            include_regiment=base.include_regiment,
            include_company=base.include_company,
            division_suffix=base.division_suffix,
            label_style=base.label_style,
            phonetic_companies=base.phonetic_companies,
            marine_regiment_style=base.marine_regiment_style,
            include_air_force=base.include_air_force,
            omit_unit_type=base.omit_unit_type,
        )

    def _vary_consistency(self, base: Consistency) -> Consistency:
        """Apply minor individual variation to consistency rates."""
        return Consistency(
            format_lock=self._vary_rate(base.format_lock, 0.05),
            minor_drift=self._vary_rate(base.minor_drift, 0.03),
            major_variation=self._vary_rate(base.major_variation, 0.02),
        )

    def _vary_imperfections(self, base: Imperfections) -> Imperfections:
        """Apply minor individual variation to imperfection rates."""
        return Imperfections(
            typo_rate=self._vary_rate(base.typo_rate, 0.02),
            abbreviation_inconsistency=self._vary_rate(base.abbreviation_inconsistency, 0.03),
            trailing_off=self._vary_rate(base.trailing_off, 0.02),
            mid_entry_corrections=self._vary_rate(base.mid_entry_corrections, 0.02),
            incomplete_unit=self._vary_rate(base.incomplete_unit, 0.03),
            column_bleed=self._vary_rate(base.column_bleed, 0.02),
        )

    def _vary_rate(self, base_rate: float, max_variation: float) -> float:
        """Apply random variation to a rate, keeping it in [0, 1]."""
        variation = self.rng.uniform(-max_variation, max_variation)
        return max(0.0, min(1.0, base_rate + variation))

    def get_clerk(self, clerk_id: str) -> Optional[Clerk]:
        """Get a clerk by ID."""
        return self.clerks.get(clerk_id)

    def get_random_archetype(
        self,
        context_levels: Optional[List[str]] = None,
    ) -> str:
        """
        Get a random archetype ID, optionally filtered by context level.

        Args:
            context_levels: Optional list of context levels to filter by

        Returns:
            A random archetype ID
        """
        candidates = list(self.archetypes.keys())

        if context_levels:
            candidates = [
                aid for aid, arch in self.archetypes.items()
                if arch.context_level in context_levels
            ]

        if not candidates:
            raise ValueError(f"No archetypes found for context levels: {context_levels}")

        return self.rng.choice(candidates)

    def get_archetype(self, archetype_id: str) -> Optional[ClerkArchetype]:
        """Get an archetype by ID."""
        return self.archetypes.get(archetype_id)

    def list_archetypes(self) -> List[str]:
        """List all available archetype IDs."""
        return list(self.archetypes.keys())

    def list_clerks(self) -> List[str]:
        """List all created clerk IDs."""
        return list(self.clerks.keys())

    def get_clerk_stats(self) -> Dict[str, Any]:
        """Get statistics about created clerks."""
        archetype_counts: Dict[str, int] = {}
        total_entries = 0

        for clerk in self.clerks.values():
            archetype_counts[clerk.archetype_id] = (
                archetype_counts.get(clerk.archetype_id, 0) + 1
            )
            total_entries += clerk.entry_count

        return {
            "total_clerks": len(self.clerks),
            "total_entries": total_entries,
            "by_archetype": archetype_counts,
        }
