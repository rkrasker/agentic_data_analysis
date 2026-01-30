# SESSION_STATE.md

**Last Updated:** 2026-01-29
**Session:** Claude Opus — Resolver Quality Bug Analysis

---

## Active Task

Resolver generation produces buggy output. Four issues traced to root cause; fixes identified but not yet implemented.

---

## Current Problem

First resolver generated (`colonial_administration_resolver.json`) has critical errors:

| Issue | Severity | Root Cause Location |
|-------|----------|---------------------|
| Tier "sparse" despite 97% of median | High | `thresholds.py:92-102` |
| DC patterns in CA resolver (hallucination) | **Critical** | `assembler.py:124-143` |
| Missing `ambiguous_when` clauses | Medium | `assembler.py:226-248` |
| Differentiator schema non-compliance | High | `assembler.py:237-240` |

**Key insight:** Issue 2 is critical — the LLM hallucinates patterns from training knowledge, and the assembler has no validation against the resolver's own exclusion rules. The resolver literally contradicts itself.

---

## Where I Left Off

Instruction files created for all four fixes:

- [instructions/active/015_assembler_quality_fixes.md](instructions/active/015_assembler_quality_fixes.md) — Issues 2, 3, 4 (pattern validation, ambiguous_when, structured schema)
- [instructions/active/016_tier_classification_guard.md](instructions/active/016_tier_classification_guard.md) — Issue 1 (tier classification guard)

**Next concrete step:** Implement fixes following the instruction files, starting with 015 (critical pattern hallucination fix).

---

## Fixes Needed

### 1. thresholds.py — Tier classification guard
Add `or pct >= 75` to prevent "sparse" classification when close to median.

### 2. assembler.py — Pattern validation (CRITICAL)
Add `_filter_patterns_against_exclusions()` to reject patterns containing terms from exclusion rules.

### 3. assembler.py — Propagate ambiguous_when
Add `entry["ambiguous_when"] = diff_result.ambiguous_when` to differentiator output.

### 4. assembler.py — Use structured fields
Replace legacy `.rules`/`.hierarchy_rules` string properties with structured `positive_signals`, `conflict_signals`, `structural_rules`.

---

## Open Questions

1. **Should we add integration tests?** Resolver self-consistency (patterns don't contain exclusion terms) should be validated.
2. **Prompt improvements?** LLM still hallucinates despite GROUNDING_PRINCIPLES in prompts. Consider structured output enforcement.

---

## Artifacts This Session

| Artifact | Location | Status |
|----------|----------|--------|
| Quality assessment | `landing_zone/resolver_quality_assessment.md` | Reference |
| Bug analysis extract | `.project_history/extracts/raw/2026-01-29_opus_resolver-quality-bugs.md` | Complete |
| Buggy resolver | `config/resolvers/colonial_administration_resolver.json` | Do not use |
| Instruction: assembler fixes | `instructions/active/015_assembler_quality_fixes.md` | Ready |
| Instruction: tier guard | `instructions/active/016_tier_classification_guard.md` | Ready |

---

## References

- `landing_zone/resolver_quality_assessment.md` — Original bug documentation
- `.project_history/extracts/raw/2026-01-29_opus_resolver-quality-bugs.md` — This session's analysis
- ADR-005 — Grounded inference (violated by pattern hallucination)
