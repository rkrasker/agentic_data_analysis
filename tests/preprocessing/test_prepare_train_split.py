"""Tests for difficulty-based train/test split preparation."""

from pathlib import Path

import pandas as pd

from src.preprocessing.splits.prepare_train_split import prepare_train_test_split


def test_prepare_train_split_stratified(tmp_path: Path) -> None:
    validation_df = pd.DataFrame(
        {
            "soldier_id": ["S1", "S2", "S3", "S4", "S5", "S6"],
            "component_id": ["C1", "C1", "C1", "C2", "C2", "C2"],
            "state_id": ["A"] * 6,
            "branch": ["B"] * 6,
            "post_path": ["P"] * 6,
            "regiment": [1, 1, 2, 1, 2, 2],
        }
    )
    difficulty_df = pd.DataFrame(
        {
            "soldier_id": ["S1", "S2", "S3", "S4", "S5", "S6"],
            "gt_difficulty_tier": ["easy", "moderate", "hard", "extreme", "hard", "moderate"],
            "gt_complementarity_score": [0.1] * 6,
            "gt_collision_zone_flag": [True] * 6,
            "gt_structural_resolvability": [True] * 6,
        }
    )

    validation_path = tmp_path / "validation.parquet"
    difficulty_path = tmp_path / "difficulty.parquet"
    validation_df.to_parquet(validation_path, index=False)
    difficulty_df.to_parquet(difficulty_path, index=False)

    train_path, test_path = prepare_train_test_split(
        validation_path=validation_path,
        difficulty_path=difficulty_path,
        output_dir=tmp_path,
        train_ratio=0.5,
        random_seed=0,
    )

    train_df = pd.read_parquet(train_path)
    test_df = pd.read_parquet(test_path)

    assert "gt_difficulty_tier" in train_df.columns
    assert "gt_difficulty_tier" in test_df.columns
    assert len(train_df) + len(test_df) == len(validation_df)

    for component_id in ["C1", "C2"]:
        assert (train_df["component_id"] == component_id).any()
        assert (test_df["component_id"] == component_id).any()

    assert set(train_df["soldier_id"]).isdisjoint(set(test_df["soldier_id"]))
