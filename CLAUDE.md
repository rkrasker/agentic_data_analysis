# CLAUDE.md

This document provides conceptual context for AI assistants working on this codebase. For setup and usage instructions, see [README.md](README.md).

## What This Project Is

A military records disambiguation system for WWII-era data focused on **state resolution**. Each soldier has a canonical `soldier_id`, but may have **multiple latent states**. Each state corresponds to a specific **post** (a unit assignment). The system must discover how many states exist for a soldier, which records belong to each state, and what post each state resolves to.

We will build and test multiple LLM workflows for this problem. Even when not stated in a prompt, the LLM's key function is to **infer states**: propose record groupings, determine how many posts are present, and consolidate each group's evidence into a resolved post.

Across workflows, three variable categories define the strategy space:

1. **Injections**: supplementary reference data injected alongside the prompt (not the prompt itself).
2. **Batching**: how batches are created and composed (e.g., pre-stratified by component, difficulty, or collision structure).
3. **Prompting**: how much reasoning is scaffolded, from explicit stepwise instructions (e.g., chain-of-thought style) to minimal guidance.

One major strategy uses **resolvers**: pre-built heuristics tailored to parsing a given component. These resolvers are not hand-authored; they are built via a sequence of per-component LLM runs that extract patterns, vocabulary, and differentiators, then injected back into later inference passes.

## The Core Problem: State Resolution (Post Assignment)

**Identity resolution is NOT the problem.** We always know which records belong to which soldier.
**State resolution is the problem.** Given all records for a soldier, infer:

1. **How many states exist** (number of posts),
2. **Which records belong to which state**, and
3. **What post each state resolves to** (component path).

A **post** is the concrete unit assignment in the hierarchy:

```
Division → Regiment → Battalion → Company
   │           │           │          │
   └───────────┴───────────┴──────────┴── "component path"
```

A **state** is the latent segment of a soldier's service that should resolve to a post.

### Why It's Hard

1. **No temporal anchors**: We cannot order records or states in time.
2. **Unknown state count**: We do not know how many posts a soldier should resolve to.
3. **Abbreviated records**: Field clerks wrote "E/2/116" not "Company E, 2nd Battalion, 116th Infantry Regiment, 29th Infantry Division".
4. **Missing unit types**: Records say "516" or "3rd" without specifying regiment/battalion/company.
5. **Collisions**: Multiple divisions share the same regiment numbers (82nd Airborne has 3rd Regiment; so does 101st Airborne).
6. **Clerk variation**: Different clerks use different formats, abbreviations, and levels of detail.

## Key Terminology

| Term | Meaning |
|------|---------|
| **State** | A latent segment of a soldier's service that should resolve to one post |
| **Post** | A concrete unit assignment at a specific component path |
| **Component** | A military unit at any hierarchy level (division, regiment, battalion, company) |
| **Component path** | Full hierarchy: Division/Regiment/Battalion/Company |
| **Collision** | When two components share a sub-unit identifier (e.g., both 82nd and 101st have "3rd Regiment") |
| **Collision zone** | The set of records or states whose partial paths are non-unique |
| **Resolver** | A JSON artifact containing patterns, vocabulary, and rules for disambiguating a post |
| **Quality tier** | Per-record measure of document completeness/explicitness (1=pristine, 5=fragmentary) |
| **State resolution difficulty** | Per-soldier measure of whether records can be partitioned into correct states and each state resolved to a unique post |
| **Partial path** | Incomplete hierarchy (e.g., regiment + battalion but no division) |
| **Structural inference** | Using hierarchy constraints to infer unit types when text omits them |

## Code Style Preferences

See [docs/CODE_STYLE.md](docs/CODE_STYLE.md) for detailed guidance. Key principles:
- Prefer functions over classes for stateless operations
- No premature abstraction — build for current requirements
- Flat is better than nested; simple is better than clever

## Documentation Map

| I need... | Go to... |
|-----------|----------|
| Disambiguation model deep-dive | [docs/DISAMBIGUATION_MODEL.md](docs/DISAMBIGUATION_MODEL.md) |
| Strategy pitfalls/warnings | [docs/components/strategies/CLAUDE.md](docs/components/strategies/CLAUDE.md) |
| Resolver-specific warnings | [docs/components/strategies/resolver/CLAUDE.md](docs/components/strategies/resolver/CLAUDE.md) |
| Component design docs | `docs/components/[name]/CURRENT.md` |
| Architecture overview | [docs/architecture/CURRENT.md](docs/architecture/CURRENT.md) |
| ADR quick reference | [docs/ADR_INDEX.md](docs/ADR_INDEX.md) |
| Context packets | [docs/context-packets/](docs/context-packets/) |

## Architecture Overview

### Synthetic Data Generation (`src/synthetic/`)
Generates training/test data. Creates soldiers with one or more states/posts, then generates records for those states using clerk archetypes and situational vocabulary.

- **soldier_factory.py**: Creates soldiers with names, ranks, post assignments
- **source_generator.py**: Creates document sources with clerk/situation context
- **pipeline.py**: Orchestrates generation, assigns quality tiers

### Preprocessing (`src/preprocessing/`)
Extracts structured signals from raw text using deterministic regex patterns. Outputs `canonical.parquet` with list-valued extraction columns that feed batching and strategy execution. Raw text remains the primary LLM input; preprocessing signals are supplementary.

- **regex_preprocessing.py**: Core extraction engine (glossary-driven regex)
- **glossary_generator.py**: Builds term glossaries from synthetic configs
- **preprocessing_adapter.py**: Bridges synthetic output (`raw.parquet`) to `canonical.parquet`

### Strategy Execution (`src/strategies/`)
Runs LLM workflows to discover states and resolve posts. Strategies vary by injections, batching, and prompting. Resolvers are one strategy among several and require a pre-build pipeline.

For strategy-specific warnings and pitfalls, see:
- [docs/components/strategies/CLAUDE.md](docs/components/strategies/CLAUDE.md) — Cross-strategy LLM pitfalls
- [docs/components/strategies/resolver/CLAUDE.md](docs/components/strategies/resolver/CLAUDE.md) — Resolver-specific pitfalls

#### Other Strategies (Stub)

- Few-shot, no resolvers
- Few-shot with resolvers
- Few-shot, component-specific only
- Few-shot, general only
- Few-shot, mixed general and component-specific

#### Resolver Strategy: Pre-build (`src/strategies/resolver/generator/`)
Builds disambiguation artifacts (resolvers) from training data using per-component LLM runs.

- **llm_phases.py**: Pattern discovery, vocabulary extraction, differentiator generation
- **sampling.py**: Collision sampling for training examples
- **thresholds.py**: Component tier calculation and phase gating
- **prompts.py**: LLM prompt construction

#### Strategy Execution: Inference (`src/strategies/`)
Applies the selected strategy during inference to group records into states and resolve posts. The resolver strategy implements this via `src/strategies/resolver/executor/`, which applies pre-built resolvers to parse records and resolve posts within inferred states.

### Evaluation (`src/evaluation/`)
Measures state resolution accuracy: state count, grouping quality, and post resolution per state.

## Architecture Status

### Implemented
- **Synthetic data generation**: v3 pipeline in `src/synthetic/` with generated artifacts in `data/synthetic/`.
- **Preprocessing**: regex extraction, glossary generation, and synthetic adapter in `src/preprocessing/`.
- **Harness foundation**: base strategy interface, train/test split, component batching, and evaluation metrics in `src/strategies/base_strategy.py`, `src/evaluation/split.py`, `src/batching/batch_manager.py`, `src/evaluation/metrics.py`.
- **LLM infrastructure**: provider layer in `src/utils/llm/`.
- **Resolver strategy (pre-build)**: resolver generation modules in `src/strategies/resolver/generator/`.

### Partially Implemented
- **Batching**: component batching is implemented; token-budget batching exists in `src/utils/llm/token_batcher.py` but is not wired end-to-end.
- **Evaluation**: metrics exist, but there is no strategy runner or automated evaluation pipeline.
- **Preprocessing routing/ID resolution**: described in docs, but router/ID resolver modules are not present in `src/preprocessing/`.

### Not Yet Implemented
- **Resolver strategy (execution runs)**: the resolver build pipeline exists, but the full data processing runs over datasets are not built.
- **Zero-shot, few-shot, multi-pass strategies**: stubs only under `src/strategies/`.

## Current State

**Branch**: `main`

**Active work**: Documentation restructure complete. Ready for multi-agent workflow optimization.

**What's stable**: Core pipeline structure, LLM phase interfaces, evaluation metrics framework, documentation organization.

**What's in flux**: How difficulty is modeled, how sampling selects training examples, how routing decisions are made.
