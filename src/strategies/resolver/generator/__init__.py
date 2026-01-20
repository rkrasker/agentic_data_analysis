"""
Resolver Generator Module

Generates resolver heuristics from validation data.

Uses lazy imports to avoid loading heavy dependencies (LangChain, LLMs)
until actually needed. Lightweight modules (thresholds, structure, etc.)
are imported eagerly for fast access.
"""

# Lightweight modules - imported eagerly (no LLM dependencies)
from .thresholds import (
    ThresholdResult,
    TierName,
    compute_thresholds,
    tier_allows_patterns,
    tier_allows_vocabulary,
    tier_allows_value_exclusions,
    get_generation_mode,
)
from .structure import (
    ComponentStructure,
    StructureResult,
    extract_structure,
    get_structural_exclusions,
    get_invalid_designators,
)
from .sampling import (
    CollisionSample,
    ComponentSamples,
    sample_collisions,
    sample_for_vocabulary,
)
from .registry import (
    RegistryEntry,
    ResolverRegistry,
    RegistryManager,
    create_entry_for_tier,
    get_recommendations_for_tier,
    get_warnings_for_tier,
)
from .assembler import (
    assemble_resolver,
    save_resolver,
    load_resolver,
    get_resolver_path,
    validate_resolver,
)

# Lazy imports for heavy modules (import LangChain/LLMs)
# These are only loaded when accessed
def __getattr__(name):
    """Lazy import for LLM-dependent modules to speed up basic imports."""
    # LLM phases
    if name in ("PatternResult", "ExclusionResult", "VocabularyResult",
                "DifferentiatorResult", "PhaseResults", "run_all_phases",
                "discover_patterns", "mine_exclusions", "discover_vocabulary",
                "generate_differentiators"):
        from . import llm_phases
        return getattr(llm_phases, name)

    # Main generation functions
    if name in ("GenerationSummary", "generate_all_resolvers", "generate_single_component"):
        from . import generate
        return getattr(generate, name)

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    # Thresholds
    "ThresholdResult",
    "TierName",
    "compute_thresholds",
    "tier_allows_patterns",
    "tier_allows_vocabulary",
    "tier_allows_value_exclusions",
    "get_generation_mode",
    # Structure
    "ComponentStructure",
    "StructureResult",
    "extract_structure",
    "get_structural_exclusions",
    "get_invalid_designators",
    # Sampling
    "CollisionSample",
    "ComponentSamples",
    "sample_collisions",
    "sample_for_vocabulary",
    # Registry
    "RegistryEntry",
    "ResolverRegistry",
    "RegistryManager",
    "create_entry_for_tier",
    "get_recommendations_for_tier",
    "get_warnings_for_tier",
    # LLM Phases
    "PatternResult",
    "ExclusionResult",
    "VocabularyResult",
    "DifferentiatorResult",
    "PhaseResults",
    "run_all_phases",
    "discover_patterns",
    "mine_exclusions",
    "discover_vocabulary",
    "generate_differentiators",
    # Assembler
    "assemble_resolver",
    "save_resolver",
    "load_resolver",
    "get_resolver_path",
    "validate_resolver",
    # Main
    "GenerationSummary",
    "generate_all_resolvers",
    "generate_single_component",
]
