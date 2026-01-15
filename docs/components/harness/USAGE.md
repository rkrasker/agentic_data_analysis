# Harness Usage Guide

**Last Updated:** 2026-01-15

## Overview

The harness provides a strategy-agnostic framework for testing different LLM consolidation approaches. All strategies implement a common interface and use the same evaluation pipeline.

## Components

### 1. Base Strategy Interface

All strategies implement `BaseStrategy`:

```python
from src.strategies import BaseStrategy, SoldierBatch, ConsolidationResult

class MyStrategy(BaseStrategy):
    def consolidate(self, batch: SoldierBatch) -> ConsolidationResult:
        # Your consolidation logic here
        pass
```

**Key classes:**
- `SoldierBatch` - Input: batch of soldiers with records
- `ConsolidationResult` - Output: per-soldier assignments with confidence
- `UnitAssignment` - Single soldier's unit with confidence tier
- `ConfidenceTier` - Enum: ROBUST, STRONG, MODERATE, TENTATIVE

### 2. Train/Test Splitter

Stratified splitting for resolver generation and evaluation:

```python
from src.evaluation import StratifiedSplitter, SplitConfig
from pathlib import Path
import pandas as pd

# Load validation data
validation_df = pd.read_parquet("data/synthetic/validation.parquet")

# Configure splitter
config = SplitConfig(
    train_ratio=0.75,
    test_ratio=0.25,
    stratify_by="regiment",
    random_seed=42,
)

# Create splits
splitter = StratifiedSplitter(config)
splits = splitter.split(validation_df)

# Save split metadata
splitter.save_split(
    splits,
    output_path=Path("config/resolvers/train_test_split.json"),
    validation_source="data/synthetic/validation.parquet",
)

# Get train/test dataframes
train_df = splitter.get_train_df(validation_df, splits)
test_df = splitter.get_test_df(validation_df, splits)
```

**Key features:**
- Stratifies by regiment within each component
- Handles sparse components gracefully (no split if too small)
- Ensures minimum test samples per stratum
- Saves split metadata for reproducibility

### 3. Batching Manager

Groups soldiers by component for efficient processing:

```python
from src.batching import BatchManager, BatchConfig
from pathlib import Path
import pandas as pd

# Load data
canonical_df = pd.read_parquet("data/synthetic/canonical.parquet")

# Optional: component mapping for grouping
# component_mapping has columns: soldier_id, likely_component, confidence
component_mapping = None  # Create from routing signals

# Configure batching
config = BatchConfig(
    max_soldiers_per_batch=50,
    max_records_per_batch=500,
    group_by_component=True,
)

# Create batches
manager = BatchManager(config)
batches = manager.create_batches(
    canonical_df=canonical_df,
    hierarchy_path=Path("config/hierarchies/hierarchy_reference.json"),
    component_mapping=component_mapping,
    soldier_filter=test_ids,  # Optional: filter to test set
)

print(f"Created {len(batches)} batches")
for batch in batches[:3]:
    print(f"  {batch.batch_id}: {len(batch)} soldiers, {batch.total_records} records")
```

**Key features:**
- Groups by component for focused context
- Respects token budget constraints
- Filters to test set for evaluation
- Loads component hierarchy automatically

### 4. Evaluation Framework

Compare strategy predictions to ground truth:

```python
from src.evaluation import compute_metrics
import pandas as pd

# Get strategy predictions
result = strategy.consolidate(batch)

# Load ground truth
validation_df = pd.read_parquet("data/synthetic/validation.parquet")

# Compute metrics
metrics = compute_metrics(result, validation_df)

# Print summary
metrics.print_summary()

# Access specific metrics
print(f"Company accuracy: {metrics.company_accuracy:.1%}")
print(f"Cost per soldier: ${metrics.cost_per_soldier:.4f}")
```

**Metrics computed:**
- Accuracy at each level (division, regiment, battalion, company)
- Per-component breakdown
- Confidence calibration
- Cost tracking
- Error analysis

---

## Complete Example Workflow

### Step 1: Split Data

```python
from src.evaluation import StratifiedSplitter
from pathlib import Path
import pandas as pd

# Load validation data
validation_df = pd.read_parquet("data/synthetic/validation.parquet")

# Create train/test split
splitter = StratifiedSplitter()
splits = splitter.split(validation_df)

# Save split
splitter.save_split(
    splits,
    Path("config/resolvers/train_test_split.json"),
    "data/synthetic/validation.parquet"
)

# Get test set IDs
test_ids = set()
for split in splits.values():
    test_ids.update(split.test_ids)
```

### Step 2: Create Batches (Test Set Only)

```python
from src.batching import create_batches
import pandas as pd

# Load canonical data
canonical_df = pd.read_parquet("data/synthetic/canonical.parquet")

# Create batches for test set
batches = create_batches(
    canonical_df=canonical_df,
    hierarchy_path=Path("config/hierarchies/hierarchy_reference.json"),
    soldier_filter=test_ids,  # Only test set
)
```

### Step 3: Run Strategy

```python
from src.strategies import ConsolidationResult

# Initialize your strategy
strategy = MyStrategy(strategy_name="my_strategy")

# Process all batches
all_results = []
for batch in batches:
    result = strategy.consolidate(batch)
    all_results.append(result)

# Merge results
merged_result = merge_results(all_results)  # Helper function needed
```

### Step 4: Evaluate

```python
from src.evaluation import compute_metrics

# Get test set validation data
test_df = splitter.get_test_df(validation_df, splits)

# Compute metrics
metrics = compute_metrics(merged_result, test_df)
metrics.print_summary()
```

---

## Data Flow

```
validation.parquet
    ↓
[Train/Test Split]
    ↓
train_ids, test_ids
    ↓
canonical.parquet + soldier_filter=test_ids
    ↓
[Batching Manager] ← hierarchy_reference.json
    ↓
SoldierBatch objects
    ↓
[Strategy.consolidate()] ← strategy artifacts (resolver, examples, etc.)
    ↓
ConsolidationResult
    ↓
[compute_metrics()] ← validation.parquet (test_df)
    ↓
EvaluationMetrics
```

---

## Implementing a New Strategy

1. **Subclass BaseStrategy:**

```python
from src.strategies import BaseStrategy, SoldierBatch, ConsolidationResult, UnitAssignment, ConfidenceTier

class ZeroShotStrategy(BaseStrategy):
    def __init__(self, model_name: str = "gemini-2.0-flash"):
        super().__init__(strategy_name="zero_shot")
        from src.utils.llm import create_provider
        self.llm = create_provider(model_name)

    def consolidate(self, batch: SoldierBatch) -> ConsolidationResult:
        assignments = {}
        total_input = 0
        total_output = 0

        for soldier in batch.soldiers:
            # Build prompt
            prompt = self._build_prompt(soldier, batch.hierarchy)

            # Call LLM
            response = self.llm.invoke(prompt)
            total_input += response.input_tokens
            total_output += response.output_tokens

            # Parse response
            assignment = self._parse_response(response.content, soldier.soldier_id)
            assignments[soldier.soldier_id] = assignment

        return ConsolidationResult(
            batch_id=batch.batch_id,
            assignments=assignments,
            strategy_name=self.strategy_name,
            model_name="gemini-2.0-flash",
            input_tokens=total_input,
            output_tokens=total_output,
            cost_usd=self.llm.estimate_cost(total_input, total_output),
        )

    def _build_prompt(self, soldier, hierarchy):
        # Your prompt construction logic
        pass

    def _parse_response(self, content, soldier_id):
        # Your response parsing logic
        return UnitAssignment(
            component_id="1st_infantry_division",
            division="1st Infantry Division",
            regiment=5,
            battalion=2,
            company="E",
            confidence=ConfidenceTier.STRONG,
        )
```

2. **Test with harness:**

```python
# Use the workflow above with your strategy
strategy = ZeroShotStrategy()
```

---

## File Locations

| Component | Location |
|-----------|----------|
| Base Strategy | `src/strategies/base_strategy.py` |
| Splitter | `src/evaluation/split.py` |
| Metrics | `src/evaluation/metrics.py` |
| Batching | `src/batching/batch_manager.py` |
| Example | `examples/harness_demo.py` (TODO) |

---

## Next Steps

1. Implement resolver generation workflow
2. Implement zero-shot baseline strategy
3. Create end-to-end evaluation script
4. Add component routing for batching
