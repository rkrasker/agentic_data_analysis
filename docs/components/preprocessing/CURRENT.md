# Preprocessing

**Status:** Regex extraction implemented, routing/ID resolution pending
**Last Updated:** 2026-01-12

## Purpose

Extract structured fields from raw military records using pattern matching. Provides both routing signals for pipeline orchestration and structured attributes for downstream consolidation.

## Responsibilities

- **Field extraction:** Parse roster text into structured categories (units, roles, organizations, numeric/alpha identifiers)
- **Glossary-driven patterns:** Build regex alternations from term glossaries with stem/literal matching logic
- **Component signal identification:** Extract signals for routing decisions
- **ID resolution:** Apply corr table to resolve old IDs to current (pending)

## Design Philosophy

### Hybrid Approach: Regex + LLM

**Regex preprocessing** handles what it does well:
- Fast, deterministic pattern matching at scale
- Extracting surface-level tokens from unstructured text
- Providing structured attributes for batching/routing decisions
- Unicode-safe, case-insensitive, vectorized pandas operations

**LLM layers** handle what regex cannot:
- Semantic disambiguation (is "Company E" the unit or just mentioned context?)
- Cross-record reasoning about unit relationships
- Temporal/hierarchical consolidation
- Handling novel patterns not in glossary

**Key principle:** Raw text remains the primary LLM input. Regex outputs are supplementary signals, not replacements for LLM interpretation.

## Architecture

### Input/Output Contract

**Input:**
- DataFrame with `Name` (required), `Notes` (optional) columns
- Glossary DataFrame with `full term`, `abbreviations`, `term type` columns

**Output:**
- Original DataFrame + list-valued extraction columns:
  - **Paired categories:** `Unit_Term_Alpha_Term:Pair`, `Org_Term_Digit_Term:Pair`, etc.
  - **Split derivatives:** `Unit_Term_Alpha_Term:Unit`, `Unit_Term_Alpha_Term:Alpha`, etc.
  - **Standalone:** `Org_Terms`, `Unit_Terms`, `Role_Terms`, `Unchar_Alpha`, `Unchar_Digits`
  - **Optional:** `Special_Numbers` (exact-length extraction, e.g., 4-digit years)

### Key Design Choices

#### 1. Glossary-Driven Pattern Generation

Terms from the glossary drive regex alternations:
- **Short terms** (≤ threshold): Literal match with letter-boundary constraint
- **Long terms** (> threshold): Stem match allowing suffix variations

*Rationale:* Balances precision (avoid false matches on short strings) with recall (catch inflected forms of longer terms).

#### 2. Unicode-Safe Boundaries

Uses `(?<![^\W\d_])` and `(?![^\W\d_])` instead of `\b`:
- Handles accented names, curly quotes, em-dashes
- More reliable than ASCII-centric word boundaries

#### 3. Paired Category Extraction

Captures term-number and term-alpha pairs bidirectionally:
- `506th PIR` → `PIR:506`
- `Company E` → `COMPANY:E`
- `75 Counterintelligence` → `COUNTERINTELLIGENCE:75`

*Rationale:* Historical records use inconsistent ordering. Capturing both directions and normalizing to canonical format (TERM:VALUE) enables consistent downstream processing.

#### 4. Factorize-Extract-Broadcast Pattern

Process unique `Name ¶ Notes` strings once, broadcast results:
```
df → factorize → extract(unique_texts) → broadcast(codes) → df_out
```

*Rationale:* Roster datasets have significant text duplication. This optimization provides ~10-100x speedup on typical data.

#### 5. Graceful Degradation

Failed extraction categories return sentinel values (`<EXTRACT_FAIL:CATEGORY>`) with error details:
- Pipeline continues even if one category fails
- Timing and error metadata available for debugging

## Implementation

### File Structure

```
src/preprocessing/
├── regex_preprocessing.py    # Core extraction engine (implemented)
├── regex_extractor.py        # High-level wrapper (pending)
├── component_router.py       # Route records based on signals (pending)
└── id_resolver.py            # Corr table application (pending)
```

### regex_preprocessing.py

Fully vectorized, pandas-only extraction engine.

**Key functions:**
- `compile_patterns(gloss_df, **config)` → Compiled regex patterns
- `extract_roster_fields(df, gloss_df, **config)` → DataFrame with extracted columns

**Configuration knobs:**
- `stem_threshold`, `max_suffix_len`: Control literal vs. stem matching
- `num_min_len`, `num_max_len`: Digit length bounds (e.g., exclude 4-digit years from unit numbers)
- `alpha_letters`, `alpha_tokens`: Define valid company letters and Roman numerals
- `special_num_lengths`: Extract exact-length numbers separately (e.g., years)
- `case_insensitive`, `enable_timing`, `on_error`: Behavior controls

**Outputs:**
- All tokens normalized to ALL CAPS
- List-valued columns (multiple matches per record)
- Optional timing/error diagnostics

### Integration Points

#### Upstream: Raw Data
- Reads `data/raw/` records
- Expects minimally cleaned text (Name/Notes fields)

#### Downstream: Batching
- Extracted signals feed batching decisions:
  - Group by unit terms for unit-focused strategies
  - Route by organization terms for hierarchy inference
  - Use alpha/numeric patterns for component identification

#### Downstream: LLM Strategies
- Structured attributes supplement raw text in prompts
- LLM sees both raw context AND parsed signals
- Enables hybrid reasoning (deterministic + semantic)

## Dependencies

- **Upstream:** Raw records (`data/raw/`), term glossaries (`config/glossaries/`)
- **Downstream:** Batching, Strategy execution modules
- **External:** pandas, numpy (no LLM dependencies at this layer)

## Subcomponents

### Regex Extraction ✓ Implemented
Extract patterns from raw text into structured columns.
- **Implementation:** `src/preprocessing/regex_preprocessing.py`
- **Status:** Complete, production-ready

### Component Routing (Pending)
High-level wrapper: load glossary, extract, route to components.
- **Implementation:** `src/preprocessing/component_router.py`
- **Status:** Not started
- **Design:** Use extracted `Unit_Terms`, `Org_Terms` to infer likely component (Army, Navy, Air Force, etc.)

### ID Resolution (Pending)
Apply corr table to resolve old soldier IDs to current canonical IDs.
- **Implementation:** `src/preprocessing/id_resolver.py`
- **Status:** Not started
- **Design:** Join on old ID, replace with new ID, log unmatched

## Key Design Questions

- [x] ~~Should regex replace or supplement LLM?~~ → **Supplement.** Raw text remains primary input.
- [x] ~~How to handle glossary terms with inflections?~~ → **Stem matching for long terms, literal for short.**
- [ ] What routing signals are sufficient for component classification?
- [ ] How should ID resolution failures be handled (strict vs. lenient)?
- [ ] Should extracted fields be validated/corrected by LLM before consolidation?

## Testing Strategy

1. **Unit tests:** Pattern compilation, boundary cases (unicode, ordering)
2. **Integration tests:** Full extraction on synthetic roster data
3. **Performance benchmarks:** Factorize optimization on realistic data volumes
4. **Error handling:** Verify graceful degradation with malformed glossaries

## Implementation Status

| Subcomponent | Status | Location |
|--------------|--------|----------|
| Regex Extraction | ✓ Complete | `src/preprocessing/regex_preprocessing.py` |
| Component Routing | Not started | `src/preprocessing/component_router.py` |
| ID Resolution | Not started | `src/preprocessing/id_resolver.py` |

## Future Enhancements

- **Adaptive glossaries:** Learn new terms from LLM outputs, expand glossary over time
- **Canonicalization:** Map surface forms to canonical terms (glossary integration)
- **Multi-pass extraction:** Iteratively refine patterns based on LLM feedback

## References

- **Architecture:** `docs/architecture/CURRENT.md`
- **Implementation:** `src/preprocessing/regex_preprocessing.py` (docstring for API details)
- **Example usage:** See inline comments at end of `regex_preprocessing.py`
