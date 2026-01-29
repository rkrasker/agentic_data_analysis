# Active Instructions

Store task handoffs for Claude Code here.

## Naming Convention

`NNN_[task-name].md`

Examples:
- `001_resolver-generator-phase1.md`
- `002_batch-manager.md`
- `003_regex-extractor.md`

Number sequentially. Gaps are fine (after completion/removal).

## Workflow

1. Create instruction from template (`templates/instruction_template.md`)
2. Reference relevant `docs/components/.../CURRENT.md`
3. Hand off to Claude Code
4. On completion, move to `completed/`
5. Log activity in `.project_history/code-activity/`
6. Update relevant CURRENT.md with implementation status

## Current Instructions

<!-- Update this list as instructions are added/completed -->

| # | Task | Status | Component |
|---|------|--------|-----------|
| 011 | Difficulty-Based Sampling | active | preprocessing/splits, strategies/resolver/generator |

## Recently Completed

| # | Task | Completed | Component |
|---|------|-----------|-----------|
| 004 | Synthetic Data v4.1 – Terraform Combine | 2026-01-25 | synthetic_data_generation |
| 001 | Documentation Restructure | 2026-01-25 | docs |
| 001 | Synthetic Data Generator (v3) | 2026-01-14 | synthetic_data_generation |
| — | Preprocessing Adapter | 2026-01-14 | preprocessing |

## Suggested Next Instructions

1. **Component Router** — route records to components based on extraction signals
2. **Batching** — group records for efficient LLM processing
3. **Zero-Shot Strategy** — baseline consolidation approach
