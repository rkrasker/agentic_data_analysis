# ADR Index

Quick reference to Architecture Decision Records.

| ADR | Topic | Key Insight | Location |
|-----|-------|-------------|----------|
| ADR-001 | Validation leakage policy | Train/test splits are soldier-level disjoint | `docs/architecture/decisions/ADR-001_validation-leakage-policy.md` |
| ADR-002 | Dual-run stateful extraction | Hard cases detected via forward/reverse batch comparison | `docs/architecture/decisions/ADR-002_llm-batching-statefulness.md` |
| ADR-004 | Few-shot corpus from resolver | Hard cases become training examples | `docs/architecture/decisions/ADR-004_few-shot-corpus-from-resolver.md` |
| ADR-005 | Grounded inference | Patterns must be observed or marked inferred; no absence-based rules | `docs/architecture/decisions/ADR-005_grounded-inference-provenance.md` |
| ADR-006 | Three-layer difficulty model | Record quality ≠ resolution difficulty; extraction, aggregation, structural layers | `docs/architecture/decisions/ADR-006_per-record-vs-per-soldier-difficulty.md` |
| ADR-007 | Synthetic data redesign | Domain decontamination via Terraform Combine; explicit states | `docs/architecture/decisions/ADR-007-synthetic-data-redesign.md` |

## When to Reference ADRs

- **Before changing** a system that an ADR governs — understand the decision first
- **When confused** about why something works a certain way — ADR may explain
- **When proposing changes** that might conflict with an ADR — surface the conflict explicitly
