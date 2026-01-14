"""
Synthetic data generation module (v3).

Philosophy: Clerks are characters, not sampling functions.
"""

from .models import (
    Clerk,
    ClerkArchetype,
    Situation,
    Soldier,
    Source,
    Entry,
    Transfer,
    Assignment,
)
from .clerk_factory import ClerkFactory
from .situation_manager import SituationManager
from .vocabulary_injector import VocabularyInjector
from .source_generator import SourceGenerator
from .transfer_manager import TransferManager
from .hierarchy_loader import HierarchyLoader
from .renderer import Renderer
from .soldier_factory import SoldierFactory
from .pipeline import Pipeline, run_pipeline

__all__ = [
    # Models
    "Clerk",
    "ClerkArchetype",
    "Situation",
    "Soldier",
    "Source",
    "Entry",
    "Transfer",
    "Assignment",
    # Factories/Managers
    "ClerkFactory",
    "SituationManager",
    "VocabularyInjector",
    "SourceGenerator",
    "TransferManager",
    # Phase 2: Rendering
    "HierarchyLoader",
    "Renderer",
    # Phase 3: Pipeline
    "SoldierFactory",
    "Pipeline",
    "run_pipeline",
]
