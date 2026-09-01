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
            for name in ("request.txt", "brief.json", "scaffold.json", "coverage.json", "legoized.json", "validation.json", "analysis.json", "final.ldr", "render-front.svg", "render-three-quarter.svg", "manifest.json"):
                self.assertTrue((Path(first["run_dir"]) / name).is_file(), name)
            self.assertEqual(json.loads((Path(first["run_dir"]) / "coverage.json").read_text())["uncovered"], [])

    def test_unsupported_scaffold_fails_before_finalization(self):
        with tempfile.TemporaryDirectory() as directory:
            result = replay_demo(DEMO / "tiny-red-box.request.txt", DEMO / "tiny-red-box.brief.json", ROOT / "examples/scaffolds/unsupported-depth-3.json", Path(directory) / "bad", PALETTE)
            self.assertFalse(result["valid"])
            self.assertEqual(result["outcome"], "failed")
            root = Path(result["run_dir"])
            self.assertTrue((root / "failure.json").is_file())
            self.assertFalse((root / "final.ldr").exists())
            self.assertTrue(any(issue["code"] == "UNFILLED_TARGET_REGION" for issue in result["issues"]))
