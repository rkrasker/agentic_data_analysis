"""
Data models for synthetic data generation (v4.1).
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class RankStyle(Enum):
    """How rank is formatted in the entry."""
    PREFIX = "prefix"
    SUFFIX = "suffix"
    MIXED = "mixed"
    SEPARATE_COLUMN = "separate_column"


class RankForm(Enum):
    """The form of rank abbreviation."""
    PROPER_ABBREV = "proper_abbrev"
    CAPS_ABBREV = "caps_abbrev"
    MIXED_ABBREV = "mixed_abbrev"
    PHONETIC = "phonetic"


class UnitFormatStyle(Enum):
    """How unit hierarchy is formatted."""
    LABELED_HIERARCHICAL = "labeled_hierarchical"
    LABELED_FULL = "labeled_full"
    LABELED_MICRO = "labeled_micro"
    SLASH_POSITIONAL = "slash_positional"
    SLASH_COMPACT = "slash_compact"
    RUNON_COMPACT = "runon_compact"
    PHONETIC_INFORMAL = "phonetic_informal"
    MINIMAL = "minimal"


class VocabularyDensity(Enum):
    """How much situational vocabulary a clerk uses."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Branch(Enum):
    """Terraform Combine branches."""
    COLONIAL_ADMINISTRATION = "colonial_administration"
    DEFENSE_COMMAND = "defense_command"
    EXPEDITIONARY_CORPS = "expeditionary_corps"
    RESOURCE_DIRECTORATE = "resource_directorate"


class TransferScope(Enum):
    """Scope of a transfer between states."""
    WITHIN_LEVEL3 = "within_level3"
    WITHIN_LEVEL2 = "within_level2"
    WITHIN_BRANCH = "within_branch"
    CROSS_BRANCH = "cross_branch"


class CollisionSeverity(Enum):
    """Severity of collision zone for a post."""
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CROSS_BRANCH = "cross_branch"


class DifficultyTier(Enum):
    """Soldier-level difficulty tier."""
    EASY = "easy"
    MODERATE = "moderate"
    HARD = "hard"
    EXTREME = "extreme"


class FamiliarityLevel(Enum):
    """Familiarity level for rendering."""
    SAME_L3 = "same_level3"
    SAME_L2 = "same_level2"
    SAME_BRANCH = "same_branch"
    DIFFERENT_BRANCH = "different_branch"


@dataclass
class NameFormat:
    """How a clerk formats names."""
    template: str
    drop_middle_rate: float = 0.0


@dataclass
class RankFormat:
    """How a clerk formats rank."""
    style: RankStyle
    form: RankForm
    omit_rate: float = 0.0


@dataclass
class UnitFormat:
    """How a clerk formats unit hierarchy."""
    style: UnitFormatStyle
    separator: str = ", "
    orientation: str = "child_over_parent"
    include_sector: bool = True
    include_branch: bool = False
    include_level2: bool = True
    include_lowest_levels: bool = True
    omit_level_names: bool = False
    label_style: str = "abbreviated"
    branch_suffix: bool = False
    phonetic_letters: bool = False


@dataclass
class Consistency:
    """Clerk's format consistency rates."""
    format_lock: float = 0.85
    minor_drift: float = 0.12
    major_variation: float = 0.03


@dataclass
class Imperfections:
    """Behavioral imperfections for a clerk."""
    typo_rate: float = 0.02
    abbreviation_inconsistency: float = 0.05
    trailing_off: float = 0.0
    mid_entry_corrections: float = 0.0
    incomplete_unit: float = 0.0
    column_bleed: float = 0.0


@dataclass
class ClerkArchetype:
    """
    A clerk archetype defines the behavioral patterns for a category of clerks.
    """
    archetype_id: str
    description: str
    context_level: str
    name_format: NameFormat
    rank_format: RankFormat
    unit_format: UnitFormat
    vocabulary_density: VocabularyDensity
    vocabulary_bias: List[str] = field(default_factory=list)
    applicable_branches: List[str] = field(default_factory=list)
    familiarity_override: Optional[str] = None
    familiarity_applies: bool = False
    path_completeness_tendency: str = "medium"
    structural_signals_tendency: str = "medium"
    consistency: Consistency = field(default_factory=Consistency)
    imperfections: Imperfections = field(default_factory=Imperfections)


@dataclass
class Clerk:
    """A concrete clerk instance with locked habits."""
    clerk_id: str
    archetype_id: str
    name: str
    context: str
    name_format: NameFormat
    rank_format: RankFormat
    unit_format: UnitFormat
    vocabulary_density: VocabularyDensity
    vocabulary_bias: List[str]
    applicable_branches: List[str]
    familiarity_override: Optional[str]
    familiarity_applies: bool
    path_completeness_tendency: str
    structural_signals_tendency: str
    consistency: Consistency
    imperfections: Imperfections
    used_vocabulary: List[str] = field(default_factory=list)
    entry_count: int = 0


@dataclass
class VocabularyPool:
    """Vocabulary terms available for a situation."""
    primary: List[str] = field(default_factory=list)
    secondary: List[str] = field(default_factory=list)
    rare: List[str] = field(default_factory=list)


@dataclass
class Situation:
    """An operational situation that drives vocabulary selection."""
    situation_id: str
    description: str
    branch: Optional[str] = None
    vocabulary_pool: VocabularyPool = field(default_factory=VocabularyPool)


@dataclass
class State:
    """
    A single state in a soldier's service.

    Each state represents a temporal segment where the soldier
    was assigned to a specific post.
    """
    state_id: str
    soldier_id: str
    state_order: int
    branch: Branch
    post_path: str
    post_levels: Dict[str, str]
    collision_zone_flag: bool = False
    collision_severity: CollisionSeverity = CollisionSeverity.NONE
    colliding_paths: List[str] = field(default_factory=list)


@dataclass
class Soldier:
    """A soldier with 1-3 states."""
    soldier_id: str
    name_first: str
    name_middle: str
    name_last: str
    rank: str
    states: List[State]
    difficulty_tier: Optional[DifficultyTier] = None
    complementarity_score: Optional[float] = None
    structural_resolvability: Optional[bool] = None


@dataclass
class Entry:
    """A single rendered record."""
    entry_id: str
    source_id: str
    soldier_id: str
    state_id: str
    raw_text: str
    clerk_id: str
    situation_id: str
    quality_tier: int
    path_completeness: float = 0.0
    levels_provided: List[str] = field(default_factory=list)
    extraction_signals: List[str] = field(default_factory=list)


@dataclass
class Source:
    """A source document (manifest page, personnel list, etc.)."""
    source_id: str
    clerk_id: str
    situation_id: str
    quality_tier: int
    home_unit: str
    temporal_anchor: int
