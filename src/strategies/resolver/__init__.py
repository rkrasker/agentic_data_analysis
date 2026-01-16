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

from .executor.strategy import ResolverStrategy
from .generator import (
    generate_all_resolvers,
    generate_single_component,
    GenerationSummary,
    ThresholdResult,
    compute_thresholds,
)

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
