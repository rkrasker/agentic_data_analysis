# Theme Namespaces

## Namespace Principles

1. Strategy-agnostic pipeline stages at top level
2. All strategies are peers under strategy/
3. Data structures use data/[name]-[format] pattern (extensible without editing this list)
4. New concepts start in uncategorized/[topic] until pattern emerges
5. After 3+ extracts share an uncategorized tag, consider promotion to proper namespace

## Extension Rules

### Adding a new strategy
- Create strategy/[strategy-name]/
- Add sub-namespaces as concepts emerge
- Cross-strategy concerns go in strategy/_comparison

### Adding a new data structure
- Use data/[name]-[format] pattern immediately
- Examples: data/batch-assignments-parquet, data/pattern-cache-json
- No pre-registration required

### Adding a new pipeline stage
- If strategy-agnostic: top-level namespace (peer to preprocessing/, batching/)
- If strategy-specific: under strategy/[name]/

### Handling uncategorized
- Tag as uncategorized/[descriptive-topic]
- After 3+ extracts, promote to proper namespace
- Review uncategorized/ weekly during synthesis

---

## Core Pipeline (strategy-agnostic)

### architecture/
Top-level design decisions spanning the whole system.
- core-problem — cross-row synthesis, fragmentation, collision challenges
- pipeline-flow — preprocessing → batching → strategy → evaluation
- input-formats — raw vs canonical, what LLM receives
- token-management — context budgets, batch sizing constraints
- decisions/ — architecture decision records (ADRs)

### preprocessing/
Steps before strategy execution.
- regex-extraction — what regex does, canonical output structure
- component-routing — assigning soldiers to likely components
- id-resolution — corr table application, alt_id handling

### batching/
Grouping soldiers for efficient LLM processing.
- component-grouping — logic for grouping by component
- batch-sizing — soldiers per batch, token considerations
- multi-component — handling ambiguous or mixed-component batches
- context-loading — what hierarchy/strategy data loads per batch

### consolidation/
The core task all strategies perform (strategy-agnostic framing).
- cross-row-synthesis — aggregating information across records
- pattern-interpretation — resolving ambiguous notations
- confidence-assignment — how confidence is determined
- transfer-detection — distinguishing unit changes from errors

### evaluation/
Measuring strategy performance.
- accuracy-metrics — comparison vs validation holdout
- confidence-calibration — does high confidence mean correct?
- strategy-comparison — cross-strategy metrics and analysis
- error-analysis — categorizing failure modes

---

## Strategies

### strategy/_comparison
Cross-strategy analysis, tradeoffs, head-to-head results.

### strategy/zero-shot/
No pre-learned heuristics; LLM discovers patterns during parsing.
- prompt-design — instruction structure, hierarchy presentation
- failure-modes — where zero-shot struggles

### strategy/resolver/
Pre-learned heuristics from validation data.
- generation-workflow — the multi-phase resolver creation process
- pattern-discovery — finding shorthand patterns in records
- pattern-tiers — confidence levels (robust/strong/moderate/tentative)
- vocabulary-signals — characteristic terms and their weight
- collision-detection — identifying component overlaps
- exclusion-logic — incompatible-presence rules
- differentiators — rules distinguishing similar components

### strategy/few-shot/
Learning from solved examples.
- example-selection — which soldiers/records to include
- example-format — how to present examples to LLM
- shot-count-tradeoffs — more examples vs token cost

### strategy/multi-pass/
Iterative refinement across multiple LLM calls.
- pass-structure — what each pass does
- state-between-passes — what persists across passes
- convergence — when to stop iterating

### strategy/[future]/
Placeholder for strategies not yet conceived. Create as needed.

---

## Data Structures

Pattern: data/[structure-name]-[format]

### Currently known:
- data/validation-parquet — ground truth, one row per soldier
- data/raw-parquet — historical records, multiple rows per soldier
- data/canonical-parquet — regex extraction output
- data/consolidated-parquet — canonical with ID resolution
- data/corr-parquet — old_id → new_id mapping
- data/unit-changes-parquet — transfer documentation
- data/soldier-component-mapping-parquet — component routing assignments
- data/hierarchy-json — per-component structural schema
- data/resolver-json — resolver strategy heuristics

### Adding new structures:
Use pattern immediately: data/[name]-[format]
Examples: data/pattern-cache-json, data/batch-log-parquet

---

## Workflow

Meta-process for managing project knowledge across LLMs.
- thread-extraction — Layer 1: extracting themes from threads
- daily-reconciliation — Layer 2: synthesizing across same-day extracts
- synthesis-process — Layer 3: updating CURRENT.md from reconciliations
- cleanup-retroactive — processing historical threads
- hygiene-practices — discipline for clean ongoing threads

---

## Catch-all

### uncategorized/[topic]
Explicit home for concepts that don't fit existing namespaces.
- Tag freely during extraction
- Review weekly during synthesis
- Promote after 3+ occurrences suggest stable pattern
