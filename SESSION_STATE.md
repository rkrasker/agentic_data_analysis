# SESSION_STATE.md

**Last Updated:** 2026-01-27
**Session:** Opus 4.5 strategy session — Resolver generation alignment

---

## Active Task

Align resolver generation process with the three-layer disambiguation model (ADR-006) and Terraform Combine domain (ADR-007).

---

## Current Approach and Key Decisions

**Scope clarification established:** Resolvers are component discrimination and parsing aids only — they do not handle state discovery, record grouping, or full consolidation orchestration. This narrowed the redesign to four targeted changes.

**Decisions made (documented in ADR-009):**

1. **Sampling criterion changed:** Sample soldiers by assignment difficulty (Layer 2-3: collision position, complementarity, structural ambiguity), not record quality tier. Include ALL records for sampled soldiers regardless of quality.

2. **Branch-aware structural encoding:** Phase 1 now produces branch-specific constraints including depth, level names, and structural discriminators (terms unique to a branch like "squadron" for Defense Command).

3. **Phase 5 simplified:** Exclusion mining becomes deterministic derivation from hierarchy — no LLM call, no "value-based" exclusions. Rationale: with synthetic data where hierarchy is complete by construction, mining structural facts from data is backwards.

4. **Hard case criteria reframed:** Aligned with three-layer model (collision position, non-complementary records, structural ambiguity). Removed "transfer indicators" criterion — that's a state problem, not component discrimination.

**Artifacts produced:**
- `ADR-009_resolver-generation-alignment.md` — formal decision record
- `resolver_CURRENT.md` — updated specification with new schema examples

---

## Where I Left Off

**Next step:** Implement `compute_soldier_difficulty()` in `sampling.py` — this is the foundation for the new sampling strategy. Requires defining:
- How to detect collision position from partial path
- Complementarity score formula (how much do records cover different path segments?)
- Structural resolvability check (do hierarchy constraints resolve ambiguity?)
- Thresholds for difficulty tiers (easy/moderate/hard/extreme)

---

## Open Questions

1. **Complementarity formula:** How exactly to score whether records are complementary vs. redundant? Need to define what "covering different path segments" means operationally.

2. **Difficulty tier thresholds:** What cutoffs define easy/moderate/hard/extreme? Should these be relative (percentiles) or absolute?

3. **Structural discriminator extraction:** How to automatically identify which terms are unique to which branch from hierarchy_reference.json? May need to add explicit term lists to hierarchy config.

4. **Cross-branch collision handling:** When components from different branches share a designator (e.g., "7" in Fleet 7 vs Operation 7), how does depth mismatch interact with the collision sampling logic?

5. **Migration path:** Existing resolver code is marked "complete" — what's the refactoring strategy? Rewrite modules in place, or create v2 alongside?
