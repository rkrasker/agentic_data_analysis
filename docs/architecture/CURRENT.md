# Architecture

**Last Updated:** YYYY-MM-DD  
**Version:** X.Y

<!-- 
This is the canonical architecture document. 
When updating, snapshot previous version to iterations/ first.
-->

## Overview

Consolidate fragmented historical military records into coherent soldier unit assignments using LLM-based strategies.

## Core Problem

**Cross-row synthesis:** Interpreting ambiguous notations by cross-referencing other records for the same soldier, then aggregating across all records.

Not an extraction problem — regex handles extraction. The LLM must:
- Aggregate evidence across records
- Interpret ambiguous patterns in context
- Detect transfers vs errors vs missing data
- Resolve contradictions
- Assign confidence

## Pipeline Flow

```
Raw Records → [Regex Preprocessing] → canonical.parquet (routing only)
                                            ↓
                                    [Component-Based Batching]
                                            ↓
                                    [Strategy Execution]
                                            ↓
                                    [Evaluation vs Validation]
```

## Key Decisions

<!-- Reference ADRs for details -->

1. Raw text is primary LLM input (ADR-XXX)
2. Component-based batching for efficiency (ADR-XXX)
3. Strategy plugin architecture (ADR-XXX)
4. Proportional confidence tiers (ADR-XXX)
5. Conservative exclusions — presence only (ADR-XXX)

## Strategies

| Strategy | Input | Tradeoff |
|----------|-------|----------|
| Zero-Shot | Raw + hierarchy | No prep vs cognitive load |
| Resolver | Raw + hierarchy + heuristics | Requires generation |
| Few-Shot | Raw + hierarchy + examples | Learning vs tokens |
| Multi-Pass | Multiple passes | Self-improving vs cost |

## Data Structures

See `docs/data-structures/CURRENT.md`

## Components

- Preprocessing: `docs/components/preprocessing/CURRENT.md`
- Batching: `docs/components/batching/CURRENT.md`
- Consolidation: `docs/components/consolidation/CURRENT.md`
- Evaluation: `docs/components/evaluation/CURRENT.md`
- Strategies: `docs/components/strategies/*/CURRENT.md`

## Open Questions

- [ ] [Open question 1]
- [ ] [Open question 2]
