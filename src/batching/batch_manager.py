"""
Batch manager for grouping soldiers by component.

Creates batches of soldiers for consolidation, grouping by likely component
to provide focused context for LLM processing.
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set
import pandas as pd

from ..strategies import SoldierBatch, SoldierRecords


@dataclass
class BatchConfig:
    """Configuration for batching."""
    max_soldiers_per_batch: int = 50
    max_records_per_batch: int = 500
    group_by_component: bool = True


class BatchManager:
    """
    Manager for creating component-focused batches.

    Groups soldiers by their likely component (from routing/preprocessing signals)
    to provide focused context for LLM consolidation.
    """

    def __init__(self, config: Optional[BatchConfig] = None):
        """
        Initialize batch manager.

        Args:
            config: Batch configuration (uses defaults if None)
        """
        self.config = config or BatchConfig()

    def create_batches(
        self,
        canonical_df: pd.DataFrame,
        hierarchy_path: Path,
        component_mapping: Optional[pd.DataFrame] = None,
        soldier_filter: Optional[Set[str]] = None,
    ) -> List[SoldierBatch]:
        """
        Create batches from canonical data.

        Args:
            canonical_df: Canonical dataframe with extraction signals
            hierarchy_path: Path to hierarchy_reference.json
            component_mapping: Optional soldier->component mapping
                (if None, creates single "unknown" batch)
            soldier_filter: Optional set of soldier_ids to include
                (useful for test set filtering)

        Returns:
            List of SoldierBatch objects
        """
        # Filter soldiers if requested
        df = canonical_df.copy()
        if soldier_filter is not None:
            df = df[df["soldier_id"].isin(soldier_filter)]

        if df.empty:
            return []

        # Load hierarchy
        with open(hierarchy_path) as f:
            hierarchy = json.load(f)

        # Group by component
        if self.config.group_by_component and component_mapping is not None:
            return self._create_component_batches(df, hierarchy, component_mapping)
        else:
            return self._create_single_batch(df, hierarchy)

    def _create_component_batches(
        self,
        canonical_df: pd.DataFrame,
        hierarchy: Dict,
        component_mapping: pd.DataFrame,
    ) -> List[SoldierBatch]:
        """Create batches grouped by component."""
        batches = []

        # Create lookup for soldier -> component
        component_lookup = component_mapping.set_index("soldier_id")["likely_component"].to_dict()

        # Group soldiers by component
        soldier_groups: Dict[str, List[str]] = {}
        for soldier_id in canonical_df["soldier_id"].unique():
            component = component_lookup.get(soldier_id, "unknown")
            if component not in soldier_groups:
                soldier_groups[component] = []
            soldier_groups[component].append(soldier_id)

        # Create batches for each component
        for component_id, soldier_ids in soldier_groups.items():
            component_hierarchy = None
            if component_id != "unknown" and component_id in hierarchy.get("components", {}):
                component_hierarchy = hierarchy["components"][component_id]

            # Split into multiple batches if needed
            component_batches = self._split_into_batches(
                canonical_df,
                soldier_ids,
                component_id,
                component_hierarchy,
            )
            batches.extend(component_batches)

        return batches

    def _create_single_batch(
        self,
        canonical_df: pd.DataFrame,
        hierarchy: Dict,
    ) -> List[SoldierBatch]:
        """Create batches without component grouping."""
        soldier_ids = canonical_df["soldier_id"].unique().tolist()

        return self._split_into_batches(
            canonical_df,
            soldier_ids,
            component_hint="unknown",
            component_hierarchy=None,
        )

    def _split_into_batches(
        self,
        canonical_df: pd.DataFrame,
        soldier_ids: List[str],
        component_hint: str,
        component_hierarchy: Optional[Dict],
    ) -> List[SoldierBatch]:
        """
        Split soldiers into multiple batches based on size constraints.

        Args:
            canonical_df: Canonical dataframe
            soldier_ids: List of soldier IDs to batch
            component_hint: Likely component for this batch
            component_hierarchy: Component hierarchy (if known)

        Returns:
            List of batches
        """
        batches = []
        current_soldiers = []
        current_records = 0

        for soldier_id in soldier_ids:
            soldier_df = canonical_df[canonical_df["soldier_id"] == soldier_id]
            soldier_record_count = len(soldier_df)

            # Check if adding this soldier would exceed limits
            would_exceed_soldiers = len(current_soldiers) >= self.config.max_soldiers_per_batch
            would_exceed_records = (
                current_records + soldier_record_count > self.config.max_records_per_batch
            )

            if current_soldiers and (would_exceed_soldiers or would_exceed_records):
                # Create batch with current soldiers
                batch = self._create_batch(
                    canonical_df,
                    current_soldiers,
                    component_hint,
                    component_hierarchy,
                    batch_idx=len(batches),
                )
                batches.append(batch)

                # Start new batch
                current_soldiers = []
                current_records = 0

            # Add soldier to current batch
            current_soldiers.append(soldier_id)
            current_records += soldier_record_count

        # Create final batch if any soldiers remain
        if current_soldiers:
            batch = self._create_batch(
                canonical_df,
                current_soldiers,
                component_hint,
                component_hierarchy,
                batch_idx=len(batches),
            )
            batches.append(batch)

        return batches

    def _create_batch(
        self,
        canonical_df: pd.DataFrame,
        soldier_ids: List[str],
        component_hint: str,
        component_hierarchy: Optional[Dict],
        batch_idx: int,
    ) -> SoldierBatch:
        """Create a single batch from soldier IDs."""
        soldiers = []
        for soldier_id in soldier_ids:
            soldier_df = canonical_df[canonical_df["soldier_id"] == soldier_id].copy()
            soldiers.append(SoldierRecords(
                soldier_id=soldier_id,
                records=soldier_df,
            ))

        batch_id = f"{component_hint}_batch_{batch_idx:03d}"

        return SoldierBatch(
            batch_id=batch_id,
            component_hint=component_hint if component_hint != "unknown" else None,
            soldiers=soldiers,
            hierarchy=component_hierarchy,
        )


def create_batches(
    canonical_df: pd.DataFrame,
    hierarchy_path: Path,
    component_mapping: Optional[pd.DataFrame] = None,
    soldier_filter: Optional[Set[str]] = None,
    config: Optional[BatchConfig] = None,
) -> List[SoldierBatch]:
    """
    Convenience function to create batches.

    Args:
        canonical_df: Canonical dataframe with extraction signals
        hierarchy_path: Path to hierarchy_reference.json
        component_mapping: Optional soldier->component mapping
        soldier_filter: Optional set of soldier_ids to include
        config: Batch configuration

    Returns:
        List of SoldierBatch objects
    """
    manager = BatchManager(config)
    return manager.create_batches(
        canonical_df,
        hierarchy_path,
        component_mapping,
        soldier_filter,
    )
