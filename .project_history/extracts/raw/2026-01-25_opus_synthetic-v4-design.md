# Synthetic Data v4 Design Session

**Date:** 2026-01-25
**Model:** Claude Opus 4.5
**Context:** Implementing ADR-007 synthetic data redesign

---

## Session Summary

Created the v4 synthetic style specification (`synthetic_style_spec_v4.yaml`) based on ADR-007 decisions. This session focused on translating the architectural decisions into a detailed specification that can guide implementation.

---

## Key Decisions Made

### 1. Domain: Terraform Combine

Replaced WWII military domain with fictional interstellar organization called "Terraform Combine" (TFC). Four operational branches:

| Branch | Purpose | Depth | Levels |
|--------|---------|-------|--------|
| Colonial Administration (CA) | Governance | 4 | Sector → Colony → District → Settlement |
| Defense Command (DC) | Security | 5 | Sector → Fleet → Squadron → Wing → Element |
| Expeditionary Corps (EC) | Exploration | 3 | Sector → Expedition → Team |
| Resource Directorate (RD) | Extraction | 4 | Sector → Operation → Facility → Crew |

**Rationale:** Zero LLM pretraining contamination. If disambiguation succeeds, it's due to our signals, not background knowledge.

### 2. State Model

- Soldiers have 1-3 states (65%/28%/7% distribution)
- Each state has explicit `state_id` and `state_order`
- States link to posts (full hierarchy paths)
- Records include `state_id` linking to ground truth

**Rationale:** Enables evaluation of state grouping accuracy, not just state count and resolution.

### 3. Source-Anchored State Assignment

- Sources have `temporal_anchor` indicating which state-period they capture
- All records for a soldier within a source reflect the same state
- Soldier appears at most once per source
- State conflicts arise across sources, not within them

**Rationale:** Mirrors real-world scenario where documents were created at different times.

### 4. Familiarity Gradient

- Sources have `home_unit` at Level-3 granularity
- Familiarity determines notation detail:
  - Same Level-3: Minimal ("Martinez A")
  - Same Level-2: Low ("Martinez A/Sq-3")
  - Same Branch: Medium ("Martinez A/Sq-3/Fleet-Kestrel")
  - Different Branch: Maximum (full path with branch)

**Rationale:** Creates exploitable asymmetry - records from same source with same abbreviation pattern likely share home unit.

### 5. Transfer Distribution

- Within same Level-3: 40%
- Within same Level-2: 30%
- Within same Branch: 15%
- Cross-branch: 15%

**Rationale:** Cross-branch transfers create hardest cases where hierarchy structure differs between states.

### 6. Collision Design

Shared designators create meaningful ambiguity:
- Numbers (1-12): Appear at fleet, district, facility, team levels
- Letters (A-F): Appear as element, wing, crew, team designators
- Names (Kestrel, Amber, etc.): Appear as colony, fleet, expedition names

---

## Alternatives Considered

### Domain Alternatives (Rejected)

1. **Prompting controls only**: Unreliable - LLM priors are deeply embedded
2. **Scrambled designators**: Partial fix - structure/patterns might still cue priors
3. **Fictional historical**: Risk of fantasy trope contamination (e.g., Lord of the Rings military)
4. **Abstract bureaucracy**: Too sterile - hard to create meaningful situational vocabulary

### State Count Alternatives (Rejected)

1. **Unlimited states**: Adds complexity without proportional methodological value
2. **Binary only (1-2)**: Misses the three-state stress test for state discovery

---

## Implementation Implications

### Files Requiring Full Rewrite

| File | Reason |
|------|--------|
| `hierarchy_reference.json` | New domain - 4 branches with different structures |
| `synthetic_vocabulary.json` | All new situational, clutter, confounder terms |
| `synthetic_themes.json` | Branch-based themes replacing military themes |
| `synthetic_style_spec.yaml` | Now v4 (created this session) |

### Files Requiring Significant Update

| File | Key Changes |
|------|-------------|
| `models.py` | Add State class, update Assignment, add Branch enum |
| `soldier_factory.py` | Generate states not just assignments |
| `source_generator.py` | Add home_unit, temporal_anchor |
| `renderer.py` | Familiarity-aware rendering, 4 branch formats |
| `transfer_manager.py` | Cross-branch transfers |
| `pipeline.py` | Wire state assignment |

### What Transfers from v3 (Logic Unchanged)

- Clerk archetype behavioral patterns
- Quality tier system (1-5)
- Within-source consistency model
- Behavioral imperfections
- Vocabulary density levels
- Fatigue modeling

---

## Warnings for Implementation

### Hierarchy Depth Pitfall

Code must not assume fixed depth. Each branch has different depth (3-5 levels). Use `len(branch.levels)` or equivalent.

### State vs Assignment Confusion

v3 had Assignments. v4 has States. A State contains a post (which is like an Assignment). Don't conflate:
- State = temporal segment of service
- Post = unit path within a state

### Familiarity is Source-Relative

Familiarity is calculated relative to SOURCE's home unit, not SOLDIER's unit. Same soldier appears differently in different sources.

### Collision Must Be Meaningful

Ensure designator overlaps are at comparable levels. "7" should plausibly be Fleet 7, District 7, Facility 7, or Team 7 - not arbitrary.

---

## Deliverables from This Session

1. **synthetic_style_spec_v4.yaml** - Full v4 specification (1400+ lines)
2. **Instruction file 004** - Implementation guide for Sonnet
3. **This extract** - Decision record

---

## Next Steps

1. Execute instruction 004 (Sonnet) to implement code changes
2. Create seed_set_v4.json with hand-crafted calibration examples (future)
3. Run generation pipeline and validate output (future)
4. Update preprocessing for new domain (future)

---

## Related Documents

- ADR-007: `docs/architecture/decisions/ADR-007-synthetic-data-redesign.md`
- Style spec v4: `docs/components/synthetic_data_generation/synthetic_style_spec_v4.yaml`
- CURRENT.md: `docs/components/synthetic_data_generation/CURRENT.md`
- Instruction file: `instructions/active/004_synthetic-v4-terraform-combine.md`
