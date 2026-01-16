# Project Bootstrap: Military Records Consolidation

Load this at the start of any fresh LLM session for full project context.

## Project Goal

Consolidate fragmented historical military records into coherent soldier unit assignments using LLM-based strategies.

## Core Challenge

**Cross-row synthesis:** Interpreting ambiguous notations by cross-referencing other records for the same soldier, then aggregating across all records to produce final assignment.

**This is NOT an extraction problem.** Regex handles extraction. The LLM must:
- Aggregate evidence across multiple records per soldier
- Interpret ambiguous patterns in context (e.g., "3/505" = bn/reg or reg/bn?)
- Detect transfers vs errors vs missing data
- Resolve contradictions between records
- Assign appropriate confidence

## Architecture Summary

### Pipeline Flow

```
Raw Records → [Regex Preprocessing] → canonical.parquet (routing only)
                                            ↓
                                    [Component-Based Batching]
                                            ↓
                                    [Strategy Execution] ← strategies are hot-swappable
                                            ↓
                                    [Evaluation vs Validation]
```

### Key Architectural Decisions

1. **Raw text is primary LLM input** — canonical is for routing/batching only
2. **Component-based batching** — group soldiers by likely component, load focused context
3. **Strategy plugin architecture** — all strategies solve same task, differ in guidance provided
4. **Proportional confidence tiers** — robust/strong/moderate/tentative (not percentages)
5. **Conservative exclusions** — only incompatible PRESENCE excludes, never absence

### Strategies (Peers)

| Strategy | What LLM Receives | Tradeoff |
|----------|-------------------|----------|
| Zero-Shot | Raw + hierarchy only | No prep vs higher cognitive load |
| Resolver | Raw + hierarchy + pre-learned heuristics | Requires generation workflow |
| Few-Shot | Raw + hierarchy + solved examples | Learning by example vs token-heavy |
| Multi-Pass | Multiple passes with state | Self-improving vs 2x API calls |

### Data Structures

- **validation.parquet** — Ground truth (one row per soldier)
- **raw.parquet** — Historical records (multiple rows per soldier)
- **canonical.parquet** — Regex extraction (for routing only)
- **hierarchy/{component}.json** — Per-component structure
- **resolver/{component}_resolver.json** — Pre-learned heuristics (resolver strategy)

## Key Decisions in Effect

- Raw text is primary LLM input (canonical for routing only)
- Component-based batching for token efficiency
- Resolver is one strategy among peers (zero-shot, few-shot, multi-pass)
- Cross-record context for pattern interpretation (soldier-level aggregation)
- Vocabulary is tiebreaker only (one tier nudge max)
- Absence of data never excludes a component

## Open Questions

<!-- Update with current unresolved tensions -->

- [List current open questions here]

---

## Session Recovery

If resuming after a session timeout:

1. **Check current status:** `README.md` → Current Status section
2. **Review component docs:** `docs/components/[name]/CURRENT.md`
3. **Check implementation status:** Look at `src/` structure and existing code
4. **Run demo to verify:** `python examples/harness_demo.py`

**Key entry points:**
- Harness foundation: `docs/components/harness/CURRENT.md`
- Resolver strategy: `docs/components/strategies/resolver/CURRENT.md`
- Architecture: `docs/architecture/CURRENT.md`

---

## Session Prompt

What aspect are you working on today? State:

1. **Theme namespace** (e.g., strategy/resolver/collision-detection)
2. **Specific question** you're exploring
3. **Context needed** (any recent decisions or constraints)
