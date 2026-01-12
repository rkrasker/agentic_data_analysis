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

## Dependencies

- **Upstream:** Strategy execution (consolidated results)
- **Reference:** Validation data (ground truth)

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
