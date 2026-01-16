"""
Module 6: Resolver Assembler

Assembles all phase outputs into final resolver JSON.
Creates the resolver artifact that will be used at consolidation time.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

from .thresholds import TierName, get_generation_mode
from .structure import ComponentStructure
from .llm_phases import PhaseResults


def assemble_resolver(
    component_id: str,
    tier: TierName,
    sample_size: int,
    pct_of_median: float,
    structure: ComponentStructure,
    phase_results: PhaseResults,
) -> Dict[str, Any]:
    """
    Assemble resolver JSON from all phase outputs.

    Args:
        component_id: Component identifier
        tier: Component tier
        sample_size: Number of soldiers in validation data
        pct_of_median: Percentage of median sample size
        structure: Component structure
        phase_results: Results from all LLM phases

    Returns:
        Complete resolver dictionary ready for JSON serialization
    """
    generation_mode = get_generation_mode(tier)

    resolver = {
        "meta": _build_meta_section(
            component_id=component_id,
            tier=tier,
            sample_size=sample_size,
            pct_of_median=pct_of_median,
            generation_mode=generation_mode,
        ),
        "structure": _build_structure_section(structure),
        "patterns": _build_patterns_section(phase_results.patterns, tier),
        "vocabulary": _build_vocabulary_section(phase_results.vocabulary, structure, tier),
        "exclusions": _build_exclusions_section(phase_results.exclusions),
        "differentiators": _build_differentiators_section(phase_results.differentiators),
    }

    # Add quality notes for sparse/under-represented components
    if tier in ("sparse", "under_represented"):
        resolver["quality_notes"] = _build_quality_notes(tier, phase_results)

    return resolver


def _build_meta_section(
    component_id: str,
    tier: TierName,
    sample_size: int,
    pct_of_median: float,
    generation_mode: str,
) -> Dict[str, Any]:
    """Build the meta section of the resolver."""
    return {
        "component_id": component_id,
        "generated_utc": datetime.utcnow().isoformat() + "Z",
        "tier": tier,
        "sample_size": sample_size,
        "pct_of_median": round(pct_of_median, 1),
        "generation_mode": generation_mode,
    }


def _build_structure_section(structure: ComponentStructure) -> Dict[str, Any]:
    """Build the structure section from component structure."""
    result = {
        "status": "complete",
        "battalion_designator_type": structure.battalion_type,
    }

    # Add non-empty designator lists
    if structure.valid_regiments:
        result["valid_regiments"] = [_try_int(r) for r in structure.valid_regiments]

    if structure.valid_battalions:
        result["valid_battalions"] = [_try_int(b) for b in structure.valid_battalions]

    if structure.valid_companies:
        result["valid_companies"] = structure.valid_companies

    # For non-standard hierarchies
    if structure.valid_combat_commands:
        result["valid_combat_commands"] = structure.valid_combat_commands

    if structure.valid_bomb_groups:
        result["valid_bomb_groups"] = [_try_int(g) for g in structure.valid_bomb_groups]

    if structure.valid_squadrons:
        result["valid_squadrons"] = [_try_int(s) for s in structure.valid_squadrons]

    return result


def _build_patterns_section(patterns_result, tier: TierName) -> Dict[str, Any]:
    """Build the patterns section from pattern discovery results."""
    if patterns_result.status == "not_generated":
        return {
            "status": "not_generated",
            "reason": "insufficient_sample",
            "rebuild_when": "tier >= under_represented",
        }

    if patterns_result.status == "limited":
        return {
            "status": "limited",
            "entries": _format_pattern_entries(patterns_result.patterns),
            "note": patterns_result.observations or "Limited data available",
        }

    return {
        "status": "complete",
        "entries": _format_pattern_entries(patterns_result.patterns),
    }


def _format_pattern_entries(patterns: List[Dict]) -> Dict[str, Dict]:
    """Format pattern list into entries dict."""
    entries = {}
    for p in patterns:
        pattern = p.get("pattern", "")
        if not pattern:
            continue

        entry = {
            "means": p.get("means", ""),
            "tier": p.get("tier", "tentative"),
        }
        if p.get("note"):
            entry["note"] = p["note"]

        entries[pattern] = entry

    return entries


def _build_vocabulary_section(
    vocabulary_result,
    structure: ComponentStructure,
    tier: TierName,
) -> Dict[str, Any]:
    """Build the vocabulary section."""
    if vocabulary_result.status == "not_generated":
        # Include known aliases from hierarchy even if vocabulary not generated
        result = {
            "status": "not_generated",
            "reason": "insufficient_sample",
        }

        if structure.aliases:
            result["known_aliases"] = structure.aliases
            result["alias_source"] = "hierarchy_reference (not validated from data)"

        return result

    result = {
        "status": vocabulary_result.status,
    }

    if vocabulary_result.strong:
        result["strong"] = vocabulary_result.strong

    if vocabulary_result.moderate:
        result["moderate"] = vocabulary_result.moderate

    if vocabulary_result.weak:
        result["weak"] = vocabulary_result.weak

    # Add any newly discovered aliases
    if vocabulary_result.discovered_aliases:
        result["discovered_aliases"] = vocabulary_result.discovered_aliases

    return result


def _build_exclusions_section(exclusions_result) -> Dict[str, Any]:
    """Build the exclusions section."""
    return {
        "structural": {
            "status": exclusions_result.structural_status,
            "rules": exclusions_result.structural,
        },
        "value_based": {
            "status": exclusions_result.value_based_status,
            "rules": exclusions_result.value_based,
        } if exclusions_result.value_based_status != "not_generated" else {
            "status": "not_generated",
            "reason": "insufficient_sample",
        },
    }


def _build_differentiators_section(
    differentiators: Dict[str, Any],
) -> Dict[str, Any]:
    """Build the differentiators section."""
    if not differentiators:
        return {
            "generation_mode": "hierarchy_only",
            "note": "No collision rivals found",
        }

    result = {}

    for rival_id, diff_result in differentiators.items():
        key = f"vs_{rival_id}"

        entry = {
            "status": diff_result.status,
            "rival_sample_size": diff_result.rival_sample_size,
        }

        if diff_result.rival_tier:
            entry["rival_tier"] = diff_result.rival_tier

        # Combine rules
        all_rules = diff_result.rules + diff_result.hierarchy_rules
        if all_rules:
            entry["rules"] = all_rules

        if diff_result.not_generated:
            entry["not_generated"] = diff_result.not_generated

        if diff_result.notes:
            entry["notes"] = diff_result.notes

        result[key] = entry

    return result


def _build_quality_notes(tier: TierName, phase_results: PhaseResults) -> List[str]:
    """Build quality notes for sparse/under-represented components."""
    notes = []

    if tier == "sparse":
        notes.append("Sample size below p25 threshold - limited heuristics available")
        notes.append("Recommend using zero-shot or few-shot strategy")

    if phase_results.patterns.status == "not_generated":
        notes.append("Pattern discovery not performed due to insufficient data")

    if phase_results.vocabulary.status == "not_generated":
        notes.append("Vocabulary discovery not performed due to insufficient data")

    # Check for high-collision rivals
    for rival_id, diff in phase_results.differentiators.items():
        if diff.status == "hierarchy_only" and not diff.hierarchy_rules:
            notes.append(f"High collision risk with {rival_id} - limited disambiguation available")

    return notes


def _try_int(value: str) -> Any:
    """Try to convert string to int, return original if not possible."""
    try:
        return int(value)
    except (ValueError, TypeError):
        return value


def save_resolver(
    resolver: Dict[str, Any],
    output_dir: Path,
    component_id: str,
) -> Path:
    """
    Save resolver JSON to file.

    Args:
        resolver: Resolver dictionary
        output_dir: Output directory
        component_id: Component identifier

    Returns:
        Path to saved file
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{component_id}_resolver.json"
    output_path = output_dir / filename

    with open(output_path, "w") as f:
        json.dump(resolver, f, indent=2)

    return output_path


def load_resolver(resolver_path: Path) -> Dict[str, Any]:
    """
    Load resolver from JSON file.

    Args:
        resolver_path: Path to resolver JSON

    Returns:
        Resolver dictionary
    """
    with open(resolver_path) as f:
        return json.load(f)


def get_resolver_path(output_dir: Path, component_id: str) -> Path:
    """Get expected path for a resolver file."""
    return output_dir / f"{component_id}_resolver.json"


def validate_resolver(resolver: Dict[str, Any]) -> List[str]:
    """
    Validate resolver structure.

    Args:
        resolver: Resolver dictionary

    Returns:
        List of validation errors (empty if valid)
    """
    errors = []

    # Check required sections
    required_sections = ["meta", "structure", "patterns", "vocabulary", "exclusions", "differentiators"]
    for section in required_sections:
        if section not in resolver:
            errors.append(f"Missing required section: {section}")

    # Validate meta
    if "meta" in resolver:
        meta = resolver["meta"]
        if "component_id" not in meta:
            errors.append("meta.component_id is required")
        if "tier" not in meta:
            errors.append("meta.tier is required")

    # Validate structure
    if "structure" in resolver:
        structure = resolver["structure"]
        if "status" not in structure:
            errors.append("structure.status is required")

    return errors
