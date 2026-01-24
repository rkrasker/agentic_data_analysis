# Disambiguation Model

This document describes the analytical framework for resolving posts within inferred states. Extracted from project context for reference.

**See also:** `CLAUDE.md` for core problem definition, `docs/architecture/CURRENT.md` for implementation architecture.

---

## The Three-Layer Disambiguation Model

This is the analytical framework for resolving posts within inferred states. Difficulty operates at three layers, but now the system must also discover the states themselves.

### Layer 1: Per-Record Extraction
Can we parse **some or all** of the post pathway from a single document?

- "Co E, 2nd Bn, 116th Inf, 29th Div" → full path extracted
- "E2-116" → partial path (company, battalion, regiment)
- "3rd" → minimal (just a number, no unit type)

**Quality tiers (1-5)** measure this layer. Tier 1 = explicit/complete. Tier 5 = fragmentary.

### Interdependence: Extraction ↔ Grouping
Per-record extraction is not a one-way prerequisite for grouping. We must extract a **set of candidate meanings** from each record to propose groupings, but those groupings provide the **context** needed to refine or expand the candidates. State resolution therefore operates as a **bootstrapping loop**: propose candidates → cluster records into states → re-interpret records in-state → resolve posts.

### Layer 2: Cross-Record Aggregation (Within a State)
Do the records that belong to a single inferred state **jointly** provide a unique post?

Two individually ambiguous records can be complementary:

| Record | Provides | Alone |
|--------|----------|-------|
| Record 1 | "Co E, 3rd Bn" | Ambiguous (which regiment?) |
| Record 2 | "116th Infantry" | Ambiguous (which battalion?) |
| **Together** | Co E, 3rd Bn, 116th | Unique path |

**Key insight**: Complementary records can resolve a post even when each record is degraded. This only works if the records are grouped into the correct state.

### Layer 3: Structural Inference
Do hierarchy constraints disambiguate even when unit types are omitted?

| Record | Text | Inference |
|--------|------|-----------|
| "516" | No unit type | Must be regiment (companies are letters, battalions are 1st/2nd/3rd) |
| "3rd" | No unit type | Could be battalion or regiment (requires other context) |

The hierarchy structure itself is a disambiguation signal. Numbers constrain valid hierarchy levels:
- "516" can only be a regiment (number too high for battalion/company)
- "A" or "E" can only be a company (letters)
- "1st", "2nd", "3rd" could be battalion or regiment (requires other context)

## The Critical Distinction

**Record quality ≠ state resolution difficulty**

| Scenario | Record Quality | State Resolution Difficulty |
|----------|---------------|-----------------------------|
| Pristine record saying "3rd Regiment" in collision zone | High (Tier 1) | High (ambiguous post, may induce false state split) |
| Degraded records saying "516" + "3rd" + "Co E" | Low (Tier 4-5) | Low (structurally unique, easy to group) |

Filtering toward degraded records does NOT guarantee hard cases. Hard cases are often those where records are high-quality but collide, or where grouping into states is ambiguous.
