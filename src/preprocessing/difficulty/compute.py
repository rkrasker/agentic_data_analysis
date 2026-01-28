# -*- coding: utf-8 -*-
"""
Compute soldier-level difficulty signals and tiers.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

import pandas as pd


@dataclass
class DifficultyAssessment:
    soldier_id: str
    collision_position: bool
    complementarity_score: float
    structural_resolvability: bool
    difficulty_tier: str
    candidate_branches: List[str]
    level_confidences: Dict[str, float]
    eliminating_constraints: List[str]


CHARACTERIZED_CONFIDENCE = 1.0
UNCHAR_SINGLE_LEVEL_CONFIDENCE = 0.75
UNCHAR_MULTI_LEVEL_CONFIDENCE = 0.25
COMPLEMENTARITY_HIGH = 0.7
COMPLEMENTARITY_LOW = 0.4
COMPLEMENTARITY_DENOM_CAP = 4


def compute_soldier_difficulty(
    soldier_id: str,
    records: pd.DataFrame,
    structural_discriminators: Dict,
    hierarchy_reference: Dict,
) -> DifficultyAssessment:
    """
    Compute difficulty signals for a single soldier.
    """
    _validate_structural_inputs(structural_discriminators, hierarchy_reference)
    collision_index = _normalize_collision_index(structural_discriminators["collision_index"])
    extraction = _extract_signals(records, hierarchy_reference)
    has_extractable = _has_extractable_values(extraction)
    collision_position, candidate_branches = _compute_collision_position(
        extraction["level_value_pairs"],
        collision_index,
        extraction["value_to_levels"],
        hierarchy_reference,
    )
    if not has_extractable:
        collision_position = True
    structural_resolvability, eliminating_constraints, candidate_branches = (
        _compute_structural_resolvability(
            extraction,
            structural_discriminators["branch_exclusion_rules"],
            hierarchy_reference,
            candidate_branches,
        )
    )
    complementarity_score, level_confidences = _compute_complementarity(
        extraction,
        hierarchy_reference,
        candidate_branches,
    )
    difficulty_tier = _assign_difficulty_tier(
        collision_position,
        structural_resolvability,
        complementarity_score,
    )
    if not has_extractable:
        difficulty_tier = "extreme"
    return DifficultyAssessment(
        soldier_id=soldier_id,
        collision_position=collision_position,
        complementarity_score=complementarity_score,
        structural_resolvability=structural_resolvability,
        difficulty_tier=difficulty_tier,
        candidate_branches=candidate_branches,
        level_confidences=level_confidences,
        eliminating_constraints=eliminating_constraints,
    )


def compute_all_soldier_difficulties(
    canonical_df: pd.DataFrame,
    structural_discriminators: Dict,
    hierarchy_reference: Dict,
) -> pd.DataFrame:
    """
    Compute difficulty for all soldiers in canonical_df.
    """
    if "soldier_id" not in canonical_df.columns:
        raise ValueError("canonical_df missing required column 'soldier_id'")

    assessments: List[DifficultyAssessment] = []
    for soldier_id, group in canonical_df.groupby("soldier_id", sort=False):
        assessments.append(
            compute_soldier_difficulty(
                soldier_id=str(soldier_id),
                records=group,
                structural_discriminators=structural_discriminators,
                hierarchy_reference=hierarchy_reference,
            )
        )

    return pd.DataFrame([_assessment_to_row(a) for a in assessments])


def _assessment_to_row(assessment: DifficultyAssessment) -> Dict[str, Any]:
    return {
        "soldier_id": assessment.soldier_id,
        "collision_position": assessment.collision_position,
        "complementarity_score": assessment.complementarity_score,
        "structural_resolvability": assessment.structural_resolvability,
        "difficulty_tier": assessment.difficulty_tier,
        "candidate_branches": assessment.candidate_branches,
        "level_confidences": assessment.level_confidences,
        "eliminating_constraints": assessment.eliminating_constraints,
    }


def _validate_structural_inputs(
    structural_discriminators: Dict,
    hierarchy_reference: Dict,
) -> None:
    required_structural = {"collision_index", "branch_exclusion_rules"}
    missing_structural = required_structural - set(structural_discriminators.keys())
    if missing_structural:
        raise ValueError(
            f"structural_discriminators missing required keys: {sorted(missing_structural)}"
        )
    if "branches" not in hierarchy_reference:
        raise ValueError("hierarchy_reference missing required key 'branches'")


def _normalize_collision_index(collision_index: Dict) -> Dict[Tuple[str, Any], Set[str]]:
    normalized: Dict[Tuple[str, Any], Set[str]] = {}
    for key, components in collision_index.items():
        if isinstance(key, tuple):
            level, value = key
            value = _normalize_unchar_value(value)
        elif isinstance(key, str):
            parsed = _parse_collision_key(key)
            if parsed is None:
                continue
            level, value = parsed
        else:
            continue
        normalized[(str(level).lower(), value)] = set(components)
    return normalized


def _parse_collision_key(key: str) -> Optional[Tuple[str, Any]]:
    text = key.strip()
    if not text.startswith("(") or not text.endswith(")"):
        return None
    inner = text[1:-1]
    parts = inner.split(", ", 1)
    if len(parts) != 2:
        return None
    level = parts[0].strip()
    value_text = parts[1].strip()
    try:
        value = json.loads(value_text)
    except Exception:
        value = value_text.strip("\"'")
    value = _normalize_unchar_value(value)
    return level.lower(), value


def _extract_signals(
    records: pd.DataFrame,
    hierarchy_reference: Dict,
) -> Dict[str, Any]:
    level_names = _collect_level_names(hierarchy_reference)
    valid_designators = _collect_valid_designators(hierarchy_reference)
    valid_designators_by_branch = _collect_valid_designators_by_branch(hierarchy_reference)
    record_values = _extract_values_from_records(records)
    level_value_pairs = _map_characterized_pairs(record_values["pairs"], level_names)
    unchar_values = record_values["unchar_values"]
    for term in record_values["unit_terms"]:
        if term.lower() not in level_names:
            unchar_values.append(term)
    value_to_levels = _map_unchar_to_levels(unchar_values, valid_designators)
    return {
        "level_names": level_names,
        "valid_designators": valid_designators,
        "valid_designators_by_branch": valid_designators_by_branch,
        "level_value_pairs": level_value_pairs,
        "value_to_levels": value_to_levels,
        "unchar_values": unchar_values,
        "term_values": record_values["terms"],
    }


def _collect_level_names(hierarchy_reference: Dict) -> Set[str]:
    level_names: Set[str] = set()
    for branch in hierarchy_reference.get("branches", {}).values():
        for level in branch.get("levels", []):
            if level:
                level_names.add(level.lower())
    return level_names


def _collect_valid_designators(hierarchy_reference: Dict) -> Dict[str, Set[Any]]:
    designators: Dict[str, Set[Any]] = {}
    for branch in hierarchy_reference.get("branches", {}).values():
        level_config = branch.get("level_config", {})
        for level_name, config in level_config.items():
            level = level_name.lower()
            values = config.get("values", [])
            designators.setdefault(level, set()).update(_normalize_values(values))
    return designators


def _collect_valid_designators_by_branch(hierarchy_reference: Dict) -> Dict[str, Dict[str, Set[Any]]]:
    designators: Dict[str, Dict[str, Set[Any]]] = {}
    for branch_id, branch in hierarchy_reference.get("branches", {}).items():
        level_config = branch.get("level_config", {})
        branch_map: Dict[str, Set[Any]] = {}
        for level_name, config in level_config.items():
            level = level_name.lower()
            values = config.get("values", [])
            branch_map.setdefault(level, set()).update(_normalize_values(values))
        designators[branch_id] = branch_map
    return designators


def _normalize_values(values: Iterable[Any]) -> List[Any]:
    normalized: List[Any] = []
    for value in values:
        if isinstance(value, int):
            normalized.append(value)
        elif isinstance(value, str):
            if value.isdigit():
                normalized.append(int(value))
            else:
                normalized.append(value.strip().upper())
        else:
            normalized.append(value)
    return normalized


def _extract_values_from_records(records: pd.DataFrame) -> Dict[str, Any]:
    pair_cols = [c for c in records.columns if c.endswith(":Pair")]
    unit_term_cols = [c for c in records.columns if "Unit_Terms" == c or "Unit_Terms" in c]
    org_term_cols = [c for c in records.columns if "Org_Terms" == c or "Org_Terms" in c]
    unchar_cols = [c for c in records.columns if c.startswith("Unchar_")]

    pairs: List[Tuple[str, Any]] = []
    for col in pair_cols:
        for values in records[col].dropna():
            pairs.extend(_parse_pair_values(values))

    terms: Set[str] = set()
    unit_terms: List[str] = []
    for col in unit_term_cols + org_term_cols:
        for values in records[col].dropna():
            for value in _to_list(values):
                if isinstance(value, str) and value:
                    terms.add(value.strip().lower())
                    if col in unit_term_cols:
                        unit_terms.append(value.strip())

    unchar_values: List[Any] = []
    for col in unchar_cols:
        for values in records[col].dropna():
            unchar_values.extend(_to_list(values))

    return {
        "pairs": pairs,
        "terms": terms,
        "unit_terms": unit_terms,
        "unchar_values": unchar_values,
    }


def _parse_pair_values(values: Any) -> List[Tuple[str, Any]]:
    pairs: List[Tuple[str, Any]] = []
    for item in _to_list(values):
        if not isinstance(item, str):
            continue
        parts = item.split(":", 1)
        if len(parts) != 2:
            continue
        left, right = parts[0].strip(), parts[1].strip()
        if not left or not right:
            continue
        pairs.append((left.lower(), _normalize_pair_value(right)))
    return pairs


def _normalize_pair_value(value: str) -> Any:
    if value.isdigit():
        return int(value)
    return value.strip().upper()


def _to_list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _map_characterized_pairs(
    pairs: Iterable[Tuple[str, Any]],
    level_names: Set[str],
) -> List[Tuple[str, Any]]:
    level_value_pairs: List[Tuple[str, Any]] = []
    for left, right in pairs:
        if left.lower() in level_names:
            level_value_pairs.append((left.lower(), right))
    return level_value_pairs


def _map_unchar_to_levels(
    values: Iterable[Any],
    valid_designators: Dict[str, Set[Any]],
) -> Dict[Any, List[str]]:
    value_to_levels: Dict[Any, List[str]] = {}
    for value in values:
        if value is None:
            continue
        normalized_value = _normalize_unchar_value(value)
        if normalized_value is None:
            continue
        matching_levels = []
        for level, designators in valid_designators.items():
            if normalized_value in designators:
                matching_levels.append(level)
        if matching_levels:
            value_to_levels.setdefault(normalized_value, sorted(set(matching_levels)))
        else:
            value_to_levels.setdefault(normalized_value, [])
    return value_to_levels


def _normalize_unchar_value(value: Any) -> Optional[Any]:
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        if stripped.isdigit():
            return int(stripped)
        return stripped.upper()
    return value


def _compute_collision_position(
    level_value_pairs: List[Tuple[str, Any]],
    collision_index: Dict[Tuple[str, Any], Set[str]],
    value_to_levels: Dict[Any, List[str]],
    hierarchy_reference: Dict,
) -> Tuple[bool, List[str]]:
    collision_components: Set[str] = set()
    for level, value in level_value_pairs:
        comps = collision_index.get((level.lower(), value))
        if comps:
            collision_components.update(comps)
    for value, levels in value_to_levels.items():
        for level in levels:
            comps = collision_index.get((level.lower(), value))
            if comps:
                collision_components.update(comps)
    if collision_components:
        candidate_branches = sorted({c.split(".")[0] for c in collision_components})
        return True, candidate_branches
    return False, sorted(hierarchy_reference.get("branches", {}).keys())


def _compute_structural_resolvability(
    extraction: Dict[str, Any],
    branch_exclusion_rules: Dict[str, List[Dict]],
    hierarchy_reference: Dict,
    candidate_branches: List[str],
) -> Tuple[bool, List[str], List[str]]:
    remaining = set(candidate_branches)
    eliminating_constraints: List[str] = []

    depth = _extracted_depth(
        extraction["level_value_pairs"],
        extraction["value_to_levels"],
    )
    if depth is not None:
        for branch_id in list(remaining):
            branch_depth = hierarchy_reference["branches"][branch_id]["depth"]
            if depth > branch_depth:
                eliminating_constraints.append(
                    f"depth {depth} exceeds branch depth {branch_depth} for {branch_id}"
                )
                remaining.discard(branch_id)

    term_values = extraction["term_values"]
    unchar_values = extraction["unchar_values"]
    normalized_unchar = {_normalize_unchar_value(v) for v in unchar_values}
    normalized_unchar.discard(None)
    for term in extraction["term_values"]:
        normalized_unchar.add(_normalize_unchar_value(term))

    for branch_id in list(remaining):
        rules = branch_exclusion_rules.get(branch_id, [])
        for rule in rules:
            rule_type = rule.get("rule_type")
            condition = rule.get("condition", "")
            if rule_type == "term_presence":
                if _condition_matches_terms(condition, term_values):
                    eliminating_constraints.append(condition)
                    remaining.discard(branch_id)
                    break
            elif rule_type == "designator_invalidity":
                if _condition_matches_designator(condition, normalized_unchar):
                    eliminating_constraints.append(condition)
                    remaining.discard(branch_id)
                    break
            elif rule_type == "depth_mismatch":
                if depth is not None and _condition_matches_depth(condition, depth):
                    eliminating_constraints.append(condition)
                    remaining.discard(branch_id)
                    break

    if len(remaining) == 1:
        return True, eliminating_constraints, sorted(remaining)
    return False, [], sorted(remaining)


def _extracted_depth(
    level_value_pairs: List[Tuple[str, Any]],
    value_to_levels: Dict[Any, List[str]],
) -> Optional[int]:
    depth = len({lvl for (lvl, _) in level_value_pairs})
    depth += sum(1 for levels in value_to_levels.values() if len(levels) == 1)
    return depth if depth > 0 else None


def _condition_matches_terms(condition: str, term_values: Set[str]) -> bool:
    token = _extract_quoted(condition)
    if not token:
        return False
    return token.lower() in term_values


def _condition_matches_designator(condition: str, designators: Set[Any]) -> bool:
    token = _extract_quoted(condition)
    if not token:
        return False
    normalized = _normalize_unchar_value(token)
    return normalized in designators


def _condition_matches_depth(condition: str, depth: int) -> bool:
    if "path has" not in condition:
        return False
    for part in condition.split():
        if part.isdigit():
            return int(part) == depth
    return False


def _extract_quoted(condition: str) -> Optional[str]:
    if "'" not in condition:
        return None
    parts = condition.split("'")
    if len(parts) < 3:
        return None
    return parts[1]


def _compute_complementarity(
    extraction: Dict[str, Any],
    hierarchy_reference: Dict,
    candidate_branches: List[str],
) -> Tuple[float, Dict[str, float]]:
    best_score = 0.0
    best_confidences: Dict[str, float] = {}
    for branch_id in candidate_branches:
        branch = hierarchy_reference["branches"][branch_id]
        branch_levels = [lvl.lower() for lvl in branch.get("levels", [])]
        level_confidences = {lvl: 0.0 for lvl in branch_levels}
        branch_designators = extraction["valid_designators_by_branch"].get(branch_id, {})

        if _has_contradictory_pairs(extraction["level_value_pairs"], branch_designators):
            score = 0.0
            if score > best_score:
                best_score = score
                best_confidences = level_confidences
            continue

        for level, _ in extraction["level_value_pairs"]:
            if level in level_confidences:
                level_confidences[level] = max(level_confidences[level], CHARACTERIZED_CONFIDENCE)

        for value, levels in extraction["value_to_levels"].items():
            if not levels:
                continue
            matching_levels = [
                level
                for level in levels
                if value in branch_designators.get(level, set())
            ]
            if not matching_levels:
                continue
            if len(matching_levels) == 1:
                level = matching_levels[0]
                if level in level_confidences:
                    level_confidences[level] = max(
                        level_confidences[level], UNCHAR_SINGLE_LEVEL_CONFIDENCE
                    )
            else:
                for level in matching_levels:
                    if level in level_confidences:
                        level_confidences[level] = max(
                            level_confidences[level], UNCHAR_MULTI_LEVEL_CONFIDENCE
                        )

        denom = min(branch.get("depth", len(branch_levels)), COMPLEMENTARITY_DENOM_CAP)
        if denom <= 0:
            score = 0.0
        else:
            score = sum(level_confidences.values()) / denom
        if score > best_score:
            best_score = score
            best_confidences = level_confidences

    return best_score, best_confidences


def _has_extractable_values(extraction: Dict[str, Any]) -> bool:
    if extraction["level_value_pairs"]:
        return True
    for levels in extraction["value_to_levels"].values():
        if levels:
            return True
    if extraction["term_values"]:
        return True
    return False


def _has_contradictory_pairs(
    level_value_pairs: List[Tuple[str, Any]],
    branch_designators: Dict[str, Set[Any]],
) -> bool:
    for level, value in level_value_pairs:
        if value not in branch_designators.get(level, set()):
            return True
    return False


def _assign_difficulty_tier(
    collision_position: bool,
    structural_resolvability: bool,
    complementarity_score: float,
) -> str:
    if not collision_position:
        return "easy"
    if structural_resolvability:
        return "moderate"
    if complementarity_score >= COMPLEMENTARITY_HIGH:
        return "moderate"
    if complementarity_score >= COMPLEMENTARITY_LOW:
        return "hard"
    return "extreme"
