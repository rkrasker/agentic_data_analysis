# SESSION_STATE.md

**Last Updated:** 2026-01-28
**Session:** Opus 4.5 implementation session — Structural discriminators complete

---

## Active Task

None — `extract_structural_discriminators()` implementation complete. Ready for next task.

---

## Completed This Session

### Implemented `extract_structural_discriminators()`

Built the utility that extracts structural discrimination rules from hierarchy reference:

**Location:** `src/preprocessing/hierarchy/structural_discriminators.py`

**Output:** `config/hierarchies/structural_discriminators.json`

**Features:**
- Level name discriminators (which terms are unique to which branches)
- Designator discriminators (which values are valid in which branches/levels)
- Depth discriminators (which depths are unique to which branches)
- Branch exclusion rules (presence-based rules for excluding branches)
- Collision index (which (level, value) pairs map to multiple components)

**Tests:** 19 unit tests in `tests/test_structural_discriminators.py` — all passing

### Updated Documentation

| File | Update |
|------|--------|
| `DIFFICULTY_MODEL.md` | Updated collision index source to reference new module |
| `CLAUDE.md` | Fixed broken links to DIFFICULTY_MODEL.md |
| `docs/components/preprocessing/CURRENT.md` | Added hierarchy/ subdirectory, changelog entry |
| `docs/components/strategies/resolver/CURRENT.md` | Updated Module 2 and Phase 5 to reference new module |
| `docs/GLOSSARY.md` | Added "structural discriminator" term |
| `docs/architecture/CURRENT.md` | Updated preprocessing status, added artifact |

### Moved Completed Instruction

`instructions/active/008extract_structural_discriminators.md` → `instructions/completed/`

---

## Where I Left Off

**Implementation complete.** The structural discriminators utility is now available for:

1. **Difficulty Model:** `compute_soldier_difficulty()` can load `structural_discriminators.json` to determine `structural_resolvability`
2. **Resolver Phase 5:** Can read pre-computed `branch_exclusion_rules` instead of computing them

---

## Task Dependencies (Updated)

```
extract_structural_discriminators()     ✓ COMPLETE
        │
        ├──► compute_soldier_difficulty()   [unblocked - ready to implement]
        │           │
        │           └──► sampling.py updates
        │
        └──► Phase 5 deterministic exclusions [unblocked - can use output]
                    │
                    └──► llm_phases.py updates
```

---

## Open Questions

### Resolved This Session

1. ~~**Complementarity formula**~~ → Sum of level confidences / min(branch_depth, 4)
2. ~~**Difficulty tier thresholds**~~ → Fixed: 0.7 and 0.4
3. ~~**Structural discriminator extraction**~~ → ✓ Implemented

### Still Open

4. **Cross-branch collision handling:** Partially addressed (depth mismatch as exclusion signal). May need refinement when hitting real examples.

5. **Migration path:** Existing resolver code marked "complete" — refactoring strategy TBD. Options: rewrite modules in place, or create v2 alongside.

6. **Minimum extraction threshold:** Should soldiers with zero extractions be excluded from sampling entirely, or left as Extreme? (Deferred to implementation)

---

## Artifacts Produced

| Artifact | Location | Status |
|----------|----------|--------|
| Structural Discriminators Module | `src/preprocessing/hierarchy/structural_discriminators.py` | ✓ Complete |
| Structural Discriminators Output | `config/hierarchies/structural_discriminators.json` | ✓ Generated |
| Unit Tests | `tests/test_structural_discriminators.py` | ✓ 19 tests passing |
| Test Fixtures | `tests/fixtures/test_hierarchy_*.json` | ✓ Complete |
| Instruction (completed) | `instructions/completed/008extract_structural_discriminators.md` | ✓ Moved |

---

## Next Steps

1. **`compute_soldier_difficulty()`** — Now unblocked; can consume `structural_discriminators.json`
2. **Resolver Phase 5 update** — Wire up to use pre-computed exclusion rules
3. **`sampling.py` updates** — Add difficulty-based sampling using new difficulty computation

---

## References

- `DIFFICULTY_MODEL.md` — Operational difficulty computation
- `docs/DISAMBIGUATION_MODEL.md` — Three-layer conceptual framework
- `ADR-006` — Record quality ≠ resolution difficulty
- `ADR-009` — Resolver generation alignment (Phase 5 deterministic exclusions)
