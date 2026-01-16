"""
Strategy implementations for consolidation.

All strategies implement the BaseStrategy interface for plug-and-play
comparison using the same harness.
"""

from .base_strategy import (
    BaseStrategy,
    SoldierBatch,
    SoldierRecords,
    ConsolidationResult,
    UnitAssignment,
    TransferDetection,
    ConfidenceTier,
)

__all__ = [
    "BaseStrategy",
    "SoldierBatch",
    "SoldierRecords",
    "ConsolidationResult",
    "UnitAssignment",
    "TransferDetection",
    "ConfidenceTier",
]
