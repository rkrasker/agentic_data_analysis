# Batching

**Status:** Not yet implemented  
**Last Updated:** 2026-01-15

## Purpose

Group soldiers by likely component to enable focused context loading. Batch soldiers from same component together for efficient LLM processing.

## Responsibilities

- Component-based grouping
- Batch size optimization (token budget)
- Context loading per batch (hierarchy, strategy data)
- Cross-cutting LLM batch sizing + statefulness policy (resolver generation and other LLM phases)

## Dependencies

- **Upstream:** Preprocessing (component routing signals)
- **Downstream:** Strategy execution

## Key Design Questions (Open)

- [ ] Optimal batch size per model?
- [ ] How to handle ambiguous component assignments?
- [ ] Multi-component batch handling?
- [ ] LLM batch sizing vs total sample size: how many records per LLM call, and how state is preserved across batches?
- [ ] Row similarity reduction vs signal loss for real data (ADR-003)?

## Implementation Status

| Subcomponent | Status | Location |
|--------------|--------|----------|
| Batch Manager | Not started | `src/batching/batch_manager.py` |

## References

- Architecture: `docs/architecture/CURRENT.md`
- ADR: `docs/architecture/decisions/ADR-002_llm-batching-statefulness.md`
- ADR: `docs/architecture/decisions/ADR-003_row-dedup-dim-reduction.md`
