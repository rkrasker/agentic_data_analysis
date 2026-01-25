# Synthetic Data Generation

**Version:** 4.0.0  
**Last Updated:** 2026-01-25  
**Status:** Design specification (not yet implemented)

---

## Purpose

Generate synthetic personnel records for a fictional interstellar organization that:
1. Resemble archival capture artifacts (compressed shorthand, inconsistent formatting)
2. Contain realistic ambiguity and confounders
3. Have learnable signals linking language to organizational categories
4. Force multi-signal disambiguation (no single-feature classification)
5. Are reproducible and comparable across experiments
6. **Feel organic** — written by humans, not sampled from probability distributions
7. **Are methodologically clean** — zero LLM pretraining contamination

---

## v4 Philosophy: Decontaminated Domain with Explicit States

The v4 spec makes two fundamental changes from v3:

### Change 1: Domain Decontamination

| v3 Approach | v4 Approach |
|-------------|-------------|
| WWII military units (29th ID, 116th Inf, etc.) | Fictional interstellar organization (Terraform Combine) |
| Real operations (Normandy, Bastogne) | Invented operations (Operation Deepcore, Survey Horizon) |
| Historical vocabulary (OMAHA, DZ-O) | Fictional vocabulary (SECTOR-7, BEACON-ALPHA) |
| LLM has strong priors from pretraining | LLM has zero priors; must use in-context signals only |

### Change 2: Explicit State Tracking

| v3 Approach | v4 Approach |
|-------------|-------------|
| States implicit (inferred from assignment field) | States are first-class objects with `state_id` |
| Binary: soldier has transfer or doesn't | 1-3 states per soldier with distribution weights |
| Can evaluate state count and resolution | Can evaluate state count, **grouping**, and resolution |

---

## The Terraform Combine

A fictional interstellar colonization and governance authority. Personnel serve in one of four operational branches, each with distinct hierarchy structure.

### Branch Structures

| Branch | Purpose | Depth | Level 1 | Level 2 | Level 3 | Level 4 | Level 5 |
|--------|---------|-------|---------|---------|---------|---------|---------|
| Colonial Administration | Governance of settlements | 4 | Sector | Colony | District | Settlement | — |
| Defense Command | Security, patrol, enforcement | 5 | Sector | Fleet | Squadron | Wing | Element |
| Expeditionary Corps | Exploration, survey, first contact | 3 | Sector | Expedition | Team | — | — |
| Resource Directorate | Mining, extraction, processing | 4 | Sector | Operation | Facility | Crew | — |

**Key structural features:**
- **Depth variation:** 3, 4, or 5 levels depending on branch
- **Shared top level:** All branches use "Sector" as Level 1 (shared organizational geography)
- **Unique level names:** "Squadron" only in Defense; "Colony" only in Colonial; "Expedition" only in Expeditionary
- **Mixed designator types:** Names, numbers, letters, and ordinals depending on level and branch

### Designator Conventions by Branch

| Branch | Level 2 | Level 3 | Level 4 | Level 5 |
|--------|---------|---------|---------|---------|
| Colonial | Colony names (Verdant, Kestrel, Thornmark) | District numbers/names (District 7, North District) | Settlement letters/names (Settlement C, Outpost Amber) | — |
| Defense | Fleet numbers (Fleet 7, Fleet 12) | Squadron letters (Squadron Alpha, Squadron C) | Wing numbers (Wing 3, Wing 7) | Element letters (Element A, Element Delta) |
| Expeditionary | Expedition names (Horizon, Far Reach, Pioneer) | Team designators (Team 4, Survey Alpha) | — | — |
| Resource | Operation names (Deepcore, Icevein, Yield-7) | Facility numbers (Facility 12, Platform 7) | Crew letters (Crew A, Crew Delta) | — |

### Collision Zones

Designators are deliberately shared across branches to create ambiguity:

| Designator | Possible Meanings |
|------------|-------------------|
| "7" | Fleet 7 (Defense), District 7 (Colonial), Facility 7 (Resource), Team 7 (Expeditionary) |
| "Alpha" | Squadron Alpha (Defense), Team Alpha (Expeditionary), Crew Alpha (Resource), Element Alpha (Defense) |
| "Kestrel" | Colony Kestrel (Colonial), Expedition Kestrel (Expeditionary) |
| "3" | Wing 3, Settlement 3, Crew 3, Team 3... |
| "A" | Element A, Crew A, Settlement A, Team A... |
| "12" | Fleet 12, District 12, Facility 12... |

A record saying "MARTINEZ CPL 7 ALPHA 3" is deeply ambiguous without additional signals.

---

## States as First-Class Objects

### Conceptual Model

```
Soldier
  └── has 1-3 States (ordered temporally)
        └── each State resolves to exactly one Post
              └── Post = full path through branch hierarchy
```

A **state** is a latent segment of a soldier's service. States are sequential (temporal ordering) but records have no dates—the challenge is discovering state boundaries from record content alone.

### State Distribution

| State Count | Frequency | Scenario |
|-------------|-----------|----------|
| 1 state | ~65% | Soldier served in one post throughout |
| 2 states | ~28% | One transfer during service |
| 3 states | ~7% | Two transfers during service |

### Transfer Types (State Transitions)

| Type | Frequency | Example |
|------|-----------|---------|
| Within same Level-3 unit | 50% | Element A → Element B within Wing 3 |
| Within same branch, different Level-2 | 35% | Squadron Alpha → Squadron Beta within Fleet 7 |
| Different branch | 15% | Defense Command → Colonial Administration |

Cross-branch transfers create the hardest cases: records where the hierarchy structure itself differs between states.

### Schema: States in Output Files

**validation.parquet** (or states.parquet):

| Column | Type | Description |
|--------|------|-------------|
| `soldier_id` | string | Soldier identifier |
| `state_id` | string | Unique state identifier (e.g., S001-1, S001-2) |
| `state_order` | int | Temporal position (1, 2, or 3) |
| `branch` | string | Branch identifier |
| `component_path` | string | Full hierarchy path |
| Level-specific columns | string | Vary by branch (sector, fleet/colony/expedition/operation, etc.) |

**raw.parquet**:

| Column | Type | Description |
|--------|------|-------------|
| `source_id` | string | Document/manifest identifier |
| `soldier_id` | string | Ground truth soldier identifier |
| `state_id` | string | Ground truth state this record captures |
| `raw_text` | string | Rendered manifest line |
| `clerk_id` | string | Clerk instance identifier |
| `situation_id` | string | Situation assigned to source |
| `quality_tier` | int | 1-5 quality level |

---

## Source-Anchored State Assignment

### Concept

Each source document has a **temporal anchor** — it captures soldiers at a specific point in their service. For multi-state soldiers:
- Source created during State 1 → records show State 1 assignment
- Source created during State 2 → records show State 2 assignment

**Key constraint:** A given source contains each soldier **at most once**. No soldier appears twice in the same manifest.

### Source Properties

| Property | Description |
|----------|-------------|
| `source_id` | Unique identifier |
| `clerk_id` | Which clerk produced this source (determines formatting) |
| `situation_id` | Operational context (determines vocabulary) |
| `home_unit` | Writer's organizational context (determines familiarity gradient) |
| `temporal_anchor` | Which state-period this source captures |

### Implementation

When generating records for a multi-state soldier:
1. Determine which sources will include this soldier
2. For each source, use its temporal_anchor to select which state to render
3. Render the record using that state's assignment

---

## Familiarity Gradient

### Concept

Clerks abbreviate aggressively for their "home unit" because context is shared with the reader. Foreign units get spelled out fully.

**Home unit granularity:** Level 3 of hierarchy (Squadron, District, Expedition, Facility)

### Familiarity Levels

| Relationship to Writer's Home Unit | Detail Level | Example (Defense Command clerk from Squadron Alpha, Fleet 7) |
|------------------------------------|--------------|--------------------------------------------------------------|
| Same Level-3 unit | Minimal | "Martinez Cpl A-3" (Element A, Wing 3 implied) |
| Same Level-2, different Level-3 | Low | "Martinez Cpl A-3 Sq-B" (specify squadron) |
| Same branch, different Level-2 | Medium | "Martinez Cpl A-3/Sq-B/Flt-12" (specify fleet) |
| Different branch | Maximum | "Martinez Cpl Crew-A, Facility-7, Op-Deepcore, Resource Directorate" |

### Interaction with Clerk Archetypes

Archetypes define the **template** and **style**. Familiarity modifies the **content** rendered into that template.

A `formal` archetype always uses full labels and commas:
```
{RANK} {LAST}, {FIRST} {MI}.  {UNIT_STRING}
```

But `{UNIT_STRING}` expands based on familiarity:
- Home unit: "Element A, Wing 3"
- Same branch, foreign Level-2: "Element A, Wing 3, Squadron Beta, Fleet 12"
- Different branch: "Crew A, Facility 7, Operation Deepcore, Resource Directorate"

### Source Home Unit Assignment

Sources are assigned home units based on:
1. **Clerk archetype context** — Some archetypes are "local" (battalion-level), others are "transient" (depot, hospital, transport)
2. **Situation correlation** — Certain situations associate with certain units

| Source Type | Home Unit Soldiers | Foreign Soldiers |
|-------------|-------------------|------------------|
| Local administrative | 90% | 10% (attachments, liaisons) |
| Sector HQ | 70% | 30% (cross-unit coordination) |
| Transit hub | 30% | 70% (mixed manifests) |
| Medical facility | 25% | 75% (casualties from across sector) |
| Processing depot | 10% | 90% (inbound transfers) |

---

## Clerk Archetypes (v4)

Archetypes from v3 transfer with context renaming. Examples:

| Archetype | Context | Example Output |
|-----------|---------|----------------|
| `hq_formal` | Sector HQ, trained on forms | `Spc Martinez, Carlos J.  Element A, Wing 3, Squadron Alpha, Fleet 7, Defense Command` |
| `hq_efficient` | Experienced HQ, efficient | `Martinez, C.J.  A/3/Alpha/7/DEF` |
| `local_rushed` | Unit clerk under pressure | `MARTINEZ SPC A3-ALPHA` |
| `local_methodical` | Careful unit clerk | `Martinez, Carlos  Elem A Wg3 SqAlpha` |
| `field_exhausted` | Aid station, stressed | `Martinez Carlos  Spc Alpha 7  WND` |
| `transit_manifest` | Transport hub | `MARTINEZ C    A/3/ALPHA  FLT7  SPC` |
| `depot_intake` | Processing depot | `Martinez, C.J., Spc, Element A, Wing 3, Squadron Alpha, Fleet 7, Defense Command` |
| `expeditionary_field` | Survey team, minimal | `Martinez  Team 4` |

---

## Vocabulary Layers (v4)

### 1. Situational Vocabulary (Signal-bearing)

Tied to operations and contexts within the Terraform Combine:

| Branch | Situations | Vocabulary |
|--------|------------|------------|
| Defense | Patrol ops, incursions, alerts | REDLINE, CONDITION-3, INTERCEPT, PERIMETER |
| Colonial | Founding, census, emergencies | FOUNDING, CENSUS-7, EVAC-NOTICE, HARVEST |
| Expeditionary | Surveys, contacts, discoveries | SURVEY-7, BEACON, CONTACT, UNCHARTED |
| Resource | Extraction, incidents, quotas | DEEPCORE, YIELD-12, INCIDENT, SHIFT-3 |

"DEEPCORE" in a record is a strong signal for Resource Directorate.

### 2. Contextual Clutter (Non-signal noise)

Tied to clerk's working environment:

| Clerk Context | Clutter Terms |
|---------------|---------------|
| Transit hub | Dk2, Bay-C, Berth-7, Hold3 |
| Medical | Ward3, Bed17, Intake-442 |
| Depot | Grp7, Ln23, Proc-2 |
| Local admin | Ref-447, File-C, Seq-12 |

### 3. Confounders (Deliberately ambiguous)

Terms that look like unit data but aren't:

| Confounder | Appears As | Could Be | Actually Is |
|------------|------------|----------|-------------|
| `A` | `...SPC A` | Element A | Berth A |
| `C-4` | `...Alpha C-4` | Squadron C, Wing 4 | Compartment C-4 |
| `7` | `...Martinez 7` | Fleet 7 | Processing group 7 |
| `??` | `...Team 4 ??` | Unknown unit | Clerk uncertainty mark |

---

## Within-Source Consistency

Unchanged from v3:

```yaml
within_source_behavior:
  format_consistency:
    identical_format_rate: 0.85
    minor_variation_rate: 0.12
    format_switch_rate: 0.03
  vocabulary_consistency:
    term_persistence: 0.95
  fatigue_modeling:
    enabled: true
```

---

## Quality Tiers

Unchanged from v3. Quality tier is assigned at source level:

| Tier | Description | Characteristics |
|------|-------------|-----------------|
| 1 | Pristine | Full hierarchy, clear formatting, no ambiguity |
| 2 | Good | Minor abbreviation, still parseable |
| 3 | Moderate | Significant abbreviation, some inference needed |
| 4 | Degraded | Heavy compression, structural inference required |
| 5 | Fragmentary | Minimal info, high ambiguity |

---

## Output Schema

### raw.parquet

| Column | Type | Description |
|--------|------|-------------|
| `source_id` | string | Manifest/page identifier |
| `soldier_id` | string | Ground truth soldier identifier |
| `state_id` | string | Ground truth state identifier |
| `raw_text` | string | Rendered manifest line |
| `clerk_id` | string | Clerk instance identifier |
| `situation_id` | string | Situation assigned to source |
| `quality_tier` | int | 1-5 quality level (source-level) |

### validation.parquet

| Column | Type | Description |
|--------|------|-------------|
| `soldier_id` | string | Soldier identifier |
| `state_id` | string | State identifier |
| `state_order` | int | Temporal position (1, 2, or 3) |
| `branch` | string | Branch (Colonial, Defense, Expeditionary, Resource) |
| `component_path` | string | Full path as string |
| Branch-specific columns | string | Level values for this branch |

### sources.parquet (NEW)

| Column | Type | Description |
|--------|------|-------------|
| `source_id` | string | Source identifier |
| `clerk_id` | string | Clerk who produced this source |
| `situation_id` | string | Operational situation |
| `home_unit` | string | Writer's organizational context (Level-3 path) |
| `quality_tier` | int | Quality tier for all records in source |

---

## Generator Responsibilities (v4)

### SoldierFactory
- Create soldiers with identity
- Determine state count (1, 2, or 3)
- Generate state_ids and assign posts to each state
- Apply transfer logic for multi-state soldiers

### SourceGenerator
- Create sources with clerk, situation, home_unit, temporal_anchor
- Assign quality tier at source level
- Enforce within-source consistency

### StateAssigner (NEW)
- For each (soldier, source) pair, determine which state to render
- Use source's temporal_anchor to select state
- Ensure soldier appears at most once per source

### FamiliarityCalculator (NEW)
- Compare soldier's state assignment to source's home_unit
- Return familiarity level (same-L3, same-L2, same-branch, different-branch)
- Feed to renderer for detail level selection

### Renderer
- Apply clerk's template
- Expand unit string based on familiarity level
- Apply imperfections based on position in batch

### VocabularyInjector
- Layer 1: Situational vocabulary from situation pool
- Layer 2: Contextual clutter from clerk context
- Layer 3: Confounders based on clerk context and rate

---

## Migration from v3

### Files Requiring Full Rewrite

| File | Reason |
|------|--------|
| `hierarchy_reference.json` | New domain (Terraform Combine branches) |
| `synthetic_vocabulary.json` | New situational terms, clutter, confounders |
| `synthetic_themes.json` | Branch-based themes replacing military themes |
| `seed_set.json` | New hand-crafted examples for calibration |

### Files Requiring Significant Update

| File | Changes |
|------|---------|
| `synthetic_style_spec.yaml` | Rename archetypes, update contexts, add familiarity spec |
| `soldier_factory.py` | Add state generation logic |
| `source_generator.py` | Add home_unit, temporal_anchor |
| `pipeline.py` | Wire state assignment, familiarity calculation |
| `renderer.py` | Familiarity-aware unit string expansion |

### Files Unchanged in Logic

| File | Notes |
|------|-------|
| Quality tier mechanics | Same system, new context |
| Within-source consistency | Identical logic |
| Fatigue modeling | Identical logic |
| Confounder injection rate | Same rates, new terms |

---

## Related Documents

- [ADR-004: Synthetic Data Redesign](../../../docs/adr/ADR-004-synthetic-data-redesign.md) — Decision record
- [DISAMBIGUATION_MODEL.md](../../../docs/DISAMBIGUATION_MODEL.md) — Core problem framing
- `hierarchy_reference.json` — Branch hierarchy definitions (to be created)
- `synthetic_vocabulary.json` — Vocabulary with layers (to be rewritten)

---

## Changelog

### v4.0.0 (2026-01-25)
- **Breaking:** Full domain change from WWII military to Terraform Combine
- **Breaking:** States explicit with `state_id` in all schemas
- **Feature:** Heterogeneous branch structures (3-5 levels)
- **Feature:** Familiarity gradient based on source home_unit
- **Feature:** Source-anchored state assignment
- **Feature:** 1-3 states per soldier (was 1-2)
- **Feature:** Cross-branch transfers
- **Reference:** ADR-004
