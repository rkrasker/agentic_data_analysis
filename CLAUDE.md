# CLAUDE.md

This document provides conceptual context for AI assistants working on this codebase. For setup and usage instructions, see [README.md](README.md).

## What This Project Is

A military records disambiguation system for WWII-era data. Given historical records (rosters, manifests, personnel documents) that mention soldiers, determine which military unit (component) each soldier belonged to.

## The Core Problem: Component Assignment

**Entity resolution is NOT the problem.** Each soldier has a canonical `soldier_id`. We always know which records belong to which soldier.

**The problem is component assignment:** Given a soldier (identity known) and all their records, determine their component (military unit) in the organizational hierarchy:

```
Division → Regiment → Battalion → Company
   │           │           │          │
   └───────────┴───────────┴──────────┴── "component path"
```

### Why It's Hard

1. **Abbreviated records**: Field clerks wrote "E/2/116" not "Company E, 2nd Battalion, 116th Infantry Regiment, 29th Infantry Division"

2. **Missing unit types**: Records say "516" or "3rd" without specifying regiment/battalion/company

3. **Collisions**: Multiple divisions share the same regiment numbers (82nd Airborne has 3rd Regiment; so does 101st Airborne)

4. **Clerk variation**: Different clerks use different formats, abbreviations, and levels of detail

## The Three-Layer Disambiguation Model

This is the fundamental analytical framework. Assignment difficulty operates at three layers:

### Layer 1: Per-Record Extraction
Can we parse explicit unit information from a single document?

- "Co E, 2nd Bn, 116th Inf, 29th Div" → full path extracted
- "E2-116" → partial path (company, battalion, regiment)
- "3rd" → minimal (just a number, no unit type)

**Quality tiers (1-5)** measure this layer. Tier 1 = explicit/complete. Tier 5 = fragmentary.

### Layer 2: Cross-Record Aggregation
Do a soldier's records **jointly** provide a unique path?

Two individually ambiguous records can be complementary:

| Record | Provides | Alone |
|--------|----------|-------|
| Record 1 | "Co E, 3rd Bn" | Ambiguous (which regiment?) |
| Record 2 | "116th Infantry" | Ambiguous (which battalion?) |
| **Together** | Co E, 3rd Bn, 116th | Unique path |

**Key insight**: A soldier with multiple degraded records may be easier to assign than a soldier with one pristine record, if the degraded records are complementary.

### Layer 3: Structural Inference
Do hierarchy constraints disambiguate even when unit types are omitted?

| Record | Text | Inference |
|--------|------|-----------|
| "516" | No unit type | Must be regiment (companies are letters, battalions are 1st/2nd/3rd) |
| "3rd" | No unit type | Could be battalion or company within the structurally-inferred regiment |

The hierarchy structure itself is a disambiguation signal. Numbers constrain valid hierarchy levels:
- "516" can only be a regiment (number too high for battalion/company)
- "A" or "E" can only be a company (letters)
- "1st", "2nd", "3rd" could be battalion or regiment (requires other context)

## The Critical Distinction

**Record quality ≠ Assignment difficulty**

| Scenario | Record Quality | Assignment Difficulty |
|----------|---------------|----------------------|
| Pristine record saying "3rd Regiment" in collision zone | High (Tier 1) | High (ambiguous) |
| Degraded records saying "516" + "3rd" + "Co E" | Low (Tier 4-5) | Low (structurally unique) |

Filtering toward degraded records does NOT guarantee hard cases. Filtering toward soldiers in collision zones with redundant (not complementary) records does.

## Key Terminology

| Term | Meaning |
|------|---------|
| **Component** | A military unit at any hierarchy level (division, regiment, battalion, company) |
| **Component path** | Full hierarchy: Division/Regiment/Battalion/Company |
| **Collision** | When two components share a sub-unit identifier (e.g., both 82nd and 101st have "3rd Regiment") |
| **Collision zone** | The set of soldiers whose records fall in a collision (their partial path is non-unique) |
| **Resolver** | A JSON artifact containing patterns, vocabulary, and rules for disambiguating a component |
| **Quality tier** | Per-record measure of document completeness/explicitness (1=pristine, 5=fragmentary) |
| **Assignment difficulty** | Per-soldier measure of whether their records jointly resolve to a unique path |
| **Partial path** | Incomplete hierarchy (e.g., regiment + battalion but no division) |
| **Structural inference** | Using hierarchy constraints to infer unit types when text omits them |

## Architecture Overview

### Synthetic Data Generation (`src/synthetic/`)
Generates training/test data. Creates soldiers first (with canonical component assignments), then generates records for those soldiers using clerk archetypes and situational vocabulary.

- **soldier_factory.py**: Creates soldiers with names, ranks, component assignments
- **source_generator.py**: Creates document sources with clerk/situation context
- **pipeline.py**: Orchestrates generation, assigns quality tiers

### Resolver Generation (`src/strategies/resolver/generator/`)
Builds disambiguation artifacts (resolvers) from training data using LLM-powered phases.

- **llm_phases.py**: Pattern discovery, vocabulary extraction, differentiator generation
- **sampling.py**: Collision sampling for training examples
- **thresholds.py**: Component tier calculation and phase gating
- **prompts.py**: LLM prompt construction

### Resolver Execution (`src/strategies/resolver/executor/`)
Applies resolvers to assign components to soldiers at inference time.

### Evaluation (`src/evaluation/`)
Measures assignment accuracy. Metrics are per-soldier (one assignment per soldier, regardless of record count).

## What NOT to Assume

1. **Record degradation ≠ assignment difficulty.** A soldier with pristine records can be hard to assign (collision zone, redundant information). A soldier with degraded records can be easy (complementary partials, structural inference).

2. **Entity resolution is not the problem.** The `soldier_id` is canonical. We're not figuring out "is this the same person?" We're figuring out "what unit was this person in?"

3. **Absence is not evidence.** A record lacking "ABN" does not mean the soldier isn't airborne. Records are abbreviated, not comprehensive. Only the presence of conflicting indicators counts as negative evidence. (See ADR-005)

4. **Single-record reasoning is insufficient.** The disambiguation task operates across all of a soldier's records. Two useless records can combine to a definitive assignment.

5. **Unit types can be inferred.** Even when text omits "Regiment" or "Battalion," the numbers themselves constrain the possibilities. "516" must be a regiment. "E" must be a company.

## ADR Pointers

| ADR | Topic | Key Insight |
|-----|-------|-------------|
| ADR-001 | Validation leakage policy | Train/test splits are soldier-level disjoint |
| ADR-002 | Dual-run stateful extraction | Hard cases detected via forward/reverse batch comparison |
| ADR-004 | Few-shot corpus from resolver | Hard cases become training examples |
| ADR-005 | Grounded inference | Patterns must be observed or marked inferred; no absence-based rules |
| ADR-006 | Assignment difficulty model | The three-layer disambiguation framework (this document's foundation) |

## Current State

**Branch**: `feature/assignment-difficulty-model`

**Active work**: Refactoring the conceptual model to distinguish per-record quality from per-soldier assignment difficulty. This affects synthetic generation, resolver training, and evaluation stratification.

**What's stable**: Core pipeline structure, LLM phase interfaces, evaluation metrics framework.

**What's in flux**: How difficulty is modeled, how sampling selects training examples, how routing decisions are made.
