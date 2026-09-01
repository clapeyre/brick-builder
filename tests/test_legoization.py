import json
import unittest
from pathlib import Path

from brick_builder import WallBoxScaffold, legoize_wall_box, load_palette, validate_model


ROOT = Path(__file__).parents[1]


class LEGOizationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.palette = load_palette(ROOT / "brick_builder" / "palettes" / "classic-core-v0.json")

    def test_reference_wall_is_complete_deterministic_and_structurally_valid(self):
        target = json.loads((ROOT / "examples" / "scaffolds" / "wall-box-5x2.json").read_text())
        first = legoize_wall_box(target, self.palette)
        second = legoize_wall_box(target, self.palette)
        self.assertTrue(first.valid)
        self.assertTrue(first.coverage.complete)
        self.assertEqual(first.coverage.required, first.coverage.covered)
        self.assertEqual(first.coverage.uncovered, ())
        self.assertEqual(first.model, second.model)
        validate_model(first.model, self.palette)

    def test_partial_plate_height_uses_a_supported_plate(self):
        result = legoize_wall_box(WallBoxScaffold(4, height_plates=4), self.palette)
        self.assertTrue(result.valid)
        self.assertIn("3710.dat", {part["part"] for part in result.model["parts"]})

    def test_unsupported_depth_reports_actionable_uncovered_region(self):
        result = legoize_wall_box(WallBoxScaffold(4, 1, depth_studs=2), self.palette)
        self.assertFalse(result.coverage.complete)
        self.assertEqual(len(result.coverage.uncovered), 12)
        self.assertTrue(any("UNFILLED_TARGET_REGION" in item for item in result.coverage.diagnostics))
        # The partial candidate is still a valid connected assembly: coverage
        # and structural validity are intentionally separate checks.
        self.assertTrue(result.structural_valid)
        self.assertFalse(result.valid)

    def test_complete_coverage_can_still_fail_structural_validity(self):
        # A one-layer odd-width wall needs two bricks, whose side seam has no
        # stud connection.  This demonstrates the independent structural gate.
        result = legoize_wall_box(WallBoxScaffold(5, 1), self.palette)
        self.assertTrue(result.coverage.complete)
        self.assertFalse(result.structural_valid)
        self.assertFalse(result.valid)
        self.assertTrue(any(issue.code == "DISCONNECTED_ASSEMBLY" for issue in result.structural_issues))


if __name__ == "__main__":
    unittest.main()
