"""Tests for difficulty-based sampling."""

from collections import Counter

import numpy as np

from src.strategies.resolver.generator import sampling


def test_stratified_sample_redistributes_quota() -> None:
    soldiers_by_tier = {
        "extreme": ["E1"],
        "hard": ["H1", "H2", "H3", "H4", "H5"],
    }
    tier_weights = {"extreme": 0.5, "hard": 0.5}

    rng = np.random.RandomState(0)
    sampled, undersampled = sampling._stratified_sample(
        soldiers_by_tier=soldiers_by_tier,
        target_size=4,
        tier_weights=tier_weights,
        rng=rng,
    )

    assert not undersampled
    assert len(sampled) == 4

    tier_by_soldier = {soldier: "extreme" for soldier in soldiers_by_tier["extreme"]}
    tier_by_soldier.update({soldier: "hard" for soldier in soldiers_by_tier["hard"]})
    counts = Counter(tier_by_soldier[soldier] for soldier in sampled)

    assert counts["extreme"] == 1
    assert counts["hard"] == 3


def test_sample_soldiers_fills_from_unassigned() -> None:
    soldiers = ["S1", "S2", "S3", "S4"]
    soldier_tiers = {"S1": "extreme"}
    tier_weights = {"extreme": 1.0}

    rng = np.random.RandomState(1)
    sampled, undersampled = sampling._sample_soldiers(
        soldiers=soldiers,
        target_size=3,
        rng=rng,
        soldier_tiers=soldier_tiers,
        tier_weights=tier_weights,
    )

    assert not undersampled
    assert len(sampled) == 3
    assert "S1" in sampled
