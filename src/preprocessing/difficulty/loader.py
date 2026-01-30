# -*- coding: utf-8 -*-
"""
Load inputs for difficulty computation.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CANONICAL_PATH = PROJECT_ROOT / "data" / "synthetic" / "canonical.parquet"
DEFAULT_STRUCTURAL_PATH = (
    PROJECT_ROOT / "config" / "hierarchies" / "structural_discriminators.json"
)
DEFAULT_HIERARCHY_PATH = (
    PROJECT_ROOT / "config" / "hierarchies" / "hierarchy_reference.json"
)


def load_canonical(path: Path = DEFAULT_CANONICAL_PATH) -> pd.DataFrame:
    """Load canonical.parquet for difficulty computation."""
    if not path.exists():
        raise FileNotFoundError(f"canonical.parquet not found: {path}")
    return pd.read_parquet(path)


def load_structural_discriminators(path: Path = DEFAULT_STRUCTURAL_PATH) -> Dict:
    """Load structural_discriminators.json."""
    if not path.exists():
        raise FileNotFoundError(f"structural_discriminators.json not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_hierarchy_reference(path: Path = DEFAULT_HIERARCHY_PATH) -> Dict:
    """Load hierarchy_reference.json."""
    if not path.exists():
        raise FileNotFoundError(f"hierarchy_reference.json not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
