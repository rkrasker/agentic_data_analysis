# -*- coding: utf-8 -*-
"""
Compute ground-truth difficulty metrics from validation labels and raw records.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple, Set

import json

import pandas as pd


@dataclass
class GroundTruthDifficultyConfig:
    hierarchy_path: Path


SEVERITY_ORDER = {
    "none": 0,
    "low": 1,
    "medium": 2,
    "high": 3,
    "cross_branch": 4,
}


def load_hierarchy_reference(path: Path) -> Dict[str, Any]:
    """Load hierarchy_reference.json."""
    if not path.exists():
        raise FileNotFoundError(f"hierarchy_reference.json not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def compute_ground_truth_difficulty(
    validation_df: pd.DataFrame,
    raw_df: pd.DataFrame,
    hierarchy_reference: Dict[str, Any],
    *,
    synthetic_records_df: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
    """
    Compute gt_* difficulty metrics from validation labels and raw records.

    Returns a DataFrame with one row per validation state, with soldier-level
    metrics repeated for each state row.
    """
    required_validation_cols = {"soldier_id", "state_id", "branch"}
    missing = required_validation_cols - set(validation_df.columns)
    if missing:
        raise ValueError(f"validation_df missing required columns: {sorted(missing)}")

    records_df = _merge_record_metadata(raw_df, synthetic_records_df)
    hierarchy = hierarchy_reference.get("branches", {})
    collision_index = hierarchy_reference.get("collision_index", {})
    structural_signals = hierarchy_reference.get("structural_signals", {})

    branch_levels = {
        branch_id: list(cfg.get("levels", []))
        for branch_id, cfg in hierarchy.items()
    }

    branch_unique_terms = structural_signals.get("branch_unique_terms", {})

    state_rows: List[Dict[str, Any]] = []
    state_info_by_soldier: Dict[str, List[Dict[str, Any]]] = {}

    for _, row in validation_df.iterrows():
        soldier_id = str(row["soldier_id"])
        state_id = str(row["state_id"])
        branch = str(row["branch"]) if row["branch"] is not None else ""
        post_levels = _extract_post_levels(row, branch_levels.get(branch, []))
        severity = _get_collision_severity(branch, post_levels, collision_index)
        collision_flag = severity != "none"

        state_info = {
            "soldier_id": soldier_id,
            "state_id": state_id,
            "branch": branch,
            "post_levels": post_levels,
            "gt_collision_zone_flag": collision_flag,
            "gt_collision_severity": severity,
        }
        state_rows.append(state_info)
        state_info_by_soldier.setdefault(soldier_id, []).append(state_info)

    soldier_rows: List[Dict[str, Any]] = []
    for soldier_id, states in state_info_by_soldier.items():
        soldier_records = records_df[records_df["soldier_id"] == soldier_id]
        any_complete = _any_complete_record(soldier_records)
        collision_zone, max_severity = _aggregate_collision(states)
        complementarity_score = _compute_complementarity(
            soldier_records,
            states,
            branch_levels,
        )
        structural_resolvability = _compute_structural_resolvability(
            soldier_records,
            states,
            branch_unique_terms,
        )
        difficulty_tier = _assign_tier(
            any_complete=any_complete,
            collision_zone=collision_zone,
            collision_severity=max_severity,
            complementarity_score=complementarity_score,
            structural_resolvability=structural_resolvability,
        )
        soldier_rows.append({
            "soldier_id": soldier_id,
            "gt_complementarity_score": complementarity_score,
            "gt_structural_resolvability": structural_resolvability,
            "gt_difficulty_tier": difficulty_tier,
        })

    state_df = pd.DataFrame(state_rows)
    soldier_df = pd.DataFrame(soldier_rows)
    return state_df.merge(soldier_df, on="soldier_id", how="left")


def compute_ground_truth_difficulty_from_paths(
    validation_path: Path,
    raw_path: Path,
    *,
    hierarchy_path: Path,
    synthetic_records_path: Optional[Path] = None,
) -> pd.DataFrame:
    """Convenience wrapper to load dataframes and compute gt_difficulty."""
    validation_df = pd.read_parquet(validation_path)
    raw_df = pd.read_parquet(raw_path)
    synthetic_records_df = None
    if synthetic_records_path and synthetic_records_path.exists():
        synthetic_records_df = pd.read_parquet(synthetic_records_path)
    hierarchy_reference = load_hierarchy_reference(hierarchy_path)
    return compute_ground_truth_difficulty(
        validation_df,
        raw_df,
        hierarchy_reference,
        synthetic_records_df=synthetic_records_df,
    )


def _merge_record_metadata(
    raw_df: pd.DataFrame,
    synthetic_records_df: Optional[pd.DataFrame],
) -> pd.DataFrame:
    if synthetic_records_df is None:
        return raw_df.copy()

    join_keys = [
        col for col in ["source_id", "soldier_id"]
        if col in raw_df.columns and col in synthetic_records_df.columns
    ]
    if not join_keys:
        return raw_df.copy()

    return raw_df.merge(
        synthetic_records_df,
        on=join_keys,
        how="left",
        suffixes=("", "_synthetic"),
    )


def _extract_post_levels(row: pd.Series, level_names: Sequence[str]) -> Dict[str, Any]:
    post_levels: Dict[str, Any] = {}
    for level in level_names:
        if level in row and pd.notna(row[level]):
            post_levels[level] = row[level]
    return post_levels


def _get_collision_severity(
    branch: str,
    post_levels: Dict[str, Any],
    collision_index: Dict[str, Dict[str, List[str]]],
) -> str:
    if not post_levels:
        return "none"

    max_collisions = 0
    cross_branch = False

    for designator in post_levels.values():
        matches = _get_collisions_for_designator(str(designator), collision_index)
        if not matches:
            continue
        max_collisions = max(max_collisions, len(matches))
        if _has_cross_branch_collision(branch, matches):
            cross_branch = True

    if cross_branch:
        return "cross_branch"
    if max_collisions <= 1:
        return "none"
    if max_collisions == 2:
        return "low"
    if max_collisions == 3:
        return "medium"
    return "high"


def _get_collisions_for_designator(
    designator: str,
    collision_index: Dict[str, Dict[str, List[str]]],
) -> List[str]:
    for section in ("numbers", "letters", "names"):
        matches = collision_index.get(section, {}).get(designator)
        if matches:
            return list(matches)
    return []


def _has_cross_branch_collision(branch: str, matches: Iterable[str]) -> bool:
    for match in matches:
        match_branch, _ = _split_collision_entry(match)
        if match_branch and match_branch != branch:
            return True
    return False


def _split_collision_entry(entry: str) -> Tuple[str, str]:
    if "." not in entry:
        return entry, ""
    return tuple(entry.split(".", 1))  # type: ignore[return-value]


def _aggregate_collision(states: List[Dict[str, Any]]) -> Tuple[bool, str]:
    collision_zone = any(state.get("gt_collision_zone_flag") for state in states)
    max_severity = "none"
    for state in states:
        severity = state.get("gt_collision_severity", "none")
        if SEVERITY_ORDER.get(severity, 0) > SEVERITY_ORDER.get(max_severity, 0):
            max_severity = severity
    return collision_zone, max_severity


def _any_complete_record(records_df: pd.DataFrame) -> bool:
    if "path_completeness" not in records_df.columns:
        return False
    values = records_df["path_completeness"].dropna()
    if values.empty:
        return False
    return (values >= 0.95).any()


def _compute_complementarity(
    records_df: pd.DataFrame,
    states: List[Dict[str, Any]],
    branch_levels: Dict[str, List[str]],
) -> float:
    if "levels_provided" not in records_df.columns:
        return 0.0
    if "state_id" not in records_df.columns:
        return 0.0

    total_coverage = 0.0
    total_redundancy = 0.0

    for state in states:
        state_id = state.get("state_id")
        branch = state.get("branch")
        depth = len(branch_levels.get(branch, [])) or 1
        state_records = records_df[records_df["state_id"] == state_id]
        covered: Set[str] = set()
        counts: Dict[str, int] = {}

        for _, row in state_records.iterrows():
            levels = row.get("levels_provided")
            if not isinstance(levels, list):
                continue
            for level in levels:
                covered.add(level)
                counts[level] = counts.get(level, 0) + 1

        coverage = len(covered) / depth
        if counts:
            avg_count = sum(counts.values()) / len(counts)
            redundancy = max(0.0, avg_count - 1) / avg_count
        else:
            redundancy = 0.0

        total_coverage += coverage
        total_redundancy += redundancy

    n_states = max(len(states), 1)
    avg_coverage = total_coverage / n_states
    avg_redundancy = total_redundancy / n_states

    return avg_coverage / (1 + avg_redundancy)


def _compute_structural_resolvability(
    records_df: pd.DataFrame,
    states: List[Dict[str, Any]],
    branch_unique_terms: Dict[str, str],
) -> bool:
    if "extraction_signals" in records_df.columns:
        for signals in records_df["extraction_signals"].dropna():
            if isinstance(signals, list):
                for signal in signals:
                    if isinstance(signal, str) and (
                        signal.startswith("branch_unique:") or signal == "depth:5"
                    ):
                        return True

    branches = {state.get("branch") for state in states if state.get("branch")}
    terms = [
        term for term, branch in branch_unique_terms.items()
        if branch in branches
    ]
    if not terms or "raw_text" not in records_df.columns:
        return False

    lower_terms = [term.lower() for term in terms]
    for text in records_df["raw_text"].dropna():
        if not isinstance(text, str):
            continue
        text_lower = text.lower()
        if any(term in text_lower for term in lower_terms):
            return True
    return False


def _assign_tier(
    *,
    any_complete: bool,
    collision_zone: bool,
    collision_severity: str,
    complementarity_score: float,
    structural_resolvability: bool,
) -> str:
    if any_complete and not collision_zone:
        return "easy"
    if any_complete and collision_zone and structural_resolvability:
        return "easy"
    if complementarity_score > 0.8 and not collision_zone:
        return "easy"
    if structural_resolvability and complementarity_score > 0.5:
        return "easy"
    if any_complete and collision_zone:
        return "moderate"

    if not collision_zone and complementarity_score > 0.5:
        return "moderate"
    if collision_zone and complementarity_score > 0.6:
        return "moderate"
    if structural_resolvability:
        return "moderate"

    if collision_severity == "cross_branch":
        if complementarity_score < 0.3:
            return "extreme"
    if collision_zone and complementarity_score < 0.3:
        return "extreme"

    return "hard"
