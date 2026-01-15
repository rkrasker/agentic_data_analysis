"""
Pipeline: Wire all components together for synthetic data generation.

Produces raw.parquet and validation.parquet files.
"""

import random
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

from .models import Soldier, Source, Entry, Transfer, Assignment
from .clerk_factory import ClerkFactory
from .situation_manager import SituationManager
from .vocabulary_injector import VocabularyInjector
from .source_generator import SourceGenerator
from .transfer_manager import TransferManager
from .hierarchy_loader import HierarchyLoader
from .soldier_factory import SoldierFactory
from .renderer import Renderer


# Default component distribution weights
COMPONENT_WEIGHTS = {
    "1st_infantry_division": 0.12,
    "2nd_infantry_division": 0.06,
    "3rd_infantry_division": 0.06,
    "82nd_airborne_division": 0.10,
    "101st_airborne_division": 0.10,
    "1st_marine_division": 0.10,
    "2nd_marine_division": 0.08,
    "3rd_marine_division": 0.08,
    "1st_armored_division": 0.05,
    "2nd_armored_division": 0.05,
    "10th_mountain_division": 0.05,
    "8th_air_force": 0.06,
    "9th_air_force": 0.04,
    "15th_air_force": 0.03,
    "36th_infantry_division": 0.02,
}


class Pipeline:
    """
    Main pipeline for synthetic data generation.

    Orchestrates all components to produce synthetic datasets
    matching the v3 spec.
    """

    def __init__(
        self,
        style_spec_path: Path,
        vocabulary_path: Path,
        hierarchy_path: Path,
        random_seed: Optional[int] = None,
    ):
        """
        Initialize the pipeline with all required config paths.

        Args:
            style_spec_path: Path to synthetic_style_spec_v3.yaml
            vocabulary_path: Path to synthetic_vocabulary.json
            hierarchy_path: Path to hierarchy_reference.json
            random_seed: Seed for reproducibility
        """
        self.rng = random.Random(random_seed)
        self.seed = random_seed

        # Initialize all components
        self.clerk_factory = ClerkFactory(
            style_spec_path=style_spec_path,
            random_seed=random_seed,
        )
        self.situation_manager = SituationManager(
            style_spec_path=style_spec_path,
            random_seed=random_seed,
        )
        self.vocabulary_injector = VocabularyInjector(
            vocabulary_path=vocabulary_path,
            random_seed=random_seed,
        )
        self.transfer_manager = TransferManager(
            random_seed=random_seed,
        )
        self.hierarchy_loader = HierarchyLoader(
            hierarchy_path=hierarchy_path,
        )
        self.soldier_factory = SoldierFactory(
            hierarchy_loader=self.hierarchy_loader,
            random_seed=random_seed,
        )
        self.renderer = Renderer(
            hierarchy_loader=self.hierarchy_loader,
            random_seed=random_seed,
        )
        self.source_generator = SourceGenerator(
            clerk_factory=self.clerk_factory,
            situation_manager=self.situation_manager,
            vocabulary_injector=self.vocabulary_injector,
            random_seed=random_seed,
        )

        # Storage
        self.soldiers: Dict[str, Soldier] = {}
        self.sources: Dict[str, Source] = {}
        self.entries: Dict[str, Entry] = {}

    def generate(
        self,
        target_records: int = 10000,
        soldiers_count: Optional[int] = None,
        component_weights: Optional[Dict[str, float]] = None,
    ) -> Tuple[List[Dict], List[Dict], List[Dict]]:
        """
        Generate synthetic dataset.

        Args:
            target_records: Target number of raw entries to generate
            soldiers_count: Number of unique soldiers (auto-calculated if None)
            component_weights: Distribution weights by component

        Returns:
            Tuple of (raw_records, validation_records, transfer_records)
        """
        if component_weights is None:
            component_weights = COMPONENT_WEIGHTS

        # Calculate soldier count if not provided
        # Assume ~2-3 entries per soldier on average
        if soldiers_count is None:
            soldiers_count = target_records // 3

        # Phase 1: Generate soldiers
        print(f"Generating {soldiers_count} soldiers...")
        self._generate_soldiers(soldiers_count, component_weights)

        # Phase 2: Apply transfers
        print("Applying transfers...")
        self._apply_transfers()

        # Phase 3: Generate sources and entries
        print(f"Generating entries (target: {target_records})...")
        self._generate_entries(target_records)

        # Phase 4: Export records
        print("Preparing export records...")
        raw_records = self._build_raw_records()
        validation_records = self._build_validation_records()
        transfer_records = self.transfer_manager.to_records()

        print(f"Generated {len(raw_records)} raw entries")
        print(f"Generated {len(validation_records)} validation records")
        print(f"Generated {len(transfer_records)} transfer records")

        return raw_records, validation_records, transfer_records

    def _generate_soldiers(
        self,
        count: int,
        component_weights: Dict[str, float],
    ) -> None:
        """Generate soldiers across components."""
        components = list(component_weights.keys())
        weights = [component_weights[c] for c in components]

        # Normalize weights
        total = sum(weights)
        weights = [w / total for w in weights]

        # Distribute soldiers by component
        for _ in range(count):
            component_id = self.rng.choices(components, weights=weights)[0]
            soldier = self.soldier_factory.create_soldier(component_id)
            self.soldiers[soldier.primary_id] = soldier

    def _apply_transfers(self) -> None:
        """Apply transfers to soldiers."""
        soldiers_list = list(self.soldiers.values())

        # Build available regiments by component
        available_regiments = {}
        for comp_id in self.hierarchy_loader.list_components():
            regs = self.hierarchy_loader.get_regiments(comp_id)
            if regs:
                available_regiments[comp_id] = regs

        # Apply transfers
        self.transfer_manager.apply_transfers_to_soldiers(
            soldiers_list,
            available_regiments=available_regiments,
            available_divisions=self.hierarchy_loader.get_all_divisions(),
        )

    def _generate_entries(self, target_records: int) -> None:
        """Generate sources and entries until target is reached."""
        soldiers_list = list(self.soldiers.values())
        total_entries = 0

        while total_entries < target_records:
            # Select soldiers for this source
            source_size = self.source_generator.get_entries_per_source_count()
            source_size = min(source_size, target_records - total_entries)

            if source_size <= 0:
                break

            # Sample soldiers (with possible duplicates for multi-appearance)
            source_soldiers = self._sample_soldiers_for_source(
                soldiers_list, source_size
            )

            if not source_soldiers:
                break

            # Determine component for this source (majority component)
            component_counts: Dict[str, int] = {}
            for s in source_soldiers:
                cid = s.assignment.component_id
                component_counts[cid] = component_counts.get(cid, 0) + 1

            primary_component = max(component_counts, key=component_counts.get)

            # Create source
            source = self.source_generator.create_source(primary_component)
            self.sources[source.source_id] = source

            # Generate entries
            # Render function that handles transfer assignment selection
            def render_with_transfer(soldier, clerk):
                assignment = None  # Use current assignment by default
                if soldier.has_transfer and soldier.original_assignment:
                    # 50% chance to use original assignment for transferred soldiers
                    if self.rng.random() < 0.5:
                        assignment = soldier.original_assignment
                return self.renderer.render(soldier, clerk, assignment=assignment)

            entries = self.source_generator.generate_entries(
                source,
                source_soldiers,
                render_func=render_with_transfer,
            )

            for entry in entries:
                self.entries[entry.entry_id] = entry

            total_entries += len(entries)

    def _sample_soldiers_for_source(
        self,
        soldiers: List[Soldier],
        count: int,
    ) -> List[Soldier]:
        """
        Sample soldiers for a source with unit concentration.

        Args:
            soldiers: Pool of available soldiers
            count: Number of soldiers to sample

        Returns:
            List of soldiers (may include duplicates for multi-appearance)
        """
        if not soldiers:
            return []

        # Select a primary component (70% from same battalion)
        primary = self.rng.choice(soldiers)
        same_component = [
            s for s in soldiers
            if s.assignment.component_id == primary.assignment.component_id
        ]

        result = []
        for _ in range(count):
            if self.rng.random() < 0.70 and same_component:
                # Same component
                soldier = self.rng.choice(same_component)
            else:
                # Any soldier
                soldier = self.rng.choice(soldiers)

            result.append(soldier)

        return result

    def _build_raw_records(self) -> List[Dict[str, Any]]:
        """Build raw records for parquet export."""
        records = []

        for entry in self.entries.values():
            source = self.sources.get(entry.source_id)
            if not source:
                continue

            record = {
                "source_id": entry.source_id,
                "soldier_id": entry.soldier_id,
                "raw_text": entry.raw_text,
                "clerk_id": source.clerk_id,
                "situation_id": source.situation_id,
                "quality_tier": source.quality_tier,
            }
            records.append(record)

        return records

    def _build_validation_records(self) -> List[Dict[str, Any]]:
        """Build validation (truth) records for parquet export."""
        records = []

        for soldier in self.soldiers.values():
            record = {
                "primary_id": soldier.primary_id,
                "name_first": soldier.name_first,
                "name_middle": soldier.name_middle,
                "name_last": soldier.name_last,
                "rank": soldier.rank,
                "component_id": soldier.assignment.component_id,
                "regiment": soldier.assignment.regiment,
                "battalion": soldier.assignment.battalion,
                "company": soldier.assignment.company,
                "combat_command": soldier.assignment.combat_command,
                "bomb_group": soldier.assignment.bomb_group,
                "squadron": soldier.assignment.squadron,
                "has_transfer": soldier.has_transfer,
            }

            # Add original assignment if transferred
            if soldier.has_transfer and soldier.original_assignment:
                record["original_component_id"] = soldier.original_assignment.component_id
                record["original_regiment"] = soldier.original_assignment.regiment
                record["original_battalion"] = soldier.original_assignment.battalion
                record["original_company"] = soldier.original_assignment.company

            records.append(record)

        return records

    def export_parquet(
        self,
        output_dir: Path,
        raw_records: List[Dict],
        validation_records: List[Dict],
        transfer_records: List[Dict],
    ) -> None:
        """
        Export records to parquet files (with CSV fallback).

        Args:
            output_dir: Directory to write parquet files
            raw_records: Raw entry records
            validation_records: Truth records
            transfer_records: Transfer records
        """
        try:
            import pandas as pd
        except ImportError:
            raise ImportError("pandas is required for export")

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Check if parquet is available
        parquet_available = True
        try:
            import pyarrow
        except ImportError:
            try:
                import fastparquet
            except ImportError:
                parquet_available = False
                print("Note: pyarrow not available, using CSV export")

        ext = ".parquet" if parquet_available else ".csv"

        # Export raw
        if raw_records:
            raw_df = pd.DataFrame(raw_records)
            if parquet_available:
                raw_df.to_parquet(output_dir / "raw.parquet", index=False)
            else:
                raw_df.to_csv(output_dir / "raw.csv", index=False)
            print(f"Wrote {len(raw_df)} records to {output_dir}/raw{ext}")

        # Export validation
        if validation_records:
            val_df = pd.DataFrame(validation_records)
            if parquet_available:
                val_df.to_parquet(output_dir / "validation.parquet", index=False)
            else:
                val_df.to_csv(output_dir / "validation.csv", index=False)
            print(f"Wrote {len(val_df)} records to {output_dir}/validation{ext}")

        # Export unit_changes
        if transfer_records:
            transfer_df = pd.DataFrame(transfer_records)
            if parquet_available:
                transfer_df.to_parquet(output_dir / "unit_changes.parquet", index=False)
            else:
                transfer_df.to_csv(output_dir / "unit_changes.csv", index=False)
            print(f"Wrote {len(transfer_df)} records to {output_dir}/unit_changes{ext}")

    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive pipeline statistics."""
        # Count entries by source
        entries_per_source: Dict[str, int] = {}
        for entry in self.entries.values():
            entries_per_source[entry.source_id] = (
                entries_per_source.get(entry.source_id, 0) + 1
            )

        # Count soldiers by component
        soldiers_by_component: Dict[str, int] = {}
        for soldier in self.soldiers.values():
            cid = soldier.assignment.component_id
            soldiers_by_component[cid] = soldiers_by_component.get(cid, 0) + 1

        # Count entries with vocabulary
        entries_with_situational = sum(
            1 for e in self.entries.values() if e.situational_terms
        )
        entries_with_clutter = sum(
            1 for e in self.entries.values() if e.clutter_terms
        )
        entries_with_confounder = sum(
            1 for e in self.entries.values() if e.confounder_terms
        )

        return {
            "total_soldiers": len(self.soldiers),
            "total_sources": len(self.sources),
            "total_entries": len(self.entries),
            "avg_entries_per_source": (
                sum(entries_per_source.values()) / max(len(self.sources), 1)
            ),
            "soldiers_by_component": soldiers_by_component,
            "transfer_stats": self.transfer_manager.get_stats(),
            "clerk_stats": self.clerk_factory.get_clerk_stats(),
            "situation_stats": self.situation_manager.get_assignment_stats(),
            "vocabulary_coverage": {
                "entries_with_situational": entries_with_situational,
                "entries_with_clutter": entries_with_clutter,
                "entries_with_confounder": entries_with_confounder,
                "situational_rate": entries_with_situational / max(len(self.entries), 1),
                "clutter_rate": entries_with_clutter / max(len(self.entries), 1),
                "confounder_rate": entries_with_confounder / max(len(self.entries), 1),
            },
        }


def run_pipeline(
    output_dir: str = "data/synthetic",
    target_records: int = 10000,
    random_seed: int = 42,
) -> Dict[str, Any]:
    """
    Convenience function to run the full pipeline.

    Args:
        output_dir: Directory for output parquet files
        target_records: Target number of raw entries
        random_seed: Seed for reproducibility

    Returns:
        Pipeline statistics
    """
    # Default paths
    style_spec = Path("docs/components/synthetic_data_generation/synthetic_style_spec_v3.yaml")
    vocab_path = Path("config/synthetic/synthetic_vocabulary.json")
    hierarchy_path = Path("config/hierarchies/hierarchy_reference.json")

    # Initialize pipeline
    pipeline = Pipeline(
        style_spec_path=style_spec,
        vocabulary_path=vocab_path,
        hierarchy_path=hierarchy_path,
        random_seed=random_seed,
    )

    # Generate data
    raw_records, validation_records, transfer_records = pipeline.generate(
        target_records=target_records,
    )

    # Export to parquet
    pipeline.export_parquet(
        output_dir=Path(output_dir),
        raw_records=raw_records,
        validation_records=validation_records,
        transfer_records=transfer_records,
    )

    # Return stats
    return pipeline.get_stats()
