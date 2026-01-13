# Thread Extract: Hierarchy Revision for Synthetic Data Generation

**Date:** 2026-01-13
**LLM:** Claude Opus
**Session:** hierarchy-revision
**Participants:** Eli, Claude Opus

---

## Context

Reviewed existing synthetic data generation system in `docs/components/synthetic_data_generation/`. The previous approach used historically accurate WW2 unit hierarchies, but these lacked the complexity needed to force the parsing LLM to develop robust disambiguation strategies.

---

## Key Problem Identified

The original hierarchy had globally unique subunit designators. For example:
- 506th PIR → only exists in 101st Airborne
- 16th Infantry Regiment → only exists in 1st Infantry Division

This allowed the parser to resolve component assignment from a single designator without needing to aggregate multiple signals. The synthetic data wasn't forcing the analytical complexity required for real-world ambiguous records.

---

## Design Decisions

### 1. Terminology Standardization

| Term | Definition | Example |
|------|------------|---------|
| **Component** | Top-level entity being classified | `1st_infantry_division` |
| **Subunit** | Unit subordinate to a component | "5th Regiment of 1st ID" |
| **Designator** | Numeric/alpha identifier of a subunit | `5`, `A`, `327` |
| **Unit type** | Category of the subunit | `regiment`, `battalion`, `company` |

### 2. Deliberate Designator Collisions

Created overlapping designator assignments across components:
- Regiment `1` appears in: 1st ID, 2nd ID, 101st AB, 1st MarDiv, 36th ID
- Regiment `5` appears in: 1st ID, 3rd ID, 82nd AB, 1st MarDiv, 10th Mtn
- Regiment `7` appears in: 1st ID, 3rd ID, 82nd AB, 1st MarDiv, 10th Mtn

This forces the parser to use (designator, unit_type) pairs plus additional signals.

### 3. Designator Convention Variation

Different components use different designation patterns at each hierarchical level:

| Convention | Description | Example |
|------------|-------------|---------|
| numeric_sequential | Consecutive integers | 1, 2, 3, 4 |
| numeric_discrete | Non-consecutive set | 1, 5, 7 |
| alpha_sequential | Letters in order | A, B, C, D, E, F, G, H |
| alpha_gapped | Letters with military gaps | A-M, no J |
| alpha_discrete | Arbitrary letter subset | A, B, R |

Applied differently by component type:
- Infantry: numeric_discrete regiments, numeric_sequential battalions, alpha_gapped companies
- Airborne: numeric_discrete regiments, alpha_sequential battalions, numeric_sequential companies
- Armored: alpha_discrete combat commands, numeric_discrete battalions
- Marines: numeric_discrete regiments, numeric_sequential battalions, alpha_sequential companies (shorter range than army)

### 4. Temporal Aliases

Added structured alias tracking for:
- **Redesignation**: Unit name/number changes over time (82nd Infantry → 82nd Airborne)
- **Reassignment**: Subunit moves between components
- **Type reclassification**: Unit type changes (325th Infantry → 325th Glider)
- **Informal**: Common shorthand variants (1st MarDiv, 82nd AB)

Schema:
```
aliases[]:
  - alias_id
  - alias_name
  - alias_designator (if different)
  - alias_type
  - period {start, end}
  - parent_component (for reassignments)
```

### 5. Separation of LLM-Facing vs Generation-Only Data

Split into three files:
1. **hierarchy_reference.json** - Provided to parsing LLM, used for validation
2. **synthetic_themes.json** - Generation only, defines conceptual categories
3. **synthetic_vocabulary.json** - Generation only, actual terms to inject

### 6. Theme and Vocabulary Structure

**Themes** define conceptual categories:
- Theme types: operational_context, logistics, administrative, organizational, equipment, geographic
- Specificity levels: universal, service, type, component

**Vocabulary** defines injectable terms:
- Term types: transport_code, equipment_code, zone_designator, manifest_code, admin_code, etc.
- Each term links to a theme via `theme_ref`
- Frequency weights: common (0.60), uncommon (0.30), rare (0.10)
- Placement options: suffix, infix

**Signal gradient**:
- Universal terms (HQ, DET) → no component signal
- Service terms (USMC, AAF) → branch-level signal
- Type terms (ABN, TK, FMF) → component-type signal
- Component terms (DZ-O, OMAHA) → specific component signal

### 7. Vocabulary Constraints

Terms must be:
- Plausible clerk manifest entries (not nicknames like "Devil Dogs")
- Implicit signals (no direct regex-extractable designators)
- Varied in diagnostic power (some unique, some shared across similar components)

---

## Files Created

| File | Location | Purpose |
|------|----------|---------|
| `hierarchy_reference.json` | `config/hierarchies/` | LLM-facing canonical hierarchy |
| `synthetic_themes.json` | `config/synthetic/` | Theme definitions for generation |
| `synthetic_vocabulary.json` | `config/synthetic/` | Vocabulary terms for generation |

---

## Collision Index Summary

15 components created with deliberate collisions:

**Cross-branch collisions** (require service-level disambiguation):
- Regiment 1: army infantry, army airborne, marines
- Regiment 5: army infantry, army airborne, army mountain, marines
- Regiment 7: army infantry, army airborne, army mountain, marines

**Within-branch collisions** (require division-level or structural disambiguation):
- Regiment 1 in army: 1st ID, 2nd ID, 36th ID, 101st AB
- Regiment 3 in army: 2nd ID, 36th ID, 82nd AB, 101st AB

**Battalion-level collisions**:
- Alpha battalions (A, B, C): airborne divisions, armored divisions
- Numeric battalion 1: all infantry, marine, mountain divisions

---

## Next Steps

- Update synthetic data generator to use new hierarchy structure
- Update style spec to reference new theme/vocabulary files
- Regenerate seed set with collision-heavy examples
- Update validation logic to use new hierarchy_reference.json
