# -*- coding: utf-8 -*-
"""
Preprocessing adapter for synthetic data (v4.1).

Bridges synthetic generator output (raw.parquet) to the regex extraction pipeline,
producing canonical.parquet for component routing and synthetic_records.parquet
for synthetic-only fields when available.

Usage:
    python -m src.preprocessing.preprocessing_adapter

    # Or with custom paths:
    python -m src.preprocessing.preprocessing_adapter --input data/synthetic/raw.parquet --output data/synthetic/canonical.parquet
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Optional, Sequence

import pandas as pd

from .regex_preprocessing import extract_roster_fields


# Paths relative to project root
PROJECT_ROOT = Path(__file__).parent.parent.parent
DEFAULT_INPUT_PATH = PROJECT_ROOT / "data/synthetic/raw.parquet"
DEFAULT_OUTPUT_PATH = PROJECT_ROOT / "data/synthetic/canonical.parquet"
DEFAULT_SYNTHETIC_RECORDS_PATH = PROJECT_ROOT / "data/synthetic/synthetic_records.parquet"
GLOSSARY_PATH = PROJECT_ROOT / "config/glossaries/synthetic_glossary.json"

RAW_CORE_COLS = ["source_id", "soldier_id", "raw_text"]


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

    Synthetic schema (v4.1):
        source_id, soldier_id, raw_text

    Regex extraction expects:
        Name (required), Notes (optional)

    We map raw_text -> Name and leave Notes empty.
    """
    adapted = df.copy()
    if "raw_text" in adapted.columns:
        adapted["Name"] = adapted["raw_text"]
    else:
        adapted["Name"] = ""
        print("Warning: raw_text missing from input; Name column filled with empty strings")
    adapted["Notes"] = ""  # No separate notes field in synthetic data
    return adapted


def _ensure_columns(df: pd.DataFrame, cols: Sequence[str]) -> pd.DataFrame:
    for col in cols:
        if col not in df.columns:
            df[col] = pd.NA
    return df


def run_extraction(
    input_path: Optional[Path] = None,
    output_path: Optional[Path] = None,
    enable_timing: bool = False,
    synthetic_records_path: Optional[Path] = None,
) -> pd.DataFrame:
    """
    Run the full extraction pipeline.

    1. Load raw.parquet
    2. Adapt to extraction schema
    3. Load glossary
    4. Run extraction
    5. Save canonical.parquet
    6. Save synthetic_records.parquet (if present or derivable)
    7. Return result

    Args:
        input_path: Path to raw.parquet (default: data/synthetic/raw.parquet)
        output_path: Path for canonical.parquet (default: data/synthetic/canonical.parquet)
        enable_timing: If True, print timing information
        synthetic_records_path: Optional path to synthetic_records.parquet

    Returns:
        DataFrame with extraction results
    """
    input_path = input_path or DEFAULT_INPUT_PATH
    output_path = output_path or DEFAULT_OUTPUT_PATH
    synthetic_records_path = synthetic_records_path or DEFAULT_SYNTHETIC_RECORDS_PATH

    # Load raw data
    print(f"Loading raw data from {input_path}")
    raw_df = pd.read_parquet(input_path)
    print(f"  Loaded {len(raw_df)} records")

    expected_raw = set(RAW_CORE_COLS)
    raw_cols = set(raw_df.columns)
    missing_expected = sorted(expected_raw - raw_cols)
    extra_cols = sorted(raw_cols - expected_raw)
    if missing_expected:
        print(f"Warning: missing expected raw columns: {missing_expected}")
    if extra_cols:
        print(f"Warning: unexpected raw columns will be routed to metadata: {extra_cols}")

    # Adapt schema
    adapted_df = adapt_raw_for_extraction(raw_df)

    # Load glossary
    print(f"Loading glossary from {GLOSSARY_PATH}")
    glossary_df = load_glossary_as_dataframe()
    print(f"  Loaded {len(glossary_df)} terms")

    # Configure extraction
    alpha_letters = list("ABCDEF")
    alpha_tokens: Sequence[str] = []

    # Run extraction
    print("Running regex extraction...")
    if enable_timing:
        result_df, timing = extract_roster_fields(
            adapted_df,
            glossary_df,
            alpha_letters=alpha_letters,
            alpha_tokens=alpha_tokens,
            num_min_len=1,
            num_max_len=3,
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

    # Ensure core columns exist for canonical output
    result_df = _ensure_columns(result_df, RAW_CORE_COLS)

    # Canonical includes core + extraction outputs
    core_cols = [c for c in RAW_CORE_COLS if c in result_df.columns]
    adapter_cols = ["Name", "Notes"]

    raw_metadata_cols = sorted(set(raw_df.columns) - set(RAW_CORE_COLS))
    exclude_cols = set(core_cols + raw_metadata_cols + adapter_cols)
    extraction_cols = sorted(set(result_df.columns) - exclude_cols)

    canonical_df = result_df[core_cols + extraction_cols].copy()

    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Save canonical (production-ready)
    print(f"Saving canonical data to {output_path}")
    canonical_df.to_parquet(output_path, index=False)
    print(f"  Saved {len(canonical_df)} records with {len(canonical_df.columns)} columns")

    # Save synthetic metadata separately (for debugging/analysis)
    raw_metadata_cols = sorted(set(raw_df.columns) - set(RAW_CORE_COLS))
    synthetic_records_df = None

    if synthetic_records_path and synthetic_records_path.exists():
        synthetic_records_df = pd.read_parquet(synthetic_records_path)
        print(f"Loaded synthetic records from {synthetic_records_path}")
    elif raw_metadata_cols:
        metadata_key_cols = [
            c for c in ["source_id", "soldier_id", "state_id"]
            if c in result_df.columns
        ]
        metadata_cols = metadata_key_cols + [c for c in raw_metadata_cols if c in result_df.columns]
        if metadata_cols:
            synthetic_records_df = result_df[metadata_cols].copy()

    if synthetic_records_df is not None and not synthetic_records_df.empty:
        metadata_path = output_path.parent / "synthetic_records.parquet"
        synthetic_records_df.to_parquet(metadata_path, index=False)
        print(f"  Saved synthetic records to {metadata_path}")
    else:
        print("Note: no synthetic records available; skipping synthetic_records.parquet")

    # Summary of extraction results
    summary_cols = [
        "Unit_Terms", "Org_Terms", "Role_Terms",
        "Unit_Term_Digit_Term:Pair", "Unit_Term_Alpha_Term:Pair",
        "Alpha_Digit:Pair", "Digit_Sequences",
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
    parser.add_argument(
        "--synthetic-records",
        type=Path,
        default=DEFAULT_SYNTHETIC_RECORDS_PATH,
        help="Optional path to synthetic_records.parquet",
    )

    args = parser.parse_args()

    run_extraction(
        input_path=args.input,
        output_path=args.output,
        enable_timing=args.timing,
        synthetic_records_path=args.synthetic_records,
    )


if __name__ == "__main__":
    main()
