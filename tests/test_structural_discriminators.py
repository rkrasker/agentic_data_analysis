# -*- coding: utf-8 -*-
"""
Unit tests for structural_discriminators module.
"""

import json
import sys
import tempfile
from pathlib import Path

import pytest

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.preprocessing.hierarchy.structural_discriminators import (
    extract_structural_discriminators,
    StructuralDiscriminators,
)


FIXTURES_DIR = Path(__file__).parent / "fixtures"


class TestLevelNameDiscriminators:
    """Tests for level name uniqueness detection."""

    def test_unique_level_names(self):
        """Level names unique to one branch should be identified."""
        hierarchy_path = FIXTURES_DIR / "test_hierarchy_reference.json"
        result = extract_structural_discriminators(
            hierarchy_path,
            output_path=Path(tempfile.gettempdir()) / "test_output.json",
        )

        # "squadron" only appears in branch_beta
        assert result.level_name_discriminators["squadron"]["unique_to"] == "branch_beta"
        assert result.level_name_discriminators["squadron"]["appears_in"] == ["branch_beta"]

        # "flight" only appears in branch_beta
        assert result.level_name_discriminators["flight"]["unique_to"] == "branch_beta"

        # "division" only appears in branch_alpha
        assert result.level_name_discriminators["division"]["unique_to"] == "branch_alpha"

        # "region" only appears in branch_gamma
        assert result.level_name_discriminators["region"]["unique_to"] == "branch_gamma"

    def test_shared_level_names(self):
        """Level names appearing in multiple branches should have unique_to=None."""
        hierarchy_path = FIXTURES_DIR / "test_hierarchy_reference.json"
        result = extract_structural_discriminators(
            hierarchy_path,
            output_path=Path(tempfile.gettempdir()) / "test_output.json",
        )

        # "sector" appears in both branch_alpha and branch_beta
        assert result.level_name_discriminators["sector"]["unique_to"] is None
        assert "branch_alpha" in result.level_name_discriminators["sector"]["appears_in"]
        assert "branch_beta" in result.level_name_discriminators["sector"]["appears_in"]


class TestDesignatorDiscriminators:
    """Tests for designator value discrimination."""

    def test_unique_designator_values(self):
        """Designator values unique to one branch should be identified."""
        hierarchy_path = FIXTURES_DIR / "test_hierarchy_reference.json"
        result = extract_structural_discriminators(
            hierarchy_path,
            output_path=Path(tempfile.gettempdir()) / "test_output.json",
        )

        # "Recon" only appears in branch_alpha
        assert result.designator_discriminators["Recon"]["unique_to_branch"] == "branch_alpha"

        # "North", "South", "East", "West" only in branch_gamma
        assert result.designator_discriminators["North"]["unique_to_branch"] == "branch_gamma"

        # "Central", "Perimeter" only in branch_gamma
        assert result.designator_discriminators["Central"]["unique_to_branch"] == "branch_gamma"

    def test_shared_designator_values(self):
        """Designator values in multiple branches should have unique_to_branch=None."""
        hierarchy_path = FIXTURES_DIR / "test_hierarchy_reference.json"
        result = extract_structural_discriminators(
            hierarchy_path,
            output_path=Path(tempfile.gettempdir()) / "test_output.json",
        )

        # "Alpha" appears in branch_alpha and branch_beta
        assert result.designator_discriminators["Alpha"]["unique_to_branch"] is None
        assert "branch_alpha" in result.designator_discriminators["Alpha"]["valid_in"]
        assert "branch_beta" in result.designator_discriminators["Alpha"]["valid_in"]

        # "A" appears in all three branches
        assert result.designator_discriminators["A"]["unique_to_branch"] is None

    def test_designator_type_classification(self):
        """Designator values should be classified by type."""
        hierarchy_path = FIXTURES_DIR / "test_hierarchy_reference.json"
        result = extract_structural_discriminators(
            hierarchy_path,
            output_path=Path(tempfile.gettempdir()) / "test_output.json",
        )

        # Single letters are "alpha"
        assert result.designator_discriminators["A"]["type"] == "alpha"
        assert result.designator_discriminators["B"]["type"] == "alpha"

        # Integers are "numeric"
        assert result.designator_discriminators["1"]["type"] == "numeric"
        assert result.designator_discriminators["2"]["type"] == "numeric"

        # Multi-char strings are "word"
        assert result.designator_discriminators["Alpha"]["type"] == "word"
        assert result.designator_discriminators["Recon"]["type"] == "word"


class TestDepthDiscriminators:
    """Tests for depth-based discrimination."""

    def test_unique_depths(self):
        """Unique depths should be identified."""
        hierarchy_path = FIXTURES_DIR / "test_hierarchy_reference.json"
        result = extract_structural_discriminators(
            hierarchy_path,
            output_path=Path(tempfile.gettempdir()) / "test_output.json",
        )

        # Depth 5 is unique to branch_gamma
        assert result.depth_discriminators[5]["is_unique"] is True
        assert result.depth_discriminators[5]["branches"] == ["branch_gamma"]

        # Depth 4 is unique to branch_alpha
        assert result.depth_discriminators[4]["is_unique"] is True
        assert result.depth_discriminators[4]["branches"] == ["branch_alpha"]

        # Depth 3 is unique to branch_beta
        assert result.depth_discriminators[3]["is_unique"] is True
        assert result.depth_discriminators[3]["branches"] == ["branch_beta"]


class TestCollisionIndex:
    """Tests for collision index generation."""

    def test_actual_collisions_from_components(self):
        """Collision index should map (level, value) pairs to component paths."""
        hierarchy_path = FIXTURES_DIR / "test_hierarchy_reference.json"
        result = extract_structural_discriminators(
            hierarchy_path,
            output_path=Path(tempfile.gettempdir()) / "test_output.json",
        )

        # ("sector", "Alpha") appears in multiple components
        key = ("sector", "Alpha")
        assert key in result.collision_index
        assert len(result.collision_index[key]) > 1

        # Components from both branch_alpha and branch_beta should be present
        components = result.collision_index[key]
        has_alpha = any("branch_alpha" in c for c in components)
        has_beta = any("branch_beta" in c for c in components)
        assert has_alpha and has_beta

    def test_no_single_component_entries(self):
        """Collision index should only include entries with 2+ components."""
        hierarchy_path = FIXTURES_DIR / "test_hierarchy_reference.json"
        result = extract_structural_discriminators(
            hierarchy_path,
            output_path=Path(tempfile.gettempdir()) / "test_output.json",
        )

        for key, components in result.collision_index.items():
            assert len(components) >= 2, f"Key {key} has only {len(components)} components"


class TestExclusionRules:
    """Tests for branch exclusion rule generation."""

    def test_term_presence_rules(self):
        """Terms unique to other branches should generate exclusion rules."""
        hierarchy_path = FIXTURES_DIR / "test_hierarchy_reference.json"
        result = extract_structural_discriminators(
            hierarchy_path,
            output_path=Path(tempfile.gettempdir()) / "test_output.json",
        )

        # branch_alpha should have exclusion rules for terms unique to other branches
        alpha_rules = result.branch_exclusion_rules["branch_alpha"]

        # Find rule about "squadron" (unique to branch_beta)
        squadron_rules = [
            r for r in alpha_rules
            if r["rule_type"] == "term_presence" and "squadron" in r["condition"]
        ]
        assert len(squadron_rules) == 1
        assert squadron_rules[0]["strength"] == "definitive"
        assert squadron_rules[0]["implies_branch"] == "branch_beta"

    def test_depth_mismatch_rules(self):
        """Depth mismatches should generate exclusion rules."""
        hierarchy_path = FIXTURES_DIR / "test_hierarchy_reference.json"
        result = extract_structural_discriminators(
            hierarchy_path,
            output_path=Path(tempfile.gettempdir()) / "test_output.json",
        )

        # branch_beta (depth 3) should have exclusion rule for depth 5 paths
        beta_rules = result.branch_exclusion_rules["branch_beta"]
        depth_rules = [r for r in beta_rules if r["rule_type"] == "depth_mismatch"]

        # Should have rules for depths > 3 (i.e., 4 and 5)
        depth_conditions = [r["condition"] for r in depth_rules]
        assert any("5 levels" in c for c in depth_conditions)
        assert any("4 levels" in c for c in depth_conditions)

    def test_exclusion_rules_are_definitive(self):
        """All exclusion rules should have definitive strength."""
        hierarchy_path = FIXTURES_DIR / "test_hierarchy_reference.json"
        result = extract_structural_discriminators(
            hierarchy_path,
            output_path=Path(tempfile.gettempdir()) / "test_output.json",
        )

        for branch_id, rules in result.branch_exclusion_rules.items():
            for rule in rules:
                assert rule["strength"] == "definitive", (
                    f"Rule for {branch_id} has non-definitive strength: {rule}"
                )


class TestLevelConfigFormat:
    """Tests for handling level_config schema format."""

    def test_level_config_parsing(self):
        """Should correctly parse level_config format (like actual hierarchy_reference.json)."""
        hierarchy_path = FIXTURES_DIR / "test_hierarchy_level_config.json"
        result = extract_structural_discriminators(
            hierarchy_path,
            output_path=Path(tempfile.gettempdir()) / "test_output.json",
        )

        # Should have parsed both branches
        assert "defense_force" in result.metadata["branches_analyzed"]
        assert "admin_corps" in result.metadata["branches_analyzed"]

        # "fleet" is unique to defense_force
        assert result.level_name_discriminators["fleet"]["unique_to"] == "defense_force"

        # "bureau" is unique to admin_corps
        assert result.level_name_discriminators["bureau"]["unique_to"] == "admin_corps"

        # "sector" is shared
        assert result.level_name_discriminators["sector"]["unique_to"] is None

    def test_string_numbers_converted(self):
        """String numbers in level_config values should be converted to ints."""
        hierarchy_path = FIXTURES_DIR / "test_hierarchy_level_config.json"
        result = extract_structural_discriminators(
            hierarchy_path,
            output_path=Path(tempfile.gettempdir()) / "test_output.json",
        )

        # "1", "2", "3" from fleet should be parsed as integers
        assert "1" in result.designator_discriminators
        assert result.designator_discriminators["1"]["type"] == "numeric"


class TestJsonSerialization:
    """Tests for JSON round-trip serialization."""

    def test_roundtrip_serialization(self):
        """Serializing to JSON and back should preserve data."""
        hierarchy_path = FIXTURES_DIR / "test_hierarchy_reference.json"
        original = extract_structural_discriminators(
            hierarchy_path,
            output_path=Path(tempfile.gettempdir()) / "test_output.json",
        )

        # Serialize and deserialize
        json_data = original.to_json()
        restored = StructuralDiscriminators.from_json(json_data)

        # Compare key fields
        assert original.metadata["branches_analyzed"] == restored.metadata["branches_analyzed"]
        assert original.level_name_discriminators == restored.level_name_discriminators
        assert original.designator_discriminators == restored.designator_discriminators
        assert original.depth_discriminators == restored.depth_discriminators
        assert original.branch_exclusion_rules == restored.branch_exclusion_rules

        # Collision index comparison (sets need special handling)
        assert len(original.collision_index) == len(restored.collision_index)
        for key in original.collision_index:
            assert key in restored.collision_index
            assert original.collision_index[key] == restored.collision_index[key]

    def test_output_file_written(self):
        """Output file should be written as valid JSON."""
        hierarchy_path = FIXTURES_DIR / "test_hierarchy_reference.json"
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "structural_discriminators.json"

            extract_structural_discriminators(hierarchy_path, output_path)

            assert output_path.exists()

            # Should be valid JSON
            with open(output_path) as f:
                data = json.load(f)

            assert "metadata" in data
            assert "level_name_discriminators" in data
            assert "designator_discriminators" in data
            assert "depth_discriminators" in data
            assert "branch_exclusion_rules" in data
            assert "collision_index" in data


class TestErrorHandling:
    """Tests for error handling."""

    def test_missing_file_raises(self):
        """Missing hierarchy file should raise FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            extract_structural_discriminators(
                Path("/nonexistent/path.json"),
                output_path=Path(tempfile.gettempdir()) / "test_output.json",
            )

    def test_missing_branches_raises(self):
        """Hierarchy without branches key should raise ValueError."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"meta": "test"}, f)
            temp_path = Path(f.name)

        try:
            with pytest.raises(ValueError, match="missing required 'branches' key"):
                extract_structural_discriminators(
                    temp_path,
                    output_path=Path(tempfile.gettempdir()) / "test_output.json",
                )
        finally:
            temp_path.unlink()

    def test_missing_depth_raises(self):
        """Branch without depth should raise ValueError."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({
                "branches": {
                    "test_branch": {
                        "levels": ["a", "b"]
                    }
                }
            }, f)
            temp_path = Path(f.name)

        try:
            with pytest.raises(ValueError, match="missing required 'depth' field"):
                extract_structural_discriminators(
                    temp_path,
                    output_path=Path(tempfile.gettempdir()) / "test_output.json",
                )
        finally:
            temp_path.unlink()


class TestActualHierarchy:
    """Tests against the actual hierarchy_reference.json file."""

    def test_actual_hierarchy_file(self):
        """Should successfully process the actual hierarchy_reference.json."""
        actual_path = PROJECT_ROOT / "config" / "hierarchies" / "hierarchy_reference.json"
        if not actual_path.exists():
            pytest.skip("Actual hierarchy_reference.json not found")

        result = extract_structural_discriminators(
            actual_path,
            output_path=Path(tempfile.gettempdir()) / "test_actual_output.json",
        )

        # Should have processed all 4 branches
        assert len(result.metadata["branches_analyzed"]) == 4
        assert "colonial_administration" in result.metadata["branches_analyzed"]
        assert "defense_command" in result.metadata["branches_analyzed"]
        assert "expeditionary_corps" in result.metadata["branches_analyzed"]
        assert "resource_directorate" in result.metadata["branches_analyzed"]

        # Check known unique terms
        assert result.level_name_discriminators["squadron"]["unique_to"] == "defense_command"
        assert result.level_name_discriminators["colony"]["unique_to"] == "colonial_administration"
        assert result.level_name_discriminators["expedition"]["unique_to"] == "expeditionary_corps"
        assert result.level_name_discriminators["facility"]["unique_to"] == "resource_directorate"

        # Check depth discriminators
        assert result.depth_discriminators[5]["branches"] == ["defense_command"]
        assert result.depth_discriminators[3]["branches"] == ["expeditionary_corps"]
