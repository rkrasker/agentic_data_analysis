# Current Session State

**Last Updated:** 2026-01-26 13:17

## Active Task

Rebuild resolver strategy with updated synthetic data

## What We Accomplished

Completed the v4.1 synthetic data implementation based on ADR-006 and ADR-007:

### Config Rewrites (Implemented)
1. **[hierarchy_reference.json](config/hierarchies/hierarchy_reference.json)** - Terraform Combine branches + collision index
2. **[synthetic_vocabulary.json](config/synthetic/synthetic_vocabulary.json)** - New domain vocabulary
3. **[synthetic_themes.json](config/synthetic/synthetic_themes.json)** - Branch-based themes

### New/Updated Code (Implemented)
4. **[models.py](src/synthetic/models.py)** - State model + difficulty fields + new enums
5. **[hierarchy_loader.py](src/synthetic/hierarchy_loader.py)** - Variable-depth support + collision queries
6. **[soldier_factory.py](src/synthetic/soldier_factory.py)** - State generation + collision tagging
7. **[source_generator.py](src/synthetic/source_generator.py)** - home_unit + temporal_anchor
8. **[renderer.py](src/synthetic/renderer.py)** - Familiarity-aware rendering + completeness tracking
9. **[transfer_manager.py](src/synthetic/transfer_manager.py)** - Cross-branch transfers
10. **[pipeline.py](src/synthetic/pipeline.py)** - Wired difficulty computation + rebalancer
11. **[clerk_factory.py](src/synthetic/clerk_factory.py)** - Updated archetypes
12. **[situation_manager.py](src/synthetic/situation_manager.py)** - Updated situations
13. **[vocabulary_injector.py](src/synthetic/vocabulary_injector.py)** - New vocabulary structure

### New Difficulty Modules
14. **[completeness_analyzer.py](src/synthetic/completeness_analyzer.py)** - Path coverage + complementarity score
15. **[difficulty_computer.py](src/synthetic/difficulty_computer.py)** - Soldier-level difficulty tier
16. **[difficulty_rebalancer.py](src/synthetic/difficulty_rebalancer.py)** - Target difficulty distribution controls

### Preprocessing v4.1 Updates
17. **[glossary_generator.py](src/preprocessing/glossary_generator.py)** - Terraform Combine glossary generation (v4.1 sources)
18. **[preprocessing_adapter.py](src/preprocessing/preprocessing_adapter.py)** - v4.1 schema routing + explicit join key
19. **[synthetic_glossary.json](config/glossaries/synthetic_glossary.json)** - Regenerated glossary
20. **[CURRENT.md](docs/components/preprocessing/CURRENT.md)** - Updated preprocessing documentation

### Regenerated Artifacts (v4.1)
21. **[raw.parquet](data/synthetic/raw.parquet)** - 200,000 records
22. **[validation.parquet](data/synthetic/validation.parquet)** - 1,408 state rows (1,000 soldiers)
23. **[sources.parquet](data/synthetic/sources.parquet)** - 5,762 sources
24. **[canonical.parquet](data/synthetic/canonical.parquet)** - Record-level extraction output (200,000 rows)
25. **[synthetic_metadata.parquet](data/synthetic/synthetic_metadata.parquet)** - Synthetic-only fields (200,000 rows)

### Documentation Updates
26. **[ADR_INDEX.md](docs/ADR_INDEX.md)** - ADR-006/ADR-007 entries clarified
27. **[CURRENT.md](docs/architecture/CURRENT.md)** - v4.1 status and difficulty model documented
28. **[planning-synthetic.md](docs/context-packets/planning-synthetic.md)** - v4.1 context + glossary added
29. **[GLOSSARY.md](docs/GLOSSARY.md)** - New glossary with difficulty model terms

### Session Extract
30. **[2026-01-25_opus_synthetic-v4-design.md](.project_history/extracts/raw/2026-01-25_opus_synthetic-v4-design.md)** - Decision record
31. **[2026-01-26_codex_difficulty-tier-all-easy-investigation.md](.project_history/extracts/raw/2026-01-26_codex_difficulty-tier-all-easy-investigation.md)** - Investigation report

## Current State of Project

The v4.1 synthetic data system is implemented and artifacts are regenerated. Preprocessing now supports v4.1
schema routing with a record-level canonical output. Code emits:
- `state_id` and explicit states (1-3 per soldier)
- `path_completeness`, `levels_provided`, `extraction_signals`
- `difficulty_tier`, `complementarity_score`, `structural_resolvability`

## Issues and Surprises Encountered

- Difficulty distribution reported as 100% easy in the latest regeneration run (see `.project_history/extracts/raw/2026-01-26_codex_difficulty-tier-all-easy-investigation.md`).
- PyArrow emitted sandbox sysctl warnings during parquet writes (non-fatal).

## Next Steps

### Immediate
- Rebuild resolver strategy with updated synthetic data

### Pending Active Instructions
None. Instruction 005 moved to completed:
- `instructions/completed/005_preprocessing-v4.1-terraform-combine.md`

## Recent Context

- **ADR-007**: `docs/architecture/decisions/ADR-007-synthetic-data-redesign.md`
- **ADR-006**: `docs/architecture/decisions/ADR-006_per-record-vs-per-soldier-difficulty.md`
- **v4.1 Style Spec**: `docs/components/synthetic_data_generation/synthetic_style_spec_v4.1.yaml`
- **Extract**: `.project_history/extracts/raw/2026-01-25_opus_synthetic-v4-design.md`
- **Key principle**: Domain decontamination - fictional setting eliminates LLM pretraining bias
