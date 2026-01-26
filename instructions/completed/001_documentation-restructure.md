# Documentation Restructure for Multi-Agent Workflow

**Status:** ✅ Complete
**Model:** Sonnet, thinking off
**Prerequisites:** None

## Objective

Restructure project documentation to support efficient multi-agent workflows:
- Trim root CLAUDE.md to essential always-loaded context
- Extract detailed content to purpose-specific files
- Create CLAUDE.md files for agent operational warnings
- Create context packets for different work modes
- Add code style preferences

## Principles Guiding This Restructure

1. **CLAUDE.md = agent operational context** (warnings, pitfalls, working guidance)
2. **CURRENT.md = design documentation** (architecture, specs, status)
3. **Root CLAUDE.md should be lean** — loaded every session, so only universal context
4. **Folder-level CLAUDE.md provides localized warnings** — loaded when working in that area
5. **Context packets enable selective loading** — right context for right task
6. **All existing docs/**.md files remain untouched** — we're adding, not replacing

## Files to Create

### 1. Restructured Root CLAUDE.md

**Location:** `CLAUDE.md` (root, overwrite existing)

**Content to KEEP (these sections remain, may be tightened):**
- "What This Project Is" — trim to essential paragraph
- "The Core Problem: State Resolution" — keep, this is fundamental
- "Key Terminology" table — keep entire table
- "Architecture Status" section (Implemented / Partially Implemented / Not Yet Implemented)
- "Current State" (branch, active work, what's stable, what's in flux)

**Content to REMOVE (extracted to other files):**
- "The Three-Layer Disambiguation Model" → moves to docs/DISAMBIGUATION_MODEL.md
- "The Critical Distinction" section → moves with disambiguation model
- "Cross-Strategy LLM Pitfalls" → moves to docs/components/strategies/CLAUDE.md
- "Resolver Strategy" subsection → moves to docs/components/strategies/resolver/CLAUDE.md
- "Resolver Pitfalls" → moves to docs/components/strategies/resolver/CLAUDE.md
- "ADR Pointers" table → moves to docs/ADR_INDEX.md

**Content to ADD:**
```markdown
## Code Style Preferences

See `docs/CODE_STYLE.md` for detailed guidance. Key principles:
- Prefer functions over classes for stateless operations
- No premature abstraction — build for current requirements
- Flat is better than nested; simple is better than clever

## Documentation Map

| I need... | Go to... |
|-----------|----------|
| Disambiguation model deep-dive | `docs/DISAMBIGUATION_MODEL.md` |
| Strategy pitfalls/warnings | `docs/components/strategies/CLAUDE.md` |
| Resolver-specific warnings | `docs/components/strategies/resolver/CLAUDE.md` |
| Component design docs | `docs/components/[name]/CURRENT.md` |
| Architecture overview | `docs/architecture/CURRENT.md` |
| ADR quick reference | `docs/ADR_INDEX.md` |
| Context packets | `docs/context-packets/` |
```

---

### 2. docs/DISAMBIGUATION_MODEL.md

**Location:** `docs/DISAMBIGUATION_MODEL.md` (new file)

**Content:** Extract these sections verbatim from current CLAUDE.md:
- "The Three-Layer Disambiguation Model" (full section including all subsections)
- "Layer 1: Per-Record Extraction"
- "Interdependence: Extraction ↔ Grouping"  
- "Layer 2: Cross-Record Aggregation"
- "Layer 3: Structural Inference"
- "The Critical Distinction" section

**Add header:**
```markdown
# Disambiguation Model

This document describes the analytical framework for resolving posts within inferred states. Extracted from project context for reference.

**See also:** `CLAUDE.md` for core problem definition, `docs/architecture/CURRENT.md` for implementation architecture.

---
```

---

### 3. docs/CODE_STYLE.md

**Location:** `docs/CODE_STYLE.md` (new file)

**Content:**
```markdown
# Code Style Preferences

This project favors explicit, readable code over architectural elegance.

## Core Principles

**Prefer functions over classes** for stateless operations. Only introduce a class when you need to manage state across multiple method calls.

**No premature abstraction.** Build for current requirements. "Future flexibility" that isn't needed now is complexity that costs now.

**Flat is better than nested; simple is better than clever.** If you can accomplish something with straightforward code, do that.

## Specific Guidance

### When to Use Classes

✓ Use a class when:
- Managing state across multiple method calls
- Implementing a defined interface (e.g., BaseStrategy)
- The object has a clear lifecycle (creation → use → cleanup)

✗ Don't use a class when:
- A function with parameters would work
- The "class" would have only `__init__` and one method
- You're wrapping a single operation

### What to Avoid

- **Factory patterns** unless construction logic is genuinely complex
- **Abstract base classes** with only one implementation
- **Getter/setter methods** when direct attribute access works
- **Configuration objects** for things that could be function parameters
- **Inheritance hierarchies** when composition (or nothing) would work

### Patterns That Fit This Project

- **Dataclasses** for structured data (already used throughout)
- **Module-level functions** for stateless operations
- **Simple classes** for stateful components with clear responsibilities
- **Dictionary/DataFrame returns** over custom container classes

## The Test

Before adding structure, ask: "Does this structure solve a problem I have now, or a problem I imagine having later?"

If later → don't add it. We can refactor when the need is real.

## Context

This guidance exists because LLM coding agents tend toward over-engineering. When in doubt, choose the simpler implementation.
```

---

### 4. docs/ADR_INDEX.md

**Location:** `docs/ADR_INDEX.md` (new file)

**Content:** Extract from current CLAUDE.md and format as:
```markdown
# ADR Index

Quick reference to Architecture Decision Records.

| ADR | Topic | Key Insight | Location |
|-----|-------|-------------|----------|
| ADR-001 | Validation leakage policy | Train/test splits are soldier-level disjoint | `docs/architecture/decisions/ADR-001_validation-leakage-policy.md` |
| ADR-002 | Dual-run stateful extraction | Hard cases detected via forward/reverse batch comparison | `docs/architecture/decisions/ADR-002_llm-batching-statefulness.md` |
| ADR-004 | Few-shot corpus from resolver | Hard cases become training examples | `docs/architecture/decisions/ADR-004_*.md` |
| ADR-005 | Grounded inference | Patterns must be observed or marked inferred; no absence-based rules | `docs/architecture/decisions/ADR-005_grounded-inference-provenance.md` |
| ADR-006 | Assignment difficulty model | The three-layer disambiguation framework | `docs/architecture/decisions/ADR-006_*.md` |

## When to Reference ADRs

- **Before changing** a system that an ADR governs — understand the decision first
- **When confused** about why something works a certain way — ADR may explain
- **When proposing changes** that might conflict with an ADR — surface the conflict explicitly
```

---

### 5. docs/components/strategies/CLAUDE.md

**Location:** `docs/components/strategies/CLAUDE.md` (new file)

**Content:** Extract "Cross-Strategy LLM Pitfalls" from current CLAUDE.md:
```markdown
# Strategy Development: Operational Warnings

These pitfalls apply across all LLM-based strategies. Review before designing or modifying any strategy.

## Cross-Strategy LLM Pitfalls

- **Training prior leakage**: The model uses innate training data or general military knowledge instead of only provided data.

- **State over-splitting**: The model invents multiple states when a single post should explain the records.

- **State under-splitting**: Distinct posts are merged into one state because the model over-generalizes.

- **Order anchoring**: Early records or early batches lock the model into a wrong state count or grouping.

- **Drift across batches**: Successive batches shift interpretation even when evidence is similar.

- **Premature convergence**: The model stops revising candidate meanings once a grouping seems plausible.

- **Scaffolded hallucination**: Overly explicit prompting induces invented steps or unjustified inferences.

## Implications for Strategy Design

When designing prompts or evaluation criteria, explicitly test for these failure modes. A strategy that works on easy cases may fail via these pitfalls on harder cases.

## See Also

- Individual strategy designs: `docs/components/strategies/[name]/CURRENT.md`
- Strategy comparison: `docs/components/strategies/_comparison/CURRENT.md`
- Resolver-specific pitfalls: `docs/components/strategies/resolver/CLAUDE.md`
```

---

### 6. docs/components/strategies/resolver/CLAUDE.md

**Location:** `docs/components/strategies/resolver/CLAUDE.md` (new file)

**Content:** Extract "Resolver Pitfalls" from current CLAUDE.md:
```markdown
# Resolver Strategy: Operational Warnings

These pitfalls are specific to the resolver strategy. Review before modifying resolver generation or execution.

## Resolver-Specific Pitfalls

- **Spurious pattern induction**: Heuristics reflect quirks of the sampled training records rather than stable evidence.

- **Over-generalization**: Patterns match across collision zones and fire on adjacent components.

- **Overfitting to injections**: Heuristics mirror injected reference data instead of record evidence.

- **Coverage gaps**: Resolver rules handle canonical formats but miss clerk variation and partial paths.

- **Internal inconsistency**: Generated patterns conflict or encode incompatible assumptions.

## Implications for Resolver Work

When building or modifying resolvers:
- Test patterns against collision pairs, not just single-component data
- Verify patterns fire on held-out data, not just training samples
- Check for rule conflicts in the assembled resolver JSON

## See Also

- Resolver design: `docs/components/strategies/resolver/CURRENT.md`
- Cross-strategy pitfalls: `docs/components/strategies/CLAUDE.md`
- Grounded inference policy: ADR-005
```

---

### 7. Context Packets

**Location:** `docs/context-packets/` (create directory if needed)

#### 7a. docs/context-packets/planning-architecture.md
```markdown
# Context: Architecture Planning

## Purpose
High-level design work, cross-cutting decisions, Opus sessions on system structure.

## Always Load
- CLAUDE.md (root)
- docs/DISAMBIGUATION_MODEL.md

## Core Context
- docs/architecture/CURRENT.md
- docs/ADR_INDEX.md
- docs/components/strategies/_comparison/CURRENT.md

## If Relevant
- docs/data-structures/CURRENT.md
- Specific component CURRENT.md for the area under discussion

## Current State
- Check SESSION_STATE.md for active focus
- Check instructions/active/ for pending work
```

#### 7b. docs/context-packets/planning-resolver.md
```markdown
# Context: Resolver Planning

## Purpose
Designing resolver approach, modifying generation workflow, reviewing resolver strategy.

## Always Load
- CLAUDE.md (root)
- docs/DISAMBIGUATION_MODEL.md
- docs/components/strategies/CLAUDE.md
- docs/components/strategies/resolver/CLAUDE.md

## Core Context
- docs/components/strategies/resolver/CURRENT.md
- docs/architecture/decisions/ADR-002_llm-batching-statefulness.md
- docs/architecture/decisions/ADR-005_grounded-inference-provenance.md

## If Relevant
- docs/components/strategies/_comparison/CURRENT.md
- docs/data-structures/CURRENT.md (resolver JSON schema)

## Current State
- Check SESSION_STATE.md
- Check instructions/active/ for resolver-related tasks
```

#### 7c. docs/context-packets/planning-synthetic.md
```markdown
# Context: Synthetic Data Planning

## Purpose
Modifying data generation, adjusting soldier/record distributions, changing quality tiers.

## Always Load
- CLAUDE.md (root)
- docs/DISAMBIGUATION_MODEL.md

## Core Context
- docs/components/synthetic_data_generation/CURRENT.md
- docs/components/preprocessing/CURRENT.md

## If Relevant
- config/synthetic/ files
- docs/data-structures/CURRENT.md

## Current State
- Check SESSION_STATE.md
- Check data/synthetic/ for current artifacts
```

#### 7d. docs/context-packets/execution-resolver.md
```markdown
# Context: Resolver Implementation

## Purpose
Implementing resolver modules against existing specs. Sonnet execution mode.

## Always Load
- CLAUDE.md (root)
- The specific instruction file from instructions/active/

## Core Context
- docs/components/strategies/resolver/CURRENT.md (implementation specs section)
- docs/CODE_STYLE.md

## Code Locations
- src/strategies/resolver/generator/ — generation modules
- src/strategies/resolver/executor/ — execution modules
- src/utils/llm/ — LLM infrastructure

## Note
If the instruction file is unclear or requires architectural decisions, pause and escalate to Opus planning session.
```

#### 7e. docs/context-packets/execution-general.md
```markdown
# Context: General Implementation

## Purpose
Implementing well-specified tasks. Sonnet execution mode.

## Always Load
- CLAUDE.md (root)
- The specific instruction file from instructions/active/
- docs/CODE_STYLE.md

## Load Based on Task Area
- Preprocessing: docs/components/preprocessing/CURRENT.md
- Evaluation: docs/components/evaluation/CURRENT.md
- Synthetic: docs/components/synthetic_data_generation/CURRENT.md

## Note
If the instruction file is unclear or requires architectural decisions, pause and escalate to Opus planning session.
```

---

### 8. Workflow Prompts

**Location:** `docs/workflows/` (create directory)

#### 8a. docs/workflows/session-wrapup-prompt.md
```markdown
# Session Wrap-up Prompts

Copy and paste at end of session.

---

## For Opus GUI Sessions
```
I need to wrap up this session. Please generate the following artifacts:

1. **SESSION_STATE.md update** — formatted as a complete replacement for the file:
   - Active task (one sentence)
   - Current approach and key decisions made
   - Where I left off (specific next step)
   - Open questions remaining

2. **Extract for `.project_history/extracts/raw/`** — filename format YYYY-MM-DD_opus_[topic].md:
   - Key decisions made and rationale
   - Alternatives considered and why rejected
   - Implications for implementation
   - Any warnings or pitfalls identified

3. **Instruction file(s)** if we defined executable tasks — for `instructions/active/`:
   - Full spec per our discussion
   - Ready for Sonnet execution

Generate all three as copyable text blocks I can save directly.
```

---

## For Claude Code Sessions
```
Before we finish, update the project state:

1. Read current SESSION_STATE.md
2. Update it to reflect:
   - What we accomplished
   - Current state of the task
   - Next steps
3. Write the updated file to SESSION_STATE.md

Also note any issues or surprises we encountered.
```

---

## For End-of-Day Reconciliation (Sonnet)
```
I have these session extracts from today: [list files or paste content]

Create a daily reconciliation that:
1. Synthesizes the key decisions across sessions
2. Notes any tensions or open questions
3. Identifies what CURRENT.md files need updating
4. Lists concrete next steps

Format for `.project_history/extracts/daily/YYYY-MM-DD_[topic].md`
```
```

---

### 9. SESSION_STATE.md Template

**Location:** `SESSION_STATE.md` (root)
```markdown
# Current Session State

**Last Updated:** [date/time]

## Active Task
[One sentence: what you're trying to accomplish]

## Current Approach
[What strategy you're pursuing, key decisions made this session]

## Where I Left Off
[Specific: last file touched, next concrete step]

## Open Questions
[What's unresolved, what judgment calls are pending]

## Recent Context
[Links to relevant instruction files, recent extracts, active docs]
```

---

## Verification

After execution, confirm:
- [ ] Root CLAUDE.md is shorter, contains documentation map
- [ ] docs/DISAMBIGUATION_MODEL.md exists with full model description
- [ ] docs/CODE_STYLE.md exists
- [ ] docs/ADR_INDEX.md exists
- [ ] docs/components/strategies/CLAUDE.md exists with cross-strategy pitfalls
- [ ] docs/components/strategies/resolver/CLAUDE.md exists with resolver pitfalls
- [ ] docs/context-packets/ contains 5 packet files
- [ ] docs/workflows/session-wrapup-prompt.md exists
- [ ] SESSION_STATE.md template exists at root
- [ ] All existing docs/**/*.md files unchanged
- [ ] No content lost — all CLAUDE.md content exists somewhere

## Execution Notes

- Read current CLAUDE.md first to understand section boundaries
- Extract content verbatim where indicated, don't paraphrase
- Maintain any internal links (update paths if content moves)
- Create directories as needed (docs/context-packets/, docs/workflows/)
