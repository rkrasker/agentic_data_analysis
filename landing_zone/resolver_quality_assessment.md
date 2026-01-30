# Resolver Quality Assessment: colonial_administration_resolver.json

**Date:** 2026-01-29  
**Resolver:** `colonial_administration_resolver.json`  
**Reference Files:** `hierarchy_reference.json`, `synthetic_style_spec_v4_1.yaml`, `CURRENT.md` (resolver strategy)

---

## Executive Summary

The first generated resolver shows that **hierarchy-derived sections are working correctly**, but there are critical errors in **tier classification**, **LLM-generated patterns**, and **schema compliance** in differentiators.

| Aspect | Verdict |
|--------|---------|
| Structure section | ✓ Correct |
| Exclusions | ✓ Correct |
| Tier classification | ✗ Wrong |
| Patterns | ✗ Critical error |
| Collision handling | ✗ Missing ambiguous_when |
| Differentiator schema | ✗ Non-compliant format |

---

## What's Correct

### Structure Section

The `valid_designators` match the hierarchy exactly. The `structural_discriminators` correctly include only branch-unique level names and non-colliding designator names:

**Correctly included as discriminators:**
- Level names: Colony, District, Settlement (unique to CA per `structural_signals.branch_unique_terms`)
- Colony names: Thornmark, Waystation (don't appear in other branches)
- Settlement names: Haven, Prospect, Landfall, Waypoint (unique to CA)

**Correctly excluded:**
- "Horizon" is correctly ABSENT from discriminators because it collides with `expeditionary_corps.expedition` per the `collision_index`

### Exclusions Section

Term exclusions align with hierarchy's `structural_signals.branch_unique_terms`:
- Squadron, Wing, Element → exclude (DC terms)
- Expedition, Team → exclude (EC terms)
- Operation, Facility, Crew → exclude (RD terms)

Depth exclusions are correct:
- `if_depth: 3` → exclude (EC depth)
- `if_depth: 5` → exclude (DC depth)
- CA depth is 4, so these exclusions are valid

---

## Issues

### Issue 1: Tier Classification is Wrong

**Observed:**
```json
{
  "tier": "sparse",
  "sample_size": 712,
  "pct_of_median": 97.3,
  "generation_mode": "hierarchy_only"
}
```

**Problem:**  
`pct_of_median: 97.3` means 712 soldiers is ~97% of median. Per the threshold spec in CURRENT.md:

| Tier | Threshold |
|------|-----------|
| sparse | < p25 |
| under_represented | ≥ p25, < median |
| adequately_represented | ≥ median |
| well_represented | ≥ p75 |

At 97.3% of median, this component should be classified as `adequately_represented`, not `sparse`.

**Cascade Effect:**  
This incorrect tier triggers `generation_mode: "hierarchy_only"`, which then incorrectly marks `vocabulary.status: "not_generated"` and limits differentiator generation. The component should have received fuller pattern and vocabulary discovery.

**Root Cause Hypothesis:**  
Bug in `thresholds.py` — possibly comparing against wrong value or using inverted logic.

---

### Issue 2: Critical Error in Patterns (Defense Command Terms in CA Resolver)

**Observed:**
```json
"patterns": {
  "status": "complete",
  "entries": {
    "Sq | Wg | El": {
      "means": "Abbreviations for a military-style organization: Squadron, Wing, Element.",
      "tier": "moderate"
    }
  }
}
```

**Problem:**  
Squadron, Wing, and Element are **Defense Command terms** per `hierarchy_reference.json`:

```json
"branch_unique_terms": {
  "Squadron": "defense_command",
  "Wing": "defense_command",
  "Element": "defense_command"
}
```

These terms should **exclude** Colonial Administration, not appear as patterns **for** it.

**Impact:**  
If this resolver is used at consolidation time, the LLM would incorrectly boost confidence for CA when DC abbreviations appear. This is exactly backwards.

**Root Cause Hypothesis:**  
The patterns phase is LLM-generated. The LLM likely hallucinated this from training knowledge (generic military organization patterns) rather than grounding in the actual collision samples. This violates ADR-005 (Grounded Inference).

**Additional Pattern Concern:**
```json
"patterns.status": "complete"
```

But `generation_mode: "hierarchy_only"` — these are contradictory. If generation mode is hierarchy-only, patterns should be `"status": "not_generated"`.

---

### Issue 3: Missing Collision Handling (ambiguous_when clauses)

**Context from hierarchy_reference.json collision_index:**
```json
"names": {
  "Kestrel": [
    "colonial_administration.colony",
    "defense_command.fleet",
    "expeditionary_corps.expedition",
    "resource_directorate.operation"
  ],
  "Horizon": [
    "expeditionary_corps.expedition",
    "colonial_administration.settlement"
  ],
  "Amber": [
    "colonial_administration.colony",
    "resource_directorate.operation"
  ],
  "Verdant": [
    "colonial_administration.colony",
    "expeditionary_corps.expedition"
  ]
}
```

**Observed in differentiators:**
```json
"vs_expeditionary_corps": {
  "rules": [
    "Contains 'settlement Haven or Horizon or Landfall or Prospect or Waypoint' -> colonial_administration",
    "Contains 'expedition Beacon or Horizon or Kestrel or Pioneer or Verdant' -> expeditionary_corps"
  ]
}
```

**Problem:**  
The rules handle `settlement Horizon` and `expedition Horizon` correctly, but there's no handling for when "Horizon" appears **without** a level prefix. Per the schema in CURRENT.md, this should include:

```json
"ambiguous_when": {
  "condition": "Record contains 'Horizon' without 'settlement' or 'expedition' prefix",
  "example_patterns": ["assigned Horizon", "unit Horizon", "Horizon duty"],
  "recommendation": "cannot_determine"
}
```

Same issue applies to:
- **Kestrel** — collides across 4 branches (CA.colony, DC.fleet, EC.expedition, RD.operation)
- **Amber** — collides between CA.colony and RD.operation
- **Verdant** — collides between CA.colony and EC.expedition

Without `ambiguous_when` clauses, the LLM has no guidance for these genuinely ambiguous cases.

---

### Issue 4: Differentiator Schema Non-Compliance

**Expected schema (from CURRENT.md):**
```json
"positive_signals": [
  {
    "if_contains": "squadron or wing or element",
    "then": "increase_confidence",
    "target": "defense_command_fleet_7",
    "strength": "strong",
    "provenance": "structural"
  }
],
"structural_rules": [
  {
    "if_depth": 5,
    "then": "identifies",
    "target": "defense_command_fleet_7",
    "strength": "definitive",
    "note": "Resource Directorate has depth 4"
  }
]
```

**Actual output:**
```json
"rules": [
  "Contains 'Colony' -> colonial_administration",
  "Contains 'District' -> colonial_administration",
  "Contains 'squadron 1 or 10 or 11 or 12 or 2 or 3...' -> defense_command"
]
```

**What's Lost:**
| Field | Purpose | Impact of Loss |
|-------|---------|----------------|
| `provenance` | observed/inferred/structural | Downstream code can't weight by trust level |
| `strength` | definitive/strong/moderate/tentative | Can't distinguish conclusive vs suggestive signals |
| `then` action | increase_confidence vs identifies | Loses semantic distinction |
| Machine parseability | Structured objects | Rules are free-text strings, not programmatically usable |

**Root Cause Hypothesis:**  
`assembler.py` is not enforcing the schema, or the LLM phase is generating free-text that isn't being post-processed into the required structure.

---

## Recommended Actions

### Immediate Fixes

1. **Trace tier calculation** — Debug `thresholds.py` to verify why 97.3% of median yields "sparse"

2. **Remove DC patterns from CA resolver** — Either manually or by identifying why patterns phase included them

3. **Add schema validation to assembler.py** — Reject or transform non-compliant differentiator formats

### Workflow Improvements

4. **Add grounding enforcement to patterns phase** — Patterns should cite specific records; reject patterns that can't be grounded (ADR-005 compliance)

5. **Generate ambiguous_when from collision_index** — For each colliding name, automatically generate the ambiguity clause

6. **Add internal consistency checks** — Flag when `generation_mode: "hierarchy_only"` but `patterns.status: "complete"`

---

## Test Cases for Regression

Once fixes are applied, verify:

| Test | Expected |
|------|----------|
| CA resolver tier | `adequately_represented` (at 97.3% of median) |
| CA resolver patterns | No DC/EC/RD terms present |
| CA resolver patterns.status | `"complete"` only if tier ≥ under_represented |
| vs_expeditionary_corps | Has `ambiguous_when` for Horizon, Verdant |
| vs_resource_directorate | Has `ambiguous_when` for Amber |
| All differentiators | Has `ambiguous_when` for Kestrel |
| Differentiator rules | Structured objects, not strings |

---

## References

- `CURRENT.md` — Resolver strategy and schema definitions
- `hierarchy_reference.json` — Ground truth for structural signals and collisions
- `DIFFICULTY_MODEL.md` — Three-layer difficulty framework
- `ADR-005` — Grounded inference requirements
- `ADR-006` — Record quality ≠ resolution difficulty
