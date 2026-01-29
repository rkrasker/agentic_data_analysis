"""
Module 5: Registry Manager

Tracks resolver generation status and rebuild triggers.
Maintains resolver_registry.json with generation metadata.
"""

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
import numpy as np

from .thresholds import ThresholdResult, TierName
from .assembler import NumpyEncoder


@dataclass
class SectionStatus:
    """Status of a resolver section."""
    status: str  # "complete", "limited", "not_generated"
    reason: Optional[str] = None  # Reason if not complete
    rebuild_when: Optional[str] = None  # Condition for rebuild


@dataclass
class RegistryEntry:
    """Registry entry for a single component's resolver."""
    component_id: str
    tier: TierName
    sample_size: int
    pct_of_median: float
    generated_utc: str
    generation_mode: str  # "full", "limited", "hierarchy_only"

    # Section status
    structure_status: str = "complete"
    patterns_status: str = "complete"
    vocabulary_status: str = "complete"
    exclusions_structural_status: str = "complete"
    exclusions_value_based_status: str = "not_applicable"
    differentiators_status: str = "complete"

    # Rebuild triggers
    rebuild_when_tier: Optional[str] = None
    rebuild_when_sample_size: Optional[int] = None

    # Quality flags
    warnings: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "tier": self.tier,
            "sample_size": self.sample_size,
            "pct_of_median": round(self.pct_of_median, 1),
            "generated_utc": self.generated_utc,
            "generation_mode": self.generation_mode,
            "sections": {
                "structure": self.structure_status,
                "patterns": self.patterns_status,
                "vocabulary": self.vocabulary_status,
                "exclusions_structural": self.exclusions_structural_status,
                "exclusions_value_based": self.exclusions_value_based_status,
                "differentiators": self.differentiators_status,
            },
            "rebuild_triggers": {
                "when_tier": self.rebuild_when_tier,
                "when_sample_size": self.rebuild_when_sample_size,
            },
            "warnings": self.warnings,
            "recommendations": self.recommendations,
        }

    @classmethod
    def from_dict(cls, component_id: str, data: Dict) -> "RegistryEntry":
        """Create from dictionary."""
        sections = data.get("sections", {})
        rebuild = data.get("rebuild_triggers", {})

        return cls(
            component_id=component_id,
            tier=data.get("tier", "sparse"),
            sample_size=data.get("sample_size", 0),
            pct_of_median=data.get("pct_of_median", 0.0),
            generated_utc=data.get("generated_utc", ""),
            generation_mode=data.get("generation_mode", "hierarchy_only"),
            structure_status=sections.get("structure", "complete"),
            patterns_status=sections.get("patterns", "not_generated"),
            vocabulary_status=sections.get("vocabulary", "not_generated"),
            exclusions_structural_status=sections.get("exclusions_structural", "complete"),
            exclusions_value_based_status=sections.get("exclusions_value_based", "not_applicable"),
            differentiators_status=sections.get("differentiators", "not_generated"),
            rebuild_when_tier=rebuild.get("when_tier"),
            rebuild_when_sample_size=rebuild.get("when_sample_size"),
            warnings=data.get("warnings", []),
            recommendations=data.get("recommendations", []),
        )


@dataclass
class ResolverRegistry:
    """Complete registry tracking all resolvers."""
    generated_utc: str
    validation_source: str
    thresholds: Dict[str, float]
    model_used: str
    entries: Dict[str, RegistryEntry] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "meta": {
                "generated_utc": self.generated_utc,
                "validation_source": self.validation_source,
                "model_used": self.model_used,
            },
            "thresholds": self.thresholds,
            "components": {
                comp_id: entry.to_dict()
                for comp_id, entry in self.entries.items()
            },
            "summary": self._compute_summary(),
        }

    def _compute_summary(self) -> Dict[str, Any]:
        """Compute registry summary statistics."""
        tier_counts = {"well_represented": 0, "adequately_represented": 0, "under_represented": 0, "sparse": 0}
        mode_counts = {"full": 0, "limited": 0, "hierarchy_only": 0}

        for entry in self.entries.values():
            tier_counts[entry.tier] += 1
            mode_counts[entry.generation_mode] += 1

        return {
            "total_components": len(self.entries),
            "by_tier": tier_counts,
            "by_generation_mode": mode_counts,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "ResolverRegistry":
        """Create from dictionary."""
        meta = data.get("meta", {})
        entries = {}
        for comp_id, entry_data in data.get("components", {}).items():
            entries[comp_id] = RegistryEntry.from_dict(comp_id, entry_data)

        return cls(
            generated_utc=meta.get("generated_utc", ""),
            validation_source=meta.get("validation_source", ""),
            model_used=meta.get("model_used", "unknown"),
            thresholds=data.get("thresholds", {}),
            entries=entries,
        )


class RegistryManager:
    """Manages resolver registry operations."""

    def __init__(self, registry_path: Path):
        """
        Initialize registry manager.

        Args:
            registry_path: Path to resolver_registry.json
        """
        self.registry_path = registry_path
        self._registry: Optional[ResolverRegistry] = None

    def load(self) -> Optional[ResolverRegistry]:
        """Load existing registry from disk."""
        if not self.registry_path.exists():
            return None

        with open(self.registry_path) as f:
            data = json.load(f)

        self._registry = ResolverRegistry.from_dict(data)
        return self._registry

    def save(self, registry: ResolverRegistry):
        """Save registry to disk."""
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)

        with open(self.registry_path, "w") as f:
            json.dump(registry.to_dict(), f, indent=2, cls=NumpyEncoder)

        self._registry = registry

    def create_registry(
        self,
        validation_source: str,
        thresholds: ThresholdResult,
        model_used: str,
    ) -> ResolverRegistry:
        """
        Create a new registry.

        Args:
            validation_source: Path to validation data used
            thresholds: Threshold computation result
            model_used: Model used for generation

        Returns:
            New ResolverRegistry instance
        """
        registry = ResolverRegistry(
            generated_utc=datetime.utcnow().isoformat() + "Z",
            validation_source=validation_source,
            thresholds=thresholds.thresholds,
            model_used=model_used,
        )
        self._registry = registry
        return registry

    def add_entry(
        self,
        registry: ResolverRegistry,
        component_id: str,
        tier: TierName,
        sample_size: int,
        pct_of_median: float,
        generation_mode: str,
        section_status: Dict[str, str],
        warnings: Optional[List[str]] = None,
        recommendations: Optional[List[str]] = None,
    ) -> RegistryEntry:
        """
        Add an entry to the registry.

        Args:
            registry: Registry to add to
            component_id: Component identifier
            tier: Component tier
            sample_size: Number of soldiers
            pct_of_median: Percentage of median count
            generation_mode: "full", "limited", or "hierarchy_only"
            section_status: Dict mapping section name to status
            warnings: Quality warnings
            recommendations: Usage recommendations

        Returns:
            Created RegistryEntry
        """
        # Determine rebuild triggers based on tier
        rebuild_when_tier = None
        rebuild_when_sample_size = None

        if tier == "sparse":
            rebuild_when_tier = "under_represented"
            rebuild_when_sample_size = int(registry.thresholds.get("p25", 10))
        elif tier == "under_represented":
            rebuild_when_tier = "adequately_represented"
            rebuild_when_sample_size = int(registry.thresholds.get("median", 50))

        entry = RegistryEntry(
            component_id=component_id,
            tier=tier,
            sample_size=sample_size,
            pct_of_median=pct_of_median,
            generated_utc=datetime.utcnow().isoformat() + "Z",
            generation_mode=generation_mode,
            structure_status=section_status.get("structure", "complete"),
            patterns_status=section_status.get("patterns", "not_generated"),
            vocabulary_status=section_status.get("vocabulary", "not_generated"),
            exclusions_structural_status=section_status.get("exclusions_structural", "complete"),
            exclusions_value_based_status=section_status.get("exclusions_value_based", "not_applicable"),
            differentiators_status=section_status.get("differentiators", "not_generated"),
            rebuild_when_tier=rebuild_when_tier,
            rebuild_when_sample_size=rebuild_when_sample_size,
            warnings=warnings or [],
            recommendations=recommendations or [],
        )

        registry.entries[component_id] = entry
        return entry

    def should_rebuild(
        self,
        component_id: str,
        current_tier: TierName,
        current_sample_size: int,
    ) -> bool:
        """
        Check if a resolver should be regenerated.

        Args:
            component_id: Component to check
            current_tier: Current tier based on new data
            current_sample_size: Current sample size

        Returns:
            True if resolver should be rebuilt
        """
        if self._registry is None:
            self.load()

        if self._registry is None:
            return True  # No registry, need to build

        if component_id not in self._registry.entries:
            return True  # New component

        entry = self._registry.entries[component_id]

        # Check tier improvement trigger
        if entry.rebuild_when_tier:
            tier_order = ["sparse", "under_represented", "adequately_represented", "well_represented"]
            current_idx = tier_order.index(current_tier)
            target_idx = tier_order.index(entry.rebuild_when_tier)
            if current_idx >= target_idx:
                return True

        # Check sample size trigger
        if entry.rebuild_when_sample_size:
            if current_sample_size >= entry.rebuild_when_sample_size:
                return True

        return False

    def get_rebuild_candidates(
        self,
        thresholds: ThresholdResult,
    ) -> List[str]:
        """
        Get list of components that should be rebuilt.

        Args:
            thresholds: Current threshold results

        Returns:
            List of component IDs that need rebuilding
        """
        candidates = []

        for component_id, count in thresholds.component_counts.items():
            current_tier = thresholds.get_tier(component_id)
            if self.should_rebuild(component_id, current_tier, count):
                candidates.append(component_id)

        return candidates


def create_entry_for_tier(
    component_id: str,
    tier: TierName,
    sample_size: int,
    pct_of_median: float,
) -> Dict[str, str]:
    """
    Get default section status based on tier.

    Args:
        component_id: Component identifier
        tier: Component tier
        sample_size: Number of soldiers
        pct_of_median: Percentage of median

    Returns:
        Dict mapping section name to status
    """
    if tier == "well_represented":
        return {
            "structure": "complete",
            "patterns": "complete",
            "vocabulary": "complete",
            "exclusions_structural": "complete",
            "exclusions_value_based": "not_applicable",
            "differentiators": "complete",
        }
    elif tier == "adequately_represented":
        return {
            "structure": "complete",
            "patterns": "complete",
            "vocabulary": "complete",  # May be thin
            "exclusions_structural": "complete",
            "exclusions_value_based": "not_applicable",
            "differentiators": "complete",
        }
    elif tier == "under_represented":
        return {
            "structure": "complete",
            "patterns": "limited",
            "vocabulary": "not_generated",
            "exclusions_structural": "complete",
            "exclusions_value_based": "not_applicable",
            "differentiators": "hierarchy_only",
        }
    else:  # sparse
        return {
            "structure": "complete",
            "patterns": "not_generated",
            "vocabulary": "not_generated",
            "exclusions_structural": "complete",
            "exclusions_value_based": "not_applicable",
            "differentiators": "hierarchy_only",
        }


def get_recommendations_for_tier(tier: TierName) -> List[str]:
    """Get usage recommendations based on tier."""
    if tier == "sparse":
        return [
            "Consider using zero-shot or few-shot strategy for this component",
            "Resolver provides hierarchy-only guidance",
            "High collision risk with similar components",
        ]
    elif tier == "under_represented":
        return [
            "Pattern and vocabulary sections are limited",
            "Differentiators are hierarchy-based only",
            "Consider supplementing with few-shot examples",
        ]
    else:
        return []


def get_warnings_for_tier(tier: TierName, pct_of_median: float) -> List[str]:
    """Get quality warnings based on tier and distribution."""
    warnings = []

    if tier == "sparse":
        warnings.append(f"Sample size is only {pct_of_median:.1f}% of median")
        warnings.append("Pattern discovery not performed due to insufficient data")

    if pct_of_median < 50:
        warnings.append("Component significantly underrepresented in validation data")

    return warnings
