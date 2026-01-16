"""
Module 3: Collision Sampler

Creates head-to-head soldier samples for collision pairs (Phase 3).
Samples soldiers from both sides of a collision for LLM analysis.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Set, Tuple, Optional

import numpy as np
import pandas as pd

from .thresholds import ThresholdResult, TierName
from .structure import StructureResult


@dataclass
class CollisionSample:
    """Sample of soldiers from two colliding components."""
    component_a: str
    component_b: str

    # Soldier IDs
    soldiers_a: List[str] = field(default_factory=list)
    soldiers_b: List[str] = field(default_factory=list)

    # Raw text records for each side
    records_a: Optional[pd.DataFrame] = None
    records_b: Optional[pd.DataFrame] = None

    # Undersampling flags
    undersampled_a: bool = False
    undersampled_b: bool = False

    # Collision context
    collision_levels: List[Tuple[str, str]] = field(default_factory=list)
    # List of (level, value) where these components collide

    @property
    def total_soldiers(self) -> int:
        """Total soldiers in sample."""
        return len(self.soldiers_a) + len(self.soldiers_b)

    @property
    def is_balanced(self) -> bool:
        """Check if sample is roughly balanced."""
        if not self.soldiers_a or not self.soldiers_b:
            return False
        ratio = len(self.soldiers_a) / len(self.soldiers_b)
        return 0.5 <= ratio <= 2.0

    def get_texts_a(self) -> List[str]:
        """Get all raw texts for component A."""
        if self.records_a is None or self.records_a.empty:
            return []
        return self.records_a["raw_text"].tolist()

    def get_texts_b(self) -> List[str]:
        """Get all raw texts for component B."""
        if self.records_b is None or self.records_b.empty:
            return []
        return self.records_b["raw_text"].tolist()

    def to_dict(self) -> Dict:
        """Convert to dictionary (without DataFrames)."""
        return {
            "component_a": self.component_a,
            "component_b": self.component_b,
            "soldiers_a": self.soldiers_a,
            "soldiers_b": self.soldiers_b,
            "count_a": len(self.soldiers_a),
            "count_b": len(self.soldiers_b),
            "undersampled_a": self.undersampled_a,
            "undersampled_b": self.undersampled_b,
            "collision_levels": self.collision_levels,
        }


@dataclass
class ComponentSamples:
    """All collision samples for a single component."""
    component_id: str
    tier: TierName
    rival_samples: Dict[str, CollisionSample] = field(default_factory=dict)
    # rival_component_id -> CollisionSample

    # All soldiers available for this component (for vocabulary discovery)
    all_soldiers: List[str] = field(default_factory=list)
    all_records: Optional[pd.DataFrame] = None

    @property
    def rival_count(self) -> int:
        """Number of rivals with samples."""
        return len(self.rival_samples)

    def get_rival_tiers(self, thresholds: ThresholdResult) -> Dict[str, TierName]:
        """Get tier for each rival."""
        return {
            rival: thresholds.get_tier(rival)
            for rival in self.rival_samples.keys()
        }


def sample_collisions(
    train_df: pd.DataFrame,
    raw_df: pd.DataFrame,
    structure_result: StructureResult,
    thresholds: ThresholdResult,
    samples_per_side: int = 20,
    random_seed: int = 42,
) -> Dict[str, ComponentSamples]:
    """
    Sample soldiers for collision analysis.

    For each component, creates samples against each rival component
    that shares at least one designator collision.

    Args:
        train_df: Training split of validation.parquet (has component_id)
        raw_df: Raw text records (joined via soldier_id)
        structure_result: Structure extraction result with collision info
        thresholds: Tier thresholds for undersampling detection
        samples_per_side: Target number of soldiers per side
        random_seed: Random seed for reproducibility

    Returns:
        Dict mapping component_id -> ComponentSamples
    """
    rng = np.random.RandomState(random_seed)

    # Normalize column names
    train = train_df.copy()
    raw = raw_df.copy()

    if "primary_id" in train.columns:
        train = train.rename(columns={"primary_id": "soldier_id"})
    if "primary_id" in raw.columns:
        raw = raw.rename(columns={"primary_id": "soldier_id"})

    # Group train data by component
    component_soldiers: Dict[str, List[str]] = {}
    for component_id, group in train.groupby("component_id"):
        component_soldiers[component_id] = group["soldier_id"].unique().tolist()

    # Get all collision pairs
    all_pairs = structure_result.list_all_collision_pairs()

    # Build samples for each component
    result: Dict[str, ComponentSamples] = {}

    for component_id in component_soldiers.keys():
        tier = thresholds.get_tier(component_id)
        all_soldiers = component_soldiers[component_id]

        # Get all records for this component
        all_records = raw[raw["soldier_id"].isin(all_soldiers)].copy()

        component_samples = ComponentSamples(
            component_id=component_id,
            tier=tier,
            all_soldiers=all_soldiers,
            all_records=all_records,
        )

        # Find rivals for this component
        rivals = structure_result.get_rivals(component_id)

        for rival_id in rivals:
            if rival_id not in component_soldiers:
                continue  # Rival not in training data

            rival_soldiers = component_soldiers[rival_id]
            collision_levels = structure_result.get_collision_levels(component_id, rival_id)

            # Sample from both sides
            sample_a, undersampled_a = _sample_soldiers(
                all_soldiers, samples_per_side, rng
            )
            sample_b, undersampled_b = _sample_soldiers(
                rival_soldiers, samples_per_side, rng
            )

            # Get raw records for samples
            records_a = raw[raw["soldier_id"].isin(sample_a)].copy()
            records_b = raw[raw["soldier_id"].isin(sample_b)].copy()

            collision_sample = CollisionSample(
                component_a=component_id,
                component_b=rival_id,
                soldiers_a=sample_a,
                soldiers_b=sample_b,
                records_a=records_a,
                records_b=records_b,
                undersampled_a=undersampled_a,
                undersampled_b=undersampled_b,
                collision_levels=collision_levels,
            )

            component_samples.rival_samples[rival_id] = collision_sample

        result[component_id] = component_samples

    return result


def _sample_soldiers(
    soldiers: List[str],
    target_size: int,
    rng: np.random.RandomState,
) -> Tuple[List[str], bool]:
    """
    Sample soldiers, detecting undersampling.

    Args:
        soldiers: Available soldiers
        target_size: Target sample size
        rng: Random state

    Returns:
        Tuple of (sampled_soldiers, is_undersampled)
    """
    available = len(soldiers)

    if available <= target_size:
        # Use all available - undersampled
        return list(soldiers), True

    # Random sample
    indices = rng.choice(available, size=target_size, replace=False)
    sampled = [soldiers[i] for i in indices]
    return sampled, False


def get_samples_for_component(
    component_id: str,
    all_samples: Dict[str, ComponentSamples],
) -> ComponentSamples:
    """Get samples for a specific component."""
    if component_id not in all_samples:
        raise ValueError(f"No samples found for component: {component_id}")
    return all_samples[component_id]


def sample_for_vocabulary(
    component_id: str,
    train_df: pd.DataFrame,
    raw_df: pd.DataFrame,
    max_soldiers: int = 50,
    max_records_per_soldier: int = 5,
    random_seed: int = 42,
) -> pd.DataFrame:
    """
    Sample records for vocabulary discovery.

    Gets a representative sample of raw text records for a component,
    suitable for vocabulary analysis.

    Args:
        component_id: Target component
        train_df: Training split with component assignments
        raw_df: Raw text records
        max_soldiers: Maximum soldiers to sample
        max_records_per_soldier: Max records per soldier
        random_seed: Random seed

    Returns:
        DataFrame with sampled raw text records
    """
    rng = np.random.RandomState(random_seed)

    # Normalize
    train = train_df.copy()
    raw = raw_df.copy()

    if "primary_id" in train.columns:
        train = train.rename(columns={"primary_id": "soldier_id"})
    if "primary_id" in raw.columns:
        raw = raw.rename(columns={"primary_id": "soldier_id"})

    # Get soldiers for this component
    component_soldiers = train[train["component_id"] == component_id]["soldier_id"].unique()

    # Sample soldiers
    if len(component_soldiers) > max_soldiers:
        indices = rng.choice(len(component_soldiers), size=max_soldiers, replace=False)
        sampled_soldiers = [component_soldiers[i] for i in indices]
    else:
        sampled_soldiers = list(component_soldiers)

    # Get records for sampled soldiers
    records = raw[raw["soldier_id"].isin(sampled_soldiers)].copy()

    # Limit records per soldier
    if max_records_per_soldier:
        limited_records = []
        for soldier_id, group in records.groupby("soldier_id"):
            if len(group) > max_records_per_soldier:
                indices = rng.choice(len(group), size=max_records_per_soldier, replace=False)
                limited_records.append(group.iloc[indices])
            else:
                limited_records.append(group)
        if limited_records:
            records = pd.concat(limited_records, ignore_index=True)

    return records
