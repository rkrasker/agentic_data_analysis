# ADR-006: Per-Record vs Per-Soldier Assignment Difficulty

**Date:** 2026-01-18
**Status:** accepted
**Scope:** architecture

## Context

Analysis of the resolver generation system revealed a fundamental conflation: the system treats **record quality** (how complete/explicit is a document) as a proxy for **assignment difficulty** (how hard is it to determine a soldier's component). These are related but distinct concepts.

**The current model assumes:**
- Degraded records → hard disambiguation → need subtle signals
- Quality tier filtering toward tiers 3-5 "forces discovery of subtle signals"
- Component representation (soldier count) determines generation mode

**Evidence this model is incomplete:**

1. A soldier with pristine tier-1 records can be hard to assign if:
   - Their unit is in a collision zone (e.g., "3rd Regiment" exists in both 82nd and 101st Airborne)
   - All records provide the same partial path (redundant, not complementary)

2. A soldier with degraded tier-5 records can be easy to assign if:
   - Records are complementary (each provides different path segments)
   - Structural inference resolves ambiguity (e.g., "516" must be a regiment due to number range)

3. Entity resolution is NOT the problem. The `soldier_id` is canonical—we always know which records belong to which soldier. The challenge is component assignment, not identity.

**The key insight:** Two individually ambiguous records can, taken together, create a partial path that is globally unique. This aggregation operates at the soldier level, not the record level.

## Options Considered

### Option A: Continue Using Record Quality as Proxy

Keep the current model where quality tiers (1-5) drive sampling, routing, and difficulty estimation.

- Pro: No architectural changes required
- Pro: Quality tiers are already implemented
- Con: Conflates orthogonal concerns
- Con: Filters toward degraded records, not hard soldiers
- Con: Cannot explain why some pristine-record soldiers fail disambiguation

### Option B: Replace Quality Tiers with Assignment Difficulty

Compute soldier-level assignment difficulty, discard record-level quality tiers.

- Pro: Directly models the actual problem
- Con: Loses useful signal about document readability
- Con: Quality tier affects extraction (Layer 1), which still matters
- Con: Large refactor with unclear migration path

### Option C: Three-Layer Disambiguation Model (SELECTED)

Recognize that disambiguation operates at three distinct layers, each with its own difficulty dimension:

1. **Per-record extraction** (quality tier): Can we parse this document?
2. **Cross-record aggregation** (soldier-level): Do records jointly provide a unique path?
3. **Structural inference** (hierarchy-level): Do constraints disambiguate without explicit types?

Model all three explicitly. Use the appropriate layer for each decision point.

- Pro: Correctly separates concerns
- Pro: Preserves existing quality tier infrastructure
- Pro: Explains previously confusing cases
- Pro: Enables targeted improvements at each layer
- Con: More complex model to maintain
- Con: Requires new soldier-level difficulty computation
- Con: Evaluation must stratify by multiple dimensions

## Decision

**Adopt the three-layer disambiguation model.** Each layer operates at a different level of abstraction and has its own difficulty dimension.

### Layer 1: Per-Record Extraction

**Question:** Can we extract unit information from this single document?

**Difficulty factors:**
- OCR quality / legibility
- Field completeness
- Explicit vs. abbreviated unit identifiers
- Clerk format consistency

**Measured by:** Quality tier (1-5), already implemented.

**Where it matters:**
- Signal extraction from individual documents
- Deciding if a record is worth processing
- Training extraction models

### Layer 2: Cross-Record Aggregation

**Question:** Do this soldier's records jointly provide a globally unique component path?

**Difficulty factors:**
- Complementarity: Do records provide different path segments?
- Redundancy: Do all records provide the same partial information?
- Collision position: Is the soldier's unit in a collision zone?
- Signal density: Do any records contain discriminating vocabulary?

**Key insight:** Two records can be individually unparseable but jointly definitive:

```
Record 1: "Co E, 3rd Bn"     → [company=E, battalion=3]
Record 2: "116th Infantry"   → [regiment=116]
Together:                    → [company=E, battalion=3, regiment=116] → UNIQUE
```

Conversely, multiple records can be individually complete but jointly ambiguous:

```
Record 1: "3rd Regiment, Co A"  → [regiment=3, company=A]
Record 2: "3rd Regiment, Co A"  → [regiment=3, company=A]
Together:                       → Still missing division; regiment 3 in COLLISION
```

**Measured by:** Soldier-level assignment difficulty score (to be implemented).

**Where it matters:**
- Sampling for collision training (sample hard soldiers, not degraded records)
- Routing decisions (hard soldiers need strong differentiators)
- Evaluation stratification (accuracy by difficulty tier)

### Layer 3: Structural Inference

**Question:** Do hierarchy constraints disambiguate even when unit types are omitted?

**Key insight:** Numbers constrain valid hierarchy levels:

| Pattern | Inference |
|---------|-----------|
| "516" | Must be regiment (companies are letters/single digits, battalions are ordinals) |
| "E" or "Baker" | Must be company (letter/phonetic designations) |
| "3rd" | Could be battalion or regiment (requires other context) |
| "1st", "2nd" | Ambiguous without structural context |

Two records without explicit unit types can still resolve:

```
Record 1: "516"   → regiment=516 (structurally forced)
Record 2: "3rd"   → battalion=3 (within regiment 516 context)
Record 3: "Co E"  → company=E
Together:         → UNIQUE PATH via structural inference
```

**Difficulty factors:**
- Whether numbers fall in unambiguous ranges
- Whether the hierarchy has unique sub-paths
- Availability of cross-record context for ordinals ("3rd")

**Measured by:** Path uniqueness after structural constraint propagation.

**Where it matters:**
- Resolver pattern generation (must encode structural constraints)
- Disambiguation logic (apply constraints before declaring ambiguity)
- Synthetic generation (model which omissions are resolvable)

### Interaction Between Layers

The layers are not independent. A soldier's overall assignment difficulty depends on all three:

```
Assignment Difficulty = f(
    Layer 1: min/mean record quality across records,
    Layer 2: complementarity of partial paths,
    Layer 3: structural resolvability of remaining ambiguity
)
```

A soldier is **easy** if:
- Any record provides a complete explicit path (Layer 1 sufficient), OR
- Records are complementary and cover all path segments (Layer 2 sufficient), OR
- Structural constraints resolve remaining ambiguity (Layer 3 sufficient)

A soldier is **hard** only if all three layers fail to produce a unique path.

## Consequences

### Synthetic Data Generation

**Current:** Quality tier assigned per-source based on clerk archetype. Soldier difficulty emerges randomly from record distribution.

**Change:** Model soldier-level assignment difficulty explicitly:
- Track which soldiers are in collision zones
- Track complementarity of each soldier's record set
- Track structural resolvability of partial paths
- Tag soldiers with difficulty tier (easy/moderate/hard/extreme)

**New capability:** Generate targeted hard cases by controlling:
- Collision position (place soldier in shared regiment)
- Record redundancy (give soldier multiple records with same partial path)
- Structural ambiguity (use ordinals like "3rd" that require context)

### Resolver Generation

**Current:** Filter records by quality tier to "force subtle signal discovery."

**Change:**
- Sample hard soldiers (Layer 2), not degraded records (Layer 1)
- Ensure collision samples contain soldiers with non-complementary records
- Mine structural constraints explicitly (Layer 3)

**New phases/artifacts:**
- Structural constraint rules: "3-digit numbers are regiments"
- Cross-record aggregation guidance: "combine partial paths before disambiguation"
- Soldier difficulty estimation in sampling

### Routing and Gating

**Current:** Component tier (soldier count) gates which phases run.

**Change:** Also consider assignment difficulty distribution:
- A well-represented component with all-easy soldiers needs minimal disambiguation
- A well-represented component with many hard soldiers needs strong differentiators
- Route based on (component_tier, difficulty_distribution), not just component_tier

### Evaluation

**Current:** Accuracy reported per-component and aggregate.

**Change:** Stratify accuracy by soldier difficulty tier:

```
Component: 82nd_airborne_division
  Overall accuracy: 94.2%
  By difficulty:
    Easy soldiers:     98.1% (n=450)
    Moderate soldiers: 91.3% (n=120)
    Hard soldiers:     76.4% (n=55)
    Extreme soldiers:  42.9% (n=14)
```

This reveals whether improvements are needed at Layer 1 (extraction), Layer 2 (aggregation), or Layer 3 (structural inference).

### Documentation

**New:** CLAUDE.md captures this framework as foundational context for AI assistants.

**Updated:** CURRENT.md must distinguish record quality from assignment difficulty throughout.

## Implementation Roadmap

### Phase 1: Difficulty Computation (Foundation)
- Add `assignment_difficulty` computation to soldier records
- Based on: collision position, record complementarity, structural resolvability
- Output: difficulty_tier per soldier in validation.parquet

### Phase 2: Synthetic Generation Updates
- Tag generated soldiers with difficulty tier
- Add controls for targeted hard case generation
- Ensure evaluation sets have balanced difficulty distribution

### Phase 3: Sampling Refactor
- Refactor collision sampling to prioritize hard soldiers
- Ensure each difficulty tier is represented in training samples
- Update quality tier filtering to be Layer-1 specific (extraction), not difficulty proxy

### Phase 4: Structural Inference
- Encode hierarchy constraints in resolvers
- Add structural inference phase to resolver generation
- Apply constraints in disambiguation before declaring ambiguity

### Phase 5: Evaluation Stratification
- Add difficulty-stratified accuracy reporting
- Track improvement by difficulty tier across experiments
- Alert when hard-soldier accuracy degrades

## References

- CLAUDE.md: Conceptual framework documentation
- ADR-005: Grounded inference (related: positive signals only)
- Claude Code session 2026-01-18: Discovery conversation
- Current implementation: `src/strategies/resolver/generator/llm_phases.py` (quality tier filtering)
- Current implementation: `src/strategies/resolver/generator/sampling.py` (collision sampling)
