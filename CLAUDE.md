# CLAUDE.md

This document provides conceptual context for AI assistants working on this codebase. For setup and usage instructions, see [README.md](README.md).

## What This Project Is

A military records disambiguation system for WWII-era data focused on **state resolution**. Each soldier has a canonical `soldier_id`, but may have **multiple latent states**. Each state corresponds to a specific **post** (a unit assignment). The system must discover how many states exist for a soldier, which records belong to each state, and what post each state resolves to.

We build and test multiple LLM workflows for this problem. Even when not stated in a prompt, the LLM's key function is to **infer states**: propose record groupings, determine how many posts are present, and consolidate each group's evidence into a resolved post.

Across workflows, three variable categories define the strategy space:

1. **Injections**: supplementary reference data injected alongside the prompt
2. **Batching**: how batches are created and composed (e.g., pre-stratified by component, difficulty, or collision structure)
3. **Prompting**: how much reasoning is scaffolded, from explicit stepwise instructions to minimal guidance

## The Core Problem: State Resolution

**Identity resolution is NOT the problem.** We always know which records belong to which soldier.
**State resolution is the problem.** Given all records for a soldier, infer:

1. **How many states exist** (number of posts),
2. **Which records belong to which state**, and
3. **What post each state resolves to** (component path).

### Why It's Hard

1. **No temporal anchors**: We cannot order records or states in time.
2. **Unknown state count**: We do not know how many posts a soldier should resolve to.
3. **Abbreviated records**: Field clerks wrote "E/2/116" not "Company E, 2nd Battalion, 116th Infantry Regiment, 29th Infantry Division".
4. **Missing unit types**: Records say "516" or "3rd" without specifying regiment/battalion/company.
5. **Collisions**: Multiple divisions share the same regiment numbers.
6. **Clerk variation**: Different clerks use different formats, abbreviations, and levels of detail.

## The Three-Layer Difficulty Model

**Critical insight: Record quality ≠ State resolution difficulty** (see [ADR-006](docs/architecture/decisions/ADR-006_per-record-vs-per-soldier-difficulty.md)). For operational computation of soldier difficulty tiers, see [DIFFICULTY_MODEL.md](docs/DIFFICULTY_MODEL.md).

A pristine record in a collision zone may be harder to resolve than degraded records that are complementary. The three layers—extraction, aggregation, structural—are detailed in ADR-006 and the [Glossary](docs/GLOSSARY.md).

**Difficulty tiers:** easy / moderate / hard / extreme

## Key Terminology

See [docs/GLOSSARY.md](docs/GLOSSARY.md) for the canonical glossary including: state, post, component path, collision zone, collision severity, resolver, quality tier, difficulty tier, complementarity score, structural resolvability, familiarity gradient.

## Code Style Preferences

See [docs/CODE_STYLE.md](docs/CODE_STYLE.md) for detailed guidance. Key principles:
- Prefer functions over classes for stateless operations
- No premature abstraction — build for current requirements
- Flat is better than nested; simple is better than clever

## Documentation Map

| I need... | Go to... |
|-----------|----------|
| Architecture overview & status | [docs/architecture/CURRENT.md](docs/architecture/CURRENT.md) |
| Disambiguation model deep-dive | [docs/DISAMBIGUATION_MODEL.md](docs/DISAMBIGUATION_MODEL.md) |
| Difficulty computation (operational) | [docs/DIFFICULTY_MODEL.md](docs/DIFFICULTY_MODEL.md) |
| Three-layer difficulty model | [ADR-006](docs/architecture/decisions/ADR-006_per-record-vs-per-soldier-difficulty.md) |
| Synthetic data v4.1 spec | [docs/components/synthetic_data_generation/CURRENT.md](docs/components/synthetic_data_generation/CURRENT.md) |
| Glossary / terminology | [docs/GLOSSARY.md](docs/GLOSSARY.md) |
| Strategy pitfalls/warnings | [docs/components/strategies/CLAUDE.md](docs/components/strategies/CLAUDE.md) |
| Resolver-specific warnings | [docs/components/strategies/resolver/CLAUDE.md](docs/components/strategies/resolver/CLAUDE.md) |
| Component design docs | `docs/components/[name]/CURRENT.md` |
| ADR quick reference | [docs/ADR_INDEX.md](docs/ADR_INDEX.md) |
| Context packets | [docs/context-packets/](docs/context-packets/) |

## Current State

**Branch**: `main`

**Active work**: Synthetic data v4.1 implementation — Terraform Combine domain with three-layer difficulty model.

**What's stable**: Core pipeline structure, LLM phase interfaces, evaluation metrics framework, documentation organization, difficulty model design (ADR-006, DIFFICULTY_MODEL.md).

**What's in flux**: Synthetic generation code being rewritten for v4.1. Preprocessing will need updates after synthetic v4.1 is complete.

## Key ADRs

| ADR | Decision |
|-----|----------|
| **ADR-006** | Three-layer difficulty model: record quality ≠ resolution difficulty |
| **ADR-007** | Domain decontamination: Terraform Combine fictional setting for synthetic data |
| **ADR-009** | Resolver generation alignment: sample by soldier difficulty, not record quality |

See [docs/ADR_INDEX.md](docs/ADR_INDEX.md) for full list.
