# Multi-Pass Strategy

**Status:** Not yet implemented  
**Last Updated:** YYYY-MM-DD

## Purpose

Consolidation using iterative refinement across multiple LLM calls. First pass discovers patterns; subsequent passes apply and refine.

## Pass Structure

### Pass 1: Discovery
- Input: Raw text records + hierarchy
- Task: Identify patterns, flag ambiguities, initial consolidation
- Output: Draft consolidations + discovered patterns

### Pass 2: Refinement
- Input: Pass 1 output + raw records
- Task: Apply discovered patterns, resolve flagged ambiguities
- Output: Refined consolidations

### Optional Pass 3: Verification
- Input: Pass 2 output
- Task: Cross-check for consistency, final confidence assignment
- Output: Final consolidations

## State Between Passes

```json
{
  "discovered_patterns": {
    "3/505": {"interpretation": "bn=3,reg=505", "occurrences": 12}
  },
  "draft_consolidations": [...],
  "flagged_ambiguities": [...],
  "confidence_adjustments": [...]
}
```

## Key Design Questions (Open)

- [ ] How many passes optimal?
- [ ] Convergence criteria (when to stop)?
- [ ] State representation between passes?
- [ ] Cost vs accuracy tradeoff?

## Tradeoffs

**Advantages:**
- Self-improving within batch
- Can handle complex patterns discovered on first pass
- No external preprocessing

**Disadvantages:**
- 2-3x API cost (multiple passes)
- More complex orchestration
- Potential for drift across passes

## Implementation Status

| Component | Status | Location |
|-----------|--------|----------|
| Multi-Pass Orchestrator | Not started | `src/strategies/multi_pass/` |

## References

- Architecture: `docs/architecture/CURRENT.md`
- Comparison: `docs/components/strategies/_comparison/CURRENT.md`
