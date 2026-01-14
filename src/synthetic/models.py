"""
Data models for synthetic data generation.

These models represent the core entities in the v3 clerk-as-character philosophy.
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any
from enum import Enum


class RankStyle(Enum):
    """How rank is formatted in the entry."""
    PREFIX = "prefix"
    SUFFIX = "suffix"
    MIXED = "mixed"
    SEPARATE_COLUMN = "separate_column"


class RankForm(Enum):
    """The form of rank abbreviation."""
    PROPER_ABBREV = "proper_abbrev"  # S/Sgt, T/5, Cpl
    CAPS_ABBREV = "caps_abbrev"      # SGT, CPL, PVT
    MIXED_ABBREV = "mixed_abbrev"    # Sgt, Cpl, Pvt
    PHONETIC = "phonetic"            # SSgt, Sarnt, Pfc


class UnitFormatStyle(Enum):
    """How unit hierarchy is formatted."""
    LABELED_HIERARCHICAL = "labeled_hierarchical"    # Co E, 2nd Bn, 116th Inf, 29th Div
    LABELED_FULL = "labeled_full"                    # Co E, 2nd Bn, 116th Inf Regt, 29th Inf Div
    LABELED_MICRO = "labeled_micro"                  # E Co 2Bn 116Inf
    SLASH_POSITIONAL = "slash_positional"            # E/2/116/29ID
    SLASH_COMPACT = "slash_compact"                  # A/1/7
    RUNON_COMPACT = "runon_compact"                  # E2-116
    PHONETIC_INFORMAL = "phonetic_informal"          # Easy Co 116
    MINIMAL = "minimal"                              # 116th or 2/116
    AAF_STANDARD = "aaf_standard"                    # 3rd Sq, 91st BG, 8th AF
    COMPACT_AAF = "compact_aaf"                      # 91BG-3
    MARINE_STANDARD = "marine_standard"              # Co A, 1st Bn, 7th Mar, 1st MarDiv


class VocabularyDensity(Enum):
    """How much situational vocabulary a clerk uses."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class TransferType(Enum):
    """Level of unit transfer."""
    COMPANY = "company_level"
    BATTALION = "battalion_level"
    REGIMENT = "regiment_level"
    DIVISION = "division_level"


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
    include_division: bool = True
    include_regiment: bool = True
    include_company: bool = True
    division_suffix: bool = False
    label_style: str = "abbreviated"
    phonetic_companies: bool = False
    marine_regiment_style: str = "Mar"
    include_air_force: bool = True


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

    Individual clerks are instantiated from archetypes with their habits locked.
    """
    archetype_id: str
    description: str
    context_level: str
    name_format: NameFormat
    rank_format: RankFormat
    unit_format: UnitFormat
    vocabulary_density: VocabularyDensity
    vocabulary_bias: List[str] = field(default_factory=list)
    consistency: Consistency = field(default_factory=Consistency)
    imperfections: Imperfections = field(default_factory=Imperfections)


@dataclass
class Clerk:
    """
    A concrete clerk instance with locked habits.

    Once instantiated, a clerk's style never changes. This is the key to
    the v3 philosophy: clerks are persistent characters, not sampling functions.
    """
    clerk_id: str
    archetype_id: str
    name: str  # The clerk's own name (for context)
    context: str  # Description of their working situation

    # Locked habits from archetype (with minor individual variation)
    name_format: NameFormat
    rank_format: RankFormat
    unit_format: UnitFormat
    vocabulary_density: VocabularyDensity
    vocabulary_bias: List[str]
    consistency: Consistency
    imperfections: Imperfections

    # Vocabulary terms this clerk has used (for persistence within source)
    used_vocabulary: List[str] = field(default_factory=list)

    # How many entries this clerk has produced
    entry_count: int = 0


@dataclass
class VocabularyPool:
    """Vocabulary terms available for a situation."""
    primary: List[str] = field(default_factory=list)
    secondary: List[str] = field(default_factory=list)
    rare: List[str] = field(default_factory=list)


@dataclass
class Situation:
    """
    An operational situation that drives vocabulary selection.

    Sources are assigned situations, and all entries in that source share
    the situational vocabulary because they're from the same event.
    """
    situation_id: str
    description: str
    theater: str
    operation_type: str
    applies_to: List[str]  # component_ids or "any"
    vocabulary_pool: VocabularyPool
    date_range: List[str] = field(default_factory=list)


@dataclass
class Assignment:
    """A soldier's unit assignment."""
    component_id: str
    # Infantry/Airborne/Mountain/Marine structure
    regiment: Optional[str] = None
    battalion: Optional[str] = None
    company: Optional[str] = None
    # Armored structure
    combat_command: Optional[str] = None
    # Air Force structure
    bomb_group: Optional[str] = None
    squadron: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary, excluding None values."""
        return {k: v for k, v in {
            "component_id": self.component_id,
            "regiment": self.regiment,
            "battalion": self.battalion,
            "company": self.company,
            "combat_command": self.combat_command,
            "bomb_group": self.bomb_group,
            "squadron": self.squadron,
        }.items() if v is not None}


@dataclass
class Transfer:
    """A soldier's unit transfer record."""
    soldier_id: str
    transfer_type: TransferType
    original_assignment: Assignment
    new_assignment: Assignment


@dataclass
class Soldier:
    """
    A soldier's truth record.

    This represents "what the soldier is" - the canonical facts.
    How they appear in raw entries depends on the rendering layer.
    """
    primary_id: str
    name_first: str
    name_last: str
    name_middle: Optional[str]
    rank: str

    # Current assignment (or new assignment if transferred)
    assignment: Assignment

    # Optional: original assignment if transferred
    original_assignment: Optional[Assignment] = None
    has_transfer: bool = False


@dataclass
class Source:
    """
    A source document representing a physical manifest page or list.

    Produced by one clerk in one situation. All entries share the
    clerk's locked format and situational vocabulary.
    """
    source_id: str
    clerk_id: str
    situation_id: str
    quality_tier: int  # 1-5

    # Entry IDs in this source
    entry_ids: List[str] = field(default_factory=list)

    # Vocabulary terms selected for this source (for consistency)
    selected_vocabulary: List[str] = field(default_factory=list)


@dataclass
class Entry:
    """
    A rendered entry in a source document.

    This is the raw text output - how the truth record appears
    when rendered by a specific clerk in a specific situation.
    """
    entry_id: str
    source_id: str
    soldier_id: str
    raw_text: str

    # Which assignment was used (for transferred soldiers)
    is_original_assignment: bool = False
    is_new_assignment: bool = False

    # Optional metadata
    clutter_terms: List[str] = field(default_factory=list)
    confounder_terms: List[str] = field(default_factory=list)
    situational_terms: List[str] = field(default_factory=list)
