# Daily Reconciliation: Synthetic Data Hierarchy Redesign

**Date:** 2026-01-13
**Namespace:** synthetic-data / hierarchy / redesign

---

## Summary

Redesigned the unit hierarchy system for synthetic data generation. The previous historically-accurate hierarchy had globally unique designators that allowed trivial component resolution. The new design introduces deliberate designator collisions and convention variations to force multi-signal disambiguation.

---

## What Changed

### Files Created

| File | Location |
|------|----------|
| `hierarchy_reference.json` | `config/hierarchies/` |
| `synthetic_themes.json` | `config/synthetic/` |
| `synthetic_vocabulary.json` | `config/synthetic/` |

### Files Deprecated

| File | Status |
|------|--------|
| `docs/components/synthetic_data_generation/hierarchy_json.json` | Superseded by new structure |

---

## Key Design Changes

1. **Designator collisions**: Same (designator, unit_type) pairs appear under multiple components
2. **Convention variation**: Different components use different designation patterns (numeric vs alpha, sequential vs discrete)
3. **Three-file separation**: LLM-facing hierarchy separate from generation-only themes/vocabulary
4. **Structured aliases**: Temporal naming variations captured in structured fields
5. **Signal gradient vocabulary**: Terms range from universal (no signal) to component-specific (strong signal)

---

## Disambiguation Requirements

The parser must now aggregate multiple signals:
- Unit type (regiment vs battalion vs company)
- Designator convention patterns (alpha vs numeric, range)
- Service branch indicators (USMC, AAF, etc.)
- Component-type vocabulary (ABN, TK, FMF, etc.)
- Component-specific vocabulary (DZ-O, OMAHA, FOGGIA, etc.)

---

## Impact on Other Components

| Component | Impact |
|-----------|--------|
| Synthetic data generator | Must be updated to use new file structure |
| Style spec | Needs reference updates to theme/vocabulary files |
| Validation | Should use `config/hierarchies/hierarchy_reference.json` |
| LLM parsing strategies | May receive hierarchy_reference.json as context |

---

## Source

Raw extract: `.project_history/extracts/raw/2026-01-13_opus_hierarchy-revision.md`
