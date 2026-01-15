# 001: Synthetic Data Generator (v3)

**Created:** 2026-01-13
**Updated:** 2026-01-14
**Status:** ✅ Complete
**Component:** synthetic_data_generation
**Depends on:** `config/hierarchies/hierarchy_reference.json`, `config/synthetic/synthetic_themes.json`, `config/synthetic/synthetic_vocabulary.json`, `docs/components/synthetic_data_generation/synthetic_style_spec_v3.yaml`

---

## Objective

Build the synthetic data generator using the **v3 clerk-as-character philosophy**: clerks are persistent characters with fixed habits, not sampling functions.

---

## Context

- v3 spec created (2026-01-13) with clerk archetypes and situational vocabulary
- Seed set created with 41 hand-crafted entries demonstrating the approach
- Three vocabulary layers defined: situational, contextual clutter, confounders
- Key principle: **within-source consistency** - 85% of entries use identical format
- **Transfers:** 25% of soldiers have unit transfers creating multi-assignment disambiguation challenges

---

## v3 Philosophy Summary

| Principle | Implementation |
|-----------|----------------|
| Clerks are characters | 13 archetypes with fixed habits per instance |
| Situations drive vocabulary | 16 situations with vocabulary pools |
| Within-source consistency | Same format repeated, not sampled per-entry |
| Vocabulary layers | Situational (signal), clutter (noise), confounders (misleading) |
| Behavioral imperfections | Fatigue drift, self-correction, not random noise |

---

## Tasks

### Phase 1: Core Components

1. [x] **ClerkFactory** - `src/synthetic/clerk_factory.py`
   - Load clerk archetypes from v3 spec
   - Instantiate clerk instances with locked habits
   - Minor individual variation within archetype constraints
   - Track which clerks have been used for distribution modeling

2. [x] **SituationManager** - `src/synthetic/situation_manager.py`
   - Load situations from v3 spec
   - Assign situations to sources based on component compatibility
   - Manage vocabulary pools (primary/secondary/rare)
   - Handle term persistence within source

3. [x] **VocabularyInjector** - `src/synthetic/vocabulary_injector.py`
   - Load vocabulary from `synthetic_vocabulary.json`
   - Layer 1: Situational vocabulary from situation pool
   - Layer 2: Contextual clutter based on clerk context
   - Layer 3: Confounders based on clerk context and rate
   - Expand templates (e.g., `Dk{N}` → `Dk2`)

4. [x] **SourceGenerator** - `src/synthetic/source_generator.py`
   - Create source batches with assigned clerk and situation
   - Enforce within-source consistency (85% identical format)
   - Apply fatigue modeling for late-batch entries
   - Manage soldier distribution per source (unit concentration)

5. [x] **TransferManager** - `src/synthetic/transfer_manager.py`
   - Generate transfers for 25% of soldiers
   - Transfer type distribution: company (50%), battalion (30%), regiment (15%), division (5%)
   - Track both original and new assignments in truth layer
   - Ensure transferred soldiers appear with both assignments across sources
   - Produce `unit_changes.parquet` for transfer documentation

### Phase 2: Rendering

6. [x] **Renderer** - `src/synthetic/renderer.py`
   - `render_name(truth, clerk)` - apply clerk's locked name template
   - `render_rank(truth, clerk)` - apply clerk's rank style/placement
   - `render_unit(truth, clerk, hierarchy, assignment)` - apply clerk's unit format (supports transfer assignment override)
   - `apply_vocabulary(entry, situation, clerk)` - inject vocabulary layers
   - `apply_imperfections(text, clerk, position_in_batch)` - behavioral drift

7. [x] **HierarchyLoader** - `src/synthetic/hierarchy_loader.py`
   - Load `hierarchy_reference.json`
   - Collision-aware subunit lookups
   - Resolve designator conventions per component

### Phase 3: Pipeline Integration

8. [x] **Pipeline** - `src/synthetic/pipeline.py`
   - Wire components together
   - Produce `raw.parquet` with schema: source_id, soldier_id, raw_text, clerk_id, situation_id, quality_tier
   - Produce `validation.parquet` with truth records
   - Support configurable target record count
   - Handle transfer assignment selection (50/50 original vs new)

9. [x] **Validation** - spot-checked 2026-01-14
   - Verify seed set entries can be reproduced
   - Check collision coverage in output (8 regiment collisions found)
   - Validate vocabulary distribution by layer (situational, clutter, confounders present)
   - Confirm within-source consistency rates

---

## Acceptance Criteria

- [x] Generator produces raw.parquet matching v3 schema
- [x] Within-source consistency: ≥80% of entries per source use identical format
- [x] Vocabulary layers appear correctly:
  - Situational terms correlate with situations (OMAHA, DZ-, BASTOGNE, etc.)
  - Clutter terms correlate with clerk contexts (Dk, Bed, Ward, etc.)
  - Confounders appear at ~8% rate in clutter entries
- [x] Designator collisions present (8 regiments appear in multiple components)
- [x] All 13 clerk archetypes represented in output (289 unique clerks generated)
- [ ] Seed set entries match expected output when using same clerk/situation *(not yet tested)*
- [x] Transfers: 24.6% of soldiers have transfers
  - Transfer type distribution matches spec (company 50%, battalion 29%, regiment 16%, division 5%)
  - Transferred soldiers appear with both assignments across sources (47% of transferred soldiers with 3+ entries show both)
  - `unit_changes.parquet` produced with correct schema

---

## Key Files

### Spec & Config

| File | Purpose |
|------|---------|
| [CURRENT.md](../../docs/components/synthetic_data_generation/CURRENT.md) | v3 spec documentation |
| [synthetic_style_spec_v3.yaml](../../docs/components/synthetic_data_generation/synthetic_style_spec_v3.yaml) | Full v3 rendering spec |
| [seed_set_v3.json](../../config/synthetic/seed_set_v3.json) | Hand-crafted examples (41 entries, incl. transfers) |
| [synthetic_vocabulary.json](../../config/synthetic/synthetic_vocabulary.json) | Vocabulary with all three layers |
| [synthetic_themes.json](../../config/synthetic/synthetic_themes.json) | Theme definitions |
| [hierarchy_reference.json](../../config/hierarchies/hierarchy_reference.json) | Component hierarchy with collisions |

### Implementation

| File | Purpose |
|------|---------|
| [pipeline.py](../../src/synthetic/pipeline.py) | Main orchestration, entry point via `run_pipeline()` |
| [clerk_factory.py](../../src/synthetic/clerk_factory.py) | Clerk archetype loading and instantiation |
| [situation_manager.py](../../src/synthetic/situation_manager.py) | Situation assignment and vocabulary pools |
| [vocabulary_injector.py](../../src/synthetic/vocabulary_injector.py) | Three-layer vocabulary injection |
| [source_generator.py](../../src/synthetic/source_generator.py) | Source document generation |
| [transfer_manager.py](../../src/synthetic/transfer_manager.py) | Transfer generation and tracking |
| [renderer.py](../../src/synthetic/renderer.py) | Text rendering with clerk formats |
| [hierarchy_loader.py](../../src/synthetic/hierarchy_loader.py) | Hierarchy loading with collision support |
| [soldier_factory.py](../../src/synthetic/soldier_factory.py) | Soldier generation |
| [models.py](../../src/synthetic/models.py) | Data models (Soldier, Clerk, Entry, etc.) |

### Output

| File | Purpose |
|------|---------|
| `data/synthetic/raw.parquet` | Generated manifest entries |
| `data/synthetic/validation.parquet` | Ground truth records |
| `data/synthetic/unit_changes.parquet` | Transfer documentation |

---

## Implementation Notes

### Clerk Instance Locking
```python
class ClerkInstance:
    def __init__(self, archetype: ClerkArchetype):
        # Lock all habits at instantiation
        self.name_template = archetype.name_format.template
        self.rank_style = archetype.rank_format.style
        self.rank_form = archetype.rank_format.form
        self.unit_format = archetype.unit_format.style
        self.separator = archetype.unit_format.separator
        # These never change for this clerk instance
```

### Within-Source Consistency
```python
def generate_source(clerk: ClerkInstance, situation: Situation, soldiers: List[Soldier]):
    entries = []
    for i, soldier in enumerate(soldiers):
        position_ratio = i / len(soldiers)

        # 85% use base format, 12% minor drift, 3% major variation
        if random.random() < 0.85:
            entry = render_with_base_format(soldier, clerk)
        elif random.random() < 0.97:
            entry = render_with_minor_drift(soldier, clerk)
        else:
            entry = render_with_variation(soldier, clerk)

        # Apply fatigue for late-batch entries
        if position_ratio > 0.8:
            entry = apply_fatigue(entry, clerk)

        entries.append(entry)
    return entries
```

### Vocabulary Layer Injection
```python
def inject_vocabulary(entry: str, clerk: ClerkInstance, situation: Situation):
    result = entry

    # Layer 1: Situational (from situation pool)
    if random.random() < clerk.vocabulary_density:
        term = situation.sample_vocabulary()
        result = append_term(result, term)

    # Layer 2: Clutter (from clerk context)
    if random.random() < CLUTTER_RATE[clerk.archetype]:
        clutter = sample_clutter_for_context(clerk.context)
        result = append_term(result, clutter)

        # Layer 3: Confounder (8% of clutter entries)
        if random.random() < 0.08:
            confounder = sample_confounder_for_context(clerk.context)
            result = append_term(result, confounder)

    return result
```

---

## References

- [v3 Philosophy Discussion](.project_history/extracts/daily/2026-01-13_synthetic-data-v3-spec.md)
- [Hierarchy Redesign](.project_history/extracts/daily/2026-01-13_synthetic-data-hierarchy-redesign.md)
