# SESSION_STATE.md

**Last Updated:** 2026-01-28
**Session:** Opus 4.5 implementation session — Difficulty computation implemented

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

### Implemented `compute_soldier_difficulty()`

Built the soldier-level difficulty computation module and batch helper:

**Location:** `src/preprocessing/difficulty/`

**Features:**
- Collision position detection using precomputed collision index
- Complementarity scoring with branch-aware aggregation
- Structural resolvability via exclusion rules
- Difficulty tier assignment (easy/moderate/hard/extreme)
- Batch computation over canonical records

**Tests:** `tests/test_difficulty_compute.py` — 8 unit tests passing

### Added Synthetic Generation Notebook

**Notebook:** `synthetic_generation_pipeline.ipynb`

**Purpose:** End-to-end synthetic generation + preprocessing pipeline scaffold

---

## Where I Left Off

**Implementation complete.** The difficulty computation is now available for:

1. **Sampling workflows:** `compute_soldier_difficulty()` can be called from `sampling.py`
2. **Difficulty stratification:** validation data can be enriched with computed tiers

---

## Task Dependencies (Updated)

```
extract_structural_discriminators()     ✓ COMPLETE
        │
        ├──► compute_soldier_difficulty()   ✓ COMPLETE
        │           │
        │           └──► sampling.py updates [pending]
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

6. ~~**Minimum extraction threshold:** Should soldiers with zero extractions be excluded from sampling entirely, or left as Extreme?~~ → Implemented: zero extractions yield Extreme.

---

## Artifacts Produced

| Artifact | Location | Status |
|----------|----------|--------|
| Structural Discriminators Module | `src/preprocessing/hierarchy/structural_discriminators.py` | ✓ Complete |
| Structural Discriminators Output | `config/hierarchies/structural_discriminators.json` | ✓ Generated |
| Unit Tests | `tests/test_structural_discriminators.py` | ✓ 19 tests passing |
| Test Fixtures | `tests/fixtures/test_hierarchy_*.json` | ✓ Complete |
| Instruction (completed) | `instructions/completed/008extract_structural_discriminators.md` | ✓ Moved |
| Difficulty Module | `src/preprocessing/difficulty/compute.py` | ✓ Complete |
| Difficulty Loader | `src/preprocessing/difficulty/loader.py` | ✓ Complete |
| Difficulty Tests | `tests/test_difficulty_compute.py` | ✓ 8 tests passing |
| Synthetic Pipeline Notebook | `synthetic_generation_pipeline.ipynb` | ✓ Added |

---

## Next Steps

1. **`sampling.py` updates** — Add difficulty-based sampling using new difficulty computation
2. **Resolver Phase 5 update** — Wire up to use pre-computed exclusion rules

---

## References

- `DIFFICULTY_MODEL.md` — Operational difficulty computation
- `docs/DISAMBIGUATION_MODEL.md` — Three-layer conceptual framework
- `ADR-006` — Record quality ≠ resolution difficulty
- `ADR-009` — Resolver generation alignment (Phase 5 deterministic exclusions)
