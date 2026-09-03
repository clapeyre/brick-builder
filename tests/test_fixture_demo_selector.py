import json
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

import brick_builder.fixture_demo_selector as selector
from brick_builder.fixture_demo_selector import FixtureDemoController, FixtureDemoApp, tk


class FixtureDemoControllerTests(unittest.TestCase):
    def test_generation_is_contained_and_selection_is_explicit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            controller = FixtureDemoController(root)
            self.assertFalse(controller.generated)
            with self.assertRaises(ValueError):
                controller.select("compact-box")
            result = controller.create_tower_choices()
            run = Path(result["run_dir"])
            self.assertTrue(result["valid"])
            self.assertEqual(run.parent, root)
            self.assertEqual([entry["id"] for entry in result["candidate_index"]], ["compact-box", "stepped-box", "gatehouse"])
            compact_faces = controller.preview_faces("compact-box")
            stepped_faces = controller.preview_faces("stepped-box")
            gatehouse_faces = controller.preview_faces("gatehouse")
            self.assertGreater(len(compact_faces), 0)
            self.assertGreater(len(stepped_faces), 0)
            self.assertGreater(len(gatehouse_faces), 0)
            self.assertNotEqual(
                [(face["block_id"], face["points"]) for face in compact_faces],
                [(face["block_id"], face["points"]) for face in stepped_faces],
            )
            self.assertNotEqual(
                [(face["block_id"], face["points"]) for face in compact_faces],
                [(face["block_id"], face["points"]) for face in gatehouse_faces],
            )
            with self.assertRaises(ValueError):
                controller.select("compact")
            selected = controller.select("gatehouse")
            destination = Path(selected["run_dir"])
            self.assertTrue(destination.is_relative_to(root))
            receipt = json.loads((destination / "selection.json").read_text(encoding="utf-8"))
            self.assertEqual(receipt["selected_candidate_id"], "gatehouse")

    def test_repeated_generation_uses_fresh_runs(self):
        with tempfile.TemporaryDirectory() as directory:
            controller = FixtureDemoController(directory)
            first = Path(controller.create_tower_choices()["run_dir"])
            second = Path(controller.create_tower_choices()["run_dir"])
            self.assertNotEqual(first, second)
            self.assertTrue(first.is_dir())
            self.assertTrue(second.is_dir())

    def test_fitted_previews_are_centered_and_inside_canvas(self):
        with tempfile.TemporaryDirectory() as directory:
            controller = FixtureDemoController(directory)
            controller.create_tower_choices()
            for candidate_id in controller.candidate_ids:
                points = [point for face in controller.preview_faces(candidate_id) for point in face["points"]]
                self.assertTrue(all(0 <= x <= 360 and 0 <= y <= 260 for x, y in points))
                self.assertGreater(max(x for x, _ in points) - min(x for x, _ in points), 100)
                self.assertGreater(max(y for _, y in points) - min(y for _, y in points), 100)

    def test_canonical_vertical_axis_is_upright_for_all_candidates(self):
        with tempfile.TemporaryDirectory() as directory:
            controller = FixtureDemoController(directory)
            controller.create_tower_choices()
            for candidate_id in controller.candidate_ids:
                blocks = controller._preview_blocks(candidate_id)
                self.assertGreater(max(block.center[1] for block in blocks), min(block.center[1] for block in blocks))
            stepped = controller._preview_blocks("stepped-box")
            self.assertGreater(stepped[-1].center[1], stepped[0].center[1])
            gatehouse = controller._preview_blocks("gatehouse")
            self.assertGreater(gatehouse[-1].center[1], gatehouse[0].center[1])

    def test_preview_rotation_is_independent_and_reset_is_exact(self):
        with tempfile.TemporaryDirectory() as directory:
            controller = FixtureDemoController(directory)
            controller.create_tower_choices()
            original = controller.preview_faces("compact-box")
            controller.rotate_preview("compact-box", delta_yaw=18, delta_pitch=-7)
            self.assertEqual(controller.preview_state("stepped-box"), {"yaw": -35.0, "pitch": 25.0})
            self.assertEqual(controller.preview_state("gatehouse"), {"yaw": -35.0, "pitch": 25.0})
            self.assertNotEqual(controller.preview_faces("compact-box"), original)
            self.assertEqual(controller.reset_preview("compact-box"), {"yaw": -35.0, "pitch": 25.0})
            self.assertEqual(controller.preview_faces("compact-box"), original)
            controller.rotate_preview("gatehouse", delta_yaw=-11, delta_pitch=6)
            self.assertEqual(controller.preview_state("compact-box"), {"yaw": -35.0, "pitch": 25.0})
            self.assertEqual(controller.preview_state("stepped-box"), {"yaw": -35.0, "pitch": 25.0})
            self.assertEqual(controller.reset_preview("gatehouse"), {"yaw": -35.0, "pitch": 25.0})

    def test_screen_drag_maps_rightward_motion_to_negative_yaw(self):
        with tempfile.TemporaryDirectory() as directory:
            controller = FixtureDemoController(directory)

            state = controller.drag_preview("compact-box", screen_dx=12, screen_dy=4)

            self.assertEqual(state, {"yaw": -47.0, "pitch": 29.0})
            self.assertEqual(controller.preview_state("stepped-box"), {"yaw": -35.0, "pitch": 25.0})

    def test_failed_candidate_set_is_not_exposed_as_generated(self):
        with tempfile.TemporaryDirectory() as directory:
            failed_run = Path(directory) / "tower-choices-001"
            failed = {
                "valid": False,
                "outcome": "failed",
                "run_dir": str(failed_run),
                "candidate_index": [
                    {"id": "compact-box", "status": "failed", "issues": [{
                        "code": "SCHEMA_DEPENDENCY",
                        "message": "jsonschema dependency is required for structural validation",
                    }]},
                    {"id": "stepped-box", "status": "failed", "issues": [{
                        "code": "SCHEMA_DEPENDENCY",
                        "message": "jsonschema dependency is required for structural validation",
                    }]},
                    {"id": "gatehouse", "status": "failed", "issues": [{
                        "code": "SCHEMA_DEPENDENCY",
                        "message": "jsonschema dependency is required for structural validation",
                    }]},
                ],
            }
            controller = FixtureDemoController(directory)
            with patch.object(selector, "replay_candidate_set", return_value=failed):
                with self.assertRaisesRegex(ValueError, "SCHEMA_DEPENDENCY.*docs/demo-setup.md"):
                    controller.create_tower_choices()
            self.assertFalse(controller.generated)
            self.assertIsNone(controller.candidate_set_run)
            with self.assertRaisesRegex(ValueError, "create tower choices"):
                controller.preview_faces("compact-box")
            with self.assertRaisesRegex(ValueError, "create tower choices"):
                controller.select("compact-box")


@unittest.skipIf(tk is None, "Tk is unavailable in this Python runtime")
class FixtureDemoTkSmokeTests(unittest.TestCase):
    def test_widgets_start_with_selection_disabled(self):
        try:
            root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"Tcl/Tk cannot initialize: {exc}")
        try:
            with tempfile.TemporaryDirectory() as directory:
                app = FixtureDemoApp(FixtureDemoController(directory), root)
                self.assertEqual(list(app.canvases), ["compact-box", "stepped-box", "gatehouse"])
                self.assertEqual(str(app.select_buttons["compact-box"]["state"]), "disabled")
                self.assertEqual(str(app.select_buttons["stepped-box"]["state"]), "disabled")
                self.assertEqual(str(app.select_buttons["gatehouse"]["state"]), "disabled")
                self.assertEqual(str(app.reset_buttons["compact-box"]["state"]), "disabled")
                self.assertEqual(str(app.reset_buttons["stepped-box"]["state"]), "disabled")
                self.assertEqual(str(app.reset_buttons["gatehouse"]["state"]), "disabled")
        finally:
            root.destroy()


if __name__ == "__main__":
    unittest.main()
