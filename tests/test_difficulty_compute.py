# -*- coding: utf-8 -*-
"""
Unit tests for soldier difficulty computation.
"""

import sys
from pathlib import Path

import pandas as pd
import pytest

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.preprocessing.difficulty.compute import (
    compute_all_soldier_difficulties,
    compute_soldier_difficulty,
)


def _make_hierarchy_reference():
    return {
        "branches": {
            "alpha_branch": {
                "depth": 4,
                "levels": ["sector", "fleet", "wing", "element"],
                "level_config": {
                    "sector": {"values": ["Alpha", "Beta"]},
                    "fleet": {"values": [1, 2]},
                    "wing": {"values": ["A", "B"]},
                    "element": {"values": [1, 2]},
                },
            },
            "beta_branch": {
                "depth": 4,
                "levels": ["sector", "crew", "facility", "operation"],
                "level_config": {
                    "sector": {"values": ["Alpha", "Beta"]},
                    "crew": {"values": ["Red", "Blue"]},
                    "facility": {"values": [1, 2]},
                    "operation": {"values": ["X", "Y"]},
                },
            },
        }
    }


def _make_structural_discriminators():
    return {
        "collision_index": {
            '(sector, "Alpha")': ["alpha_branch.sector", "beta_branch.sector"],
        },
        "branch_exclusion_rules": {
            "alpha_branch": [
                {
                    "rule_type": "term_presence",
                    "condition": "contains term 'crew'",
                    "excludes_branch": "alpha_branch",
                    "implies_branch": "beta_branch",
                    "strength": "definitive",
                },
                {
                    "rule_type": "designator_invalidity",
                    "condition": "contains designator 'Red' (only valid in beta_branch)",
                    "excludes_branch": "alpha_branch",
                    "implies_branch": "beta_branch",
                    "strength": "definitive",
                },
            ],
            "beta_branch": [
                {
                    "rule_type": "term_presence",
                    "condition": "contains term 'wing'",
                    "excludes_branch": "beta_branch",
                    "implies_branch": "alpha_branch",
                    "strength": "definitive",
                }
            ],
        },
    }


def _record(
    soldier_id: str,
    *,
    unit_digit_pairs=None,
    unit_alpha_pairs=None,
    unchar_alpha=None,
    unchar_digits=None,
    unit_terms=None,
    org_terms=None,
):
    return {
        "soldier_id": soldier_id,
        "Unit_Term_Digit_Term:Pair": unit_digit_pairs or [],
        "Unit_Term_Alpha_Term:Pair": unit_alpha_pairs or [],
        "Unchar_Alpha": unchar_alpha or [],
        "Unchar_Digits": unchar_digits or [],
        "Unit_Terms": unit_terms or [],
        "Org_Terms": org_terms or [],
    }


def test_easy_case_non_collision():
    hierarchy = _make_hierarchy_reference()
    structural = _make_structural_discriminators()
    records = pd.DataFrame(
        [_record("S1", unit_alpha_pairs=["Wing:A"])]
    )
    result = compute_soldier_difficulty("S1", records, structural, hierarchy)
    assert result.collision_position is False
    assert result.difficulty_tier == "easy"


def test_moderate_resolvable_by_term():
    hierarchy = _make_hierarchy_reference()
    structural = _make_structural_discriminators()
    records = pd.DataFrame(
        [_record("S2", unchar_alpha=["Alpha"], unit_terms=["WING"])]
    )
    result = compute_soldier_difficulty("S2", records, structural, hierarchy)
    assert result.collision_position is True
    assert result.structural_resolvability is True
    assert result.difficulty_tier == "moderate"
    assert result.candidate_branches == ["alpha_branch"]


def test_moderate_high_complementarity():
    hierarchy = _make_hierarchy_reference()
    structural = _make_structural_discriminators()
    records = pd.DataFrame(
        [
            _record(
                "S3",
                unchar_alpha=["Alpha"],
                unit_digit_pairs=["Fleet:1", "Element:2"],
                unit_alpha_pairs=["Wing:A"],
            )
        ]
    )
    result = compute_soldier_difficulty("S3", records, structural, hierarchy)
    assert result.collision_position is True
    assert result.structural_resolvability is False
    assert result.complementarity_score >= 0.7
    assert result.difficulty_tier == "moderate"


def test_hard_case():
    hierarchy = _make_hierarchy_reference()
    structural = _make_structural_discriminators()
    records = pd.DataFrame(
        [_record("S4", unchar_alpha=["Alpha"], unit_digit_pairs=["Fleet:1"])]
    )
    result = compute_soldier_difficulty("S4", records, structural, hierarchy)
    assert result.collision_position is True
    assert result.structural_resolvability is False
    assert 0.4 <= result.complementarity_score < 0.7
    assert result.difficulty_tier == "hard"


def test_extreme_case_low_complementarity():
    hierarchy = _make_hierarchy_reference()
    structural = _make_structural_discriminators()
    records = pd.DataFrame([_record("S5", unchar_alpha=["Alpha"])])
    result = compute_soldier_difficulty("S5", records, structural, hierarchy)
    assert result.collision_position is True
    assert result.complementarity_score < 0.4
    assert result.difficulty_tier == "extreme"


def test_edge_no_extractions():
    hierarchy = _make_hierarchy_reference()
    structural = _make_structural_discriminators()
    records = pd.DataFrame([_record("S6")])
    result = compute_soldier_difficulty("S6", records, structural, hierarchy)
    assert result.complementarity_score == 0.0
    assert result.difficulty_tier == "extreme"


def test_edge_multi_branch_collision_max_complementarity():
    hierarchy = _make_hierarchy_reference()
    structural = _make_structural_discriminators()
    records = pd.DataFrame(
        [_record("S7", unchar_alpha=["Alpha", "Red"])]
    )
    result = compute_soldier_difficulty("S7", records, structural, hierarchy)
    assert result.collision_position is True
    assert result.complementarity_score == pytest.approx(0.375)


def test_batch_function_groups_by_soldier():
    hierarchy = _make_hierarchy_reference()
    structural = _make_structural_discriminators()
    records = pd.DataFrame(
        [
            _record("S8", unchar_alpha=["Alpha"]),
            _record("S9", unit_alpha_pairs=["Wing:A"]),
        ]
    )
    df = compute_all_soldier_difficulties(records, structural, hierarchy)
    assert set(df["soldier_id"]) == {"S8", "S9"}
    assert df.loc[df["soldier_id"] == "S8", "difficulty_tier"].iloc[0] == "extreme"
