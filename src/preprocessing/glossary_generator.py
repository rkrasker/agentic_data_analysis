# -*- coding: utf-8 -*-
"""
Glossary generator for synthetic data preprocessing (v4.1).

Extracts terms from synthetic config files and produces a glossary
in the format expected by regex_preprocessing.py.

Build-time script: run when configs change, not at runtime.

Usage:
    python -m src.preprocessing.glossary_generator

Output:
    config/glossaries/synthetic_glossary.json
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Set

import yaml


# Paths relative to project root
PROJECT_ROOT = Path(__file__).parent.parent.parent
STYLE_SPEC_PATH = PROJECT_ROOT / "docs/components/synthetic_data_generation/synthetic_style_spec_v4.1.yaml"
HIERARCHY_PATH = PROJECT_ROOT / "config/hierarchies/hierarchy_reference.json"
VOCABULARY_PATH = PROJECT_ROOT / "config/synthetic/synthetic_vocabulary.json"
OUTPUT_PATH = PROJECT_ROOT / "config/glossaries/synthetic_glossary.json"


def load_style_spec() -> dict:
    """Load the synthetic style spec YAML."""
    with open(STYLE_SPEC_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_hierarchy() -> dict:
    """Load the hierarchy reference JSON."""
    with open(HIERARCHY_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def load_vocabulary() -> dict:
    """Load the synthetic vocabulary JSON."""
    with open(VOCABULARY_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _titleize(token: str) -> str:
    return token.replace("_", " ").title()


def extract_branch_terms(style_spec: dict, hierarchy: dict) -> List[dict]:
    """
    Extract branch terms (full name + abbreviation) as Organization Terms.
    """
    terms: List[dict] = []
    branches_spec = style_spec.get("setting", {}).get("branches", {})
    branches = hierarchy.get("branches", {})

    for branch_id, branch_cfg in branches.items():
        spec_cfg = branches_spec.get(branch_id, {})
        full_term = spec_cfg.get("name") or branch_cfg.get("name") or _titleize(branch_id)
        abbrev = spec_cfg.get("abbreviation") or branch_cfg.get("abbreviation")
        abbrevs = [abbrev] if abbrev else []

        if full_term:
            terms.append({
                "full term": full_term,
                "abbreviations": abbrevs,
                "term type": "Organization Term",
            })

    return terms


def extract_level_terms(hierarchy: dict) -> List[dict]:
    """
    Extract hierarchy level names (Sector, Fleet, Squadron, etc.) as Unit Terms.
    """
    terms: List[dict] = []
    seen: Set[str] = set()
    branches = hierarchy.get("branches", {})

    for branch_cfg in branches.values():
        for level in branch_cfg.get("levels", []):
            full_term = _titleize(level)
            if full_term and full_term not in seen:
                terms.append({
                    "full term": full_term,
                    "abbreviations": [],
                    "term type": "Unit Term",
                })
                seen.add(full_term)

    return terms


def _is_collision_designator(value: str) -> bool:
    if value.isdigit():
        return True
    if len(value) == 1 and value.isalpha():
        return True
    return False


def extract_designator_names(hierarchy: dict, vocabulary: dict) -> List[dict]:
    """
    Extract named designators (Kestrel, Verdant, Alpha, etc.) as Unit Terms.

    Note: vocabulary.json currently contains situational/clutter/confounder terms
    that do not map cleanly to Branch/Level/Designator categories, so we do not
    include them here.
    """
    terms: List[dict] = []
    seen: Set[str] = set()

    branches = hierarchy.get("branches", {})
    for branch_cfg in branches.values():
        level_config = branch_cfg.get("level_config", {})
        for level_cfg in level_config.values():
            values = level_cfg.get("values", [])
            for value in values:
                if not isinstance(value, str) or not value:
                    continue
                if _is_collision_designator(value):
                    continue
                if value in seen:
                    continue
                terms.append({
                    "full term": value,
                    "abbreviations": [],
                    "term type": "Unit Term",
                })
                seen.add(value)

    return terms


def extract_role_terms_placeholder() -> List[dict]:
    """
    Placeholder for Role Terms (ranks) - intentionally empty for v4.1.
    """
    return []


def deduplicate_terms(terms: List[dict]) -> List[dict]:
    """Remove duplicate terms, merging abbreviations where needed."""
    seen: Dict[str, dict] = {}

    for term in terms:
        full = term["full term"]
        if full in seen:
            existing_abbrevs = set(seen[full]["abbreviations"])
            new_abbrevs = set(term["abbreviations"])
            seen[full]["abbreviations"] = sorted(existing_abbrevs | new_abbrevs)
        else:
            seen[full] = term.copy()

    return list(seen.values())


def generate_glossary() -> dict:
    """
    Generate the complete glossary from synthetic configs.

    Returns a dict with metadata and term list.
    """
    style_spec = load_style_spec()
    hierarchy = load_hierarchy()
    vocabulary = load_vocabulary()

    branch_terms = extract_branch_terms(style_spec, hierarchy)
    level_terms = extract_level_terms(hierarchy)
    designator_terms = extract_designator_names(hierarchy, vocabulary)
    role_terms = extract_role_terms_placeholder()

    all_terms = branch_terms + level_terms + designator_terms + role_terms
    all_terms = deduplicate_terms(all_terms)

    type_order = {"Organization Term": 0, "Unit Term": 1, "Role Term": 2}
    all_terms.sort(key=lambda t: (type_order.get(t["term type"], 99), t["full term"]))

    return {
        "meta": {
            "version": "4.1.0",
            "description": "Auto-generated glossary for synthetic data preprocessing (Terraform Combine)",
            "source_files": [
                "docs/components/synthetic_data_generation/synthetic_style_spec_v4.1.yaml",
                "config/hierarchies/hierarchy_reference.json",
                "config/synthetic/synthetic_vocabulary.json",
            ],
            "term_types": {
                "Organization Term": "Branch terms for Terraform Combine",
                "Unit Term": "Hierarchy level names and named designators",
                "Role Term": "Rank terms (placeholder; empty in v4.1)",
            },
            "role_terms_placeholder": "Role Terms intentionally empty; ranks TBD for real data transition.",
        },
        "terms": all_terms,
    }


def main():
    """Generate and save the glossary."""
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    glossary = generate_glossary()

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(glossary, f, indent=2, ensure_ascii=False)

    term_counts = {}
    for term in glossary["terms"]:
        ttype = term["term type"]
        term_counts[ttype] = term_counts.get(ttype, 0) + 1

    print(f"Generated glossary: {OUTPUT_PATH}")
    print(f"Total terms: {len(glossary['terms'])}")
    for ttype, count in sorted(term_counts.items()):
        print(f"  {ttype}: {count}")


if __name__ == "__main__":
    main()
