# Military Records Consolidation Project

LLM-based methodology for consolidating fragmented historical military records into coherent soldier unit assignments.

## Quick Start

```bash
# Setup environment
./scripts/setup.sh

# Run pipeline
python -m src.main --config config/default.yaml
```

## Project Structure

| Folder | Purpose |
|--------|---------|
| `src/` | Implementation code |
| `tests/` | Test suite |
| `config/` | Runtime config (hierarchies, resolvers, prompts) |
| `data/` | Data files (gitignored) |
| `docs/` | Canonical design documentation |
| `instructions/` | Task handoffs for Claude Code |
| `.project_history/` | Process artifacts (extracts, logs, synthesis) |
| `scripts/` | Utility scripts |

## Documentation

- **Architecture:** `docs/architecture/CURRENT.md`
- **Components:** `docs/components/[name]/CURRENT.md`
- **Data structures:** `docs/data-structures/CURRENT.md`
- **Sandboxing:** `docs/components/sandboxing/CURRENT.md`

## Quick Reference

| I need to... | Go to... |
|--------------|----------|
| Understand current architecture | `docs/architecture/CURRENT.md` |
| See design for a component | `docs/components/[name]/CURRENT.md` |
| Give Claude Code a task | `instructions/active/` |
| Find implementation code | `src/[component]/` |
| See what was discussed today | `.project_history/extracts/daily/` |
| Find a past thread extract | `.project_history/extracts/raw/` |
| Check what Claude Code did | `.project_history/code-activity/` |
| Bootstrap a new LLM session | `docs/context-packets/` |
| Find runtime hierarchies/resolvers | `config/` |

## Workflow

1. Design ideation in GUI LLMs
2. Extract → `.project_history/extracts/raw/`
3. Reconcile → `.project_history/extracts/daily/`
4. Update → `docs/.../CURRENT.md`
5. Create instruction → `instructions/active/`
6. Claude Code implements → `src/`
7. Log activity → `.project_history/code-activity/`

## File Naming Conventions

| Type | Pattern | Example |
|------|---------|---------|
| Thread extract | `YYYY-MM-DD_[llm]_[session].md` | `2026-01-12_opus_session2.md` |
| Daily reconciliation | `YYYY-MM-DD_[namespace-path].md` | `2026-01-12_strategy-resolver-pattern-tiers.md` |
| Code activity log | `YYYY-MM-DD.md` | `2026-01-12.md` |
| Instruction | `NNN_[task-name].md` | `001_resolver-generator-phase1.md` |
| Architecture iteration | `vX.Y_YYYY-MM-DD.md` | `v3.0_2026-01-11.md` |
| ADR | `ADR-NNN_[title].md` | `ADR-001_raw-text-as-primary-input.md` |

## Security

The project implements comprehensive sandboxing for:
- **File system access control** - Restricts read/write to authorized directories
- **Code execution isolation** - Safely executes LLM-generated resolvers with timeout and import restrictions

See `docs/components/sandboxing/CURRENT.md` for details.

Example usage in `examples/sandbox_usage.py`.

## Current Status

<!-- Update with current focus and blockers -->

**Focus:** [Current primary work area]

**Blockers:** [Any blocking issues]

**Recent:** Sandboxing implementation (2026-01-12)
