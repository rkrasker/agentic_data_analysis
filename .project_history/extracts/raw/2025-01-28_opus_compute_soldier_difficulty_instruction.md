# Extract: compute_soldier_difficulty() Instruction Design

**Date:** 2025-01-28
**Session type:** Instruction file generation
**Output:** `instructions/active/009_compute_soldier_difficulty.md`

---

## Key Decisions

### 1. Module Location

**Decision:** Create new module at `src/preprocessing/difficulty/` rather than adding to `sampling.py`

**Rationale:** Follows the pattern established by `structural_discriminators.py` — difficulty computation is conceptually preprocessing, not sampling logic. Keeps sampling.py focused on sample selection, not signal computation.

**Note:** This deviates from ADR-009 which stated "Add to `sampling.py`" — the ADR's intent (make difficulty available for sampling) is preserved, but implementation location is cleaner as a separate module.

### 2. Collision Index Source

**Decision:** Load pre-computed collision index from `structural_discriminators.json`

**Alternatives considered:**
- Pass as parameter (rejected: pushes complexity to caller)
- Compute fresh (rejected: wasteful, duplicates work already done)

**Implication:** The function has a hard dependency on `structural_discriminators.json` existing and containing the `collision_index` key. Instruction specifies to fail loudly if missing.

### 3. Interface Design

**Decision:** Provide both single-soldier and batch functions; batch calls single internally

**Rationale:** 
- Single-soldier function is the conceptual unit (matches DIFFICULTY_MODEL.md framing)
- Batch function is what sampling workflows actually need
- Internal delegation keeps logic in one place

**Interface:**
```python
compute_soldier_difficulty(soldier_id, records, structural_discriminators, hierarchy_reference) -> DifficultyAssessment

compute_all_soldier_difficulties(canonical_df, structural_discriminators, hierarchy_reference) -> pd.DataFrame
```

### 4. Column Name Discovery

**Decision:** Implementing agent must inspect `canonical.parquet` to discover actual column names

**Rationale:** DIFFICULTY_MODEL.md uses conceptual names (`Unit_Term_Digit_Term:Pair`, `Unchar_Alpha`) that may not match actual schema. Hardcoding would be fragile.

**Implication:** Instruction includes anti-pattern warning against hardcoded column names and decision boundary guidance for ambiguous mappings.

---

## Scope Boundaries Established

**In scope:**
- Three signal computation (collision position, complementarity, structural resolvability)
- Difficulty tier assignment
- Batch processing for full dataset
- Diagnostic fields for debugging

**Out of scope:**
- Modifying sampling.py (separate task)
- Wiring to resolver Phase 5 (separate task)
- Record quality tier computation (Layer 1 — already exists elsewhere)

---

## Warnings for Implementation

1. **Don't filter by record quality.** The whole point of ADR-006/009 is that we include ALL records for a soldier regardless of quality tier.

2. **Multi-branch collision handling is subtle.** When a soldier's extractions could belong to multiple branches, compute complementarity for each candidate and take maximum. This is the "best-case interpretation" principle from DIFFICULTY_MODEL.md.

3. **Denominator cap at 4.** Deep hierarchies (5+ levels) shouldn't penalize soldiers whose records don't mention micro-levels like fire teams. This is already in DIFFICULTY_MODEL.md but easy to miss.

4. **Structural resolvability is a rescue mechanism.** It promotes to Moderate even with low complementarity. The decision tree order matters.

---

## Open Items Not Resolved

1. **Characterized vs Uncharacterized column identification.** The instruction tells the agent to discover this from the parquet schema, but doesn't specify how to distinguish them. May need follow-up if the schema isn't self-documenting.

2. **Multi-branch complementarity edge case.** If records contain contradictory branch signals (e.g., "squadron" which implies Defense Command AND "laboratory" which implies Resource Directorate), current spec says complementarity = 0 for any single-branch interpretation. This feels right but wasn't deeply validated.

---

## Task Dependencies Updated
```
extract_structural_discriminators()     ✓ COMPLETE
        │
        └──► compute_soldier_difficulty()   ← THIS INSTRUCTION
                    │
                    ├──► sampling.py updates (next instruction)
                    │
                    └──► Phase 5 wiring (separate instruction)
```

---

## Artifacts Produced

| Artifact | Location | Status |
|----------|----------|--------|
| Instruction file | `instructions/active/009_compute_soldier_difficulty.md` | Ready for execution |
| Session extract | `.project_history/extracts/raw/2025-01-28_opus_compute_soldier_difficulty_instruction.md` | This file |

---

## References

- DIFFICULTY_MODEL.md — primary specification consumed
- ADR-009 — alignment rationale
- ADR-006 — three-layer model origin
- SESSION_STATE.md — task context