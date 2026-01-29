"""
Validation test for 82nd Airborne Division resolver.

This test validates the resolver by:
1. Loading unused validation soldiers (not used in resolver training)
2. Presenting raw records to the LLM with resolver context
3. Asking the LLM to return full name and fullest unit characterization
4. Comparing against ground truth from validation.parquet
"""

import json
import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Any

import numpy as np
import pandas as pd
from dotenv import load_dotenv
from tqdm import tqdm

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Load environment variables
load_dotenv(PROJECT_ROOT / ".env")

from src.utils.llm import create_provider, Message

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


# =============================================================================
# VALIDATION PROMPT
# =============================================================================

VALIDATION_SYSTEM_PROMPT = """You are an expert at parsing historical military records. Your task is to analyze raw text records for soldiers and extract:

1. FULL NAME: The soldier's complete name (first, middle initial if present, last)
2. UNIT CHARACTERIZATION: The most complete unit assignment determinable from the records

Use the provided resolver heuristics to help identify unit assignments accurately."""


def build_validation_prompt(
    soldiers: List[Dict],
    resolver: Dict[str, Any],
) -> str:
    """
    Build validation prompt for a batch of soldiers.

    Args:
        soldiers: List of dicts with soldier_id and raw_texts
        resolver: Loaded resolver JSON

    Returns:
        Formatted prompt string
    """
    # Build resolver context
    resolver_context = _format_resolver_context(resolver)

    # Build soldiers section
    soldiers_section = []
    for soldier in soldiers:
        records_text = "\n".join(f"    - {text}" for text in soldier["raw_texts"][:5])
        soldiers_section.append(f"""
Soldier ID: {soldier['soldier_id']}
Records:
{records_text}""")

    soldiers_text = "\n".join(soldiers_section)

    return f"""Analyze these soldier records and extract their full name and unit assignment.

RESOLVER HEURISTICS FOR 82nd AIRBORNE DIVISION:
{resolver_context}

SOLDIER RECORDS:
{soldiers_text}

TASK:
For each soldier, determine:
1. full_name: Complete name from records (e.g., "John A. Smith")
2. regiment: Regiment number (3, 5, or 7 for 82nd AB) or null if not determinable
3. battalion: Battalion designation (A, B, or C for 82nd AB) or null
4. company: Company number (1, 2, 3, or 4) or null
5. confidence: How confident you are (robust/strong/moderate/tentative)
6. reasoning: Brief explanation of how you determined the assignment

Respond in JSON format:
{{
  "soldiers": [
    {{
      "soldier_id": "ID",
      "full_name": "First Middle Last",
      "regiment": number or null,
      "battalion": "letter" or null,
      "company": "number" or null,
      "confidence": "robust|strong|moderate|tentative",
      "reasoning": "brief explanation"
    }}
  ]
}}"""


def _format_resolver_context(resolver: Dict[str, Any]) -> str:
    """Format resolver heuristics for the validation prompt."""
    sections = []

    # Structure
    structure = resolver.get("structure", {})
    if structure:
        struct_lines = []
        if structure.get("valid_regiments"):
            struct_lines.append(f"Valid regiments: {structure['valid_regiments']}")
        if structure.get("valid_battalions"):
            struct_lines.append(f"Valid battalions: {structure['valid_battalions']}")
        if structure.get("valid_companies"):
            struct_lines.append(f"Valid companies: {structure['valid_companies']}")
        if struct_lines:
            sections.append("STRUCTURE:\n" + "\n".join(struct_lines))

    # Patterns
    patterns = resolver.get("patterns", {})
    if patterns.get("status") == "complete" and patterns.get("entries"):
        pattern_lines = []
        for pattern, info in patterns["entries"].items():
            tier = info.get("tier", "tentative")
            means = info.get("means", "")
            pattern_lines.append(f"  - '{pattern}' [{tier}]: {means}")
        sections.append("PATTERNS:\n" + "\n".join(pattern_lines))

    # Vocabulary
    vocabulary = resolver.get("vocabulary", {})
    if vocabulary.get("status") == "complete":
        vocab_parts = []
        if vocabulary.get("strong"):
            vocab_parts.append(f"  Strong indicators: {vocabulary['strong']}")
        if vocabulary.get("moderate"):
            vocab_parts.append(f"  Moderate indicators: {vocabulary['moderate']}")
        if vocab_parts:
            sections.append("VOCABULARY:\n" + "\n".join(vocab_parts))

    return "\n\n".join(sections) if sections else "No resolver heuristics available."


@dataclass
class ValidationResult:
    """Result for a single soldier validation."""
    soldier_id: str

    # Predicted values
    predicted_name: Optional[str] = None
    predicted_regiment: Optional[int] = None
    predicted_battalion: Optional[str] = None
    predicted_company: Optional[str] = None
    predicted_confidence: Optional[str] = None
    predicted_reasoning: Optional[str] = None

    # Ground truth
    true_name: Optional[str] = None
    true_regiment: Optional[int] = None
    true_battalion: Optional[str] = None
    true_company: Optional[str] = None

    # Metrics
    name_match: bool = False
    regiment_match: bool = False
    battalion_match: bool = False
    company_match: bool = False

    # Raw records for reference
    raw_texts: List[str] = field(default_factory=list)
    quality_tiers: List[int] = field(default_factory=list)


def load_validation_data(
    validation_path: Path,
    raw_path: Path,
    component_id: str = "82nd_airborne_division",
    sample_size: int = 20,
    random_seed: int = 999,  # Different seed to minimize overlap with training
    min_quality_tier: int = 3,  # Only use records with quality_tier >= this value
) -> tuple[List[Dict], pd.DataFrame]:
    """
    Load validation soldiers and their raw text records.

    Args:
        validation_path: Path to validation.parquet
        raw_path: Path to raw.parquet
        component_id: Component to validate
        sample_size: Number of soldiers to sample
        random_seed: Random seed (use different seed than training)
        min_quality_tier: Minimum quality tier to include (3+ = degraded records)

    Returns:
        Tuple of (soldiers list for LLM, ground truth DataFrame)
    """
    rng = np.random.RandomState(random_seed)

    # Load data
    val_df = pd.read_parquet(validation_path)
    raw_df = pd.read_parquet(raw_path)

    synthetic_records_path = raw_path.parent / "synthetic_records.parquet"
    if synthetic_records_path.exists():
        synthetic_records_df = pd.read_parquet(synthetic_records_path)
        join_keys = [
            col for col in ["source_id", "soldier_id"]
            if col in raw_df.columns and col in synthetic_records_df.columns
        ]
        if join_keys:
            raw_df = raw_df.merge(
                synthetic_records_df,
                on=join_keys,
                how="left",
                suffixes=("", "_synthetic"),
            )
        else:
            logger.info("Synthetic records found but no join keys; skipping merge")

    # Normalize column names
    if "primary_id" in val_df.columns:
        val_df = val_df.rename(columns={"primary_id": "soldier_id"})

    # Filter to component
    component_soldiers = val_df[val_df["component_id"] == component_id].copy()
    logger.info(f"Found {len(component_soldiers)} soldiers for {component_id}")

    # Filter raw records to degraded quality only (tier 3+)
    if "quality_tier" in raw_df.columns:
        raw_degraded = raw_df[raw_df["quality_tier"] >= min_quality_tier].copy()
        logger.info(f"Filtered to {len(raw_degraded)} records with quality_tier >= {min_quality_tier}")
    else:
        raw_degraded = raw_df.copy()
        logger.info("quality_tier missing; using all raw records for validation")

    # Find soldiers who have degraded records
    soldiers_with_degraded = raw_degraded["soldier_id"].unique()
    component_soldiers = component_soldiers[
        component_soldiers["soldier_id"].isin(soldiers_with_degraded)
    ]
    logger.info(f"Found {len(component_soldiers)} soldiers with tier {min_quality_tier}+ records")

    # Sample soldiers
    if len(component_soldiers) > sample_size:
        indices = rng.choice(len(component_soldiers), size=sample_size, replace=False)
        sampled = component_soldiers.iloc[indices]
    else:
        sampled = component_soldiers

    logger.info(f"Sampled {len(sampled)} soldiers for validation")

    # Get ALL raw records for sampled soldiers (fair eval - show complete picture)
    soldier_ids = sampled["soldier_id"].tolist()
    raw_records = raw_df[raw_df["soldier_id"].isin(soldier_ids)]

    # Build soldiers list for LLM
    soldiers = []
    for _, row in sampled.iterrows():
        soldier_id = row["soldier_id"]
        soldier_records = raw_records[raw_records["soldier_id"] == soldier_id]
        records = soldier_records["raw_text"].tolist()
        tiers = soldier_records["quality_tier"].tolist() if "quality_tier" in soldier_records.columns else []
        soldiers.append({
            "soldier_id": soldier_id,
            "raw_texts": records,
            "quality_tiers": tiers,
        })

    return soldiers, sampled


def run_validation(
    soldiers: List[Dict],
    ground_truth: pd.DataFrame,
    resolver: Dict[str, Any],
    model_name: str = "gemini-2.5-pro",
    batch_size: int = 5,
) -> List[ValidationResult]:
    """
    Run validation by calling the LLM with resolver context.

    Args:
        soldiers: List of soldiers with raw_texts
        ground_truth: DataFrame with ground truth
        resolver: Loaded resolver JSON
        model_name: LLM model to use
        batch_size: Soldiers per LLM call

    Returns:
        List of ValidationResult objects
    """
    from src.utils.llm.structured import extract_json_from_text

    llm = create_provider(model_name, temperature=0.0)
    results = []

    # Index ground truth
    gt_index = ground_truth.set_index("soldier_id").to_dict("index")

    # Calculate total batches for progress bar
    total_batches = (len(soldiers) + batch_size - 1) // batch_size

    # Process in batches with progress bar
    batch_iter = range(0, len(soldiers), batch_size)
    pbar = tqdm(batch_iter, total=total_batches, desc="Validating soldiers", unit="batch")

    for i in pbar:
        batch = soldiers[i:i + batch_size]
        pbar.set_postfix({"soldiers": f"{i+len(batch)}/{len(soldiers)}"})

        # Build prompt
        prompt = build_validation_prompt(batch, resolver)

        # Call LLM
        messages = [
            Message(role="system", content=VALIDATION_SYSTEM_PROMPT),
            Message(role="human", content=prompt),
        ]

        try:
            response = llm.invoke(messages)
            pbar.set_postfix({
                "soldiers": f"{i+len(batch)}/{len(soldiers)}",
                "tokens": f"{response.input_tokens}→{response.output_tokens}"
            })

            # Parse response
            parsed = extract_json_from_text(response.content)

            if parsed and "soldiers" in parsed:
                for pred in parsed["soldiers"]:
                    soldier_id = pred.get("soldier_id")
                    gt = gt_index.get(soldier_id, {})

                    # Build ground truth name
                    true_name = None
                    if gt:
                        name_parts = [gt.get("name_first", "")]
                        if gt.get("name_middle"):
                            name_parts.append(gt.get("name_middle"))
                        name_parts.append(gt.get("name_last", ""))
                        true_name = " ".join(filter(None, name_parts))

                    # Normalize values for comparison - convert to strings for consistent comparison
                    pred_regiment = pred.get("regiment")
                    true_regiment = gt.get("regiment")
                    # Convert both to strings for comparison
                    pred_regiment_str = str(pred_regiment) if pred_regiment is not None else None
                    true_regiment_str = str(true_regiment) if true_regiment is not None else None

                    pred_battalion = str(pred.get("battalion", "")).upper() if pred.get("battalion") else None
                    true_battalion = str(gt.get("battalion", "")).upper() if gt.get("battalion") else None

                    pred_company = str(pred.get("company", "")) if pred.get("company") else None
                    true_company = str(gt.get("company", "")) if gt.get("company") else None

                    # Get raw texts for this soldier
                    soldier_data = next((s for s in batch if s["soldier_id"] == soldier_id), {})

                    result = ValidationResult(
                        soldier_id=soldier_id,
                        predicted_name=pred.get("full_name"),
                        predicted_regiment=pred_regiment,
                        predicted_battalion=pred_battalion,
                        predicted_company=pred_company,
                        predicted_confidence=pred.get("confidence"),
                        predicted_reasoning=pred.get("reasoning"),
                        true_name=true_name,
                        true_regiment=true_regiment,
                        true_battalion=true_battalion,
                        true_company=true_company,
                        name_match=_normalize_name(pred.get("full_name")) == _normalize_name(true_name),
                        regiment_match=pred_regiment_str == true_regiment_str,
                        battalion_match=pred_battalion == true_battalion,
                        company_match=pred_company == true_company,
                        raw_texts=soldier_data.get("raw_texts", []),
                        quality_tiers=soldier_data.get("quality_tiers", []),
                    )
                    results.append(result)

        except Exception as e:
            logger.error(f"Error processing batch: {e}")
            # Create error results for this batch
            for soldier in batch:
                results.append(ValidationResult(
                    soldier_id=soldier["soldier_id"],
                    raw_texts=soldier.get("raw_texts", []),
                ))

    return results


def _normalize_name(name: Optional[str]) -> Optional[str]:
    """Normalize name for comparison."""
    if not name:
        return None
    # Remove extra spaces, punctuation variations
    name = name.strip().lower()
    name = name.replace(".", "").replace(",", "")
    # Collapse multiple spaces
    name = " ".join(name.split())
    return name


def print_results(results: List[ValidationResult]) -> Dict[str, float]:
    """Print validation results and return metrics."""
    print("\n" + "=" * 80)
    print("VALIDATION RESULTS FOR 82nd AIRBORNE DIVISION RESOLVER")
    print("=" * 80)

    # Calculate metrics
    total = len(results)
    name_correct = sum(1 for r in results if r.name_match)
    regiment_correct = sum(1 for r in results if r.regiment_match)
    battalion_correct = sum(1 for r in results if r.battalion_match)
    company_correct = sum(1 for r in results if r.company_match)

    # Full unit match (all hierarchy levels correct)
    full_unit_match = sum(1 for r in results
                          if r.regiment_match and r.battalion_match and r.company_match)

    metrics = {
        "total_soldiers": total,
        "name_accuracy": name_correct / total if total > 0 else 0,
        "regiment_accuracy": regiment_correct / total if total > 0 else 0,
        "battalion_accuracy": battalion_correct / total if total > 0 else 0,
        "company_accuracy": company_correct / total if total > 0 else 0,
        "full_unit_accuracy": full_unit_match / total if total > 0 else 0,
    }

    print(f"\nSUMMARY METRICS:")
    print(f"  Total soldiers validated: {total}")
    print(f"  Name accuracy:            {metrics['name_accuracy']:.1%} ({name_correct}/{total})")
    print(f"  Regiment accuracy:        {metrics['regiment_accuracy']:.1%} ({regiment_correct}/{total})")
    print(f"  Battalion accuracy:       {metrics['battalion_accuracy']:.1%} ({battalion_correct}/{total})")
    print(f"  Company accuracy:         {metrics['company_accuracy']:.1%} ({company_correct}/{total})")
    print(f"  Full unit accuracy:       {metrics['full_unit_accuracy']:.1%} ({full_unit_match}/{total})")

    print("\n" + "-" * 80)
    print("INDIVIDUAL RESULTS:")
    print("-" * 80)

    for r in results:
        name_sym = "✓" if r.name_match else "✗"
        reg_sym = "✓" if r.regiment_match else "✗"
        btn_sym = "✓" if r.battalion_match else "✗"
        coy_sym = "✓" if r.company_match else "✗"

        tier_str = f"tiers={r.quality_tiers}" if r.quality_tiers else ""

        print(f"\n{r.soldier_id}: ({len(r.raw_texts)} records, {tier_str})")
        print(f"  Name:     {name_sym} predicted='{r.predicted_name}' vs true='{r.true_name}'")
        print(f"  Regiment: {reg_sym} predicted={r.predicted_regiment} vs true={r.true_regiment}")
        print(f"  Battalion:{btn_sym} predicted={r.predicted_battalion} vs true={r.true_battalion}")
        print(f"  Company:  {coy_sym} predicted={r.predicted_company} vs true={r.true_company}")
        print(f"  Confidence: {r.predicted_confidence}")
        print(f"  Reasoning: {r.predicted_reasoning}")
        if r.raw_texts:
            for i, text in enumerate(r.raw_texts[:3]):
                tier = r.quality_tiers[i] if i < len(r.quality_tiers) else "?"
                print(f"  Record [tier {tier}]: {text[:80]}...")

    return metrics


def main():
    """Run the validation test."""
    # Paths
    project_root = Path(__file__).parent.parent
    validation_path = project_root / "data" / "synthetic" / "validation.parquet"
    raw_path = project_root / "data" / "synthetic" / "raw.parquet"
    resolver_path = project_root / "config" / "resolvers" / "82nd_airborne_division_resolver.json"

    # Check files exist
    for path in [validation_path, raw_path, resolver_path]:
        if not path.exists():
            logger.error(f"Missing required file: {path}")
            return

    # Load resolver
    with open(resolver_path) as f:
        resolver = json.load(f)
    logger.info(f"Loaded resolver for {resolver['meta']['component_id']}")

    # Load validation data - using only degraded records (tier 3+)
    soldiers, ground_truth = load_validation_data(
        validation_path=validation_path,
        raw_path=raw_path,
        component_id="82nd_airborne_division",
        sample_size=20,  # Start with 20 soldiers
        random_seed=999,  # Different from training seed (42)
        min_quality_tier=3,  # Only tier 3, 4, 5 (degraded records)
    )

    # Run validation
    results = run_validation(
        soldiers=soldiers,
        ground_truth=ground_truth,
        resolver=resolver,
        model_name="gemini-2.5-pro",
        batch_size=5,
    )

    # Print results
    metrics = print_results(results)

    return metrics


if __name__ == "__main__":
    main()
