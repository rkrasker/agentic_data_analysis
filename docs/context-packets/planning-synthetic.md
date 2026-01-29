# Context: Synthetic Data Planning

## Purpose
Modifying data generation, adjusting soldier/record distributions, changing quality tiers, implementing difficulty model.

## Always Load
- CLAUDE.md (root)
- docs/DISAMBIGUATION_MODEL.md
- DIFFICULTY_MODEL.md (computation contexts)
- docs/architecture/decisions/ADR-006_per-record-vs-per-soldier-difficulty.md (three-layer difficulty)
- docs/architecture/decisions/ADR-007-synthetic-data-redesign.md (domain decontamination)
- docs/architecture/decisions/ADR-010-synthetic-metadata-separation.md (schema separation)

## Core Context
- docs/components/synthetic_data_generation/CURRENT.md
- docs/components/synthetic_data_generation/synthetic_style_spec_v4.1.yaml
- docs/components/preprocessing/CURRENT.md

## If Relevant
- config/synthetic/ files
- config/hierarchies/hierarchy_reference.json
- docs/data-structures/CURRENT.md
- docs/GLOSSARY.md

## Current State
- Check SESSION_STATE.md
- Check data/synthetic/ for current artifacts

## v4.1 Key Concepts
- **Domain**: Terraform Combine (fictional interstellar setting)
- **States**: Explicit with state_id (1-3 per soldier)
- **Branches**: 4 branches with variable depth (3-5 levels)
- **Difficulty**: Three layers (extraction, aggregation, structural)
- **Collision zones**: Tagged at post selection time
- **Schema separation** (ADR-010): Core data vs synthetic metadata vs computed difficulty
- **Difficulty prefixes**: gen_ (generation control), gt_ (ground-truth), inferred_ (from raw only)
