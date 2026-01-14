# Synthetic Data Generation

**Version:** 3.0.0
**Last Updated:** 2026-01-13

---

## Purpose

Generate synthetic military manifest records that:
1. Resemble archival capture artifacts (compressed shorthand, inconsistent formatting)
2. Contain realistic ambiguity and confounders
3. Have learnable signals linking language to component categories
4. Force multi-signal disambiguation (no single-feature classification)
5. Are reproducible and comparable across experiments
6. **Feel organic** - written by humans, not sampled from probability distributions

---

## v3 Philosophy: Clerks as Characters

The v3 spec fundamentally changes how synthetic data is generated:

| v2 Approach | v3 Approach |
|-------------|-------------|
| Sample template per-entry with weights | Clerk has ONE template, uses it every time |
| `component_affinities` with flavor tokens | Situations drive vocabulary naturally |
| `source_profiles` as config objects | Clerk archetypes as **characters** with habits |
| Random noise profiles | Behavioral imperfections (fatigue, self-correction) |
| Random separator sampling | Clerk always uses their separator |
| Quality tier affects per-entry probabilities | Quality tier assigned to **source**, affects whole batch |
| Uniform variation within sources | 85% of entries in a source use **identical format** |

**Key insight:** Real clerks don't sample from probability distributions. They develop habits, stick with what works, and write the same way for dozens of entries in a row.

---

## Architecture: Truth vs Rendering

### Truth Layer
Represents "what the soldier is":
- Identity (primary_id, canonical name parts)
- Canonical assignment (division/regiment/battalion/company)
- Component classification (component_id)

Truth is stable and not required to look like a document.

### Rendering Layer
Represents "how it got written down":
- **Clerk character** (archetype with fixed habits)
- **Situation** (operational context driving vocabulary)
- **Within-source consistency** (same format repeated)
- **Vocabulary layers** (situational, clutter, confounders)
- **Behavioral imperfections** (fatigue drift, self-correction)

Multiple raw lines can correspond to the same truth record, rendered by different clerks.

---

## File Structure

### LLM-Facing Files (may be provided to parsing LLM)

| File | Location | Purpose |
|------|----------|---------|
| `hierarchy_reference.json` | `config/hierarchies/` | Canonical component hierarchy with collisions |

### Generation-Only Files (never provided to parsing LLM)

| File | Location | Purpose |
|------|----------|---------|
| `synthetic_themes.json` | `config/synthetic/` | Theme definitions (31 themes) |
| `synthetic_vocabulary.json` | `config/synthetic/` | Terms with layers: situational, clutter, confounders |
| `synthetic_style_spec_v3.yaml` | `docs/components/synthetic_data_generation/` | v3 clerk-as-character rendering spec |
| `seed_set_v3.json` | `config/synthetic/` | Hand-crafted calibration examples (38 entries) |

### Deprecated Files

| File | Location | Notes |
|------|----------|-------|
| `synthetic_style_spec_v2.yaml` | `deprecated/` | v2 sampling-based approach |
| `README_synthetic_workflow.md` | `deprecated/` | Superseded by this document |
| `AGENT_BUILD_INSTRUCTIONS.md` | `deprecated/` | Superseded by instruction 001 |

---

## Clerk Archetypes

Clerks are defined as persistent characters with fixed behavioral patterns:

| Archetype | Context | Example Output |
|-----------|---------|----------------|
| `hq_formal` | Division HQ, trained on forms | `S/Sgt Kowalski, Stanley J.  Co E, 2nd Bn, 16th Inf, 1st Div` |
| `hq_efficient` | Experienced HQ, efficient | `Kowalski, S.J.  E/2/116/29ID` |
| `battalion_rushed` | S-1 under pressure | `KOWALSKI SSGT E2-16` |
| `battalion_methodical` | Careful battalion clerk | `Kowalski, Stanley  E Co 2Bn 116Inf` |
| `field_exhausted` | Field hospital, stressed | `Kowalski Stanley  SSgt Easy Co 16  WIA` |
| `field_medevac` | Medical evacuation | `KOWALSKI, S.  116th  WIA` |
| `transport_ship` | Ship manifest | `KOWALSKI S    116/2/E  29ID  SSG` |
| `transport_air` | Troop carrier manifest | `S/Sgt Kowalski, Stanley J.  Co E, 2nd Bn, 505th PIR, 82nd AB  CHK-42` |
| `repldep_intake` | Replacement depot | `Kowalski, S.J., SSgt, Co E, 2nd Bn, 116th Inf Regt, 29th Inf Div` |
| `aaf_squadron` | Squadron-level AAF | `Kowalski, Stanley J.  3rd Sq, 91st BG, 8th AF` |
| `aaf_operations` | Group ops, mission tracking | `Kowalski, S.J.  91BG-322  SSGT  B-17` |
| `marine_fmf` | Fleet Marine Force | `Kowalski, Stanley J.  Co E, 2nd Bn, 1st Mar, 1st MarDiv` |
| `marine_shipboard` | Marine transport | `KOWALSKI S    E/2/1  1MARDIV  SGT` |

A clerk's style is **LOCKED** for all entries they produce. No per-entry sampling.

---

## Situations

Situations define operational context that drives vocabulary selection:

| Situation | Theater | Components | Key Vocabulary |
|-----------|---------|------------|----------------|
| `normandy_assault` | ETO | 1st ID, 29th ID | OMAHA, UTAH, LST, LCVP |
| `normandy_airborne` | ETO | 82nd AB, 101st AB | DZ-O, DZ-N, CHK-42, C-47 |
| `bulge_defensive` | ETO | 82nd AB, 101st AB | BASTOGNE, ABN |
| `eto_breakout` | ETO | 2nd AD, 1st ID | COBRA, ARMD, TK |
| `italy_anzio` | MTO | 36th ID, 1st AD | SALERNO, ANZIO, RAPIDO |
| `italy_mountain` | MTO | 10th Mtn | RIVA, BELVEDERE, MTN, SKI |
| `guadalcanal` | PTO | 1st MarDiv | LUNGA, RED-1, USMC, FMF |
| `tarawa` | PTO | 2nd MarDiv | BETIO, RED-2, LVT |
| `iwo_jima` | PTO | 3rd MarDiv | SURIBACHI, GREEN-1 |
| `eighth_af_strategic` | ETO | 8th AF | B-17, B-24, STATION-121 |
| `fifteenth_af_mediterranean` | MTO | 15th AF | FOGGIA, BARI |
| `ninth_af_tactical` | ETO | 9th AF | A-26, STATION-416 |

A source is assigned ONE situation. All entries share situational vocabulary.

---

## Vocabulary Layers

Vocabulary is NOT randomly sampled. It appears based on three distinct sources:

### 1. Situational Vocabulary (Signal-bearing)
- Tied to the operation/situation assigned to the source
- Provides disambiguation signals (OMAHA = 1st ID Normandy, DZ-O = 82nd AB)
- **Helps the parser** identify component

### 2. Contextual Clutter (Non-signal noise)
- Tied to the clerk's working environment, not the soldier's unit
- Ship clerks add deck/berth codes; hospital clerks add ward/bed numbers
- **Does NOT help** disambiguation

| Clerk Context | Clutter Terms |
|---------------|---------------|
| `transport_ship` | Dk2, Hold3, Bth-C, Bay4 |
| `field_medevac` | Ward3, Bed17, Adm442 |
| `aaf_operations` | AC847, Pos3, Msn142 |
| `repldep_intake` | Grp7, Ln23, Sec-2 |

### 3. Confounders (Deliberately ambiguous)
- Terms that LOOK like unit data but aren't
- Forces parser to use context, not pattern matching
- **Actively misleads** if parsed naively

| Confounder | Appears As | Could Be | Actually Is |
|------------|------------|----------|-------------|
| `A` | `...SGT A` | Company A | Berth A |
| `C-4` | `...E2-16 C-4` | C Co, 4th Bn | Compartment C-4 |
| `2A` | `...505th PIR 2A` | 2nd Co, A Bn | Boarding group |
| `??` | `...Fox 16 ??` | Unknown | Clerk uncertainty |

---

## Within-Source Consistency

This is the key differentiator from v2:

```yaml
within_source_behavior:
  format_consistency:
    identical_format_rate: 0.85  # 85% exactly the same
    minor_variation_rate: 0.12   # spacing, caps drift
    format_switch_rate: 0.03     # rare: different approach

  vocabulary_consistency:
    term_persistence: 0.95       # if OMAHA once, OMAHA throughout

  fatigue_modeling:
    enabled: true
    # Clerk gets sloppier over course of batch
```

Variation happens **between sources**, not **within them**.

---

## Seed Set

Hand-crafted examples in `config/synthetic/seed_set_v3.json`:

| Statistic | Count |
|-----------|-------|
| Soldiers | 13 |
| Sources (clerks) | 6 |
| Total entries | 41 |
| Collision cases | 5 |
| Clutter examples | 8 |
| Confounder examples | 4 |
| Transfer cases | 1 |

Demonstrates:
- Same soldier rendered by different clerks
- Within-source consistency
- Collision disambiguation
- All three vocabulary layers
- Transfer disambiguation challenge (same soldier, different valid units)

---

## Collision Design

Designators are deliberately shared across components to force disambiguation:

| Collision Type | Example | Components |
|----------------|---------|------------|
| Cross-branch | Regiment 1 | 1st ID, 2nd ID, 101st AB, 1st MarDiv, 36th ID |
| Within-branch | Regiment 5 | 1st ID, 3rd ID, 82nd AB, 1st MarDiv, 10th Mtn |
| Battalion alpha | A | 82nd AB, 101st AB, 1st AD, 2nd AD |

Parser must combine (designator, unit_type) with additional signals.

---

## Soldier Transfers

25% of soldiers have a unit transfer in their history. This creates the hardest disambiguation cases: the same soldier legitimately appears with different unit assignments across sources.

### Transfer Type Distribution

| Type | Frequency | Example |
|------|-----------|---------|
| company_level | 50% | E Co → F Co within 2nd Bn |
| battalion_level | 30% | 2nd Bn → 3rd Bn within 16th Inf |
| regiment_level | 15% | 16th Inf → 18th Inf within 1st ID |
| division_level | 5% | 1st ID → 29th ID via replacement depot |

### Key Constraints

- **Undated documents**: No temporal consistency to rely on
- **Both assignments valid**: Truth layer tracks both, parser must recognize both as correct
- **No clerk awareness**: Clerks record what they see, don't note "formerly Co E"
- **No cross-branch**: Army ↔ Marines transfers not modeled

### Disambiguation Challenge

For a transferred soldier:
```
Source A (HQ): "S/Sgt Kowalski, Stanley J.  Co E, 2nd Bn, 16th Inf, 1st Div"
Source B (rushed): "KOWALSKI SSGT F3-16"
```

Without dates, parser cannot distinguish:
- Parsing error (E vs F, 2nd vs 3rd)?
- Valid transfer (both correct)?
- Two different Kowalskis?

This is exactly what makes the real data hard.

---

## Generator Responsibilities (v3)

### ClerkFactory
- Instantiate clerks from archetypes
- Lock habits for duration of clerk's batch
- Apply minor individual variation within archetype constraints

### SituationManager
- Assign situations to sources based on component
- Manage vocabulary pools (primary/secondary/rare)
- Handle term persistence within source

### SourceGenerator
- Create source batches with assigned clerk and situation
- Enforce within-source consistency
- Apply fatigue modeling for late-batch entries

### VocabularyInjector
- Layer 1: Situational vocabulary from situation pool
- Layer 2: Contextual clutter from clerk context
- Layer 3: Confounders based on clerk context and rate

### Renderer
- Apply clerk's locked style to each entry
- `render_name(truth, clerk)` - clerk's name template
- `render_rank(truth, clerk)` - clerk's rank style
- `render_unit(truth, clerk)` - clerk's unit format
- `apply_imperfections(text, clerk, position_in_batch)` - behavioral drift

---

## Output Schema

### raw.parquet / raw.csv

| Column | Type | Description |
|--------|------|-------------|
| `source_id` | string | Manifest/page identifier |
| `soldier_id` | string | Ground truth soldier identifier |
| `raw_text` | string | Rendered manifest line |
| `clerk_id` | string | Clerk instance identifier |
| `situation_id` | string | Situation assigned to source |
| `quality_tier` | int | 1-5 quality level (source-level) |

### validation.parquet

| Column | Type | Description |
|--------|------|-------------|
| `primary_id` | string | Soldier identifier |
| `component_id` | string | Ground truth component |
| `name_first` | string | First name |
| `name_middle` | string | Middle name/initial |
| `name_last` | string | Last name |
| `rank` | string | Canonical rank |
| Unit fields vary by component type |

---

## Related Documents

- [synthetic_style_spec_v3.yaml](synthetic_style_spec_v3.yaml) - Full v3 rendering spec
- [seed_set_v3.json](../../config/synthetic/seed_set_v3.json) - Hand-crafted examples
- [synthetic_vocabulary.json](../../config/synthetic/synthetic_vocabulary.json) - Vocabulary with layers
- [synthetic_themes.json](../../config/synthetic/synthetic_themes.json) - Theme definitions
- [hierarchy_reference.json](../../config/hierarchies/hierarchy_reference.json) - Component hierarchy

---

## Changelog

### v3.0.1 (2026-01-13)
- Added soldier transfers specification (25% of soldiers, 4 transfer types)
- Updated seed_set_v3.json with transfer demonstration (S013 Brennan)
- Updated data-structures/CURRENT.md with transfer type distribution

### v3.0.0 (2026-01-13)
- **Philosophy change:** Clerks as characters, not sampling functions
- Added 13 clerk archetypes with fixed behavioral patterns
- Added 16 situations driving vocabulary selection
- Added vocabulary layers: situational, contextual clutter, confounders
- Added within-source consistency (85% identical format)
- Added behavioral imperfections (fatigue, self-correction, drift)
- Created seed_set_v3.json with 41 hand-crafted entries
- Updated synthetic_vocabulary.json with clutter and confounder terms

### v2.0.1 (2026-01-13)
- Unified component_type to `division`
- Added `subtype` specificity level for themes

### v2.0.0 (2026-01-13)
- Redesigned hierarchy with deliberate designator collisions
- Split into three files: hierarchy_reference, synthetic_themes, synthetic_vocabulary

### v1.0.0 (2026-01-11)
- Initial synthetic data generation system
