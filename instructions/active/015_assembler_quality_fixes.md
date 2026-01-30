# 015: Assembler Quality Fixes

**Status:** active
**Created:** 2026-01-29
**Component:** src/strategies/resolver/generator/assembler.py

## Context

The resolver assembler produces JSON that contains quality bugs. Analysis in `.project_history/extracts/raw/2026-01-29_opus_resolver-quality-bugs.md` traced three issues to this file:

1. **Pattern hallucination (Critical)**: LLM-generated patterns may contain terms that contradict the resolver's own exclusion rules. Example: Colonial Administration resolver's `patterns` section contains "Sq | Wg | El" (Squadron/Wing/Element) while `exclusions` correctly says `{"if_contains": "Squadron", "then": "exclude"}`.

2. **Missing `ambiguous_when` clauses (Medium)**: The `DifferentiatorResult` dataclass has an `ambiguous_when` field but the assembler ignores it.

3. **Differentiator schema non-compliance (High)**: The assembler uses legacy `.rules` and `.hierarchy_rules` properties that convert structured signals to free-text strings. The resolver schema expects structured objects with `provenance`, `strength`, `then` action.

## Task

Fix the three assembler bugs to ensure resolver output is self-consistent and schema-compliant.

## Scope

- **Working in:** `src/strategies/resolver/generator/assembler.py`
- **Reference:** `DifferentiatorResult` dataclass in `src/strategies/resolver/generator/llm_phases.py:260-310`
- **Test location:** `tests/strategies/resolver/generator/`
- **Ignore:** `.project_history/`, unrelated components

## Inputs

- `PhaseResults` containing `patterns`, `exclusions`, and `differentiators`
- `DifferentiatorResult` dataclass with structured fields: `positive_signals`, `conflict_signals`, `structural_rules`, `ambiguous_when`

## Outputs

- Resolver JSON where:
  - Patterns do not contain terms from exclusion rules
  - Differentiators include `ambiguous_when` when present
  - Differentiators use structured signal format, not string rules

## Implementation

### Fix 1: Pattern validation against exclusions (Critical)

Add a function to filter patterns against exclusion rules. Call it in `_build_patterns_section`.

```python
def _filter_patterns_against_exclusions(
    patterns: List[Dict],
    exclusion_rules: List[Dict],
) -> List[Dict]:
    """
    Remove patterns that contain terms from exclusion rules.

    This prevents self-contradiction where a resolver's patterns
    contain terms that its exclusion rules reject.
    """
    if not exclusion_rules:
        return patterns

    # Extract exclusion terms
    exclusion_terms = []
    for rule in exclusion_rules:
        if term := rule.get("if_contains"):
            exclusion_terms.append(term.lower())

    if not exclusion_terms:
        return patterns

    filtered = []
    for p in patterns:
        pattern = p.get("pattern", "").lower()
        means = p.get("means", "").lower()

        # Check if pattern or meaning contains any exclusion term
        contains_excluded = any(
            term in pattern or term in means
            for term in exclusion_terms
        )

        if not contains_excluded:
            filtered.append(p)

    return filtered
```

Update `_build_patterns_section` signature to accept `exclusion_rules` and call the filter:

```python
def _build_patterns_section(
    patterns_result,
    tier: TierName,
    exclusion_rules: List[Dict],  # Add parameter
) -> Dict[str, Any]:
    # ... existing logic ...

    # Before formatting, filter against exclusions
    filtered_patterns = _filter_patterns_against_exclusions(
        patterns_result.patterns,
        exclusion_rules,
    )

    return {
        "status": "complete",
        "entries": _format_pattern_entries(filtered_patterns),
    }
```

Update call site in `assemble_resolver`:

```python
"patterns": _build_patterns_section(
    phase_results.patterns,
    tier,
    phase_results.exclusions.structural,  # Pass exclusion rules
),
```

### Fix 2: Propagate `ambiguous_when` (Medium)

In `_build_differentiators_section`, add the `ambiguous_when` field to the output entry when present:

```python
# After line 246 (after handling notes)
if diff_result.ambiguous_when:
    entry["ambiguous_when"] = diff_result.ambiguous_when
```

### Fix 3: Use structured signal fields (High)

Replace the legacy string-based rules with structured fields. In `_build_differentiators_section`, replace:

```python
# OLD (lines 237-240):
all_rules = diff_result.rules + diff_result.hierarchy_rules
if all_rules:
    entry["rules"] = all_rules
```

With:

```python
# NEW: Use structured signal fields
if diff_result.positive_signals:
    entry["positive_signals"] = diff_result.positive_signals

if diff_result.conflict_signals:
    entry["conflict_signals"] = diff_result.conflict_signals

if diff_result.structural_rules:
    entry["structural_rules"] = diff_result.structural_rules
```

## Acceptance Criteria

- [ ] New function `_filter_patterns_against_exclusions` exists and is called during assembly
- [ ] Generated resolvers have no patterns containing terms from their own exclusion rules
- [ ] Differentiator entries include `ambiguous_when` field when the source `DifferentiatorResult` has one
- [ ] Differentiator entries use `positive_signals`, `conflict_signals`, `structural_rules` (structured dicts) instead of `rules` (list of strings)
- [ ] Existing tests pass
- [ ] Add test case for pattern filtering (pattern with exclusion term should be removed)

## Notes

- Follow [CODE_STYLE.md](docs/CODE_STYLE.md): use functions, not classes; no premature abstraction
- The `_filter_patterns_against_exclusions` function is stateless and fits the project's preference for module-level functions
- The legacy `.rules` and `.hierarchy_rules` properties in `DifferentiatorResult` can remain for backward compatibility elsewhere, but the assembler should not use them

## References

- Bug analysis: `.project_history/extracts/raw/2026-01-29_opus_resolver-quality-bugs.md`
- Quality assessment: `landing_zone/resolver_quality_assessment.md`
- `DifferentiatorResult` dataclass: `src/strategies/resolver/generator/llm_phases.py:260-310`
- ADR-005 grounded inference requirements (violated by pattern hallucination)
