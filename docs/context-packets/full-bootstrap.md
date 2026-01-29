# Project Bootstrap: Military Records State Resolution

Load this at the start of any fresh LLM session for full project context.

## Project Goal

Resolve fragmented historical military records into **states**—latent segments of a soldier's service—where each state maps to a concrete **post** (unit assignment in the military hierarchy).

## Core Challenge: State Resolution

**This is NOT identity resolution.** We always know which records belong to which soldier.

**This is NOT extraction.** Regex handles extraction. The canonical.parquet contains extracted signals for routing/batching only.

**State resolution IS the problem.** Given all records for a soldier, the LLM must infer:

1. **How many states exist** (the count is unknown—could be 1, 2, or more)
2. **Which records belong to which state** (grouping/partitioning)
3. **What post each state resolves to** (the component path)

A **post** is the concrete unit assignment: `Sector → Fleet → Squadron → Wing → Element`

**Note:** Development uses synthetic data in the fictional "Terraform Combine" domain (ADR-007) to prevent LLM training data leakage. Production targets real WWII records.

### Why It's Hard

| Challenge | Example |
|-----------|---------|
| No temporal anchors | Cannot order records or states in time |
| Unknown state count | Don't know if soldier had 1 post or 3 |
| Abbreviated records | "Kestrel-3" not "Fleet Kestrel, 3rd Squadron, Wing A, Element 2" |
| Missing unit types | "7" or "3rd" without specifying fleet/squadron/wing |
| Collisions | Multiple branches share designators like "3" or "Alpha" |
| Clerk variation | Different formats, abbreviations, detail levels |

## Architecture Summary

### Pipeline Flow

```
Raw Records → [Regex Preprocessing] → canonical.parquet (routing/batching only)
                                            ↓
                                    [Component-Based Batching]
                                            ↓
                                    [Strategy Execution] ← strategies vary by injection/batching/prompting
                                            ↓
                                    [Evaluation vs Validation]

Resolver Strategy additionally requires:
    Training Data → [Per-Component LLM Runs] → resolver/{component}_resolver.json
                                                        ↓
                                              (injected at inference)
```

### Strategy Framework

All strategies solve the same task (state resolution) but vary along three dimensions:

| Dimension | What Varies | Examples |
|-----------|-------------|----------|
| **Injections** | Supplementary reference data loaded with prompt | Hierarchy only, hierarchy + resolvers, hierarchy + few-shot examples |
| **Batching** | How soldiers are grouped for processing | By component, by difficulty tier, by collision structure |
| **Prompting** | How much reasoning is scaffolded | Explicit chain-of-thought vs minimal guidance |

### Strategy Taxonomy

Current strategies (resolver implemented; others are stubs):

| Strategy | Injections | Notes |
|----------|------------|-------|
| Few-shot, no resolvers | Hierarchy + examples | Learning by example |
| Few-shot with resolvers | Hierarchy + examples + resolvers | Combines example-based and heuristic guidance |
| Few-shot, component-specific only | Hierarchy + component-focused examples | Narrower context |
| Few-shot, general only | Hierarchy + diverse examples | Broader patterns |
| Few-shot, mixed | Hierarchy + both example types | Balanced approach |

**Resolver strategy detail:** Resolvers are NOT hand-authored. They are built via a sequence of per-component LLM runs that extract patterns, vocabulary, and differentiators from training data, then injected into inference passes.

### Key Architectural Decisions

1. **Raw text is primary LLM input** — canonical.parquet is for routing/batching only
2. **Component-based batching** — group soldiers by likely component, load focused context
3. **Strategy plugin architecture** — all strategies implement same interface, differ in guidance
4. **Proportional confidence tiers** — robust/strong/moderate/tentative (not percentages)
5. **Conservative exclusions** — only incompatible PRESENCE excludes, never absence

### Data Structures

**Core files (production-equivalent):**

| File | Purpose |
|------|---------|
| `raw.parquet` | Historical records (source_id, soldier_id, raw_text) |
| `validation.parquet` | Ground truth labels (state assignments, post paths) |
| `canonical.parquet` | Regex extraction output (routing/batching signals only) |

**Synthetic-only metadata (ADR-010):**

| File | Purpose |
|------|---------|
| `synthetic_records.parquet` | Per-record generation metadata (clerk_id, quality_tier, state_id linkage) |
| `synthetic_soldiers.parquet` | Per-soldier generation metrics (gen_difficulty_tier, etc.) |

**Difficulty computation (ADR-010):**

| File | Purpose |
|------|---------|
| `gt_difficulty.parquet` | Ground-truth difficulty from validation labels (gt_* columns) |
| `inferred_difficulty.parquet` | Inferred difficulty from raw records alone (inferred_* columns) |

**Reference files:**

| File | Purpose |
|------|---------|
| `hierarchy_reference.json` | Branch structures and valid designators |
| `resolver/{component}_resolver.json` | LLM-generated disambiguation heuristics |

## Key Decisions in Effect

- Raw text is primary LLM input (canonical for routing only)
- Component-based batching for token efficiency
- Resolver is one strategy among peers (few-shot variants)
- State count discovery is part of the task (not given)
- Vocabulary is tiebreaker only (one tier nudge max)
- Absence of data never excludes a component

## What's Currently In Flux

These areas have working implementations but designs may shift:

- **Schema implementation** — ADR-010 schema separation is designed but not yet implemented
- **Routing decisions** — how preprocessing signals inform batching/strategy selection

**Recently stabilized:**

- **Difficulty modeling** — three-layer model (ADR-006), computation contexts (ADR-010)
- **Sampling strategy** — sample by soldier difficulty, not record quality (ADR-009)

## Implementation Status

### Implemented
- Synthetic data generation v4.1 (`src/synthetic/`)
- Preprocessing: regex extraction, glossary generation, structural discriminators (`src/preprocessing/`)
- Difficulty model design (ADR-006, ADR-009, ADR-010)
- Harness foundation: base strategy interface, train/test split, component batching
- LLM infrastructure (`src/utils/llm/`)
- Resolver strategy pre-build pipeline (`src/strategies/resolver/generator/`)

### Partially Implemented
- Batching (component batching works; token-budget batching not wired end-to-end)
- Evaluation (metrics exist; no automated evaluation pipeline)
- ADR-010 schema separation (designed, not yet implemented)

### Not Yet Implemented
- Resolver strategy execution runs (build pipeline exists, full dataset runs not built)
- Few-shot strategy variants (stubs only)

---

## Session Recovery

If resuming after a session timeout:

1. **Check current status:** `CLAUDE.md` → "Current State" section
2. **Review component docs:** `docs/components/[name]/CURRENT.md`
3. **Check implementation status:** `src/` structure and existing code
4. **Verify with tests:** Run existing test suite if available

**Key documentation entry points:**

| I need... | Go to... |
|-----------|----------|
| Disambiguation model deep-dive | `docs/DISAMBIGUATION_MODEL.md` |
| Difficulty computation | `DIFFICULTY_MODEL.md` |
| Strategy pitfalls/warnings | `docs/components/strategies/CLAUDE.md` |
| Resolver-specific warnings | `docs/components/strategies/resolver/CLAUDE.md` |
| Component design docs | `docs/components/[name]/CURRENT.md` |
| Architecture overview | `docs/architecture/CURRENT.md` |
| ADR quick reference | `docs/ADR_INDEX.md` |

---

## Session Prompt

What aspect are you working on today? State:

1. **Theme namespace** (e.g., strategy/resolver/collision-detection)
2. **Specific question** you're exploring
3. **Context needed** (any recent decisions or constraints)
