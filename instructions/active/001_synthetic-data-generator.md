# 001: Synthetic Data Generator

**Created:** 2026-01-13
**Component:** synthetic_data_generation
**Depends on:** `config/hierarchies/hierarchy_reference.json`, `config/synthetic/synthetic_themes.json`, `config/synthetic/synthetic_vocabulary.json`

---

## Objective

Build the synthetic data generator that renders ground truth soldier records into manifest-like raw text, using the new hierarchy and vocabulary structures.

---

## Context

- Hierarchy redesign completed (2026-01-13) with deliberate designator collisions
- Three reference files now in `config/`: hierarchy_reference.json, synthetic_themes.json, synthetic_vocabulary.json
- Old generator artifacts deprecated in `docs/components/synthetic_data_generation/deprecated/`
- See `docs/components/synthetic_data_generation/CURRENT.md` for full spec

---

## Tasks

1. [ ] Create `SpecLoader` - parse style spec YAML (needs new style spec or update deprecated one)
2. [ ] Create `HierarchyLoader` - load hierarchy_reference.json with collision-aware lookups
3. [ ] Create `ThemeVocabularyLoader` - load themes/vocabulary, sample by affinity and frequency
4. [ ] Create `SourceContextManager` - manage source_id batches and clerk profile assignment
5. [ ] Create `Renderer` - render name, rank, unit, extra text with noise application
6. [ ] Wire into pipeline to produce `raw.parquet` and `validation.parquet`
7. [ ] Create new seed set calibrated to collision-heavy hierarchy
8. [ ] Write tests validating collision coverage and vocabulary distribution

---

## Acceptance Criteria

- Generator produces raw.parquet matching schema in CURRENT.md
- Designator collisions appear in output (same regiment designator, different components)
- Vocabulary terms appear with correct frequency distribution
- Component-specific terms correlate with their components (with leak-through)
- Seed set includes examples from all 15 components

---

## References

- [CURRENT.md](../../docs/components/synthetic_data_generation/CURRENT.md)
- [hierarchy_reference.json](../../config/hierarchies/hierarchy_reference.json)
- [Deprecated style spec](../../docs/components/synthetic_data_generation/deprecated/synthetic_style_spec_v2.yaml) (for reference)
