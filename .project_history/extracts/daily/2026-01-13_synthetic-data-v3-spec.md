# Synthetic Data v3 Spec: Clerks as Characters

**Date:** 2026-01-13
**Source:** Claude Code session
**Topic:** Redesign of synthetic data generation philosophy

---

## Summary

Created v3 style spec based on fundamental philosophy change: **clerks are characters, not sampling functions**. Previous v2 approach generated entries that felt synthetic because they sampled from probability distributions per-entry. v3 models clerks as persistent characters whose habits are locked for all entries they produce.

---

## Key Decisions

### 1. Clerk Archetypes Replace Source Profiles

**v2:** Source profiles were config objects with weighted distributions
```yaml
- id: "S01_standard_compact"
  unit_family_weights: {"A_labeled_micro": 0.25, "B_slash_positional": 0.55}
```

**v3:** Clerk archetypes are characters with fixed habits
```yaml
hq_formal:
  description: "Division HQ clerk. Trained on proper Army forms."
  name_format:
    template: "{LAST}, {FIRST} {MI}."
  unit_format:
    style: "labeled_hierarchical"
    separator: ", "
```

A clerk's style is **locked** - they don't sample per entry.

### 2. Situations Replace Component Affinities

**v2:** Vocabulary was injected based on component affinity weights
```yaml
component_affinities:
  82nd_airborne_division:
    airborne_flavor: strong
    air_flavor: medium
```

**v3:** Situations drive vocabulary naturally
```yaml
normandy_airborne:
  applies_to: [82nd_airborne_division, 101st_airborne_division]
  vocabulary_pool:
    primary: ["DZ-O", "DZ-N", "ABN", "PIR"]
    secondary: ["C-47", "CHK-42", "TCG"]
```

Vocabulary appears because the clerk is processing D-Day jump manifests, not because we're injecting "airborne signal tokens."

### 3. Within-Source Consistency

**v2:** Each entry independently sampled format, separator, etc.

**v3:** 85% of entries in a source use identical format
- Variation happens **between** sources, not **within** them
- Fatigue modeling: clerk gets sloppier late in batch
- This matches real clerical behavior

### 4. Three Vocabulary Layers

| Layer | Purpose | Helps Parser? |
|-------|---------|---------------|
| Situational | Terms from operation context | Yes - provides disambiguation signals |
| Contextual Clutter | Noise from clerk environment | No - deck codes, ward numbers |
| Confounders | Deliberately ambiguous | Actively misleads if parsed naively |

---

## Files Created/Updated

| File | Action | Description |
|------|--------|-------------|
| `synthetic_style_spec_v3.yaml` | Created | Full v3 spec with 13 archetypes, 16 situations, transfers |
| `seed_set_v3.json` | Created | 41 hand-crafted entries (incl. 1 transfer case) |
| `synthetic_vocabulary.json` | Updated | Added clutter (15 terms) and confounders (13 terms) |
| `CURRENT.md` | Updated | Rewrote for v3 philosophy, added transfers section |
| `001_synthetic-data-generator.md` | Updated | Revised tasks, added TransferManager |
| `data-structures/CURRENT.md` | Updated | Expanded unit_changes.parquet with transfer distribution |

---

## Clerk Archetypes (13 total)

| Category | Archetypes |
|----------|------------|
| Headquarters | `hq_formal`, `hq_efficient` |
| Battalion | `battalion_rushed`, `battalion_methodical` |
| Field | `field_exhausted`, `field_medevac` |
| Transport | `transport_ship`, `transport_air` |
| Replacement | `repldep_intake` |
| Air Force | `aaf_squadron`, `aaf_operations` |
| Marines | `marine_fmf`, `marine_shipboard` |

---

## Situations (16 total)

| Theater | Situations |
|---------|------------|
| ETO | `normandy_assault`, `normandy_airborne`, `bulge_defensive`, `eto_breakout` |
| MTO | `italy_anzio`, `italy_mountain`, `north_africa` |
| PTO | `guadalcanal`, `tarawa`, `iwo_jima` |
| AAF | `eighth_af_strategic`, `fifteenth_af_mediterranean`, `ninth_af_tactical` |
| Admin | `replacement_processing`, `transport_generic`, `casualty_processing` |

---

## Example: Same Soldier, Different Clerks

**Canonical:** S/Sgt Stanley Joseph Kowalski, E Co, 2nd Bn, 16th Inf, 1st ID

| Clerk | Output |
|-------|--------|
| HQ Formal | `S/Sgt Kowalski, Stanley J.  Co E, 2nd Bn, 16th Inf, 1st Div` |
| Battalion Rushed | `KOWALSKI SSGT E2-16` |
| Field Exhausted | `Kowalski Stanley  SSgt Easy Co 16  WIA` |
| Transport Ship | `KOWALSKI S    116/2/E  29ID  SSG` |

Parser must recognize all as equivalent.

---

## Vocabulary Layer Examples

**Entry with all layers:**
```
SULLIVAN J    E/2/1  1MARDIV  SGT  Dk2 Bth-C  A
├── Core: SULLIVAN J  E/2/1  1MARDIV  SGT (clerk style)
├── Clutter: Dk2 Bth-C (deck 2, berth C - ship locations)
└── Confounder: A (berth A, not Company A)
```

**Confounder demonstration:**
```
KOWALSKI SSGT E2-16 C-4
```
- Apparent meaning: E Company, 2nd Bn, 16th Regt, then C Company 4th Bn???
- Actual meaning: E Company 2nd Bn 16th Regt + Compartment C-4 on transport
- Parser must use E2-16 to know soldier is E Company, so C-4 cannot be a company

---

## Soldier Transfers

25% of soldiers have a unit transfer in their history. This creates the hardest disambiguation cases.

### Transfer Type Distribution

| Type | Frequency | Example |
|------|-----------|---------|
| Company-level | 50% | E Co → F Co within 2nd Bn |
| Battalion-level | 30% | 2nd Bn → 3rd Bn within 16th Inf |
| Regiment-level | 15% | 16th Inf → 18th Inf within 1st ID |
| Division-level | 5% | 1st ID → 29th ID via replacement depot |

### Key Constraints

- Documents are **undated** - no temporal consistency to rely on
- Both assignments are valid "truth" for disambiguation purposes
- Clerks have no awareness of transfers - they just record what they see
- Cross-branch transfers (Army ↔ Marines) not modeled

### Transfer Example (S013 Brennan)

```
Source A (HQ): "Pfc Brennan, Thomas E.  Co C, 2nd Bn, 16th Inf, 1st Div"
Source B (Rushed): "BRENNAN PFC C2-16"
Source B (Rushed): "BRENNAN PFC B1-18"
```

Without dates, parser cannot distinguish:
- Parsing error?
- Valid transfer (both correct)?
- Two different Brennans?

---

## Scale Parameters

| Parameter | Target |
|-----------|--------|
| Unique soldiers | 4,000 |
| Total records | 250,000 |
| Sources (documents) | 7,000 |
| Clerk instances | 200 |
| Records per soldier | ~62 average (geometric distribution) |

### Component Distribution
- Weight toward collision-prone components
- 1st ID, 82nd AB, 1st MarDiv get higher representation
- Ensures collision disambiguation challenge

---

## Next Steps

1. Build generator implementing v3 philosophy
2. Implement TransferManager for 25% soldier transfers
3. Validate seed set entries can be reproduced
4. Generate full dataset with collision coverage
5. Test parser against v3 output

---

## Related

- Previous: [2026-01-13_synthetic-data-hierarchy-redesign.md](2026-01-13_synthetic-data-hierarchy-redesign.md)
- Spec: [synthetic_style_spec_v3.yaml](../../docs/components/synthetic_data_generation/synthetic_style_spec_v3.yaml)
- Seed set: [seed_set_v3.json](../../config/synthetic/seed_set_v3.json)
