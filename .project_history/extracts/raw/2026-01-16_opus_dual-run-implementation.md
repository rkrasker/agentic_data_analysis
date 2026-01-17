# Thread Extract: Dual-Run Implementation Session

Date: 2026-01-16
Source: Claude Code (Opus 4.5) session

## Context

Session began with resolver generation timing out repeatedly. This led to a design discussion about batching and statefulness, culminating in the formal decision for ADR-002 and implementation of the dual-run workflow.

## Key Design Decisions

### 1. Separate Batching from Statefulness

Token-budget batching is a **global utility** (needed across all LLM phases), while statefulness decisions are **resolver-specific**. This led to:
- `src/utils/llm/token_batcher.py` as a global utility
- Dual-run orchestrator as resolver-specific infrastructure

### 2. Dual-Run Stateful Extraction (ADR-002 Decision)

**Problem:** Contextual disambiguation is critical (cross-record synthesis is the core challenge), but stateful extraction risks drift from ordering effects.

**Solution:** Run extraction twice with inverted ordering, then reconcile.

Key insight from user: "what about running the 'stateful' workflow at least twice with either deliberate inversion or shuffling of records between batches/batch orders followed by a reconciliation session as a final llm call"

### 3. Hard Case Flagging

User enhancement: "what about having the llm flag soldier id for 'hard case' in each of the batches/passes. these can be the disambiguation cases submitted to the reconciliation pass along with the conclusions of the initial passes"

Hard cases serve multiple purposes:
- Identify genuinely difficult soldiers (flagged by both runs)
- Reveal where ordering "helped" disambiguation (flagged by one run only)
- Provide targeted validation corpus for reconciliation

### 4. Pattern Robustness Classification

Patterns classified by dual-run results:
- **Robust**: Found in both runs (ordering-independent)
- **Validated**: Passed hard case testing
- **Order-dependent**: Found in one run only (flagged with lower confidence)
- **Rejected**: Failed hard case validation

## Analytic Losses Discussion

When discussing hybrid vs stateful approaches, identified irreducible losses from stateless:
1. Frequency/confidence calibration (how often pattern appears)
2. Cross-batch pattern relationships
3. Negative evidence/absence patterns
4. Early stopping efficiency
5. **Contextual disambiguation** (the key irreducible loss for this project)

User insight: "since contextual disambiguation is in many ways the key goal of this project, this is an important issue"

## Technical Implementation Notes

### Token-Budget Batching
- Size batches by token count, not record count
- Soldier coherence: all records for a soldier in same batch
- Greedy bin packing with ~4 chars per token heuristic
- Support forward, inverted, and custom ordering

### Retry Logic
- 3 retries with exponential backoff
- Handle transient errors (timeouts, rate limits)
- Configurable via RetryConfig dataclass

### Reconciliation
- Compare patterns from both runs
- Validate against hard case records (full records provided)
- Final LLM pass produces validated confidence tiers
