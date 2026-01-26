# Session Extract: Preprocessing Pipeline v4.1 Planning

**Date:** 2026-01-26  
**Participants:** Human (Project Lead), Claude (Opus 4.5)  
**Purpose:** Plan preprocessing pipeline updates for synthetic v4.1  
**Duration:** ~45 minutes  
**Outputs:** Instruction 005, ADR-008

---

## Session Summary

Planning session to identify changes needed in the preprocessing pipeline following the synthetic data v4.1 implementation. Resulted in scoped instruction for Sonnet execution and decision record.

---

## Documents Reviewed

1. `docs/components/synthetic_data_generation/CURRENT.md` (v4.1 spec)
2. `docs/components/synthetic_data_generation/synthetic_style_spec_v4.1.yaml` (~1300 lines)
3. `docs/components/preprocessing/CURRENT.md` (current preprocessing architecture)
4. `docs/architecture/decisions/ADR-006_per-record-vs-per-soldier-difficulty.md`
5. `docs/architecture/decisions/ADR-007-synthetic-data-redesign.md`
6. `SESSION_STATE.md`
7. Project files: CLAUDE.md, DISAMBIGUATION_MODEL.md, GLOSSARY.md

---

## Key Discussion Points

### 1. Initial Analysis

Identified delta between current preprocessing and v4.1 requirements:

- **Glossary Generator:** Full rewrite needed (WWII → Terraform Combine vocabulary)
- **Preprocessing Adapter:** Schema updates for new columns
- **Regex Preprocessing:** Structure unchanged, uses new glossary
- **Component Router:** Still pending, more complex with variable-depth hierarchies

### 2. Schema Column Routing Decision

**Question:** Where should new v4.1 columns go?

**Resolution:**
- `state_id` → canonical.parquet (needed for evaluation)
- `path_completeness`, `levels_provided`, `extraction_signals` → synthetic_metadata.parquet (synthetic-only artifacts)

Human confirmed: "go with your suggestion"

### 3. Extraction Signals Definition Gap

**Issue discovered:** The v4.1 spec defines extraction_signals as "structural signals that aid disambiguation" with four *types* (branch_unique_term, depth_indicator, designator_pattern, vocabulary_signal) but never enumerates the actual string values.

**Options presented:**
- Option A: Simple term presence (`["squadron", "kestrel"]`)
- Option B: Typed signals (`["level_unique:squadron", "fleet_name:kestrel"]`)
- Option C: Resolution outcomes (`["branch_resolved:DC", "level_3_provided"]`)

**Resolution:** Human decided to bracket this: "in terms of defining these signals in the synthetic generation functions, lets bracket and leave for later"

### 4. Scoping Decision for Synthetic Fields

**Human directive:** "for pipeline preprocessing, lets treat `path_completeness`, `levels_provided`, `extraction_signals` etc as synthetic only artifacts that would not be present in the real data, but should be passed through intact for testing purposes"

This cleanly separated:
1. Preprocessing pipeline concerns (vocabulary swap, schema routing)
2. Synthetic generation design questions (signal definitions)

### 5. Ranks/Role Terms

**Question:** Does Terraform Combine have defined rank vocabulary?

**Resolution:** Human noted this was forgotten in synthetic generator build. Decision: "populate with empty placeholder list for use in regex that can be populated with transition to real data"

### 6. Join Key Decision

**Question:** Should metadata join key be `(source_id, soldier_id)` or `(source_id, soldier_id, state_id)`?

**Resolution:** Human chose explicit three-column key: "go with explicit"

### 7. Sources.parquet Handling

**Question:** Should preprocessing handle the new `sources.parquet` file?

**Resolution:** Human confirmed: "purely for synthetic generation - do not use in pre-processing"

---

## Decisions Made

| Topic | Decision |
|-------|----------|
| state_id destination | canonical.parquet |
| Completeness fields destination | synthetic_metadata.parquet (pass-through) |
| Join key | (source_id, soldier_id, state_id) explicit |
| sources.parquet | Ignore in preprocessing |
| Role terms | Empty placeholder |
| extraction_signals definition | Bracketed for later |
| Component router | Remains out of scope |

---

## Files Generated

1. `instructions/active/005_preprocessing-v4.1-terraform-combine.md`
   - Full implementation instruction for Sonnet
   - Context/rationale, anti-patterns, decision boundaries
   
2. `docs/architecture/decisions/ADR-008-preprocessing-v4.1-update.md`
   - Decision record with options considered
   - What we explicitly decided NOT to do
   - Edge cases discussed

3. `.project_history/extracts/raw/2026-01-26_opus_preprocessing-v4.1-planning.md`
   - This file (session transcript)

---

## Context Window Note

At ~75% through session, human asked about remaining context. Estimated 40-50% used at that point. Session completed successfully within limits.

---

## Follow-up Items

1. **Rank vocabulary:** Needs to be defined in synthetic generator or deferred to real data transition
2. **extraction_signals vocabulary:** Design decision bracketed; needs resolution before signals can be used
3. **Component router:** Separate design work needed given collision complexity
4. **Test data:** Will be generated after synthetic v4.1 artifacts are produced

---

## Session Artifacts Location

```
instructions/active/005_preprocessing-v4.1-terraform-combine.md
docs/architecture/decisions/ADR-008-preprocessing-v4.1-update.md
.project_history/extracts/raw/2026-01-26_opus_preprocessing-v4.1-planning.md
```
