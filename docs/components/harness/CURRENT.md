# Strategy-Agnostic Harness

**Status:** Complete (foundation)
**Last Updated:** 2026-01-15

## Purpose

The harness provides a strategy-agnostic framework for testing and comparing different LLM consolidation approaches. It handles data preparation, batching, evaluation, and cost tracking, allowing strategies to focus purely on consolidation logic.

**Key principle:** All strategies implement the same interface (`BaseStrategy.consolidate()`), enabling fair comparison using identical test sets and metrics.

---

## Architecture Overview

```
validation.parquet + canonical.parquet
    ↓
[Train/Test Splitter] ← Strategy-agnostic
    ├── train_df (for resolver generation, few-shot examples, etc.)
    └── test_df (for evaluation)
    ↓
canonical.parquet + test_ids
    ↓
[Batching Manager] ← Strategy-agnostic
    ↓
SoldierBatch (soldiers + records + hierarchy + optional strategy artifacts)
    ↓
[Strategy.consolidate()] ← Strategy-specific
    ↓
ConsolidationResult (assignments + confidence + cost)
    ↓
[Evaluation Metrics] ← Strategy-agnostic
    ↓
EvaluationMetrics (accuracy, calibration, cost)
```

---

## Components

### 1. Base Strategy Interface

**File:** `src/strategies/base_strategy.py`

Defines the contract all strategies must implement.

#### Core Classes

**`BaseStrategy` (abstract):**
```python
class BaseStrategy(ABC):
    def consolidate(self, batch: SoldierBatch) -> ConsolidationResult:
        """Main entry point for all strategies."""
        pass
```

**`SoldierBatch` (input):**
- `batch_id`: Unique identifier
- `component_hint`: Likely component from routing (optional)
- `soldiers`: List of `SoldierRecords` (soldier_id + DataFrame of records)
- `hierarchy`: Component hierarchy dict (optional)
- `strategy_artifacts`: Strategy-specific data (e.g., resolver JSON)

**`ConsolidationResult` (output):**
- `batch_id`: Matches input batch
- `assignments`: Dict[soldier_id → `UnitAssignment`]
- `transfers`: Detected unit transfers (optional)
- `strategy_name`: Strategy identifier
- `model_name`: LLM model used
- `input_tokens`, `output_tokens`, `cost_usd`: Cost tracking
- `errors`, `warnings`: Per-soldier issues

**`UnitAssignment`:**
- `component_id`, `division`, `regiment`, `battalion`, `company`
- `confidence`: ConfidenceTier (ROBUST, STRONG, MODERATE, TENTATIVE)
- `reasoning`: Brief explanation
- `supporting_signals`, `conflicting_signals`

**`ConfidenceTier` (enum):**
- `ROBUST`: >90% certain
- `STRONG`: 75-90% certain
- `MODERATE`: 50-75% certain
- `TENTATIVE`: <50% certain, tiebreaker only

#### Usage

```python
from src.strategies import BaseStrategy, SoldierBatch, ConsolidationResult

class MyStrategy(BaseStrategy):
    def __init__(self):
        super().__init__(strategy_name="my_strategy")

    def consolidate(self, batch: SoldierBatch) -> ConsolidationResult:
        # Your consolidation logic here
        assignments = {}
        for soldier in batch.soldiers:
            # Process soldier.records, use batch.hierarchy
            assignment = UnitAssignment(...)
            assignments[soldier.soldier_id] = assignment

        return ConsolidationResult(
            batch_id=batch.batch_id,
            assignments=assignments,
            strategy_name=self.strategy_name,
            # ... token counts, cost, etc.
        )
```

---

### 2. Train/Test Splitter

**File:** `src/evaluation/split.py`

Stratified train/test splitting for reproducible evaluation.

#### Features

- **Stratification:** Splits by regiment within each component
- **Sparse handling:** Components below threshold remain unsplit
- **Configurable ratios:** Default 75% train / 25% test
- **Reproducible:** Fixed random seed
- **Leakage prevention:** Soldier-level disjoint splits (complies with ADR-001)

#### Usage

```python
from src.evaluation import StratifiedSplitter, SplitConfig

# Configure split
config = SplitConfig(
    train_ratio=0.75,
    test_ratio=0.25,
    stratify_by="regiment",
    random_seed=42,
    min_test_per_component=10,
)

# Create splitter
splitter = StratifiedSplitter(config)
splits = splitter.split(validation_df)

# Get train/test subsets
train_df = splitter.get_train_df(validation_df, splits)
test_df = splitter.get_test_df(validation_df, splits)

# Save split metadata
splitter.save_split(
    splits,
    output_path=Path("data/splits/train_test_split.json"),
    validation_source="data/synthetic/validation.parquet"
)

# Load later
splits = StratifiedSplitter.load_split(Path("data/splits/train_test_split.json"))
```

#### Split Metadata

Saved JSON contains:
- `meta`: Generation timestamp, split ratios, stratification column, random seed
- `splits`: Per-component train/test soldier IDs and counts
- `exclusions`: Components too small to split

---

### 3. Batching Manager

**File:** `src/batching/batch_manager.py`

Groups soldiers into batches for LLM processing.

#### Features

- **Component-based grouping:** Batches soldiers by likely component
- **Size constraints:** Configurable max soldiers/records per batch
- **Test set filtering:** Create batches only for test soldiers
- **Hierarchy loading:** Automatically loads component hierarchy

#### Usage

```python
from src.batching import create_batches, BatchConfig
from pathlib import Path

# Configure batching
config = BatchConfig(
    max_soldiers_per_batch=50,
    max_records_per_batch=500,
    group_by_component=True,
)

# Get test set soldier IDs
test_ids = set()
for split in splits.values():
    test_ids.update(split.test_ids)

# Create batches
batches = create_batches(
    canonical_df=canonical_df,
    hierarchy_path=Path("config/hierarchies/hierarchy_reference.json"),
    component_mapping=None,  # Optional: soldier→component mapping
    soldier_filter=test_ids,  # Only test set
    config=config,
)

# Process batches
for batch in batches:
    print(f"{batch.batch_id}: {len(batch)} soldiers, {batch.total_records} records")
    result = strategy.consolidate(batch)
```

---

### 4. Evaluation Framework

**File:** `src/evaluation/metrics.py`

Computes accuracy and calibration metrics against ground truth.

#### Metrics

**Accuracy by unit level:**
- Division-level: Most permissive
- Regiment-level: Division + regiment must match
- Battalion-level: Division + regiment + battalion must match
- Company-level: All levels must match (strictest)

**Confidence calibration:**
- Per-tier accuracy (ROBUST, STRONG, MODERATE, TENTATIVE)
- Measures if confidence assignments match actual accuracy

**Cost tracking:**
- Total tokens (input + output)
- Total cost (USD)
- Cost per soldier

**Coverage:**
- Fraction of soldiers with predictions
- Error rate

#### Usage

```python
from src.evaluation import compute_metrics

# Run strategy on test set
result = strategy.consolidate(batch)

# Evaluate against ground truth
metrics = compute_metrics(
    result=result,
    validation_df=test_df,
)

# Print summary
metrics.print_summary()

# Access specific metrics
print(f"Company accuracy: {metrics.company_accuracy:.1%}")
print(f"Cost per soldier: ${metrics.cost_per_soldier:.4f}")

# Per-component breakdown
for component_id, comp_metrics in metrics.by_component.items():
    print(f"{component_id}: {comp_metrics.company_accuracy:.1%}")
```

#### Output Example

```
================================================================================
Evaluation Summary: my_strategy
Model: gemini-2.0-flash
================================================================================

Coverage:
  Total soldiers: 1,234
  Predictions: 1,234 (100.0%)
  Errors: 45 (3.6%)

Accuracy (on non-error predictions):
  Division:  98.3%
  Regiment:  94.7%
  Battalion: 89.2%
  Company:   85.1%

Confidence Calibration:
  robust    :  234/ 250 = 93.6%
  strong    :  421/ 500 = 84.2%
  moderate  :  289/ 400 = 72.3%
  tentative :   32/  84 = 38.1%

Cost:
  Total: $1.23
  Per soldier: $0.0010
  Tokens: 456,789
================================================================================
```

---

### 5. LLM Infrastructure

**Directory:** `src/utils/llm/`

Multi-provider LLM client with structured output support.

#### Features

- **Provider abstraction:** Unified interface for Gemini, Claude, OpenAI
- **LangChain-based:** Compatible with LangChain 0.2.x through 1.2.x
- **Structured output:** Pydantic models with version-safe fallback
- **Cost tracking:** Automatic token counting and cost estimation
- **Message abstraction:** Simple `Message(role, content)` interface

#### Files

- `config.py`: Model registry, pricing, provider enum
- `base.py`: `BaseLLMProvider`, `LLMResponse`, `Message`
- `structured.py`: JSON extraction, Pydantic parsing
- `providers/gemini.py`: Full Gemini implementation
- `providers/anthropic.py`: Claude stub (ready to expand)
- `providers/openai.py`: OpenAI stub (ready to expand)

#### Usage

```python
from src.utils.llm import create_provider, Message
from pydantic import BaseModel

# Create provider
llm = create_provider("gemini-2.0-flash", temperature=0.0)

# Simple invocation
response = llm.invoke([
    Message(role="system", content="You are a helpful assistant."),
    Message(role="human", content="What is 2+2?"),
])
print(response.content)
print(f"Tokens: {response.input_tokens} in, {response.output_tokens} out")

# Structured output with Pydantic
class Answer(BaseModel):
    value: int
    explanation: str

parsed, response = llm.invoke_structured(
    [Message(role="human", content="What is 2+2?")],
    output_class=Answer
)
print(parsed.value)  # 4
print(parsed.explanation)

# Cost estimation
cost = llm.estimate_cost(response.input_tokens, response.output_tokens)
print(f"Cost: ${cost:.4f}")
```

#### Supported Models

**Gemini (ready):**
- `gemini-2.0-flash` (default)
- `gemini-2.5-pro`
- `gemini-1.5-flash`
- `gemini-1.5-pro`

**Claude (stub, requires `langchain-anthropic`):**
- `claude-3-5-sonnet`
- `claude-3-5-haiku`

**OpenAI (stub, requires `langchain-openai`):**
- `gpt-4o`
- `gpt-4o-mini`

---

## Data Flow

### Full Workflow Example

```python
from pathlib import Path
import pandas as pd
from src.evaluation import StratifiedSplitter
from src.batching import create_batches
from src.evaluation import compute_metrics
from my_strategy import MyStrategy

# 1. Load data
validation_df = pd.read_parquet("data/synthetic/validation.parquet")
canonical_df = pd.read_parquet("data/synthetic/canonical.parquet")

# 2. Create train/test split
splitter = StratifiedSplitter()
splits = splitter.split(validation_df)
test_ids = set()
for split in splits.values():
    test_ids.update(split.test_ids)

# 3. Create test batches
batches = create_batches(
    canonical_df=canonical_df,
    hierarchy_path=Path("config/hierarchies/hierarchy_reference.json"),
    soldier_filter=test_ids,
)

# 4. Run strategy
strategy = MyStrategy()
all_results = []
for batch in batches:
    result = strategy.consolidate(batch)
    all_results.append(result)

# 5. Merge results
merged_result = ConsolidationResult(
    batch_id="merged",
    assignments={k: v for r in all_results for k, v in r.assignments.items()},
    strategy_name=strategy.strategy_name,
    # ... aggregate tokens, cost, etc.
)

# 6. Evaluate
test_df = splitter.get_test_df(validation_df, splits)
metrics = compute_metrics(merged_result, test_df)
metrics.print_summary()
```

---

## Installation

Update dependencies:

```bash
pip install -r requirements.txt
```

Required packages:
- `langchain-core>=0.2.0,<2.0.0`
- `langchain-google-genai>=1.0.0` (Gemini)
- `pydantic>=2.0.0`
- `python-dotenv>=1.0.0`

Optional providers:
- `langchain-anthropic>=0.1.0` (Claude)
- `langchain-openai>=0.1.0` (OpenAI)

---

## Examples

**Demo script:** `examples/harness_demo.py`

Run the demo:
```bash
python examples/harness_demo.py
```

This demonstrates:
1. Loading validation and canonical data
2. Creating train/test split
3. Creating batches
4. Running a mock strategy
5. Evaluating against ground truth

---

## Key Design Principles

1. **Strategy-agnostic:** Harness doesn't care which strategy you use
2. **Reproducible:** Fixed random seeds, saved split metadata
3. **Leakage prevention:** Soldier-level disjoint splits (ADR-001)
4. **Cost-aware:** All operations track tokens and cost
5. **Fair comparison:** All strategies use same test set and metrics
6. **Graceful degradation:** Sparse components handled appropriately

---

## References

- Base Strategy: `src/strategies/base_strategy.py`
- Evaluation Split: `src/evaluation/split.py`
- Batching: `src/batching/batch_manager.py`
- Metrics: `src/evaluation/metrics.py`
- LLM: `src/utils/llm/`
- Demo: `examples/harness_demo.py`
- Validation Policy: `docs/architecture/decisions/ADR-001_validation-leakage-policy.md`
