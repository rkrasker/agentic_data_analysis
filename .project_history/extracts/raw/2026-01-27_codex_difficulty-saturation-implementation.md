# Session Extract: Difficulty Saturation Fix Implementation + Realism Gap

**Date:** 2026-01-27  
**Participants:** Human (Project Lead), Codex (GPT-5)  
**Purpose:** Implement Instruction 006 fixes and validate pipeline sample  
**Duration:** ~1 hour  
**Outputs:** Code changes, unit tests, sample pipeline run, realism gap noted

---

## Summary

Implemented the full set of fixes for difficulty-tier saturation (Instruction 006) and ran a small pipeline sample to validate distributions. The fixes succeeded in spreading difficulty tiers, but the resulting synthetic records still appear too clean relative to real-world data. This prompted a documentation plan to note the realism gap.

---

## Decisions / Clarifications

- **Level dropping:** Use randomness with a strong bias toward dropping higher echelons.
- **Tier assignment:** Replace `_assign_tier` logic with the provided full block (collision-aware).
- **Confounder rate:** Set to **15%**, independent of clutter.
- **Imperfections:** Use plain-text correction patterns; abbreviation inconsistency mixed within entry; column bleed via delimiter merging.
- **Retention target:** Use `candidates` length for target count.
- **Tests:** Add unit tests now.

---

## Implementation Highlights

### Renderer (`src/synthetic/renderer.py`)
- Added `TENDENCY_RETENTION` and wired `path_completeness_tendency` into `_select_levels`.
- Implemented stochastic level dropping with a bias toward higher-echelon drops.
- Added imperfection application after vocabulary injection:
  - Typos, abbreviation inconsistency, mid-entry corrections, incomplete unit, column bleed.

### Difficulty Tiering (`src/synthetic/difficulty_computer.py`)
- Replaced `_assign_tier` logic:
  - `any_complete` no longer guarantees EASY in collision zones.
  - Collision + complete defaults to MODERATE unless structurally resolvable.

### Vocabulary Injection (`src/synthetic/vocabulary_injector.py`)
- Confounders now independent of clutter.
- `CONFOUNDER_RATE = 0.15`.

### Tests
Added `tests/synthetic/test_difficulty_saturation_fix.py`:
- Tendency affects included levels.
- Collision + complete logic returns MODERATE unless structurally resolvable.
- Confounders inject without clutter.
- Imperfections alter text.

---

## Commands Run

```bash
PYTHONPATH=. /Users/Eli/.venvs/primary311/bin/pytest tests/synthetic/test_difficulty_saturation_fix.py
```

```bash
venv/bin/python -m src.synthetic.pipeline --output-dir data/synthetic --target-records 200 --seed 42
venv/bin/python -m src.preprocessing.preprocessing_adapter --input data/synthetic/raw.parquet --output data/synthetic/canonical.parquet
```

---

## Observations

- Difficulty distribution from sample run: **easy 48.5%**, **moderate 27.3%**, **hard 15.2%**, **extreme 9.1%**.
- Records still look **too clean** despite imperfections and confounders — realism gap remains.
- Quality tier is **source-level**, not per-entry; a tier‑3 record can still look clean.

---

## Data Inspection

- Displayed canonical records for `S0031` and `S0008`.
- Joined canonical records with raw `quality_tier` for `S0008`.
- Displayed validation states for `S0008`.

---

## Follow-up

- Document the realism gap in top-level README + CLAUDE + synthetic generation component doc.
