"""
Module 7: Main Orchestrator

Main entry point for resolver generation workflow.
Coordinates all modules to generate resolvers for all components.

Updated for ADR-002: Dual-run stateful extraction with hard case reconciliation.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Literal

import pandas as pd

from src.utils.llm import create_provider, BaseLLMProvider, TokenBatcher, TokenBatchConfig, TokenBatch, Message
from src.utils.llm.structured import extract_json_from_text
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
from .dual_run import (
    DualRunOrchestrator,
    DualRunResult,
    BatchExtractionResult,
    HardCase,
    StatefulAccumulator,
    run_dual_extraction,
)
from .reconciliation import (
    Reconciler,
    ReconciliationResult,
    reconcile_patterns,
)
from .prompts import (
    PATTERN_DISCOVERY_SYSTEM,
    build_pattern_discovery_prompt,
)


logger = logging.getLogger(__name__)


@dataclass
class GenerationConfig:
    """Configuration for resolver generation."""
    use_dual_run: bool = True
    """Whether to use dual-run extraction (ADR-002). If False, uses single-pass."""

    token_budget: int = 8000
    """Token budget per LLM batch."""

    checkpoint_dir: Optional[Path] = None
    """Directory to save checkpoints. If None, no checkpointing."""


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

    # Dual-run metrics (ADR-002)
    dual_run_enabled: bool = True
    total_hard_cases: int = 0
    hard_cases_both_runs: int = 0
    robust_patterns: int = 0
    order_dependent_patterns: int = 0

    def to_dict(self) -> Dict[str, Any]:
        result = {
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

        if self.dual_run_enabled:
            result["dual_run"] = {
                "total_hard_cases": self.total_hard_cases,
                "hard_cases_both_runs": self.hard_cases_both_runs,
                "robust_patterns": self.robust_patterns,
                "order_dependent_patterns": self.order_dependent_patterns,
            }

        return result


def generate_all_resolvers(
    validation_path: Path,
    raw_path: Path,
    hierarchy_path: Path,
    output_dir: Path,
    split_path: Optional[Path] = None,
    train_split_path: Optional[Path] = None,
    stratify_by_difficulty: bool = True,
    tier_weights: Optional[Dict[str, float]] = None,
    model_name: str = "gemini-2.5-pro",
    components_filter: Optional[List[str]] = None,
    rebuild_existing: bool = False,
    config: Optional[GenerationConfig] = None,
    progress_callback: Optional[callable] = None,
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
        train_split_path: Optional path to precomputed train split parquet
        stratify_by_difficulty: Whether to stratify sampling by difficulty tier
        tier_weights: Optional weights for difficulty tiers
        model_name: LLM model to use
        components_filter: Optional list of component IDs to process
        rebuild_existing: If True, regenerate all resolvers
        config: Generation configuration (uses defaults if None)
        progress_callback: Optional callback(phase_name: str) to report progress

    Returns:
        GenerationSummary with results
    """
    config = config or GenerationConfig()
    started = datetime.utcnow().isoformat() + "Z"

    logger.info("=" * 60)
    logger.info("RESOLVER GENERATION WORKFLOW")
    if config.use_dual_run:
        logger.info("Mode: Dual-Run with Hard Case Reconciliation (ADR-002)")
    else:
        logger.info("Mode: Single-Pass (legacy)")
    logger.info("=" * 60)

    # Initialize summary
    summary = GenerationSummary(
        started_utc=started,
        completed_utc="",
        total_components=0,
        successful=0,
        failed=0,
        skipped=0,
        dual_run_enabled=config.use_dual_run,
    )

    # Step 1: Load data
    logger.info("\nStep 1: Loading data...")
    validation_df = pd.read_parquet(validation_path)
    raw_df = pd.read_parquet(raw_path)
    logger.info(f"  Validation records: {len(validation_df)}")
    logger.info(f"  Raw records: {len(raw_df)}")

    # Step 2: Create or load split
    logger.info("\nStep 2: Train/test split...")
    if train_split_path:
        if split_path:
            logger.warning(
                "Both train_split_path and split_path provided; "
                "using train_split_path for training data."
            )
        logger.info(f"  Loading precomputed train split from {train_split_path}")
        train_df = pd.read_parquet(train_split_path)
    else:
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
    if train_split_path and not stratify_by_difficulty:
        logger.warning(
            "train_split_path provided but stratify_by_difficulty disabled; "
            "sampling will be random."
        )

    all_samples = sample_collisions(
        train_df=train_df,
        raw_df=raw_df,
        structure_result=structure_result,
        thresholds=thresholds,
        stratify_by_difficulty=stratify_by_difficulty if not train_split_path else True,
        tier_weights=tier_weights,
    )
    logger.info(f"  Components with samples: {len(all_samples)}")

    # Step 6: Initialize LLM
    logger.info("\nStep 6: Initializing LLM...")
    from src.utils.llm.base import RetryConfig

    # Configure aggressive timeouts and reduced retries
    # 5 minute timeout for individual calls, only 1 retry attempt
    retry_config = RetryConfig(
        max_retries=1,  # Reduced from 3 to avoid wasting time
        initial_delay=2.0,
        max_delay=10.0,
        retry_on_timeout=True,
        retry_on_rate_limit=True,
    )

    llm = create_provider(
        model_name,
        temperature=0.0,
        timeout=300,  # 5 minute timeout (vs old 120s which wasn't enforced)
        retry_config=retry_config,
    )
    logger.info(f"  Model: {model_name}")
    logger.info(f"  Timeout: 300s (5 min), Max retries: 1")

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
                raw_df=raw_df,
                structure_result=structure_result,
                thresholds=thresholds,
                llm=llm,
                registry=registry,
                registry_manager=registry_manager,
                output_dir=output_dir,
                rebuild_existing=rebuild_existing,
                config=config,
                progress_callback=progress_callback,
            )

            if result["status"] == "success":
                summary.successful += 1
                summary.component_results[component_id] = "success"
                # Accumulate dual-run metrics
                if config.use_dual_run and "dual_run" in result:
                    summary.total_hard_cases += result["dual_run"].get("hard_cases", 0)
                    summary.hard_cases_both_runs += result["dual_run"].get("hard_cases_both", 0)
                    summary.robust_patterns += result["dual_run"].get("robust_patterns", 0)
                    summary.order_dependent_patterns += result["dual_run"].get("order_dependent", 0)
                # Accumulate tokens
                summary.total_input_tokens += result.get("input_tokens", 0)
                summary.total_output_tokens += result.get("output_tokens", 0)
            elif result["status"] == "skipped":
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
    model_config = llm.config
    summary.estimated_cost_usd = model_config.estimate_cost(
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

    if config.use_dual_run:
        logger.info(f"  Hard cases: {summary.total_hard_cases} total, {summary.hard_cases_both_runs} in both runs")
        logger.info(f"  Patterns: {summary.robust_patterns} robust, {summary.order_dependent_patterns} order-dependent")

    return summary


def _generate_single_resolver(
    component_id: str,
    all_samples: Dict[str, ComponentSamples],
    raw_df: pd.DataFrame,
    structure_result: StructureResult,
    thresholds: ThresholdResult,
    llm: BaseLLMProvider,
    registry: ResolverRegistry,
    registry_manager: RegistryManager,
    output_dir: Path,
    rebuild_existing: bool,
    config: GenerationConfig,
    progress_callback: Optional[callable] = None,
) -> Dict[str, Any]:
    """
    Generate resolver for a single component.

    Args:
        progress_callback: Optional callback(phase_name: str) to report progress

    Returns:
        Dict with "status" ("success" or "skipped"), token counts, and dual-run metrics
    """
    tier = thresholds.get_tier(component_id)
    sample_size = thresholds.get_count(component_id)
    pct_of_median = thresholds.pct_of_median(component_id)

    logger.info(f"  Tier: {tier}, Sample size: {sample_size} ({pct_of_median:.1f}% of median)")

    # Check if rebuild needed
    if not rebuild_existing:
        if not registry_manager.should_rebuild(component_id, tier, sample_size):
            logger.info("  Skipping - no rebuild needed")
            return {"status": "skipped"}

    # Get samples
    component_samples = all_samples.get(component_id)
    if not component_samples:
        logger.warning(f"  No samples for {component_id}")
        return {"status": "skipped"}

    # Get structure
    structure = structure_result.structures.get(component_id)
    if not structure:
        raise ValueError(f"No structure found for {component_id}")

    result = {"status": "success", "input_tokens": 0, "output_tokens": 0}

    if config.use_dual_run:
        # Dual-run mode (ADR-002)
        phase_results, dual_run_metrics = _run_dual_mode(
            component_id=component_id,
            component_samples=component_samples,
            raw_df=raw_df,
            structure=structure,
            structure_result=structure_result,
            all_samples=all_samples,
            thresholds=thresholds,
            llm=llm,
            tier=tier,
            config=config,
            progress_callback=progress_callback,
        )
        result["dual_run"] = dual_run_metrics
    else:
        # Legacy single-pass mode
        phase_results = run_all_phases(
            component_id=component_id,
            component_samples=component_samples,
            all_structures=structure_result.structures,
            all_samples=all_samples,
            llm=llm,
            tier=tier,
            thresholds_result=thresholds,
            progress_callback=progress_callback,
        )

    # Assemble resolver
    resolver = assemble_resolver(
        component_id=component_id,
        tier=tier,
        sample_size=sample_size,
        pct_of_median=pct_of_median,
        structure=structure,
        phase_results=phase_results,
    )

    # Add dual-run metadata to resolver if applicable
    if config.use_dual_run and "dual_run" in result:
        resolver["meta"]["validation_mode"] = "dual_run_reconciliation"
        resolver["meta"]["hard_cases_flagged"] = result["dual_run"].get("hard_cases", 0)

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

    result["input_tokens"] = phase_results.total_input_tokens
    result["output_tokens"] = phase_results.total_output_tokens
    logger.info(f"  Tokens: {phase_results.total_input_tokens} in, {phase_results.total_output_tokens} out")

    return result


def _run_dual_mode(
    component_id: str,
    component_samples: ComponentSamples,
    raw_df: pd.DataFrame,
    structure: Any,
    structure_result: StructureResult,
    all_samples: Dict[str, ComponentSamples],
    thresholds: ThresholdResult,
    llm: BaseLLMProvider,
    tier: TierName,
    config: GenerationConfig,
    progress_callback: Optional[callable] = None,
) -> tuple:
    """
    Run dual-run extraction with reconciliation for pattern discovery.

    Args:
        progress_callback: Optional callback(phase_name: str) to report progress

    Returns:
        Tuple of (PhaseResults, dual_run_metrics dict)
    """
    logger.info("  Running dual-run extraction (ADR-002)")

    # For now, run the existing phases but with dual-run for pattern discovery
    # This is a transitional implementation - full integration would replace all phases

    # Create extraction function for pattern discovery
    def pattern_extraction_fn(batch: TokenBatch, accumulator: StatefulAccumulator, llm_provider: BaseLLMProvider) -> BatchExtractionResult:
        """Extract patterns from a batch."""
        # Get texts and soldier IDs from batch
        texts = batch.get_all_texts()
        soldier_ids = batch.get_soldier_ids()

        # Build prompt with prior context
        prior_context = accumulator.to_context_string() if accumulator.patterns else None

        # For pattern discovery, we need rival texts too
        # For this simplified version, we'll use the existing phase logic
        # A full implementation would restructure the collision-based extraction

        prompt = build_pattern_discovery_prompt(
            component_name=structure.canonical_name,
            component_id=component_id,
            rival_name="(comparison)",  # Simplified for batch extraction
            rival_id="",
            target_texts=texts,
            rival_texts=[],  # Would need rival batching too
            collision_levels=[],
            prior_context=prior_context,
            soldier_ids=soldier_ids,
        )

        messages = [
            Message(role="system", content=PATTERN_DISCOVERY_SYSTEM),
            Message(role="human", content=prompt),
        ]

        response = llm_provider.invoke(messages)
        result_json = extract_json_from_text(response.content)

        patterns = result_json.get("patterns", []) if result_json else []
        hard_cases_raw = result_json.get("hard_cases", []) if result_json else []

        hard_cases = [
            HardCase(
                soldier_id=hc.get("soldier_id", ""),
                reason=hc.get("reason", "unknown"),
                notes=hc.get("notes", ""),
            )
            for hc in hard_cases_raw
        ]

        return BatchExtractionResult(
            batch_id=batch.batch_id,
            patterns=patterns,
            hard_cases=hard_cases,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            raw_response=response.content,
        )

    # Get records for this component
    if component_samples.all_records is not None and not component_samples.all_records.empty:
        records_df = component_samples.all_records
    else:
        # Fallback: get from raw_df
        soldier_ids = component_samples.all_soldiers
        records_df = raw_df[raw_df["soldier_id"].isin(soldier_ids)].copy()

    # Run dual extraction for pattern discovery
    dual_result = run_dual_extraction(
        component_id=component_id,
        records_df=records_df,
        llm=llm,
        extraction_fn=pattern_extraction_fn,
        phase="patterns",
        token_budget=config.token_budget,
    )

    # Run reconciliation
    reconciler = Reconciler(llm)
    reconciliation = reconciler.reconcile(
        dual_run_result=dual_result,
        records_df=records_df,
        component_name=structure.canonical_name,
    )

    # Collect metrics
    dual_run_metrics = {
        "hard_cases": len(dual_result.all_hard_case_ids),
        "hard_cases_both": sum(1 for v in dual_result.hard_case_agreement.values() if v == "both"),
        "robust_patterns": len(reconciliation.robust_patterns),
        "order_dependent": len(reconciliation.order_dependent_patterns),
    }

    logger.info(f"  Dual-run: {dual_run_metrics['robust_patterns']} robust patterns, "
               f"{dual_run_metrics['hard_cases']} hard cases")

    # Now run the remaining phases (exclusions, vocabulary, differentiators)
    # using the original single-pass approach for now
    # A full implementation would apply dual-run to these as well

    phase_results = run_all_phases(
        component_id=component_id,
        component_samples=component_samples,
        all_structures=structure_result.structures,
        all_samples=all_samples,
        llm=llm,
        tier=tier,
        thresholds_result=thresholds,
        progress_callback=progress_callback,
    )

    # Merge reconciled patterns into phase results
    # Replace the single-pass patterns with reconciled patterns
    if reconciliation.final_patterns:
        phase_results.patterns.patterns = reconciliation.final_patterns
        phase_results.patterns.status = "complete"

    # Add dual-run token usage
    phase_results.patterns.input_tokens += dual_result.total_input_tokens + reconciliation.input_tokens
    phase_results.patterns.output_tokens += dual_result.total_output_tokens + reconciliation.output_tokens

    return phase_results, dual_run_metrics


def generate_single_component(
    component_id: str,
    validation_path: Path,
    raw_path: Path,
    hierarchy_path: Path,
    output_dir: Path,
    model_name: str = "gemini-2.5-pro",
    progress_callback: Optional[callable] = None,
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
        progress_callback: Optional callback(phase_name: str) to report progress

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
        progress_callback=progress_callback,
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
        "--no-dual-run",
        action="store_true",
        help="Disable dual-run extraction (use legacy single-pass)",
    )
    parser.add_argument(
        "--token-budget",
        type=int,
        default=8000,
        help="Token budget per LLM batch (default: 8000)",
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

    # Create generation config from CLI args
    config = GenerationConfig(
        use_dual_run=not args.no_dual_run,
        token_budget=args.token_budget,
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
        config=config,
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
