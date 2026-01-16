"""
Module 7: Main Orchestrator

Main entry point for resolver generation workflow.
Coordinates all modules to generate resolvers for all components.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

import pandas as pd

from src.utils.llm import create_provider, BaseLLMProvider
from src.evaluation.split import StratifiedSplitter, SplitConfig, TrainTestSplit

from .thresholds import compute_thresholds, ThresholdResult, TierName
from .structure import extract_structure, StructureResult
from .sampling import sample_collisions, ComponentSamples
from .registry import (
    RegistryManager,
    ResolverRegistry,
    create_entry_for_tier,
    get_recommendations_for_tier,
    get_warnings_for_tier,
)
from .llm_phases import run_all_phases, PhaseResults
from .assembler import assemble_resolver, save_resolver


logger = logging.getLogger(__name__)


@dataclass
class GenerationSummary:
    """Summary of resolver generation run."""
    started_utc: str
    completed_utc: str
    total_components: int
    successful: int
    failed: int
    skipped: int

    # Token usage
    total_input_tokens: int = 0
    total_output_tokens: int = 0

    # Cost estimate
    estimated_cost_usd: float = 0.0

    # Per-component details
    component_results: Dict[str, str] = field(default_factory=dict)
    errors: Dict[str, str] = field(default_factory=dict)

    # Tier breakdown
    by_tier: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timing": {
                "started_utc": self.started_utc,
                "completed_utc": self.completed_utc,
            },
            "counts": {
                "total": self.total_components,
                "successful": self.successful,
                "failed": self.failed,
                "skipped": self.skipped,
            },
            "tokens": {
                "input": self.total_input_tokens,
                "output": self.total_output_tokens,
            },
            "estimated_cost_usd": round(self.estimated_cost_usd, 4),
            "by_tier": self.by_tier,
            "component_results": self.component_results,
            "errors": self.errors,
        }


def generate_all_resolvers(
    validation_path: Path,
    raw_path: Path,
    hierarchy_path: Path,
    output_dir: Path,
    split_path: Optional[Path] = None,
    model_name: str = "gemini-2.5-pro",
    components_filter: Optional[List[str]] = None,
    rebuild_existing: bool = False,
) -> GenerationSummary:
    """
    Generate resolvers for all components.

    This is the main entry point for the resolver generation workflow.

    Args:
        validation_path: Path to validation.parquet
        raw_path: Path to raw.parquet
        hierarchy_path: Path to hierarchy_reference.json
        output_dir: Output directory for resolver JSONs
        split_path: Optional path to existing train/test split JSON
        model_name: LLM model to use
        components_filter: Optional list of component IDs to process
        rebuild_existing: If True, regenerate all resolvers

    Returns:
        GenerationSummary with results
    """
    started = datetime.utcnow().isoformat() + "Z"

    logger.info("=" * 60)
    logger.info("RESOLVER GENERATION WORKFLOW")
    logger.info("=" * 60)

    # Initialize summary
    summary = GenerationSummary(
        started_utc=started,
        completed_utc="",
        total_components=0,
        successful=0,
        failed=0,
        skipped=0,
    )

    # Step 1: Load data
    logger.info("\nStep 1: Loading data...")
    validation_df = pd.read_parquet(validation_path)
    raw_df = pd.read_parquet(raw_path)
    logger.info(f"  Validation records: {len(validation_df)}")
    logger.info(f"  Raw records: {len(raw_df)}")

    # Step 2: Create or load split
    logger.info("\nStep 2: Train/test split...")
    splitter = StratifiedSplitter(SplitConfig())

    if split_path and split_path.exists():
        logger.info(f"  Loading existing split from {split_path}")
        splits = splitter.load_split(split_path)
    else:
        logger.info("  Creating new stratified split")
        splits = splitter.split(validation_df)
        if split_path:
            splitter.save_split(splits, split_path, str(validation_path))

    train_df = splitter.get_train_df(validation_df, splits)
    logger.info(f"  Training soldiers: {len(train_df)}")

    # Step 3: Compute thresholds
    logger.info("\nStep 3: Computing thresholds...")
    thresholds = compute_thresholds(train_df)
    logger.info(f"  Thresholds: p25={thresholds.thresholds['p25']:.0f}, "
                f"median={thresholds.thresholds['median']:.0f}, "
                f"p75={thresholds.thresholds['p75']:.0f}")

    tier_counts = thresholds.summary()
    summary.by_tier = tier_counts
    logger.info(f"  Tier distribution: {tier_counts}")

    # Step 4: Extract structure
    logger.info("\nStep 4: Extracting structure...")
    structure_result = extract_structure(hierarchy_path)
    logger.info(f"  Components in hierarchy: {len(structure_result.structures)}")
    logger.info(f"  Collision pairs: {len(structure_result.list_all_collision_pairs())}")

    # Step 5: Sample collisions
    logger.info("\nStep 5: Sampling collisions...")
    all_samples = sample_collisions(
        train_df=train_df,
        raw_df=raw_df,
        structure_result=structure_result,
        thresholds=thresholds,
    )
    logger.info(f"  Components with samples: {len(all_samples)}")

    # Step 6: Initialize LLM
    logger.info("\nStep 6: Initializing LLM...")
    llm = create_provider(model_name, temperature=0.0)
    logger.info(f"  Model: {model_name}")

    # Step 7: Initialize registry
    logger.info("\nStep 7: Initializing registry...")
    registry_path = output_dir / "resolver_registry.json"
    registry_manager = RegistryManager(registry_path)
    registry = registry_manager.create_registry(
        validation_source=str(validation_path),
        thresholds=thresholds,
        model_used=model_name,
    )

    # Step 8: Determine components to process
    if components_filter:
        components_to_process = [c for c in components_filter if c in all_samples]
    else:
        components_to_process = list(all_samples.keys())

    summary.total_components = len(components_to_process)
    logger.info(f"\nStep 8: Processing {len(components_to_process)} components...")

    # Step 9: Generate resolvers
    for i, component_id in enumerate(components_to_process, 1):
        logger.info(f"\n[{i}/{len(components_to_process)}] Processing {component_id}")

        try:
            result = _generate_single_resolver(
                component_id=component_id,
                all_samples=all_samples,
                structure_result=structure_result,
                thresholds=thresholds,
                llm=llm,
                registry=registry,
                registry_manager=registry_manager,
                output_dir=output_dir,
                rebuild_existing=rebuild_existing,
            )

            if result == "success":
                summary.successful += 1
                summary.component_results[component_id] = "success"
            elif result == "skipped":
                summary.skipped += 1
                summary.component_results[component_id] = "skipped"

        except Exception as e:
            logger.error(f"  ERROR: {e}")
            summary.failed += 1
            summary.errors[component_id] = str(e)
            summary.component_results[component_id] = "failed"

    # Step 10: Save registry
    logger.info("\nStep 10: Saving registry...")
    registry_manager.save(registry)
    logger.info(f"  Registry saved to {registry_path}")

    # Finalize summary
    summary.completed_utc = datetime.utcnow().isoformat() + "Z"

    # Estimate cost
    config = llm.config
    summary.estimated_cost_usd = config.estimate_cost(
        summary.total_input_tokens,
        summary.total_output_tokens,
    )

    logger.info("\n" + "=" * 60)
    logger.info("GENERATION COMPLETE")
    logger.info("=" * 60)
    logger.info(f"  Total: {summary.total_components}")
    logger.info(f"  Successful: {summary.successful}")
    logger.info(f"  Failed: {summary.failed}")
    logger.info(f"  Skipped: {summary.skipped}")
    logger.info(f"  Tokens: {summary.total_input_tokens} in, {summary.total_output_tokens} out")
    logger.info(f"  Estimated cost: ${summary.estimated_cost_usd:.4f}")

    return summary


def _generate_single_resolver(
    component_id: str,
    all_samples: Dict[str, ComponentSamples],
    structure_result: StructureResult,
    thresholds: ThresholdResult,
    llm: BaseLLMProvider,
    registry: ResolverRegistry,
    registry_manager: RegistryManager,
    output_dir: Path,
    rebuild_existing: bool,
) -> str:
    """
    Generate resolver for a single component.

    Returns:
        "success", "skipped", or raises exception
    """
    tier = thresholds.get_tier(component_id)
    sample_size = thresholds.get_count(component_id)
    pct_of_median = thresholds.pct_of_median(component_id)

    logger.info(f"  Tier: {tier}, Sample size: {sample_size} ({pct_of_median:.1f}% of median)")

    # Check if rebuild needed
    if not rebuild_existing:
        if not registry_manager.should_rebuild(component_id, tier, sample_size):
            logger.info("  Skipping - no rebuild needed")
            return "skipped"

    # Get samples
    component_samples = all_samples.get(component_id)
    if not component_samples:
        logger.warning(f"  No samples for {component_id}")
        return "skipped"

    # Run LLM phases
    phase_results = run_all_phases(
        component_id=component_id,
        component_samples=component_samples,
        all_structures=structure_result.structures,
        all_samples=all_samples,
        llm=llm,
        tier=tier,
        thresholds_result=thresholds,
    )

    # Get structure
    structure = structure_result.structures.get(component_id)
    if not structure:
        raise ValueError(f"No structure found for {component_id}")

    # Assemble resolver
    resolver = assemble_resolver(
        component_id=component_id,
        tier=tier,
        sample_size=sample_size,
        pct_of_median=pct_of_median,
        structure=structure,
        phase_results=phase_results,
    )

    # Save resolver
    resolver_path = save_resolver(resolver, output_dir, component_id)
    logger.info(f"  Saved: {resolver_path}")

    # Update registry
    section_status = create_entry_for_tier(component_id, tier, sample_size, pct_of_median)
    warnings = get_warnings_for_tier(tier, pct_of_median)
    recommendations = get_recommendations_for_tier(tier)

    registry_manager.add_entry(
        registry=registry,
        component_id=component_id,
        tier=tier,
        sample_size=sample_size,
        pct_of_median=pct_of_median,
        generation_mode=resolver["meta"]["generation_mode"],
        section_status=section_status,
        warnings=warnings,
        recommendations=recommendations,
    )

    logger.info(f"  Tokens: {phase_results.total_input_tokens} in, {phase_results.total_output_tokens} out")

    return "success"


def generate_single_component(
    component_id: str,
    validation_path: Path,
    raw_path: Path,
    hierarchy_path: Path,
    output_dir: Path,
    model_name: str = "gemini-2.5-pro",
) -> Dict[str, Any]:
    """
    Generate resolver for a single component.

    Convenience function for generating/regenerating a single resolver.

    Args:
        component_id: Component to generate
        validation_path: Path to validation.parquet
        raw_path: Path to raw.parquet
        hierarchy_path: Path to hierarchy_reference.json
        output_dir: Output directory
        model_name: LLM model to use

    Returns:
        Generated resolver dictionary
    """
    summary = generate_all_resolvers(
        validation_path=validation_path,
        raw_path=raw_path,
        hierarchy_path=hierarchy_path,
        output_dir=output_dir,
        model_name=model_name,
        components_filter=[component_id],
        rebuild_existing=True,
    )

    if summary.failed > 0:
        raise RuntimeError(f"Generation failed: {summary.errors}")

    # Load and return the generated resolver
    from .assembler import load_resolver, get_resolver_path

    resolver_path = get_resolver_path(output_dir, component_id)
    return load_resolver(resolver_path)


# =============================================================================
# CLI ENTRY POINT
# =============================================================================

def main():
    """Command-line entry point for resolver generation."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate resolver heuristics from validation data"
    )
    parser.add_argument(
        "--validation",
        type=Path,
        default=Path("data/validation.parquet"),
        help="Path to validation.parquet",
    )
    parser.add_argument(
        "--raw",
        type=Path,
        default=Path("data/raw.parquet"),
        help="Path to raw.parquet",
    )
    parser.add_argument(
        "--hierarchy",
        type=Path,
        default=Path("config/hierarchies/hierarchy_reference.json"),
        help="Path to hierarchy_reference.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("config/resolvers"),
        help="Output directory for resolver JSONs",
    )
    parser.add_argument(
        "--split",
        type=Path,
        default=None,
        help="Path to save/load train_test_split.json",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="gemini-2.5-pro",
        help="LLM model to use",
    )
    parser.add_argument(
        "--components",
        type=str,
        nargs="*",
        default=None,
        help="Specific components to process (default: all)",
    )
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Rebuild all resolvers regardless of registry state",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()

    # Configure logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Run generation
    summary = generate_all_resolvers(
        validation_path=args.validation,
        raw_path=args.raw,
        hierarchy_path=args.hierarchy,
        output_dir=args.output,
        split_path=args.split,
        model_name=args.model,
        components_filter=args.components,
        rebuild_existing=args.rebuild,
    )

    # Print summary
    print("\n" + "=" * 40)
    print("SUMMARY")
    print("=" * 40)
    print(f"Successful: {summary.successful}/{summary.total_components}")
    print(f"Failed: {summary.failed}")
    print(f"Estimated cost: ${summary.estimated_cost_usd:.4f}")

    if summary.errors:
        print("\nErrors:")
        for comp, error in summary.errors.items():
            print(f"  {comp}: {error}")

    return 0 if summary.failed == 0 else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
