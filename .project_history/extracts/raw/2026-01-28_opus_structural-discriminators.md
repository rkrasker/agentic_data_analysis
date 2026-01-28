# Session Extract: Structural Discriminators Extraction

**Date:** 2026-01-28
**Session Type:** Opus 4.5 strategy session
**Topic:** Identifying and scoping the structural discriminators utility as a shared dependency

---

## Context

Previous session completed the difficulty model design (DIFFICULTY_MODEL.md) with complementarity formula, confidence weights, and tier thresholds. Implementation of `compute_soldier_difficulty()` was identified as next step, but open question #3 remained: "How to automatically identify which terms are unique to which branch?"

This session resolved that question by recognizing it as already-scoped work.

---

## Key Insight: Shared Dependency

The "structural discriminator extraction" problem appears in two places:

1. **Difficulty Model** — needs to answer "do this soldier's extractions eliminate all but one candidate branch?" (structural resolvability boolean)

2. **Resolver Phase 5** — ADR-009 specifies that exclusion mining becomes deterministic derivation from hierarchy, not LLM mining

Both consumers need the same underlying data:
- Which level names are unique to which branches
- Which designator values are unique to which branches
- Which depth values are unique
- What exclusion rules can be derived from these facts

**Decision:** Build this once as a shared utility that produces a reference artifact consumed by both systems.

---

## Architecture Decision: Output Location

**Decision:** Output sits alongside its input at `config/hierarchies/structural_discriminators.json`

**Rationale:**
- Derived deterministically from hierarchy_reference.json
- Should be regenerated whenever hierarchy_reference.json changes
- Both are reference data consumed by multiple downstream systems
- Keeps related artifacts together

**Alternative considered:** Put in `src/preprocessing/` output directory. Rejected because this is reference data, not processed dataset output.

---

## Clarification: Potential vs Actual Collisions

**Question raised:** Does hierarchy_reference.json contain just branch templates, or full component enumeration?

**Answer:** Full enumeration — includes `components` array with all actual component paths.

**Why it matters:**

| Collision Type | Source | What It Tells You |
|----------------|--------|-------------------|
| Potential | Branch templates only | "These designator values are ambiguous in principle" |
| Actual | Enumerated components | "These specific components exist and share ambiguous partial paths" |

With full enumeration, the collision index shows **actual** collisions — component paths that genuinely share partial path segments. This is what the difficulty model needs.

**Implication for instruction:** The instruction specifies that `components` is a required top-level field in hierarchy_reference.json, and collision index is built from actual paths.

---

## Implementation Approach

Created detailed instruction file following project conventions:

| Section | Purpose |
|---------|---------|
| Context and Rationale | Why this exists, what consumes it |
| Input/Output Specifications | Exact schemas with Terraform Combine examples |
| Computation Logic | Step-by-step algorithm for each discrimination type |
| Anti-Patterns | Five explicit "don't do X" warnings |
| Decision Boundaries | What to do when encountering edge cases |
| Testing Strategy | Unit tests and integration tests |
| Acceptance Criteria | Nine checkboxes for completion |

**Execution mode:** Sonnet with thinking on (requires understanding domain model)

---

## Anti-Patterns Flagged

1. **Don't hardcode branch/level names** — must work for any hierarchy structure
2. **Don't assume uniform depth** — branches have 3-5 levels
3. **Don't conflate level names with designator values** — "squadron" as level name ≠ "squadron" as designator value
4. **Don't generate absence-based exclusion rules** — only presence triggers exclusions
5. **Don't create circular dependencies** — no imports from sampling.py or llm_phases.py

---

## Task Dependencies Clarified

```
extract_structural_discriminators()     ← CURRENT PRIORITY
        │
        ├──► compute_soldier_difficulty()   [blocked]
        │
        └──► Phase 5 deterministic exclusions [blocked]
```

Both downstream tasks are blocked on this utility. It's the critical path.

---

## Open Questions Resolved

| Question | Resolution |
|----------|------------|
| How to identify branch-unique terms? | Utility computes level_name_discriminators from hierarchy |
| How to identify branch-unique designators? | Utility computes designator_discriminators from hierarchy |
| Where does Phase 5 get exclusion rules? | From structural_discriminators.json (same source as difficulty model) |
| Potential vs actual collisions? | Actual — hierarchy has full component enumeration |

---

## Artifacts Produced

1. **Instruction file:** `instructions/active/008extract_structural_discriminators.md`
   - Complete implementation spec for agent execution
   - Includes function signature, test strategy, acceptance criteria

2. **Updated SESSION_STATE.md**
   - Reflects new task priority and dependency chain
   - Marks open question #3 as resolved

---

## Next Steps

1. Agent executes instruction to build `extract_structural_discriminators()`
2. After utility passes tests, implement `compute_soldier_difficulty()` (can now consume structural_discriminators.json)
3. Update resolver Phase 5 to use same output for deterministic exclusions

---

## References

- `docs/DIFFICULTY_MODEL.md` — Specifies structural_resolvability as input signal
- `ADR-009` — Decision that Phase 5 exclusions are deterministic from hierarchy
- `docs/components/strategies/resolver/CURRENT.md` — Module specs for sampling.py and structure.py
