# Session Extract: Rendering Realism Overhaul (Instruction 007)

**Date:** 2026-01-27  
**Participants:** Human (Project Lead), Codex (GPT-5)  
**Purpose:** Implement rendering realism improvements and validate with larger sample  
**Duration:** ~1 hour  
**Outputs:** Renderer/model/spec updates, tests, 1000-record sample run

---

## Summary

Implemented Instruction 007 to improve realism in rendered synthetic records by:

- Per-level label omission (with familiarity boost)
- Value abbreviation for named designators
- Mixed delimiters within a single entry
- Spec updates for new fields and missing archetypes

Ran a 1000-record sample to surface tier‑4/5 records and inspected outputs.

---

## Key Decisions

- **Label omission:** stochastic per-level with higher omission at lower echelons.
- **Familiarity boost:** additive boost based on SAME_L3/SAME_L2/SAME_BRANCH.
- **Value abbreviation:** truncation or consonant skeleton; Greek letters abbreviated less aggressively.
- **Delimiter mixing:** based on clerk format consistency (format_lock).
- **Spec updates:** added `colonial_district` and `defense_operations` archetypes.

---

## Files Changed

| File | Change |
|------|--------|
| `src/synthetic/models.py` | Added `label_omission_rate`, `value_abbreviation_rate` |
| `src/synthetic/clerk_factory.py` | Parse/vary new unit_format fields |
| `src/synthetic/renderer.py` | Label omission, abbreviation, delimiter mixing, familiarity wiring |
| `docs/components/synthetic_data_generation/synthetic_style_spec_v4.1.yaml` | Added unit_format fields + missing archetypes |
| `tests/synthetic/test_difficulty_saturation_fix.py` | Added unit tests for realism behaviors |

---

## Commands Run

```bash
venv/bin/python -m src.synthetic.pipeline --output-dir data/synthetic --target-records 1000 --seed 42
venv/bin/python -m src.preprocessing.preprocessing_adapter --input data/synthetic/raw.parquet --output data/synthetic/canonical.parquet
```

---

## Observations

- Label omission and mixed delimiters are now visible in outputs.
- Abbreviated values (e.g., "Prspc", "De") appear in tier‑4 records.
- Realism improved but still not fully representative of archival messiness.

---

## Follow-up

- Continue tuning realism rates (label omission, abbreviation, OCR-style corruption).
- Re-evaluate difficulty distribution after realism tuning.
