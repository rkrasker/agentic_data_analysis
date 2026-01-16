# Daily Reconciliation: Dual-Run Architecture (2026-01-16)

## Summary

Formal decision for ADR-002: Dual-Run Stateful with Hard Case Reconciliation. Full implementation of the workflow including token batching, dual-run orchestration, reconciliation, and integration into the main generator.

## Design Decision

**Problem:** Resolver generation needs contextual disambiguation (interpreting one record in light of another), but stateful extraction risks drift from ordering effects.

**Solution:** Run extraction twice (forward + inverted order), have LLM flag "hard cases" during each pass, then reconcile results using hard cases as the validation corpus.

## Architecture

```
Run 1 (Forward):  Batch A → B → C  (stateful, accumulating context)
Run 2 (Inverted): Batch C → B → A  (fresh accumulator)

Reconciliation:
- Patterns in both runs → robust
- Patterns in one run only → order-dependent (flagged)
- Hard cases flagged by both → genuinely difficult
- Hard cases flagged by one → ordering "helped" disambiguation
```

## Pattern Classification

| Category | Criteria | Confidence |
|----------|----------|------------|
| Robust | Found in both runs | High |
| Validated | Robust + passed hard case test | Highest |
| Order-dependent | Found in one run only | Lower (flagged) |
| Rejected | Failed hard case validation | Excluded |

## Hard Case Flagging Criteria

Flag soldier as hard case if:
- Multiple component indicators present (conflicting signals)
- Key identifiers missing or ambiguous
- Unusual notation not matching known patterns
- Assignment uncertain despite having records
- Transfer indicators present

## Implementation Completed

| Component | File |
|-----------|------|
| Token Batcher | `src/utils/llm/token_batcher.py` |
| Retry Logic | `src/utils/llm/base.py` (RetryConfig) |
| Dual-Run Orchestrator | `src/strategies/resolver/generator/dual_run.py` |
| Reconciliation | `src/strategies/resolver/generator/reconciliation.py` |
| Hard Case Prompts | `src/strategies/resolver/generator/prompts.py` |
| Main Integration | `src/strategies/resolver/generator/generate.py` |

## CLI Usage

```bash
# Default: dual-run with 8K token budget
python -m src.strategies.resolver.generator.generate

# Disable dual-run (legacy single-pass)
python -m src.strategies.resolver.generator.generate --no-dual-run

# Custom token budget
python -m src.strategies.resolver.generator.generate --token-budget 12000
```

## Open Items

- `llm_phases.py` could be updated to use token batching + return hard cases
- Vocabulary and differentiator phases could be extended to use dual-run
- Both noted as "Needs update" in docs but not blocking
