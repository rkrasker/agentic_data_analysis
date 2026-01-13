# Synthetic Data Workflow: Truth → Render (Manifest Shorthand)

## Why this workflow exists
You have ground-truth soldier/unit data (`validation.parquet`) but cannot share or directly use archival manifests. The goal is to generate large-scale synthetic `raw_text` that:
1) resembles archival capture artifacts (compressed shorthand, inconsistent formatting),
2) contains realistic ambiguity/confounders,
3) still has learnable signals linking language to component categories (infantry vs airborne vs marine vs air force, etc.),
4) is reproducible and comparable across future experiments.

## Key design decision: separate Truth from Rendering
### Truth
Represents “what the soldier is”:
- identity (primary_id, canonical name parts)
- canonical assignment (division/regiment/battalion/company, or air-force equivalents)
- component_id (ties into your hierarchy reference)
- optional dynamics (id changes, rare unit changes)

Truth is stable and is not required to look like a document.

### Rendering
Represents “how it got written down”:
- clerk/source style (source_profile)
- shorthand dialect (slash vs run-on vs labeled micro)
- token placement (templates)
- ambiguity (two unit-like tokens without relationship text)
- confounders (berths, decks, serial fragments, admin marks)
- capture noise (spacing jitter, OCR confusions, truncation)

Multiple different raw lines can correspond to the same truth.

## What’s in the reusable artifacts
### 1) `synthetic_style_spec_v1.yaml`
A config that defines:
- templates for assembling lines
- shorthand families and orientation rules (including reversal clerks)
- extra text snippet families and an affinity map to components
- noise profiles
- global distributions (records per soldier, sources per soldier, quality tiers)

### 2) `seed_set_v1.jsonl`
A small, auditable set of rendered examples with embedded truth.
Use it to:
- eyeball realism
- test that your renderer expresses the intended ambiguity and correlations
- calibrate probabilities without generating 250k rows

### 3) `AGENT_BUILD_INSTRUCTIONS.md`
A procedural guide for an agentic code model to build the generator:
- load spec + truth
- assign clustered source profiles
- render name/rank/unit/extra snippets
- apply noise
- output schema-compatible `raw.parquet`

## How the generator should behave (at a glance)
- Compressed shorthand is common, not exceptional.
- Reversal (parent/child orientation) is rare overall but common within a specific clerk/source.
- Extra text is inserted often enough to act as a feature signal, but not so deterministically that classification is trivial.
- Confounders are “document-context-driven,” not random noise.

## Practical usage pattern
1) Adjust only the spec (YAML) until the data “reads right.”
2) Keep Python renderer stable and deterministic.
3) Re-run generation with a seed to produce new raw datasets that are comparable across model experiments.

