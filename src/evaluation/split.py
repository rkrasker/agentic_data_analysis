"""
Train/test splitting with stratification for resolver generation and evaluation.

Implements stratified splitting by a configurable subcomponent level (e.g., sector)
within each component to ensure representative samples for both training
(resolver generation) and testing (evaluation).
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import pandas as pd
import numpy as np


@dataclass
class SplitConfig:
    """Configuration for train/test split."""
    train_ratio: float = 0.75
    test_ratio: float = 0.25
    stratify_by: str = "sector"  # Column to stratify on within each component
    random_seed: int = 42
    min_test_per_component: int = 10
    min_test_per_stratum: int = 1  # At least 1 test per stratum (if stratum has >=4 total)
    min_stratum_size_for_split: int = 4  # Don't split strata smaller than this

    def __post_init__(self):
        """Validate configuration."""
        if not 0 < self.train_ratio < 1:
            raise ValueError("train_ratio must be between 0 and 1")
        if not abs(self.train_ratio + self.test_ratio - 1.0) < 0.001:
            raise ValueError("train_ratio + test_ratio must equal 1.0")


@dataclass
class TrainTestSplit:
    """Result of a train/test split."""
    component_id: str
    total: int
    train_count: int
    test_count: int
    train_ids: Set[str]
    test_ids: Set[str]
    by_stratum: Dict[str, Dict[str, int]] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)

    @property
    def train_ratio(self) -> float:
        """Actual train ratio achieved."""
        return self.train_count / self.total if self.total > 0 else 0.0

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "total": self.total,
            "train_count": self.train_count,
            "test_count": self.test_count,
            "train_ids": sorted(list(self.train_ids)),
            "test_ids": sorted(list(self.test_ids)),
            "by_stratum": self.by_stratum,
            "warnings": self.warnings,
        }


class StratifiedSplitter:
    """
    Stratified train/test splitter for validation data.

    Splits soldiers by component, stratifying on a configurable subcomponent level
    (e.g., sector) to ensure both train and test sets have representative samples
    from each stratum.

    Handles sparse components gracefully:
    - Very small components: No split, all data available for resolver/evaluation
    - Small strata: Handled with min_test_per_stratum setting
    """

    def __init__(self, config: Optional[SplitConfig] = None):
        """
        Initialize splitter.

        Args:
            config: Split configuration (uses defaults if None)
        """
        self.config = config or SplitConfig()
        self.rng = np.random.RandomState(self.config.random_seed)

    def split(
        self,
        validation_df: pd.DataFrame,
    ) -> Dict[str, TrainTestSplit]:
        """
        Split validation data into train/test sets per component.

        Args:
            validation_df: DataFrame with columns:
                - primary_id (or soldier_id): Unique soldier identifier
                - component_id: Component identifier
                - [stratify_by column]: Column to stratify on (default: sector)

        Returns:
            Dict mapping component_id -> TrainTestSplit
        """
        # Normalize column names
        df = validation_df.copy()
        if "primary_id" in df.columns:
            df = df.rename(columns={"primary_id": "soldier_id"})

        if "soldier_id" not in df.columns:
            raise ValueError("validation_df must have 'soldier_id' or 'primary_id' column")

        if "component_id" not in df.columns:
            raise ValueError("validation_df must have 'component_id' column")

        if self.config.stratify_by not in df.columns:
            raise ValueError(
                f"validation_df must have '{self.config.stratify_by}' column for stratification"
            )

        splits = {}
        for component_id, component_df in df.groupby("component_id"):
            splits[component_id] = self._split_component(component_id, component_df)

        return splits

    def _split_component(
        self,
        component_id: str,
        component_df: pd.DataFrame
    ) -> TrainTestSplit:
        """Split a single component's data."""
        total = len(component_df)
        warnings = []

        # Check if component is too small to split
        if total < self.config.min_test_per_component:
            warnings.append(
                f"Component has only {total} soldiers, below minimum "
                f"{self.config.min_test_per_component}. No split performed - "
                f"all data available for resolver/evaluation."
            )
            return TrainTestSplit(
                component_id=component_id,
                total=total,
                train_count=total,
                test_count=0,
                train_ids=set(component_df["soldier_id"]),
                test_ids=set(),
                warnings=warnings,
            )

        # Stratified split by regiment (or other stratum)
        train_ids = set()
        test_ids = set()
        by_stratum = {}

        strata = component_df.groupby(self.config.stratify_by)
        for stratum_value, stratum_df in strata:
            stratum_size = len(stratum_df)
            stratum_ids = stratum_df["soldier_id"].values

            # Shuffle IDs for this stratum
            shuffled = self.rng.permutation(stratum_ids)

            # Determine split for this stratum
            if stratum_size < self.config.min_stratum_size_for_split:
                # Too small to split - put all in training
                train_ids.update(shuffled)
                by_stratum[str(stratum_value)] = {"train": stratum_size, "test": 0}
                warnings.append(
                    f"Stratum {self.config.stratify_by}={stratum_value} has only "
                    f"{stratum_size} soldiers, below split threshold. All in training."
                )
            else:
                # Compute split sizes
                test_size = max(
                    self.config.min_test_per_stratum,
                    int(stratum_size * self.config.test_ratio)
                )
                test_size = min(test_size, stratum_size - 1)  # Leave at least 1 for train
                train_size = stratum_size - test_size

                # Split
                test_ids.update(shuffled[:test_size])
                train_ids.update(shuffled[test_size:])

                by_stratum[str(stratum_value)] = {"train": train_size, "test": test_size}

                # Check if split is adequate
                if test_size < self.config.min_test_per_stratum:
                    warnings.append(
                        f"Stratum {self.config.stratify_by}={stratum_value} has "
                        f"only {test_size} test samples (marginal)."
                    )

        return TrainTestSplit(
            component_id=component_id,
            total=total,
            train_count=len(train_ids),
            test_count=len(test_ids),
            train_ids=train_ids,
            test_ids=test_ids,
            by_stratum=by_stratum,
            warnings=warnings,
        )

    def save_split(
        self,
        splits: Dict[str, TrainTestSplit],
        output_path: Path,
        validation_source: str,
    ):
        """
        Save split metadata to JSON.

        Args:
            splits: Dict of component splits
            output_path: Path to output JSON file
            validation_source: Path to validation.parquet used for split
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Collect exclusions (components not split)
        exclusions = []
        for component_id, split in splits.items():
            if split.test_count == 0:
                exclusions.append({
                    "component": component_id,
                    "count": split.total,
                    "reason": "below minimum threshold"
                })

        output = {
            "meta": {
                "generated_utc": datetime.utcnow().isoformat() + "Z",
                "validation_source": str(validation_source),
                "split_ratio": {
                    "train": self.config.train_ratio,
                    "test": self.config.test_ratio,
                },
                "stratify_by": self.config.stratify_by,
                "random_seed": self.config.random_seed,
            },
            "splits": {
                component_id: split.to_dict()
                for component_id, split in splits.items()
            },
            "exclusions": exclusions,
        }

        with open(output_path, "w") as f:
            json.dump(output, f, indent=2)

        print(f"Split saved to {output_path}")
        print(f"Total components: {len(splits)}")
        print(f"Components with splits: {len(splits) - len(exclusions)}")
        print(f"Components excluded (too small): {len(exclusions)}")

    @staticmethod
    def load_split(split_path: Path) -> Dict[str, TrainTestSplit]:
        """
        Load split metadata from JSON.

        Args:
            split_path: Path to split JSON file

        Returns:
            Dict mapping component_id -> TrainTestSplit
        """
        with open(split_path) as f:
            data = json.load(f)

        splits = {}
        for component_id, split_data in data["splits"].items():
            splits[component_id] = TrainTestSplit(
                component_id=component_id,
                total=split_data["total"],
                train_count=split_data["train_count"],
                test_count=split_data["test_count"],
                train_ids=set(split_data["train_ids"]),
                test_ids=set(split_data["test_ids"]),
                by_stratum=split_data.get("by_stratum", {}),
                warnings=split_data.get("warnings", []),
            )

        return splits

    def get_train_df(
        self,
        validation_df: pd.DataFrame,
        splits: Dict[str, TrainTestSplit],
    ) -> pd.DataFrame:
        """
        Get training subset from validation dataframe.

        Args:
            validation_df: Full validation dataframe
            splits: Train/test splits

        Returns:
            DataFrame with only training soldiers
        """
        df = validation_df.copy()
        if "primary_id" in df.columns:
            df = df.rename(columns={"primary_id": "soldier_id"})

        train_ids = set()
        for split in splits.values():
            train_ids.update(split.train_ids)

        return df[df["soldier_id"].isin(train_ids)].copy()

    def get_test_df(
        self,
        validation_df: pd.DataFrame,
        splits: Dict[str, TrainTestSplit],
    ) -> pd.DataFrame:
        """
        Get test subset from validation dataframe.

        Args:
            validation_df: Full validation dataframe
            splits: Train/test splits

        Returns:
            DataFrame with only test soldiers
        """
        df = validation_df.copy()
        if "primary_id" in df.columns:
            df = df.rename(columns={"primary_id": "soldier_id"})

        test_ids = set()
        for split in splits.values():
            test_ids.update(split.test_ids)

        return df[df["soldier_id"].isin(test_ids)].copy()
