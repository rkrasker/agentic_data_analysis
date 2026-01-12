# Consolidation

**Status:** Not yet implemented  
**Last Updated:** YYYY-MM-DD

## Purpose

The core task all strategies perform: parse raw text records and synthesize information across multiple records per soldier to produce final unit assignment.

## Responsibilities

- Cross-row synthesis (aggregating across records)
- Pattern interpretation (resolving ambiguous notations)
- Confidence assignment
- Transfer detection (unit changes vs errors)

## Dependencies

- **Upstream:** Batching (soldier batches with context)
- **Downstream:** Evaluation

## Strategy-Agnostic Interface

All strategies implement the same consolidation interface:

```python
class BaseStrategy:
    def consolidate(self, batch: SoldierBatch) -> ConsolidationResult:
        """
        Input: Batch of soldiers with raw text records
        Output: Per-soldier assignments with confidence
        """
        pass
```

## Key Design Questions (Open)

- [ ] Output schema for consolidated assignments?
- [ ] How to represent confidence (tiers vs scores)?
- [ ] Transfer detection output format?

## Implementation Status

| Component | Status | Location |
|-----------|--------|----------|
| Base Strategy Interface | Not started | `src/strategies/base_strategy.py` |

## References

- Architecture: `docs/architecture/CURRENT.md`
- Strategies: `docs/components/strategies/*/CURRENT.md`
