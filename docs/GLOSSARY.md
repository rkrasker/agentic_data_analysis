# Glossary

Canonical terminology definitions for the military records disambiguation project.

| Term | Meaning |
|------|---------|
| **State** | A latent segment of a soldier's service that should resolve to one post |
| **Post** | A concrete unit assignment at a specific component path |
| **Component** | A military unit at any hierarchy level (division, regiment, battalion, company) |
| **Component path** | Full hierarchy: Division/Regiment/Battalion/Company |
| **Collision** | When two components share a sub-unit identifier (e.g., both 82nd and 101st have "3rd Regiment") |
| **Collision zone** | The set of records or states whose partial paths are non-unique |
| **Collision severity** | How ambiguous a post is: none/low/medium/high/cross_branch |
| **Resolver** | A JSON artifact containing patterns, vocabulary, and rules for disambiguating a post |
| **Quality tier** | Per-record measure of extraction difficulty (Layer 1): 1=pristine, 5=fragmentary |
| **Difficulty tier** | Per-soldier measure of resolution difficulty (all layers): easy/moderate/hard/extreme |
| **Complementarity score** | How well a soldier's records cover different path segments (0.0-1.0) |
| **Structural resolvability** | Whether Layer 3 constraints can resolve ambiguity |
| **Structural discriminator** | A level name, designator value, or depth that uniquely identifies a branch |
| **Partial path** | Incomplete hierarchy (e.g., regiment + battalion but no division) |
| **Structural inference** | Using hierarchy constraints to infer unit types when text omits them |
| **Familiarity gradient** | Clerks abbreviate for their own unit, spell out foreign units |

## Three-Layer Difficulty Model

See [ADR-006](architecture/decisions/ADR-006_per-record-vs-per-soldier-difficulty.md) for full details.

| Layer | Question | Measured By | Level |
|-------|----------|-------------|-------|
| **1. Extraction** | Can we parse this record? | Quality tier (1-5) | Per-record |
| **2. Aggregation** | Do records jointly resolve? | Complementarity score | Per-soldier |
| **3. Structural** | Do constraints disambiguate? | Structural resolvability | Per-soldier |

**Key insight:** Record quality (Layer 1) does not equal resolution difficulty. A pristine record in a collision zone may be harder to resolve than degraded records that are complementary.
