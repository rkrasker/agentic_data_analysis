# Strategy Comparison

**Status:** Not yet implemented  
**Last Updated:** YYYY-MM-DD

## Purpose

Cross-strategy analysis, tradeoffs, and head-to-head results.

## Strategies Under Comparison

| Strategy | Status | Unique Characteristic |
|----------|--------|----------------------|
| Zero-Shot | Design phase | No pre-learning; pure instruction |
| Resolver | Design phase | Pre-learned heuristics from validation |
| Few-Shot | Not started | Learning by example |
| Multi-Pass | Not started | Iterative refinement |

## Comparison Dimensions

- **Accuracy:** Raw performance vs validation
- **Token cost:** Tokens per soldier
- **Latency:** Time per batch
- **Robustness:** Performance on edge cases
- **Setup cost:** One-time preparation required

## Results

<!-- Populate as experiments run -->

| Strategy | Accuracy | Tokens/Soldier | Setup Cost |
|----------|----------|----------------|------------|
| Zero-Shot | TBD | TBD | None |
| Resolver | TBD | TBD | Generation workflow |
| Few-Shot | TBD | TBD | Example curation |
| Multi-Pass | TBD | TBD | None |

## Open Questions

- [ ] Fair comparison methodology?
- [ ] How to account for setup cost in comparison?

## References

- Individual strategies: `docs/components/strategies/[name]/CURRENT.md`
