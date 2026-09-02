import json
import tempfile
import unittest
from pathlib import Path

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
            self.assertEqual([entry["id"] for entry in result["candidate_index"]], ["compact-box", "stepped-box"])
            compact_faces = controller.preview_faces("compact-box")
            stepped_faces = controller.preview_faces("stepped-box")
            self.assertGreater(len(compact_faces), 0)
            self.assertGreater(len(stepped_faces), 0)
            self.assertNotEqual(
                [(face["block_id"], face["points"]) for face in compact_faces],
                [(face["block_id"], face["points"]) for face in stepped_faces],
            )
            with self.assertRaises(ValueError):
                controller.select("compact")
            selected = controller.select("stepped-box")
            destination = Path(selected["run_dir"])
            self.assertTrue(destination.is_relative_to(root))
            receipt = json.loads((destination / "selection.json").read_text(encoding="utf-8"))
            self.assertEqual(receipt["selected_candidate_id"], "stepped-box")

    def test_repeated_generation_uses_fresh_runs(self):
        with tempfile.TemporaryDirectory() as directory:
            controller = FixtureDemoController(directory)
            first = Path(controller.create_tower_choices()["run_dir"])
            second = Path(controller.create_tower_choices()["run_dir"])
            self.assertNotEqual(first, second)
            self.assertTrue(first.is_dir())
            self.assertTrue(second.is_dir())


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
                self.assertEqual(str(app.select_buttons["compact-box"]["state"]), "disabled")
                self.assertEqual(str(app.select_buttons["stepped-box"]["state"]), "disabled")
        finally:
            root.destroy()


if __name__ == "__main__":
    unittest.main()
