# Resolver Generation Quality Bugs Analysis

**Date:** 2026-01-29
**Session:** Claude Opus — Resolver troubleshooting from quality assessment
**Trigger:** First resolver generated (`colonial_administration_resolver.json`) had multiple errors

---

## Summary

Ran resolver generation via `resolver_generation.ipynb` for colonial_administration. The output had four categories of bugs documented in `landing_zone/resolver_quality_assessment.md`. This session traced each to root cause.

---

## Issue 1: Tier Classification Bug

**Symptom:** `tier: "sparse"` despite `pct_of_median: 97.0`

**Root Cause:** Percentile-based tier system fails with N=4 components. With only 4 components, quantile math guarantees exactly 1 component per tier regardless of how close counts are. Tier is assigned by **rank**, not semantic meaning.

**Location:** `src/strategies/resolver/generator/thresholds.py:92-102`

**Fix:** Add guard to prevent "sparse" when pct_of_median >= 75%:
```python
elif count >= p25 or pct >= 75:  # Don't mark as sparse if close to median
    tier = "under_represented"
```

**Impact:** Cascade effect — wrong tier triggers `generation_mode: "hierarchy_only"`, incorrectly limits pattern/vocabulary discovery.

---

## Issue 2: LLM Pattern Hallucination (Critical)

**Symptom:** Defense Command terms ("Sq | Wg | El" = Squadron/Wing/Element) appear in Colonial Administration resolver patterns.

**Root Cause (2 parts):**
1. LLM generates patterns from training knowledge instead of grounding in provided records
2. No cross-validation: patterns aren't checked against resolver's own exclusion rules

**Irony:** The `exclusions` section correctly says `{"if_contains": "Squadron", "then": "exclude"}`, yet `patterns` section includes "Sq | Wg | El". Resolver contradicts itself.

**Location:**
- `src/strategies/resolver/generator/assembler.py:124-143` (no validation)
- `src/strategies/resolver/generator/llm_phases.py:474` (incorrect status)

**Fix:** Add `_filter_patterns_against_exclusions()` in assembler.py that rejects patterns containing terms from the exclusion rules.

**Secondary issue:** `generation_mode: "hierarchy_only"` but `patterns.status: "complete"` — contradictory. Should be `"not_generated"` for hierarchy_only mode.

---

## Issue 3: Missing `ambiguous_when` Clauses

**Symptom:** Differentiators lack guidance for genuinely ambiguous cases (e.g., "Horizon" without level prefix).

**Root Cause:** `_build_differentiators_section()` in assembler.py ignores `ambiguous_when` field from `DifferentiatorResult`. Field exists in dataclass but never propagates to output.

**Location:** `src/strategies/resolver/generator/assembler.py:226-248`

**Fix:** Add to output:
```python
if diff_result.ambiguous_when:
    entry["ambiguous_when"] = diff_result.ambiguous_when
```

---

## Issue 4: Differentiator Schema Non-Compliance

**Symptom:** Rules are free-text strings instead of structured objects with `provenance`, `strength`, `then` action.

**Root Cause:** Assembler uses legacy properties (`.rules`, `.hierarchy_rules`) that convert structured signals to strings, instead of outputting structured fields.

**Location:** `src/strategies/resolver/generator/assembler.py:237-240`

**Fix:** Replace legacy properties with structured fields:
```python
# Instead of:
entry["rules"] = diff_result.rules + diff_result.hierarchy_rules

# Use:
entry["positive_signals"] = diff_result.positive_signals
entry["conflict_signals"] = diff_result.conflict_signals
entry["structural_rules"] = diff_result.structural_rules
```

---

## Files Analyzed

| File | Purpose |
|------|---------|
| `config/resolvers/colonial_administration_resolver.json` | Generated resolver with bugs |
| `landing_zone/resolver_quality_assessment.md` | Manual quality assessment |
| `src/strategies/resolver/generator/thresholds.py` | Tier calculation |
| `src/strategies/resolver/generator/assembler.py` | Resolver JSON assembly |
| `src/strategies/resolver/generator/llm_phases.py` | LLM orchestration |
| `src/strategies/resolver/generator/prompts.py` | LLM prompts |
| `src/strategies/resolver/generator/generate.py` | Main orchestrator |

---

## Priority Order for Fixes

1. **Issue 2 (Critical)** — Pattern hallucination produces incorrect resolvers
2. **Issue 1 (High)** — Tier bug cascades to wrong generation mode
3. **Issue 4 (High)** — Schema non-compliance breaks downstream consumers
4. **Issue 3 (Medium)** — Missing ambiguity guidance

---

## Next Steps

1. Create instruction file for assembler.py fixes (Issues 2, 3, 4)
2. Create instruction file for thresholds.py fix (Issue 1)
3. Regenerate resolvers after fixes
4. Add validation tests to prevent regression

---

## References

- `landing_zone/resolver_quality_assessment.md` — Original bug report
- `docs/architecture/CURRENT.md` — Resolver schema spec
- ADR-005 — Grounded inference requirements (violated by Issue 2)
