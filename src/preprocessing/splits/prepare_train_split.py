"""Prepare train/test splits with difficulty labels joined."""

import argparse
import logging
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def prepare_train_test_split(
    validation_path: Path,
    difficulty_path: Path,
    output_dir: Path,
    train_ratio: float = 0.7,
    random_seed: int = 42,
    component_id_col: str = "component_id",
) -> Tuple[Path, Path]:
    """
    Create train/test splits with difficulty labels joined.

    Steps:
    1. Load validation.parquet and gt_difficulty.parquet
    2. Join on soldier_id (left join from validation to difficulty)
    3. Create stratified train/test split (stratify by component_id_col)
    4. Write train_with_difficulty.parquet and test_with_difficulty.parquet

    Args:
        validation_path: Path to validation.parquet
        difficulty_path: Path to gt_difficulty.parquet
        output_dir: Output directory for train/test parquet files
        train_ratio: Fraction of data for training (default: 0.7)
        random_seed: Random seed for reproducibility (default: 42)
        component_id_col: Column to use as component identifier. Use 'branch'
            for Terraform Combine synthetic data, 'component_id' for WWII data.

    Returns:
        Tuple of (train_path, test_path)
    """
    if not 0 < train_ratio < 1:
        raise ValueError("train_ratio must be between 0 and 1")

    validation_df = pd.read_parquet(validation_path)
    difficulty_df = pd.read_parquet(difficulty_path)

    validation_df = _normalize_ids(validation_df)
    difficulty_df = _normalize_ids(difficulty_df)

    if "soldier_id" not in validation_df.columns:
        raise ValueError("validation data must include soldier_id")
    if component_id_col not in validation_df.columns:
        raise ValueError(f"validation data must include '{component_id_col}' column")

    # Normalize to component_id for internal processing
    if component_id_col != "component_id":
        validation_df = validation_df.rename(columns={component_id_col: "component_id"})

    difficulty_df = difficulty_df.drop_duplicates(subset=["soldier_id"])
    merged = validation_df.merge(difficulty_df, on="soldier_id", how="left")

    rng = np.random.RandomState(random_seed)
    train_ids, test_ids = _split_ids_by_component(merged, train_ratio, rng)

    train_df = merged[merged["soldier_id"].isin(train_ids)].copy()
    test_df = merged[merged["soldier_id"].isin(test_ids)].copy()

    output_dir.mkdir(parents=True, exist_ok=True)
    train_path = output_dir / "train_with_difficulty.parquet"
    test_path = output_dir / "test_with_difficulty.parquet"

    train_df.to_parquet(train_path, index=False)
    test_df.to_parquet(test_path, index=False)

    logger.info(
        "Prepared train/test splits: %s (%d rows), %s (%d rows)",
        train_path,
        len(train_df),
        test_path,
        len(test_df),
    )

    return train_path, test_path


def _normalize_ids(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize primary_id to soldier_id when needed."""
    normalized = df.copy()
    if "primary_id" in normalized.columns and "soldier_id" not in normalized.columns:
        normalized = normalized.rename(columns={"primary_id": "soldier_id"})
    return normalized


def _split_ids_by_component(
    merged: pd.DataFrame,
    train_ratio: float,
    rng: np.random.RandomState,
) -> Tuple[List[str], List[str]]:
    """Split soldier IDs by component_id to keep both splits represented."""
    train_ids: List[str] = []
    test_ids: List[str] = []

    for component_id, group in merged.groupby("component_id"):
        soldiers = group["soldier_id"].dropna().unique().tolist()
        if not soldiers:
            continue

        rng.shuffle(soldiers)
        total = len(soldiers)

        if total < 2:
            logger.warning(
                "Component %s has only %d soldier(s); placing all in train split",
                component_id,
                total,
            )
            train_ids.extend(soldiers)
            continue

        test_size = int(round(total * (1 - train_ratio)))
        test_size = max(1, min(test_size, total - 1))

        test_ids.extend(soldiers[:test_size])
        train_ids.extend(soldiers[test_size:])

    return train_ids, test_ids


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prepare train/test splits with difficulty labels joined."
    )
    parser.add_argument(
        "--validation",
        type=Path,
        required=True,
        help="Path to validation.parquet",
    )
    parser.add_argument(
        "--difficulty",
        type=Path,
        required=True,
        help="Path to gt_difficulty.parquet",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Output directory for train/test parquet files",
    )
    parser.add_argument(
        "--train-ratio",
        type=float,
        default=0.7,
        help="Train split ratio (default: 0.7)",
    )
    parser.add_argument(
        "--random-seed",
        type=int,
        default=42,
        help="Random seed (default: 42)",
    )
    parser.add_argument(
        "--component-id-col",
        type=str,
        default="component_id",
        help="Column to use as component identifier (default: component_id, use 'branch' for Terraform Combine)",
    )
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    args = _parse_args()
    prepare_train_test_split(
        validation_path=args.validation,
        difficulty_path=args.difficulty,
        output_dir=args.output_dir,
        train_ratio=args.train_ratio,
        random_seed=args.random_seed,
        component_id_col=args.component_id_col,
    )


if __name__ == "__main__":
    main()
