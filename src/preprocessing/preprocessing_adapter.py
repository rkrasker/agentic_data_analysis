# -*- coding: utf-8 -*-
"""
Preprocessing adapter for synthetic data.

Bridges synthetic generator output (raw.parquet) to the regex extraction pipeline,
producing canonical.parquet for component routing.

Usage:
    python -m src.preprocessing.preprocessing_adapter

    # Or with custom paths:
    python -m src.preprocessing.preprocessing_adapter --input data/synthetic/raw.parquet --output data/synthetic/canonical.parquet
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Optional

import pandas as pd

from .regex_preprocessing import extract_roster_fields


# Paths relative to project root
PROJECT_ROOT = Path(__file__).parent.parent.parent
DEFAULT_INPUT_PATH = PROJECT_ROOT / "data/synthetic/raw.parquet"
DEFAULT_OUTPUT_PATH = PROJECT_ROOT / "data/synthetic/canonical.parquet"
GLOSSARY_PATH = PROJECT_ROOT / "config/glossaries/synthetic_glossary.json"


def load_glossary_as_dataframe() -> pd.DataFrame:
    """
    Load the synthetic glossary and convert to DataFrame format
    expected by regex_preprocessing.

    Expected columns: 'full term', 'abbreviations', 'term type'
    """
    with open(GLOSSARY_PATH, "r", encoding="utf-8") as f:
        glossary = json.load(f)

    terms = glossary.get("terms", [])

    return pd.DataFrame(terms)


def adapt_raw_for_extraction(df: pd.DataFrame) -> pd.DataFrame:
    """
    Adapt synthetic raw.parquet schema to regex extraction schema.

    Synthetic schema:
        source_id, soldier_id, raw_text, clerk_id, situation_id, quality_tier

    Regex extraction expects:
        Name (required), Notes (optional)

    We map raw_text -> Name and leave Notes empty.
    """
    adapted = df.copy()
    adapted["Name"] = adapted["raw_text"]
    adapted["Notes"] = ""  # No separate notes field in synthetic data
    return adapted


def run_extraction(
    input_path: Optional[Path] = None,
    output_path: Optional[Path] = None,
    enable_timing: bool = False,
) -> pd.DataFrame:
    """
    Run the full extraction pipeline.

    1. Load raw.parquet
    2. Adapt to extraction schema
    3. Load glossary
    4. Run extraction
    5. Save canonical.parquet
    6. Return result

    Args:
        input_path: Path to raw.parquet (default: data/synthetic/raw.parquet)
        output_path: Path for canonical.parquet (default: data/synthetic/canonical.parquet)
        enable_timing: If True, print timing information

    Returns:
        DataFrame with extraction results
    """
    input_path = input_path or DEFAULT_INPUT_PATH
    output_path = output_path or DEFAULT_OUTPUT_PATH

    # Load raw data
    print(f"Loading raw data from {input_path}")
    raw_df = pd.read_parquet(input_path)
    print(f"  Loaded {len(raw_df)} records")

    # Adapt schema
    adapted_df = adapt_raw_for_extraction(raw_df)

    # Load glossary
    print(f"Loading glossary from {GLOSSARY_PATH}")
    glossary_df = load_glossary_as_dataframe()
    print(f"  Loaded {len(glossary_df)} terms")

    # Configure extraction
    # Company letters for military units (including I but not J, O as they were often skipped)
    alpha_letters = list("ABCDEFGHIKLM")  # Standard WWII company letters

    # Roman numerals for battalion designations (airborne units used these)
    alpha_tokens = ["I", "II", "III", "IV", "V"]

    # Run extraction
    print("Running regex extraction...")
    if enable_timing:
        result_df, timing = extract_roster_fields(
            adapted_df,
            glossary_df,
            alpha_letters=alpha_letters,
            alpha_tokens=alpha_tokens,
            num_min_len=1,
            num_max_len=3,  # Exclude 4-digit years
            enable_timing=True,
            return_timing=True,
        )
        print("Timing breakdown:")
        for key, value in timing.items():
            if key != "errors":
                print(f"  {key}: {value:.3f}s")
        if timing.get("errors"):
            print(f"  Errors: {timing['errors']}")
    else:
        result_df = extract_roster_fields(
            adapted_df,
            glossary_df,
            alpha_letters=alpha_letters,
            alpha_tokens=alpha_tokens,
            num_min_len=1,
            num_max_len=3,
        )

    # Define columns to keep in canonical.parquet
    # Core columns (universal - work for synthetic + production)
    core_cols = ['source_id', 'soldier_id', 'raw_text']

    # Synthetic-specific columns to exclude from canonical
    synthetic_cols = ['clerk_id', 'situation_id', 'quality_tier']

    # Adapter columns to drop
    adapter_cols = ['Name', 'Notes']

    # Extraction columns = everything except core, synthetic, and adapter columns
    all_cols = set(result_df.columns)
    exclude_cols = set(core_cols + synthetic_cols + adapter_cols)
    extraction_cols = sorted(all_cols - exclude_cols)

    # Build canonical dataframe with universal schema
    canonical_df = result_df[core_cols + extraction_cols].copy()

    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Save canonical (production-ready)
    print(f"Saving canonical data to {output_path}")
    canonical_df.to_parquet(output_path, index=False)
    print(f"  Saved {len(canonical_df)} records with {len(canonical_df.columns)} columns")

    # Save synthetic metadata separately (for debugging/analysis)
    if all(col in result_df.columns for col in synthetic_cols):
        metadata_path = output_path.parent / 'synthetic_metadata.parquet'
        metadata_cols = ['source_id', 'soldier_id'] + synthetic_cols
        metadata_df = result_df[metadata_cols].copy()
        metadata_df.to_parquet(metadata_path, index=False)
        print(f"  Saved synthetic metadata to {metadata_path}")

    # Summary of extraction results
    summary_cols = [
        "Unit_Terms", "Org_Terms", "Role_Terms",
        "Unit_Term_Digit_Term:Pair", "Unit_Term_Alpha_Term:Pair",
        "Alpha_Digit:Pair", "Digit_Sequences"
    ]
    print("\nExtraction summary:")
    for col in summary_cols:
        if col in canonical_df.columns:
            non_empty = canonical_df[col].apply(lambda x: len(x) > 0 if isinstance(x, list) else False).sum()
            print(f"  {col}: {non_empty} records with matches ({100*non_empty/len(canonical_df):.1f}%)")

    return canonical_df


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Run regex extraction on synthetic raw.parquet"
    )
    parser.add_argument(
        "--input", "-i",
        type=Path,
        default=DEFAULT_INPUT_PATH,
        help="Path to input raw.parquet"
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help="Path for output canonical.parquet"
    )
    parser.add_argument(
        "--timing", "-t",
        action="store_true",
        help="Enable timing output"
    )

    args = parser.parse_args()

    run_extraction(
        input_path=args.input,
        output_path=args.output,
        enable_timing=args.timing,
    )


if __name__ == "__main__":
    main()
