"""
Demonstration of harness components.

Shows how to use train/test splitting, batching, and evaluation
with a minimal mock strategy.
"""

from pathlib import Path
import pandas as pd

from src.strategies import (
    BaseStrategy,
    SoldierBatch,
    ConsolidationResult,
    UnitAssignment,
    ConfidenceTier,
)
from src.evaluation import StratifiedSplitter, SplitConfig, compute_metrics
from src.batching import create_batches


class MockStrategy(BaseStrategy):
    """
    Mock strategy for demonstration.

    Returns the first valid unit from the component hierarchy.
    """

    def consolidate(self, batch: SoldierBatch) -> ConsolidationResult:
        assignments = {}

        for soldier in batch.soldiers:
            # Mock assignment using hierarchy
            if batch.hierarchy:
                levels = batch.hierarchy["organizational_structure"]["levels"]
                regiment = levels["regiment"]["designators"][0]
                battalion = levels["battalion"]["designators"][0]
                company = levels["company"]["designators"][0]

                assignment = UnitAssignment(
                    component_id=batch.component_hint or "unknown",
                    division=batch.hierarchy.get("canonical_name"),
                    regiment=int(regiment),
                    battalion=int(battalion),
                    company=company,
                    confidence=ConfidenceTier.TENTATIVE,
                    reasoning="Mock assignment using first valid units from hierarchy",
                )
            else:
                assignment = UnitAssignment(
                    component_id="unknown",
                    confidence=ConfidenceTier.TENTATIVE,
                    reasoning="No hierarchy available",
                )

            assignments[soldier.soldier_id] = assignment

        return ConsolidationResult(
            batch_id=batch.batch_id,
            assignments=assignments,
            strategy_name=self.strategy_name,
        )


def main():
    """Run harness demo."""
    print("=" * 80)
    print("Harness Components Demo")
    print("=" * 80)

    # Paths
    data_dir = Path("data/synthetic")
    config_dir = Path("config")

    validation_path = data_dir / "validation.parquet"
    canonical_path = data_dir / "canonical.parquet"
    hierarchy_path = config_dir / "hierarchies" / "hierarchy_reference.json"

    # Check if files exist
    if not validation_path.exists():
        print(f"\nError: {validation_path} not found")
        print("Run synthetic data generation first.")
        return

    # Step 1: Load data
    print("\n1. Loading data...")
    validation_df = pd.read_parquet(validation_path)
    canonical_df = pd.read_parquet(canonical_path)
    print(f"   Validation: {len(validation_df):,} soldiers")
    print(f"   Canonical: {len(canonical_df):,} records")

    # Step 2: Create train/test split
    print("\n2. Creating train/test split...")
    config = SplitConfig(
        train_ratio=0.75,
        test_ratio=0.25,
        stratify_by="regiment",
        random_seed=42,
    )
    splitter = StratifiedSplitter(config)
    splits = splitter.split(validation_df)

    # Print split summary
    total_train = sum(s.train_count for s in splits.values())
    total_test = sum(s.test_count for s in splits.values())
    print(f"   Components: {len(splits)}")
    print(f"   Train: {total_train:,} soldiers")
    print(f"   Test: {total_test:,} soldiers")

    # Get test set IDs
    test_ids = set()
    for split in splits.values():
        test_ids.update(split.test_ids)

    # Step 3: Create batches for test set
    print("\n3. Creating batches for test set...")
    batches = create_batches(
        canonical_df=canonical_df,
        hierarchy_path=hierarchy_path,
        component_mapping=None,  # No routing for demo
        soldier_filter=test_ids,
    )
    print(f"   Created {len(batches)} batches")
    if batches:
        print(f"   Sample batch: {batches[0].batch_id}")
        print(f"     Soldiers: {len(batches[0])}")
        print(f"     Records: {batches[0].total_records}")

    # Step 4: Run mock strategy
    print("\n4. Running mock strategy...")
    strategy = MockStrategy(strategy_name="mock_demo")

    all_assignments = {}
    for i, batch in enumerate(batches):
        result = strategy.consolidate(batch)
        all_assignments.update(result.assignments)
        if i == 0:
            print(f"   Batch {batch.batch_id}: {len(result.assignments)} assignments")

    print(f"   Total assignments: {len(all_assignments)}")

    # Create merged result
    merged_result = ConsolidationResult(
        batch_id="merged",
        assignments=all_assignments,
        strategy_name="mock_demo",
    )

    # Step 5: Evaluate
    print("\n5. Evaluating against ground truth...")
    test_df = splitter.get_test_df(validation_df, splits)
    metrics = compute_metrics(merged_result, test_df)

    # Print summary
    print("\n" + "=" * 80)
    metrics.print_summary()

    print("\n" + "=" * 80)
    print("Demo complete!")
    print("=" * 80)
    print("\nNext steps:")
    print("  1. Implement resolver generation workflow")
    print("  2. Implement zero-shot baseline strategy")
    print("  3. Compare strategies using this harness")


if __name__ == "__main__":
    main()
