# Batching

**Status:** Not yet implemented  
**Last Updated:** YYYY-MM-DD

## Purpose

Group soldiers by likely component to enable focused context loading. Batch soldiers from same component together for efficient LLM processing.

## Responsibilities

- Component-based grouping
- Batch size optimization (token budget)
- Context loading per batch (hierarchy, strategy data)

## Dependencies

- **Upstream:** Preprocessing (component routing signals)
- **Downstream:** Strategy execution

## Key Design Questions (Open)

- [ ] Optimal batch size per model?
- [ ] How to handle ambiguous component assignments?
- [ ] Multi-component batch handling?

## Implementation Status

| Subcomponent | Status | Location |
|--------------|--------|----------|
| Batch Manager | Not started | `src/batching/batch_manager.py` |

## References

- Architecture: `docs/architecture/CURRENT.md`
