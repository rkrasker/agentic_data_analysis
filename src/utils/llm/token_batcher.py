"""
Token-budget batching utility for LLM processing.

Splits datasets into LLM-sized chunks based on token count rather than
record/soldier count, ensuring consistent payload sizes and soldier coherence.

Key principles:
1. Token-based sizing: Batches fit within token budget
2. Soldier coherence: All records for a soldier stay in same batch
3. Ordering support: Forward, inverted, and custom orders for dual-run
"""

from dataclasses import dataclass, field
from typing import List, Optional, Literal, Callable
import pandas as pd


@dataclass
class SoldierTexts:
    """All texts for a single soldier."""
    soldier_id: str
    texts: List[str]
    estimated_tokens: int

    @property
    def record_count(self) -> int:
        return len(self.texts)


@dataclass
class TokenBatch:
    """A batch of soldiers sized by token budget."""
    batch_id: str
    soldiers: List[SoldierTexts]
    estimated_tokens: int

    @property
    def soldier_count(self) -> int:
        return len(self.soldiers)

    @property
    def record_count(self) -> int:
        return sum(s.record_count for s in self.soldiers)

    def get_all_texts(self) -> List[str]:
        """Get all texts for LLM prompt construction."""
        return [text for s in self.soldiers for text in s.texts]

    def get_soldier_ids(self) -> List[str]:
        """Get all soldier IDs in this batch."""
        return [s.soldier_id for s in self.soldiers]

    def get_texts_by_soldier(self) -> dict:
        """Get texts grouped by soldier ID."""
        return {s.soldier_id: s.texts for s in self.soldiers}


@dataclass
class TokenBatchConfig:
    """Configuration for token-budget batching."""
    token_budget: int = 8000
    """Max tokens per batch (sample text only, excluding prompt/response overhead)."""

    estimation_method: Literal["chars", "tiktoken"] = "chars"
    """Method for estimating token count."""

    chars_per_token: int = 4
    """Characters per token for 'chars' estimation method."""

    batch_id_prefix: str = "batch"
    """Prefix for batch IDs."""


class TokenBatcher:
    """
    Creates token-budget batches from records while maintaining soldier coherence.

    Usage:
        batcher = TokenBatcher(TokenBatchConfig(token_budget=8000))
        batches = batcher.create_batches(df, soldier_id_col="soldier_id", text_col="raw_text")
    """

    def __init__(self, config: Optional[TokenBatchConfig] = None):
        self.config = config or TokenBatchConfig()
        self._tiktoken_encoder = None

    def estimate_tokens(self, text: str) -> int:
        """
        Estimate token count for text.

        Args:
            text: Text to estimate

        Returns:
            Estimated token count
        """
        if not text:
            return 0

        if self.config.estimation_method == "chars":
            return len(text) // self.config.chars_per_token

        elif self.config.estimation_method == "tiktoken":
            if self._tiktoken_encoder is None:
                try:
                    import tiktoken
                    self._tiktoken_encoder = tiktoken.get_encoding("cl100k_base")
                except ImportError:
                    raise ImportError(
                        "tiktoken is required for accurate token estimation. "
                        "Install with: pip install tiktoken"
                    )
            return len(self._tiktoken_encoder.encode(text))

        else:
            raise ValueError(f"Unknown estimation method: {self.config.estimation_method}")

    def _group_by_soldier(
        self,
        df: pd.DataFrame,
        soldier_id_col: str,
        text_col: str,
    ) -> List[SoldierTexts]:
        """Group records by soldier and estimate tokens."""
        soldiers = []

        for soldier_id, group in df.groupby(soldier_id_col):
            texts = group[text_col].tolist()
            total_tokens = sum(self.estimate_tokens(t) for t in texts)

            soldiers.append(SoldierTexts(
                soldier_id=str(soldier_id),
                texts=texts,
                estimated_tokens=total_tokens,
            ))

        return soldiers

    def _apply_order(
        self,
        soldiers: List[SoldierTexts],
        order: Literal["forward", "inverted"] = "forward",
        soldier_order: Optional[List[str]] = None,
    ) -> List[SoldierTexts]:
        """Apply ordering to soldier list."""
        if soldier_order is not None:
            # Custom order
            order_map = {sid: i for i, sid in enumerate(soldier_order)}
            return sorted(soldiers, key=lambda s: order_map.get(s.soldier_id, len(order_map)))

        elif order == "inverted":
            return list(reversed(soldiers))

        else:
            # Forward (original) order
            return soldiers

    def _pack_batches(
        self,
        soldiers: List[SoldierTexts],
    ) -> List[TokenBatch]:
        """Pack soldiers into batches using greedy first-fit."""
        batches = []
        current_soldiers = []
        current_tokens = 0

        for soldier in soldiers:
            # Check if adding this soldier would exceed budget
            would_exceed = (
                current_tokens + soldier.estimated_tokens > self.config.token_budget
                and current_soldiers  # Don't create empty batch
            )

            if would_exceed:
                # Create batch with current soldiers
                batch = TokenBatch(
                    batch_id=f"{self.config.batch_id_prefix}_{len(batches):03d}",
                    soldiers=current_soldiers,
                    estimated_tokens=current_tokens,
                )
                batches.append(batch)

                # Start new batch
                current_soldiers = []
                current_tokens = 0

            # Add soldier to current batch
            current_soldiers.append(soldier)
            current_tokens += soldier.estimated_tokens

        # Create final batch if any soldiers remain
        if current_soldiers:
            batch = TokenBatch(
                batch_id=f"{self.config.batch_id_prefix}_{len(batches):03d}",
                soldiers=current_soldiers,
                estimated_tokens=current_tokens,
            )
            batches.append(batch)

        return batches

    def create_batches(
        self,
        df: pd.DataFrame,
        soldier_id_col: str = "soldier_id",
        text_col: str = "raw_text",
        order: Literal["forward", "inverted"] = "forward",
        soldier_order: Optional[List[str]] = None,
    ) -> List[TokenBatch]:
        """
        Create token-budget batches from DataFrame.

        Args:
            df: DataFrame with soldier records
            soldier_id_col: Column name for soldier ID
            text_col: Column name for text content
            order: Batch order - "forward" or "inverted"
            soldier_order: Optional explicit soldier ordering (overrides order param)

        Returns:
            List of TokenBatch objects
        """
        if df.empty:
            return []

        # Validate columns
        if soldier_id_col not in df.columns:
            raise ValueError(f"Column '{soldier_id_col}' not found in DataFrame")
        if text_col not in df.columns:
            raise ValueError(f"Column '{text_col}' not found in DataFrame")

        # Group by soldier
        soldiers = self._group_by_soldier(df, soldier_id_col, text_col)

        # Apply ordering
        soldiers = self._apply_order(soldiers, order, soldier_order)

        # Pack into batches
        batches = self._pack_batches(soldiers)

        return batches

    def create_batches_from_texts(
        self,
        soldier_texts: dict,
        order: Literal["forward", "inverted"] = "forward",
        soldier_order: Optional[List[str]] = None,
    ) -> List[TokenBatch]:
        """
        Create batches from pre-grouped soldier texts.

        Args:
            soldier_texts: Dict mapping soldier_id -> list of texts
            order: Batch order
            soldier_order: Optional explicit ordering

        Returns:
            List of TokenBatch objects
        """
        soldiers = []
        for soldier_id, texts in soldier_texts.items():
            total_tokens = sum(self.estimate_tokens(t) for t in texts)
            soldiers.append(SoldierTexts(
                soldier_id=str(soldier_id),
                texts=texts,
                estimated_tokens=total_tokens,
            ))

        soldiers = self._apply_order(soldiers, order, soldier_order)
        return self._pack_batches(soldiers)

    def get_batch_summary(self, batches: List[TokenBatch]) -> dict:
        """Get summary statistics for batches."""
        if not batches:
            return {
                "batch_count": 0,
                "total_soldiers": 0,
                "total_records": 0,
                "total_tokens": 0,
            }

        return {
            "batch_count": len(batches),
            "total_soldiers": sum(b.soldier_count for b in batches),
            "total_records": sum(b.record_count for b in batches),
            "total_tokens": sum(b.estimated_tokens for b in batches),
            "avg_tokens_per_batch": sum(b.estimated_tokens for b in batches) // len(batches),
            "min_tokens": min(b.estimated_tokens for b in batches),
            "max_tokens": max(b.estimated_tokens for b in batches),
        }


def create_token_batches(
    df: pd.DataFrame,
    soldier_id_col: str = "soldier_id",
    text_col: str = "raw_text",
    token_budget: int = 8000,
    order: Literal["forward", "inverted"] = "forward",
) -> List[TokenBatch]:
    """
    Convenience function to create token-budget batches.

    Args:
        df: DataFrame with soldier records
        soldier_id_col: Column name for soldier ID
        text_col: Column name for text content
        token_budget: Max tokens per batch
        order: Batch order

    Returns:
        List of TokenBatch objects
    """
    config = TokenBatchConfig(token_budget=token_budget)
    batcher = TokenBatcher(config)
    return batcher.create_batches(df, soldier_id_col, text_col, order)
