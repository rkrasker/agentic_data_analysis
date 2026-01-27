"""
Tests for difficulty saturation fixes in synthetic generation.
"""

import pytest

from src.synthetic.completeness_analyzer import CompletenessAnalyzer
from src.synthetic.difficulty_computer import DifficultyComputer
from src.synthetic.hierarchy_loader import HierarchyLoader
from src.synthetic.models import (
    Branch,
    Clerk,
    CollisionSeverity,
    Consistency,
    DifficultyTier,
    FamiliarityLevel,
    Imperfections,
    NameFormat,
    RankForm,
    RankFormat,
    RankStyle,
    Situation,
    UnitFormat,
    UnitFormatStyle,
    VocabularyDensity,
    VocabularyPool,
)
from src.synthetic.renderer import Renderer
from src.synthetic.vocabulary_injector import CLUTTER_RATES, VocabularyInjector


def _make_hierarchy() -> HierarchyLoader:
    loader = HierarchyLoader()
    loader.branches = {
        Branch.DEFENSE_COMMAND.value: {
            "depth": 5,
            "levels": ["sector", "fleet", "squadron", "wing", "element"],
            "level_config": {},
            "abbreviation": "DC",
        }
    }
    return loader


def _make_clerk(tendency: str = "medium") -> Clerk:
    return Clerk(
        clerk_id="clerk-1",
        archetype_id="test_archetype",
        name="Test Clerk",
        context="test",
        name_format=NameFormat(template="{LAST}, {FIRST}"),
        rank_format=RankFormat(style=RankStyle.PREFIX, form=RankForm.PROPER_ABBREV),
        unit_format=UnitFormat(style=UnitFormatStyle.LABELED_FULL, separator=", "),
        vocabulary_density=VocabularyDensity.MEDIUM,
        vocabulary_bias=[],
        applicable_branches=[],
        familiarity_override=None,
        familiarity_applies=False,
        path_completeness_tendency=tendency,
        structural_signals_tendency="medium",
        consistency=Consistency(),
        imperfections=Imperfections(),
        used_vocabulary=[],
        entry_count=0,
    )


def test_select_levels_respects_path_completeness_tendency():
    loader = _make_hierarchy()
    levels = loader.get_branch_levels(Branch.DEFENSE_COMMAND)

    renderer_low = Renderer(loader, random_seed=7)
    renderer_high = Renderer(loader, random_seed=7)

    low_levels = renderer_low._select_levels(
        levels, FamiliarityLevel.DIFFERENT_BRANCH, _make_clerk("very_low")
    )
    high_levels = renderer_high._select_levels(
        levels, FamiliarityLevel.DIFFERENT_BRANCH, _make_clerk("very_high")
    )

    assert len(low_levels) < len(high_levels)
    assert len(low_levels) >= 1
    assert len(high_levels) >= 1


def test_assign_tier_collision_complete_is_moderate():
    loader = _make_hierarchy()
    analyzer = CompletenessAnalyzer(loader)
    computer = DifficultyComputer(analyzer)

    tier = computer._assign_tier(
        any_complete=True,
        collision_zone=True,
        collision_severity=CollisionSeverity.HIGH,
        complementarity_score=0.1,
        structural_resolvability=False,
    )
    assert tier == DifficultyTier.MODERATE

    tier = computer._assign_tier(
        any_complete=True,
        collision_zone=True,
        collision_severity=CollisionSeverity.HIGH,
        complementarity_score=0.1,
        structural_resolvability=True,
    )
    assert tier == DifficultyTier.EASY

    tier = computer._assign_tier(
        any_complete=True,
        collision_zone=False,
        collision_severity=CollisionSeverity.NONE,
        complementarity_score=0.1,
        structural_resolvability=False,
    )
    assert tier == DifficultyTier.EASY


class _DeterministicRng:
    def __init__(self, values):
        self.values = list(values)

    def random(self):
        if self.values:
            return self.values.pop(0)
        return 0.5

    def choice(self, seq):
        return seq[0]


def test_confounder_injects_without_clutter(monkeypatch):
    injector = VocabularyInjector(random_seed=1)
    injector.rng = _DeterministicRng([1.0, 1.0, 0.0, 0.5])
    injector.confounder_terms = ["A"]

    clerk = _make_clerk()
    monkeypatch.setitem(CLUTTER_RATES, clerk.archetype_id, 0.0)

    situation = Situation(
        situation_id="s1",
        description="test",
        vocabulary_pool=VocabularyPool(primary=[]),
    )

    text, injected = injector.inject_vocabulary("Base Entry", clerk, situation)

    assert injected["clutter"] == []
    assert injected["confounder"] == ["A"]
    assert "A" in text


def test_imperfections_modify_text():
    loader = _make_hierarchy()
    renderer = Renderer(loader, random_seed=3)

    clerk = _make_clerk()
    clerk.imperfections = Imperfections(
        typo_rate=1.0,
        abbreviation_inconsistency=1.0,
        trailing_off=0.0,
        mid_entry_corrections=1.0,
        incomplete_unit=1.0,
        column_bleed=1.0,
    )

    unit_text = "Squadron 3 / Wing 2"
    text = f"Sgt Zara {unit_text}"
    altered = renderer._apply_imperfections(text, clerk, unit_text)

    assert altered != text


def test_label_omission_rate_full_drops_labels():
    loader = _make_hierarchy()
    renderer = Renderer(loader, random_seed=1)
    clerk = _make_clerk()
    clerk.unit_format.label_omission_rate = 1.0

    parts = [("sector", "Alpha"), ("fleet", "Kestrel")]
    output = renderer._format_labeled(parts, clerk, familiarity=FamiliarityLevel.DIFFERENT_BRANCH)

    assert "Sec" not in output
    assert "Sector" not in output


def test_label_omission_rate_zero_keeps_labels():
    loader = _make_hierarchy()
    renderer = Renderer(loader, random_seed=1)
    clerk = _make_clerk()
    clerk.unit_format.label_omission_rate = 0.0

    parts = [("sector", "Alpha"), ("fleet", "Kestrel")]
    output = renderer._format_labeled(parts, clerk, familiarity=FamiliarityLevel.DIFFERENT_BRANCH)

    assert "Sec" in output or "Sector" in output


def test_abbreviate_value_rules():
    loader = _make_hierarchy()
    renderer = Renderer(loader, random_seed=2)

    assert renderer._abbreviate_value("7") == "7"
    assert renderer._abbreviate_value("A") == "A"

    abbreviated = renderer._abbreviate_value("Landfall")
    assert abbreviated
    assert len(abbreviated) < len("Landfall")


def test_mix_delimiters_varies_for_low_consistency():
    loader = _make_hierarchy()
    renderer = Renderer(loader, random_seed=2)
    renderer.rng = _DeterministicRng([0.0, 0.0, 0.0])
    clerk = _make_clerk()
    clerk.consistency = Consistency(format_lock=0.0, minor_drift=0.0, major_variation=0.0)

    unit_text = "Sec Alpha, Col Amber, Dist 8"
    mixed = renderer._mix_delimiters(unit_text, clerk)

    assert mixed != unit_text


def test_mix_delimiters_respects_high_consistency():
    loader = _make_hierarchy()
    renderer = Renderer(loader, random_seed=2)
    renderer.rng = _DeterministicRng([1.0])
    clerk = _make_clerk()
    clerk.consistency = Consistency(format_lock=0.99, minor_drift=0.0, major_variation=0.0)

    unit_text = "Sec Alpha, Col Amber, Dist 8"
    mixed = renderer._mix_delimiters(unit_text, clerk)

    assert mixed == unit_text


def test_familiarity_boost_increases_label_omission():
    loader = _make_hierarchy()
    renderer = Renderer(loader, random_seed=2)
    renderer.rng = _DeterministicRng([0.5, 0.5])
    clerk = _make_clerk()
    clerk.unit_format.label_omission_rate = 0.0

    parts = [("sector", "Alpha"), ("fleet", "Kestrel")]
    same_output = renderer._format_labeled(parts, clerk, familiarity=FamiliarityLevel.SAME_L3)

    renderer.rng = _DeterministicRng([0.5, 0.5])
    diff_output = renderer._format_labeled(parts, clerk, familiarity=FamiliarityLevel.DIFFERENT_BRANCH)

    assert "Sec" not in same_output
    assert "Sec" in diff_output or "Sector" in diff_output
