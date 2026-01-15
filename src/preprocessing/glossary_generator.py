# -*- coding: utf-8 -*-
"""
Glossary generator for synthetic data preprocessing.

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
STYLE_SPEC_PATH = PROJECT_ROOT / "docs/components/synthetic_data_generation/synthetic_style_spec_v3.yaml"
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


def extract_role_terms(style_spec: dict) -> List[dict]:
    """
    Extract rank terms from style spec as Role Terms.

    Returns list of {full_term, abbreviations, term_type} dicts.
    """
    terms = []
    rank_rendering = style_spec.get("rank_rendering", {})
    canonical_to_variants = rank_rendering.get("canonical_to_variants", {})

    for canonical_rank, variants in canonical_to_variants.items():
        # Collect all abbreviation forms
        abbrevs = set()
        for form_name, form_value in variants.items():
            if isinstance(form_value, str) and form_value:
                abbrevs.add(form_value)

        # Remove the canonical if it ended up in abbrevs
        abbrevs.discard(canonical_rank)

        terms.append({
            "full term": canonical_rank,
            "abbreviations": sorted(abbrevs),
            "term type": "Role Term"
        })

    return terms


def extract_unit_terms(style_spec: dict) -> List[dict]:
    """
    Extract unit structure terms from style spec as Unit Terms.

    Includes:
    - Unit labels (Company, Battalion, Regiment, Division, Squadron, etc.)
    - Phonetic company names (Able, Baker, Easy, Fox, etc.)
    """
    terms = []
    unit_rendering = style_spec.get("unit_rendering", {})

    # Unit labels
    unit_labels = unit_rendering.get("unit_labels", {})

    # Company
    company_labels = unit_labels.get("company", {})
    if company_labels:
        abbrevs = set()
        for key, val in company_labels.items():
            if key != "full" and isinstance(val, str) and val:
                abbrevs.add(val)
        terms.append({
            "full term": company_labels.get("full", "Company"),
            "abbreviations": sorted(abbrevs - {""}),
            "term type": "Unit Term"
        })

    # Battalion
    battalion_labels = unit_labels.get("battalion", {})
    if battalion_labels:
        abbrevs = set()
        for key, val in battalion_labels.items():
            if key not in ("full", "ordinal") and isinstance(val, str) and val:
                abbrevs.add(val)
        terms.append({
            "full term": battalion_labels.get("full", "Battalion"),
            "abbreviations": sorted(abbrevs - {""}),
            "term type": "Unit Term"
        })

    # Regiment - note: the spec has multiple forms
    regiment_labels = unit_labels.get("regiment", {})
    if regiment_labels:
        full_term = regiment_labels.get("full", "Regiment")
        abbrevs = set()
        for key, val in regiment_labels.items():
            if key != "full" and isinstance(val, str) and val:
                abbrevs.add(val)
        terms.append({
            "full term": full_term,
            "abbreviations": sorted(abbrevs - {""}),
            "term type": "Unit Term"
        })
        # Also add "Regiment" as standalone if not already the full term
        if "Regiment" not in full_term:
            terms.append({
                "full term": "Regiment",
                "abbreviations": ["Regt", "Reg"],
                "term type": "Unit Term"
            })

    # Division (just the word, not the type - types go in Organization Terms)
    terms.append({
        "full term": "Division",
        "abbreviations": ["Div"],
        "term type": "Unit Term"
    })

    # Combat Command (armored)
    cc_labels = unit_labels.get("combat_command", {})
    if cc_labels:
        terms.append({
            "full term": cc_labels.get("full", "Combat Command"),
            "abbreviations": [cc_labels.get("abbreviated", "CC")],
            "term type": "Unit Term"
        })

    # Bomb Group (AAF)
    bg_labels = unit_labels.get("bomb_group", {})
    if bg_labels:
        terms.append({
            "full term": bg_labels.get("full", "Bombardment Group"),
            "abbreviations": [bg_labels.get("abbreviated", "BG"), "Bomb Group"],
            "term type": "Unit Term"
        })

    # Squadron (AAF)
    sq_labels = unit_labels.get("squadron", {})
    if sq_labels:
        terms.append({
            "full term": sq_labels.get("full", "Squadron"),
            "abbreviations": [sq_labels.get("abbreviated", "Sq")],
            "term type": "Unit Term"
        })

    # Phonetic company names
    company_styles = unit_rendering.get("company_styles", {})
    phonetic = company_styles.get("phonetic", {})
    for letter, name in phonetic.items():
        terms.append({
            "full term": name,
            "abbreviations": [],  # No abbreviations - these ARE the informal form
            "term type": "Unit Term"
        })

    # Add "Headquarters" / "HQ" as unit term
    terms.append({
        "full term": "Headquarters",
        "abbreviations": ["HQ", "Hq"],
        "term type": "Unit Term"
    })

    return terms


def extract_organization_terms(style_spec: dict, hierarchy: dict, vocabulary: dict) -> List[dict]:
    """
    Extract organization/branch terms as Organization Terms.

    Includes:
    - Division type indicators (Infantry Division/ID, Airborne/AB, etc.)
    - Branch indicators from vocabulary (AAF, FMF, USMC, ARMD, etc.)
    """
    terms = []
    seen_terms: Set[str] = set()

    # Division types from style spec
    unit_rendering = style_spec.get("unit_rendering", {})
    unit_labels = unit_rendering.get("unit_labels", {})
    division_types = unit_labels.get("division", {})

    for div_type, labels in division_types.items():
        if not isinstance(labels, dict):
            continue
        full_term = labels.get("full", "")
        if full_term and full_term not in seen_terms:
            abbrevs = set()
            for key, val in labels.items():
                if key != "full" and isinstance(val, str) and val:
                    abbrevs.add(val)
            terms.append({
                "full term": full_term,
                "abbreviations": sorted(abbrevs),
                "term type": "Organization Term"
            })
            seen_terms.add(full_term)

    # Service branches from hierarchy
    branches_seen = set()
    for component in hierarchy.get("components", {}).values():
        branch = component.get("service_branch", "")
        if branch and branch not in branches_seen:
            branches_seen.add(branch)

    # Map branches to terms
    branch_terms = {
        "army": {"full term": "Army", "abbreviations": ["USA"], "term type": "Organization Term"},
        "marines": {"full term": "Marine Corps", "abbreviations": ["USMC", "Marines", "Mar"], "term type": "Organization Term"},
        "army_air_forces": {"full term": "Army Air Forces", "abbreviations": ["AAF", "Air Force", "AF"], "term type": "Organization Term"},
    }
    for branch in branches_seen:
        if branch in branch_terms and branch_terms[branch]["full term"] not in seen_terms:
            terms.append(branch_terms[branch])
            seen_terms.add(branch_terms[branch]["full term"])

    # Admin codes from vocabulary that indicate organization
    vocab_list = vocabulary.get("vocabulary", [])
    org_codes = [
        # Manually curated list of admin_code terms that are organizationally meaningful
        "AGF", "ETOUSA", "FMF", "USMC", "AAF", "ABN", "PIR", "GIR", "ARMD", "MTN", "ALP",
        "TCG", "TCC", "HQ", "DET",
    ]

    for item in vocab_list:
        if isinstance(item, dict) and item.get("term_type") == "admin_code":
            term = item.get("term", "")
            if term in org_codes and term not in seen_terms:
                context = item.get("context", term)
                terms.append({
                    "full term": context,
                    "abbreviations": [term] if term != context else [],
                    "term type": "Organization Term"
                })
                seen_terms.add(term)

    # Add Parachute Infantry Regiment / Glider Infantry Regiment
    terms.append({
        "full term": "Parachute Infantry Regiment",
        "abbreviations": ["PIR"],
        "term type": "Organization Term"
    })
    terms.append({
        "full term": "Glider Infantry Regiment",
        "abbreviations": ["GIR"],
        "term type": "Organization Term"
    })

    return terms


def deduplicate_terms(terms: List[dict]) -> List[dict]:
    """Remove duplicate terms, merging abbreviations where needed."""
    seen: Dict[str, dict] = {}

    for term in terms:
        full = term["full term"]
        if full in seen:
            # Merge abbreviations
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
    # Load configs
    style_spec = load_style_spec()
    hierarchy = load_hierarchy()
    vocabulary = load_vocabulary()

    # Extract terms
    role_terms = extract_role_terms(style_spec)
    unit_terms = extract_unit_terms(style_spec)
    org_terms = extract_organization_terms(style_spec, hierarchy, vocabulary)

    # Combine and deduplicate
    all_terms = role_terms + unit_terms + org_terms
    all_terms = deduplicate_terms(all_terms)

    # Sort by term type then full term
    type_order = {"Organization Term": 0, "Unit Term": 1, "Role Term": 2}
    all_terms.sort(key=lambda t: (type_order.get(t["term type"], 99), t["full term"]))

    return {
        "meta": {
            "version": "1.0.0",
            "description": "Auto-generated glossary for synthetic data preprocessing",
            "source_files": [
                "docs/components/synthetic_data_generation/synthetic_style_spec_v3.yaml",
                "config/hierarchies/hierarchy_reference.json",
                "config/synthetic/synthetic_vocabulary.json"
            ],
            "term_types": {
                "Organization Term": "Branch, division type, and organizational indicators",
                "Unit Term": "Unit structure terms (company, battalion, regiment, etc.)",
                "Role Term": "Rank and position terms"
            }
        },
        "terms": all_terms
    }


def main():
    """Generate and save the glossary."""
    # Ensure output directory exists
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    # Generate glossary
    glossary = generate_glossary()

    # Write output
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(glossary, f, indent=2, ensure_ascii=False)

    # Summary
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
