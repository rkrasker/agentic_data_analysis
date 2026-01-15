# Thread Extract: Resolver Generation Workflow Design

**Date:** 2026-01-15
**LLM:** Claude Opus 4.5
**Session:** resolver-generation-design
**Participants:** Eli, Opus

---

## Context

Detailed design session for the resolver generation workflow. Clarified that resolver generation is NOT a parallel routing pipeline, but rather a component-centric build-time workflow that produces artifacts from ground truth validation data.

---

## Key Discussions

### 1. Routing vs Resolver Generation (Misconception Corrected)

**Initial assumption:** Resolver strategy requires a parallel routing pipeline because it uses LLM in preprocessing to create heuristics.

**Correction:** Routing implies uncertainty about component assignment. For resolver generation:
- Validation data ALREADY HAS ground truth component assignments
- No routing decision needed — you GROUP BY known component
- Information flow is inverted from main pipeline

| Pipeline | Direction | Input | Output |
|----------|-----------|-------|--------|
| Main Routing | Unknown → Component | Regex signals | Component assignment |
| Resolver Gen | Component → Patterns | Ground truth grouping | Learned heuristics |

**Conclusion:** Two separate workflows sharing infrastructure, not parallel routing pipelines.

### 2. Relative Threshold System

**Problem:** Validation data will have inconsistent distribution across components. Absolute thresholds (e.g., "min 30 soldiers") don't account for this.

**Solution:** Calculate tiers from validation set distribution using percentiles:
```
well_represented:        count >= p75
adequately_represented:  count >= median
under_represented:       count >= p25
sparse:                  count < p25
```

This makes thresholds self-calibrating to actual data distribution.

### 3. Tiered Resolver Generation

What gets generated varies by tier:

| Section | well_represented | adequately_represented | under_represented | sparse |
|---------|------------------|------------------------|-------------------|--------|
| structure | Full | Full | Full | Full |
| patterns | Full | Full | Limited | Not generated |
| vocabulary | Full | May be thin | Not generated | Not generated |
| exclusions.structural | Full | Full | Full | Full (hierarchy) |
| exclusions.value_based | Full | Full | Limited | Not generated |
| differentiators | Full | Full | Hierarchy-only | Hierarchy-only |

### 4. Asymmetric Rival Handling

**Strong component building differentiator against weak rival:**
- Use weak rival's limited data in collision sampling
- Flag differentiator as `rival_undersampled`
- Generate hierarchy-based rules only for that rival

**Weak component building its own resolver:**
- Structure: Complete (from hierarchy)
- Patterns/vocabulary: Explicitly marked `not_generated`
- Differentiators: Hierarchy-only with quality warnings
- Recommendation: Use zero-shot or few-shot strategy instead

### 5. Train/Test Split Strategy

**Purpose:**
- Training set: Resolver generation (phases 3-8)
- Test set: Evaluation (held out to prevent data leakage)

**Rules:**
- Stratify by regiment within each component
- Target 75/25 split
- Minimum test set per component (configurable)
- Sparse components: No split — all data for limited resolver or few-shot

### 6. Resolver Registry for Rebuild Tracking

`resolver_registry.json` tracks:
- Generation status per component
- Section-level completeness
- Subcomponent coverage (train/test counts per regiment)
- Rebuild triggers (conditions for regeneration)
- Quality notes and recommendations

**Rebuild workflow:** When new validation data arrives, compare counts against triggers, flag components for regeneration.

---

## Walkthrough: 1st Infantry Division Resolver

Used 1st Infantry Division as example to illustrate the 8-phase workflow:

1. **Structure extraction:** Valid regiments [1, 5, 7], battalions [1, 2, 3]
2. **Collision detection:** Regiment 1 collides with 4 rivals, regiments 5 and 7 each collide with 4 rivals
3. **Collision sampling:** Head-to-head soldier sets from validation data
4. **Pattern discovery:** LLM identifies distinguishing text patterns
5. **Exclusion mining:** Structural (from hierarchy) + value-based (from data)
6. **Vocabulary discovery:** "Big Red One" = strong, "Normandy" = weak
7. **Differentiator generation:** Per-rival disambiguation rules
8. **Tier assignment:** robust/strong/moderate/tentative confidence levels

---

## Decisions Made

1. **No parallel routing pipeline** — Resolver generation uses ground truth, not routing
2. **Relative thresholds** — Based on percentiles of actual validation distribution
3. **Graceful degradation** — Sparse components get hierarchy-only resolvers with explicit gaps
4. **Asymmetric handling** — Strong components can use weak rivals; weak components get limited resolvers
5. **Rebuild tracking** — Registry tracks when resolvers should be regenerated

---

## Artifacts Updated

### Major Updates

| File | Changes |
|------|---------|
| `docs/components/strategies/resolver/CURRENT.md` | Complete rewrite with implementation plan |
| `docs/data-structures/CURRENT.md` | Added resolver_registry.json, train_test_split.json schemas |

### Minor Updates

| File | Changes |
|------|---------|
| `docs/architecture/CURRENT.md` | Added resolver status, generation workflow to next steps |
| `docs/components/strategies/_comparison/CURRENT.md` | Updated resolver status to "Detailed design" |

---

## New Data Structures Defined

### resolver_registry.json
- Tracks all resolver generation status
- Records thresholds used (p25, median, p75)
- Per-component: tier, sample_size, section completeness, rebuild triggers
- Summary: counts by tier, rebuild candidates

### train_test_split.json
- Records split used for resolver generation
- Per-component: train_ids, test_ids, by_stratum breakdown
- Enables reproducible splits and evaluation integrity

### {component}_resolver.json (updated schema)
- Added `meta.tier`, `meta.generation_mode`, `meta.pct_of_median`
- Added `status` field to each section
- Added `quality_notes` array for warnings/recommendations

---

## Implementation Path (Not Started)

Proposed file structure:
```
src/strategies/resolver/generator/
├── thresholds.py      # Tier calculation from validation distribution
├── split.py           # Train/test split with stratification
├── structure.py       # Phase 1-2: hierarchy extraction, collision detection
├── sampling.py        # Phase 3: collision-based sampling
├── llm_phases.py      # Phase 4-8: LLM-driven pattern/vocabulary/exclusion discovery
└── registry.py        # Registry management and rebuild checks
```

---

## Open Questions

- [ ] Exact threshold percentiles (p25/median/p75) vs other methods?
- [ ] Minimum per-collision-pair sample size?
- [ ] LLM model selection for generation phases?
