# Current Session State

**Last Updated:** 2026-01-25 14:30

## Active Task

Synthetic Data v4 Implementation - spec complete, ready for code implementation

## What We Accomplished

Created the v4 synthetic data specification based on ADR-007:

### New/Updated Documentation
1. **[synthetic_style_spec_v4.yaml](docs/components/synthetic_data_generation/synthetic_style_spec_v4.yaml)** - Complete v4 specification (1400+ lines)
   - Terraform Combine fictional domain (4 branches with depths 3-5)
   - Explicit state model (1-3 states per soldier)
   - Familiarity gradient at Level-3 granularity
   - Source-anchored state assignment
   - Cross-branch transfers (15%)
   - Full clerk archetype system translated to new domain

2. **[CURRENT.md](docs/components/synthetic_data_generation/CURRENT.md)** - Already updated to v4 design (pre-existing)

### New Instruction File
3. **[004_synthetic-v4-terraform-combine.md](instructions/active/004_synthetic-v4-terraform-combine.md)** - Implementation guide
   - Full task breakdown for config files and Python modules
   - Detailed warnings and pitfalls
   - Acceptance criteria checklist
   - Test strategy

### Session Extract
4. **[2026-01-25_opus_synthetic-v4-design.md](.project_history/extracts/raw/2026-01-25_opus_synthetic-v4-design.md)** - Decision record

## Current State of Project

The v4 synthetic data specification is complete. The following files need to be created/updated by executing instruction 004:

### Config Files (Full Rewrite)
- `config/hierarchies/hierarchy_reference.json` → Terraform Combine branches
- `config/synthetic/synthetic_vocabulary.json` → New vocabulary terms
- `config/synthetic/synthetic_themes.json` → Branch-based themes

### Python Modules (Significant Updates)
- `src/synthetic/models.py` → Add State, update enums
- `src/synthetic/soldier_factory.py` → State generation
- `src/synthetic/source_generator.py` → home_unit, temporal_anchor
- `src/synthetic/renderer.py` → Familiarity-aware rendering
- `src/synthetic/hierarchy_loader.py` → Variable-depth support
- `src/synthetic/transfer_manager.py` → Cross-branch transfers
- `src/synthetic/pipeline.py` → Wire state assignment

## Issues and Surprises Encountered

None - clean planning session.

## Next Steps

### Immediate
- Execute instruction 004 (Sonnet execution mode) to implement code changes
- This is a substantial implementation (~13 files affected)

### After Implementation
- Create `seed_set_v4.json` with hand-crafted calibration examples
- Run generation pipeline and validate output schema
- Update preprocessing for new domain

### Pending Active Instructions
Three instruction files in `instructions/active/`:
- **002_collision-sampling-synthetic-fix.md** - Phase 1 complete, Phase 2 may be superseded by v4
- **003_synthetic-degradation-phase2.md** - May be superseded by v4
- **004_synthetic-v4-terraform-combine.md** - NEW: Ready for execution

**Note:** Instructions 002 and 003 were designed for v3. Review whether they're still relevant after v4 implementation.

## Recent Context

- **ADR-007**: `docs/architecture/decisions/ADR-007-synthetic-data-redesign.md`
- **v4 Style Spec**: `docs/components/synthetic_data_generation/synthetic_style_spec_v4.yaml`
- **Extract**: `.project_history/extracts/raw/2026-01-25_opus_synthetic-v4-design.md`
- **Key principle**: Domain decontamination - fictional setting eliminates LLM pretraining bias
