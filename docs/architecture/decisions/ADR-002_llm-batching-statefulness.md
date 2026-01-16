# ADR-002: LLM Batching Statefulness for Resolver Generation

**Date:** 2026-01-15  
**Status:** proposed  
**Scope:** architecture

## Context

Resolver generation uses LLM phases that consume raw text samples. Today, each phase truncates input to a fixed number of rows, but there is no policy for splitting larger samples into multiple LLM calls while preserving cross-batch context. This is distinct from total sample size and impacts cost, latency, and the fidelity of discovered patterns.

## Options Considered

### Option A: Stateless micro-batches

Each batch is processed independently; results are merged with a simple union/deduplication step.

- Pro: Simple implementation, parallelizable
- Con: Loses cross-batch context, increases inconsistency

### Option B: Stateful iterative batches (LangChain memory or accumulator)

Process batches sequentially; maintain a stateful summary or structured accumulator that is passed into each subsequent call.

- Pro: Preserves cross-batch context, enables refinement
- Con: More complex prompts, risk of drift/overfitting to earlier batches

### Option C: Hybrid (stateless batch extraction + stateful synthesis)

Extract candidates per batch statelessly, then run a final LLM synthesis step with accumulated candidates.

- Pro: Limits state growth while preserving global reasoning
- Con: Requires an extra synthesis phase and careful schema design

## Decision

Pending. We must define a per-phase batch size (records per LLM call) and a statefulness strategy (memory vs accumulator vs hybrid), separate from total sample size. The decision should apply to resolver generation phases 4-8 and be documented in the resolver strategy and batching component docs.

## Consequences

**Easier:**
- Clear token budgeting and predictable runtime per call
- Consistent batching approach across phases

**Harder:**
- Additional orchestration and state management
- Need for robust merge logic and prompt schema design

**New constraints:**
- Per-phase batch size must be configurable
- Cross-batch state representation must be deterministic and bounded

## References

- Related ADRs: `ADR-001_validation-leakage-policy.md`
