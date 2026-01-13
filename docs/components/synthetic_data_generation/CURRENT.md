# Synthetic Data Generation

**Version:** 2.0.0
**Last Updated:** 2026-01-13

---

## Purpose

Generate synthetic military manifest records that:
1. Resemble archival capture artifacts (compressed shorthand, inconsistent formatting)
2. Contain realistic ambiguity and confounders
3. Have learnable signals linking language to component categories
4. Force multi-signal disambiguation (no single-feature classification)
5. Are reproducible and comparable across experiments

---

## Architecture: Truth vs Rendering

### Truth Layer
Represents "what the soldier is":
- Identity (primary_id, canonical name parts)
- Canonical assignment (division/regiment/battalion/company)
- Component classification (component_id)
- Optional dynamics (ID changes, unit transfers)

Truth is stable and not required to look like a document.

### Rendering Layer
Represents "how it got written down":
- Clerk/source style (source_profile)
- Shorthand dialect (slash vs run-on vs labeled)
- Token placement (templates)
- Ambiguity injection (confounders)
- Capture noise (spacing jitter, OCR confusions, truncation)

Multiple raw lines can correspond to the same truth record.

---

## File Structure

### LLM-Facing Files (may be provided to parsing LLM)

| File | Location | Purpose |
|------|----------|---------|
| `hierarchy_reference.json` | `config/hierarchies/` | Canonical component hierarchy with subunits, designator conventions, and aliases |

### Generation-Only Files (never provided to parsing LLM)

| File | Location | Purpose |
|------|----------|---------|
| `synthetic_themes.json` | `config/synthetic/` | Theme definitions driving vocabulary selection |
| `synthetic_vocabulary.json` | `config/synthetic/` | Injectable terms with theme associations |
| `synthetic_style_spec_v2.yaml` | `docs/components/synthetic_data_generation/` | Rendering rules, templates, noise profiles |
| `seed_set_v2.jsonl` | `docs/components/synthetic_data_generation/` | Calibration examples |

---

## Hierarchy Reference Schema

```
hierarchy_reference.json
├── meta
│   ├── version
│   └── description
├── components
│   └── {component_id}
│       ├── component_id
│       ├── component_type (infantry_division, airborne_division, marine_division, armored_division, mountain_division, air_force)
│       ├── canonical_name
│       ├── service_branch (army, marines, army_air_forces)
│       ├── aliases[]
│       │   ├── alias_id
│       │   ├── alias_name
│       │   ├── alias_type (informal, redesignation, reassignment, type_reclassification)
│       │   └── period {start, end}
│       ├── organizational_structure
│       │   ├── hierarchy_pattern
│       │   └── levels
│       │       └── {level_name}
│       │           ├── designator_convention
│       │           └── designators[]
│       └── known_subordinate_units
│           └── {unit_type}[]
│               ├── designator
│               ├── unit_type
│               └── canonical_name
└── collision_index
    ├── regiment_collisions
    ├── battalion_collisions
    └── cross_branch_collisions
```

### Designator Conventions

| Convention | Description | Example |
|------------|-------------|---------|
| `numeric_sequential` | Consecutive integers | 1, 2, 3, 4 |
| `numeric_discrete` | Non-consecutive set | 1, 5, 7 |
| `alpha_sequential` | Letters in order | A, B, C, D, E, F, G, H |
| `alpha_gapped` | Letters with military gaps | A-M, no J |
| `alpha_discrete` | Arbitrary letter subset | A, B, R |

### Collision Design

Designators are deliberately shared across components to force disambiguation:
- **Cross-branch**: Regiment 1 exists in army infantry, army airborne, and marines
- **Within-branch**: Regiment 5 exists in multiple army divisions

The parser must combine (designator, unit_type) with additional signals.

---

## Themes Schema

```
synthetic_themes.json
├── meta
├── theme_types
│   └── {type}: description
├── specificity_levels
│   └── {level}: description
└── themes[]
    ├── theme_id
    ├── theme_type (operational_context, logistics, administrative, organizational, equipment, geographic)
    ├── specificity (universal, service, type, component)
    ├── applies_to
    │   ├── service_branch[] (if specificity=service)
    │   ├── component_type[] (if specificity=type)
    │   └── component_id[] (if specificity=component)
    └── description
```

---

## Vocabulary Schema

```
synthetic_vocabulary.json
├── meta
├── term_types
│   └── {type}: description
├── frequency_weights
│   └── common/uncommon/rare: weight
└── vocabulary[]
    ├── term
    ├── term_type (transport_code, equipment_code, zone_designator, manifest_code, admin_code, status_code, base_code, position_code, process_code)
    ├── theme_ref
    ├── specificity (universal, service, type, component)
    ├── frequency (common, uncommon, rare)
    ├── context
    └── placement[] (suffix, infix)
```

### Signal Gradient

| Specificity | Signal Strength | Example Terms |
|-------------|-----------------|---------------|
| `universal` | None | HQ, DET, WIA |
| `service` | Branch-level | USMC, AAF, AGF |
| `type` | Component-type | ABN, TK, FMF, C-47 |
| `component` | Specific component | DZ-O, OMAHA, FOGGIA |

---

## Disambiguation Flow

When the parser encounters ambiguous raw text:

```
Raw text: "B/2/5INF"

1. Extract (designator, unit_type) pairs:
   → (B, company), (2, battalion), (5, regiment)

2. Query hierarchy for (5, regiment):
   → Candidates: 1st ID, 3rd ID, 82nd AB, 1st MarDiv, 10th Mtn

3. Apply structural filters:
   - Battalion convention: numeric → excludes 82nd AB (uses alpha)
   - Company convention: alpha → consistent with all remaining

4. Apply vocabulary signals:
   - Presence of "USMC" → 1st MarDiv
   - Presence of "ABN" → (already excluded)
   - Presence of "MTN" → 10th Mtn
   - No branch signal → army infantry candidates remain

5. Final assignment or explicit ambiguity
```

---

## Generator Responsibilities

### SpecLoader
- Parse YAML style spec
- Expose distributions, templates, source profiles, noise profiles

### SourceContextManager
- Sample source_id batches
- Assign/reuse source_profile per source (clerk clustering)

### HierarchyLoader
- Load `hierarchy_reference.json`
- Provide collision-aware subunit lookups

### ThemeVocabularyLoader
- Load themes and vocabulary
- Sample terms based on component affinity and frequency weights

### Renderer
- `render_name(truth, quality_tier, profile)`
- `render_rank(truth, profile)`
- `render_unit(truth, profile, component_type)`
- `render_extra(component_id, theme_affinities)`
- `apply_noise(text, noise_profile, quality_tier)`

---

## Output Schema

### raw.parquet / raw.csv

| Column | Type | Description |
|--------|------|-------------|
| `source_id` | string | Manifest/page identifier |
| `soldier_id` | string | Ground truth soldier identifier |
| `raw_text` | string | Rendered manifest line |
| `quality_tier` | int | 1-5 quality level |
| `pattern_tier` | string | A/B/C pattern classification |
| `has_error` | bool | Contains injected error |
| `has_confounding` | bool | Contains confounder snippet |

### validation.parquet

| Column | Type | Description |
|--------|------|-------------|
| `primary_id` | string | Soldier identifier |
| `component_id` | string | Ground truth component |
| `name_first` | string | First name |
| `name_middle` | string | Middle name/initial |
| `name_last` | string | Last name |
| `rank` | string | Canonical rank |
| `division` | string | Division name |
| `regiment` | string | Regiment designator |
| `battalion` | string | Battalion designator |
| `company` | string | Company designator |
| `squadron` | string | Squadron designator (air force) |
| `bomb_group` | string | Bomb group designator (air force) |

---

## Related Documents

- [README_synthetic_workflow.md](README_synthetic_workflow.md) - Original workflow overview
- [synthetic_style_spec_v2.yaml](synthetic_style_spec_v2.yaml) - Rendering rules
- [seed_set_v2.jsonl](seed_set_v2.jsonl) - Calibration examples
- [AGENT_BUILD_INSTRUCTIONS.md](AGENT_BUILD_INSTRUCTIONS.md) - Implementation guide

---

## Changelog

### v2.0.0 (2026-01-13)
- Redesigned hierarchy with deliberate designator collisions
- Split into three files: hierarchy_reference, synthetic_themes, synthetic_vocabulary
- Added designator convention variation across components
- Added structured alias support for temporal naming variations
- Added signal gradient vocabulary (universal → component-specific)
- Moved hierarchy to `config/hierarchies/`, generation files to `config/synthetic/`

### v1.0.0 (2026-01-11)
- Initial synthetic data generation system
- Historically accurate WW2 unit hierarchies
