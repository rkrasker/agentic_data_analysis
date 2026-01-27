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

GREEK_LETTERS = {
    "Alpha",
    "Beta",
    "Gamma",
    "Delta",
    "Epsilon",
    "Zeta",
    "Eta",
    "Theta",
    "Iota",
    "Kappa",
    "Lambda",
    "Omega",
}

ALTERNATIVE_SEPARATORS = {
    ", ": [" ", "/", "/ ", " - "],
    "/": [" ", ", ", "-"],
    "-": [" ", "/"],
    " ": ["/", ", ", "-"],
}

TENDENCY_RETENTION = {
    "very_high": (0.90, 1.00),
    "high": (0.70, 0.90),
    "medium": (0.50, 0.70),
    "low": (0.30, 0.50),
    "very_low": (0.20, 0.40),
}

FAMILIARITY_LABEL_OMISSION_BOOST = {
    FamiliarityLevel.SAME_L3: 0.70,
    FamiliarityLevel.SAME_L2: 0.45,
    FamiliarityLevel.SAME_BRANCH: 0.20,
    FamiliarityLevel.DIFFERENT_BRANCH: 0.0,
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
        raw_text = self._apply_imperfections(raw_text, clerk, unit_text)

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
            familiarity,
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

        include = self._apply_path_completeness_tendency(levels, include, clerk)

        if not clerk.unit_format.include_sector and levels:
            include = [lvl for lvl in include if lvl != levels[0]]
        if not clerk.unit_format.include_level2 and len(levels) > 1:
            include = [lvl for lvl in include if lvl != levels[1]]
        if not clerk.unit_format.include_lowest_levels and len(levels) > 3:
            include = [lvl for lvl in include if levels.index(lvl) <= 2]

        if not include and levels:
            include = [levels[-1]]

        return include

    def _apply_path_completeness_tendency(
        self,
        levels: List[str],
        candidates: List[str],
        clerk: Clerk,
    ) -> List[str]:
        """Drop higher echelon levels based on path completeness tendency."""
        if not candidates:
            return candidates

        tendency = getattr(clerk, "path_completeness_tendency", "medium")
        lo, hi = TENDENCY_RETENTION.get(tendency, (0.50, 0.70))
        target_retention = self.rng.uniform(lo, hi)
        target_count = max(1, round(len(candidates) * target_retention))

        if len(candidates) <= target_count:
            return candidates

        return self._drop_levels_to_target(candidates, levels, target_count)

    def _drop_levels_to_target(
        self,
        candidates: List[str],
        all_levels: List[str],
        target_count: int,
    ) -> List[str]:
        """Drop levels with a bias toward higher echelons."""
        remaining = list(candidates)
        if len(remaining) <= target_count:
            return remaining

        while len(remaining) > target_count and len(remaining) > 1:
            weights = []
            for level in remaining:
                idx = all_levels.index(level)
                weight = max(len(all_levels) - idx, 1)
                weights.append(weight * weight)
            drop_index = self._weighted_choice_index(weights)
            remaining.pop(drop_index)

        return remaining

    def _weighted_choice_index(self, weights: List[int]) -> int:
        """Select an index using integer weights."""
        total = sum(weights)
        if total <= 0:
            return 0
        roll = self.rng.uniform(0, total)
        upto = 0.0
        for idx, weight in enumerate(weights):
            upto += weight
            if roll <= upto:
                return idx
        return len(weights) - 1

    def _format_unit(
        self,
        state: State,
        levels: List[str],
        clerk: Clerk,
        familiarity: FamiliarityLevel = FamiliarityLevel.DIFFERENT_BRANCH,
    ) -> str:
        """Format unit string from selected levels."""
        parts = [(lvl, state.post_levels.get(lvl, "")) for lvl in levels]

        if clerk.unit_format.phonetic_letters:
            parts = [(lvl, self._phoneticize(value)) for lvl, value in parts]

        if clerk.unit_format.value_abbreviation_rate > 0:
            abbreviated_parts = []
            for lvl, value in parts:
                if self.rng.random() < clerk.unit_format.value_abbreviation_rate:
                    abbreviated_parts.append((lvl, self._abbreviate_value(value)))
                else:
                    abbreviated_parts.append((lvl, value))
            parts = abbreviated_parts

        style = clerk.unit_format.style
        if style in (UnitFormatStyle.LABELED_HIERARCHICAL, UnitFormatStyle.LABELED_FULL):
            unit_text = self._format_labeled(parts, clerk, familiarity=familiarity)
        elif style == UnitFormatStyle.LABELED_MICRO:
            unit_text = self._format_labeled(parts, clerk, micro=True, familiarity=familiarity)
        elif style in (UnitFormatStyle.SLASH_POSITIONAL, UnitFormatStyle.SLASH_COMPACT):
            unit_text = self._format_slash(parts, clerk)
        elif style == UnitFormatStyle.RUNON_COMPACT:
            unit_text = self._format_runon(parts, clerk)
        elif style == UnitFormatStyle.PHONETIC_INFORMAL:
            unit_text = self._format_runon(parts, clerk)
        elif style == UnitFormatStyle.MINIMAL:
            unit_text = self._format_minimal(parts, clerk)
        else:
            unit_text = self._format_labeled(parts, clerk, familiarity=familiarity)

        unit_text = self._mix_delimiters(unit_text, clerk)

        if clerk.unit_format.include_branch:
            branch_abbrev = self.hierarchy.get_branch_abbreviation(state.branch)
            unit_text = f"{unit_text} {branch_abbrev}".strip()
        if clerk.unit_format.branch_suffix:
            branch_abbrev = self.hierarchy.get_branch_abbreviation(state.branch)
            unit_text = f"{unit_text}-{branch_abbrev}".strip("-")

        return unit_text.strip()

    def _format_labeled(
        self,
        parts: List[Tuple[str, str]],
        clerk: Clerk,
        micro: bool = False,
        familiarity: FamiliarityLevel = FamiliarityLevel.DIFFERENT_BRANCH,
    ) -> str:
        """Format with labels for each level."""
        formatted: List[str] = []
        omit_all = clerk.unit_format.omit_level_names
        base_omission = clerk.unit_format.label_omission_rate
        familiarity_boost = FAMILIARITY_LABEL_OMISSION_BOOST.get(familiarity, 0.0)
        for idx, (level, value) in enumerate(parts):
            if omit_all:
                formatted.append(value)
                continue
            echelon_bonus = 0.0
            if len(parts) > 1:
                position_ratio = idx / (len(parts) - 1)
                echelon_bonus = position_ratio * 0.2
            effective_rate = min(1.0, base_omission + echelon_bonus + familiarity_boost)
            if effective_rate > 0 and self.rng.random() < effective_rate:
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

    def _abbreviate_value(self, value: str) -> str:
        """Abbreviate a named designator value."""
        if not value:
            return value
        if len(value) <= 2 or value.isdigit():
            return value

        if value in GREEK_LETTERS:
            if self.rng.random() < 0.5:
                return value[:2]
            return value

        if len(value) <= 4:
            return value[:2]

        abbrev_len = self.rng.choice([2, 3, 4])
        if self.rng.random() < 0.5:
            return value[:abbrev_len]

        skeleton = value[0] + "".join(c for c in value[1:] if c.lower() not in "aeiou")
        if len(skeleton) >= 2:
            return skeleton[:abbrev_len + 1]
        return value[:abbrev_len]

    def _mix_delimiters(self, unit_text: str, clerk: Clerk) -> str:
        """Stochastically replace some delimiters in the unit string."""
        mix_rate = 1.0 - clerk.consistency.format_lock
        if mix_rate <= 0 or self.rng.random() > mix_rate:
            return unit_text

        sep = clerk.unit_format.separator
        alternatives = ALTERNATIVE_SEPARATORS.get(sep, [])
        if not alternatives:
            return unit_text

        parts = unit_text.split(sep)
        if len(parts) <= 1:
            return unit_text

        result_parts = [parts[0]]
        for part in parts[1:]:
            if self.rng.random() < 0.4:
                new_sep = self.rng.choice(alternatives)
                result_parts.append(new_sep + part.lstrip())
            else:
                result_parts.append(sep + part)
        return "".join(result_parts)

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

    def _apply_imperfections(self, text: str, clerk: Clerk, unit_text: Optional[str] = None) -> str:
        """Apply character-level imperfections to rendered text."""
        result = text
        imp = clerk.imperfections

        if self.rng.random() < imp.trailing_off and len(result) > 2:
            cut_point = self.rng.randint(len(result) // 2, len(result) - 1)
            result = result[:cut_point]

        if unit_text and self.rng.random() < imp.abbreviation_inconsistency:
            altered_unit = self._apply_abbreviation_inconsistency(unit_text)
            if altered_unit != unit_text and unit_text in result:
                result = result.replace(unit_text, altered_unit, 1)

        if self.rng.random() < imp.typo_rate:
            result = self._inject_typo(result)

        if self.rng.random() < imp.mid_entry_corrections:
            result = self._apply_mid_entry_correction(result)

        if unit_text and self.rng.random() < imp.incomplete_unit:
            altered_unit = self._drop_unit_component(unit_text)
            if altered_unit != unit_text and unit_text in result:
                result = result.replace(unit_text, altered_unit, 1)

        if self.rng.random() < imp.column_bleed:
            result = self._apply_column_bleed(result)

        return result

    def _apply_abbreviation_inconsistency(self, unit_text: str) -> str:
        """Swap one unit label variant for a mixed abbreviation style."""
        variants = {}
        for level, label in LEVEL_LABELS.items():
            variants.setdefault(level, set()).add(label)
        for level, label in LEVEL_LABELS_ABBREV.items():
            variants.setdefault(level, set()).add(label)
        for level, label in LEVEL_LABELS_MICRO.items():
            variants.setdefault(level, set()).add(label)

        matches = []
        for level, labels in variants.items():
            for label in labels:
                token = f"{label} "
                if token in unit_text:
                    matches.append((level, label))

        if not matches:
            return unit_text

        level, current = self.rng.choice(matches)
        options = [v for v in variants[level] if v != current]
        if not options:
            return unit_text

        replacement = self.rng.choice(options)
        return unit_text.replace(f"{current} ", f"{replacement} ", 1)

    def _inject_typo(self, text: str) -> str:
        """Inject a simple typo into the text."""
        if not text:
            return text

        ops = ["transpose", "substitute", "omit", "double"]
        op = self.rng.choice(ops)
        idx = self.rng.randint(0, max(len(text) - 1, 0))

        if op == "transpose" and len(text) > 2 and idx < len(text) - 1:
            chars = list(text)
            chars[idx], chars[idx + 1] = chars[idx + 1], chars[idx]
            return "".join(chars)

        if op == "omit" and len(text) > 1:
            return text[:idx] + text[idx + 1:]

        substitutions = {
            "l": "1",
            "O": "0",
            "rn": "m",
            "m": "rn",
            "S": "5",
            "E": "F",
        }
        for key, value in substitutions.items():
            if key in text:
                return text.replace(key, value, 1)

        if op == "double" and len(text) > 1:
            return text[:idx] + text[idx] + text[idx:]

        if op == "substitute" and len(text) > 1:
            alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
            if text[idx].isalpha():
                replacement = self.rng.choice(alphabet)
                return text[:idx] + replacement + text[idx + 1:]

        return text

    def _apply_mid_entry_correction(self, text: str) -> str:
        """Insert a plain-text correction pattern into the entry."""
        for i, ch in enumerate(text):
            if ch.isdigit():
                corrected = str((int(ch) + 1) % 10)
                return f"{text[:i]}{ch} {corrected}{text[i + 1:]}"
        return text

    def _drop_unit_component(self, unit_text: str) -> str:
        """Drop a unit component from the unit string."""
        separators = ["/", ",", ";"]
        for sep in separators:
            if sep in unit_text:
                parts = [p.strip() for p in unit_text.split(sep) if p.strip()]
                if len(parts) > 1:
                    drop_index = self.rng.randint(0, len(parts) - 2)
                    parts.pop(drop_index)
                    return f"{sep} ".join(parts) if sep != "/" else sep.join(parts)
        tokens = unit_text.split()
        if len(tokens) > 2:
            drop_index = self.rng.randint(1, len(tokens) - 2)
            tokens.pop(drop_index)
            return " ".join(tokens)
        return unit_text

    def _apply_column_bleed(self, text: str) -> str:
        """Merge delimiters between adjacent fields."""
        for i in range(1, len(text) - 1):
            if text[i] == " " and text[i - 1].isalnum() and text[i + 1].isalnum():
                return text[:i] + text[i + 1:]
        return text
