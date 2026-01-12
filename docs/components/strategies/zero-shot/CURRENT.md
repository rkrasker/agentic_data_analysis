# Zero-Shot Strategy

**Status:** Not yet implemented  
**Last Updated:** YYYY-MM-DD

## Purpose

Consolidation using raw text + hierarchy only. No pre-learned heuristics — LLM must discover patterns during parsing.

## What LLM Receives

- Raw text records for batch of soldiers
- Component hierarchy document
- Consolidation instructions

## What LLM Must Do

- Parse raw text (no pre-extraction hints)
- Discover notation patterns (e.g., "3/505" meaning)
- Learn vocabulary signals during processing
- Cross-reference records per soldier
- Produce consolidated assignments

## Tradeoffs

**Advantages:**
- No preprocessing workflow
- No strategy-specific artifacts to maintain
- Tests LLM's raw capability

**Disadvantages:**
- Higher cognitive load per batch
- May miss subtle patterns
- Potentially lower accuracy

## Key Design Questions (Open)

- [ ] Prompt structure?
- [ ] How much hierarchy detail to include?
- [ ] Batch size constraints?

## Implementation Status

| Component | Status | Location |
|-----------|--------|----------|
| Zero-Shot Executor | Not started | `src/strategies/zero_shot/` |

## References

- Architecture: `docs/architecture/CURRENT.md`
- Comparison: `docs/components/strategies/_comparison/CURRENT.md`
