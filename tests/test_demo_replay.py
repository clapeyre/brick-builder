import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from brick_builder.demo_replay import replay_candidate_set, replay_demo, select_candidate

ROOT = Path(__file__).parents[1]
PALETTE = ROOT / "brick_builder/palettes/classic-core-v0.json"
DEMO = ROOT / "examples/demo"


class DemoReplayTests(unittest.TestCase):
    def test_selection_receipt_copies_each_valid_choice_without_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            source_result = replay_candidate_set(DEMO / "tiny-red-tower.request.txt", DEMO / "tiny-red-tower.brief.json", DEMO / "candidate-set-boxes.json", base / "set", PALETTE)
            source = base / "set"
            before = {path.relative_to(source): path.read_bytes() for path in source.rglob("*") if path.is_file()}
            for candidate_id in ("compact-box", "stepped-box"):
                destination = base / candidate_id
                selected = select_candidate(source, candidate_id, destination, PALETTE)
                self.assertTrue(selected["valid"])
                receipt = json.loads((destination / "selection.json").read_text())
                self.assertEqual(receipt["selected_candidate_id"], candidate_id)
                self.assertEqual(set(receipt["selected_artifact_hashes"]), {"legoized.json", "final.ldr", "validation.json", "analysis.json", "render-front.svg", "render-three-quarter.svg", "render-evidence.json"})
                self.assertEqual(selected["manifest"]["source_child_manifest_sha256"], receipt["source_child_manifest_sha256"])
                self.assertNotIn(str(source), (destination / "selection.json").read_text())
            self.assertEqual(before, {path.relative_to(source): path.read_bytes() for path in source.rglob("*") if path.is_file()})

    def test_selection_preflights_unknown_failed_and_tampered_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            replay_candidate_set(DEMO / "tiny-red-tower.request.txt", DEMO / "tiny-red-tower.brief.json", DEMO / "candidate-set-boxes.json", base / "set", PALETTE)
            source = base / "set"
            with self.assertRaises(ValueError):
                select_candidate(source, "missing", base / "unknown", PALETTE)
            (source / "candidates/compact-box/final.ldr").write_text("tampered", encoding="utf-8")
            destination = base / "tampered"
            with self.assertRaises(ValueError):
                select_candidate(source, "compact-box", destination, PALETTE)
            self.assertFalse(destination.exists())
            mismatch_source = base / "set-mismatch"
            replay_candidate_set(DEMO / "tiny-red-tower.request.txt", DEMO / "tiny-red-tower.brief.json", DEMO / "candidate-set-boxes.json", mismatch_source, PALETTE)
            index_path = mismatch_source / "candidate-index.json"
            index = json.loads(index_path.read_text())
            index["candidates"][0]["manifest_sha256"] = "0" * 64
            index_path.write_text(json.dumps(index), encoding="utf-8")
            root_manifest_path = mismatch_source / "manifest.json"
            root_manifest = json.loads(root_manifest_path.read_text())
            root_manifest["files"]["candidate-index.json"] = hashlib.sha256(index_path.read_bytes()).hexdigest()
            root_manifest_path.write_text(json.dumps(root_manifest), encoding="utf-8")
            mismatch_destination = base / "mismatch"
            with self.assertRaises(ValueError):
                select_candidate(mismatch_source, "compact-box", mismatch_destination, PALETTE)
            self.assertFalse(mismatch_destination.exists())

    def test_candidate_set_replays_two_ordered_candidates_without_selection(self):
        fixture = DEMO / "candidate-set-boxes.json"
        with tempfile.TemporaryDirectory() as directory:
            first = replay_candidate_set(DEMO / "tiny-red-tower.request.txt", DEMO / "tiny-red-tower.brief.json", fixture, Path(directory) / "one", PALETTE)
            second = replay_candidate_set(DEMO / "tiny-red-tower.request.txt", DEMO / "tiny-red-tower.brief.json", fixture, Path(directory) / "two", PALETTE)
            self.assertTrue(first["valid"])
            self.assertEqual(first["candidate_index"], second["candidate_index"])
            self.assertEqual([item["id"] for item in first["candidate_index"]], ["compact-box", "stepped-box"])
            self.assertNotIn("selected", json.loads((Path(first["run_dir"]) / "candidate-index.json").read_text()))
            root = Path(first["run_dir"])
            self.assertTrue((root / "candidate-set.json").is_file())
            self.assertIn("candidate-set.json", first["manifest"]["files"])
            for candidate in ("compact-box", "stepped-box"):
                child = root / "candidates" / candidate
                self.assertTrue((child / "manifest.json").is_file())
                self.assertTrue((child / "final.ldr").is_file())
            self.assertEqual(first["manifest"]["files"], second["manifest"]["files"])

    def test_candidate_set_preflights_malformed_and_duplicate_ids(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "candidates.json"
            config.write_text(json.dumps({"candidates": [{"id": "bad/id", "scaffold": str(ROOT / "examples/scaffolds/box-4x2x2.json")}, {"id": "ok", "scaffold": str(ROOT / "examples/scaffolds/box-4x2x2.json")}, {"id": "third", "scaffold": str(ROOT / "examples/scaffolds/box-4x2x2.json")}] }))
            output = Path(directory) / "run"
            with self.assertRaises(ValueError):
                replay_candidate_set(DEMO / "tiny-red-box.request.txt", DEMO / "tiny-red-box.brief.json", config, output, PALETTE)
            self.assertFalse(output.exists())
            config.write_text(json.dumps({"candidates": [{"id": "same", "scaffold": str(ROOT / "examples/scaffolds/box-4x2x2.json")}, {"id": "same", "scaffold": str(ROOT / "examples/scaffolds/box-4x2x2.json")}, {"id": "third", "scaffold": str(ROOT / "examples/scaffolds/box-4x2x2.json")}] }))
            with self.assertRaises(ValueError):
                replay_candidate_set(DEMO / "tiny-red-box.request.txt", DEMO / "tiny-red-box.brief.json", config, output, PALETTE)
            self.assertFalse(output.exists())

    def test_candidate_set_retains_success_when_other_candidate_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "candidates.json"
            config.write_text(json.dumps({"candidates": [
                {"id": "good", "scaffold": str(ROOT / "examples/scaffolds/box-4x2x2.json")},
                {"id": "bad", "scaffold": str(ROOT / "examples/scaffolds/unsupported-depth-3.json")},
                {"id": "third", "scaffold": str(ROOT / "examples/scaffolds/box-4x2x2.json")},
            ]}))
            result = replay_candidate_set(DEMO / "tiny-red-box.request.txt", DEMO / "tiny-red-box.brief.json", config, Path(directory) / "run", PALETTE)
            self.assertFalse(result["valid"])
            self.assertEqual([item["status"] for item in result["candidate_index"]], ["valid", "failed", "valid"])
            self.assertTrue((Path(result["run_dir"]) / "candidates/good/final.ldr").is_file())
            self.assertTrue((Path(result["run_dir"]) / "candidates/bad/manifest.json").is_file())

    def test_gatehouse_candidate_replays_with_complete_render_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            result = replay_candidate_set(DEMO / "tiny-red-tower.request.txt", DEMO / "tiny-red-tower.brief.json", DEMO / "candidate-set-towers-with-gatehouse.json", Path(directory) / "run", PALETTE)
            self.assertTrue(result["valid"])
            root = Path(result["run_dir"])
            gatehouse = root / "candidates/gatehouse"
            self.assertEqual(result["candidate_index"][2]["model_id"], "gatehouse-6x2")
            for name in ("manifest.json", "legoized.json", "final.ldr", "render-front.svg", "render-three-quarter.svg", "render-evidence.json"):
                self.assertTrue((gatehouse / name).is_file(), name)
            self.assertEqual(json.loads((gatehouse / "coverage.json").read_text())["uncovered"], [])
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
