"""
Resolver Strategy Executor

Implements ResolverStrategy(BaseStrategy) to apply resolver heuristics
at consolidation time. Uses pre-generated resolver artifacts to guide
LLM-based record consolidation.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any

from src.strategies.base_strategy import (
    BaseStrategy,
    SoldierBatch,
    SoldierRecords,
    ConsolidationResult,
    UnitAssignment,
    ConfidenceTier,
)
from src.utils.llm import create_provider, Message, BaseLLMProvider


logger = logging.getLogger(__name__)


# =============================================================================
# CONSOLIDATION PROMPTS
# =============================================================================

CONSOLIDATION_SYSTEM_PROMPT = """You are an expert at parsing historical military records to determine unit assignments. You will analyze records for multiple soldiers and determine their military unit assignments.

You have access to:
1. Raw text records for each soldier
2. Component hierarchy defining valid unit designators
3. Resolver heuristics with patterns, vocabulary, and disambiguation rules

Use all available information to make accurate assignments. When records are ambiguous, use the resolver patterns and differentiators to disambiguate."""


def build_consolidation_prompt(
    batch: SoldierBatch,
    resolver: Dict[str, Any],
    hierarchy: Dict[str, Any],
) -> str:
    """
    Build the consolidation prompt for a batch of soldiers.

    Args:
        batch: Soldier batch to consolidate
        resolver: Resolver heuristics for the component
        hierarchy: Component hierarchy

    Returns:
        Formatted prompt string
    """
    component_id = batch.component_hint or resolver.get("meta", {}).get("component_id", "unknown")
    component_name = hierarchy.get("canonical_name", component_id)

    # Build resolver context
    resolver_context = _format_resolver_context(resolver)

    # Build soldier records section
    soldiers_section = _format_soldiers_section(batch.soldiers)

    # Build structure reference
    structure_ref = _format_structure_reference(resolver.get("structure", {}))

    return f"""Analyze records for {len(batch.soldiers)} soldiers and determine their unit assignments within {component_name}.

COMPONENT STRUCTURE:
{structure_ref}

RESOLVER HEURISTICS:
{resolver_context}

SOLDIER RECORDS:
{soldiers_section}

TASK:
For each soldier, determine:
1. Regiment (if determinable)
2. Battalion (if determinable)
3. Company (if determinable)
4. Confidence level (robust/strong/moderate/tentative)
5. Brief reasoning

Respond in JSON format:
{{
  "assignments": [
    {{
      "soldier_id": "soldier ID",
      "regiment": number or null,
      "battalion": number/string or null,
      "company": "letter" or null,
      "confidence": "robust|strong|moderate|tentative",
      "reasoning": "brief explanation",
      "supporting_signals": ["signal1", "signal2"],
      "conflicting_signals": ["signal1"] or []
    }}
  ]
}}"""


def _format_resolver_context(resolver: Dict[str, Any]) -> str:
    """Format resolver heuristics for prompt context."""
    sections = []

    # Patterns
    patterns = resolver.get("patterns", {})
    if patterns.get("status") == "complete" and patterns.get("entries"):
        pattern_lines = []
        for pattern, info in list(patterns["entries"].items())[:10]:
            tier = info.get("tier", "tentative")
            means = info.get("means", "")
            pattern_lines.append(f"  - '{pattern}' [{tier}]: {means}")
        sections.append("PATTERNS:\n" + "\n".join(pattern_lines))

    # Vocabulary
    vocabulary = resolver.get("vocabulary", {})
    if vocabulary.get("status") == "complete":
        vocab_parts = []
        if vocabulary.get("strong"):
            vocab_parts.append(f"  Strong indicators: {vocabulary['strong'][:5]}")
        if vocabulary.get("moderate"):
            vocab_parts.append(f"  Moderate indicators: {vocabulary['moderate'][:5]}")
        if vocab_parts:
            sections.append("VOCABULARY:\n" + "\n".join(vocab_parts))

    # Exclusions
    exclusions = resolver.get("exclusions", {})
    structural = exclusions.get("structural", {})
    if structural.get("rules"):
        excl_lines = []
        for rule in structural["rules"][:5]:
            if isinstance(rule, dict):
                excl_lines.append(f"  - If {rule.get('if', '')}, then {rule.get('then', '')}")
            else:
                excl_lines.append(f"  - {rule}")
        sections.append("EXCLUSION RULES:\n" + "\n".join(excl_lines))

    # Key differentiators (if any rivals)
    differentiators = resolver.get("differentiators", {})
    if differentiators and not differentiators.get("note"):
        diff_lines = []
        for rival_key, diff_info in list(differentiators.items())[:3]:
            if isinstance(diff_info, dict) and diff_info.get("rules"):
                rival_name = rival_key.replace("vs_", "")
                rules = diff_info["rules"][:3]
                diff_lines.append(f"  vs {rival_name}:")
                for rule in rules:
                    diff_lines.append(f"    - {rule}")
        if diff_lines:
            sections.append("DISAMBIGUATION RULES:\n" + "\n".join(diff_lines))

    if not sections:
        return "No resolver heuristics available - use hierarchy structure only."

    return "\n\n".join(sections)


def _format_soldiers_section(soldiers: List[SoldierRecords]) -> str:
    """Format soldier records for prompt."""
    sections = []

    for soldier in soldiers:
        records_text = "\n".join(f"    - {text}" for text in soldier.raw_texts[:5])
        if len(soldier.raw_texts) > 5:
            records_text += f"\n    ... and {len(soldier.raw_texts) - 5} more records"

        sections.append(f"""
Soldier ID: {soldier.soldier_id}
Records ({soldier.record_count} total):
{records_text}
""")

    return "\n".join(sections)


def _format_structure_reference(structure: Dict[str, Any]) -> str:
    """Format structure for quick reference."""
    lines = []

    if structure.get("valid_regiments"):
        lines.append(f"Valid regiments: {structure['valid_regiments']}")

    if structure.get("valid_battalions"):
        lines.append(f"Valid battalions: {structure['valid_battalions']}")

    if structure.get("valid_companies"):
        lines.append(f"Valid companies: {structure['valid_companies']}")

    if structure.get("valid_combat_commands"):
        lines.append(f"Valid combat commands: {structure['valid_combat_commands']}")

    if structure.get("valid_bomb_groups"):
        lines.append(f"Valid bomb groups: {structure['valid_bomb_groups']}")

    return "\n".join(lines) if lines else "See hierarchy reference"


# =============================================================================
# RESOLVER STRATEGY
# =============================================================================

class ResolverStrategy(BaseStrategy):
    """
    Consolidation strategy using pre-generated resolver heuristics.

    Applies resolver artifacts (patterns, vocabulary, exclusions, differentiators)
    to guide LLM-based consolidation of soldier records.
    """

    def __init__(
        self,
        resolver_dir: Path,
        hierarchy_path: Path,
        model_name: str = "gemini-2.5-pro",
        llm_client: Optional[BaseLLMProvider] = None,
        **kwargs,
    ):
        """
        Initialize resolver strategy.

        Args:
            resolver_dir: Directory containing resolver JSON files
            hierarchy_path: Path to hierarchy_reference.json
            model_name: LLM model to use
            llm_client: Optional pre-configured LLM client
            **kwargs: Additional configuration
        """
        super().__init__(strategy_name="resolver", **kwargs)

        self.resolver_dir = Path(resolver_dir)
        self.hierarchy_path = Path(hierarchy_path)
        self.model_name = model_name

        # Load hierarchy
        with open(hierarchy_path) as f:
            self._hierarchy = json.load(f)

        # Cache for loaded resolvers
        self._resolver_cache: Dict[str, Dict] = {}

        # LLM client (lazy initialization)
        self._llm = llm_client

    @property
    def llm(self) -> BaseLLMProvider:
        """Get or create LLM client."""
        if self._llm is None:
            self._llm = create_provider(self.model_name, temperature=0.0)
        return self._llm

    def _load_resolver(self, component_id: str) -> Optional[Dict[str, Any]]:
        """Load resolver for a component, with caching."""
        if component_id in self._resolver_cache:
            return self._resolver_cache[component_id]

        resolver_path = self.resolver_dir / f"{component_id}_resolver.json"
        if not resolver_path.exists():
            logger.warning(f"No resolver found for {component_id}")
            return None

        with open(resolver_path) as f:
            resolver = json.load(f)

        self._resolver_cache[component_id] = resolver
        return resolver

    def _get_hierarchy(self, component_id: str) -> Dict[str, Any]:
        """Get hierarchy for a component."""
        components = self._hierarchy.get("components", {})
        return components.get(component_id, {})

    def consolidate(self, batch: SoldierBatch) -> ConsolidationResult:
        """
        Consolidate records for a batch of soldiers using resolver heuristics.

        Args:
            batch: SoldierBatch with records to consolidate

        Returns:
            ConsolidationResult with per-soldier assignments
        """
        component_id = batch.component_hint
        if not component_id:
            return self._consolidate_without_resolver(batch)

        # Load resolver
        resolver = self._load_resolver(component_id)
        if not resolver:
            logger.warning(f"No resolver for {component_id}, falling back to hierarchy-only")
            return self._consolidate_without_resolver(batch)

        # Get hierarchy
        hierarchy = self._get_hierarchy(component_id)

        # Build prompt
        prompt = build_consolidation_prompt(batch, resolver, hierarchy)

        # Call LLM
        messages = [
            Message(role="system", content=CONSOLIDATION_SYSTEM_PROMPT),
            Message(role="human", content=prompt),
        ]

        try:
            response = self.llm.invoke(messages)

            # Parse response
            from src.utils.llm.structured import extract_json_from_text
            result = extract_json_from_text(response.content)

            if result and "assignments" in result:
                return self._parse_assignments(
                    batch=batch,
                    component_id=component_id,
                    assignments_data=result["assignments"],
                    response=response,
                )

        except Exception as e:
            logger.error(f"Consolidation failed for batch {batch.batch_id}: {e}")
            return self._create_error_result(batch, str(e))

        # Fallback: create tentative assignments
        return self._create_fallback_result(batch, component_id)

    def _consolidate_without_resolver(self, batch: SoldierBatch) -> ConsolidationResult:
        """Consolidate without resolver (hierarchy only)."""
        # Simplified consolidation using just hierarchy
        assignments = {}

        for soldier in batch.soldiers:
            assignments[soldier.soldier_id] = UnitAssignment(
                component_id=batch.component_hint or "unknown",
                confidence=ConfidenceTier.TENTATIVE,
                reasoning="No resolver available - hierarchy-only assignment",
            )

        return ConsolidationResult(
            batch_id=batch.batch_id,
            assignments=assignments,
            strategy_name=self.strategy_name,
            model_name=self.model_name,
        )

    def _parse_assignments(
        self,
        batch: SoldierBatch,
        component_id: str,
        assignments_data: List[Dict],
        response: Any,
    ) -> ConsolidationResult:
        """Parse LLM response into ConsolidationResult."""
        assignments = {}
        errors = {}

        # Index assignments by soldier_id
        assignment_map = {a.get("soldier_id"): a for a in assignments_data}

        for soldier in batch.soldiers:
            assignment_data = assignment_map.get(soldier.soldier_id)

            if not assignment_data:
                errors[soldier.soldier_id] = "No assignment in LLM response"
                assignments[soldier.soldier_id] = UnitAssignment(
                    component_id=component_id,
                    confidence=ConfidenceTier.TENTATIVE,
                    reasoning="Missing from LLM response",
                )
                continue

            # Parse confidence
            confidence_str = assignment_data.get("confidence", "tentative")
            try:
                confidence = ConfidenceTier(confidence_str)
            except ValueError:
                confidence = ConfidenceTier.TENTATIVE

            assignments[soldier.soldier_id] = UnitAssignment(
                component_id=component_id,
                regiment=assignment_data.get("regiment"),
                battalion=assignment_data.get("battalion"),
                company=assignment_data.get("company"),
                confidence=confidence,
                reasoning=assignment_data.get("reasoning"),
                supporting_signals=assignment_data.get("supporting_signals", []),
                conflicting_signals=assignment_data.get("conflicting_signals", []),
            )

        return ConsolidationResult(
            batch_id=batch.batch_id,
            assignments=assignments,
            strategy_name=self.strategy_name,
            model_name=self.model_name,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            cost_usd=self.llm.estimate_cost(response.input_tokens, response.output_tokens),
            errors=errors,
        )

    def _create_error_result(self, batch: SoldierBatch, error_msg: str) -> ConsolidationResult:
        """Create result for failed consolidation."""
        assignments = {}
        errors = {}

        for soldier in batch.soldiers:
            assignments[soldier.soldier_id] = UnitAssignment(
                component_id=batch.component_hint or "unknown",
                confidence=ConfidenceTier.TENTATIVE,
                reasoning=f"Error: {error_msg}",
            )
            errors[soldier.soldier_id] = error_msg

        return ConsolidationResult(
            batch_id=batch.batch_id,
            assignments=assignments,
            strategy_name=self.strategy_name,
            errors=errors,
        )

    def _create_fallback_result(self, batch: SoldierBatch, component_id: str) -> ConsolidationResult:
        """Create fallback result when LLM response parsing fails."""
        assignments = {}

        for soldier in batch.soldiers:
            assignments[soldier.soldier_id] = UnitAssignment(
                component_id=component_id,
                confidence=ConfidenceTier.TENTATIVE,
                reasoning="LLM response could not be parsed",
            )

        return ConsolidationResult(
            batch_id=batch.batch_id,
            assignments=assignments,
            strategy_name=self.strategy_name,
            model_name=self.model_name,
            warnings={s.soldier_id: ["LLM response parsing failed"] for s in batch.soldiers},
        )

    def get_resolver_info(self, component_id: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a component's resolver.

        Args:
            component_id: Component to query

        Returns:
            Resolver metadata or None if not found
        """
        resolver = self._load_resolver(component_id)
        if not resolver:
            return None

        meta = resolver.get("meta", {})
        return {
            "component_id": component_id,
            "tier": meta.get("tier"),
            "sample_size": meta.get("sample_size"),
            "generation_mode": meta.get("generation_mode"),
            "generated_utc": meta.get("generated_utc"),
        }

    def list_available_resolvers(self) -> List[str]:
        """List all available resolver component IDs."""
        if not self.resolver_dir.exists():
            return []

        resolvers = []
        for path in self.resolver_dir.glob("*_resolver.json"):
            component_id = path.stem.replace("_resolver", "")
            resolvers.append(component_id)

        return sorted(resolvers)
