"""
Module 3: Collision Sampler

Creates head-to-head soldier samples for collision pairs (Phase 3).
Samples soldiers from both sides of a collision for LLM analysis.
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

from .thresholds import ThresholdResult, TierName
from .structure import StructureResult

DEFAULT_TIER_WEIGHTS = {
    "extreme": 0.35,
    "hard": 0.35,
    "moderate": 0.20,
    "easy": 0.10,
}


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
    stratify_by_difficulty: bool = False,
    tier_weights: Optional[Dict[str, float]] = None,
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
        stratify_by_difficulty: Whether to stratify sampling by difficulty tier
        tier_weights: Optional weights for difficulty tiers

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

    soldier_tiers: Optional[Dict[str, str]] = None
    weights = tier_weights or DEFAULT_TIER_WEIGHTS
    if stratify_by_difficulty:
        if "gt_difficulty_tier" not in train.columns:
            logger.warning(
                "Difficulty stratification requested but 'gt_difficulty_tier' is missing. "
                "Falling back to random sampling."
            )
            stratify_by_difficulty = False
        else:
            tier_series = train.dropna(subset=["gt_difficulty_tier"]).drop_duplicates("soldier_id")
            soldier_tiers = (
                tier_series.set_index("soldier_id")["gt_difficulty_tier"].to_dict()
            )
            if not soldier_tiers:
                logger.warning(
                    "Difficulty stratification requested but no tier labels were found. "
                    "Falling back to random sampling."
                )
                stratify_by_difficulty = False

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

            # Filter to soldiers in colliding sub-units
            soldiers_in_collision_a = _filter_to_collision(
                all_soldiers, train, collision_levels
            )
            soldiers_in_collision_b = _filter_to_collision(
                rival_soldiers, train, collision_levels
            )

            # Log filtering results
            logger.info(
                f"Collision filter {component_id} vs {rival_id}: "
                f"{len(all_soldiers)} -> {len(soldiers_in_collision_a)} soldiers (A), "
                f"{len(rival_soldiers)} -> {len(soldiers_in_collision_b)} soldiers (B)"
            )

            # Fallback to all soldiers if filter returns empty
            if not soldiers_in_collision_a:
                logger.warning(
                    f"Collision filter returned no soldiers for {component_id}, "
                    f"falling back to all {len(all_soldiers)} soldiers"
                )
                soldiers_in_collision_a = all_soldiers
            if not soldiers_in_collision_b:
                logger.warning(
                    f"Collision filter returned no soldiers for {rival_id}, "
                    f"falling back to all {len(rival_soldiers)} soldiers"
                )
                soldiers_in_collision_b = rival_soldiers

            # Sample from filtered soldiers
            sample_a, undersampled_a = _sample_soldiers(
                soldiers_in_collision_a,
                samples_per_side,
                rng,
                soldier_tiers=soldier_tiers if stratify_by_difficulty else None,
                tier_weights=weights if stratify_by_difficulty else None,
            )
            sample_b, undersampled_b = _sample_soldiers(
                soldiers_in_collision_b,
                samples_per_side,
                rng,
                soldier_tiers=soldier_tiers if stratify_by_difficulty else None,
                tier_weights=weights if stratify_by_difficulty else None,
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
    soldier_tiers: Optional[Dict[str, str]] = None,
    tier_weights: Optional[Dict[str, float]] = None,
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

    if not soldier_tiers or not tier_weights:
        # Random sample
        indices = rng.choice(available, size=target_size, replace=False)
        sampled = [soldiers[i] for i in indices]
        return sampled, False

    soldiers_by_tier: Dict[str, List[str]] = {tier: [] for tier in tier_weights.keys()}
    unassigned: List[str] = []
    for soldier_id in soldiers:
        tier = soldier_tiers.get(soldier_id)
        if tier in soldiers_by_tier:
            soldiers_by_tier[tier].append(soldier_id)
        else:
            unassigned.append(soldier_id)

    sampled, _ = _stratified_sample(
        soldiers_by_tier=soldiers_by_tier,
        target_size=target_size,
        tier_weights=tier_weights,
        rng=rng,
    )

    if len(sampled) < target_size and unassigned:
        remaining = target_size - len(sampled)
        if len(unassigned) <= remaining:
            sampled.extend(unassigned)
        else:
            indices = rng.choice(len(unassigned), size=remaining, replace=False)
            sampled.extend([unassigned[i] for i in indices])

    return sampled, False


def _stratified_sample(
    soldiers_by_tier: Dict[str, List[str]],
    target_size: int,
    tier_weights: Dict[str, float],
    rng: np.random.RandomState,
) -> Tuple[List[str], bool]:
    """Perform stratified sampling across difficulty tiers."""
    all_soldiers = [s for soldiers in soldiers_by_tier.values() for s in soldiers]
    total_available = len(all_soldiers)

    if total_available <= target_size:
        return list(all_soldiers), True

    weights = {tier: weight for tier, weight in tier_weights.items() if weight > 0}
    if not weights:
        indices = rng.choice(total_available, size=target_size, replace=False)
        sampled = [all_soldiers[i] for i in indices]
        return sampled, False

    available_by_tier = {
        tier: len(soldiers_by_tier.get(tier, [])) for tier in weights.keys()
    }
    allocations = {tier: 0 for tier in weights.keys()}
    remaining = target_size
    active_tiers = {tier for tier, cap in available_by_tier.items() if cap > 0}

    while remaining > 0 and active_tiers:
        total_weight = sum(weights[tier] for tier in active_tiers)
        if total_weight <= 0:
            break

        raw = {
            tier: remaining * (weights[tier] / total_weight) for tier in active_tiers
        }
        base = {tier: int(raw[tier]) for tier in active_tiers}
        allocated = sum(base.values())
        leftover = remaining - allocated

        if leftover > 0:
            for tier in sorted(
                active_tiers,
                key=lambda t: (raw[t] - base[t], t),
                reverse=True,
            ):
                if leftover <= 0:
                    break
                base[tier] += 1
                leftover -= 1

        next_active = set(active_tiers)
        for tier in list(active_tiers):
            capacity = available_by_tier[tier] - allocations[tier]
            if capacity <= 0:
                next_active.discard(tier)
                continue

            take = min(base.get(tier, 0), capacity)
            allocations[tier] += take
            remaining -= take

            if allocations[tier] >= available_by_tier[tier]:
                next_active.discard(tier)

        active_tiers = next_active

    sampled: List[str] = []
    for tier, count in allocations.items():
        if count <= 0:
            continue
        pool = soldiers_by_tier.get(tier, [])
        if count >= len(pool):
            sampled.extend(pool)
        else:
            indices = rng.choice(len(pool), size=count, replace=False)
            sampled.extend([pool[i] for i in indices])

    return sampled, False


def _filter_to_collision(
    soldiers: List[str],
    train_df: pd.DataFrame,
    collision_levels: List[Tuple[str, str]],
) -> List[str]:
    """
    Filter to soldiers in colliding sub-units.

    For example, if 82nd and 101st both have regiment 3, this filters
    to only soldiers in regiment 3 so the LLM sees the actual collision.

    Args:
        soldiers: List of soldier IDs to filter
        train_df: Training data with hierarchy columns (regiment, battalion, etc.)
        collision_levels: List of (level, value) tuples where collision occurs
            e.g., [("regiment", "3")] means both components have regiment 3

    Returns:
        Filtered list of soldier IDs in colliding sub-units
    """
    if not collision_levels:
        return soldiers

    df = train_df[train_df["soldier_id"].isin(soldiers)]
    if df.empty:
        return soldiers

    # Build masks for each collision level
    masks = []
    for level, value in collision_levels:
        if level in df.columns:
            masks.append(df[level] == value)

    if not masks:
        return soldiers

    # Combine with OR - soldier is in collision if they match ANY collision level
    combined = masks[0]
    for m in masks[1:]:
        combined |= m

    return df[combined]["soldier_id"].unique().tolist()


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
