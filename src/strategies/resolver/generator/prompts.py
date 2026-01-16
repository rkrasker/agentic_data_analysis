"""
Prompt templates for LLM phases in resolver generation.

Contains prompts for:
- Phase 4: Pattern Discovery
- Phase 5: Exclusion Mining
- Phase 6: Vocabulary Discovery
- Phase 7: Differentiator Generation

Updated for dual-run workflow (ADR-002):
- All extraction prompts now include hard case flagging
- Hard cases are soldiers that are ambiguous or difficult to classify
"""

from typing import List, Dict, Any, Optional


# =============================================================================
# HARD CASE FLAGGING INSTRUCTIONS (shared across phases)
# =============================================================================

HARD_CASE_INSTRUCTIONS = """
HARD CASE FLAGGING:
As you analyze the records, identify soldiers whose records are particularly difficult to classify.
Flag a soldier as a "hard case" if:
- Multiple component indicators are present (conflicting signals)
- Key identifiers are missing or ambiguous
- Unusual notation that doesn't match known patterns
- Assignment is uncertain despite having records
- Transfer indicators are present

Include hard cases in your response:
"hard_cases": [
  {"soldier_id": "S123", "reason": "conflicting_signals|ambiguous_notation|missing_identifiers|transfer_detected", "notes": "brief explanation"}
]
"""

# =============================================================================
# PHASE 4: PATTERN DISCOVERY
# =============================================================================

PATTERN_DISCOVERY_SYSTEM = """You are an expert at analyzing historical military records to identify text patterns that indicate unit assignments. Your task is to discover patterns that distinguish one military unit from similar units.

Focus on:
1. Explicit unit names and designations
2. Abbreviations and shorthand notations
3. Slashes and combined notations (e.g., "2/5" for 2nd Battalion, 5th Regiment)
4. Common variations in how units are referenced

Be precise and conservative. Only identify patterns you're confident about."""


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
4. Any caveats or conditions
{HARD_CASE_INSTRUCTIONS}
Respond in JSON format:
{{
  "patterns": [
    {{
      "pattern": "exact text pattern",
      "means": "interpretation (e.g., component=X, regiment=Y)",
      "tier": "robust|strong|moderate|tentative",
      "note": "optional caveat"
    }}
  ],
  "hard_cases": [
    {{"soldier_id": "S123", "reason": "conflicting_signals", "notes": "brief explanation"}}
  ],
  "observations": "brief summary of key distinguishing features"
}}"""


# =============================================================================
# PHASE 5: EXCLUSION MINING
# =============================================================================

EXCLUSION_MINING_SYSTEM = """You are an expert at analyzing military organizational structures to identify exclusion rules. An exclusion rule definitively indicates that a record does NOT belong to a specific unit.

Focus on:
1. Unit type indicators (infantry vs. airborne vs. marine)
2. Branch-specific terminology
3. Invalid designator combinations
4. Structural impossibilities

Be conservative. Only identify exclusions that are definitive."""


def build_exclusion_mining_prompt(
    component_name: str,
    component_id: str,
    component_structure: Dict[str, Any],
    all_texts: List[str],
    invalid_designators: Dict[str, List[str]],
) -> str:
    """
    Build prompt for value-based exclusion mining.

    Args:
        component_name: Canonical name of component
        component_id: Component ID
        component_structure: Structure dict with valid designators
        all_texts: Sample of raw text records
        invalid_designators: Dict of level -> invalid designator list

    Returns:
        Formatted prompt string
    """
    valid_info = []
    if component_structure.get("valid_regiments"):
        valid_info.append(f"Valid regiments: {component_structure['valid_regiments']}")
    if component_structure.get("valid_battalions"):
        valid_info.append(f"Valid battalions: {component_structure['valid_battalions']}")
    if component_structure.get("valid_companies"):
        valid_info.append(f"Valid companies: {component_structure['valid_companies']}")

    valid_section = "\n".join(valid_info) if valid_info else "See hierarchy reference"

    invalid_info = []
    for level, designators in invalid_designators.items():
        if designators:
            invalid_info.append(f"Invalid {level}s: {designators[:10]}")

    invalid_section = "\n".join(invalid_info) if invalid_info else "None pre-computed"

    text_sample = "\n".join(f"- {t}" for t in all_texts[:20])

    return f"""Analyze records to find exclusion rules for {component_name}.

COMPONENT STRUCTURE:
{valid_section}

KNOWN INVALID DESIGNATORS:
{invalid_section}

SAMPLE RECORDS (all confirmed as {component_name}):
{text_sample}

TASK:
Identify value-based patterns that would EXCLUDE a record from being {component_name}.

For example:
- Specific regiment numbers that this division never had
- Battalion designators incompatible with this unit's structure
- Company letters that don't exist in this organization

Respond in JSON format:
{{
  "value_based_exclusions": [
    {{
      "if": "condition description",
      "then": "exclude",
      "confidence": "high|medium"
    }}
  ],
  "observations": "brief notes on exclusion logic"
}}"""


# =============================================================================
# PHASE 6: VOCABULARY DISCOVERY
# =============================================================================

VOCABULARY_DISCOVERY_SYSTEM = """You are an expert at identifying characteristic vocabulary in historical military records. Your task is to find terms, phrases, and references that are strongly associated with a specific military unit.

Focus on:
1. Unit nicknames and informal names
2. Geographic references (theaters, locations)
3. Campaign or operation names
4. Equipment or organizational terms
5. Commanding officer names (if historically associated)

Be careful to distinguish unit-specific vocabulary from general military terminology."""


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

KNOWN ALIASES:
{alias_section}
{prior_section}
SAMPLE RECORDS FROM {component_name.upper()}:
{text_sample}

TASK:
Identify vocabulary terms that are characteristic of this unit. Categorize by strength:

- **Strong**: Terms that almost always indicate this unit
- **Moderate**: Terms that suggest this unit but may appear in other contexts
- **Weak**: Terms that are somewhat associated but require other evidence
{HARD_CASE_INSTRUCTIONS}
Respond in JSON format:
{{
  "vocabulary": {{
    "strong": ["term1", "term2"],
    "moderate": ["term3", "term4"],
    "weak": ["term5", "term6"]
  }},
  "discovered_aliases": ["any new nicknames or abbreviations found"],
  "hard_cases": [
    {{"soldier_id": "S123", "reason": "conflicting_signals", "notes": "brief explanation"}}
  ],
  "observations": "notes on vocabulary patterns"
}}"""


# =============================================================================
# PHASE 7: DIFFERENTIATOR GENERATION
# =============================================================================

DIFFERENTIATOR_SYSTEM = """You are an expert at creating disambiguation rules for military unit identification. Given two units that share certain designators, create specific rules to tell them apart.

Focus on creating actionable rules that can be applied during record parsing. Each rule should be:
1. Specific and unambiguous
2. Based on observable text patterns
3. Clearly state which unit the rule identifies"""


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

COLLISION CONTEXT:
These units share: {collision_desc}

{pattern_section}

{vocab_section}

TASK:
Create specific rules that determine which unit a record belongs to when it contains shared designators.

Rules should be in the form:
"[Condition] -> [Unit identification]"

Respond in JSON format:
{{
  "rules": [
    "[Condition] -> {component_name}",
    "[Condition] -> {rival_name}"
  ],
  "hierarchy_rules": [
    "Rules based purely on structural differences"
  ],
  "confidence": "complete|partial|hierarchy_only",
  "notes": "any caveats about these rules"
}}"""


# =============================================================================
# PHASE 8: TIER ASSIGNMENT (Pattern Validation)
# =============================================================================

TIER_ASSIGNMENT_SYSTEM = """You are validating discovered patterns against a sample of records. For each pattern, determine how reliably it identifies the target unit."""


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
        f"- '{p.get('pattern', '')}': {p.get('means', '')}"
        for p in patterns[:10]
    )

    text_sample = "\n".join(f"- {t}" for t in validation_texts[:15])

    return f"""Validate these patterns against records from {component_name}.

PATTERNS TO VALIDATE:
{pattern_list}

SAMPLE RECORDS (confirmed {component_name}):
{text_sample}

TASK:
For each pattern, assess:
1. How often it appears in these records
2. Whether it correctly identifies the unit
3. Assign a confidence tier:
   - robust: >90% reliable
   - strong: 75-90% reliable
   - moderate: 50-75% reliable
   - tentative: <50% reliable

Respond in JSON format:
{{
  "validated_patterns": [
    {{
      "pattern": "the pattern",
      "tier": "robust|strong|moderate|tentative",
      "matches_found": number,
      "accuracy_estimate": "percentage or description"
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
            "reason": {
                "type": "string",
                "enum": ["conflicting_signals", "ambiguous_notation", "missing_identifiers", "transfer_detected", "low_confidence"]
            },
            "notes": {"type": "string"}
        },
        "required": ["soldier_id", "reason"]
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
                    "note": {"type": "string"}
                },
                "required": ["pattern", "means", "tier"]
            }
        },
        "hard_cases": HARD_CASE_SCHEMA,
        "observations": {"type": "string"}
    },
    "required": ["patterns"]
}

EXCLUSION_MINING_SCHEMA = {
    "type": "object",
    "properties": {
        "value_based_exclusions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "if": {"type": "string"},
                    "then": {"type": "string"},
                    "confidence": {"type": "string", "enum": ["high", "medium"]}
                },
                "required": ["if", "then"]
            }
        },
        "observations": {"type": "string"}
    },
    "required": ["value_based_exclusions"]
}

VOCABULARY_DISCOVERY_SCHEMA = {
    "type": "object",
    "properties": {
        "vocabulary": {
            "type": "object",
            "properties": {
                "strong": {"type": "array", "items": {"type": "string"}},
                "moderate": {"type": "array", "items": {"type": "string"}},
                "weak": {"type": "array", "items": {"type": "string"}}
            }
        },
        "discovered_aliases": {"type": "array", "items": {"type": "string"}},
        "hard_cases": HARD_CASE_SCHEMA,
        "observations": {"type": "string"}
    },
    "required": ["vocabulary"]
}

DIFFERENTIATOR_SCHEMA = {
    "type": "object",
    "properties": {
        "rules": {"type": "array", "items": {"type": "string"}},
        "hierarchy_rules": {"type": "array", "items": {"type": "string"}},
        "confidence": {"type": "string", "enum": ["complete", "partial", "hierarchy_only"]},
        "notes": {"type": "string"}
    },
    "required": ["rules"]
}
