"""
Base strategy interface for LLM consolidation.

All strategies (resolver, zero-shot, few-shot, multi-pass) implement this
contract to enable testing with the same harness.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any
from pathlib import Path
import pandas as pd


class ConfidenceTier(Enum):
    """Confidence level for unit assignment."""
    ROBUST = "robust"        # >90% certain
    STRONG = "strong"        # 75-90% certain
    MODERATE = "moderate"    # 50-75% certain
    TENTATIVE = "tentative"  # <50% certain, tiebreaker only


@dataclass
class UnitAssignment:
    """Unit assignment for a soldier with confidence."""
    component_id: str
    division: Optional[str] = None
    regiment: Optional[int] = None
    battalion: Optional[int] = None
    company: Optional[str] = None

    confidence: ConfidenceTier = ConfidenceTier.TENTATIVE
    reasoning: Optional[str] = None  # Brief explanation of decision

    # Signals that led to this assignment
    supporting_signals: List[str] = field(default_factory=list)
    conflicting_signals: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "component_id": self.component_id,
            "division": self.division,
            "regiment": self.regiment,
            "battalion": self.battalion,
            "company": self.company,
            "confidence": self.confidence.value,
            "reasoning": self.reasoning,
            "supporting_signals": self.supporting_signals,
            "conflicting_signals": self.conflicting_signals,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UnitAssignment":
        """Create from dictionary."""
        confidence = data.get("confidence", "tentative")
        if isinstance(confidence, str):
            confidence = ConfidenceTier(confidence)

        return cls(
            component_id=data["component_id"],
            division=data.get("division"),
            regiment=data.get("regiment"),
            battalion=data.get("battalion"),
            company=data.get("company"),
            confidence=confidence,
            reasoning=data.get("reasoning"),
            supporting_signals=data.get("supporting_signals", []),
            conflicting_signals=data.get("conflicting_signals", []),
        )


@dataclass
class TransferDetection:
    """Detected unit transfer for a soldier."""
    from_assignment: UnitAssignment
    to_assignment: UnitAssignment
    transfer_level: str  # company_level, battalion_level, regiment_level, division_level
    confidence: ConfidenceTier
    evidence: List[str] = field(default_factory=list)


@dataclass
class SoldierRecords:
    """All records for a single soldier."""
    soldier_id: str
    records: pd.DataFrame  # Rows from canonical.parquet for this soldier

    def __post_init__(self):
        """Validate that all records belong to same soldier."""
        if not self.records.empty:
            unique_ids = self.records["soldier_id"].unique()
            if len(unique_ids) > 1:
                raise ValueError(
                    f"Records contain multiple soldier_ids: {unique_ids}. "
                    f"Expected only {self.soldier_id}"
                )

    @property
    def raw_texts(self) -> List[str]:
        """Get all raw text records."""
        return self.records["raw_text"].tolist()

    @property
    def record_count(self) -> int:
        """Number of records for this soldier."""
        return len(self.records)


@dataclass
class SoldierBatch:
    """Batch of soldiers to consolidate together."""
    batch_id: str
    component_hint: Optional[str] = None  # Likely component from routing
    soldiers: List[SoldierRecords] = field(default_factory=list)

    # Component hierarchy for reference (loaded from config)
    hierarchy: Optional[Dict[str, Any]] = None

    # Strategy-specific artifacts (e.g., resolver JSON for resolver strategy)
    strategy_artifacts: Optional[Dict[str, Any]] = None

    def __len__(self) -> int:
        return len(self.soldiers)

    @property
    def soldier_ids(self) -> List[str]:
        """Get list of soldier IDs in this batch."""
        return [s.soldier_id for s in self.soldiers]

    @property
    def total_records(self) -> int:
        """Total number of records across all soldiers."""
        return sum(s.record_count for s in self.soldiers)


@dataclass
class ConsolidationResult:
    """Result of consolidating a batch."""
    batch_id: str
    assignments: Dict[str, UnitAssignment]  # soldier_id -> assignment
    transfers: Dict[str, List[TransferDetection]] = field(default_factory=dict)

    # Metadata
    strategy_name: str = "unknown"
    model_name: Optional[str] = None

    # Token tracking
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0

    # Errors/warnings per soldier
    errors: Dict[str, str] = field(default_factory=dict)
    warnings: Dict[str, List[str]] = field(default_factory=dict)

    def to_dataframe(self) -> pd.DataFrame:
        """
        Convert to DataFrame format for evaluation.

        Returns DataFrame with columns:
        - soldier_id
        - component_id
        - division
        - regiment
        - battalion
        - company
        - confidence
        - has_error
        """
        rows = []
        for soldier_id, assignment in self.assignments.items():
            row = {
                "soldier_id": soldier_id,
                "component_id": assignment.component_id,
                "division": assignment.division,
                "regiment": assignment.regiment,
                "battalion": assignment.battalion,
                "company": assignment.company,
                "confidence": assignment.confidence.value,
                "has_error": soldier_id in self.errors,
            }
            rows.append(row)
        return pd.DataFrame(rows)

    @property
    def success_rate(self) -> float:
        """Fraction of soldiers with non-error assignments."""
        if not self.assignments:
            return 0.0
        return 1.0 - (len(self.errors) / len(self.assignments))


class BaseStrategy(ABC):
    """
    Abstract base class for consolidation strategies.

    All strategies must implement the consolidate() method which takes
    a SoldierBatch and returns a ConsolidationResult.
    """

    def __init__(self, strategy_name: str, **kwargs):
        """
        Initialize strategy.

        Args:
            strategy_name: Name identifier for this strategy
            **kwargs: Strategy-specific configuration
        """
        self.strategy_name = strategy_name
        self.config = kwargs

    @abstractmethod
    def consolidate(self, batch: SoldierBatch) -> ConsolidationResult:
        """
        Consolidate records for a batch of soldiers.

        This is the main entry point for all strategies. Implementations should:
        1. Parse raw text records for each soldier
        2. Interpret extraction signals from preprocessing
        3. Cross-reference records for the same soldier
        4. Resolve contradictions and detect transfers
        5. Assign confidence tiers

        Args:
            batch: SoldierBatch with records to consolidate

        Returns:
            ConsolidationResult with per-soldier assignments
        """
        pass

    def load_hierarchy(self, component_id: str, hierarchy_path: Path) -> Dict[str, Any]:
        """
        Load component hierarchy from config.

        Args:
            component_id: Component identifier (e.g., "1st_infantry_division")
            hierarchy_path: Path to hierarchy_reference.json

        Returns:
            Component hierarchy dict
        """
        import json

        with open(hierarchy_path) as f:
            hierarchy = json.load(f)

        components = hierarchy.get("components", {})
        if component_id not in components:
            raise ValueError(
                f"Component {component_id} not found in hierarchy. "
                f"Available: {list(components.keys())}"
            )

        return components[component_id]

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(strategy={self.strategy_name})"
