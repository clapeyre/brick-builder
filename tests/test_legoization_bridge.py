import unittest
from pathlib import Path

from brick_builder.legoization_bridge import legoize_accepted_box
from brick_builder.palette import load_palette
from brick_builder.spatial_concept import GenericBoxConcept
from brick_builder.local_redesign import Block


ROOT = Path(__file__).parents[1]
PALETTE = load_palette(ROOT / "brick_builder/palettes/classic-core-v0.json")


def concept(*boxes):
    blocks = tuple(Block(ref, center, size, color) for ref, center, size, color in boxes)
    return GenericBoxConcept("bridge-test", "Bridge test", blocks, {
        "camera": "three-quarter", "geometry_refs": [block.id for block in blocks],
    })


class LEGOizationBridgeTests(unittest.TestCase):
    def test_one_grounded_box_maps_and_is_repeatable(self):
        value = concept(("box", (0, 2, 0), (4, 4, 2), "#2878b5"))
        first = legoize_accepted_box(value, PALETTE)
        second = legoize_accepted_box(value, PALETTE)
        self.assertTrue(first.success)
        self.assertTrue(first.legoization.valid)
        self.assertTrue(first.snapshot()["assembly"]["coverage_complete"])
        self.assertTrue(first.snapshot()["assembly"]["structural_valid"])
        self.assertEqual(first.serialize(), second.serialize())
        self.assertEqual(first.mapping["spatial_units"], {"x": "stud", "y": "plate", "z": "stud"})

    def test_rejects_multi_box_non_integral_grounding_and_bounds(self):
        cases = [
            (concept(("a", (0, 1, 0), (2, 2, 1), "#2878b5"), ("b", (0, 3, 0), (2, 2, 1), "#2878b5")), "MULTI_BOX_UNSUPPORTED"),
            (concept(("a", (0, 1.25, 0), (2.5, 2, 1), "#2878b5")), "NON_INTEGRAL_DIMENSION"),
            (concept(("a", (0, 0, 0), (2, 2, 1), "#2878b5")), "NOT_GROUNDED"),
            (concept(("a", (0, 9, 0), (18, 18, 1), "#2878b5")), "OUT_OF_BOUNDS"),
        ]
        for candidate, code in cases:
            result = legoize_accepted_box(candidate, PALETTE)
            self.assertFalse(result.success)
            self.assertIsNone(result.legoization)
            self.assertTrue(any(code in diagnostic for diagnostic in result.diagnostics))

    def test_source_concept_is_preserved_in_serialized_result(self):
        result = legoize_accepted_box(concept(("box", (0, 1, 0), (2, 2, 2), "#2878b5")), PALETTE)
        self.assertEqual(result.snapshot()["source_concept"]["geometry"][0]["ref"], "box")
        self.assertIn("compiled_ldr", result.snapshot()["assembly"])


if __name__ == "__main__":
    unittest.main()
