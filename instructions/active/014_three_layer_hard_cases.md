# 014: Three-Layer Hard Case Criteria

**Status:** active
**Created:** 2026-01-29
**Component:** src/strategies/resolver/generator/

## Context

ADR-009 Decision 4 specifies that hard case criteria should align with the three-layer difficulty model (ADR-006) rather than using symptomatic criteria. The current hard case instructions in prompts.py include:

**Current (symptomatic):**
- Multiple component indicators present
- Key identifiers missing or ambiguous
- Unusual notation not matching known patterns
- **Transfer indicators present** ← WRONG (state discovery, not resolver scope)
- Record contains only shared designators

**Required (structural, per ADR-009):**
- Layer 2: Collision position (partial path non-unique)
- Layer 2: Non-complementary records (same ambiguous path repeated)
- Layer 3: Structural ambiguity (designators don't resolve)

## Task

Update hard case criteria in prompts to use three-layer model, and add layer tracking to hard case output.

## Scope

- **Working in:** `src/strategies/resolver/generator/prompts.py`, `src/strategies/resolver/generator/dual_run.py`, `src/strategies/resolver/generator/reconciliation.py`
- **Reference:** `docs/architecture/decisions/ADR-009_resolver-generation-alignment.md`, `DIFFICULTY_MODEL.md`
- **Config inputs:** None
- **Test location:** `tests/strategies/resolver/generator/`
- **Ignore:** `.project_history/`, LLM phase logic, sampling

## Inputs

None—this is a prompt and schema update.

## Outputs

### Updated Hard Case Schema (in LLM responses)

```json
{
  "hard_cases": [
    {
      "soldier_id": "s_12345",
      "layer": "collision_position",
      "reason": "Regiment 3 belongs to both 82nd and 101st",
      "notes": "No distinguishing battalion or company info"
    },
    {
      "soldier_id": "s_67890",
      "layer": "structural_ambiguity",
      "reason": "'3rd' could be battalion (under 2-26) or regiment (82nd)",
      "notes": "Need additional context to disambiguate"
    }
  ]
}
```

### Updated HardCase Dataclass

```python
@dataclass
class HardCase:
    soldier_id: str
    layer: str  # "collision_position" | "complementarity" | "structural_ambiguity"
    reason: str
    notes: str = ""
    flagged_in: str = ""  # which phase flagged this
```

## Implementation Steps

### Step 1: Update HARD_CASE_INSTRUCTIONS in prompts.py

Replace the current instructions with:

```python
HARD_CASE_INSTRUCTIONS = """
## Hard Cases (Three-Layer Difficulty Model)

Flag a soldier as a "hard case" when disambiguation is structurally difficult.
Use these specific criteria aligned with the three-layer model:

### Layer 2: Collision Position
Flag if the soldier's partial path is NON-UNIQUE across components.
- Example: "Regiment 3" exists in both 82nd Airborne and 101st Airborne
- Example: "Battalion A" is shared by multiple divisions
- Key indicator: The path segment alone cannot determine the component

### Layer 2: Complementarity (Non-Complementary Records)
Flag if ALL records provide the SAME ambiguous partial path with no additional differentiation.
- Example: Three records all say "3rd Regiment" with no battalion or company info
- Example: Records repeat the same level without covering other levels
- Key indicator: Records don't provide complementary path segments

### Layer 3: Structural Ambiguity
Flag if designators don't resolve structurally even with context.
- Example: "3rd" could be battalion (numeric) or regiment (ordinal)
- Example: Abbreviation matches multiple level types
- Key indicator: Syntax/format doesn't distinguish the level

### DO NOT Flag
- Transfer indicators (that's state discovery, not component discrimination)
- Low quality records (quality is orthogonal to difficulty)
- Missing data alone (only flag if missing data creates structural ambiguity)

### Output Format
For each hard case, specify:
- soldier_id: The soldier identifier
- layer: One of "collision_position", "complementarity", "structural_ambiguity"
- reason: Brief explanation of why this is hard
- notes: Any additional context (optional)
"""
```

### Step 2: Update HARD_CASE_SCHEMA in prompts.py

Add or update the JSON schema for hard cases:

```python
HARD_CASE_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "soldier_id": {"type": "string"},
            "layer": {
                "type": "string",
                "enum": ["collision_position", "complementarity", "structural_ambiguity"]
            },
            "reason": {"type": "string"},
            "notes": {"type": "string"}
        },
        "required": ["soldier_id", "layer", "reason"]
    }
}
```

### Step 3: Update build_pattern_discovery_prompt()

Find where `HARD_CASE_INSTRUCTIONS` is used and ensure the prompt requests the layer field:

```python
def build_pattern_discovery_prompt(...) -> str:
    # ... existing code ...

    # Ensure hard case output format is specified
    hard_case_format = """
When flagging hard cases, use this JSON format:
{
  "hard_cases": [
    {"soldier_id": "...", "layer": "collision_position|complementarity|structural_ambiguity", "reason": "...", "notes": "..."}
  ]
}
"""
    # Include in prompt
```

### Step 4: Update build_vocabulary_discovery_prompt()

Same update as pattern discovery—ensure layer field is requested.

### Step 5: Update HardCase dataclass in dual_run.py

```python
@dataclass
class HardCase:
    """A soldier flagged as difficult to disambiguate.

    Attributes:
        soldier_id: The soldier identifier
        layer: Which difficulty layer caused the flag:
            - "collision_position": Partial path shared by multiple components
            - "complementarity": Records don't provide distinct path segments
            - "structural_ambiguity": Designators don't resolve syntactically
        reason: Brief explanation of the difficulty
        notes: Additional context (optional)
        flagged_in: Which phase flagged this case
    """
    soldier_id: str
    layer: str
    reason: str
    notes: str = ""
    flagged_in: str = ""
```

### Step 6: Update hard case parsing in dual_run.py

Find where hard cases are parsed from LLM responses and update to extract the layer field:

```python
def parse_hard_cases(response: dict, phase_name: str) -> List[HardCase]:
    """Parse hard cases from LLM response."""
    hard_cases = []
    for hc in response.get("hard_cases", []):
        hard_cases.append(HardCase(
            soldier_id=hc["soldier_id"],
            layer=hc.get("layer", "unknown"),  # Graceful fallback
            reason=hc["reason"],
            notes=hc.get("notes", ""),
            flagged_in=phase_name,
        ))
    return hard_cases
```

### Step 7: Update reconciliation.py for layer-based analysis

Add layer grouping to the reconciliation analysis:

```python
def analyze_hard_cases_by_layer(hard_cases: List[HardCase]) -> Dict[str, List[HardCase]]:
    """Group hard cases by difficulty layer for analysis."""
    by_layer = {
        "collision_position": [],
        "complementarity": [],
        "structural_ambiguity": [],
        "unknown": [],
    }
    for hc in hard_cases:
        layer = hc.layer if hc.layer in by_layer else "unknown"
        by_layer[layer].append(hc)
    return by_layer

def generate_reconciliation_summary(hard_cases: List[HardCase]) -> dict:
    """Generate summary including layer breakdown."""
    by_layer = analyze_hard_cases_by_layer(hard_cases)
    return {
        "total_hard_cases": len(hard_cases),
        "by_layer": {
            layer: len(cases) for layer, cases in by_layer.items()
        },
        "collision_position_cases": [hc.soldier_id for hc in by_layer["collision_position"]],
        "complementarity_cases": [hc.soldier_id for hc in by_layer["complementarity"]],
        "structural_ambiguity_cases": [hc.soldier_id for hc in by_layer["structural_ambiguity"]],
    }
```

### Step 8: Update resolver JSON hard case output (if stored)

If hard cases are stored in the resolver JSON, update the schema in assembler.py:

```python
def _build_meta_section(..., hard_cases: List[HardCase]) -> dict:
    return {
        # ... existing fields ...
        "hard_cases_flagged": len(hard_cases),
        "hard_cases_by_layer": {
            "collision_position": sum(1 for hc in hard_cases if hc.layer == "collision_position"),
            "complementarity": sum(1 for hc in hard_cases if hc.layer == "complementarity"),
            "structural_ambiguity": sum(1 for hc in hard_cases if hc.layer == "structural_ambiguity"),
        }
    }
```

## Acceptance Criteria

- [ ] `HARD_CASE_INSTRUCTIONS` uses three-layer criteria (collision_position, complementarity, structural_ambiguity)
- [ ] "Transfer indicators" removed from hard case criteria
- [ ] `HardCase` dataclass has `layer` field
- [ ] LLM prompts request layer in hard case output
- [ ] Hard case parsing extracts layer field (with graceful fallback)
- [ ] Reconciliation can group/analyze hard cases by layer
- [ ] Resolver JSON meta section includes layer breakdown
- [ ] Tests pass in `tests/strategies/resolver/generator/`
- [ ] No regressions in pattern/vocabulary discovery

## Notes

### Code Style

Follow `docs/CODE_STYLE.md`:
- `analyze_hard_cases_by_layer()` is a simple function, not a class
- Use dict for grouping, not a custom container
- Keep `HardCase` as a dataclass

### Graceful Degradation

LLM responses might not always include the layer field (especially early in transition). Handle this:
- Default to `layer="unknown"` if not provided
- Log a warning but don't fail
- The "unknown" category in analysis reveals prompt compliance issues

### What Each Layer Means

| Layer | Question | Example |
|-------|----------|---------|
| collision_position | Is the partial path shared? | "Regiment 3" in multiple divisions |
| complementarity | Do records cover different segments? | All records say same thing |
| structural_ambiguity | Does syntax distinguish level? | "3rd" = battalion or regiment? |

### Testing

Test that:
1. Prompts include updated instructions
2. HardCase dataclass has layer field
3. Parsing handles missing layer gracefully
4. Reconciliation groups by layer correctly

Mock LLM responses, don't rely on actual LLM calls.

## References

- ADR-009: `docs/architecture/decisions/ADR-009_resolver-generation-alignment.md` (Decision 4)
- ADR-006: `docs/architecture/decisions/ADR-006_per-record-vs-per-soldier-difficulty.md` (three-layer model)
- DIFFICULTY_MODEL.md: Operational difficulty definitions
- Current prompts: `src/strategies/resolver/generator/prompts.py`
- Current dual_run: `src/strategies/resolver/generator/dual_run.py`
