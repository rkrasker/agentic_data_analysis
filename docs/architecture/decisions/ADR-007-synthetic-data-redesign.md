# ADR-007: Synthetic Data Redesign for Methodological Validity

**Status:** Accepted  
**Date:** 2026-01-25  
**Deciders:** Project Lead  
**Context:** Planning session for synthetic data generation v4

---

## Context

Initial LLM parsing tests revealed a significant confound: the model was resolving military unit assignments using knowledge from its pretraining data (Wikipedia, unit histories, etc.) rather than from the disambiguation signals in our synthetic data. For example, the LLM "knows" that the 116th Infantry Regiment belongs to the 29th Infantry Division, bypassing our disambiguation logic entirely.

This contamination makes it impossible to:
1. Validate that our disambiguation methods work
2. Measure the contribution of specific signal types (vocabulary, structure, familiarity)
3. Trust that methods will generalize to cases where the LLM lacks priors

Additionally, the existing synthetic data model had several structural limitations:
- States were implicit (inferred from assignment) rather than explicit
- State count was capped at 2 (single transfer model)
- No familiarity gradient affecting clerk notation detail
- Homogeneous hierarchy structure across all components

---

## Decisions

### Decision 1: Explicit State Tracking

**Choice:** States become first-class objects with explicit `state_id` in both validation and raw data schemas.

**Rationale:** The project aims to evaluate three dimensions of state resolution:
1. State count discovery (how many states exist)
2. Record grouping (which records belong to which state)
3. Post resolution (what post each state resolves to)

With implicit states, only #1 and #3 can be rigorously evaluated. Explicit state tracking enables evaluation of grouping accuracy.

**Schema changes:**
- `validation.parquet` gains `state_id` and `state_order` columns
- `raw.parquet` gains `state_id` column linking each record to its ground-truth state

### Decision 2: Three-State Maximum with Bias Toward Two

**Choice:** Soldiers may have 1, 2, or 3 states (temporal/sequential). Distribution biased toward fewer states.

**Rationale:** Two-state cases (one transfer) are the common hard case. Three-state cases (two transfers) are rare but exist and stress-test state discovery. More than three adds complexity without proportional methodological value.

**Proposed distribution:**
- 1 state: ~65% of soldiers
- 2 states: ~28% of soldiers  
- 3 states: ~7% of soldiers

### Decision 3: Source-Anchored State Assignment

**Choice:** Each source document captures soldiers at a specific point in their service. All records in a source for a given soldier reflect the same state.

**Rationale:** 
- Creates realistic within-source consistency
- Records from the same source agree; conflicts arise across sources
- Mirrors real-world scenario where documents were created at different times
- A given source contains each soldier at most once

**Implementation:** Sources gain a temporal anchoring property. For multi-state soldiers, the source's anchor determines which state it captures.

### Decision 4: Familiarity Gradient at Level-3 Granularity

**Choice:** Source documents have a "home unit" (writer's organizational context) that affects notation detail. Granularity is at Level 3 of the hierarchy (battalion-equivalent).

**Rationale:** Clerks abbreviate aggressively for their own unit because context is shared with the reader. Foreign units get spelled out. This creates:
- Realistic asymmetry in record detail
- Exploitable structure (records from same source with same abbreviation pattern likely share home unit)
- Foundation for future graph-based inference on source context

**Familiarity levels:**
| Relationship to Writer | Detail Level |
|------------------------|--------------|
| Same Level-3 unit | Minimal (e.g., "Martinez A") |
| Same Level-2, different Level-3 | Low (e.g., "Martinez A/3") |
| Same branch, different Level-2 | Medium (e.g., "Martinez A/3/Fleet-7") |
| Different branch | Maximum (full path with branch identifier) |

### Decision 5: Full Domain Decontamination (Fictional Interstellar Setting)

**Choice:** Replace WWII military domain with a fictional interstellar organization ("Terraform Combine") that has zero presence in LLM pretraining data.

**Alternatives considered:**
- **Prompting controls only:** Unreliable; LLM priors are deeply embedded
- **Scrambled designators:** Partial; structure/patterns might still cue priors
- **Fictional historical:** Risk of fantasy trope contamination
- **Abstract bureaucracy:** Too sterile; hard to create meaningful situational vocabulary

**Rationale:** Proving methods on a domain with zero priors gives clean attribution. If disambiguation succeeds, it's due to our signals and structure, not background knowledge. Real-domain application becomes a deployment question, not a validity question.

**What transfers from current design:**
- Clerk archetypes (same logic, new context names)
- Familiarity gradient mechanics
- State/transfer model
- Source anchoring
- Collision zone design patterns
- Quality tier system
- Confounder/clutter vocabulary logic

### Decision 6: Heterogeneous Branch Structures

**Choice:** The Terraform Combine has 4 distinct operational branches, each with its own internal hierarchy structure. Depths vary from 3 to 5 levels.

**Rationale:** Structural heterogeneity creates disambiguation signal:
- Level names vary by branch ("Squadron" only in one branch, "Laboratory" only in another)
- Depth varies (a 5-level record can't belong to a 3-level branch)
- Designator conventions vary (some use names, some use numbers, some use letters)

**Branch structure:**

| Branch | Purpose | Depth | Levels |
|--------|---------|-------|--------|
| Colonial Administration | Governance | 4 | Sector → Colony → District → Settlement |
| Defense Command | Security | 5 | Sector → Fleet → Squadron → Wing → Element |
| Expeditionary Corps | Exploration | 3 | Sector → Expedition → Team |
| Resource Directorate | Extraction | 4 | Sector → Operation → Facility → Crew |

**Collision design:** Designators are shared across branches to create ambiguity:
- Numbers (7, 12, 3) appear at multiple levels in multiple branches
- Letters (A, B, C) appear as team/crew/element designators across branches
- Names (Kestrel, Amber, Verdant) appear as colony names, station names, expedition names

### Decision 7: Cross-Branch Transfers (Rare)

**Choice:** Most transfers stay within branch, but rare cross-branch transfers are possible.

**Rationale:** Cross-branch transfers create the hardest cases—records where the structure itself differs between states. A soldier who moved from Defense Command to Colonial Administration has states with different hierarchy depths.

**Distribution:**
- Within same Level-2 unit: 50%
- Within same branch, different Level-2: 35%
- Different branch: 15%

---

## Consequences

### Positive
- Clean methodological validity: success demonstrates method works, not LLM priors
- Richer evaluation: can measure state count, grouping, and resolution independently
- Structural disambiguation: branch heterogeneity creates new signal class
- Future-proofing: methods validated on clean data can be confidently deployed on real data

### Negative
- Development cost: substantial rework of hierarchy, vocabulary, situations
- Loss of intuition: WWII domain was familiar; new domain requires learning
- Transfer assumption: must verify methods transfer back to real military records

### Neutral
- Schema changes: state_id additions are straightforward
- Generation logic: core mechanics transfer; reskinning required

---

## Implementation Notes

### Files Requiring Changes

| File | Change Type |
|------|-------------|
| `config/hierarchies/hierarchy_reference.json` | Full rewrite for Terraform Combine |
| `config/synthetic/synthetic_vocabulary.json` | Full rewrite; new situational/clutter/confounder terms |
| `config/synthetic/synthetic_themes.json` | Full rewrite; branch-based themes |
| `docs/components/synthetic_data_generation/synthetic_style_spec_v3.yaml` | Update to v4; new clerk contexts |
| `src/synthetic/soldier_factory.py` | Add state_id generation, 3-state logic |
| `src/synthetic/source_generator.py` | Add home_unit, temporal anchoring |
| `src/synthetic/pipeline.py` | Wire new features |
| Schema definitions | Add state_id to raw and validation outputs |

### New Concepts to Implement

1. **State as first-class object:** Generation creates states, then records for states
2. **Source home_unit:** Each source has organizational context affecting rendering
3. **Familiarity-aware rendering:** Renderer checks soldier's unit vs source's home_unit
4. **Variable-depth hierarchy:** Hierarchy loader and renderer support branch-specific structures
5. **Branch-aware collisions:** Collision design accounts for cross-branch designator overlap

---

## Related Documents

- `docs/components/synthetic_data_generation/CURRENT.md` — Updated specification
- `docs/DISAMBIGUATION_MODEL.md` — Core problem framing (unchanged)
- `full-bootstrap.md` — Project overview (may need updates)
- `CLAUDE.md` — Session context (may need updates)
