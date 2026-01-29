"""
Prompt templates for LLM phases in resolver generation.

Contains prompts for:
- Phase 4: Pattern Discovery
- Phase 6: Vocabulary Discovery
- Phase 7: Differentiator Generation

Updated for dual-run workflow (ADR-002):
- All extraction prompts now include hard case flagging
- Hard cases are soldiers that are ambiguous or difficult to classify

Updated for grounded inference (ADR-004):
- Absence of evidence is NOT evidence of absence
- All patterns/vocabulary must be grounded in example records
- Ambiguity is a valid outcome - not all records can be disambiguated
- Distinguish observed (in records) vs inferred (from training knowledge)
"""

from typing import List, Dict, Any, Optional


# =============================================================================
# CORE INFERENCE PRINCIPLES (shared across all phases)
# =============================================================================

GROUNDING_PRINCIPLES = """
CRITICAL INFERENCE PRINCIPLES:

1. ABSENCE IS NOT EVIDENCE: A record lacking a term (e.g., no "ABN" for airborne)
   is UNINFORMATIVE, not negative evidence. Records are often abbreviated or
   context-dependent. Do NOT treat missing modifiers as signals.

2. GROUNDED CLAIMS ONLY: Every pattern or vocabulary term you identify must be
   supported by the example records provided. If you cannot point to a specific
   record containing the term, mark it as "inferred" rather than "observed".

3. AMBIGUITY IS VALID: Some records cannot be disambiguated without additional
   context. "Cannot determine" is an acceptable and often correct conclusion.
   Do not force classification when evidence is insufficient.

4. POSITIVE SIGNALS ONLY: Only the PRESENCE of a term counts as a signal.
   - "Contains 'ABN'" → positive signal FOR airborne unit ✓
   - "Does NOT contain 'ABN'" → NOT a valid signal ✗
   - "Contains 'Marine'" when expecting Army → conflict signal ✓
"""

# =============================================================================
# HARD CASE FLAGGING INSTRUCTIONS (shared across phases)
# =============================================================================

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

# =============================================================================
# PHASE 4: PATTERN DISCOVERY
# =============================================================================

PATTERN_DISCOVERY_SYSTEM = """You are an expert at analyzing historical military records to identify text patterns that indicate unit assignments. Your task is to discover patterns that distinguish one military unit from similar units.

Focus on:
1. Explicit unit names and designations ACTUALLY PRESENT in the example records
2. Abbreviations and shorthand notations you can cite from specific records
3. Slashes and combined notations (e.g., "2/5" for 2nd Battalion, 5th Regiment)
4. Observable variations in how units are referenced in the provided samples

CRITICAL CONSTRAINTS:
- Only identify patterns that appear in the provided example records
- For each pattern, you must be able to cite which record(s) contain it
- If you know a pattern from general knowledge but it doesn't appear in the examples,
  mark it as "provenance": "inferred" rather than "observed"
- Do NOT generate rules based on ABSENCE of patterns (e.g., "lacks ABN")

Be precise and conservative. Ground every claim in the provided examples."""


def build_pattern_discovery_prompt(
    component_name: str,
    component_id: str,
    rival_name: str,
    rival_id: str,
    target_texts: List[str],
    rival_texts: List[str],
    collision_levels: List[tuple],
    prior_context: Optional[str] = None,
    soldier_ids: Optional[List[str]] = None,
) -> str:
    """
    Build prompt for pattern discovery phase.

    Args:
        component_name: Canonical name of target component
        component_id: Target component ID
        rival_name: Canonical name of rival component
        rival_id: Rival component ID
        target_texts: Raw text records from target component
        rival_texts: Raw text records from rival component
        collision_levels: List of (level, value) collision points
        prior_context: Optional context from previous batches (for stateful extraction)
        soldier_ids: Optional list of soldier IDs corresponding to target_texts

    Returns:
        Formatted prompt string
    """
    collision_desc = ", ".join(
        f"{level} {value}" for level, value in collision_levels
    )

    # Format target texts with soldier IDs if available
    if soldier_ids and len(soldier_ids) == len(target_texts):
        target_sample = "\n".join(f"- [{sid}] {t}" for sid, t in zip(soldier_ids, target_texts[:15]))
    else:
        target_sample = "\n".join(f"- {t}" for t in target_texts[:15])

    rival_sample = "\n".join(f"- {t}" for t in rival_texts[:15])

    # Add prior context if provided (stateful extraction)
    prior_section = ""
    if prior_context:
        prior_section = f"""
CONTEXT FROM PREVIOUS BATCHES:
{prior_context}

Build upon these findings, but also look for NEW patterns.
"""

    return f"""Analyze these military records to find text patterns that distinguish {component_name} from {rival_name}.
{GROUNDING_PRINCIPLES}
COLLISION CONTEXT:
These units share the following designators: {collision_desc}
This means records mentioning these designators could belong to either unit.
{prior_section}
RECORDS FROM {component_name.upper()} ({component_id}):
{target_sample}

RECORDS FROM {rival_name.upper()} ({rival_id}):
{rival_sample}

TASK:
Identify text patterns that indicate a record belongs to {component_name} specifically.

For each pattern, provide:
1. The exact text pattern
2. What it means (unit assignment interpretation)
3. Confidence level (robust/strong/moderate/tentative)
4. Provenance: "observed" if you can cite specific records, "inferred" if from general knowledge
5. Example records where this pattern appears (if observed)
{HARD_CASE_INSTRUCTIONS}
When flagging hard cases, use this JSON format:
{{
  "hard_cases": [
    {{"soldier_id": "...", "layer": "collision_position|complementarity|structural_ambiguity", "reason": "...", "notes": "..."}}
  ]
}}
Respond in JSON format:
{{
  "patterns": [
    {{
      "pattern": "exact text pattern",
      "means": "interpretation (e.g., component=X, regiment=Y)",
      "tier": "robust|strong|moderate|tentative",
      "provenance": "observed|inferred",
      "example_records": ["record text where pattern appears"],
      "note": "optional caveat"
    }}
  ],
  "hard_cases": [
    {{"soldier_id": "S123", "layer": "collision_position", "reason": "shared regiment number", "notes": "brief explanation"}}
  ],
  "ambiguous_patterns": [
    {{
      "pattern": "pattern that appears in BOTH unit's records",
      "note": "why this pattern alone cannot disambiguate"
    }}
  ],
  "observations": "brief summary of key distinguishing features"
}}"""


# =============================================================================
# PHASE 6: VOCABULARY DISCOVERY
# =============================================================================

VOCABULARY_DISCOVERY_SYSTEM = """You are an expert at identifying characteristic vocabulary in historical military records. Your task is to find terms, phrases, and references that are strongly associated with a specific military unit.

CRITICAL: Distinguish between OBSERVED and INFERRED vocabulary.

OBSERVED vocabulary (preferred):
- Terms that ACTUALLY APPEAR in the provided example records
- You can cite specific records containing these terms
- These have high reliability for this specific dataset

INFERRED vocabulary (use sparingly, must be labeled):
- Terms you know are associated with this unit from general knowledge
- Unit nicknames, historical campaigns, etc. NOT seen in the examples
- These may or may not appear in the actual dataset
- Mark these clearly as "provenance": "inferred"

Focus on extracting vocabulary FROM THE PROVIDED RECORDS:
1. Unit designations and abbreviations actually used
2. Location references that appear in the records
3. Equipment or organizational terms present in the examples
4. Any distinctive notation patterns

You may ALSO note inferred vocabulary (nicknames, campaigns) but MUST mark it as such."""


def build_vocabulary_discovery_prompt(
    component_name: str,
    component_id: str,
    aliases: List[str],
    texts: List[str],
    prior_context: Optional[str] = None,
    soldier_ids: Optional[List[str]] = None,
) -> str:
    """
    Build prompt for vocabulary discovery.

    Args:
        component_name: Canonical name of component
        component_id: Component ID
        aliases: Known aliases from hierarchy
        texts: Sample raw text records
        prior_context: Optional context from previous batches (for stateful extraction)
        soldier_ids: Optional list of soldier IDs corresponding to texts

    Returns:
        Formatted prompt string
    """
    alias_section = ", ".join(aliases) if aliases else "None known"

    # Format texts with soldier IDs if available
    if soldier_ids and len(soldier_ids) == len(texts):
        text_sample = "\n".join(f"- [{sid}] {t}" for sid, t in zip(soldier_ids, texts[:25]))
    else:
        text_sample = "\n".join(f"- {t}" for t in texts[:25])

    # Add prior context if provided (stateful extraction)
    prior_section = ""
    if prior_context:
        prior_section = f"""
CONTEXT FROM PREVIOUS BATCHES:
{prior_context}

Build upon these findings, but also look for NEW vocabulary.
"""

    return f"""Analyze records to discover vocabulary characteristic of {component_name}.
{GROUNDING_PRINCIPLES}
KNOWN ALIASES:
{alias_section}
{prior_section}
SAMPLE RECORDS FROM {component_name.upper()}:
{text_sample}

TASK:
Identify vocabulary terms that are characteristic of this unit.

For EACH term, you must specify:
1. Strength: strong/moderate/weak
2. Provenance: "observed" (appears in records above) or "inferred" (from general knowledge)
3. For observed terms: cite at least one example record

IMPORTANT:
- Prioritize OBSERVED vocabulary over inferred
- Inferred vocabulary (nicknames, campaigns you know about but don't see) should be clearly marked
- Do NOT claim a term is "observed" unless you can point to a specific record containing it
{HARD_CASE_INSTRUCTIONS}
When flagging hard cases, use this JSON format:
{{
  "hard_cases": [
    {{"soldier_id": "...", "layer": "collision_position|complementarity|structural_ambiguity", "reason": "...", "notes": "..."}}
  ]
}}
Respond in JSON format:
{{
  "vocabulary": {{
    "observed": [
      {{"term": "ABN", "strength": "strong", "example_records": ["record containing ABN"]}},
      {{"term": "PIR", "strength": "strong", "example_records": ["record containing PIR"]}}
    ],
    "inferred": [
      {{"term": "Screaming Eagles", "strength": "strong", "note": "known nickname, not seen in examples"}},
      {{"term": "Bastogne", "strength": "moderate", "note": "historical association, not seen in examples"}}
    ]
  }},
  "discovered_aliases": ["any new nicknames or abbreviations found IN THE RECORDS"],
  "hard_cases": [
    {{"soldier_id": "S123", "layer": "complementarity", "reason": "all records repeat same partial path", "notes": "brief explanation"}}
  ],
  "observations": "notes on vocabulary patterns, including what was NOT found in the records"
}}"""


# =============================================================================
# PHASE 7: DIFFERENTIATOR GENERATION
# =============================================================================

DIFFERENTIATOR_SYSTEM = """You are an expert at creating disambiguation rules for military unit identification. Given two units that share certain designators, create rules that adjust CONFIDENCE in unit assignment.

CRITICAL PRINCIPLE: Absence of evidence is NOT evidence of absence.

You must create THREE types of rules:

1. POSITIVE SIGNALS: "Presence of X INCREASES confidence in Unit A"
   - Based on terms/patterns that appear in records
   - Example: "Contains 'ABN' or 'PIR' → increases confidence in airborne unit"

2. CONFLICT SIGNALS: "Presence of X DECREASES confidence in Unit A"
   - Based on POSITIVE evidence of a DIFFERENT unit type/branch
   - Example: "Contains 'Marine' → decreases confidence in Army unit"
   - NOT based on absence (e.g., "lacks ABN" is INVALID)

3. AMBIGUOUS CASES: Acknowledge when disambiguation is not possible
   - Records with only shared designators cannot be assigned
   - "Cannot determine" is a valid and often correct outcome

NEVER create rules like:
- "Does NOT contain X → Unit B" ❌
- "Absence of X → Unit B" ❌
- "Lacks X → Unit B" ❌
- "If no airborne terminology → default to infantry" ❌

These are logically invalid. Records may simply be abbreviated."""


def build_differentiator_prompt(
    component_name: str,
    component_id: str,
    rival_name: str,
    rival_id: str,
    collision_levels: List[tuple],
    component_patterns: List[Dict],
    rival_patterns: List[Dict],
    component_exclusions: List[Dict],
    component_vocabulary: Dict[str, List[str]],
) -> str:
    """
    Build prompt for differentiator generation.

    Args:
        component_name: Target component name
        component_id: Target component ID
        rival_name: Rival component name
        rival_id: Rival component ID
        collision_levels: Collision points
        component_patterns: Discovered patterns for target
        rival_patterns: Discovered patterns for rival (if available)
        component_exclusions: Exclusion rules for target
        component_vocabulary: Vocabulary for target

    Returns:
        Formatted prompt string
    """
    collision_desc = ", ".join(f"{level} {value}" for level, value in collision_levels)

    # Format patterns
    pattern_section = ""
    if component_patterns:
        pattern_lines = []
        for p in component_patterns[:5]:
            pattern_lines.append(f"  - '{p.get('pattern', '')}' -> {p.get('means', '')}")
        pattern_section = f"Patterns for {component_name}:\n" + "\n".join(pattern_lines)

    if rival_patterns:
        rival_lines = []
        for p in rival_patterns[:5]:
            rival_lines.append(f"  - '{p.get('pattern', '')}' -> {p.get('means', '')}")
        pattern_section += f"\n\nPatterns for {rival_name}:\n" + "\n".join(rival_lines)

    # Format vocabulary
    vocab_section = ""
    if component_vocabulary:
        strong = component_vocabulary.get("strong", [])
        if strong:
            vocab_section = f"Strong vocabulary for {component_name}: {strong[:5]}"

    return f"""Create disambiguation rules to distinguish {component_name} from {rival_name}.
{GROUNDING_PRINCIPLES}
COLLISION CONTEXT:
These units share: {collision_desc}

{pattern_section}

{vocab_section}

TASK:
Create rules that adjust CONFIDENCE based on OBSERVABLE EVIDENCE.

IMPORTANT CONSTRAINTS:
1. Only use PRESENCE of terms as signals, never ABSENCE
2. "Cannot determine" is a valid outcome for sparse records
3. Do NOT create fallback rules like "if nothing else matches → Unit X"

Respond in JSON format:
{{
  "positive_signals": [
    {{
      "if_contains": "term or pattern",
      "then": "increase_confidence",
      "target": "{component_name}",
      "strength": "strong|moderate|weak",
      "provenance": "observed|inferred"
    }},
    {{
      "if_contains": "term or pattern",
      "then": "increase_confidence",
      "target": "{rival_name}",
      "strength": "strong|moderate|weak",
      "provenance": "observed|inferred"
    }}
  ],
  "conflict_signals": [
    {{
      "if_contains": "term indicating different branch/type",
      "then": "decrease_confidence",
      "target": "{component_name}",
      "reason": "why this indicates a different unit"
    }}
  ],
  "structural_rules": [
    {{
      "if_contains": "regiment/battalion unique to one unit",
      "then": "identifies",
      "target": "unit name",
      "note": "structural basis for rule"
    }}
  ],
  "ambiguous_when": {{
    "condition": "description of records that cannot be disambiguated",
    "example_patterns": ["E2-16", "A/1/3"],
    "recommendation": "flag_for_review|use_source_context|cannot_determine"
  }},
  "notes": "reasoning about the rules, including what CANNOT be determined"
}}"""


# =============================================================================
# PHASE 8: TIER ASSIGNMENT (Pattern Validation)
# =============================================================================

TIER_ASSIGNMENT_SYSTEM = """You are validating discovered patterns against a sample of records. For each pattern, determine:
1. Whether it ACTUALLY APPEARS in the provided records (validates provenance)
2. How reliably it identifies the target unit when present

This is a GROUNDING check - patterns claimed as "observed" must appear in the records."""


def build_tier_assignment_prompt(
    component_name: str,
    patterns: List[Dict],
    validation_texts: List[str],
) -> str:
    """
    Build prompt for pattern tier validation.

    Args:
        component_name: Component name
        patterns: Discovered patterns to validate
        validation_texts: Sample texts for validation

    Returns:
        Formatted prompt string
    """
    pattern_list = "\n".join(
        f"- '{p.get('pattern', '')}': {p.get('means', '')} (claimed provenance: {p.get('provenance', 'unknown')})"
        for p in patterns[:10]
    )

    text_sample = "\n".join(f"- {t}" for t in validation_texts[:15])

    return f"""Validate these patterns against records from {component_name}.

PATTERNS TO VALIDATE:
{pattern_list}

SAMPLE RECORDS (confirmed {component_name}):
{text_sample}

TASK:
For each pattern, verify:
1. Does it ACTUALLY APPEAR in the records above? (provenance check)
2. How often does it appear? (frequency)
3. Assign a confidence tier:
   - robust: appears frequently and always indicates this unit
   - strong: appears regularly and reliably indicates this unit
   - moderate: appears sometimes or has some ambiguity
   - tentative: rarely appears or uncertain reliability
   - not_validated: claimed as observed but NOT FOUND in records

IMPORTANT: If a pattern was claimed as "observed" but you cannot find it in the
records above, mark it as "validated_provenance": false.

Respond in JSON format:
{{
  "validated_patterns": [
    {{
      "pattern": "the pattern",
      "tier": "robust|strong|moderate|tentative|not_validated",
      "matches_found": number,
      "validated_provenance": true|false,
      "example_matches": ["specific records where pattern appears"],
      "accuracy_estimate": "percentage or description"
    }}
  ],
  "ungrounded_patterns": [
    {{
      "pattern": "pattern claimed as observed but not found",
      "note": "could not locate in provided records"
    }}
  ]
}}"""


# =============================================================================
# OUTPUT SCHEMAS (for structured output)
# =============================================================================

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

PATTERN_DISCOVERY_SCHEMA = {
    "type": "object",
    "properties": {
        "patterns": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string"},
                    "means": {"type": "string"},
                    "tier": {"type": "string", "enum": ["robust", "strong", "moderate", "tentative"]},
                    "provenance": {"type": "string", "enum": ["observed", "inferred"]},
                    "example_records": {"type": "array", "items": {"type": "string"}},
                    "note": {"type": "string"}
                },
                "required": ["pattern", "means", "tier", "provenance"]
            }
        },
        "ambiguous_patterns": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string"},
                    "note": {"type": "string"}
                }
            }
        },
        "hard_cases": HARD_CASE_SCHEMA,
        "observations": {"type": "string"}
    },
    "required": ["patterns"]
}

VOCABULARY_TERM_SCHEMA = {
    "type": "object",
    "properties": {
        "term": {"type": "string"},
        "strength": {"type": "string", "enum": ["strong", "moderate", "weak"]},
        "example_records": {"type": "array", "items": {"type": "string"}},
        "note": {"type": "string"}
    },
    "required": ["term", "strength"]
}

VOCABULARY_DISCOVERY_SCHEMA = {
    "type": "object",
    "properties": {
        "vocabulary": {
            "type": "object",
            "properties": {
                "observed": {"type": "array", "items": VOCABULARY_TERM_SCHEMA},
                "inferred": {"type": "array", "items": VOCABULARY_TERM_SCHEMA}
            }
        },
        "discovered_aliases": {"type": "array", "items": {"type": "string"}},
        "hard_cases": HARD_CASE_SCHEMA,
        "observations": {"type": "string"}
    },
    "required": ["vocabulary"]
}

SIGNAL_SCHEMA = {
    "type": "object",
    "properties": {
        "if_contains": {"type": "string"},
        "then": {"type": "string", "enum": ["increase_confidence", "decrease_confidence", "identifies"]},
        "target": {"type": "string"},
        "strength": {"type": "string", "enum": ["strong", "moderate", "weak"]},
        "provenance": {"type": "string", "enum": ["observed", "inferred"]},
        "reason": {"type": "string"},
        "note": {"type": "string"}
    },
    "required": ["if_contains", "then", "target"]
}

DIFFERENTIATOR_SCHEMA = {
    "type": "object",
    "properties": {
        "positive_signals": {"type": "array", "items": SIGNAL_SCHEMA},
        "conflict_signals": {"type": "array", "items": SIGNAL_SCHEMA},
        "structural_rules": {"type": "array", "items": SIGNAL_SCHEMA},
        "ambiguous_when": {
            "type": "object",
            "properties": {
                "condition": {"type": "string"},
                "example_patterns": {"type": "array", "items": {"type": "string"}},
                "recommendation": {"type": "string", "enum": ["flag_for_review", "use_source_context", "cannot_determine"]}
            }
        },
        "notes": {"type": "string"}
    },
    "required": ["positive_signals", "ambiguous_when"]
}

TIER_ASSIGNMENT_SCHEMA = {
    "type": "object",
    "properties": {
        "validated_patterns": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string"},
                    "tier": {"type": "string", "enum": ["robust", "strong", "moderate", "tentative", "not_validated"]},
                    "matches_found": {"type": "integer"},
                    "validated_provenance": {"type": "boolean"},
                    "example_matches": {"type": "array", "items": {"type": "string"}},
                    "accuracy_estimate": {"type": "string"}
                },
                "required": ["pattern", "tier", "validated_provenance"]
            }
        },
        "ungrounded_patterns": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string"},
                    "note": {"type": "string"}
                }
            }
        }
    },
    "required": ["validated_patterns"]
}
