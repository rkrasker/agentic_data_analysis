# Evaluation

**Status:** Not yet implemented  
**Last Updated:** YYYY-MM-DD

## Purpose

Measure strategy performance against ground truth validation data. Enable objective comparison across strategies.

## Responsibilities

- Accuracy metrics (vs validation holdout)
- Confidence calibration analysis
- Strategy comparison
- Error categorization
 - Leakage enforcement per ADR-001

## Dependencies

- **Upstream:** Strategy execution (consolidated results)
- **Reference:** Validation data (ground truth)
 - **Policy:** `docs/architecture/decisions/ADR-001_validation-leakage-policy.md`

## Metrics

### Primary
- **Consolidation accuracy:** % correct vs validation.parquet
  - By unit level (division/regiment/battalion/company)
  - By component type

### Secondary
- **Pattern interpretation accuracy:** Correct resolution of ambiguous patterns
- **Transfer detection accuracy:** Correctly identifies unit changes
- **Confidence calibration:** High confidence = actually correct?
- **Token efficiency:** Cost per soldier

## Data Splits and Leakage Policy

Evaluation must comply with ADR-001:
- Train/test splits are soldier-level and disjoint by `soldier_id`.
- No `source_id` overlap between splits.
- Evaluation fails if leakage checks do not pass.
- Optional holdout split reserved for generalization tests.

## Key Design Questions (Open)

- [ ] Holdout strategy (fixed vs rolling)?
- [ ] How to weight accuracy by unit level?
- [ ] Error taxonomy?

## Implementation Status

| Component | Status | Location |
|-----------|--------|----------|
| Metrics Calculator | Not started | `src/evaluation/metrics.py` |

## References

- Architecture: `docs/architecture/CURRENT.md`
