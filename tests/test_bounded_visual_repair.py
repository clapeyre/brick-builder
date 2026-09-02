import json
import tempfile
import unittest
from pathlib import Path

from brick_builder.bounded_visual_repair import FORMAT, decrease_height, write_repair_artifact
from brick_builder.candidate_composition import compose_candidate_set
from brick_builder.local_redesign import Block
from brick_builder.palette import load_palette
from brick_builder.spatial_concept import GenericBoxConcept


ROOT = Path(__file__).parents[1]
PALETTE = load_palette(ROOT / "brick_builder/palettes/classic-core-v0.json")


def concept(identifier="chosen", height=3):
    return GenericBoxConcept(identifier, identifier, (Block("box", (0, height / 2, 0), (4, height, 2), "#2878b5"),), {"camera": "three-quarter", "geometry_refs": ["box"]})


class BoundedVisualRepairTests(unittest.TestCase):
    def setUp(self):
        self.composition = compose_candidate_set("make a small blue tower", [concept(), concept("other", 2)], PALETTE)

    def test_accepts_grounded_integral_reduction_through_bridge(self):
        result = decrease_height(self.composition, "chosen", 1, PALETTE)
        self.assertEqual(result["format"], FORMAT)
        self.assertTrue(result["accepted"])
        self.assertTrue(result["bridge"]["assembly"]["valid"])
        box = result["session"]["redesign"]["accepted_concept"]["geometry"][0]
        self.assertEqual(box["size"][1], 2)
        self.assertEqual(box["center"][1], 1)
        self.assertTrue(result["result"]["grounded"])
        self.assertFalse(any(result["claims"].values()))

    def test_invalid_and_bridge_invalid_reductions_preserve_baseline(self):
        for value in (0, -1, 3, 1.0, 1.5, "1"):
            result = decrease_height(self.composition, "chosen", value, PALETTE)
            self.assertFalse(result["accepted"], value)
            self.assertTrue(result["baseline_preserved"], value)
            self.assertTrue(result["diagnostics"], value)
        result = decrease_height(self.composition, "chosen", 2, PALETTE)
        self.assertTrue(result["accepted"])
        too_tall = compose_candidate_set("small", [concept("short", 2), concept("other", 3)], PALETTE)
        rejected = decrease_height(too_tall, "short", 2, PALETTE)
        self.assertFalse(rejected["accepted"])
        self.assertIn("positive-height", rejected["diagnostics"][0])

    def test_serialization_is_deterministic_and_has_no_resemblance_claim(self):
        first = decrease_height(self.composition, "chosen", 1, PALETTE)
        second = decrease_height(self.composition.snapshot(), "chosen", 1, PALETTE)
        self.assertEqual(json.dumps(first, sort_keys=True, separators=(",", ":")), json.dumps(second, sort_keys=True, separators=(",", ":")))
        self.assertFalse(first["claims"]["ranking"])
        self.assertNotIn('"score"', json.dumps(first).lower())
        self.assertFalse(first["claims"]["resemblance"])

        with tempfile.TemporaryDirectory() as directory:
            path = write_repair_artifact(first, Path(directory) / "repair.json")
            self.assertEqual(path.read_text(encoding="utf-8").rstrip("\n"), json.dumps(first, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    unittest.main()
