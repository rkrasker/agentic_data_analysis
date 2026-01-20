"""
Resolver Strategy Module

Consolidation using raw text + hierarchy + pre-learned heuristics (resolvers).
Resolvers are generated from validation data to guide LLM parsing.

Usage:
    # Generate resolvers
    from src.strategies.resolver.generator import generate_all_resolvers

    summary = generate_all_resolvers(
        validation_path=Path("data/validation.parquet"),
        raw_path=Path("data/raw.parquet"),
        hierarchy_path=Path("config/hierarchies/hierarchy_reference.json"),
        output_dir=Path("config/resolvers"),
    )

    # Use resolvers for consolidation
    from src.strategies.resolver import ResolverStrategy

    strategy = ResolverStrategy(
        resolver_dir=Path("config/resolvers"),
        hierarchy_path=Path("config/hierarchies/hierarchy_reference.json"),
    )
    result = strategy.consolidate(batch)
"""

# Lazy imports to avoid loading heavy dependencies when not needed
# This allows fast imports for generator functions without loading LangChain

def __getattr__(name):
    """Lazy import to avoid loading executor (which imports LangChain) unless needed."""
    if name == "ResolverStrategy":
        from .executor.strategy import ResolverStrategy
        return ResolverStrategy
    elif name == "generate_all_resolvers":
        from .generator import generate_all_resolvers
        return generate_all_resolvers
    elif name == "generate_single_component":
        from .generator import generate_single_component
        return generate_single_component
    elif name == "GenerationSummary":
        from .generator import GenerationSummary
        return GenerationSummary
    elif name == "ThresholdResult":
        from .generator import ThresholdResult
        return ThresholdResult
    elif name == "compute_thresholds":
        from .generator import compute_thresholds
        return compute_thresholds
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    # Strategy
    "ResolverStrategy",
    # Generation
    "generate_all_resolvers",
    "generate_single_component",
    "GenerationSummary",
    "ThresholdResult",
    "compute_thresholds",
]
