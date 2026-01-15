# 2026-01-15 — Architecture, Evaluation Leakage, and Routing

## Summary

Captured high-level concerns about routing-first batching, transfer-aware consolidation,
and validation leakage. Agreed to formalize leakage prevention via an ADR and integrate
the policy into evaluation and resolver documentation.

## Concerns Logged

- Component-first batching can hide transfer evidence across components.
- Ambiguous routing lacks a defined fallback path.
- Consolidation output schema for transfers/confidence is undefined.
- Synthetic grounding risks drift without a feedback/refresh plan.
- Strategy comparison needs a consistent evaluation protocol.

## Decisions

- Adopt a validation leakage policy via ADR-001:
  - Soldier-level train/test split; no overlap by `soldier_id` or `source_id`.
  - Resolver generation reads train artifacts only.
  - Evaluation fails on leakage check failure.
  - Optional holdout for generalization.

## Follow-ups

- Update evaluation doc with leakage policy and required checks.
- Update resolver strategy doc to reference ADR-001 and enforce soldier-level splits.
