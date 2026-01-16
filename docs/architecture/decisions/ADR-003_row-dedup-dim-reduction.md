# ADR-003: Dimensional Reduction for Similar Soldier Rows

**Date:** 2026-01-15  
**Status:** proposed  
**Scope:** architecture

## Context

Real-world records may contain many substantially similar rows per soldier (e.g., repeated entries or near-duplicates), which can inflate token usage for LLM processing. The synthetic dataset does not exhibit this issue, but production data likely will. We need to decide whether to apply dimensional reduction or deduplication for near-duplicate rows, or preserve all rows to avoid losing subtle signals.

## Options Considered

### Option A: No reduction (preserve all rows)

- Pro: Maximum fidelity; no risk of discarding rare but important signals
- Con: Higher token cost and latency; potential context overflow

### Option B: Exact deduplication

Remove exact duplicate rows per soldier (or per normalized raw text).

- Pro: Low risk, straightforward implementation
- Con: Does not address near-duplicates; limited savings

### Option C: Near-duplicate reduction (clustering / similarity threshold)

Cluster highly similar rows and keep a representative subset with counts/metadata.

- Pro: Significant token reduction; retains summary of repetition
- Con: Risk of attenuating subtle signals; added complexity

## Decision

Pending. We need to determine if dimensional reduction is acceptable for real data and how to encode any lost detail (e.g., counts, representative selection) without harming resolver quality.

## Consequences

**Easier:**
- Lower LLM token usage and faster inference (if reduction adopted)

**Harder:**
- Validation of impact on model accuracy
- Designing safe similarity thresholds and metadata retention

**New constraints:**
- Must be configurable per strategy and dataset
- Should not distort training/validation splits

## References

- Related ADRs: `ADR-001_validation-leakage-policy.md`
