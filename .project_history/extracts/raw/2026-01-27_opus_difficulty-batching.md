# Session Extract: Difficulty Batching Strategy

**Date:** 2026-01-27
**Session Type:** Opus 4.5 strategy session
**Topic:** Designing `compute_soldier_difficulty()` for resolver sampling

---

## Context

ADR-009 established that resolver sampling should prioritize soldiers by assignment difficulty (Layers 2-3) rather than filtering by record quality tier. This session operationalized that principle into a computable model.

---

## Key Decisions Made

### 1. Data Source: canonical.parquet (Not Raw Text)

**Decision:** Difficulty computation operates on pre-extracted features from the regex preprocessing stage, not raw text.

**Rationale:** The characterized (`Unit_Term_Digit_Term:Pair`) and uncharacterized (`Unchar_Alpha`, `Unchar_Digits`) columns represent work already done. Leveraging them avoids redundant parsing and ensures consistency with downstream processing.

**Implication:** The difficulty model depends on regex preprocessing quality. If extraction fails, records contribute nothing to complementarity (which is correct behavior — unextractable records are unhelpful).

### 2. Confidence Weights for Level Coverage

**Decision:** Three-tier confidence weighting:
- 1.0 for characterized extractions (pattern + value recognized)
- 0.75 for uncharacterized values matching exactly one hierarchy level
- 0.25 for uncharacterized values matching multiple levels

**Rationale:** Real-world records will have more uncharacterized than characterized extractions (clerks write "3" not "Fleet 3"). A binary (covered/not-covered) approach would discard the partial signal from ambiguous values.

**Alternative considered:** Binary scoring (covered if characterized OR single-level unchar match). Rejected because it loses nuance — an ambiguous "3" that could be fleet/squadron/element is weaker signal than an unambiguous "A" that can only be wing.

### 3. Complementarity Denominator: min(branch_depth, 4)

**Decision:** Cap denominator at 4 regardless of actual branch depth.

**Rationale:** Deep hierarchies may include micro-levels (fire teams, squads) that don't appear in formal records. A soldier in a 5-level branch with 3 levels covered shouldn't be penalized more than one in a 4-level branch with 3 covered.

**Alternative considered:** Use actual branch depth. Rejected because it creates false difficulty signal from organizational granularity rather than disambiguation challenge.

**Alternative considered:** Use (depth - 1) to exclude leaf level. Rejected because it breaks down for 3-level branches where 2/2 = 1.0 always.

### 4. Fixed Thresholds (Not Percentile-Based)

**Decision:** Difficulty tier cutoffs are fixed at 0.7 (moderate/hard boundary) and 0.4 (hard/extreme boundary).

**Rationale:** For sampling purposes, "extreme" should mean genuinely pathological cases, not just the bottom third of a well-behaved distribution. Fixed thresholds ensure consistent meaning across different datasets.

**Alternative considered:** Percentile-based tiers (top/middle/bottom third). Rejected because it makes difficulty relative to data distribution rather than absolute disambiguation challenge.

### 5. Collision Detection: Extraction-Based, Not Membership-Based

**Decision:** A soldier is "in collision" based on whether their extracted partial path is ambiguous, not whether their ground-truth component happens to share designators with another component.

**Rationale:** A soldier whose true component collides but whose records contain discriminating terms isn't actually a hard case — the records resolve the ambiguity. We want to measure difficulty of the records, not difficulty of the component.

**Implication:** This means collision position is computed per-soldier, not looked up from component metadata.

### 6. Multi-Branch Handling: Take Maximum Complementarity

**Decision:** When a soldier's records could be interpreted under multiple candidate branches, compute complementarity for each and take the maximum.

**Rationale:** We want to know the best-case interpretation. If even the most favorable reading has low complementarity, the soldier is genuinely hard. The alternative (average or minimum) would penalize soldiers whose records clearly point toward one branch.

### 7. Document Location: Peer to DISAMBIGUATION_MODEL.md

**Decision:** Create `docs/DIFFICULTY_MODEL.md` as a top-level reference document, not embedded in resolver CURRENT.md.

**Rationale:** Difficulty computation is relevant across multiple components (resolver sampling, evaluation stratification, synthetic data generation, cross-strategy comparison). Embedding it in resolver docs would hide it from other consumers.

---

## Alternatives Considered and Rejected

| Alternative | Why Rejected |
|-------------|--------------|
| Binary level coverage (covered/not) | Loses partial signal from ambiguous unchar values |
| Actual branch depth as denominator | False signal from micro-levels |
| Percentile-based thresholds | Makes "extreme" relative, not absolute |
| Ground-truth collision membership | Doesn't reflect record-level difficulty |
| Average complementarity across branches | Penalizes clear single-branch cases |
| ADR for difficulty model | This is specification, not architectural decision |

---

## Implications for Implementation

### compute_soldier_difficulty() Dependencies

1. **hierarchy_reference.json** — Must include `valid_designators` per level to enable validity checking of uncharacterized values
2. **Collision index** — Output from `extract_structure()`, maps (level, value) → component set
3. **Discriminating terms** — May need explicit list in hierarchy config (open question)

### Data Flow

```
canonical.parquet
    ↓
Group records by soldier_id
    ↓
For each record: map extractions → level confidences
    ↓
Aggregate: max confidence per level across records
    ↓
Compute: complementarity, collision_position, structural_resolvability
    ↓
Apply tier thresholds
    ↓
DifficultyAssessment
```

### Integration Points

- `sampling.py` calls `compute_soldier_difficulty()` for each soldier
- `sample_collisions()` filters/prioritizes by `difficulty_tier in ['hard', 'extreme']`
- Evaluation framework can stratify accuracy reports by difficulty tier
- Synthetic generation can target specific difficulty distributions

---

## Warnings and Pitfalls

### 1. Uncharacterized Value Validity Checking

The model assumes `hierarchy_reference.json` has complete `valid_designators` lists. If these are incomplete, legitimate values will be scored as 0.0 (no match), artificially deflating complementarity.

**Mitigation:** Validate hierarchy config completeness before running difficulty computation.

### 2. Characterized Extraction Dependency

Confidence 1.0 for characterized extractions assumes the regex patterns are correct. A misclassified extraction (e.g., `Fleet:3` when it's actually `Squadron:3`) propagates with high confidence.

**Mitigation:** This is upstream quality — regex patterns should be validated independently.

### 3. Edge Case: All Records Empty

A soldier with no extractable values gets complementarity = 0, landing in Extreme tier. This is correct behavior, but such soldiers may not be useful for training differentiators (no signal to learn from).

**Mitigation:** Sampling should probably exclude soldiers with zero extractions entirely, not just deprioritize them.

### 4. Structural Resolvability Requires Discriminating Terms

The model relies on knowing which terms are unique to which branch. If `discriminating_terms` isn't populated in hierarchy config, structural resolvability will always be FALSE.

**Mitigation:** Open question #3 — need to define how discriminating terms are extracted/configured.

---

## Open Items Deferred

1. **Structural discriminator extraction** — How to automatically identify branch-unique terms
2. **Migration path** — How to refactor existing resolver code
3. **Minimum extraction threshold** — Should soldiers with zero extractions be excluded from sampling entirely?
