# Architecture

**Last Updated:** 2026-01-14
**Version:** 1.1

<!--
This is the canonical architecture document.
When updating, snapshot previous version to iterations/ first.
-->

## Overview

Consolidate fragmented historical military records into coherent soldier unit assignments using LLM-based strategies.

## Current Status

| Component | Status | Notes |
|-----------|--------|-------|
| Synthetic Data | ✓ Complete | 10K records, v3 clerk-as-character |
| Preprocessing | ✓ Partial | Regex + adapter done, routing pending |
| Batching | Not started | — |
| Strategies | Not started | — |
| Evaluation | Not started | — |

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
                         ✓ IMPLEMENTED
                              ↓
Synthetic Generator → raw.parquet → [Regex Preprocessing] → canonical.parquet
                                            ↓
                                    [Component-Based Batching] ← pending
                                            ↓
                                    [Strategy Execution] ← pending
                                            ↓
                                    [Evaluation vs Validation] ← pending
```

**Data artifacts:**
- `data/synthetic/raw.parquet` — 10K generated records
- `data/synthetic/validation.parquet` — ground truth
- `data/synthetic/canonical.parquet` — preprocessed with 25 extraction columns

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

- Synthetic Data: `docs/components/synthetic_data_generation/CURRENT.md`
- Preprocessing: `docs/components/preprocessing/CURRENT.md`
- Batching: `docs/components/batching/CURRENT.md`
- Consolidation: `docs/components/consolidation/CURRENT.md`
- Evaluation: `docs/components/evaluation/CURRENT.md`
- Strategies: `docs/components/strategies/*/CURRENT.md`

## Next Steps

1. **Component Routing** — use extraction signals to route records to components
2. **Batching** — group records for efficient LLM processing
3. **Zero-Shot Strategy** — baseline consolidation approach
