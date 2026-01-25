# Session Summary: Synthetic Data Redesign Planning

**Date:** 2026-01-25  
**Session Type:** High-level planning (Opus 4.5)  
**Output:** ADR-004, CURRENT-synthetic-v4.md, this summary

---

## Session Goal

Evaluate whether existing synthetic data (v3) effectively simulates the state resolution problem, and determine what changes are needed.

---

## Key Questions Addressed

### 1. Does v3 synthetic data align with project goals?

**Assessment:** Mostly yes, with gaps:

| Aligned | Gap |
|---------|-----|
| Collision zones | State count capped at 2 |
| Clerk variation | States implicit, not explicit |
| Abbreviated records | No familiarity gradient |
| Transfer mechanism | LLM contamination from real WWII data |

### 2. Should states be implicit or explicit?

**Decision:** Explicit (Option 2)

States become first-class objects with `state_id` tracked in both validation and raw data. This enables evaluation of:
- State count discovery
- Record grouping accuracy (not possible with implicit states)
- Post resolution per state

### 3. How should records be assigned to states?

**Decision:** Source-anchored (Option C)

Each source has a temporal anchor determining which state it captures for multi-state soldiers. A soldier appears at most once per source. This creates:
- Within-source consistency for state assignment
- Cross-source conflicts for multi-state soldiers
- Realistic simulation of documents created at different times

### 4. How should clerk notation vary?

**Decision:** Familiarity gradient at Level-3 granularity

Sources have a "home unit" (writer's organizational context). Clerks abbreviate home-unit records heavily; spell out foreign-unit records fully. Creates:
- Realistic asymmetry
- Exploitable structure (same-source abbreviation patterns signal shared context)
- Foundation for future graph-based inference

### 5. How to handle LLM pretraining contamination?

**Problem:** Initial tests showed LLM resolving units using pretraining knowledge (e.g., "116th → 29th ID") rather than in-context disambiguation signals.

**Decision:** Full domain decontamination (Option C2 — Interstellar)

Replace WWII military with fictional "Terraform Combine" organization. LLM has zero priors; must use in-context signals only. Methodological validity proven on clean data transfers to real-domain deployment.

### 6. Should hierarchy be homogeneous or heterogeneous?

**Decision:** Heterogeneous

Four branches with varying depths (3, 4, 4, 5 levels) and different level names/designator conventions. Structure itself becomes disambiguation signal. Collisions designed across branches.

---

## Decisions Made

| Decision | Choice |
|----------|--------|
| State tracking | Explicit with `state_id` |
| State count | 1-3 max, bias toward 1-2 |
| State temporality | Sequential (temporal ordering) |
| Record-to-state assignment | Source-anchored |
| Familiarity gradient | Level-3 granularity (battalion-equivalent) |
| Domain | Fictional interstellar (Terraform Combine) |
| Branch count | 4 branches |
| Hierarchy depths | 3, 4, 4, 5 levels |
| Cross-branch transfers | Allowed (15% of transfers) |

---

## The Terraform Combine Structure

| Branch | Purpose | Depth | Levels |
|--------|---------|-------|--------|
| Colonial Administration | Governance | 4 | Sector → Colony → District → Settlement |
| Defense Command | Security | 5 | Sector → Fleet → Squadron → Wing → Element |
| Expeditionary Corps | Exploration | 3 | Sector → Expedition → Team |
| Resource Directorate | Extraction | 4 | Sector → Operation → Facility → Crew |

**Collision design:** Numbers (7, 12, 3), letters (A, B, C), and names (Kestrel, Verdant) shared across branches at different levels.

---

## Schema Changes from v3

### raw.parquet additions
- `state_id` — links record to ground-truth state

### validation.parquet changes
- `state_id` — unique state identifier
- `state_order` — temporal position (1, 2, or 3)
- `branch` — which branch
- Branch-specific level columns (vary by branch)

### New: sources.parquet
- `source_id`
- `clerk_id`
- `situation_id`
- `home_unit` — writer's organizational context
- `quality_tier`

---

## What Transfers from v3 (Unchanged Logic)

- Clerk archetype mechanics
- Within-source consistency (85% identical format)
- Quality tier system
- Vocabulary layers (situational, clutter, confounders)
- Fatigue modeling
- Confounder injection rates

---

## What Requires Full Rewrite

| File | Reason |
|------|--------|
| `hierarchy_reference.json` | New domain |
| `synthetic_vocabulary.json` | New terms |
| `synthetic_themes.json` | Branch-based themes |
| `seed_set.json` | New calibration examples |

---

## What Requires Significant Update

| File | Changes |
|------|---------|
| `synthetic_style_spec.yaml` | Context renaming, familiarity spec |
| `soldier_factory.py` | State generation, 3-state logic |
| `source_generator.py` | home_unit, temporal_anchor |
| `pipeline.py` | State assignment, familiarity wiring |
| `renderer.py` | Familiarity-aware rendering |

---

## New Components to Implement

1. **StateAssigner** — determines which state a source captures for a soldier
2. **FamiliarityCalculator** — computes familiarity level from soldier assignment vs source home_unit
3. **Variable-depth hierarchy support** — loader and renderer handle branch-specific structures

---

## Open Questions for Future Sessions

1. **Sector geography:** How many sectors? Do sectors span branches or are they branch-specific?
2. **Specific designator lists:** How many fleets, colonies, expeditions, operations?
3. **Vocabulary design:** Specific situational terms, clutter codes, confounders for each branch
4. **Seed set construction:** Hand-crafted examples demonstrating new features
5. **Transfer probability tuning:** Exact distribution weights for state count and transfer types

---

## Documents Produced

1. **ADR-004-synthetic-data-redesign.md** — Formal decision record with rationale and consequences
2. **CURRENT-synthetic-v4.md** — Updated specification for synthetic data generation
3. **This summary** — Session continuity document

---

## Next Steps

1. Review produced documents for accuracy and completeness
2. Load into future session with instruction to implement hierarchy_reference.json for Terraform Combine
3. Design vocabulary layers for new domain
4. Update generation code to support new features
5. Create v4 seed set

---

## Session Context

**User preferences noted:**
- Self-taught Python developer
- Comfortable with pandas, basic ML concepts
- Prefers conceptual discussion before code generation
- Code generation only on explicit request

**No code was generated in this session** — all outputs are design documents.
