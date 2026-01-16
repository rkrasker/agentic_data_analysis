"""
Batching manager for consolidation.

Groups soldiers by component for focused LLM context.
"""

from .batch_manager import (
    BatchManager,
    BatchConfig,
    create_batches,
)

__all__ = [
    "BatchManager",
    "BatchConfig",
    "create_batches",
]
