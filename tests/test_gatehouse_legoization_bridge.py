import unittest
from pathlib import Path

from brick_builder.gatehouse_legoization_bridge import legoize_gatehouse_concept
from brick_builder.palette import load_palette
from brick_builder.spatial_concept import GenericBoxConcept
from brick_builder.local_redesign import Block


PALETTE = load_palette(Path(__file__).parents[1] / "brick_builder" / "palettes" / "classic-core-v0.json")


def concept(boxes):
    return GenericBoxConcept("gatehouse-test", "Gatehouse test", tuple(boxes), {"camera": "three-quarter", "geometry_refs": [box.id for box in boxes], "width": 430, "height": 360, "scale": 24})


class GatehouseBridgeTests(unittest.TestCase):
    def test_success_is_repeatable_and_complete(self):
        boxes = [Block("left", (-2, 1, 0), (2, 2, 2), "#2878b5"), Block("right", (2, 1, 0), (2, 2, 2), "#2878b5"), Block("bridge", (0, 3, 0), (6, 2, 2), "#2878b5")]
        first = legoize_gatehouse_concept(concept(boxes), PALETTE)
        second = legoize_gatehouse_concept(concept(boxes), PALETTE)
        self.assertTrue(first.success)
        self.assertEqual(first.serialize(), second.serialize())
        self.assertTrue(first.legoization.coverage.complete)
        self.assertTrue(first.legoization.structural_valid)
        self.assertIn("0 Brick Builder model:", first.compiled_ldr)

    def test_rejects_wrong_count_and_bad_opening(self):
        one = concept([Block("one", (0, 1, 0), (2, 2, 2), "#2878b5")])
        self.assertIn("THREE_BOXES_REQUIRED", legoize_gatehouse_concept(one, PALETTE).diagnostics[0])
        boxes = [Block("left", (-1, 1, 0), (2, 2, 2), "#2878b5"), Block("right", (1, 1, 0), (2, 2, 2), "#2878b5"), Block("bridge", (0, 3, 0), (4, 2, 2), "#2878b5")]
        self.assertTrue(any("TOWERS_OVERLAP" in item or "POSITIVE_INTEGRAL_OPENING_REQUIRED" in item for item in legoize_gatehouse_concept(concept(boxes), PALETTE).diagnostics))

    def test_rejects_misaligned_bridge_and_non_integral_dimensions(self):
        boxes = [Block("left", (-2, 1, 0), (2, 2, 2), "#2878b5"), Block("right", (2, 1, 0), (2, 2, 2), "#2878b5"), Block("bridge", (0, 3, 1), (6.5, 2, 2), "#2878b5")]
        result = legoize_gatehouse_concept(concept(boxes), PALETTE)
        self.assertFalse(result.success)
        self.assertIsNone(result.mapping)
        self.assertTrue(any("NON_INTEGRAL_DIMENSION" in item for item in result.diagnostics))
        misaligned = [Block("left", (-2, 1, 0), (2, 2, 2), "#2878b5"), Block("right", (2, 1, 0), (2, 2, 2), "#2878b5"), Block("bridge", (0, 3, 1), (6, 2, 2), "#2878b5")]
        self.assertTrue(any("NOT_ALIGNED" in item for item in legoize_gatehouse_concept(concept(misaligned), PALETTE).diagnostics))


if __name__ == "__main__":
    unittest.main()
