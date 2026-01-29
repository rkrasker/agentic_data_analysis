# Synthetic Data Generation

**Version:** 4.1.0  
**Last Updated:** 2026-01-29  
**Status:** Implemented (artifacts regenerated; difficulty-tier issue noted)

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
8. **Have measurable difficulty** — distinguish record quality from resolution difficulty

---

## v4.1 Philosophy: Three-Layer Difficulty Model

The v4.1 spec addresses a critical insight from ADR-006:

> **Record quality ≠ State resolution difficulty**

A pristine Tier-1 record saying "3rd Squadron" in a collision zone is **hard** to resolve.  
Three degraded Tier-5 records that are complementary may be **easy** to resolve.

### The Three Layers

| Layer | Question | Measured By | Example |
|-------|----------|-------------|---------|
| **1. Extraction** | Can we parse this record? | Quality tier (1-5) | Tier-1 = clear; Tier-5 = fragmentary |
| **2. Aggregation** | Do records jointly resolve? | Complementarity score | Records covering different levels = complementary |
| **3. Structural** | Do constraints disambiguate? | Structural resolvability | "Squadron" term → must be Defense Command |

### Why This Matters

**Previous assumption:** Filter toward degraded records to find "hard cases."

**Reality:** Hard cases are those where:
- Records are in collision zones (designators shared across units)
- Records are redundant (all provide the same partial path)
- No structural signals disambiguate

This can happen with **pristine** records. And easy cases can have **degraded** records if they're complementary.

---

## v4 Philosophy: Decontaminated Domain with Explicit States

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
- **Shared top level:** All branches use "Sector" as Level 1
- **Unique level names:** "Squadron" only in Defense; "Colony" only in Colonial; "Expedition" only in Expeditionary
- **Mixed designator types:** Names, numbers, letters, and ordinals depending on level and branch

### Collision Zones

Designators are deliberately shared across branches to create ambiguity:

| Designator | Possible Meanings |
|------------|-------------------|
| "7" | Fleet 7 (Defense), District 7 (Colonial), Facility 7 (Resource), Team 7 (Expeditionary) |
| "Alpha" | Squadron Alpha (Defense), Team Alpha (Expeditionary), Crew Alpha (Resource), Element Alpha (Defense) |
| "Kestrel" | Colony Kestrel (Colonial), Fleet Kestrel (Defense), Expedition Kestrel (Expeditionary) |
| "3" | Wing 3, Settlement 3, Crew 3, Team 3... |
| "A" | Element A, Crew A, Settlement A, Team A... |

A record saying "MARTINEZ CPL 7 ALPHA 3" is deeply ambiguous without additional signals.

---

## Three-Layer Difficulty Model (v4.1)

### Layer 1: Per-Record Extraction

**Question:** Can we extract unit information from this single document?

**Factors:**
- OCR quality / legibility
- Field completeness
- Explicit vs. abbreviated unit identifiers
- Clerk format consistency

**Measured by:** Quality tier (1-5)

**Where it matters:**
- Signal extraction from individual documents
- Deciding if a record is worth processing
- Training extraction models

### Layer 2: Cross-Record Aggregation

**Question:** Do this soldier's records jointly provide a globally unique component path?

**Key insight:** Two individually ambiguous records can be complementary:

| Record | Provides | Alone |
|--------|----------|-------|
| "Martinez  Kestrel 3" | Fleet + Squadron | Ambiguous (which wing/element?) |
| "MARTINEZ SPEC A" | Wing (letter) | Ambiguous (which fleet/squadron?) |
| "Martinez  Elem 7" | Element | Ambiguous (which unit?) |
| **Together** | Fleet/Squadron/Wing/Element | **UNIQUE PATH** |

Conversely, multiple records can be individually complete but jointly ambiguous:

| Record | Provides | Together |
|--------|----------|----------|
| "Martinez 3rd Sq, Wing A" | Squadron + Wing | Redundant |
| "Martinez 3rd Sq, Wing A" | Squadron + Wing | Still missing Fleet |
| **Together** | Same partial path | **COLLISION** (3rd Squadron exists in multiple fleets) |

**Measured by:** Complementarity score (0.0-1.0)

**Factors:**
- **Complementarity:** Do records provide different path segments?
- **Redundancy:** Do all records provide the same partial information?
- **Collision position:** Is the soldier's unit in a collision zone?
- **Signal density:** Do any records contain discriminating vocabulary?

**Where it matters:**
- Sampling for collision training (sample hard *soldiers*, not degraded *records*)
- Routing decisions (hard soldiers need strong differentiators)
- Evaluation stratification (accuracy by difficulty tier)

### Layer 3: Structural Inference

**Question:** Do hierarchy constraints disambiguate even when unit types are omitted?

**Structural signals:**

| Signal | Example | Inference |
|--------|---------|-----------|
| Depth constraint | 5-level path | Must be Defense Command |
| Level name uniqueness | "Squadron" | Only appears in Defense Command |
| Designator pattern | Greek letter | Sector level (all branches) |
| Designator pattern | 3-digit number | Can't be Element/Crew/Team |

**Example resolution:**

| Record | Analysis |
|--------|----------|
| "Martinez Squadron 7" | "Squadron" only in DC → Defense Command |
| **Structural inference** | Branch resolved without explicit branch label |

**Measured by:** Structural resolvability (boolean)

**Where it matters:**
- Resolver pattern generation (encode structural constraints)
- Disambiguation logic (apply constraints before declaring ambiguity)
- Synthetic generation (model which omissions are resolvable)

### Difficulty Tier Computation

Computed per-soldier after all records are generated:

| Tier | Description | Conditions | Expected Accuracy |
|------|-------------|------------|-------------------|
| **Easy** | At least one layer provides definitive resolution | Complete path in any record, OR complementary coverage, OR structural resolution | >95% |
| **Moderate** | Resolution requires combining signals but achievable | Partial coverage outside collision zone, OR collision zone with complementary records | 85-95% |
| **Hard** | Resolution requires subtle signals or inference | Collision zone + redundant records, OR cross-branch transfer with ambiguous designators | 70-85% |
| **Extreme** | Resolution may be impossible | Multiple states with cross-branch collision + redundant records + no structural resolution | <70% |

---

## Realism Gap / Known Limitations

The current synthetic generator still produces records that are **cleaner than real-world archival data**. Even with imperfections and confounders enabled, many entries look well-formed and fully legible.

### Why entries can look clean

- **Quality tier is source-level**, not per-entry: a tier-3 source can yield clean-looking records depending on randomized effects.
- **Imperfections are stochastic**: typos, abbreviation drift, corrections, and column bleed may not trigger on any given entry.
- **Clutter/confounders are bounded**: injected noise is intentionally sparse to avoid overwhelming signal extraction.

### Planned realism improvements

- Increase the frequency and severity of OCR-style corruption (character substitutions, truncation).
- Introduce more aggressive abbreviation inconsistency within a single entry.
- Expand clutter/confounder vocabulary and allow denser injections for specific archetypes.
- Add explicit “handwritten/ledger” formatting artifacts (column drift, misalignment, spillover).
- Continue iterating on label omission, value abbreviation, and delimiter mixing based on sample outputs.

This gap should be documented when interpreting downstream resolver performance: current synthetic data may under-represent the noise seen in real archival corpora.

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

---

## Collision Zone Tracking (v4.1)

### Concept

At post selection time, tag whether the post falls into a collision zone. A post is in a collision zone if its partial path (missing some levels) matches another post's partial path.

### Severity Levels

| Severity | Description | Example |
|----------|-------------|---------|
| **None** | Path is globally unique at all partial specifications | Colony Waystation (Waystation is CA-only) |
| **Low** | Collision only if 2+ levels omitted | Fleet Talon, 3rd Squadron (Talon is DC-only) |
| **Medium** | Collision if 1+ levels omitted | Fleet Kestrel, 3rd Squadron (Kestrel shared with CA) |
| **High** | Collision exists at most partial specifications | Fleet 7, Squadron A (7 and A both appear across branches) |
| **Cross-branch** | Designator collides across branches at same apparent level | Kestrel as Fleet vs Colony vs Expedition |

---

## Record Completeness Tracking (v4.1)

### Concept

After rendering each record, analyze which hierarchy levels are explicitly or implicitly present. This enables complementarity analysis.

### Fields Tracked

| Field | Type | Description |
|-------|------|-------------|
| `path_completeness` | float | Fraction of full path this record provides (0.0-1.0) |
| `levels_provided` | list[str] | Which hierarchy levels appear in record |
| `extraction_signals` | list[str] | Structural signals present (branch terms, depth clues) |

### Example

```
Branch: defense_command (depth 5)
Record: "Martinez Kestrel-3"
levels_provided: ["fleet", "squadron"]
path_completeness: 0.4  (2/5 levels)
extraction_signals: ["fleet_name_kestrel"]
```

---

## Output Schema (v4.1)

> **ADR-010 implemented (2026-01-29):** Core data and synthetic metadata are separated.
> - `raw.parquet` contains only production-equivalent fields.
> - `validation.parquet` contains only ground-truth labels.
> - Synthetic artifacts live in `synthetic_records.parquet` and `synthetic_soldiers.parquet`.
> - Ground-truth difficulty is computed post-hoc in `gt_difficulty.parquet`.

### raw.parquet

| Column | Type | Description |
|--------|------|-------------|
| `source_id` | string | Manifest/page identifier |
| `soldier_id` | string | Ground truth soldier identifier |
| `raw_text` | string | Rendered manifest line |

### validation.parquet

| Column | Type | Description |
|--------|------|-------------|
| `soldier_id` | string | Soldier identifier |
| `state_id` | string | State identifier |
| `state_order` | int | Temporal position (1, 2, or 3) |
| `branch` | string | Branch (Colonial, Defense, Expeditionary, Resource) |
| `post_path` | string | Full path as string |
| Branch-specific columns | string | Level values for this branch |

### synthetic_records.parquet

| Column | Type | Description |
|--------|------|-------------|
| `source_id` | string | Join key to raw records |
| `soldier_id` | string | Join key to soldiers |
| `state_id` | string | Ground-truth state for the record |
| `clerk_id` | string | Clerk instance identifier |
| `situation_id` | string | Situation assigned to source |
| `quality_tier` | int | 1-5 quality level (Layer 1) |
| `path_completeness` | float | Fraction of full path provided |
| `levels_provided` | list[str] | Hierarchy levels in this record |
| `extraction_signals` | list[str] | Structural signals present |

### synthetic_soldiers.parquet

| Column | Type | Description |
|--------|------|-------------|
| `soldier_id` | string | Soldier identifier |
| `gen_difficulty_tier` | string | Tier used to control generation |
| `gen_complementarity_score` | float | Complementarity at generation time |
| `gen_structural_resolvability` | bool | Resolvability at generation time |
| `target_state_count` | int | Number of states targeted |

### gt_difficulty.parquet

| Column | Type | Description |
|--------|------|-------------|
| `soldier_id` | string | Soldier identifier |
| `state_id` | string | State identifier (per-state metrics) |
| `gt_collision_zone_flag` | bool | Is this post in a collision zone? |
| `gt_collision_severity` | string | none/low/medium/high/cross_branch |
| `gt_complementarity_score` | float | 0.0-1.0 record complementarity |
| `gt_structural_resolvability` | bool | Can Layer 3 resolve? |
| `gt_difficulty_tier` | string | easy/moderate/hard/extreme |

### sources.parquet

| Column | Type | Description |
|--------|------|-------------|
| `source_id` | string | Source identifier |
| `clerk_id` | string | Clerk who produced this source |
| `situation_id` | string | Operational situation |
| `home_unit` | string | Writer's organizational context (Level-3 path) |
| `quality_tier` | int | Quality tier for all records in source |
| `temporal_anchor` | int | Which state-period this source captures |

---

## Difficulty-Aware Generation (v4.1)

### Target Distribution

| Tier | Target | Controls |
|------|--------|----------|
| Easy | 50% | Force complementary records, use non-collision posts |
| Moderate | 30% | Allow some collision, ensure some structural signals |
| Hard | 15% | Force collision zone + redundant records |
| Extreme | 5% | Cross-branch collision + minimal signals |

### Generation Controls

| Control | Description | Rate |
|---------|-------------|------|
| `force_collision_zone` | Place soldier in post with shared designators | 25% |
| `force_redundant_records` | Generate records with same partial path | 15% |
| `force_complementary_records` | Ensure records cover different levels | 40% |
| `force_cross_branch_collision` | Create hardest cross-branch cases | 5% |

### Rebalancing

After initial generation, if difficulty distribution doesn't match targets:
1. Regenerate records for some soldiers
2. Adjust which sources capture which soldiers
3. Modify clerk assignments

Tolerance: ±5% from targets.

---

## Generator Responsibilities (v4.1)

### SoldierFactory
- Create soldiers with identity
- Determine state count (1, 2, or 3)
- Generate state_ids and assign posts to each state
- **Tag collision zone membership at post assignment**
- Apply transfer logic for multi-state soldiers

### SourceGenerator
- Create sources with clerk, situation, home_unit, temporal_anchor
- Assign quality tier at source level
- Enforce within-source consistency

### StateAssigner
- For each (soldier, source) pair, determine which state to render
- Use source's temporal_anchor to select state
- Ensure soldier appears at most once per source

### FamiliarityCalculator
- Compare soldier's state assignment to source's home_unit
- Return familiarity level (same-L3, same-L2, same-branch, different-branch)
- Feed to renderer for detail level selection

### Renderer
- Apply clerk's template
- Expand unit string based on familiarity level
- Apply imperfections based on position in batch
- **Track levels_provided and path_completeness** (v4.1)

### CompletenessAnalyzer (v4.1 NEW)
- After rendering, analyze which levels are present
- Detect extraction_signals (branch-unique terms, structural clues)
- Compute path_completeness

### DifficultyComputer (v4.1 NEW)
- After all records generated, compute per-soldier **generation** difficulty (`gen_*`)
- Analyze collision zones across states
- Compute complementarity from levels_provided
- Determine structural resolvability from extraction signals
- Store outputs in `synthetic_soldiers.parquet`

### DifficultyRebalancer (v4.1 NEW)
- Compare actual difficulty distribution to targets
- Identify soldiers to regenerate
- Adjust source/clerk assignments
- Re-run generation for affected soldiers

### Known Issue: Difficulty Tier Saturation (All Easy)

Recent regeneration produced **100% easy** soldiers. Root cause appears to be universal full-path
records (`path_completeness >= 0.95` for every soldier), which triggers the `any_complete` shortcut
in `DifficultyComputer`. Structural signals also appear under-detected (abbreviation mismatch), and
the rebalancer currently does not mutate records. See:
- `.project_history/extracts/raw/2026-01-26_codex_difficulty-tier-all-easy-investigation.md`
- `SESSION_STATE.md` (Issues and Surprises)

---

## Evaluation Stratification (v4.1)

### Required Breakdowns

Accuracy should be reported by:
- Difficulty tier: easy / moderate / hard / extreme
- Collision zone: true / false
- State count: 1 / 2 / 3
- Branch: CA / DC / EC / RD

### Example Output

```
Component: defense_command
  Overall accuracy: 94.2%
  By difficulty:
    Easy soldiers:     98.1% (n=450)
    Moderate soldiers: 91.3% (n=120)
    Hard soldiers:     76.4% (n=55)
    Extreme soldiers:  42.9% (n=14)
```

### Alerts

- `hard_accuracy < 0.70`: Review resolver differentiators
- `extreme_accuracy < 0.40`: May require manual review or additional signals

---

## Quality Tiers (Layer 1 Only)

Quality tier measures **extraction difficulty**, not resolution difficulty.

| Tier | Name | Description | Clerk Bias |
|------|------|-------------|------------|
| 1 | archival_clean | Well-preserved, sector-level | sector_formal, processing_intake |
| 2 | standard | Typical operational, some wear | fleet_methodical, transport_shuttle |
| 3 | field_worn | Field conditions, rushed | fleet_rushed, field_medevac |
| 4 | degraded | Poor conditions, handwritten | field_exhausted, expeditionary_field |
| 5 | fragmentary | Heavily damaged, partial | field_exhausted, field_minimal |

**Important:** A Tier-1 record in a collision zone may be **harder** to resolve than a Tier-5 record with complementary partners.

---

## ADR-010 Schema Separation

### New Outputs

- `synthetic_records.parquet` (per-record generation metadata)
- `synthetic_soldiers.parquet` (per-soldier generation metrics, `gen_` prefix)
- `gt_difficulty.parquet` (ground-truth difficulty, `gt_` prefix)

### Column Moves

- `state_id`, `clerk_id`, `situation_id`, `quality_tier`, `path_completeness`,
  `levels_provided`, `extraction_signals` moved out of `raw.parquet`
- Difficulty metrics moved out of `validation.parquet` into `gt_difficulty.parquet`

### New Generator Components

- `CompletenessAnalyzer`: Analyze record coverage
- `DifficultyComputer`: Compute soldier-level difficulty
- `DifficultyRebalancer`: Hit target difficulty distribution

### Updated Generator Components

- `SoldierFactory`: Add collision zone tagging at post assignment
- `Renderer`: Track levels_provided during rendering

---

## Related Documents

- [ADR-006: Per-Record vs Per-Soldier Difficulty](../../../docs/adr/ADR-006_per-record-vs-per-soldier-difficulty.md) — Three-layer model origin
- [ADR-007: Synthetic Data Redesign](../../../docs/adr/ADR-007-synthetic-data-redesign.md) — Domain decontamination decision
- [DISAMBIGUATION_MODEL.md](../../../docs/DISAMBIGUATION_MODEL.md) — Core problem framing
- `synthetic_style_spec_v4.1.yaml` — Full specification

---

## Changelog

### v4.1.1 (2026-01-29)
- **Schema:** Separate core data from synthetic metadata (ADR-010)
- **Schema:** `raw.parquet` trimmed to production-equivalent fields only
- **Schema:** `validation.parquet` trimmed to ground-truth labels only
- **Feature:** Added `synthetic_records.parquet`, `synthetic_soldiers.parquet`, `gt_difficulty.parquet`
- **Feature:** Ground-truth difficulty computed post-hoc with `gt_` prefix

### v4.1.0 (2026-01-25)
- **Feature:** Three-layer difficulty model (extraction, aggregation, structural)
- **Feature:** Collision zone tracking at post selection
- **Feature:** Record completeness tracking (path_completeness, levels_provided)
- **Feature:** Soldier-level difficulty computation
- **Feature:** Difficulty-aware generation controls and rebalancing
- **Feature:** Evaluation stratification by difficulty tier
- **Schema:** Added difficulty columns to validation.parquet
- **Schema:** Added completeness columns to raw.parquet
- **Reference:** ADR-006

### v4.0.0 (2026-01-25)
- **Breaking:** Full domain change from WWII military to Terraform Combine
- **Breaking:** States explicit with `state_id` in all schemas
- **Feature:** Heterogeneous branch structures (3-5 levels)
- **Feature:** Familiarity gradient based on source home_unit
- **Feature:** Source-anchored state assignment
- **Feature:** 1-3 states per soldier (was 1-2)
- **Feature:** Cross-branch transfers
- **Reference:** ADR-007
