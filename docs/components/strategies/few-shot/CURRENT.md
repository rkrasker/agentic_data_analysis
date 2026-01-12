# Few-Shot Strategy

**Status:** Not yet implemented  
**Last Updated:** YYYY-MM-DD

## Purpose

Consolidation using raw text + hierarchy + solved examples. LLM learns patterns by seeing worked examples.

## What LLM Receives

- Raw text records for batch of soldiers
- Component hierarchy document
- Few-shot examples (record sets → correct consolidations)
- Consolidation instructions

## Example Format

```
EXAMPLE 1:
Records:
  - "Mitchell 3/505 charlie"
  - "R Mitchell 505th PIR 3rd bn"
  - "Mitchell C co"

Consolidation:
  regiment: 505
  battalion: 3
  company: C
  confidence: high
  evidence: "Regiment 505 explicit in 2 records; 3/505 pattern matches; charlie = C"

EXAMPLE 2:
...
```

## Key Design Questions (Open)

- [ ] How many examples per batch?
- [ ] Example selection strategy (representative vs edge cases)?
- [ ] Token cost vs accuracy tradeoff?
- [ ] Component-specific vs generic examples?

## Tradeoffs

**Advantages:**
- Learning by example (intuitive)
- Can show edge cases explicitly
- No complex generation workflow

**Disadvantages:**
- Token-heavy (each example consumes budget)
- Example quality critical
- May overfit to example patterns

## Implementation Status

| Component | Status | Location |
|-----------|--------|----------|
| Example Selector | Not started | `src/strategies/few_shot/` |
| Few-Shot Executor | Not started | `src/strategies/few_shot/` |

## References

- Architecture: `docs/architecture/CURRENT.md`
- Comparison: `docs/components/strategies/_comparison/CURRENT.md`
