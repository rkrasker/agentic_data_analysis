"""
Renderer: Render soldier states to raw text using clerk formats.
"""

import random
from typing import Dict, List, Optional, Tuple

from .hierarchy_loader import HierarchyLoader
from .models import (
    Branch,
    Clerk,
    Entry,
    FamiliarityLevel,
    RankForm,
    RankStyle,
    Situation,
    Soldier,
    State,
    UnitFormatStyle,
)
from .vocabulary_injector import VocabularyInjector


PHONETIC_LETTERS = {
    "A": "Alpha",
    "B": "Bravo",
    "C": "Charlie",
    "D": "Delta",
    "E": "Echo",
    "F": "Foxtrot",
}

LEVEL_LABELS = {
    "sector": "Sector",
    "colony": "Colony",
    "district": "District",
    "settlement": "Settlement",
    "fleet": "Fleet",
    "squadron": "Squadron",
    "wing": "Wing",
    "element": "Element",
    "expedition": "Expedition",
    "team": "Team",
    "operation": "Operation",
    "facility": "Facility",
    "crew": "Crew",
}

LEVEL_LABELS_ABBREV = {
    "sector": "Sec",
    "colony": "Col",
    "district": "Dist",
    "settlement": "Set",
    "fleet": "Flt",
    "squadron": "Sq",
    "wing": "Wg",
    "element": "El",
    "expedition": "Exp",
    "team": "Tm",
    "operation": "Op",
    "facility": "Fac",
    "crew": "Cr",
}

LEVEL_LABELS_MICRO = {
    "sector": "S",
    "colony": "C",
    "district": "D",
    "settlement": "St",
    "fleet": "F",
    "squadron": "Sq",
    "wing": "W",
    "element": "El",
    "expedition": "Exp",
    "team": "T",
    "operation": "Op",
    "facility": "Fac",
    "crew": "Cr",
}


class Renderer:
    """Renders soldier states to raw text using clerk formats."""

    def __init__(self, hierarchy_loader: HierarchyLoader, random_seed: Optional[int] = None):
        self.rng = random.Random(random_seed)
        self.hierarchy = hierarchy_loader

    def render_entry(
        self,
        entry_id: str,
        soldier: Soldier,
        state: State,
        source,
        clerk: Clerk,
        situation: Situation,
        vocabulary_injector: Optional[VocabularyInjector] = None,
    ) -> Entry:
        """Render a soldier state to an Entry."""
        name = self.render_name(soldier, clerk)
        rank = self.render_rank(soldier, clerk)

        unit_text, levels_provided = self.render_unit(state, source, clerk)
        extraction_signals = self._extract_structural_signals(unit_text, state, levels_provided)
        path_completeness = len(levels_provided) / max(self.hierarchy.get_branch_depth(state.branch), 1)

        base_text = self._combine_fields(name, rank, unit_text, clerk)

        raw_text = base_text
        if vocabulary_injector:
            raw_text, _ = vocabulary_injector.inject_vocabulary(base_text, clerk, situation)

        return Entry(
            entry_id=entry_id,
            source_id=source.source_id,
            soldier_id=soldier.soldier_id,
            state_id=state.state_id,
            raw_text=raw_text,
            clerk_id=clerk.clerk_id,
            situation_id=situation.situation_id,
            quality_tier=source.quality_tier,
            path_completeness=path_completeness,
            levels_provided=levels_provided,
            extraction_signals=extraction_signals,
        )

    def render_name(self, soldier: Soldier, clerk: Clerk) -> str:
        """Render a soldier's name using the clerk's format."""
        template = clerk.name_format.template

        last = soldier.name_last
        first = soldier.name_first
        middle = soldier.name_middle or ""
        fi = first[0] if first else ""
        mi = middle[0] if middle else ""

        if middle and self.rng.random() < clerk.name_format.drop_middle_rate:
            mi = ""
            middle = ""

        result = template
        result = result.replace("{LAST}", last)
        result = result.replace("{FIRST}", first)
        result = result.replace("{FI}", fi)
        result = result.replace("{MI}", mi)

        result = result.replace(" .", "")
        result = result.replace(".,", ",")
        result = result.replace(". ", " ")
        result = result.replace("  ", " ")

        return result.strip()

    def render_rank(self, soldier: Soldier, clerk: Clerk) -> str:
        """Render a soldier's rank using the clerk's format."""
        if self.rng.random() < clerk.rank_format.omit_rate:
            return ""

        canonical = soldier.rank
        form = clerk.rank_format.form

        if form == RankForm.CAPS_ABBREV:
            return canonical.upper()
        if form == RankForm.MIXED_ABBREV:
            return canonical.title()
        return canonical

    def render_unit(self, state: State, source, clerk: Clerk) -> Tuple[str, List[str]]:
        """Render a unit string and return provided levels."""
        levels = self.hierarchy.get_branch_levels(state.branch)
        familiarity = self._get_familiarity_level(source, state, clerk)

        include_levels = self._select_levels(levels, familiarity, clerk)
        levels_provided = [lvl for lvl in levels if lvl in include_levels]

        unit_text = self._format_unit(
            state,
            levels_provided,
            clerk,
        )

        return unit_text, levels_provided

    def _get_familiarity_level(self, source, state: State, clerk: Clerk) -> FamiliarityLevel:
        """Determine familiarity level relative to the source home unit."""
        if clerk.familiarity_override == "ignore" or not clerk.familiarity_applies:
            return FamiliarityLevel.DIFFERENT_BRANCH

        home_branch, home_levels = self._parse_home_unit(source.home_unit)
        if not home_branch or home_branch != state.branch.value:
            return FamiliarityLevel.DIFFERENT_BRANCH

        branch_levels = self.hierarchy.get_branch_levels(state.branch)
        if len(branch_levels) < 3:
            return FamiliarityLevel.SAME_BRANCH

        l1, l2, l3 = branch_levels[:3]
        same_l3 = (
            state.post_levels.get(l1) == home_levels.get(l1) and
            state.post_levels.get(l2) == home_levels.get(l2) and
            state.post_levels.get(l3) == home_levels.get(l3)
        )
        if same_l3:
            return FamiliarityLevel.SAME_L3

        same_l2 = (
            state.post_levels.get(l1) == home_levels.get(l1) and
            state.post_levels.get(l2) == home_levels.get(l2)
        )
        if same_l2:
            return FamiliarityLevel.SAME_L2

        return FamiliarityLevel.SAME_BRANCH

    def _parse_home_unit(self, home_unit: str) -> Tuple[Optional[str], Dict[str, str]]:
        """Parse a home_unit string into branch and level mapping."""
        if ":" not in home_unit:
            return None, {}
        branch_part, path_part = home_unit.split(":", 1)
        levels = path_part.split("/") if path_part else []

        branch = branch_part.strip()
        try:
            branch_enum = Branch(branch)
        except ValueError:
            return branch, {}
        level_names = self.hierarchy.get_branch_levels(branch_enum)
        mapping: Dict[str, str] = {}
        for name, value in zip(level_names, levels):
            mapping[name] = value
        return branch, mapping

    def _select_levels(
        self,
        levels: List[str],
        familiarity: FamiliarityLevel,
        clerk: Clerk,
    ) -> List[str]:
        """Select which levels to include based on familiarity and format."""
        if familiarity == FamiliarityLevel.SAME_L3:
            include = [levels[-1]]
        elif familiarity == FamiliarityLevel.SAME_L2:
            include = levels[2:]
        elif familiarity == FamiliarityLevel.SAME_BRANCH:
            include = levels[1:]
        else:
            include = list(levels)

        if not clerk.unit_format.include_sector and levels:
            include = [lvl for lvl in include if lvl != levels[0]]
        if not clerk.unit_format.include_level2 and len(levels) > 1:
            include = [lvl for lvl in include if lvl != levels[1]]
        if not clerk.unit_format.include_lowest_levels and len(levels) > 3:
            include = [lvl for lvl in include if levels.index(lvl) <= 2]

        if not include and levels:
            include = [levels[-1]]

        return include

    def _format_unit(self, state: State, levels: List[str], clerk: Clerk) -> str:
        """Format unit string from selected levels."""
        parts = [(lvl, state.post_levels.get(lvl, "")) for lvl in levels]

        if clerk.unit_format.phonetic_letters:
            parts = [(lvl, self._phoneticize(value)) for lvl, value in parts]

        style = clerk.unit_format.style
        if style in (UnitFormatStyle.LABELED_HIERARCHICAL, UnitFormatStyle.LABELED_FULL):
            unit_text = self._format_labeled(parts, clerk)
        elif style == UnitFormatStyle.LABELED_MICRO:
            unit_text = self._format_labeled(parts, clerk, micro=True)
        elif style in (UnitFormatStyle.SLASH_POSITIONAL, UnitFormatStyle.SLASH_COMPACT):
            unit_text = self._format_slash(parts, clerk)
        elif style == UnitFormatStyle.RUNON_COMPACT:
            unit_text = self._format_runon(parts, clerk)
        elif style == UnitFormatStyle.PHONETIC_INFORMAL:
            unit_text = self._format_runon(parts, clerk)
        elif style == UnitFormatStyle.MINIMAL:
            unit_text = self._format_minimal(parts, clerk)
        else:
            unit_text = self._format_labeled(parts, clerk)

        if clerk.unit_format.include_branch:
            branch_abbrev = self.hierarchy.get_branch_abbreviation(state.branch)
            unit_text = f"{unit_text} {branch_abbrev}".strip()
        if clerk.unit_format.branch_suffix:
            branch_abbrev = self.hierarchy.get_branch_abbreviation(state.branch)
            unit_text = f"{unit_text}-{branch_abbrev}".strip("-")

        return unit_text.strip()

    def _format_labeled(self, parts: List[Tuple[str, str]], clerk: Clerk, micro: bool = False) -> str:
        """Format with labels for each level."""
        formatted: List[str] = []
        for level, value in parts:
            if clerk.unit_format.omit_level_names:
                formatted.append(value)
                continue
            label = self._level_label(level, clerk, micro)
            formatted.append(f"{label} {value}".strip())
        return clerk.unit_format.separator.join(formatted)

    def _format_slash(self, parts: List[Tuple[str, str]], clerk: Clerk) -> str:
        """Format as slash positional."""
        values = [value for _, value in parts]
        if clerk.unit_format.orientation == "child_over_parent":
            values = list(reversed(values))
        return clerk.unit_format.separator.join(values)

    def _format_runon(self, parts: List[Tuple[str, str]], clerk: Clerk) -> str:
        """Format as compact runon text."""
        values = [value for _, value in parts]
        if clerk.unit_format.orientation == "child_over_parent":
            values = list(reversed(values))
        return clerk.unit_format.separator.join(values)

    def _format_minimal(self, parts: List[Tuple[str, str]], clerk: Clerk) -> str:
        """Format minimal unit string without labels."""
        values = [value for _, value in parts]
        if clerk.unit_format.orientation == "child_over_parent":
            values = list(reversed(values))
        return clerk.unit_format.separator.join(values)

    def _level_label(self, level: str, clerk: Clerk, micro: bool) -> str:
        """Resolve level label based on style."""
        if micro or clerk.unit_format.label_style == "micro":
            return LEVEL_LABELS_MICRO.get(level, level.title())
        if clerk.unit_format.label_style == "full":
            return LEVEL_LABELS.get(level, level.title())
        return LEVEL_LABELS_ABBREV.get(level, level.title())

    def _phoneticize(self, value: str) -> str:
        """Expand letters into phonetic words when possible."""
        return PHONETIC_LETTERS.get(value, value)

    def _combine_fields(self, name: str, rank: str, unit: str, clerk: Clerk) -> str:
        """Combine name, rank, and unit based on clerk style."""
        if clerk.rank_format.style == RankStyle.PREFIX:
            return f"{rank} {name} {unit}".strip()
        if clerk.rank_format.style == RankStyle.SUFFIX:
            return f"{name} {rank} {unit}".strip()
        if clerk.rank_format.style == RankStyle.MIXED:
            if self.rng.random() < 0.5:
                return f"{rank} {name} {unit}".strip()
            return f"{name} {rank} {unit}".strip()
        if clerk.rank_format.style == RankStyle.SEPARATE_COLUMN:
            return f"{name} {unit}  {rank}".strip()
        return f"{rank} {name} {unit}".strip()

    def _extract_structural_signals(
        self,
        unit_string: str,
        state: State,
        levels_provided: List[str],
    ) -> List[str]:
        """Extract structural signals from rendered unit string."""
        signals: List[str] = []

        unique_terms = self.hierarchy.get_structural_signals_for_branch(state.branch)
        for term in unique_terms:
            if term.lower() in unit_string.lower():
                signals.append(f"branch_unique:{term}")

        if len(levels_provided) >= 4:
            signals.append("depth:4+")
        if len(levels_provided) == 5:
            signals.append("depth:5")

        return signals
