# Resolver Strategy

**Status:** Design phase
**Last Updated:** 2026-01-15

## Purpose

Consolidation using raw text + hierarchy + pre-learned heuristics (resolvers). Resolvers are generated from validation data to guide LLM parsing.

**Key distinction from other strategies:** Resolver generation is a separate build-time workflow that produces artifacts (resolver JSON files). These artifacts are then used at consolidation time. This is NOT a parallel routing pipeline — it's a component-centric generation process that uses ground truth data.

## What LLM Receives (at Consolidation Time)

- Raw text records for batch of soldiers
- Component hierarchy document
- Resolver (pre-learned heuristics for this component)
- Consolidation instructions

---

## Resolver Generation Overview

### Information Flow (Inverted from Main Pipeline)

| Pipeline | Direction | Input | Output |
|----------|-----------|-------|--------|
| **Main Routing** | Unknown → Component | Regex signals | Component assignment |
| **Resolver Gen** | Component → Patterns | Ground truth grouping | Learned heuristics |

Resolver generation does NOT require routing — validation.parquet already contains ground truth component assignments. The workflow groups by known component and learns distinguishing patterns.

### Data Requirements

**Input files:**
- `validation.parquet` — Ground truth assignments (component known)
- `raw.parquet` — Raw text records (joined via soldier_id)
- `config/hierarchies/hierarchy_reference.json` — Structural definitions

**Output files:**
- `config/resolvers/{component}_resolver.json` — Per-component heuristics
- `config/resolvers/resolver_registry.json` — Tracking and rebuild triggers

---

## Relative Threshold System

Rather than absolute sample sizes, tiers are calculated from the validation set distribution:

### Tier Calculation

```python
component_counts = validation_df.groupby("component_id").size()
median = component_counts.median()
p25 = component_counts.quantile(0.25)
p75 = component_counts.quantile(0.75)

# Tier assignment
well_represented:        count >= p75
adequately_represented:  count >= median
under_represented:       count >= p25
sparse:                  count < p25
```

### What Gets Generated Per Tier

| Resolver Section | well_represented | adequately_represented | under_represented | sparse |
|------------------|------------------|------------------------|-------------------|--------|
| **structure** | Full | Full | Full | Full |
| **patterns** | Full | Full | Limited | Not generated |
| **vocabulary** | Full | May be thin | Not generated | Not generated |
| **exclusions.structural** | Full | Full | Full | Full (hierarchy-derived) |
| **exclusions.value_based** | Full | Full | Limited | Not generated |
| **differentiators** | Full | Full | Hierarchy-only | Hierarchy-only |

### Asymmetric Rival Handling

When a **well-represented component** builds differentiators against a **sparse rival**:
- Use the sparse rival's limited data in collision sampling
- Flag differentiator as `rival_undersampled`
- Generate hierarchy-based rules only for that rival

When a **sparse component** builds its own resolver:
- Structure section: Complete (from hierarchy)
- Pattern/vocabulary sections: Explicitly marked `not_generated`
- Differentiators: Hierarchy-only with quality warnings
- Recommendation: Use zero-shot or few-shot strategy instead

---

## Train/Test Split Strategy

### Split Purpose

| Set | Purpose | When Used |
|-----|---------|-----------|
| **Training** | Resolver generation (phases 3-8) | Build time |
| **Test** | Evaluation of consolidation accuracy | After consolidation |

### Split Rules

1. **Stratify by subcomponent** (regiment) within each component
2. **Target ratio:** 75% train / 25% test
3. **Minimum test set:** Configurable, e.g., 10 soldiers per component
4. **Per-stratum minimum:** At least 1 test soldier per regiment (if regiment has ≥4 total)
5. **Leakage policy:** Must comply with ADR-001 (soldier-level disjoint splits, no source overlap)

### Handling Sparse Components

- Components below threshold: No split — all data available for limited resolver or few-shot examples
- Marginal strata: Flag in registry as `evaluation_unreliable`

**Reference policy:** `docs/architecture/decisions/ADR-001_validation-leakage-policy.md`

---

## Resolver Generation Workflow (8 Phases)

### Phase 1: Extract Structural Rules
**Input:** hierarchy_reference.json
**Output:** Valid/invalid designators for regiment, battalion, company
**Data needed:** None (hierarchy only)

### Phase 2: Collision Detection
**Input:** All hierarchy definitions
**Output:** Map of which components share which designators
**Data needed:** None (hierarchy only)
**Uses:** `collision_index` from hierarchy_reference.json

### Phase 3: Collision-Based Sampling
**Input:** Training split of validation.parquet + raw.parquet
**Output:** Head-to-head soldier sets for each collision pair
**Process:**
- For each collision (e.g., regiment 5 shared by 1st ID and 3rd ID)
- Sample N soldiers from each side
- If rival is sparse: use all available, flag as `rival_undersampled`

### Phase 4: Pattern Discovery
**Input:** Collision samples with raw text
**Output:** Text patterns that identify the component
**LLM task:** "What text patterns distinguish {component} from {rival}?"
**Tier requirement:** Skipped for `sparse` components

### Phase 5: Exclusion Mining
**Input:** Cross-component samples
**Output:** Rules for what definitively excludes this component
**Two types:**
- `structural`: From hierarchy (e.g., "PIR mention excludes infantry divisions")
- `value_based`: From data (e.g., "regiment 11 excludes 1st ID")
**Tier requirement:** `value_based` skipped for `sparse` and `under_represented`

### Phase 6: Vocabulary Discovery
**Input:** All training soldiers for target component
**Output:** Characteristic terms with frequency tiers
**LLM task:** Term frequency analysis, tier assignment
**Tier requirement:** Skipped for `sparse` and `under_represented`

### Phase 7: Differentiator Generation
**Input:** Collision analysis + patterns + exclusions + vocabulary
**Output:** Rival-specific disambiguation rules
**Per-rival status:**
- `complete`: Both sides well-sampled
- `rival_undersampled`: Rival is sparse, hierarchy-only rules
- `hierarchy_only`: Target component is sparse

### Phase 8: Tier Assignment
**Input:** All discovered patterns
**Output:** Confidence tier for each pattern
**Tiers:**
- `robust`: >90% reliable in validation sample
- `strong`: 75-90% reliable
- `moderate`: 50-75% reliable
- `tentative`: <50% reliable (tiebreaker only)

---

## Resolver JSON Schema

### Full Resolver (well_represented component)

```json
{
  "meta": {
    "component_id": "1st_infantry_division",
    "generated_utc": "2026-01-15T00:00:00Z",
    "tier": "well_represented",
    "sample_size": 847,
    "pct_of_median": 596.5,
    "generation_mode": "full"
  },

  "structure": {
    "status": "complete",
    "valid_regiments": [1, 5, 7],
    "valid_battalions": [1, 2, 3],
    "valid_companies": ["A", "B", "C", "D", "E", "F", "G", "H", "I", "K", "L", "M"],
    "battalion_designator_type": "numeric"
  },

  "patterns": {
    "status": "complete",
    "entries": {
      "1st Infantry Division": {"means": "component=1st_infantry_division", "tier": "robust"},
      "Big Red One": {"means": "component=1st_infantry_division", "tier": "robust"},
      "2/5": {"means": "battalion=2, regiment=5", "tier": "strong"},
      "5th Inf Regt": {"means": "regiment=5", "tier": "moderate", "note": "needs division signal"}
    }
  },

  "vocabulary": {
    "status": "complete",
    "strong": ["Big Red One", "1st ID", "BRO"],
    "moderate": ["1st Division", "Omaha Beach"],
    "weak": ["Normandy", "ETO"]
  },

  "exclusions": {
    "structural": {
      "status": "complete",
      "rules": [
        {"if": "contains 'PIR' or 'parachute' or 'airborne'", "then": "exclude"},
        {"if": "contains 'Marine' or 'USMC'", "then": "exclude"}
      ]
    },
    "value_based": {
      "status": "complete",
      "rules": [
        {"if": "regiment in [2, 3, 6, 8, 9, 11]", "then": "exclude"},
        {"if": "battalion in ['A', 'B', 'C']", "then": "exclude"}
      ]
    }
  },

  "differentiators": {
    "vs_3rd_infantry_division": {
      "status": "complete",
      "rival_sample_size": 423,
      "rules": [
        "Regiment 11 present → 3rd ID",
        "Regiment 1 present → 1st ID",
        "'Rock of the Marne' vocabulary → 3rd ID",
        "'Big Red One' vocabulary → 1st ID"
      ]
    },
    "vs_36th_infantry_division": {
      "status": "rival_undersampled",
      "rival_sample_size": 23,
      "rival_tier": "sparse",
      "rules": [
        "Regiment 2 or 3 → 36th ID (hierarchy-derived)",
        "Regiment 5 or 7 → 1st ID (hierarchy-derived)"
      ],
      "not_generated": ["vocabulary-based differentiators", "pattern-based rules"]
    }
  }
}
```

### Partial Resolver (sparse component)

```json
{
  "meta": {
    "component_id": "36th_infantry_division",
    "generated_utc": "2026-01-15T00:00:00Z",
    "tier": "sparse",
    "sample_size": 23,
    "pct_of_median": 16.2,
    "generation_mode": "hierarchy_only"
  },

  "structure": {
    "status": "complete",
    "valid_regiments": [1, 2, 3],
    "valid_battalions": [1, 2, 3],
    "valid_companies": ["A", "B", "C", "D", "E", "F", "G", "H", "I", "K", "L", "M"]
  },

  "patterns": {
    "status": "not_generated",
    "reason": "insufficient_sample",
    "rebuild_when": "tier >= under_represented"
  },

  "vocabulary": {
    "status": "not_generated",
    "reason": "insufficient_sample",
    "known_aliases": ["36th ID", "Texas Division"],
    "alias_source": "hierarchy_reference (not validated from data)"
  },

  "exclusions": {
    "structural": {
      "status": "complete",
      "source": "hierarchy",
      "rules": [
        {"if": "contains 'Marine' or 'USMC'", "then": "exclude"},
        {"if": "contains 'airborne' or 'PIR'", "then": "exclude"}
      ]
    },
    "value_based": {
      "status": "not_generated",
      "reason": "insufficient_sample"
    }
  },

  "differentiators": {
    "generation_mode": "hierarchy_only",
    "vs_1st_infantry_division": {
      "status": "hierarchy_only",
      "rules": ["Regiment 2 or 3 → 36th ID", "Regiment 5 or 7 → 1st ID"]
    },
    "vs_2nd_infantry_division": {
      "status": "hierarchy_only",
      "warning": "high_collision_risk",
      "rules": ["Regiment 1, 2, 3 shared — limited disambiguation from structure alone"]
    }
  },

  "quality_notes": [
    "High collision with 2nd_infantry_division — both share regiments 1, 3",
    "Recommend zero-shot or few-shot strategy until more validation data available"
  ]
}
```

---

## Resolver Registry

`config/resolvers/resolver_registry.json` tracks all resolvers and rebuild triggers.

See `docs/data-structures/CURRENT.md` for full schema.

**Key features:**
- Tracks generation status per component
- Records section-level completeness
- Defines rebuild triggers (sample size thresholds)
- Flags quality warnings and recommendations

---

## Key Principles

- **Cross-record context:** Pattern interpretation uses ALL records for soldier
- **Proportional tiers:** Confidence based on proportion of sample, not absolute counts
- **Vocabulary as tiebreaker:** One tier nudge max, never primary evidence
- **Conservative exclusions:** Only incompatible PRESENCE excludes, never absence
- **Graceful degradation:** Sparse components get hierarchy-only resolvers with explicit gaps
- **Rebuild awareness:** Registry tracks when resolvers should be regenerated

---

## Tradeoffs

**Advantages:**
- Focused guidance for LLM
- Pre-learned pattern interpretations
- Explicit disambiguation rules
- Quality-aware (knows its own limitations)

**Disadvantages:**
- Requires generation workflow
- Resolvers must be regenerated if validation data changes
- More complex system
- Sparse components get limited benefit

---

## Key Design Questions (Resolved)

- [x] Resolver token budget (~500-600)? — Yes, target range
- [x] Generation workflow automation level? — Fully automated with LLM phases
- [x] Resolver versioning strategy? — Via resolver_registry.json with rebuild triggers
- [x] How to handle sparse components? — Hierarchy-only resolvers with quality flags

## Key Design Questions (Open)

- [ ] Exact threshold percentiles (p25/median/p75) vs other methods?
- [ ] Minimum per-collision-pair sample size?
- [ ] LLM model selection for generation phases?

---

## Implementation Status

| Component | Status | Location |
|-----------|--------|----------|
| Threshold Calculator | Not started | `src/strategies/resolver/generator/thresholds.py` |
| Train/Test Splitter | Not started | `src/strategies/resolver/generator/split.py` |
| Phase 1-2 (Structure) | Not started | `src/strategies/resolver/generator/structure.py` |
| Phase 3 (Sampling) | Not started | `src/strategies/resolver/generator/sampling.py` |
| Phase 4-8 (LLM Phases) | Not started | `src/strategies/resolver/generator/llm_phases.py` |
| Registry Manager | Not started | `src/strategies/resolver/generator/registry.py` |
| Resolver Executor | Not started | `src/strategies/resolver/executor/` |

---

## References

- Architecture: `docs/architecture/CURRENT.md`
- Data Structures: `docs/data-structures/CURRENT.md`
- Hierarchy Reference: `config/hierarchies/hierarchy_reference.json`
- Comparison: `docs/components/strategies/_comparison/CURRENT.md`
