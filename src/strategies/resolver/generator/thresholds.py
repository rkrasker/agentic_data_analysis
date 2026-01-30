"""
Module 1: Threshold Calculator

Computes relative threshold tiers from validation data distribution.
Tiers are based on percentiles (p25, median, p75) rather than absolute counts.
"""

from dataclasses import dataclass
from typing import Dict, Literal

import pandas as pd


TierName = Literal["well_represented", "adequately_represented", "under_represented", "sparse"]


@dataclass
class ThresholdResult:
    """Result of threshold computation."""
    thresholds: Dict[str, float]  # p25, median, p75
    component_tiers: Dict[str, TierName]  # component_id -> tier
    component_counts: Dict[str, int]  # component_id -> count

    def get_tier(self, component_id: str) -> TierName:
        """Get tier for a component."""
        return self.component_tiers.get(component_id, "sparse")

    def get_count(self, component_id: str) -> int:
        """Get soldier count for a component."""
        return self.component_counts.get(component_id, 0)

    def pct_of_median(self, component_id: str) -> float:
        """Get component count as percentage of median."""
        count = self.get_count(component_id)
        median = self.thresholds.get("median", 1)
        if median == 0:
            return 0.0
        return (count / median) * 100

    def summary(self) -> Dict[str, int]:
        """Count of components per tier."""
        counts = {"well_represented": 0, "adequately_represented": 0, "under_represented": 0, "sparse": 0}
        for tier in self.component_tiers.values():
            counts[tier] += 1
        return counts


def compute_thresholds(validation_df: pd.DataFrame) -> ThresholdResult:
    """
    Compute tier thresholds from validation distribution.

    Tiers are assigned based on percentiles:
    - well_represented: count >= p75
    - adequately_represented: count >= median (p50)
    - under_represented: count >= p25
    - sparse: count < p25

    Args:
        validation_df: DataFrame with columns including:
            - primary_id or soldier_id: Unique soldier identifier
            - component_id: Component identifier

    Returns:
        ThresholdResult with thresholds and tier assignments
    """
    df = validation_df.copy()

    # Normalize column names
    if "primary_id" in df.columns:
        df = df.rename(columns={"primary_id": "soldier_id"})

    if "soldier_id" not in df.columns:
        raise ValueError("validation_df must have 'soldier_id' or 'primary_id' column")

    if "component_id" not in df.columns:
        raise ValueError("validation_df must have 'component_id' column")

    # Count soldiers per component
    component_counts = df.groupby("component_id")["soldier_id"].nunique()

    # Compute percentiles
    p25 = component_counts.quantile(0.25)
    median = component_counts.quantile(0.50)
    p75 = component_counts.quantile(0.75)

    thresholds = {
        "p25": float(p25),
        "median": float(median),
        "p75": float(p75),
    }

    # Assign tiers
    component_tiers: Dict[str, TierName] = {}
    for component_id, count in component_counts.items():
        pct_of_median = (count / median * 100) if median > 0 else 0

        if count >= p75:
            component_tiers[component_id] = "well_represented"
        elif count >= median:
            component_tiers[component_id] = "adequately_represented"
        elif count >= p25 or pct_of_median >= 75:
            component_tiers[component_id] = "under_represented"
        else:
            component_tiers[component_id] = "sparse"

    return ThresholdResult(
        thresholds=thresholds,
        component_tiers=component_tiers,
        component_counts=dict(component_counts),
    )


def tier_allows_patterns(tier: TierName) -> bool:
    """Check if tier allows pattern generation."""
    return tier in ("well_represented", "adequately_represented", "under_represented")


def tier_allows_vocabulary(tier: TierName) -> bool:
    """Check if tier allows vocabulary generation."""
    return tier in ("well_represented", "adequately_represented")


def tier_allows_value_exclusions(tier: TierName) -> bool:
    """Deprecated: value-based exclusion mining removed (ADR-009)."""
    return False


def get_generation_mode(tier: TierName) -> str:
    """Get generation mode based on tier."""
    if tier == "well_represented":
        return "full"
    elif tier == "adequately_represented":
        return "full"
    elif tier == "under_represented":
        return "limited"
    else:
        return "hierarchy_only"
