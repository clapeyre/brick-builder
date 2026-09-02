import unittest
from pathlib import Path

from brick_builder.gatehouse_legoization_bridge import legoize_accepted_gatehouse
from brick_builder.local_redesign import Block
from brick_builder.palette import load_palette
from brick_builder.spatial_concept import GenericBoxConcept

ROOT = Path(__file__).parents[1]
PALETTE = load_palette(ROOT / "brick_builder/palettes/classic-core-v0.json")


def concept(*boxes):
    return GenericBoxConcept(
        "gatehouse-bridge-test", "Gatehouse bridge test",
        tuple(Block(*box) for box in boxes),
        {"camera": "three-quarter", "geometry_refs": [box[0] for box in boxes]},
    )


class GatehouseLEGOizationBridgeTests(unittest.TestCase):
    def test_symmetric_three_box_gatehouse_is_complete_and_repeatable(self):
        value = concept(
            ("bridge", (0, 1.5, 0), (6, 1, 2), "#2878b5"),
            ("right", (2, 0.5, 0), (2, 1, 2), "#2878b5"),
            ("left", (-2, 0.5, 0), (2, 1, 2), "#2878b5"),
        )
        first = legoize_accepted_gatehouse(value, PALETTE)
        second = legoize_accepted_gatehouse(value, PALETTE)
        self.assertTrue(first.success)
        self.assertTrue(first.legoization.valid)
        self.assertTrue(first.snapshot()["assembly"]["coverage_complete"])
        self.assertTrue(first.snapshot()["assembly"]["structural_valid"])
        self.assertEqual(first.serialize(), second.serialize())
        self.assertEqual(first.mapping["opening_width_studs"], 2)

    def test_rejects_bad_alignment_and_partial_shape_without_assembly(self):
        candidate = concept(
            ("bridge", (0, 1.5, 0), (6, 1, 2), "#2878b5"),
            ("right", (2.25, 0.5, 0), (2, 1, 2), "#2878b5"),
            ("left", (-2, 0.5, 0), (2, 1, 2), "#2878b5"),
        )
        result = legoize_accepted_gatehouse(candidate, PALETTE)
        self.assertFalse(result.success)
        self.assertIsNone(result.legoization)
        self.assertTrue(any("TOWERS_NOT_SYMMETRIC" in item for item in result.diagnostics))

        result = legoize_accepted_gatehouse(concept(("one", (0, 0.5, 0), (2, 1, 2), "#2878b5")), PALETTE)
        self.assertFalse(result.success)
        self.assertIsNone(result.mapping)
        self.assertIn("THREE_BOXES_REQUIRED", result.diagnostics[0])

    def test_rejects_non_integral_or_mismatched_depth(self):
        result = legoize_accepted_gatehouse(concept(
            ("bridge", (0, 1.5, 0), (6.5, 1, 2), "#2878b5"),
            ("right", (2, 0.5, 0), (2, 1, 2), "#2878b5"),
            ("left", (-2, 0.5, 0), (2, 1, 2), "#2878b5"),
        ), PALETTE)
        self.assertFalse(result.success)
        self.assertTrue(any("NON_INTEGRAL_DIMENSION" in item for item in result.diagnostics))


if __name__ == "__main__":
    unittest.main()
