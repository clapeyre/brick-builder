import json
import tempfile
import unittest
from pathlib import Path

from brick_builder.candidate_composition import compose_candidate_set
from brick_builder.candidate_rendering import render_candidate_set
from brick_builder.local_redesign import Block
from brick_builder.palette import load_palette
from brick_builder.spatial_concept import GenericBoxConcept


ROOT = Path(__file__).parents[1]
PALETTE = load_palette(ROOT / "brick_builder/palettes/classic-core-v0.json")


def concept(identifier, width=2):
    return GenericBoxConcept(
        identifier,
        identifier,
        (Block("box", (0, 1, 0), (width, 2, 2), "#2878b5"),),
        {"camera": "three-quarter", "geometry_refs": ["box"]},
    )


class CandidateRenderingTests(unittest.TestCase):
    def test_successful_candidates_get_deterministic_fixed_camera_evidence(self):
        candidate_set = compose_candidate_set("render these", [concept("first"), concept("second", 4)], PALETTE)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for candidate in candidate_set.candidates:
                (root / "candidates" / candidate["id"]).mkdir(parents=True, exist_ok=True)
            first = render_candidate_set(candidate_set.snapshot(), root, PALETTE)
            bytes_one = (root / "candidates/first/render-evidence.json").read_bytes()
            second = render_candidate_set(candidate_set.snapshot(), root, PALETTE)
            self.assertEqual(first, second)
            self.assertEqual(bytes_one, (root / "candidates/first/render-evidence.json").read_bytes())
            self.assertEqual([render["camera_id"] for render in first["candidates"][0]["renders"]], ["front", "three-quarter"])
            self.assertTrue((root / "candidates/first/render-front.svg").is_file())

    def test_rejected_candidates_remain_indexed_without_render_artifacts(self):
        unsupported = GenericBoxConcept(
            "unsupported",
            "unsupported",
            tuple(Block(f"box-{index}", (0, index + 0.5, 0), (2, 1, 2), "#2878b5") for index in range(4)),
            {"camera": "three-quarter", "geometry_refs": [f"box-{index}" for index in range(4)]},
        )
        candidate_set = compose_candidate_set("render these", [concept("first"), unsupported], PALETTE)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for candidate in candidate_set.candidates:
                (root / "candidates" / candidate["id"]).mkdir(parents=True, exist_ok=True)
            result = render_candidate_set(candidate_set.snapshot(), root, PALETTE)
            self.assertEqual(result["status"], "rejected")
            self.assertEqual([item["status"] for item in result["candidates"]], ["success", "failed"])
            self.assertTrue((root / "candidates/first/render-evidence.json").is_file())
            self.assertNotIn("render_evidence", result["candidates"][1])
            self.assertFalse((root / "candidates/unsupported/render-evidence.json").exists())


if __name__ == "__main__":
    unittest.main()
