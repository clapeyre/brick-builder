import json
import pytest
from pathlib import Path

from brick_builder import (GatehouseScaffold, SteppedBoxScaffold, WallBoxScaffold,
                           legoize_gatehouse, legoize_stepped_box,
                           legoize_wall_box, load_palette, validate_model)


ROOT = Path(__file__).parents[1]


class TestLEGOization:
    def setup_class(cls):
        cls.palette = load_palette(ROOT / "brick_builder" / "palettes" / "classic-core-v0.json")

    def test_reference_wall_is_complete_deterministic_and_structurally_valid(self):
        target = json.loads((ROOT / "examples" / "scaffolds" / "wall-box-5x2.json").read_text())
        first = legoize_wall_box(target, self.palette)
        second = legoize_wall_box(target, self.palette)
        assert first.valid
        assert first.coverage.complete
        assert first.coverage.required == first.coverage.covered
        assert first.coverage.uncovered == ()
        assert first.model == second.model
        validate_model(first.model, self.palette)

    def test_partial_plate_height_uses_a_supported_plate(self):
        result = legoize_wall_box(WallBoxScaffold(4, height_plates=4), self.palette)
        assert result.valid
        assert "3710.dat" in {part["part"] for part in result.model["parts"]}

    def test_unsupported_depth_reports_actionable_uncovered_region(self):
        result = legoize_wall_box(WallBoxScaffold(4, 1, depth_studs=3), self.palette)
        assert not (result.coverage.complete)
        assert len(result.coverage.uncovered) == 24
        assert any("UNFILLED_TARGET_REGION" in item for item in result.coverage.diagnostics)
        # The partial candidate is still a valid connected assembly: coverage
        # and structural validity are intentionally separate checks.
        assert result.structural_valid
        assert not (result.valid)

    def test_complete_coverage_can_still_fail_structural_validity(self):
        # A one-layer odd-width wall needs two bricks, whose side seam has no
        # stud connection.  This demonstrates the independent structural gate.
        result = legoize_wall_box(WallBoxScaffold(5, 1), self.palette)
        assert result.coverage.complete
        assert not (result.structural_valid)
        assert not (result.valid)
        assert any(issue.code == "DISCONNECTED_ASSEMBLY" for issue in result.structural_issues)

    def test_two_stud_box_is_complete_repeatable_grounded_and_connected(self):
        target = json.loads((ROOT / "examples" / "scaffolds" / "box-4x2x2.json").read_text())
        first = legoize_wall_box(target, self.palette)
        second = legoize_wall_box(target, self.palette)
        assert first.valid
        assert first.coverage.complete
        assert first.model == second.model
        assert first.coverage.required == first.coverage.covered
        assert first.coverage.uncovered == ()
        assert first.coverage.diagnostics == ()
        assert first.coverage.diagnostics == ()
        assert first.structural_valid
        assert first.structural_issues == ()
        assert first.model["parts"][0]["matrix"] == [1, 0, 0, 0, 1, 0, 0, 0, 1]
        validate_model(first.model, self.palette)

    def test_two_stud_box_uses_existing_vertical_rotation_when_needed(self):
        result = legoize_wall_box(WallBoxScaffold(2, 1, depth_studs=2), self.palette)
        assert result.valid
        assert any(part["matrix"] != [1, 0, 0, 0, 1, 0, 0, 0, 1]
                            for part in result.model["parts"])
        assert all(part["matrix"] in (
            [1, 0, 0, 0, 1, 0, 0, 0, 1],
            [0, 0, -1, 0, 1, 0, 1, 0, 0],
        ) for part in result.model["parts"])

    def test_two_stud_coverage_and_structure_are_independent(self):
        result = legoize_wall_box(WallBoxScaffold(5, 1, depth_studs=2), self.palette)
        assert result.coverage.complete
        assert not (result.structural_valid)
        assert not (result.valid)
        assert any(issue.code == "DISCONNECTED_ASSEMBLY" for issue in result.structural_issues)

    def test_centered_stepped_box_fixture_is_complete_repeatable_and_grounded(self):
        target = json.loads((ROOT / "examples" / "scaffolds" /
                             "stepped-box-4x2-base-2x2-upper.json").read_text())
        first = legoize_stepped_box(target, self.palette)
        second = legoize_stepped_box(target, self.palette)
        assert first.valid
        assert first.model == second.model
        assert first.coverage.required == first.coverage.covered
        assert first.coverage.uncovered == ()
        assert first.structural_valid
        validate_model(first.model, self.palette)
        upper = [part for part in first.model["parts"] if part["id"].startswith("step-upper")]
        assert upper
        # The 2-wide tier is centered in the 4-wide absolute target: x=1..2.
        assert {x for x, layer, z in first.coverage.covered if layer >= 3} == {1, 2}
        assert all(part["translation_ldu"][1] <= -24 for part in upper)

    def test_stepped_box_rejects_invalid_tier_geometry(self):
        with pytest.raises(ValueError, match="even number"):
            legoize_stepped_box(SteppedBoxScaffold(5, 2, 1, 1), self.palette)
        with pytest.raises(ValueError, match="narrower"):
            legoize_stepped_box(SteppedBoxScaffold(4, 4, 1, 1), self.palette)
        with pytest.raises(ValueError, match="positive"):
            legoize_stepped_box(SteppedBoxScaffold(4, 2, 0, 1), self.palette)

    def test_stepped_box_unsupported_depth_is_incomplete_not_successful(self):
        result = legoize_stepped_box(SteppedBoxScaffold(4, 2, 1, 1, depth_studs=3), self.palette)
        assert not (result.coverage.complete)
        assert not (result.valid)
        assert any("UNFILLED_TARGET_REGION" in item
                            for item in result.coverage.diagnostics)
        # Structural validity remains an independent gate from target coverage.
        assert result.structural_valid

    def test_gatehouse_fixture_is_complete_deterministic_grounded_and_connected(self):
        target = json.loads((ROOT / "examples" / "scaffolds" /
                             "gatehouse-6x2.json").read_text())
        first = legoize_gatehouse(target, self.palette)
        second = legoize_gatehouse(target, self.palette)
        assert first.valid
        assert first.model == second.model
        assert first.coverage.required == first.coverage.covered
        assert first.coverage.uncovered == ()
        assert first.structural_valid
        assert first.structural_issues == ()
        validate_model(first.model, self.palette)

    def test_gatehouse_coverage_preserves_open_gateway(self):
        result = legoize_gatehouse(GatehouseScaffold(6, 2, 2, 2, 1), self.palette)
        # The bridge covers the full width at its three plate layers, but the
        # two-stud gateway remains intentionally absent in lower layers.
        assert {x for x, layer, z in result.coverage.covered
                          if layer == 0} == {0, 1, 4, 5}
        assert {x for x, layer, z in result.coverage.covered
                          if layer == 6} == set(range(6))
        assert (2, 0, 0) not in result.coverage.required
        assert (3, 5, 1) not in result.coverage.required

    def test_gatehouse_rejects_invalid_geometry(self):
        with pytest.raises(ValueError, match="exactly fill"):
            legoize_gatehouse(GatehouseScaffold(7, 2, 2, 2, 1), self.palette)
        with pytest.raises(ValueError, match="positive"):
            legoize_gatehouse(GatehouseScaffold(6, 2, 2, 0, 1), self.palette)

    def test_gatehouse_unsupported_depth_is_incomplete_not_successful(self):
        result = legoize_gatehouse(GatehouseScaffold(6, 2, 2, 1, 1, depth_studs=3),
                                   self.palette)
        assert not (result.coverage.complete)
        assert not (result.valid)
        assert any("UNFILLED_TARGET_REGION" in item
                            for item in result.coverage.diagnostics)
        assert result.structural_valid
