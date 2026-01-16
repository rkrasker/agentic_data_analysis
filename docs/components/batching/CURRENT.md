# Batching

**Status:** Partially implemented (component batching complete, token-budget batching pending)
**Last Updated:** 2026-01-16

## Purpose

Two distinct batching concerns:

1. **Component-Based Batching** — Group soldiers by likely component for efficient LLM processing at consolidation time. *(Implemented)*

2. **Token-Budget Batching** — Split large datasets into LLM-sized chunks with soldier coherence, used by resolver generation and other LLM phases. *(Pending implementation)*

---

## Component-Based Batching (Implemented)

Groups soldiers by likely component to enable focused context loading.

### Location

`src/batching/batch_manager.py`

### Key Features

- Groups soldiers by component assignment
- Respects max soldiers and max records per batch
- Loads component-specific hierarchy context

### Configuration

```python
@dataclass
class BatchConfig:
    max_soldiers_per_batch: int = 50
    max_records_per_batch: int = 500
    group_by_component: bool = True
```

### Usage

```python
from src.batching import create_batches, BatchConfig

batches = create_batches(
    canonical_df=canonical_df,
    hierarchy_path=Path("config/hierarchies/hierarchy_reference.json"),
    component_mapping=component_mapping_df,
    config=BatchConfig(max_soldiers_per_batch=30),
)
```

---

## Token-Budget Batching (Pending Implementation)

### Purpose

Split datasets for LLM processing based on **token count** rather than record/soldier count. This handles variable record sizes (some soldiers have 2 records, others have 20) and ensures consistent LLM payload sizes.

### Location

`src/utils/llm/token_batcher.py` (to be created)

### Design Principles

#### 1. Token-Based Sizing

```
Problem:  "Take 20 soldiers" → wildly variable token count
Solution: "Take ≤8K tokens"  → consistent LLM load
```

| Approach | Soldiers Included | Token Count |
|----------|-------------------|-------------|
| Fixed soldier count | 20 | 2K - 40K (unpredictable) |
| **Token budget** | Variable (5-50) | ≤8K (consistent) |

#### 2. Soldier Coherence (Critical)

**All records for a single soldier MUST stay in the same batch.**

Cross-record synthesis is the core challenge of this project — interpreting one record in light of another. Splitting a soldier's records across batches defeats this purpose.

```python
# WRONG: Records split across batches
Batch 1: [S1_record1, S1_record2, S2_record1]
Batch 2: [S1_record3, S2_record2, S2_record3]

# CORRECT: Soldiers stay together
Batch 1: [S1_record1, S1_record2, S1_record3]  # All of S1
Batch 2: [S2_record1, S2_record2, S2_record3]  # All of S2
```

#### 3. Greedy Bin Packing

Pack soldiers into batches using greedy first-fit:

```python
def create_token_batches(soldiers, token_budget):
    batches = []
    current_batch = []
    current_tokens = 0

    for soldier in soldiers:
        soldier_tokens = estimate_tokens(soldier.all_records)

        if current_tokens + soldier_tokens > token_budget and current_batch:
            batches.append(current_batch)
            current_batch = []
            current_tokens = 0

        current_batch.append(soldier)
        current_tokens += soldier_tokens

    if current_batch:
        batches.append(current_batch)

    return batches
```

### Token Estimation

Use tiktoken or simple heuristics:

```python
def estimate_tokens(text: str, method: str = "chars") -> int:
    """
    Estimate token count for text.

    Methods:
    - "chars": ~4 chars per token (fast, approximate)
    - "tiktoken": Use tiktoken library (accurate, slower)
    """
    if method == "chars":
        return len(text) // 4
    elif method == "tiktoken":
        import tiktoken
        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
```

### Configuration

```python
@dataclass
class TokenBatchConfig:
    token_budget: int = 8000           # Max tokens per batch (sample text only)
    prompt_overhead: int = 2000        # Reserved for system prompt
    response_overhead: int = 2000      # Reserved for response
    estimation_method: str = "chars"   # "chars" or "tiktoken"

    @property
    def effective_budget(self) -> int:
        """Available budget after overhead."""
        return self.token_budget  # Overhead handled separately
```

### API Design

```python
from src.utils.llm.token_batcher import TokenBatcher, TokenBatchConfig

# Create batcher
batcher = TokenBatcher(TokenBatchConfig(token_budget=8000))

# From DataFrame with soldier_id and raw_text columns
batches = batcher.create_batches(
    df=records_df,
    soldier_id_col="soldier_id",
    text_col="raw_text",
)

# Returns list of TokenBatch objects
for batch in batches:
    print(f"Batch {batch.batch_id}: {batch.soldier_count} soldiers, ~{batch.estimated_tokens} tokens")
    texts = batch.get_all_texts()  # For LLM prompt
```

### Data Classes

```python
@dataclass
class TokenBatch:
    batch_id: str
    soldiers: List[SoldierTexts]
    estimated_tokens: int

    @property
    def soldier_count(self) -> int:
        return len(self.soldiers)

    @property
    def record_count(self) -> int:
        return sum(len(s.texts) for s in self.soldiers)

    def get_all_texts(self) -> List[str]:
        """Get all texts for LLM prompt construction."""
        return [text for s in self.soldiers for text in s.texts]

    def get_soldier_ids(self) -> List[str]:
        """Get all soldier IDs in this batch."""
        return [s.soldier_id for s in self.soldiers]


@dataclass
class SoldierTexts:
    soldier_id: str
    texts: List[str]
    estimated_tokens: int
```

### Ordering Support

For dual-run reconciliation (ADR-002), the batcher supports ordering control:

```python
# Forward order (default)
batches_forward = batcher.create_batches(df, order="forward")

# Inverted order
batches_inverted = batcher.create_batches(df, order="inverted")

# Custom order
batches_custom = batcher.create_batches(df, soldier_order=["S5", "S3", "S1", "S2", "S4"])
```

---

## Usage Contexts

### 1. Resolver Generation (Phases 4-8)

Token batching for pattern discovery, vocabulary, differentiators:

```python
# Sample collision records for pattern discovery
component_records = get_component_records(train_df, raw_df, component_id)
batches = batcher.create_batches(component_records)

# Run dual-pass per ADR-002
forward_results = run_stateful_extraction(batches, order="forward")
inverted_results = run_stateful_extraction(batches, order="inverted")
final_patterns = reconcile(forward_results, inverted_results)
```

### 2. Consolidation-Time Execution

Token batching for strategy execution:

```python
# Batch soldiers for consolidation
batches = batcher.create_batches(test_df)

for batch in batches:
    result = strategy.consolidate(batch)
```

### 3. Few-Shot Exemplar Selection

Token batching for exemplar context:

```python
# Fit exemplars within token budget
exemplar_batches = batcher.create_batches(exemplar_df, token_budget=2000)
```

---

## Key Design Questions (Resolved)

- [x] Token vs record-based batching? → Token-based with soldier coherence
- [x] How to handle variable record counts? → Greedy bin packing by token estimate
- [x] Ordering for dual-run? → Support forward, inverted, and custom orders

## Key Design Questions (Open)

- [ ] Exact token budget per use case (generation vs consolidation)?
- [ ] Multi-component batch handling at consolidation time?
- [ ] Row similarity reduction (ADR-003) interaction with batching?

---

## Implementation Status

| Subcomponent | Status | Location |
|--------------|--------|----------|
| Component Batch Manager | ✓ Complete | `src/batching/batch_manager.py` |
| Token Budget Batcher | ✓ Complete | `src/utils/llm/token_batcher.py` |

---

## References

- Architecture: `docs/architecture/CURRENT.md`
- ADR-002: `docs/architecture/decisions/ADR-002_llm-batching-statefulness.md`
- ADR-003: `docs/architecture/decisions/ADR-003_row-dedup-dim-reduction.md`
- Resolver Strategy: `docs/components/strategies/resolver/CURRENT.md`
