# Architecture

**Last Updated:** 2026-01-26
**Version:** 2.0

<!--
This is the canonical architecture document.
When updating, snapshot previous version to iterations/ first.
-->

## Overview

Consolidate fragmented historical military records into coherent soldier unit assignments using LLM-based strategies. The core challenge is **state resolution**: discovering how many posts a soldier held, grouping records by state, and resolving each state to a component path.

## Current Status

| Component | Status | Notes |
|-----------|--------|-------|
| Synthetic Data | ✓ Implemented | Terraform Combine domain + difficulty model; artifacts pending regeneration |
| Preprocessing | Update needed | Regex + adapter need v4.1 schema updates |
| **Harness Foundation** | ✓ Complete | Strategy-agnostic framework |
| ↳ Base Strategy Interface | ✓ Complete | Plugin architecture |
| ↳ Train/Test Splitter | ✓ Complete | Stratified splitting |
| ↳ Batching Manager | ✓ Complete | Component-based grouping |
| ↳ Evaluation Framework | ✓ Complete | Metrics + cost tracking |
| ↳ LLM Infrastructure | ✓ Complete | Multi-provider (Gemini ready) |
| Resolver Generation | Pending | 7 modules specified |
| Zero-Shot Strategy | Pending | Baseline for comparison |

### In Progress

- **Synthetic data v4.1 artifacts** — generate new datasets and update preprocessing for new fields.

### What's Stable

- Core pipeline structure
- LLM phase interfaces
- Evaluation metrics framework
- Documentation organization
- Difficulty model design

### What's in Flux

- Synthetic artifacts pending regeneration
- Preprocessing updates for v4.1 schema

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
     (v4.1)               ↓                                   ↓
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
                                                        (stratified by difficulty tier)
```

**Data artifacts:**
- `data/synthetic/raw.parquet` — Generated records (v4.1: includes path_completeness, levels_provided, extraction_signals)
- `data/synthetic/validation.parquet` — Ground truth with state_id, collision_severity, difficulty tier + complementarity + structural_resolvability
- `data/synthetic/canonical.parquet` — Preprocessed with extraction columns
- `config/resolvers/*.json` — Per-component resolvers (to be generated)

## Key Decisions

| ADR | Decision |
|-----|----------|
| ADR-001 | Train/test splits are soldier-level disjoint |
| ADR-002 | LLM batching statefulness for resolver generation |
| ADR-003 | Row similarity reduction vs signal loss |
| ADR-005 | Grounded inference: patterns must be observed or marked inferred |
| ADR-006 | Three-layer difficulty model: record quality ≠ resolution difficulty |
| ADR-007 | Domain decontamination: Terraform Combine fictional setting |

See [ADR_INDEX.md](../ADR_INDEX.md) for full list.

## Synthetic Data v4.1

The synthetic data system uses a **fictional domain (Terraform Combine)** to eliminate LLM pretraining contamination. Key features:

- **Explicit states**: Each soldier has 1-3 states with `state_id`
- **Heterogeneous branches**: 4 branches with different hierarchy depths (3-5 levels)
- **Familiarity gradient**: Clerks abbreviate for home unit, spell out foreign units
- **Three-layer difficulty**: Tracks extraction (L1), aggregation (L2), structural (L3)
- **Collision zone tagging**: Posts tagged with collision severity at generation time

See [synthetic_data_generation/CURRENT.md](../components/synthetic_data_generation/CURRENT.md) for details.

## Strategies

| Strategy | Input | Tradeoff | Status |
|----------|-------|----------|--------|
| Zero-Shot | Raw + hierarchy | No prep vs cognitive load | Design |
| Resolver | Raw + hierarchy + heuristics | Requires generation workflow | **Detailed design** |
| Few-Shot | Raw + hierarchy + examples | Learning vs tokens | Outline |
| Multi-Pass | Multiple passes | Self-improving vs cost | Outline |

**Note:** Resolver strategy requires a separate build-time generation workflow that produces resolver artifacts from validation data. See `docs/components/strategies/resolver/CURRENT.md`.

## Data Structures

See `docs/data-structures/CURRENT.md`

## Components

### Implemented
- **Synthetic Data:** `docs/components/synthetic_data_generation/CURRENT.md`
- **Preprocessing:** `docs/components/preprocessing/CURRENT.md`
- **Harness Foundation:** `docs/components/harness/CURRENT.md`
  - Base Strategy Interface: `src/strategies/base_strategy.py`
  - Train/Test Splitter: `src/evaluation/split.py`
  - Batching Manager: `src/batching/batch_manager.py`
  - Evaluation Metrics: `src/evaluation/metrics.py`
  - LLM Infrastructure: `src/utils/llm/`

### Pending
- **Resolver Generation:** `docs/components/strategies/resolver/GENERATION_WORKFLOW.md`
- **Resolver Strategy:** `docs/components/strategies/resolver/CURRENT.md`
- **Zero-Shot Strategy:** `docs/components/strategies/zero-shot/CURRENT.md`
- **Few-Shot Strategy:** `docs/components/strategies/few-shot/CURRENT.md`
- **Difficulty-stratified evaluation:** Metrics need updating to report by difficulty tier

## Next Steps

### Immediate
1. Run v4.1 synthetic generation and export artifacts
2. Update preprocessing for new domain/schema + new fields
3. Update evaluation metrics to report by difficulty tier

### Then (Resolver Strategy)
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
