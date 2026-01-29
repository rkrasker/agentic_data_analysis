# SESSION_STATE.md

**Last Updated:** 2026-01-29
**Session:** Opus 4.5 architecture session — Synthetic metadata separation (ADR-010)

---

## Active Task

**Instruction 010:** Implement synthetic metadata schema separation (ADR-010)

Implementation complete; follow-up: regenerate artifacts and update any downstream notebooks/scripts.

---

## Completed This Session

### Implemented ADR-010 Schema Separation

- Added `src/difficulty/` module for ground-truth difficulty computation
- Refactored synthetic pipeline outputs into core + synthetic metadata files
- Added `gt_difficulty.parquet` post-hoc computation in synthetic pipeline
- Updated preprocessing difficulty outputs to `inferred_*` with writer CLI
- Updated preprocessing adapter to use new raw schema and synthetic_records passthrough
- Updated tests and docs for new schema and prefixes

### Created ADR-010: Synthetic Metadata Separation

Resolved confusion about difficulty column provenance by establishing:

**The Three Computation Contexts:**

| Context | Prefix | Ground Truth? | Purpose |
|---------|--------|---------------|---------|
| Generation control | `gen_` | Yes | Control synthetic difficulty distribution |
| Ground-truth | `gt_` | Yes | Evaluation stratification |
| Inferred | `inferred_` | No | Production routing/prioritization |

**New Schema (pending implementation):**

| File | Contents |
|------|----------|
| `raw.parquet` | Core only: source_id, soldier_id, raw_text |
| `validation.parquet` | Labels only: state_id, post_path, branch, levels |
| `synthetic_records.parquet` | Per-record generation metadata |
| `synthetic_soldiers.parquet` | Per-soldier gen_* metrics |
| `gt_difficulty.parquet` | Ground-truth difficulty (gt_* columns) |
| `inferred_difficulty.parquet` | Inferred difficulty (inferred_* columns) |

### Created Implementation Instruction

**File:** `instructions/010_separate_synthetic_metadata_schema.md`

- 5-phase implementation plan
- Full schema specifications for all files
- Acceptance criteria

### Updated Documentation

| File | Update |
|------|--------|
| `DIFFICULTY_MODEL.md` | Added "Computation Contexts" section |
| `docs/components/synthetic_data_generation/CURRENT.md` | Added ADR-010 schema note |
| `docs/components/preprocessing/CURRENT.md` | Added ADR-010 refs, difficulty submodule, inferred_ outputs |
| `docs/ADR_INDEX.md` | Added ADR-010 entry |
| `CLAUDE.md` | Added ADR-010 to Key ADRs table |

### Updated Context Packets

| File | Update |
|------|--------|
| `docs/context-packets/full-bootstrap.md` | Updated to Terraform Combine domain, new schema, difficulty stabilized |
| `docs/context-packets/planning-synthetic.md` | Added ADR-010, DIFFICULTY_MODEL.md, schema separation concepts |
| `docs/context-packets/planning-resolver.md` | Added ADR-009, DIFFICULTY_MODEL.md references |

### Created Session Extract

**File:** `.project_history/extracts/raw/2026-01-29_opus_synthetic-metadata-separation.md`

---

## Where I Left Off

**Implementation complete.** Pending: regenerate artifacts and validate downstream consumers.

ADR-010 establishes the schema separation and naming conventions. Instruction 010 provides the implementation roadmap. Next step is to execute the instruction.

---

## Task Dependencies (Updated)

```
ADR-010 schema separation design        ✓ COMPLETE
        │
        ├──► Instruction 010 written    ✓ COMPLETE
        │
        └──► Implementation             ✓ COMPLETE
                │
                ├──► Refactor src/synthetic/pipeline.py outputs    ✓
                ├──► Create src/difficulty/ground_truth.py         ✓
                ├──► Update src/preprocessing/difficulty/ prefix   ✓
                └──► Update downstream consumers/docs/tests        ✓
```

---

## Open Questions

### Resolved This Session

1. ~~**Where do difficulty columns come from?**~~ → Two implementations: synthetic (gen_) and preprocessing (inferred_)
2. ~~**How to distinguish difficulty contexts?**~~ → Prefix convention: gen_, gt_, inferred_
3. ~~**Where does state_id belong?**~~ → Not in raw.parquet; in synthetic_records.parquet and validation.parquet

### Still Open

4. **Cross-branch collision handling:** Partially addressed. May need refinement with real examples.

5. **Migration path for resolver code/notebooks:** Existing code marked "complete" — refactoring strategy TBD.

---

## Artifacts Produced This Session

| Artifact | Location | Status |
|----------|----------|--------|
| ADR-010 | `docs/architecture/decisions/ADR-010-synthetic-metadata-separation.md` | ✓ Complete |
| Instruction 010 | `instructions/010_separate_synthetic_metadata_schema.md` | ✓ Complete |
| Session Extract | `.project_history/extracts/raw/2026-01-29_opus_synthetic-metadata-separation.md` | ✓ Complete |
| Code Activity Log | `.project_history/code-activity/2026-01-29.md` | ✓ Complete |

## Artifacts from Previous Sessions (Still Relevant)

| Artifact | Location | Status |
|----------|----------|--------|
| Structural Discriminators Module | `src/preprocessing/hierarchy/structural_discriminators.py` | ✓ Complete |
| Structural Discriminators Output | `config/hierarchies/structural_discriminators.json` | ✓ Generated |
| Difficulty Module | `src/preprocessing/difficulty/compute.py` | ✓ Complete (needs inferred_ prefix update) |
| Synthetic Pipeline Notebook | `synthetic_generation_pipeline.ipynb` | ✓ Added |

---

## Next Steps

1. **Regenerate artifacts** — run synthetic pipeline and preprocessing to produce new files
2. **Update downstream notebooks/scripts** — migrate any old schema usage
3. **sampling.py updates** — add difficulty-based sampling
4. **Resolver Phase 5 update** — wire up to use pre-computed exclusion rules

---

## References

- `ADR-010` — Synthetic metadata separation (this session's decision)
- `ADR-006` — Three-layer difficulty model
- `ADR-009` — Resolver generation alignment
- `DIFFICULTY_MODEL.md` — Now includes computation contexts section
- `docs/DISAMBIGUATION_MODEL.md` — Three-layer conceptual framework
