# Architecture

**Last Updated:** 2026-01-15
**Version:** 1.2

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
| Preprocessing | ✓ Complete | Regex + adapter + glossary |
| **Harness Foundation** | ✓ Complete | Strategy-agnostic framework |
| ↳ Base Strategy Interface | ✓ Complete | Plugin architecture |
| ↳ Train/Test Splitter | ✓ Complete | Stratified splitting |
| ↳ Batching Manager | ✓ Complete | Component-based grouping |
| ↳ Evaluation Framework | ✓ Complete | Metrics + cost tracking |
| ↳ LLM Infrastructure | ✓ Complete | Multi-provider (Gemini ready) |
| Resolver Generation | Pending | 7 modules specified |
| Zero-Shot Strategy | Pending | Baseline for comparison |

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
                         ✓ IMPLEMENTED                    ✓ IMPLEMENTED
                              ↓                                ↓
Synthetic Generator → raw.parquet → [Regex Preprocessing] → canonical.parquet
                           ↓                                   ↓
                    validation.parquet              [Train/Test Splitter] ✓
                                                      ↓              ↓
                                                  train_df      test_df
                                                      ↓              ↓
                                          [Resolver Generation]  [Batching Manager] ✓
                                                  (pending)         ↓
                                                      ↓         SoldierBatch
                                               resolvers.json      ↓
                                                      └───→ [Strategy.consolidate()] ← pending
                                                                ↓
                                                       ConsolidationResult
                                                                ↓
                                                      [Evaluation Metrics] ✓
                                                                ↓
                                                       EvaluationMetrics
```

**Data artifacts:**
- `data/synthetic/raw.parquet` — 10K generated records
- `data/synthetic/validation.parquet` — ground truth (3,174 soldiers)
- `data/synthetic/canonical.parquet` — preprocessed with 25 extraction columns
- `config/resolvers/*.json` — per-component resolvers (to be generated)

## Key Decisions

<!-- Reference ADRs for details -->

1. Raw text is primary LLM input (ADR-XXX)
2. Component-based batching for efficiency (ADR-XXX)
3. LLM batching statefulness for resolver generation (ADR-002)
4. Row similarity reduction vs signal loss (ADR-003)
5. Strategy plugin architecture (ADR-XXX)
6. Proportional confidence tiers (ADR-XXX)
7. Conservative exclusions — presence only (ADR-XXX)

## Strategies

| Strategy | Input | Tradeoff | Status |
|----------|-------|----------|--------|
| Zero-Shot | Raw + hierarchy | No prep vs cognitive load | Design |
| Resolver | Raw + hierarchy + heuristics | Requires generation workflow | **Detailed design** |
| Few-Shot | Raw + hierarchy + examples | Learning vs tokens | Outline |
| Multi-Pass | Multiple passes | Self-improving vs cost | Outline |

**Note:** Resolver strategy requires a separate build-time generation workflow that produces resolver artifacts from validation data. This is NOT a parallel routing pipeline — see `docs/components/strategies/resolver/CURRENT.md` for details.

## Data Structures

See `docs/data-structures/CURRENT.md`

## Components

### Implemented
- **Synthetic Data:** `docs/components/synthetic_data_generation/CURRENT.md`
- **Preprocessing:** `docs/components/preprocessing/CURRENT.md`
- **Harness Foundation:** `docs/components/harness/CURRENT.md` ✨ NEW
  - Base Strategy Interface: `src/strategies/base_strategy.py`
  - Train/Test Splitter: `src/evaluation/split.py`
  - Batching Manager: `src/batching/batch_manager.py`
  - Evaluation Metrics: `src/evaluation/metrics.py`
  - LLM Infrastructure: `src/utils/llm/`

### Pending
- **Resolver Generation:** `docs/components/strategies/resolver/GENERATION_WORKFLOW.md` ✨ NEW
- **Resolver Strategy:** `docs/components/strategies/resolver/CURRENT.md`
- **Zero-Shot Strategy:** `docs/components/strategies/zero-shot/CURRENT.md`
- **Few-Shot Strategy:** `docs/components/strategies/few-shot/CURRENT.md`

## Next Steps

### Immediate (Resolver Strategy)
1. **Module 1-3: Non-LLM components**
   - Threshold Calculator
   - Structure Extractor
   - Collision Sampler
   - Registry Manager

2. **Module 4: LLM Phases**
   - Pattern Discovery (Phase 4)
   - Exclusion Mining (Phase 5)
   - Vocabulary Discovery (Phase 6)
   - Differentiator Generation (Phase 7)
   - Tier Assignment (Phase 8)

3. **Module 5-7: Integration**
   - Resolver Assembler
   - Main Orchestrator
   - Resolver Executor (consolidation-time)

### Future
4. **Zero-Shot Strategy** — baseline for comparison
5. **Strategy Comparison** — test all strategies on same holdout
