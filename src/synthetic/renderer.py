"""
Renderer: Render soldier truth records to raw text using clerk formats.

Each clerk has locked habits for name, rank, and unit formatting.
The renderer applies these consistently.
"""

import random
from typing import Dict, List, Optional, Any

from .models import (
    Clerk,
    Soldier,
    Assignment,
    RankStyle,
    RankForm,
    UnitFormatStyle,
    VocabularyDensity,
)
from .hierarchy_loader import HierarchyLoader


# Rank canonical to variants mapping
RANK_VARIANTS = {
    "Private": {"proper_abbrev": "Pvt", "caps_abbrev": "PVT", "phonetic": "Pvt"},
    "Private First Class": {"proper_abbrev": "Pfc", "caps_abbrev": "PFC", "phonetic": "Pfc"},
    "Corporal": {"proper_abbrev": "Cpl", "caps_abbrev": "CPL", "phonetic": "Cpl"},
    "Sergeant": {"proper_abbrev": "Sgt", "caps_abbrev": "SGT", "phonetic": "Sgt"},
    "Staff Sergeant": {"proper_abbrev": "S/Sgt", "caps_abbrev": "SSGT", "phonetic": "SSgt"},
    "Technical Sergeant": {"proper_abbrev": "T/Sgt", "caps_abbrev": "TSGT", "phonetic": "TSgt"},
    "First Sergeant": {"proper_abbrev": "1st Sgt", "caps_abbrev": "1SGT", "phonetic": "1st Sgt"},
    "Master Sergeant": {"proper_abbrev": "M/Sgt", "caps_abbrev": "MSGT", "phonetic": "MSgt"},
    "Technician Fifth Grade": {"proper_abbrev": "T/5", "caps_abbrev": "T5", "phonetic": "T5"},
    "Technician Fourth Grade": {"proper_abbrev": "T/4", "caps_abbrev": "T4", "phonetic": "T4"},
    "Second Lieutenant": {"proper_abbrev": "2nd Lt", "caps_abbrev": "2LT", "phonetic": "2nd Lt"},
    "First Lieutenant": {"proper_abbrev": "1st Lt", "caps_abbrev": "1LT", "phonetic": "1st Lt"},
    "Captain": {"proper_abbrev": "Capt", "caps_abbrev": "CPT", "phonetic": "Capt"},
    "Major": {"proper_abbrev": "Maj", "caps_abbrev": "MAJ", "phonetic": "Maj"},
}

# Phonetic company names
PHONETIC_COMPANIES = {
    "A": "Able", "B": "Baker", "C": "Charlie", "D": "Dog",
    "E": "Easy", "F": "Fox", "G": "George", "H": "How",
    "I": "Item", "K": "King", "L": "Love", "M": "Mike",
}

# Ordinal suffixes
ORDINALS = {
    "1": "1st", "2": "2nd", "3": "3rd", "4": "4th", "5": "5th",
    "6": "6th", "7": "7th", "8": "8th", "9": "9th", "10": "10th",
    "11": "11th", "12": "12th", "13": "13th", "14": "14th",
}


class Renderer:
    """
    Renders soldier truth records to raw text using clerk formats.

    Each clerk has locked formatting habits that are applied consistently.
    """

    def __init__(
        self,
        hierarchy_loader: HierarchyLoader,
        random_seed: Optional[int] = None,
    ):
        """
        Initialize the renderer.

        Args:
            hierarchy_loader: Loader for unit hierarchy data
            random_seed: Seed for reproducibility
        """
        self.rng = random.Random(random_seed)
        self.hierarchy = hierarchy_loader

    def render(self, soldier: Soldier, clerk: Clerk) -> str:
        """
        Render a soldier record using the clerk's format.

        Args:
            soldier: The soldier truth record
            clerk: The clerk producing the entry

        Returns:
            Rendered raw text
        """
        # Render components
        name = self.render_name(soldier, clerk)
        rank = self.render_rank(soldier, clerk)
        unit = self.render_unit(soldier, clerk)

        # Combine based on rank style
        if clerk.rank_format.style == RankStyle.PREFIX:
            return f"{rank} {name} {unit}".strip()
        elif clerk.rank_format.style == RankStyle.SUFFIX:
            return f"{name} {rank} {unit}".strip()
        elif clerk.rank_format.style == RankStyle.MIXED:
            # Random placement
            if self.rng.random() < 0.5:
                return f"{rank} {name} {unit}".strip()
            else:
                return f"{name} {rank} {unit}".strip()
        elif clerk.rank_format.style == RankStyle.SEPARATE_COLUMN:
            # Rank at end, separated
            return f"{name} {unit}  {rank}".strip()
        else:
            return f"{rank} {name} {unit}".strip()

    def render_name(self, soldier: Soldier, clerk: Clerk) -> str:
        """
        Render a soldier's name using the clerk's format.

        Args:
            soldier: The soldier truth record
            clerk: The clerk producing the entry

        Returns:
            Formatted name string
        """
        template = clerk.name_format.template

        # Get name components
        last = soldier.name_last
        first = soldier.name_first
        middle = soldier.name_middle or ""
        fi = first[0] if first else ""
        mi = middle[0] if middle else ""

        # Handle middle initial dropping
        if middle and self.rng.random() < clerk.name_format.drop_middle_rate:
            mi = ""
            middle = ""

        # Apply template
        result = template
        result = result.replace("{LAST}", last)
        result = result.replace("{FIRST}", first)
        result = result.replace("{FI}", fi)
        result = result.replace("{MI}", mi)

        # Clean up empty middle initial patterns
        result = result.replace(" .", "")
        result = result.replace(".,", ",")
        result = result.replace(". ", " ")
        result = result.replace("  ", " ")

        return result.strip()

    def render_rank(self, soldier: Soldier, clerk: Clerk) -> str:
        """
        Render a soldier's rank using the clerk's format.

        Args:
            soldier: The soldier truth record
            clerk: The clerk producing the entry

        Returns:
            Formatted rank string, or empty if omitted
        """
        # Check if rank should be omitted
        if self.rng.random() < clerk.rank_format.omit_rate:
            return ""

        canonical_rank = soldier.rank
        form = clerk.rank_format.form.value

        # Look up variant
        variants = RANK_VARIANTS.get(canonical_rank, {})
        rendered = variants.get(form, canonical_rank)

        return rendered

    def render_unit(self, soldier: Soldier, clerk: Clerk) -> str:
        """
        Render a soldier's unit using the clerk's format.

        Args:
            soldier: The soldier truth record
            clerk: The clerk producing the entry

        Returns:
            Formatted unit string
        """
        assignment = soldier.assignment
        style = clerk.unit_format.style

        # Route to appropriate renderer
        if style == UnitFormatStyle.LABELED_HIERARCHICAL:
            return self._render_labeled_hierarchical(assignment, clerk)
        elif style == UnitFormatStyle.LABELED_FULL:
            return self._render_labeled_full(assignment, clerk)
        elif style == UnitFormatStyle.LABELED_MICRO:
            return self._render_labeled_micro(assignment, clerk)
        elif style == UnitFormatStyle.SLASH_POSITIONAL:
            return self._render_slash_positional(assignment, clerk)
        elif style == UnitFormatStyle.SLASH_COMPACT:
            return self._render_slash_compact(assignment, clerk)
        elif style == UnitFormatStyle.RUNON_COMPACT:
            return self._render_runon_compact(assignment, clerk)
        elif style == UnitFormatStyle.PHONETIC_INFORMAL:
            return self._render_phonetic_informal(assignment, clerk)
        elif style == UnitFormatStyle.MINIMAL:
            return self._render_minimal(assignment, clerk)
        elif style == UnitFormatStyle.AAF_STANDARD:
            return self._render_aaf_standard(assignment, clerk)
        elif style == UnitFormatStyle.COMPACT_AAF:
            return self._render_compact_aaf(assignment, clerk)
        elif style == UnitFormatStyle.MARINE_STANDARD:
            return self._render_marine_standard(assignment, clerk)
        else:
            return self._render_labeled_hierarchical(assignment, clerk)

    def _render_labeled_hierarchical(
        self,
        assignment: Assignment,
        clerk: Clerk,
    ) -> str:
        """Co E, 2nd Bn, 116th Inf, 29th Div"""
        parts = []
        sep = clerk.unit_format.separator

        if assignment.company and clerk.unit_format.include_company:
            parts.append(f"Co {assignment.company}")

        if assignment.battalion:
            bn = self._ordinal(assignment.battalion)
            parts.append(f"{bn} Bn")

        if assignment.regiment and clerk.unit_format.include_regiment:
            reg = self._ordinal(assignment.regiment)
            parts.append(f"{reg} Inf")

        if clerk.unit_format.include_division:
            div_name = self._get_division_short(assignment.component_id)
            parts.append(div_name)

        return sep.join(parts)

    def _render_labeled_full(
        self,
        assignment: Assignment,
        clerk: Clerk,
    ) -> str:
        """Co E, 2nd Bn, 116th Inf Regt, 29th Inf Div"""
        parts = []
        sep = clerk.unit_format.separator

        if assignment.company and clerk.unit_format.include_company:
            parts.append(f"Co {assignment.company}")

        if assignment.battalion:
            bn = self._ordinal(assignment.battalion)
            parts.append(f"{bn} Bn")

        if assignment.regiment and clerk.unit_format.include_regiment:
            reg = self._ordinal(assignment.regiment)
            div_type = self.hierarchy.get_division_type(assignment.component_id)
            if div_type == "marine":
                parts.append(f"{reg} Mar Regt")
            elif div_type == "airborne":
                parts.append(f"{reg} PIR")
            elif div_type == "mountain":
                parts.append(f"{reg} Mtn Inf Regt")
            else:
                parts.append(f"{reg} Inf Regt")

        if clerk.unit_format.include_division:
            div_name = self._get_division_full(assignment.component_id)
            parts.append(div_name)

        return sep.join(parts)

    def _render_labeled_micro(
        self,
        assignment: Assignment,
        clerk: Clerk,
    ) -> str:
        """E Co 2Bn 116Inf"""
        parts = []

        if assignment.company and clerk.unit_format.include_company:
            parts.append(f"{assignment.company} Co")

        if assignment.battalion:
            parts.append(f"{assignment.battalion}Bn")

        if assignment.regiment and clerk.unit_format.include_regiment:
            parts.append(f"{assignment.regiment}Inf")

        return " ".join(parts)

    def _render_slash_positional(
        self,
        assignment: Assignment,
        clerk: Clerk,
    ) -> str:
        """E/2/116/29ID or 116/2/E depending on orientation"""
        parts = []

        if clerk.unit_format.orientation == "child_over_parent":
            # Company -> Battalion -> Regiment -> Division
            if assignment.company and clerk.unit_format.include_company:
                parts.append(assignment.company)
            if assignment.battalion:
                parts.append(assignment.battalion)
            if assignment.regiment and clerk.unit_format.include_regiment:
                parts.append(assignment.regiment)
            if clerk.unit_format.include_division:
                div_suffix = self._get_division_suffix(assignment.component_id)
                parts.append(div_suffix)
        else:
            # Division -> Regiment -> Battalion -> Company
            if clerk.unit_format.include_division:
                div_suffix = self._get_division_suffix(assignment.component_id)
                parts.append(div_suffix)
            if assignment.regiment and clerk.unit_format.include_regiment:
                parts.append(assignment.regiment)
            if assignment.battalion:
                parts.append(assignment.battalion)
            if assignment.company and clerk.unit_format.include_company:
                parts.append(assignment.company)

        return "/".join(parts)

    def _render_slash_compact(
        self,
        assignment: Assignment,
        clerk: Clerk,
    ) -> str:
        """A/1/7 or A/1/7 1MARDIV"""
        parts = []

        if assignment.company:
            parts.append(assignment.company)
        if assignment.battalion:
            parts.append(assignment.battalion)
        if assignment.regiment:
            parts.append(assignment.regiment)

        result = "/".join(parts)

        if clerk.unit_format.include_division and clerk.unit_format.division_suffix:
            div_suffix = self._get_division_suffix(assignment.component_id)
            result = f"{result} {div_suffix}"

        return result

    def _render_runon_compact(
        self,
        assignment: Assignment,
        clerk: Clerk,
    ) -> str:
        """E2-116"""
        sep = clerk.unit_format.separator
        parts = []

        if assignment.company:
            parts.append(assignment.company)
        if assignment.battalion:
            parts.append(assignment.battalion)

        company_bn = "".join(parts)

        if assignment.regiment:
            return f"{company_bn}{sep}{assignment.regiment}"

        return company_bn

    def _render_phonetic_informal(
        self,
        assignment: Assignment,
        clerk: Clerk,
    ) -> str:
        """Easy Co 116"""
        parts = []

        if assignment.company:
            phonetic = PHONETIC_COMPANIES.get(assignment.company, assignment.company)
            parts.append(f"{phonetic} Co")

        if assignment.regiment:
            reg = self._ordinal(assignment.regiment)
            parts.append(reg)

        return " ".join(parts)

    def _render_minimal(
        self,
        assignment: Assignment,
        clerk: Clerk,
    ) -> str:
        """116th or 2/116"""
        if assignment.battalion and assignment.regiment:
            return f"{assignment.battalion}/{assignment.regiment}"
        elif assignment.regiment:
            return self._ordinal(assignment.regiment)
        return ""

    def _render_aaf_standard(
        self,
        assignment: Assignment,
        clerk: Clerk,
    ) -> str:
        """3rd Sq, 91st BG, 8th AF"""
        parts = []
        sep = clerk.unit_format.separator

        if assignment.squadron:
            sq = self._ordinal(assignment.squadron)
            parts.append(f"{sq} Sq")

        if assignment.bomb_group:
            bg = self._ordinal(assignment.bomb_group)
            parts.append(f"{bg} BG")

        if clerk.unit_format.include_air_force:
            # Extract AF number from component_id
            af_num = self._get_af_number(assignment.component_id)
            parts.append(f"{af_num} AF")

        return sep.join(parts)

    def _render_compact_aaf(
        self,
        assignment: Assignment,
        clerk: Clerk,
    ) -> str:
        """91BG-3 or 3/91"""
        if assignment.bomb_group and assignment.squadron:
            if self.rng.random() < 0.5:
                return f"{assignment.bomb_group}BG-{assignment.squadron}"
            else:
                return f"{assignment.squadron}/{assignment.bomb_group}"
        elif assignment.bomb_group:
            return f"{assignment.bomb_group}BG"
        return ""

    def _render_marine_standard(
        self,
        assignment: Assignment,
        clerk: Clerk,
    ) -> str:
        """Co A, 1st Bn, 7th Mar, 1st MarDiv"""
        parts = []
        sep = clerk.unit_format.separator

        if assignment.company and clerk.unit_format.include_company:
            parts.append(f"Co {assignment.company}")

        if assignment.battalion:
            bn = self._ordinal(assignment.battalion)
            parts.append(f"{bn} Bn")

        if assignment.regiment and clerk.unit_format.include_regiment:
            reg = self._ordinal(assignment.regiment)
            style = clerk.unit_format.marine_regiment_style
            parts.append(f"{reg} {style}")

        if clerk.unit_format.include_division:
            div_name = self._get_division_short(assignment.component_id)
            parts.append(div_name)

        return sep.join(parts)

    def _ordinal(self, num: str) -> str:
        """Convert number to ordinal form."""
        if num in ORDINALS:
            return ORDINALS[num]

        # Handle larger numbers
        try:
            n = int(num)
            if 10 <= n % 100 <= 20:
                suffix = "th"
            else:
                suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
            return f"{n}{suffix}"
        except ValueError:
            return num

    def _get_division_short(self, component_id: str) -> str:
        """Get short division name (29th Div, 1st MarDiv, etc.)."""
        div_type = self.hierarchy.get_division_type(component_id)
        name = self.hierarchy.get_canonical_name(component_id)

        # Extract number
        import re
        match = re.search(r'(\d+)', name)
        num = match.group(1) if match else ""
        ord_num = self._ordinal(num)

        if div_type == "marine":
            return f"{ord_num} MarDiv"
        elif div_type == "airborne":
            return f"{ord_num} AB"
        elif div_type == "armored":
            return f"{ord_num} AD"
        elif div_type == "mountain":
            return f"{ord_num} Mtn"
        elif div_type == "air_force":
            return f"{ord_num} AF"
        else:
            return f"{ord_num} Div"

    def _get_division_full(self, component_id: str) -> str:
        """Get full division name (29th Inf Div, 1st MarDiv, etc.)."""
        div_type = self.hierarchy.get_division_type(component_id)
        name = self.hierarchy.get_canonical_name(component_id)

        import re
        match = re.search(r'(\d+)', name)
        num = match.group(1) if match else ""
        ord_num = self._ordinal(num)

        if div_type == "marine":
            return f"{ord_num} Mar Div"
        elif div_type == "airborne":
            return f"{ord_num} Abn Div"
        elif div_type == "armored":
            return f"{ord_num} Armd Div"
        elif div_type == "mountain":
            return f"{ord_num} Mtn Div"
        else:
            return f"{ord_num} Inf Div"

    def _get_division_suffix(self, component_id: str) -> str:
        """Get compact division suffix (29ID, 1MARDIV, etc.)."""
        div_type = self.hierarchy.get_division_type(component_id)
        name = self.hierarchy.get_canonical_name(component_id)

        import re
        match = re.search(r'(\d+)', name)
        num = match.group(1) if match else ""

        if div_type == "marine":
            return f"{num}MARDIV"
        elif div_type == "airborne":
            return f"{num}AB"
        elif div_type == "armored":
            return f"{num}AD"
        elif div_type == "mountain":
            return f"{num}MTN"
        else:
            return f"{num}ID"

    def _get_af_number(self, component_id: str) -> str:
        """Extract Air Force number from component ID."""
        import re
        match = re.search(r'(\d+)', component_id)
        if match:
            return self._ordinal(match.group(1))
        return ""

    def apply_imperfections(
        self,
        text: str,
        clerk: Clerk,
        position_in_batch: float,
    ) -> str:
        """
        Apply behavioral imperfections to rendered text.

        Args:
            text: The rendered text
            clerk: The clerk producing the entry
            position_in_batch: Position ratio (0.0 to 1.0)

        Returns:
            Text with imperfections applied
        """
        result = text
        imp = clerk.imperfections

        # Typos
        if self.rng.random() < imp.typo_rate:
            result = self._apply_typo(result)

        # Abbreviation inconsistency
        if self.rng.random() < imp.abbreviation_inconsistency:
            result = self._vary_abbreviation(result)

        # Trailing off (more likely late in batch)
        trailing_rate = imp.trailing_off
        if position_in_batch > 0.7:
            trailing_rate *= 1.5
        if self.rng.random() < trailing_rate:
            result = self._apply_trailing_off(result)

        # Mid-entry corrections
        if self.rng.random() < imp.mid_entry_corrections:
            result = self._apply_correction(result)

        # Column bleed (spacing issues)
        if self.rng.random() < imp.column_bleed:
            result = self._apply_column_bleed(result)

        return result

    def _apply_typo(self, text: str) -> str:
        """Apply a random typo."""
        if len(text) < 5:
            return text

        typo_type = self.rng.choice(["duplicate", "transpose", "drop"])

        if typo_type == "duplicate":
            pos = self.rng.randint(1, len(text) - 2)
            return text[:pos] + text[pos] + text[pos:]
        elif typo_type == "transpose":
            pos = self.rng.randint(1, len(text) - 2)
            return text[:pos] + text[pos + 1] + text[pos] + text[pos + 2:]
        elif typo_type == "drop":
            pos = self.rng.randint(1, len(text) - 2)
            return text[:pos] + text[pos + 1:]

        return text

    def _vary_abbreviation(self, text: str) -> str:
        """Vary an abbreviation style."""
        variations = [
            ("Sgt", "SGT"), ("SGT", "Sgt"),
            ("Cpl", "CPL"), ("CPL", "Cpl"),
            ("Pvt", "PVT"), ("PVT", "Pvt"),
            ("Co", "CO"), ("Bn", "BN"),
            ("Inf", "INF"), ("Div", "DIV"),
        ]

        for old, new in variations:
            if old in text:
                return text.replace(old, new, 1)

        return text

    def _apply_trailing_off(self, text: str) -> str:
        """Truncate the text (trailing off)."""
        # Find a good break point
        for sep in [", ", " "]:
            if sep in text:
                parts = text.rsplit(sep, 1)
                if len(parts) > 1:
                    return parts[0]
        return text

    def _apply_correction(self, text: str) -> str:
        """Apply a strikethrough correction."""
        # Find a word to "correct"
        words = text.split()
        if len(words) < 3:
            return text

        idx = self.rng.randint(1, len(words) - 1)
        original = words[idx]

        # Create correction
        if self.rng.random() < 0.5:
            corrected = f"~~{original}~~ {original}"
        else:
            corrected = f"[{original}]"

        words[idx] = corrected
        return " ".join(words)

    def _apply_column_bleed(self, text: str) -> str:
        """Remove spaces to simulate column bleed."""
        # Remove a random space
        spaces = [i for i, c in enumerate(text) if c == " "]
        if spaces:
            pos = self.rng.choice(spaces)
            return text[:pos] + text[pos + 1:]
        return text
