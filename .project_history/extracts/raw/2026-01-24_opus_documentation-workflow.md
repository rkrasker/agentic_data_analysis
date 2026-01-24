# Session Extract: Documentation & Workflow Optimization

**Date:** 2026-01-24
**Model:** Opus (Claude AI GUI)
**Topic:** Multi-agent workflow design, documentation restructuring

---

## Problem Statement

User is working on a complex Claude Code project (military records disambiguation) that requires heavy Opus usage for planning, but Pro plan rate limits cause frequent lockouts. Goal was to design workflows and documentation structures that:
1. Maximize value from limited Opus sessions
2. Enable smooth handoff to Sonnet/Codex for execution
3. Reduce context-loading overhead
4. Support agent-assisted documentation generation

---

## Key Decisions Made

### 1. Task Stratification Model

**Decision:** Explicitly categorize tasks by model requirement before starting.

| Task Type | Model | Thinking |
|-----------|-------|----------|
| Architecture/planning | Opus | On |
| Complex implementation | Sonnet | On |
| Specified implementation | Sonnet | Off |
| Mechanical/boilerplate | Sonnet | Off |
| Overflow (rate-limited) | Codex | On |

**Rationale:** Rate limits become mode-switch signals rather than obstacles. Maintain backlog of execution-ready tasks for Codex/Sonnet periods.

### 2. CLAUDE.md Restructuring

**Decision:** Trim root CLAUDE.md to essential always-loaded context; extract detailed content to purpose-specific files.

**New structure:**
- Root CLAUDE.md: Core problem, terminology, architecture status, documentation map
- docs/DISAMBIGUATION_MODEL.md: Three-layer model (extracted)
- docs/CODE_STYLE.md: Style preferences (new)
- docs/ADR_INDEX.md: ADR quick reference (extracted)
- docs/components/strategies/CLAUDE.md: Cross-strategy pitfalls (extracted)
- docs/components/strategies/resolver/CLAUDE.md: Resolver pitfalls (extracted)

**Rationale:** Root CLAUDE.md loaded every session—should only contain universal context. Detailed content belongs where it's naturally loaded based on work area.

### 3. CLAUDE.md vs CURRENT.md Distinction

**Decision:** 
- CLAUDE.md = agent operational context (warnings, pitfalls, working guidance)
- CURRENT.md = design documentation (architecture, specs, status)

**Rationale:** Different purposes, different consumers. CLAUDE.md is "instructions for working on code." CURRENT.md is "documentation about code."

### 4. Pitfalls Location

**Decision:** Place pitfalls in docs/components/strategies/ (not src/strategies/).

**Rationale:** Pitfalls are needed during Opus planning phase, not Sonnet execution phase. Opus reads docs/; Sonnet executes from instruction files that already encode pitfall-awareness. Maintains clean src/ = code only separation.

### 5. Context Packet System

**Decision:** Create markdown files in docs/context-packets/ that list what to load for different work modes.

**Packets defined:**
- planning-architecture.md
- planning-resolver.md
- planning-synthetic.md
- execution-resolver.md
- execution-general.md

**Rationale:** Enables selective context loading. Right context for right task without manual assembly each time.

### 6. Session Wrap-up Delegation

**Decision:** Use templated prompts to have agent generate end-of-session documentation.

**Created:** docs/workflows/session-wrapup-prompt.md with prompts for:
- Opus GUI session wrap-up
- Claude Code session wrap-up
- End-of-day reconciliation

**Rationale:** User time-constrained. Agent-generated documentation (with quick human review) is acceptable tradeoff.

### 7. Code Style Guidance

**Decision:** Add explicit CODE_STYLE.md to counteract LLM tendency toward over-engineering.

**Key principles:**
- Prefer functions over classes for stateless operations
- No premature abstraction
- Flat > nested, simple > clever
- No factory patterns, abstract base classes with single implementation, etc.

**Rationale:** LLM coding agents bias toward enterprise patterns from training data. Explicit guidance shifts the default.

### 8. Model Selection for Execution

**Decision:** Haiku rarely useful for this project due to conceptual density. Focus optimization on Sonnet thinking on/off distinction.

**Heuristic:** If instruction file contains the reasoning, extended thinking is unnecessary. Thinking compensates for incomplete specs.

---

## Alternatives Considered

### Tooling vs Documentation

**Considered:** Building custom tooling for context loading, documentation generation, repo maintenance.

**Rejected (for now):** 
- Mid-project with architectural churn—tooling would need to evolve with it
- Documentation-as-process has value for understanding human-agent collaboration (stated project meta-goal)
- Templates and checklists achieve 80% of benefit with 20% of effort

**Conclusion:** Document procedures rather than automate them. Revisit tooling when architecture stabilizes.

### CLAUDE.md in src/ vs docs/

**Considered:** Placing strategy pitfalls in src/strategies/CLAUDE.md for auto-loading during code work.

**Rejected:** Sonnet executing code doesn't need to reason about pitfalls—instruction file should already encode that. Opus planning reads docs/. Maintains src/ = code only.

### Automated Context Packets

**Considered:** Rules-based generation of context packets (e.g., "include everything under docs/components/X/").

**Rejected (for now):** Manual curation more accurate initially. Can automate later if patterns emerge.

---

## Implications for Implementation

### Immediate (Execute Now)

1. Save instruction file to `instructions/active/001_documentation-restructure.md`
2. Execute with Sonnet (thinking off—spec is detailed)
3. Verify all content preserved, no broken links

### Workflow Changes

1. Before starting any task, consciously categorize: planning or execution?
2. Maintain instruction backlog for rate-limited periods
3. Use context packets when starting sessions
4. Use wrap-up prompts to generate documentation
5. Update SESSION_STATE.md at session boundaries

### Future Refinements

1. Refine context packets based on actual usage
2. Consider custom /wrapup slash command for Claude Code
3. May need preprocessing and evaluation context packets
4. CODE_STYLE.md may need expansion based on observed agent patterns

---

## Warnings and Pitfalls Identified

### For This Restructure

- Don't lose content during extraction—verify checklist
- Update internal links if content moves
- Root CLAUDE.md should stay lean—resist adding back

### For Ongoing Workflow

- Agent-generated documentation needs human skim (30 sec) before saving
- Opus session value degrades after ~70% context—shift to artifact generation
- Instruction files must include reasoning, not just specs, or Sonnet may second-guess
- Rate limit = mode switch signal, not obstacle—have execution work ready

### Context Window Management

| Context % | Action |
|-----------|--------|
| 0-30% | Explore, question, consider |
| 30-50% | Converge on decisions |
| 50-70% | Generate artifacts |
| 70-85% | Finalize, wrap up |
| 85%+ | Stop. Get final outputs. End. |

---

## Files Created/Modified This Session

### To Create (via instruction execution)
- CLAUDE.md (root) — restructured
- docs/DISAMBIGUATION_MODEL.md — new
- docs/CODE_STYLE.md — new
- docs/ADR_INDEX.md — new
- docs/components/strategies/CLAUDE.md — new
- docs/components/strategies/resolver/CLAUDE.md — new
- docs/context-packets/ (5 files) — new
- docs/workflows/session-wrapup-prompt.md — new
- SESSION_STATE.md — new template

### To Save Manually
- instructions/active/001_documentation-restructure.md
- .project_history/extracts/raw/2026-01-24_opus_documentation-workflow.md (this file)
- SESSION_STATE.md (initial population)

---

## References

- Instruction file: `instructions/active/001_documentation-restructure.md`
- Current CLAUDE.md: source for extractions
- Project README: `README.md` (unchanged)
- Existing docs structure: `docs/components/*/CURRENT.md` (unchanged)