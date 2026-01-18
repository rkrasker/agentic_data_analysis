# ADR-004: Generate Few-Shot Corpus During Resolver Generation

**Date:** 2026-01-18
**Status:** proposed
**Scope:** strategy/resolver, strategy/few-shot

## Context

The project has multiple consolidation strategies planned:
- **Zero-shot**: LLM + hierarchy only
- **Few-shot**: LLM + hierarchy + worked examples
- **Resolver**: LLM-generated heuristics executed deterministically

The few-shot strategy requires a corpus of solved examples in the format:
```
Records: [raw text records for a soldier]
Consolidation: {component, regiment, battalion, company, confidence, evidence}
```

Currently, resolver generation identifies **hard cases** — soldiers whose records are ambiguous or difficult to classify. These hard cases are:
1. Flagged during dual-run extraction
2. Used for pattern validation during reconciliation
3. **Discarded** after generation (only the count is stored)

Hard cases have all the properties of ideal few-shot examples:
- Represent genuinely difficult edge cases
- Have ground truth labels (from validation data)
- After reconciliation, we know which patterns resolved them
- Are exactly the ambiguity scenarios the few-shot strategy should handle

## Options Considered

### Option A: Generate Few-Shot Corpus as Resolver Byproduct

During reconciliation, persist resolved hard cases as few-shot examples.

**Data already available during reconciliation:**
| Source | Field |
|--------|-------|
| `HardCase` | `soldier_id`, `reason`, `flagged_in` |
| `records_df` | Raw text records (fetched but discarded) |
| `validation.parquet` | Ground truth component, regiment, battalion, company |
| LLM reconciliation | `resolved_by_pattern`, `resolution_notes` |

**Output location options:**
1. New section in resolver JSON: `few_shot_examples`
2. Separate corpus file: `config/few_shot/corpus.json`
3. Per-component files: `config/few_shot/{component_id}_examples.json`

- Pro: No additional data collection needed — reuses existing pipeline
- Pro: Hard cases are exactly the difficult examples few-shot should teach
- Pro: Examples come with resolution reasoning (evidence field)
- Pro: Dual-run agreement (`"both"` vs single-run) indicates genuine difficulty
- Con: Couples resolver and few-shot strategies
- Con: Adds complexity to reconciliation output
- Con: Few-shot examples limited to hard cases (may miss "easy but representative" examples)

### Option B: Separate Few-Shot Corpus Generation

Build a dedicated pipeline to select and annotate few-shot examples.

- Pro: Can select diverse examples (not just hard cases)
- Pro: Decoupled from resolver generation
- Pro: Can curate examples manually
- Con: Duplicates data access patterns already in resolver generation
- Con: Requires separate implementation effort
- Con: May miss the most valuable examples (hard cases)

### Option C: Hybrid — Resolver Seeds + Manual Curation

Generate initial corpus from resolver hard cases, then allow manual additions.

- Pro: Best of both — automatic generation + curation flexibility
- Pro: Hard cases provide strong baseline
- Pro: Can add "representative easy" examples later
- Con: More complex corpus management
- Con: Need to track example provenance (auto vs manual)

## Decision

*[To be decided]*

**Leaning toward Option C (Hybrid)** because:
1. Hard cases from resolver are high-value and essentially free to capture
2. Manual curation allows filling gaps (easy representative examples)
3. Provenance tracking enables analysis of which example types help most

## Proposed Implementation (if Option A or C)

### 1. Extend HardCaseAnalysis

```python
@dataclass
class HardCaseAnalysis:
    # Existing fields
    soldier_id: str
    flagged_in: str
    reason: str
    notes: str
    resolved_by_pattern: Optional[str]
    resolution_notes: str

    # New fields for few-shot export
    raw_records: List[str] = field(default_factory=list)
    ground_truth: Optional[Dict[str, Any]] = None  # from validation.parquet
```

### 2. Capture During Reconciliation

In `Reconciler.reconcile()` after fetching hard case records:
```python
# Already happening (line 398-400):
hard_case_records = self._get_hard_case_records(hard_cases, records_df, ...)

# Add: join ground truth from validation data
ground_truth = self._get_ground_truth(hard_cases, validation_df)

# Persist both on HardCaseAnalysis
```

### 3. Export Format

```json
{
  "few_shot_examples": [
    {
      "id": "82nd_hc_001",
      "soldier_id": "S1234",
      "source": "resolver_hard_case",
      "source_component": "82nd_airborne_division",
      "difficulty": "both",
      "ambiguity_reason": "conflicting_signals",

      "records": [
        "Smith 3/505 PIR jumped Normandy",
        "Smith C co airborne div"
      ],

      "consolidation": {
        "component_id": "82nd_airborne_division",
        "regiment": 505,
        "battalion": 3,
        "company": "C"
      },

      "confidence": "strong",
      "evidence": "Regiment 505 unique to 82nd; PIR confirms airborne; 3/505 = 3rd Bn"
    }
  ]
}
```

### 4. Selection Criteria for Export

Not all hard cases should become few-shot examples:

| Criterion | Include? |
|-----------|----------|
| Flagged by both runs (`"both"`) | Yes — genuinely hard |
| Flagged by one run only | Maybe — if resolved by interesting pattern |
| No resolving pattern found | No — unresolved ambiguity not useful as example |
| Missing ground truth | No — can't provide correct answer |

## Consequences

**Easier:**
- Few-shot strategy gets high-quality examples with no extra work
- Examples have built-in difficulty ratings and resolution reasoning
- Cross-strategy learning: resolver patterns inform few-shot evidence

**Harder:**
- Reconciliation module grows in responsibility
- Need to pass validation data through to reconciliation
- Corpus management if using hybrid approach

**New constraints:**
- Few-shot corpus depends on resolver generation having run
- Example quality tied to reconciliation quality
- May need versioning if resolvers are regenerated

## Open Questions

1. **How many examples per component?** Token budget for few-shot prompts limits this.
2. **Cross-component examples?** Should 82nd examples help with 101st?
3. **Example staleness?** If resolver is regenerated, should examples update?
4. **Negative examples?** Include "this record is NOT component X" examples?

## References

- Few-shot strategy spec: `docs/components/strategies/few-shot/CURRENT.md`
- Resolver reconciliation: `src/strategies/resolver/generator/reconciliation.py`
- Dual-run hard case handling: `src/strategies/resolver/generator/dual_run.py`
- Related: ADR-002 (dual-run architecture that produces hard cases)
