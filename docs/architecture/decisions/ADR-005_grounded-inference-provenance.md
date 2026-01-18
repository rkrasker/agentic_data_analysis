# ADR-005: Grounded Inference and Provenance Tracking

**Date:** 2026-01-18
**Status:** accepted
**Scope:** strategy/resolver

## Context

During resolver generation, the LLM is prompted to discover patterns, vocabulary, and disambiguation rules from example records. Analysis of the 101st Airborne resolver revealed the LLM was injecting external training knowledge rather than reasoning purely from the provided examples:

**Evidence of External Knowledge Leakage:**
1. **Vocabulary not in examples**: "Screaming Eagles" marked as "strong" vocabulary despite not appearing in any seed records
2. **Historical specifics in differentiators**: Regiment numbers (501, 502, 506), battle locations (Bastogne), and drop zones (DZ A, C, D) from WWII Order of Battle knowledge
3. **Absence-based rules**: "LACKS any airborne-specific terminology → 36th Infantry" treating absence as negative evidence

**The Core Problem:**
The LLM was:
- Recognizing units from context → retrieving known facts from training → injecting that knowledge into resolvers
- Creating deterministic classification rules that force assignment even when evidence is insufficient
- Using absence of terms (e.g., "no ABN") as negative signals, which is logically invalid for sparse/abbreviated records

This conflates:
- **Pattern extraction** (intended): "I see 'PIR' in these records, it correlates with airborne units"
- **Knowledge retrieval** (problematic): "I know the 101st was at Bastogne and their motto is 'Rendezvous with Destiny'"

## Options Considered

### Option A: Completely Exclude External Knowledge

Require all patterns/vocabulary to be cited from example records. Reject any knowledge not grounded in the provided samples.

- Pro: Guarantees patterns are data-driven
- Pro: Prevents historical trivia injection
- Con: Loses valuable structural reasoning (e.g., "airborne units use ABN terminology")
- Con: May miss valid patterns that happen not to appear in small samples

### Option B: Allow All External Knowledge

Trust the LLM's training knowledge about military units and terminology.

- Pro: Leverages LLM capabilities fully
- Pro: Can handle units even with sparse examples
- Con: May generate patterns that don't appear in actual dataset
- Con: Creates false confidence in historically-specific details
- Con: Doesn't address absence-as-evidence logical flaw

### Option C: Grounded Inference with Provenance Tracking (SELECTED)

Require citation for claims but allow external knowledge if explicitly labeled as "inferred" vs "observed". Constrain logical structure to prevent absence-based rules.

- Pro: Preserves valuable type-based reasoning (Type A knowledge)
- Pro: Makes external knowledge transparent and auditable
- Pro: Downstream code can weight observed > inferred
- Pro: Forces explicit handling of ambiguous cases
- Con: More complex output schema
- Con: Additional validation pass needed
- Con: Longer prompts

## Decision

**Implement grounded inference with provenance tracking and confidence-based signals.**

### Core Principles (Apply to All LLM Phases)

**1. ABSENCE IS NOT EVIDENCE**
- A record lacking a term (e.g., no "ABN" for airborne) is UNINFORMATIVE, not negative evidence
- Records are often abbreviated or context-dependent
- Only the PRESENCE of a conflicting indicator counts as negative evidence

**2. GROUNDED CLAIMS ONLY**
- Every pattern or vocabulary term must be supported by example records OR marked as "inferred"
- Provenance: `observed` (can cite records) vs `inferred` (from training knowledge)
- Post-hoc validation confirms claimed "observed" terms actually appear

**3. AMBIGUITY IS VALID**
- Some records cannot be disambiguated without additional context
- "Cannot determine" is an acceptable and often correct outcome
- Do not force classification when evidence is insufficient

**4. POSITIVE SIGNALS ONLY**
- Rules based on PRESENCE: "Contains 'ABN'" → positive signal FOR airborne unit ✓
- NOT based on ABSENCE: "Does NOT contain 'ABN'" → INVALID ✗
- Conflicting presence is valid: "Contains 'Marine'" when expecting Army → conflict signal ✓

### Output Structure Changes

**Patterns:**
```json
{
  "patterns": [
    {
      "pattern": "101AB",
      "means": "component=101st_airborne_division",
      "tier": "strong",
      "provenance": "observed",
      "example_records": ["MURPHY SGT 101AB E2-16", "JONES PFC 101AB"]
    },
    {
      "pattern": "Screaming Eagles",
      "means": "component=101st_airborne_division",
      "tier": "moderate",
      "provenance": "inferred",
      "note": "Known nickname, not seen in examples"
    }
  ],
  "ambiguous_patterns": [
    {
      "pattern": "E2-16",
      "note": "Appears in both 101st and 2nd ID records"
    }
  ]
}
```

**Vocabulary:**
```json
{
  "vocabulary": {
    "observed": [
      {"term": "ABN", "strength": "strong", "example_records": ["..."]}
    ],
    "inferred": [
      {"term": "Bastogne", "strength": "moderate", "note": "Historical association"}
    ]
  }
}
```

**Differentiators (Most Significant Change):**
```json
{
  "positive_signals": [
    {"if_contains": "ABN or PIR", "then": "increase_confidence", "target": "101st", "strength": "strong"}
  ],
  "conflict_signals": [
    {"if_contains": "Marine or USMC", "then": "decrease_confidence", "target": "101st", "reason": "branch_mismatch"}
  ],
  "structural_rules": [
    {"if_contains": "Regiment 501", "then": "identifies", "target": "101st", "note": "Unique regiment"}
  ],
  "ambiguous_when": {
    "condition": "Only shared regiment number present, no type modifiers",
    "example_patterns": ["E2-16", "A/1/3"],
    "recommendation": "cannot_determine"
  }
}
```

### Validation Pass (Phase 8)

Tier assignment now includes provenance validation:
- Patterns claimed as "observed" are checked against actual records
- If not found → provenance changed to "inferred" with note
- Ungrounded patterns logged for review

## Consequences

**Easier:**
- Audit what knowledge came from data vs. LLM training
- Tune downstream trust levels (weight observed > inferred)
- Detect when LLM hallucinates pattern presence
- Handle ambiguous cases explicitly instead of forcing assignment
- Identify when disambiguation is genuinely impossible

**Harder:**
- Prompts are longer and more complex
- Output schema has more nested structure
- Requires provenance validation pass
- Legacy code needs `@property` compatibility adapters

**New Constraints:**
- LLM must cite examples for "observed" claims
- "Cannot determine" is required for ambiguous cases
- No absence-based rules allowed (explicit constraint in prompts)
- Downstream parsing must handle confidence-based scoring instead of deterministic rules

## Implementation

**Files Modified:**
- `src/strategies/resolver/generator/prompts.py` - Added GROUNDING_PRINCIPLES, updated all phase prompts and schemas
- `src/strategies/resolver/generator/llm_phases.py` - Updated dataclasses (PatternResult, VocabularyResult, DifferentiatorResult) and parsing logic
- All LLM phase functions now handle observed/inferred structure
- `_generate_hierarchy_rules()` returns structured signals instead of rule strings

**Backward Compatibility:**
- Legacy `@property` getters on VocabularyResult (strong, moderate, weak)
- Legacy `@property` getters on DifferentiatorResult (rules, hierarchy_rules)
- Fallback parsing for old-format responses

## References

- Implementation conversation: Claude Code session 2026-01-18
- Triggered by: Analysis of `config/resolvers/101st_airborne_division_resolver.json`
- Related: Seed set documentation in `config/synthetic/seed_set_v3.json`
