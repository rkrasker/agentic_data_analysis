# Preprocessing

**Status:** Not yet implemented  
**Last Updated:** YYYY-MM-DD

## Purpose

Extract lightweight signals from raw records for component routing and batching. Output is used for routing only — raw text remains primary LLM input.

## Responsibilities

- Regex extraction of unit fragments
- Component signal identification
- ID resolution via corr table

## Dependencies

- **Upstream:** Raw records (data/raw/)
- **Downstream:** Batching, Strategy execution

## Subcomponents

### Regex Extraction
Extract patterns from raw text into canonical format.
- Implementation: `src/preprocessing/regex_extractor.py`

### Component Routing
Identify likely component based on extracted signals.
- Implementation: `src/preprocessing/component_router.py`

### ID Resolution
Apply corr table to resolve old IDs to current.
- Implementation: `src/preprocessing/id_resolver.py`

## Key Design Questions (Open)

- [ ] [Question 1]
- [ ] [Question 2]

## Implementation Status

| Subcomponent | Status | Location |
|--------------|--------|----------|
| Regex Extraction | Not started | `src/preprocessing/regex_extractor.py` |
| Component Routing | Not started | `src/preprocessing/component_router.py` |
| ID Resolution | Not started | `src/preprocessing/id_resolver.py` |

## References

- Architecture: `docs/architecture/CURRENT.md`
