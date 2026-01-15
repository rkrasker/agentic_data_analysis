# ADR-001: Validation Data Leakage Policy

**Date:** 2026-01-15  
**Status:** proposed  
**Scope:** architecture

## Context

Resolver generation consumes validation data, and evaluation also relies on validation.
Without explicit split rules and enforcement, there is a high risk of leakage via shared
soldier identities or shared raw records, which would inflate performance and bias
strategy comparisons.

## Options Considered

### Option A: Ad-hoc splits without enforcement

Continue with informal train/test splitting and rely on manual care.

- Pro: Low implementation overhead.
- Con: High leakage risk and inconsistent evaluation integrity.

### Option B: Soldier-level split with enforced artifacts and audits

Define a strict leakage policy: split by soldier identity, persist split artifacts, and
add automated overlap checks before resolver generation and evaluation. Optionally
reserve a final holdout for generalization checks.

- Pro: Strong protection against leakage and reproducible evaluation.
- Con: Requires additional artifacts and validation steps in the workflow.

## Decision

Adopt Option B. All resolver generation uses a soldier-level training split, with
explicit artifacts and automated leakage audits. Evaluation only uses test (and
optional holdout) splits that are disjoint by soldier_id and source_id.

## Consequences

**Easier:**
- Reproducible, defensible evaluation results.
- Clear provenance for resolver artifacts and comparisons.

**Harder:**
- Additional workflow steps for split creation and validation.
- Slightly more complex data management.

**New constraints:**
- No soldier_id or source_id may appear in both train and test (or holdout).
- Resolver generation must only read training artifacts.
- Evaluation must fail if leakage checks do not pass.

## References

- Related extracts: `.project_history/extracts/daily/2026-01-15_architecture-evaluation-leakage-and-routing.md`
- Related ADRs: `ADR-000_template.md`
- Related threads: Codex session, 2026-01-15
