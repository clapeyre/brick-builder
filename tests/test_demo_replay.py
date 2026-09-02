import json
import tempfile
import unittest
from pathlib import Path

from brick_builder.demo_replay import replay_demo

ROOT = Path(__file__).parents[1]
PALETTE = ROOT / "brick_builder/palettes/classic-core-v0.json"
DEMO = ROOT / "examples/demo"


class DemoReplayTests(unittest.TestCase):
    def test_replay_writes_complete_deterministic_chain(self):
        with tempfile.TemporaryDirectory() as directory:
            first = replay_demo(DEMO / "tiny-red-box.request.txt", DEMO / "tiny-red-box.brief.json", ROOT / "examples/scaffolds/box-4x2x2.json", Path(directory) / "one", PALETTE)
            second = replay_demo(DEMO / "tiny-red-box.request.txt", DEMO / "tiny-red-box.brief.json", ROOT / "examples/scaffolds/box-4x2x2.json", Path(directory) / "two", PALETTE)
            self.assertTrue(first["valid"])
            self.assertEqual(first["manifest"]["files"], second["manifest"]["files"])
            for name in ("request.txt", "brief.json", "scaffold.json", "coverage.json", "legoized.json", "validation.json", "analysis.json", "final.ldr", "render-front.svg", "render-three-quarter.svg", "render-evidence.json", "manifest.json"):
                self.assertTrue((Path(first["run_dir"]) / name).is_file(), name)
            self.assertEqual(json.loads((Path(first["run_dir"]) / "coverage.json").read_text())["uncovered"], [])

            first_evidence = json.loads((Path(first["run_dir"]) / "render-evidence.json").read_text())
            second_evidence = json.loads((Path(second["run_dir"]) / "render-evidence.json").read_text())
            self.assertEqual(first_evidence, second_evidence)
            self.assertEqual([render["camera_id"] for render in first_evidence["renders"]], ["front", "three-quarter"])
            expected_ids = {part["id"] for part in json.loads((Path(first["run_dir"]) / "legoized.json").read_text())["parts"]}
            for render in first_evidence["renders"]:
                self.assertEqual(set(render["rendered_part_ids"]), expected_ids)
                self.assertGreater(render["visible_polygon_count"], 0)
                self.assertIsNotNone(render["non_background_bounds"])
                self.assertEqual(render["sha256"], first["manifest"]["files"][render["file"]])
            self.assertNotEqual(first_evidence["renders"][0]["non_background_bounds"], first_evidence["renders"][1]["non_background_bounds"])
            self.assertIn("render-evidence.json", first["manifest"]["files"])

    def test_unsupported_scaffold_fails_before_finalization(self):
        with tempfile.TemporaryDirectory() as directory:
            result = replay_demo(DEMO / "tiny-red-box.request.txt", DEMO / "tiny-red-box.brief.json", ROOT / "examples/scaffolds/unsupported-depth-3.json", Path(directory) / "bad", PALETTE)
            self.assertFalse(result["valid"])
            self.assertEqual(result["outcome"], "failed")
            root = Path(result["run_dir"])
            self.assertTrue((root / "failure.json").is_file())
            self.assertFalse((root / "final.ldr").exists())
            self.assertFalse((root / "render-evidence.json").exists())
            self.assertFalse((root / "render-front.svg").exists())
            self.assertTrue(any(issue["code"] == "UNFILLED_TARGET_REGION" for issue in result["issues"]))

    def test_tagged_stepped_fixture_replays_deterministically(self):
        with tempfile.TemporaryDirectory() as directory:
            first = replay_demo(DEMO / "stepped-box.request.txt", DEMO / "stepped-box.brief.json", ROOT / "examples/scaffolds/stepped-box-4x2-base-2x2-upper.json", Path(directory) / "one", PALETTE)
            second = replay_demo(DEMO / "stepped-box.request.txt", DEMO / "stepped-box.brief.json", ROOT / "examples/scaffolds/stepped-box-4x2-base-2x2-upper.json", Path(directory) / "two", PALETTE)
            self.assertTrue(first["valid"])
            self.assertEqual(first["manifest"]["files"], second["manifest"]["files"])
            first_root = Path(first["run_dir"])
            self.assertEqual(json.loads((first_root / "coverage.json").read_text())["uncovered"], [])
            model = json.loads((first_root / "legoized.json").read_text())
            self.assertEqual(model["model_id"], "stepped-box-4x2-base-2x2-upper")
            elevations = {
                part["id"]: part["translation_ldu"][1]
                for part in model["parts"]
            }
            self.assertEqual(set(elevations), {
                "step-base-box2-p00-x00-z00",
                "step-upper-box2-p00-x00-z00",
            })
            self.assertEqual(set(elevations.values()), {0, -24})
            self.assertTrue((first_root / "final.ldr").is_file())
            evidence = json.loads((first_root / "render-evidence.json").read_text())
            three_quarter = next(render for render in evidence["renders"] if render["camera_id"] == "three-quarter")
            self.assertGreaterEqual(three_quarter["visible_polygon_count"], 6)
            self.assertEqual(set(three_quarter["rendered_part_ids"]), {part["id"] for part in model["parts"]})

    def test_unknown_scaffold_kind_fails_without_legoizer_outputs(self):
        with tempfile.TemporaryDirectory() as directory:
            scaffold = Path(directory) / "unknown.json"
            scaffold.write_text(json.dumps({"kind": "hexagonal", "width_studs": 4, "height_bricks": 1, "depth_studs": 1}), encoding="utf-8")
            result = replay_demo(DEMO / "tiny-red-box.request.txt", DEMO / "tiny-red-box.brief.json", scaffold, Path(directory) / "bad", PALETTE)
            self.assertFalse(result["valid"])
            self.assertEqual(result["issues"][0]["code"], "UNKNOWN_SCAFFOLD_KIND")
            self.assertEqual(result["issues"][0]["path"], "scaffold.kind")
            root = Path(result["run_dir"])
            self.assertTrue((root / "failure.json").is_file())
            self.assertFalse((root / "final.ldr").exists())
            self.assertFalse((root / "render-evidence.json").exists())
            self.assertFalse((root / "render-front.svg").exists())
