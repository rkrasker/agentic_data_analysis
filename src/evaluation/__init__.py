"""
Evaluation framework for consolidation strategies.

Provides train/test splitting, metrics computation, and cost tracking.
"""

from .split import (
    StratifiedSplitter,
    SplitConfig,
    TrainTestSplit,
)
from .metrics import (
    compute_metrics,
    EvaluationMetrics,
    ComponentMetrics,
)

__all__ = [
    # Splitting
    "StratifiedSplitter",
    "SplitConfig",
    "TrainTestSplit",
    # Metrics
    "compute_metrics",
    "EvaluationMetrics",
    "ComponentMetrics",
]
