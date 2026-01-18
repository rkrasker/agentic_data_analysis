"""
Module 4: LLM Phases Orchestrator

Orchestrates LLM-based discovery phases (Phases 4-8).
- Phase 4: Pattern Discovery
- Phase 5: Exclusion Mining
- Phase 6: Vocabulary Discovery
- Phase 7: Differentiator Generation
- Phase 8: Tier Assignment
"""

import json
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple

import pandas as pd
from pydantic import BaseModel

from src.utils.llm import create_provider, Message, LLMResponse, BaseLLMProvider
from src.utils.llm.structured import extract_json_from_text

from .thresholds import TierName, tier_allows_patterns, tier_allows_vocabulary, tier_allows_value_exclusions
from .structure import ComponentStructure, get_structural_exclusions, get_invalid_designators
from .sampling import ComponentSamples, CollisionSample
from .prompts import (
    PATTERN_DISCOVERY_SYSTEM,
    EXCLUSION_MINING_SYSTEM,
    VOCABULARY_DISCOVERY_SYSTEM,
    DIFFERENTIATOR_SYSTEM,
    TIER_ASSIGNMENT_SYSTEM,
    build_pattern_discovery_prompt,
    build_exclusion_mining_prompt,
    build_vocabulary_discovery_prompt,
    build_differentiator_prompt,
    build_tier_assignment_prompt,
)


logger = logging.getLogger(__name__)


# =============================================================================
# QUALITY TIER FILTERING
# =============================================================================

def _filter_records_by_quality(
    records: pd.DataFrame,
    mode: str = "vocab",
    max_records: int = 40,
) -> pd.DataFrame:
    """
    Filter records by quality tier for different LLM phases.

    Modes:
        - "vocab": Skew toward lower quality (tiers 3-5 preferred, then 2, minimize 1)
        - "differentiator": Exclude tier 1, limit tier 2 to ~20% of sample

    Args:
        records: DataFrame with raw_text and quality_tier columns
        mode: Filtering mode ("vocab" or "differentiator")
        max_records: Maximum records to return

    Returns:
        Filtered DataFrame
    """
    if records is None or records.empty:
        return records

    if "quality_tier" not in records.columns:
        logger.warning("quality_tier column not found, returning unfiltered records")
        return records.head(max_records)

    if mode == "vocab":
        # Vocabulary discovery: prefer degraded/fragmentary records
        # Priority: tiers 5, 4, 3, then 2 if needed, minimize tier 1
        tier_priority = [5, 4, 3, 2, 1]
        result_records = []
        remaining = max_records

        for tier in tier_priority:
            tier_records = records[records["quality_tier"] == tier]
            if not tier_records.empty and remaining > 0:
                take = min(len(tier_records), remaining)
                result_records.append(tier_records.head(take))
                remaining -= take

        if result_records:
            return pd.concat(result_records, ignore_index=True)
        return records.head(max_records)

    elif mode == "differentiator":
        # Differentiator/pattern discovery: exclude tier 1, limit tier 2
        # No tier 1, tier 2 limited to ~20% of sample
        # Priority order: tier 5, 4, 3, then limited tier 2
        tier_2_limit = max(1, int(max_records * 0.20))

        result_records = []
        remaining = max_records

        # First take from tiers 5, 4, 3 in priority order
        for tier in [5, 4, 3]:
            tier_records = records[records["quality_tier"] == tier]
            if not tier_records.empty and remaining > 0:
                take = min(len(tier_records), remaining)
                result_records.append(tier_records.head(take))
                remaining -= take

        # Then add limited tier 2 if we still have room
        if remaining > 0:
            tier_2_take = min(remaining, tier_2_limit)
            tier_2 = records[records["quality_tier"] == 2].head(tier_2_take)
            if not tier_2.empty:
                result_records.append(tier_2)

        if result_records:
            return pd.concat(result_records, ignore_index=True)

        # Fallback: use tier 2 if no tier 3-5 available
        logger.warning("No tier 3-5 records found for differentiator, using tier 2 only")
        return records[records["quality_tier"] == 2].head(max_records)

    else:
        logger.warning(f"Unknown quality filter mode: {mode}, returning unfiltered")
        return records.head(max_records)


# =============================================================================
# DATA CLASSES FOR PHASE RESULTS
# =============================================================================

@dataclass
class PatternResult:
    """Result of pattern discovery phase."""
    status: str  # "complete", "limited", "not_generated"
    patterns: List[Dict[str, Any]] = field(default_factory=list)
    observations: str = ""
    input_tokens: int = 0
    output_tokens: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "entries": {p["pattern"]: {
                "means": p.get("means", ""),
                "tier": p.get("tier", "tentative"),
                "note": p.get("note")
            } for p in self.patterns}
        }


@dataclass
class ExclusionResult:
    """Result of exclusion mining phase."""
    structural: List[Dict[str, str]] = field(default_factory=list)
    value_based: List[Dict[str, str]] = field(default_factory=list)
    structural_status: str = "complete"
    value_based_status: str = "complete"
    observations: str = ""
    input_tokens: int = 0
    output_tokens: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "structural": {
                "status": self.structural_status,
                "rules": self.structural
            },
            "value_based": {
                "status": self.value_based_status,
                "rules": self.value_based
            }
        }


@dataclass
class VocabularyResult:
    """Result of vocabulary discovery phase."""
    status: str  # "complete", "not_generated"
    strong: List[str] = field(default_factory=list)
    moderate: List[str] = field(default_factory=list)
    weak: List[str] = field(default_factory=list)
    discovered_aliases: List[str] = field(default_factory=list)
    observations: str = ""
    input_tokens: int = 0
    output_tokens: int = 0

    def to_dict(self) -> Dict[str, Any]:
        if self.status == "not_generated":
            return {
                "status": "not_generated",
                "reason": "insufficient_sample"
            }
        return {
            "status": self.status,
            "strong": self.strong,
            "moderate": self.moderate,
            "weak": self.weak
        }


@dataclass
class DifferentiatorResult:
    """Result of differentiator generation for one rival."""
    rival_id: str
    status: str  # "complete", "rival_undersampled", "hierarchy_only"
    rival_sample_size: int = 0
    rival_tier: Optional[TierName] = None
    rules: List[str] = field(default_factory=list)
    hierarchy_rules: List[str] = field(default_factory=list)
    not_generated: List[str] = field(default_factory=list)
    notes: str = ""
    input_tokens: int = 0
    output_tokens: int = 0

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "status": self.status,
            "rival_sample_size": self.rival_sample_size,
            "rules": self.rules + self.hierarchy_rules,
        }
        if self.rival_tier:
            result["rival_tier"] = self.rival_tier
        if self.not_generated:
            result["not_generated"] = self.not_generated
        return result


@dataclass
class PhaseResults:
    """Combined results from all LLM phases for a component."""
    component_id: str
    tier: TierName
    patterns: PatternResult
    exclusions: ExclusionResult
    vocabulary: VocabularyResult
    differentiators: Dict[str, DifferentiatorResult] = field(default_factory=dict)

    @property
    def total_input_tokens(self) -> int:
        total = self.patterns.input_tokens + self.exclusions.input_tokens + self.vocabulary.input_tokens
        for d in self.differentiators.values():
            total += d.input_tokens
        return total

    @property
    def total_output_tokens(self) -> int:
        total = self.patterns.output_tokens + self.exclusions.output_tokens + self.vocabulary.output_tokens
        for d in self.differentiators.values():
            total += d.output_tokens
        return total


# =============================================================================
# LLM PHASE FUNCTIONS
# =============================================================================

def discover_patterns(
    component_id: str,
    component_name: str,
    component_samples: ComponentSamples,
    all_structures: Dict[str, ComponentStructure],
    llm: BaseLLMProvider,
    tier: TierName,
) -> PatternResult:
    """
    Phase 4: Discover text patterns that identify the component.

    Args:
        component_id: Target component ID
        component_name: Canonical component name
        component_samples: Collision samples for this component
        all_structures: All component structures
        llm: LLM provider
        tier: Component tier

    Returns:
        PatternResult with discovered patterns
    """
    if not tier_allows_patterns(tier):
        logger.info(f"Skipping pattern discovery for {component_id} (tier: {tier})")
        return PatternResult(status="not_generated")

    if not component_samples.rival_samples:
        logger.warning(f"No rival samples for {component_id}, limited pattern discovery")
        return PatternResult(status="limited", observations="No collision rivals found")

    all_patterns: List[Dict[str, Any]] = []
    total_input = 0
    total_output = 0
    observations = []

    # Discover patterns against each rival
    for rival_id, collision_sample in component_samples.rival_samples.items():
        rival_structure = all_structures.get(rival_id)
        if not rival_structure:
            continue

        # Filter records by quality - exclude tier 1, limit tier 2
        filtered_a = _filter_records_by_quality(
            collision_sample.records_a, mode="differentiator", max_records=20
        )
        filtered_b = _filter_records_by_quality(
            collision_sample.records_b, mode="differentiator", max_records=20
        )
        target_texts = filtered_a["raw_text"].tolist() if filtered_a is not None and not filtered_a.empty else []
        rival_texts = filtered_b["raw_text"].tolist() if filtered_b is not None and not filtered_b.empty else []

        logger.debug(
            f"Pattern discovery {component_id} vs {rival_id}: "
            f"{len(target_texts)} target texts, {len(rival_texts)} rival texts (quality-filtered)"
        )

        # Build prompt
        prompt = build_pattern_discovery_prompt(
            component_name=component_name,
            component_id=component_id,
            rival_name=rival_structure.canonical_name,
            rival_id=rival_id,
            target_texts=target_texts,
            rival_texts=rival_texts,
            collision_levels=collision_sample.collision_levels,
        )

        # Call LLM
        messages = [
            Message(role="system", content=PATTERN_DISCOVERY_SYSTEM),
            Message(role="human", content=prompt),
        ]

        try:
            response = llm.invoke(messages)
            total_input += response.input_tokens
            total_output += response.output_tokens

            # Parse response
            result = extract_json_from_text(response.content)
            if result:
                patterns = result.get("patterns", [])
                all_patterns.extend(patterns)
                if result.get("observations"):
                    observations.append(f"vs {rival_id}: {result['observations']}")

        except Exception as e:
            logger.error(f"Pattern discovery failed for {component_id} vs {rival_id}: {e}")
            observations.append(f"vs {rival_id}: error - {str(e)}")

    # Deduplicate patterns
    seen = set()
    unique_patterns = []
    for p in all_patterns:
        key = p.get("pattern", "").lower()
        if key and key not in seen:
            seen.add(key)
            unique_patterns.append(p)

    status = "complete" if unique_patterns else "limited"

    return PatternResult(
        status=status,
        patterns=unique_patterns,
        observations="; ".join(observations),
        input_tokens=total_input,
        output_tokens=total_output,
    )


def mine_exclusions(
    component_id: str,
    component_name: str,
    structure: ComponentStructure,
    all_structures: Dict[str, ComponentStructure],
    component_samples: ComponentSamples,
    llm: BaseLLMProvider,
    tier: TierName,
) -> ExclusionResult:
    """
    Phase 5: Mine exclusion rules.

    Structural exclusions are always generated (from hierarchy).
    Value-based exclusions require sufficient data.

    Args:
        component_id: Target component ID
        component_name: Canonical component name
        structure: Target component structure
        all_structures: All component structures
        component_samples: Component samples
        llm: LLM provider
        tier: Component tier

    Returns:
        ExclusionResult with both structural and value-based exclusions
    """
    # Structural exclusions (always generated)
    structural = get_structural_exclusions(component_id, structure, all_structures)

    # Value-based exclusions (requires data)
    value_based = []
    value_status = "complete"
    total_input = 0
    total_output = 0
    observations = ""

    if not tier_allows_value_exclusions(tier):
        value_status = "not_generated"
    else:
        # Get invalid designators
        invalid = get_invalid_designators(component_id, structure, all_structures)

        # Get sample texts - exclude tier 1, limit tier 2
        texts = []
        if component_samples.all_records is not None:
            filtered = _filter_records_by_quality(
                component_samples.all_records, mode="differentiator", max_records=30
            )
            texts = filtered["raw_text"].tolist()
            logger.debug(f"Exclusion mining using {len(texts)} records (quality-filtered)")

        if texts:
            prompt = build_exclusion_mining_prompt(
                component_name=component_name,
                component_id=component_id,
                component_structure=structure.to_dict(),
                all_texts=texts,
                invalid_designators=invalid,
            )

            messages = [
                Message(role="system", content=EXCLUSION_MINING_SYSTEM),
                Message(role="human", content=prompt),
            ]

            try:
                response = llm.invoke(messages)
                total_input = response.input_tokens
                total_output = response.output_tokens

                result = extract_json_from_text(response.content)
                if result:
                    value_based = result.get("value_based_exclusions", [])
                    observations = result.get("observations", "")

            except Exception as e:
                logger.error(f"Exclusion mining failed for {component_id}: {e}")
                value_status = "limited"
                observations = f"Error: {str(e)}"

    return ExclusionResult(
        structural=structural,
        value_based=value_based,
        structural_status="complete",
        value_based_status=value_status,
        observations=observations,
        input_tokens=total_input,
        output_tokens=total_output,
    )


def discover_vocabulary(
    component_id: str,
    component_name: str,
    structure: ComponentStructure,
    component_samples: ComponentSamples,
    llm: BaseLLMProvider,
    tier: TierName,
) -> VocabularyResult:
    """
    Phase 6: Discover characteristic vocabulary.

    Args:
        component_id: Target component ID
        component_name: Canonical component name
        structure: Component structure (for aliases)
        component_samples: Component samples
        llm: LLM provider
        tier: Component tier

    Returns:
        VocabularyResult with vocabulary tiers
    """
    if not tier_allows_vocabulary(tier):
        logger.info(f"Skipping vocabulary discovery for {component_id} (tier: {tier})")
        return VocabularyResult(status="not_generated")

    # Get sample texts - prefer lower quality records for vocab discovery
    texts = []
    if component_samples.all_records is not None:
        filtered = _filter_records_by_quality(
            component_samples.all_records, mode="vocab", max_records=40
        )
        texts = filtered["raw_text"].tolist()
        logger.debug(f"Vocabulary discovery using {len(texts)} records (quality-filtered)")

    if not texts:
        return VocabularyResult(status="not_generated")

    prompt = build_vocabulary_discovery_prompt(
        component_name=component_name,
        component_id=component_id,
        aliases=structure.aliases,
        texts=texts,
    )

    messages = [
        Message(role="system", content=VOCABULARY_DISCOVERY_SYSTEM),
        Message(role="human", content=prompt),
    ]

    try:
        response = llm.invoke(messages)

        result = extract_json_from_text(response.content)
        if result:
            vocab = result.get("vocabulary", {})
            return VocabularyResult(
                status="complete",
                strong=vocab.get("strong", []),
                moderate=vocab.get("moderate", []),
                weak=vocab.get("weak", []),
                discovered_aliases=result.get("discovered_aliases", []),
                observations=result.get("observations", ""),
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
            )

    except Exception as e:
        logger.error(f"Vocabulary discovery failed for {component_id}: {e}")

    return VocabularyResult(status="limited")


def generate_differentiators(
    component_id: str,
    component_name: str,
    component_samples: ComponentSamples,
    all_structures: Dict[str, ComponentStructure],
    patterns: PatternResult,
    exclusions: ExclusionResult,
    vocabulary: VocabularyResult,
    all_patterns: Dict[str, PatternResult],
    llm: BaseLLMProvider,
    tier: TierName,
    rival_tiers: Dict[str, TierName],
) -> Dict[str, DifferentiatorResult]:
    """
    Phase 7: Generate rival-specific disambiguation rules.

    Args:
        component_id: Target component ID
        component_name: Canonical component name
        component_samples: Component samples
        all_structures: All component structures
        patterns: Pattern discovery result for this component
        exclusions: Exclusion result for this component
        vocabulary: Vocabulary result for this component
        all_patterns: Pattern results for all components (for rival patterns)
        llm: LLM provider
        tier: Component tier
        rival_tiers: Tiers for rival components

    Returns:
        Dict mapping rival_id -> DifferentiatorResult
    """
    results: Dict[str, DifferentiatorResult] = {}

    for rival_id, collision_sample in component_samples.rival_samples.items():
        rival_structure = all_structures.get(rival_id)
        if not rival_structure:
            continue

        rival_tier = rival_tiers.get(rival_id, "sparse")

        # Determine generation mode
        if tier == "sparse":
            # Sparse component: hierarchy-only
            status = "hierarchy_only"
            rules = []
            hierarchy_rules = _generate_hierarchy_rules(
                component_id, component_name,
                rival_id, rival_structure.canonical_name,
                all_structures
            )
            not_generated = ["vocabulary-based differentiators", "pattern-based rules"]

            results[rival_id] = DifferentiatorResult(
                rival_id=rival_id,
                status=status,
                rival_sample_size=len(collision_sample.soldiers_b),
                rival_tier=rival_tier,
                rules=rules,
                hierarchy_rules=hierarchy_rules,
                not_generated=not_generated,
            )
            continue

        if collision_sample.undersampled_b or rival_tier == "sparse":
            # Undersampled rival: limited differentiators
            status = "rival_undersampled"
            hierarchy_rules = _generate_hierarchy_rules(
                component_id, component_name,
                rival_id, rival_structure.canonical_name,
                all_structures
            )

            results[rival_id] = DifferentiatorResult(
                rival_id=rival_id,
                status=status,
                rival_sample_size=len(collision_sample.soldiers_b),
                rival_tier=rival_tier,
                rules=[],
                hierarchy_rules=hierarchy_rules,
                not_generated=["vocabulary-based differentiators"],
            )
            continue

        # Full differentiator generation
        rival_patterns_result = all_patterns.get(rival_id)
        rival_pattern_list = rival_patterns_result.patterns if rival_patterns_result else []

        vocab_dict = {
            "strong": vocabulary.strong,
            "moderate": vocabulary.moderate,
            "weak": vocabulary.weak,
        }

        prompt = build_differentiator_prompt(
            component_name=component_name,
            component_id=component_id,
            rival_name=rival_structure.canonical_name,
            rival_id=rival_id,
            collision_levels=collision_sample.collision_levels,
            component_patterns=patterns.patterns,
            rival_patterns=rival_pattern_list,
            component_exclusions=exclusions.value_based,
            component_vocabulary=vocab_dict,
        )

        messages = [
            Message(role="system", content=DIFFERENTIATOR_SYSTEM),
            Message(role="human", content=prompt),
        ]

        try:
            response = llm.invoke(messages)

            result = extract_json_from_text(response.content)
            if result:
                results[rival_id] = DifferentiatorResult(
                    rival_id=rival_id,
                    status=result.get("confidence", "complete"),
                    rival_sample_size=len(collision_sample.soldiers_b),
                    rival_tier=rival_tier,
                    rules=result.get("rules", []),
                    hierarchy_rules=result.get("hierarchy_rules", []),
                    notes=result.get("notes", ""),
                    input_tokens=response.input_tokens,
                    output_tokens=response.output_tokens,
                )
            else:
                # Fallback to hierarchy only
                results[rival_id] = DifferentiatorResult(
                    rival_id=rival_id,
                    status="hierarchy_only",
                    rival_sample_size=len(collision_sample.soldiers_b),
                    hierarchy_rules=_generate_hierarchy_rules(
                        component_id, component_name,
                        rival_id, rival_structure.canonical_name,
                        all_structures
                    ),
                )

        except Exception as e:
            logger.error(f"Differentiator generation failed for {component_id} vs {rival_id}: {e}")
            results[rival_id] = DifferentiatorResult(
                rival_id=rival_id,
                status="hierarchy_only",
                rival_sample_size=len(collision_sample.soldiers_b),
                hierarchy_rules=_generate_hierarchy_rules(
                    component_id, component_name,
                    rival_id, rival_structure.canonical_name,
                    all_structures
                ),
                notes=f"Error: {str(e)}",
            )

    return results


def _generate_hierarchy_rules(
    comp_a_id: str,
    comp_a_name: str,
    comp_b_id: str,
    comp_b_name: str,
    all_structures: Dict[str, ComponentStructure],
) -> List[str]:
    """Generate hierarchy-based disambiguation rules."""
    rules = []

    struct_a = all_structures.get(comp_a_id)
    struct_b = all_structures.get(comp_b_id)

    if not struct_a or not struct_b:
        return rules

    # Regiment-based rules
    regs_a = set(struct_a.valid_regiments)
    regs_b = set(struct_b.valid_regiments)

    unique_to_a = regs_a - regs_b
    unique_to_b = regs_b - regs_a

    if unique_to_a:
        regs = sorted(unique_to_a)
        rules.append(f"Regiment {' or '.join(regs)} -> {comp_a_name}")

    if unique_to_b:
        regs = sorted(unique_to_b)
        rules.append(f"Regiment {' or '.join(regs)} -> {comp_b_name}")

    # Service branch rules
    if struct_a.service_branch != struct_b.service_branch:
        if struct_a.service_branch == "marines":
            rules.append(f"Marine/USMC context -> {comp_a_name}")
        elif struct_b.service_branch == "marines":
            rules.append(f"Marine/USMC context -> {comp_b_name}")

        if "airborne" in comp_a_id:
            rules.append(f"Airborne/PIR context -> {comp_a_name}")
        elif "airborne" in comp_b_id:
            rules.append(f"Airborne/PIR context -> {comp_b_name}")

    return rules


def assign_pattern_tiers(
    patterns: PatternResult,
    validation_texts: List[str],
    llm: BaseLLMProvider,
    component_name: str,
) -> PatternResult:
    """
    Phase 8: Assign confidence tiers to patterns based on validation.

    Args:
        patterns: Pattern discovery result
        validation_texts: Sample texts for validation
        llm: LLM provider
        component_name: Component name

    Returns:
        Updated PatternResult with validated tiers
    """
    if patterns.status == "not_generated" or not patterns.patterns:
        return patterns

    if not validation_texts:
        return patterns

    prompt = build_tier_assignment_prompt(
        component_name=component_name,
        patterns=patterns.patterns,
        validation_texts=validation_texts,
    )

    messages = [
        Message(role="system", content=TIER_ASSIGNMENT_SYSTEM),
        Message(role="human", content=prompt),
    ]

    try:
        response = llm.invoke(messages)

        result = extract_json_from_text(response.content)
        if result and "validated_patterns" in result:
            # Update pattern tiers
            validated = {p["pattern"]: p for p in result["validated_patterns"]}

            for pattern in patterns.patterns:
                if pattern["pattern"] in validated:
                    pattern["tier"] = validated[pattern["pattern"]].get("tier", pattern.get("tier", "tentative"))

            patterns.input_tokens += response.input_tokens
            patterns.output_tokens += response.output_tokens

    except Exception as e:
        logger.error(f"Tier assignment failed: {e}")

    return patterns


# =============================================================================
# MAIN ORCHESTRATION
# =============================================================================

def run_all_phases(
    component_id: str,
    component_samples: ComponentSamples,
    all_structures: Dict[str, ComponentStructure],
    all_samples: Dict[str, ComponentSamples],
    llm: BaseLLMProvider,
    tier: TierName,
    thresholds_result: Any,
) -> PhaseResults:
    """
    Run all LLM phases for a single component.

    Args:
        component_id: Target component ID
        component_samples: Samples for this component
        all_structures: All component structures
        all_samples: All component samples (for rival patterns)
        llm: LLM provider
        tier: Component tier
        thresholds_result: Threshold result for tier lookups

    Returns:
        PhaseResults with all phase outputs
    """
    structure = all_structures.get(component_id)
    if not structure:
        raise ValueError(f"No structure found for {component_id}")

    component_name = structure.canonical_name

    logger.info(f"Running LLM phases for {component_id} (tier: {tier})")

    # Phase 4: Pattern Discovery
    logger.info(f"  Phase 4: Pattern Discovery")
    patterns = discover_patterns(
        component_id=component_id,
        component_name=component_name,
        component_samples=component_samples,
        all_structures=all_structures,
        llm=llm,
        tier=tier,
    )

    # Phase 5: Exclusion Mining
    logger.info(f"  Phase 5: Exclusion Mining")
    exclusions = mine_exclusions(
        component_id=component_id,
        component_name=component_name,
        structure=structure,
        all_structures=all_structures,
        component_samples=component_samples,
        llm=llm,
        tier=tier,
    )

    # Phase 6: Vocabulary Discovery
    logger.info(f"  Phase 6: Vocabulary Discovery")
    vocabulary = discover_vocabulary(
        component_id=component_id,
        component_name=component_name,
        structure=structure,
        component_samples=component_samples,
        llm=llm,
        tier=tier,
    )

    # Get rival tiers
    rival_tiers = {
        rival_id: thresholds_result.get_tier(rival_id)
        for rival_id in component_samples.rival_samples.keys()
    }

    # Collect patterns from all components for differentiator generation
    all_patterns: Dict[str, PatternResult] = {}
    # Note: In full implementation, this would be populated as components are processed
    # For now, we only have the current component's patterns

    # Phase 7: Differentiator Generation
    logger.info(f"  Phase 7: Differentiator Generation")
    differentiators = generate_differentiators(
        component_id=component_id,
        component_name=component_name,
        component_samples=component_samples,
        all_structures=all_structures,
        patterns=patterns,
        exclusions=exclusions,
        vocabulary=vocabulary,
        all_patterns=all_patterns,
        llm=llm,
        tier=tier,
        rival_tiers=rival_tiers,
    )

    # Phase 8: Tier Assignment
    if patterns.status != "not_generated" and component_samples.all_records is not None:
        logger.info(f"  Phase 8: Tier Assignment")
        validation_texts = component_samples.all_records["raw_text"].tolist()[:20]
        patterns = assign_pattern_tiers(patterns, validation_texts, llm, component_name)

    return PhaseResults(
        component_id=component_id,
        tier=tier,
        patterns=patterns,
        exclusions=exclusions,
        vocabulary=vocabulary,
        differentiators=differentiators,
    )
