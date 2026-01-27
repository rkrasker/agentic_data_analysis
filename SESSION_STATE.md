# SESSION_STATE.md

**Last Updated:** 2026-01-27
**Session:** Opus 4.5 strategy session — Difficulty batching strategy

---

## Active Task

Implement `compute_soldier_difficulty()` for sampling. Design work complete; ready for implementation.

---

## Completed This Session

### Difficulty Model Design (New Document)

Created `docs/DIFFICULTY_MODEL.md` as a cross-cutting reference document (peer to `DISAMBIGUATION_MODEL.md`). Captures:

- Confidence weights for level coverage (1.0 / 0.75 / 0.25)
- Complementarity formula: sum of level confidences / min(branch_depth, 4)
- Structural resolvability: boolean based on branch elimination
- Difficulty tier thresholds: fixed at 0.7 and 0.4
- Edge case handling

### Key Decisions

| Decision | Resolution |
|----------|------------|
| Data source | `canonical.parquet` — leverage pre-extracted characterized + uncharacterized columns |
| Complementarity denominator | min(branch_depth, 4) — caps to avoid micro-level penalty |
| Uncharacterized handling | Check validity against hierarchy; weight by ambiguity level |
| Multi-branch collisions | Compute complementarity per candidate branch, take max |
| Threshold type | Fixed values (0.7, 0.4), not percentile-based |
| Collision detection | Extraction-based, not ground-truth membership |

---

## Where I Left Off

**Design complete.** Next step is implementation of `compute_soldier_difficulty()` in `sampling.py`.

Implementation requires:
1. Build level → valid designators lookup from hierarchy_reference.json
2. Map characterized extractions to explicit level coverage
3. Map uncharacterized extractions to speculative level coverage with validity check
4. Aggregate confidences across records per soldier
5. Check collision position against collision index
6. Check structural resolvability (do constraints eliminate all but one branch?)
7. Apply tier thresholds

---

## Open Questions (Updated)

### Resolved This Session

1. ~~**Complementarity formula**~~ → Sum of level confidences / min(branch_depth, 4)
2. ~~**Difficulty tier thresholds**~~ → Fixed: 0.7 and 0.4

### Still Open

3. **Structural discriminator extraction:** How to automatically identify which terms are unique to which branch from hierarchy_reference.json? May need explicit `discriminating_terms` list in hierarchy config.

4. **Cross-branch collision handling:** Partially addressed (depth mismatch as exclusion signal). May need refinement when hitting real examples.

5. **Migration path:** Existing resolver code marked "complete" — refactoring strategy TBD. Options: rewrite modules in place, or create v2 alongside.

---

## Artifacts Produced

| Artifact | Location | Status |
|----------|----------|--------|
| Difficulty Model | `docs/DIFFICULTY_MODEL.md` | New — ready for review |
| Session Extract | `.project_history/extracts/raw/2026-01-27_opus_difficulty-batching.md` | New |
| ADR-009 | `docs/architecture/decisions/ADR-009_resolver-generation-alignment.md` | Unchanged (design aligns with existing ADR) |
| Resolver CURRENT.md | `docs/components/strategies/resolver/CURRENT.md` | Needs update to reference DIFFICULTY_MODEL.md |

---

## References

- `docs/DIFFICULTY_MODEL.md` — Operational difficulty computation (new)
- `docs/DISAMBIGUATION_MODEL.md` — Three-layer conceptual framework
- `ADR-006` — Record quality ≠ resolution difficulty
- `ADR-009` — Resolver generation alignment
