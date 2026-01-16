# ADR-002: LLM Batching Statefulness for Resolver Generation

**Date:** 2026-01-15 (proposed), 2026-01-16 (decided)
**Status:** accepted
**Scope:** architecture

## Context

Resolver generation uses LLM phases that consume raw text samples. Each phase previously truncated input to a fixed number of rows, but there was no policy for:
1. Splitting larger samples into multiple LLM calls while preserving cross-batch context
2. Handling variable record counts per soldier (some soldiers have 2 records, others have 20)
3. Balancing contextual disambiguation (the project's core goal) against drift risk from ordering effects

This decision addresses the **statefulness strategy** for LLM phases. Token-budget batching is a separate concern addressed in the batching component docs.

## Decision Drivers

1. **Contextual disambiguation is critical** — The core challenge is interpreting ambiguous records by cross-referencing other records. Losing cross-batch context defeats the purpose.

2. **Drift from ordering is a real risk** — In stateful processing, patterns discovered in early batches can over-influence later batches, creating order-dependent artifacts.

3. **Robustness** — Generation should be fault-tolerant (single batch failure shouldn't lose all progress) and produce validated outputs.

4. **Hard cases matter most** — The quality of resolvers is determined by their performance on ambiguous cases, not easy ones.

## Options Considered

### Option A: Stateless Micro-Batches

Each batch is processed independently; results are merged with a simple union/deduplication step.

- **Pro:** Simple implementation, parallelizable, fault-tolerant
- **Con:** Loses cross-batch context, can't link related patterns across batches
- **Con:** No validation that patterns work on difficult cases

### Option B: Stateful Iterative Batches

Process batches sequentially; maintain a stateful summary or structured accumulator passed into each subsequent call.

- **Pro:** Preserves cross-batch context, enables refinement
- **Con:** Drift risk — earlier batches over-influence later ones
- **Con:** Order-dependent results (different orderings produce different patterns)
- **Con:** Single point of failure (one batch error loses all context)

### Option C: Hybrid (Stateless Extraction + Stateful Synthesis)

Extract candidates per batch statelessly, then run a final LLM synthesis step with accumulated candidates.

- **Pro:** Limits state growth while preserving global reasoning
- **Con:** Synthesis only sees extracted patterns, not original text context
- **Con:** Cross-batch pattern relationships may be missed

### Option D: Dual-Run Stateful with Hard Case Reconciliation (SELECTED)

Run the stateful workflow twice with inverted batch ordering. Each run flags "hard case" soldiers where disambiguation was difficult. A reconciliation pass validates patterns against the union of hard cases from both runs.

- **Pro:** Preserves contextual disambiguation (each run is fully stateful)
- **Pro:** Exposes drift by comparing forward vs inverted results
- **Pro:** Hard cases provide targeted validation corpus
- **Pro:** Patterns that survive both orderings are demonstrably robust
- **Con:** ~2x extraction cost (mitigated by confidence in results)

## Decision

**Selected: Option D — Dual-Run Stateful with Hard Case Reconciliation**

### Architecture

```
Run 1 (Forward Order):
  Batch A → {patterns, hard_cases: [S12, S45]}
  Batch B → {patterns, hard_cases: [S67]}        (stateful, carrying context)
  Batch C → {patterns, hard_cases: [S89, S91]}
  Output: {final_patterns, all_hard_cases: [S12, S45, S67, S89, S91]}

Run 2 (Inverted Order):
  Batch C → {patterns, hard_cases: [S91, S23]}
  Batch B → {patterns, hard_cases: [S45]}        (stateful, carrying context)
  Batch A → {patterns, hard_cases: [S12]}
  Output: {final_patterns, all_hard_cases: [S91, S23, S45, S12]}

Reconciliation:
  Inputs:
    - Run 1 final patterns + confidence
    - Run 2 final patterns + confidence
    - Hard case soldier IDs with flags (both_runs | run1_only | run2_only)
    - Full records for hard case soldiers

  Tasks:
    - Identify robust patterns (found in both runs)
    - Flag order-dependent patterns (found in one run only)
    - Validate all patterns against hard cases
    - Produce final pattern set with validated confidence tiers
```

### Hard Case Flagging

Each batch extraction returns structured hard case identification:

```json
{
  "patterns": [...],
  "hard_cases": [
    {
      "soldier_id": "S45",
      "reason": "conflicting_signals",
      "notes": "PIR and 82nd both mentioned across records"
    },
    {
      "soldier_id": "S67",
      "reason": "unusual_notation",
      "notes": "abbreviated as 'Prcht Inf' - not in known patterns"
    }
  ]
}
```

**Hard case criteria:**
- Multiple component indicators present (conflicting signals)
- Key identifiers missing or ambiguous
- Unusual notation not matching known patterns
- Low confidence in assignment despite having records
- Transfer indicators present

### Hard Case Agreement Analysis

| Hard Case Behavior | Interpretation | Action |
|-------------------|----------------|--------|
| Flagged in **both runs** | Genuinely ambiguous (order-independent difficulty) | Priority validation target |
| Flagged in **Run 1 only** | Run 2's prior context resolved it | Investigate what pattern helped |
| Flagged in **Run 2 only** | Run 1's prior context resolved it | Investigate what pattern helped |

Cases flagged by only one run reveal where ordering "helped" — the LLM used context from earlier batches to resolve ambiguity. This is valuable signal for understanding pattern dependencies.

### Pattern Robustness Classification

| Pattern Behavior | Classification | Confidence |
|-----------------|----------------|------------|
| Found in both runs, same confidence | **Robust** | High |
| Found in both runs, different confidence | **Validated** | Average of confidences |
| Found in Run 1 only | **Order-dependent** | Demoted or flagged |
| Found in Run 2 only | **Order-dependent** | Demoted or flagged |
| Fails on hard cases | **Invalid** | Rejected |

### Reconciliation Tasks

1. **Pattern comparison**: Identify agreements and disagreements between runs
2. **Hard case validation**: Test all candidate patterns against hard case records
3. **Dependency analysis**: For single-run patterns, identify what prior context enabled them
4. **Final assembly**: Produce validated pattern set with confidence tiers

### Applies To

- Phase 4: Pattern Discovery
- Phase 6: Vocabulary Discovery
- Phase 7: Differentiator Generation

Phases 5 (Exclusion Mining) and 8 (Tier Assignment) are less affected by ordering and may use single-run processing.

## Consequences

### Easier

- **Confidence in results**: Patterns that survive dual-run + hard case validation are demonstrably robust
- **Debugging drift**: When patterns differ between runs, the cause is traceable
- **Targeted validation**: Hard cases focus reconciliation on the cases that matter
- **Parallelism within runs**: Batches within a run are sequential, but the two runs can execute concurrently

### Harder

- **~2x extraction cost**: Two full passes through the data
- **More complex orchestration**: Must coordinate two runs and reconciliation
- **Hard case accumulation**: Need to store and manage flagged soldiers across batches

### New Constraints

- Hard case flagging must be part of every batch extraction prompt
- Reconciliation requires access to full records for hard case soldiers
- Registry must track which patterns were validated via dual-run vs single-run

## Implementation Notes

### Token Budget (Separate Concern)

This ADR addresses statefulness. Token-budget batching (how many tokens per LLM call) is a separate utility documented in `docs/components/batching/CURRENT.md`. Key principle: **soldier coherence** — all records for a soldier must stay in the same batch.

### Retry and Fault Tolerance

- Each batch should have retry logic (3 attempts with exponential backoff)
- If a batch fails after retries, log the failure and continue (graceful degradation)
- Failed batches are noted in reconciliation for potential manual review

### Checkpointing

- Save batch results as they complete
- If process is interrupted, resume from last checkpoint
- Registry tracks partial generation state

## References

- Related ADRs: `ADR-001_validation-leakage-policy.md`, `ADR-003_row-dedup-dim-reduction.md`
- Batching component: `docs/components/batching/CURRENT.md`
- Resolver strategy: `docs/components/strategies/resolver/CURRENT.md`
