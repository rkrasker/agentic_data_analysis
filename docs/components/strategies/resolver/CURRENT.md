# Resolver Strategy

**Status:** Design phase  
**Last Updated:** YYYY-MM-DD

## Purpose

Consolidation using raw text + hierarchy + pre-learned heuristics (resolvers). Resolvers are generated from validation data to guide LLM parsing.

## What LLM Receives

- Raw text records for batch of soldiers
- Component hierarchy document
- Resolver (pre-learned heuristics for this component)
- Consolidation instructions

## What a Resolver Contains

```json
{
  "component_id": "82nd_airborne_division",
  "structure": {
    "valid_regiments": [325, 504, 505, 507, 508],
    "valid_battalions": [1, 2, 3],
    "valid_companies": ["A", "B", "C", "D", "E", "F", "G", "H", "I"]
  },
  "patterns": {
    "3/505": {"means": "bn=3,reg=505", "tier": "strong"}
  },
  "vocabulary": {
    "strong": ["505th PIR", "all american"],
    "moderate": ["chute", "para"]
  },
  "exclusions": {
    "value_based": ["regiment in [501,502,506] → excludes 82nd"],
    "structural": ["squadron mention → excludes 82nd"]
  },
  "differentiators": {
    "vs_101st": ["regiment numbers distinguish"]
  }
}
```

## Resolver Generation Workflow (8 Phases)

1. **Extract Structural Rules** — From hierarchy document
2. **Collision Detection** — Find overlapping features with rivals
3. **Collision-Based Sampling** — Head-to-head examples
4. **Pattern Discovery** — LLM analyzes validation data
5. **Exclusion Mining** — Incompatible-presence rules
6. **Vocabulary Discovery** — Characteristic terms
7. **Differentiator Generation** — Rules to distinguish rivals
8. **Tier Assignment** — Proportional confidence levels

## Key Principles

- **Cross-record context:** Pattern interpretation uses ALL records for soldier
- **Proportional tiers:** Confidence based on proportion of sample, not absolute counts
- **Vocabulary as tiebreaker:** One tier nudge max, never primary evidence
- **Conservative exclusions:** Only incompatible PRESENCE excludes, never absence

## Tradeoffs

**Advantages:**
- Focused guidance for LLM
- Pre-learned pattern interpretations
- Explicit disambiguation rules

**Disadvantages:**
- Requires generation workflow
- Resolvers must be regenerated if validation data changes
- More complex system

## Key Design Questions (Open)

- [ ] Resolver token budget (~500-600)?
- [ ] Generation workflow automation level?
- [ ] Resolver versioning strategy?

## Implementation Status

| Component | Status | Location |
|-----------|--------|----------|
| Resolver Generator | Not started | `src/strategies/resolver/generator/` |
| Resolver Executor | Not started | `src/strategies/resolver/executor/` |

## References

- Architecture: `docs/architecture/CURRENT.md`
- Comparison: `docs/components/strategies/_comparison/CURRENT.md`
