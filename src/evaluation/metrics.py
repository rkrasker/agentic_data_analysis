"""
Evaluation metrics for consolidation strategies.

Compares strategy predictions against ground truth validation data.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set
import pandas as pd
import numpy as np

from ..strategies import ConsolidationResult, ConfidenceTier


@dataclass
class ComponentMetrics:
    """Metrics for a single component."""
    component_id: str
    total_soldiers: int

    # Accuracy by unit level
    division_correct: int = 0
    regiment_correct: int = 0
    battalion_correct: int = 0
    company_correct: int = 0

    # Accuracy by confidence tier
    by_confidence: Dict[str, Dict[str, int]] = field(default_factory=dict)

    # Error analysis
    errors: int = 0
    missing_predictions: int = 0

    @property
    def division_accuracy(self) -> float:
        """Division-level accuracy."""
        valid = self.total_soldiers - self.errors - self.missing_predictions
        return self.division_correct / valid if valid > 0 else 0.0

    @property
    def regiment_accuracy(self) -> float:
        """Regiment-level accuracy."""
        valid = self.total_soldiers - self.errors - self.missing_predictions
        return self.regiment_correct / valid if valid > 0 else 0.0

    @property
    def battalion_accuracy(self) -> float:
        """Battalion-level accuracy."""
        valid = self.total_soldiers - self.errors - self.missing_predictions
        return self.battalion_correct / valid if valid > 0 else 0.0

    @property
    def company_accuracy(self) -> float:
        """Company-level accuracy (strictest)."""
        valid = self.total_soldiers - self.errors - self.missing_predictions
        return self.company_correct / valid if valid > 0 else 0.0


@dataclass
class EvaluationMetrics:
    """Comprehensive evaluation metrics for a strategy."""
    strategy_name: str
    model_name: Optional[str] = None

    # Overall metrics
    total_soldiers: int = 0
    total_predictions: int = 0
    total_errors: int = 0

    # Accuracy by unit level (across all components)
    division_correct: int = 0
    regiment_correct: int = 0
    battalion_correct: int = 0
    company_correct: int = 0

    # Per-component metrics
    by_component: Dict[str, ComponentMetrics] = field(default_factory=dict)

    # Confidence calibration
    by_confidence: Dict[str, Dict[str, int]] = field(default_factory=dict)

    # Cost tracking
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cost_usd: float = 0.0

    @property
    def division_accuracy(self) -> float:
        """Overall division-level accuracy."""
        valid = self.total_predictions - self.total_errors
        return self.division_correct / valid if valid > 0 else 0.0

    @property
    def regiment_accuracy(self) -> float:
        """Overall regiment-level accuracy."""
        valid = self.total_predictions - self.total_errors
        return self.regiment_correct / valid if valid > 0 else 0.0

    @property
    def battalion_accuracy(self) -> float:
        """Overall battalion-level accuracy."""
        valid = self.total_predictions - self.total_errors
        return self.battalion_correct / valid if valid > 0 else 0.0

    @property
    def company_accuracy(self) -> float:
        """Overall company-level accuracy."""
        valid = self.total_predictions - self.total_errors
        return self.company_correct / valid if valid > 0 else 0.0

    @property
    def error_rate(self) -> float:
        """Fraction of predictions with errors."""
        return self.total_errors / self.total_soldiers if self.total_soldiers > 0 else 0.0

    @property
    def coverage(self) -> float:
        """Fraction of soldiers with predictions."""
        return self.total_predictions / self.total_soldiers if self.total_soldiers > 0 else 0.0

    @property
    def cost_per_soldier(self) -> float:
        """Average cost per soldier."""
        return self.total_cost_usd / self.total_soldiers if self.total_soldiers > 0 else 0.0

    def print_summary(self):
        """Print human-readable summary."""
        print("=" * 80)
        print(f"Evaluation Summary: {self.strategy_name}")
        if self.model_name:
            print(f"Model: {self.model_name}")
        print("=" * 80)
        print(f"\nCoverage:")
        print(f"  Total soldiers: {self.total_soldiers:,}")
        print(f"  Predictions: {self.total_predictions:,} ({self.coverage:.1%})")
        print(f"  Errors: {self.total_errors:,} ({self.error_rate:.1%})")

        print(f"\nAccuracy (on non-error predictions):")
        print(f"  Division:  {self.division_accuracy:.1%}")
        print(f"  Regiment:  {self.regiment_accuracy:.1%}")
        print(f"  Battalion: {self.battalion_accuracy:.1%}")
        print(f"  Company:   {self.company_accuracy:.1%}")

        if self.by_confidence:
            print(f"\nConfidence Calibration:")
            for tier in ["robust", "strong", "moderate", "tentative"]:
                if tier in self.by_confidence:
                    stats = self.by_confidence[tier]
                    total = stats.get("total", 0)
                    correct = stats.get("correct", 0)
                    accuracy = correct / total if total > 0 else 0.0
                    print(f"  {tier:10s}: {correct:4d}/{total:4d} = {accuracy:.1%}")

        print(f"\nCost:")
        print(f"  Total: ${self.total_cost_usd:.2f}")
        print(f"  Per soldier: ${self.cost_per_soldier:.4f}")
        print(f"  Tokens: {self.total_input_tokens + self.total_output_tokens:,}")

        if self.by_component:
            print(f"\nTop 5 Components by Sample Size:")
            sorted_components = sorted(
                self.by_component.items(),
                key=lambda x: x[1].total_soldiers,
                reverse=True
            )[:5]
            for component_id, metrics in sorted_components:
                print(f"  {component_id:30s}: "
                      f"n={metrics.total_soldiers:3d}, "
                      f"company_acc={metrics.company_accuracy:.1%}")

        print("=" * 80)


def compute_metrics(
    result: ConsolidationResult,
    validation_df: pd.DataFrame,
    strategy_name: Optional[str] = None,
) -> EvaluationMetrics:
    """
    Compute evaluation metrics by comparing predictions to ground truth.

    Args:
        result: ConsolidationResult from strategy
        validation_df: Ground truth validation data
        strategy_name: Override strategy name

    Returns:
        EvaluationMetrics with computed accuracy
    """
    # Normalize validation column names
    val_df = validation_df.copy()
    if "primary_id" in val_df.columns:
        val_df = val_df.rename(columns={"primary_id": "soldier_id"})

    # Create lookup dict for ground truth
    val_dict = val_df.set_index("soldier_id").to_dict("index")

    # Initialize metrics
    metrics = EvaluationMetrics(
        strategy_name=strategy_name or result.strategy_name,
        model_name=result.model_name,
        total_soldiers=len(val_dict),
        total_input_tokens=result.input_tokens,
        total_output_tokens=result.output_tokens,
        total_cost_usd=result.cost_usd,
    )

    # Initialize confidence tracking
    for tier in ["robust", "strong", "moderate", "tentative"]:
        metrics.by_confidence[tier] = {"total": 0, "correct": 0}

    # Track per-component metrics
    component_metrics: Dict[str, ComponentMetrics] = {}

    # Compare each prediction to ground truth
    for soldier_id, assignment in result.assignments.items():
        if soldier_id not in val_dict:
            # Soldier not in validation set (shouldn't happen if properly filtered)
            continue

        metrics.total_predictions += 1
        ground_truth = val_dict[soldier_id]
        component_id = ground_truth["component_id"]

        # Initialize component metrics if needed
        if component_id not in component_metrics:
            component_count = len(val_df[val_df["component_id"] == component_id])
            component_metrics[component_id] = ComponentMetrics(
                component_id=component_id,
                total_soldiers=component_count,
            )

        comp_metrics = component_metrics[component_id]

        # Check for errors
        if soldier_id in result.errors:
            metrics.total_errors += 1
            comp_metrics.errors += 1
            continue

        # Compare at each level
        division_match = _safe_compare(assignment.division, ground_truth.get("division"))
        regiment_match = _safe_compare(assignment.regiment, ground_truth.get("regiment"))
        battalion_match = _safe_compare(assignment.battalion, ground_truth.get("battalion"))
        company_match = _safe_compare(assignment.company, ground_truth.get("company"))

        # Division-level accuracy
        if division_match:
            metrics.division_correct += 1
            comp_metrics.division_correct += 1

        # Regiment-level accuracy (requires division + regiment)
        if division_match and regiment_match:
            metrics.regiment_correct += 1
            comp_metrics.regiment_correct += 1

        # Battalion-level accuracy (requires division + regiment + battalion)
        if division_match and regiment_match and battalion_match:
            metrics.battalion_correct += 1
            comp_metrics.battalion_correct += 1

        # Company-level accuracy (requires all levels)
        if division_match and regiment_match and battalion_match and company_match:
            metrics.company_correct += 1
            comp_metrics.company_correct += 1

        # Confidence calibration tracking
        confidence_key = assignment.confidence.value
        metrics.by_confidence[confidence_key]["total"] += 1
        if division_match and regiment_match and battalion_match and company_match:
            metrics.by_confidence[confidence_key]["correct"] += 1

    # Store component metrics
    metrics.by_component = component_metrics

    return metrics


def _safe_compare(pred, truth) -> bool:
    """
    Safely compare prediction to ground truth, handling None and type mismatches.
    """
    if pred is None or truth is None:
        return False

    # Handle pandas NA values
    if pd.isna(pred) or pd.isna(truth):
        return False

    # Compare as strings for mixed types
    return str(pred).lower() == str(truth).lower()
