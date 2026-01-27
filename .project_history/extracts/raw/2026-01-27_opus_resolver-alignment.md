# Extract: Resolver Generation Alignment with Disambiguation Model

**Date:** 2026-01-27
**Session type:** Opus 4.5 strategy session
**Artifacts produced:** ADR-009, resolver_CURRENT.md (updated)

---

## Context

The resolver generation process (documented in resolver CURRENT.md, governed by ADR-002) was designed before the three-layer disambiguation model (ADR-006) and Terraform Combine domain redesign (ADR-007) were adopted. This session identified conceptual misalignments and produced a targeted redesign.

---

## Key Decisions and Rationale

### Decision 1: Sample by Soldier Difficulty, Not Record Quality

**Old approach:** Filter records by quality tier (tiers 3-5) to "force subtle signal discovery."

**New approach:** Sample soldiers by assignment difficulty (Layer 2-3), include all their records.

**Rationale:** ADR-006 establishes that record quality (Layer 1) is orthogonal to assignment difficulty. A soldier with three pristine tier-1 records all saying "3rd Regiment" in a collision zone is exactly what differentiator training needs — but the old sampling would exclude those records. The insight: we want hard *soldiers*, not degraded *records*.

**Implementation impact:** Remove `_filter_records_by_quality()` from llm_phases.py. Add `compute_soldier_difficulty()` to sampling.py. Sampling prioritizes soldiers where `difficulty_tier in ['hard', 'extreme']`.

### Decision 2: Branch-Aware Structural Encoding

**Old approach:** Phase 1 extracted uniform hierarchy constraints (valid regiments, battalions, companies) assuming homogeneous WWII-style structure.

**New approach:** Phase 1 produces branch-specific constraints including depth, level names, and structural discriminators.

**Rationale:** ADR-007 introduces heterogeneous branches with depths 3-5. Structural heterogeneity creates discrimination signal: "squadron" only exists in Defense Command, a 5-level path can't belong to Expeditionary Corps (depth 3). These are powerful disambiguation signals the old model ignored.

**Implementation impact:** Rewrite structure.py to parse heterogeneous hierarchy. New `ComponentStructure` dataclass includes branch, depth, levels list, and structural_discriminators. Schema changes to resolver JSON.

### Decision 3: Phase 5 Becomes Deterministic

**Old approach:** Phase 5 had two sub-phases — structural exclusions (hierarchy-derived) and value-based exclusions (LLM-mined from data, e.g., "regiment 11 excludes 1st ID").

**New approach:** Phase 5 is pure computation from hierarchy. No LLM call.

**Rationale:** Value-based exclusion mining assumed the hierarchy might be incomplete or that data patterns weren't captured structurally. With synthetic data where hierarchy is complete by construction, this is backwards — if it's true, it's in the structure; if it's not in the structure, it shouldn't be in the data. Mining structural facts from data is redundant work.

**Implementation impact:** Remove LLM call from Phase 5 in llm_phases.py. Implement `compute_exclusions()` as pure function over hierarchy. Simplify exclusions schema (remove value_based section).

### Decision 4: Three-Layer Hard Case Criteria

**Old criteria:** Symptomatic flags — "multiple component indicators," "unusual notation," "transfer indicators present."

**New criteria:** Structural flags aligned with ADR-006:
- Collision position (Layer 2): Soldier's partial path is non-unique
- Non-complementary records (Layer 2): All records provide same ambiguous partial path  
- Structural ambiguity (Layer 3): Designators don't resolve structurally

**Rationale:** "Transfer indicators" is a state discovery problem, not component discrimination. Resolvers don't need to flag transfers; they need to flag "I can't determine which component." The new criteria map directly to the layers where disambiguation can fail.

**Implementation impact:** Update hard case flagging prompts in prompts.py. Hard case output includes which layer caused difficulty, enabling layer-specific analysis in reconciliation.

---

## Alternatives Considered

### Broader redesign of resolver purpose
**Considered:** Expanding resolvers to handle state discovery and record grouping.

**Rejected:** Resolvers are component discrimination aids. State discovery and grouping are upstream orchestration problems that *use* resolvers but aren't the resolver's job. Keeping scope narrow allows targeted fixes without architectural overhaul.

### Source-anchored inference as resolver signal
**Considered:** Using source document context (home unit, temporal anchoring) as resolver input.

**Rejected (bracketed):** Source-anchored inference is valuable but belongs in orchestration layer, not resolver artifacts. For now, it's purely a synthetic data architecture component — resolvers see records without source context.

### Keeping value-based exclusions for real data
**Considered:** Retaining the LLM mining step for future use on real (non-synthetic) data where hierarchy might be incomplete.

**Rejected:** The synthetic domain is specifically designed to prove methodology without contamination. If methods work on clean synthetic data, value-based mining could be re-added for real deployment. But for validation purposes, deterministic exclusions are cleaner.

---

## Implications for Implementation

### Files Requiring Changes

| File | Change Type | Priority |
|------|-------------|----------|
| `sampling.py` | Add `compute_soldier_difficulty()`, remove quality tier logic | High — foundational |
| `structure.py` | Rewrite for heterogeneous branches | High — schema change |
| `llm_phases.py` | Remove Phase 5 LLM call, remove quality filtering | Medium |
| `prompts.py` | Update hard case criteria | Medium |
| `assembler.py` | Update for new schema | Medium |

### Files Unchanged

- `thresholds.py` — tier calculation logic unaffected
- `dual_run.py` — orchestration architecture preserved
- `reconciliation.py` — reconciliation logic preserved
- `registry.py` — registry system preserved
- `generate.py` — workflow unchanged, modules updated

### Schema Migration

Resolver JSON schema changes:
- `structure` section gains `branch`, `depth`, `levels`, `structural_discriminators`
- `exclusions` section loses `value_based`, gains `source: "hierarchy_derived"`
- `differentiators` gain depth-based rules

Existing resolvers (if any) would need regeneration — but since we're in synthetic data redesign anyway, this is expected.

---

## Warnings and Pitfalls

### Complementarity Score Definition
The new sampling requires a `complementarity_score` measuring how much records cover different path segments. **This formula is not yet defined.** Risk: if poorly specified, "hard" soldiers might not actually be hard, defeating the purpose of the change.

**Recommendation:** Define operationally before implementation. Consider: what fraction of path segments are covered by only one record vs. multiple records?

### Structural Discriminator Extraction
Automatically identifying branch-unique terms requires either:
1. Explicit term lists in hierarchy_reference.json, or
2. Computational derivation (scan all branches, find terms appearing in only one)

**Risk:** If hierarchy_reference.json doesn't include level name vocabulary, structural discriminators won't be extractable.

**Recommendation:** Ensure hierarchy config includes level names explicitly. Add validation that each branch has at least some unique terms.

### Cross-Branch Collision Complexity
When components from different branches share a designator (e.g., "7" appears in Fleet 7 and Operation 7), the collision has asymmetric structure — one branch is depth 5, one is depth 4. Sampling and differentiator generation must handle this.

**Risk:** Collision sampling code may assume symmetric structure.

**Recommendation:** Test with cross-branch collisions explicitly. Ensure `CollisionSample` captures structural asymmetry.

### Hard Case Layer Attribution
New hard case criteria require attributing difficulty to specific layers. This means the LLM must output structured reasoning about *why* a case is hard.

**Risk:** LLM may flag hard cases without proper layer attribution, making analysis difficult.

**Recommendation:** Update prompts to require explicit layer citation. Validate hard case output schema includes layer field.

---

## Related Documents

- **ADR-006:** Three-layer difficulty model (source framework)
- **ADR-007:** Synthetic data redesign (Terraform Combine domain)
- **ADR-009:** Resolver generation alignment (produced this session)
- **resolver_CURRENT.md:** Updated specification (produced this session)
- **CLAUDE.md:** Core problem definition (state resolution scope)
- **DISAMBIGUATION_MODEL.md:** Three-layer analytical framework
