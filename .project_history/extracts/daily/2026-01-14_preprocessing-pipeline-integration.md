# Daily Reconciliation: Preprocessing Pipeline Integration

**Date:** 2026-01-14
**Namespace:** preprocessing / pipeline / integration

---

## Summary

Connected synthetic data generation to regex extraction via glossary generation and preprocessing adapter. Completed the bridge from `raw.parquet` (synthetic output) to `canonical.parquet` (extraction-ready format). Added `Digit_Sequences` extraction pattern for slash/dash notation and fixed pandas 2.x compatibility issue.

---

## What Changed

### Files Created

| File | Purpose |
|------|---------|
| `src/preprocessing/glossary_generator.py` | Build-time script to generate glossary from synthetic configs |
| `src/preprocessing/preprocessing_adapter.py` | Bridge synthetic output to regex extraction pipeline |
| `config/glossaries/synthetic_glossary.json` | Auto-generated glossary (56 terms: 22 org, 20 unit, 14 role) |
| `data/synthetic/canonical.parquet` | Preprocessed output with 25 extraction columns |

### Files Modified

| File | Changes |
|------|---------|
| `src/preprocessing/regex_preprocessing.py` | Added `Digit_Sequences` pattern; fixed pandas 2.x index alignment |
| `docs/components/preprocessing/CURRENT.md` | Added glossary generator, adapter docs; changelog v1.1.0 |
| `docs/architecture/CURRENT.md` | Added status table, updated pipeline diagram |
| `README.md` | Updated current status, added Quick Commands section |
| `instructions/active/README.md` | Added recently completed, suggested next tasks |
| `instructions/completed/README.md` | Added completed instructions index |

---

## Key Technical Decisions

### 1. Build-Time Glossary Generation

**Approach:** Generate glossary from synthetic configs once at build time, not at runtime.

**Rationale:**
- Simpler debugging — glossary is explicit artifact
- Faster runtime — no config parsing overhead
- Clear dependencies — glossary changes when configs change

**Implementation:**
```bash
python3.11 -m src.preprocessing.glossary_generator
```

Extracts from:
- `synthetic_style_spec_v3.yaml` → ranks, unit labels
- `hierarchy_reference.json` → service branches
- `synthetic_vocabulary.json` → admin codes

Output: 56 terms categorized as org/unit/role.

### 2. Glossary Scope: Structural Terms Only

**Included:** Unit structure terms (Regiment, Battalion, Division, ranks)
**Excluded:** Situational vocabulary (OMAHA, DZ-O, FOGGIA)

**Rationale:**
- Situational terms are LLM disambiguation signals, not regex targets
- Including them would create false positives (e.g., "OMAHA" matching beach name vs code)
- Glossary focuses on structural terms that clearly identify unit/role components

### 3. Digit_Sequences Extraction

Added pattern for slash/dash separated digit sequences:
- **Pattern:** `\d{1,3}(?:st|nd|rd|th)?(?:[/\-:.]\d{1,3}(?:st|nd|rd|th)?)+`
- **Captures:** "2/116", "1-2-116", "1st/2nd/3rd"
- **Output format:** Colon-joined per match (e.g., "2:116:29"), collected into list per record

**Rationale:** Positional unit notation (common in compact clerk styles) needs explicit extraction before LLM sees the text.

### 4. Pandas 2.x Compatibility Fix

**Issue:** Index alignment in broadcast loop failed on pandas 2.x

**Fix:**
```python
# Before (pandas 1.x only)
df_out[k] = pd.Series(s_uni.values).take(codes)

# After (pandas 2.x compatible)
broadcast_values = [s_uni.values[c] for c in codes]
df_out[k] = broadcast_values
```

**Rationale:** Pandas 2.x changed index behavior; explicit list comprehension is more robust.

---

## Pipeline Flow (Now Complete)

```
Synthetic Generator → raw.parquet (10K records)
          ↓
Preprocessing Adapter → adapts schema (raw_text → Name)
          ↓
Regex Extraction → extracts 25 fields using glossary
          ↓
canonical.parquet → ready for component routing
```

---

## Extraction Results (10K records)

| Category | Match Rate | Purpose |
|----------|-----------|---------|
| Role_Terms | 96.6% | Rank identification |
| Unit_Terms | 48.8% | Unit type signals |
| Org_Terms | 47.8% | Organization names |
| Digit_Sequences | 25.8% | Positional notation |
| Unit+Digit pairs | 45.4% | Combined structural signals |
| Alpha+Digit pairs | 48.4% | Alpha-numeric patterns |

---

## Impact on Other Components

| Component | Impact |
|-----------|--------|
| Component routing | Can now use extraction signals to route records |
| Batching | Has structured input (`canonical.parquet`) to group |
| Zero-shot strategy | Ready to receive batches with extraction metadata |
| Glossary maintenance | Regenerate when synthetic configs change |

---

## Next Steps Enabled

1. **Component Router** — Use extraction signals (Unit_Terms, Org_Terms, Digit_Sequences) to route records to appropriate component strategies
2. **Batching** — Group records by component/source for efficient LLM processing
3. **Zero-Shot Strategy** — Baseline consolidation approach with hierarchy context

---

## Commands Reference

```bash
# Generate synthetic data
python3.11 -m src.synthetic.pipeline

# Regenerate glossary (after config changes)
python3.11 -m src.preprocessing.glossary_generator

# Run preprocessing
python3.11 -m src.preprocessing.preprocessing_adapter --timing

# Verify output
python3.11 -c "import pandas as pd; df = pd.read_parquet('data/synthetic/canonical.parquet'); print(df.columns.tolist())"
```

---

## Source

Code activity log: `.project_history/code-activity/2026-01-14.md`
