import json
import tempfile
import pytest
from pathlib import Path

import brick_builder.fixture_demo_selector as selector
from brick_builder.fixture_demo_selector import FixtureDemoController, FixtureDemoApp, _rasterize_faces, tk


class TestFixtureDemoController:
    def test_generation_is_contained_and_selection_is_explicit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            controller = FixtureDemoController(root)
            assert not (controller.generated)
            with pytest.raises(ValueError):
                controller.select("compact-box")
            result = controller.create_tower_choices()
            run = Path(result["run_dir"])
            assert result["valid"]
            assert run.parent == root
            assert [entry["id"] for entry in result["candidate_index"]] == ["compact-box", "stepped-box", "gatehouse"]
            compact_faces = controller.preview_faces("compact-box")
            stepped_faces = controller.preview_faces("stepped-box")
            gatehouse_faces = controller.preview_faces("gatehouse")
            assert len(compact_faces) > 0
            assert len(stepped_faces) > 0
            assert len(gatehouse_faces) > 0
            assert [(face["block_id"], face["points"]) for face in compact_faces] != [(face["block_id"], face["points"]) for face in stepped_faces]
            assert [(face["block_id"], face["points"]) for face in compact_faces] != [(face["block_id"], face["points"]) for face in gatehouse_faces]
            with pytest.raises(ValueError):
                controller.select("compact")
            selected = controller.select("gatehouse")
            destination = Path(selected["run_dir"])
            assert destination.is_relative_to(root)
            receipt = json.loads((destination / "selection.json").read_text(encoding="utf-8"))
            assert receipt["selected_candidate_id"] == "gatehouse"

    def test_repeated_generation_uses_fresh_runs(self):
        with tempfile.TemporaryDirectory() as directory:
            controller = FixtureDemoController(directory)
            first = Path(controller.create_tower_choices()["run_dir"])
            second = Path(controller.create_tower_choices()["run_dir"])
            assert first != second
            assert first.is_dir()
            assert second.is_dir()

    def test_fitted_previews_are_centered_and_inside_canvas(self):
        with tempfile.TemporaryDirectory() as directory:
            controller = FixtureDemoController(directory)
            controller.create_tower_choices()
            for candidate_id in controller.candidate_ids:
                points = [point for face in controller.preview_faces(candidate_id) for point in face["points"]]
                assert all(0 <= x <= 360 and 0 <= y <= 260 for x, y in points)
                assert max(x for x, _ in points) - min(x for x, _ in points) > 100
                assert max(y for _, y in points) - min(y for _, y in points) > 100

    def test_canonical_vertical_axis_is_upright_for_all_candidates(self):
        with tempfile.TemporaryDirectory() as directory:
            controller = FixtureDemoController(directory)
            controller.create_tower_choices()
            for candidate_id in controller.candidate_ids:
                blocks = controller._preview_blocks(candidate_id)
                assert max(block.center[1] for block in blocks) > min(block.center[1] for block in blocks)
            stepped = controller._preview_blocks("stepped-box")
            assert stepped[-1].center[1] > stepped[0].center[1]
            gatehouse = controller._preview_blocks("gatehouse")
            assert gatehouse[-1].center[1] > gatehouse[0].center[1]

    def test_raster_preview_uses_depth_not_face_input_order_for_overlap(self):
        far = {
            "points": ((1, 1), (11, 1), (11, 9), (1, 9)),
            "depth_points": (1, 1, 1, 1),
            "depth": 1,
            "color": "#c91a09",
        }
        near = {
            "points": ((6, 1), (15, 1), (15, 9), (6, 9)),
            "depth_points": (2, 2, 2, 2),
            "depth": 2,
            "color": "#0055bf",
        }
        pixels = _rasterize_faces((near, far), width=16, height=10)
        assert pixels[5][3] == "#c91a09"
        assert pixels[5][8] == "#0055bf"

    def test_preview_rotation_is_independent_and_reset_is_exact(self):
        with tempfile.TemporaryDirectory() as directory:
            controller = FixtureDemoController(directory)
            controller.create_tower_choices()
            original = controller.preview_faces("compact-box")
            controller.rotate_preview("compact-box", delta_yaw=18, delta_pitch=-7)
            assert controller.preview_state("stepped-box") == {"yaw": -35.0, "pitch": 25.0}
            assert controller.preview_state("gatehouse") == {"yaw": -35.0, "pitch": 25.0}
            assert controller.preview_faces("compact-box") != original
            assert controller.reset_preview("compact-box") == {"yaw": -35.0, "pitch": 25.0}
            assert controller.preview_faces("compact-box") == original
            controller.rotate_preview("gatehouse", delta_yaw=-11, delta_pitch=6)
            assert controller.preview_state("compact-box") == {"yaw": -35.0, "pitch": 25.0}
            assert controller.preview_state("stepped-box") == {"yaw": -35.0, "pitch": 25.0}
            assert controller.reset_preview("gatehouse") == {"yaw": -35.0, "pitch": 25.0}

    def test_screen_drag_maps_rightward_motion_to_negative_yaw(self):
        with tempfile.TemporaryDirectory() as directory:
            controller = FixtureDemoController(directory)

            state = controller.drag_preview("compact-box", screen_dx=12, screen_dy=4)

            assert state == {"yaw": -47.0, "pitch": 29.0}
            assert controller.preview_state("stepped-box") == {"yaw": -35.0, "pitch": 25.0}

    def test_failed_candidate_set_is_not_exposed_as_generated(self, monkeypatch):
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
            monkeypatch.setattr(selector, "replay_candidate_set", lambda *args: failed)
            with pytest.raises(ValueError, match="SCHEMA_DEPENDENCY.*docs/demo-setup.md"):
                controller.create_tower_choices()
            assert not (controller.generated)
            assert controller.candidate_set_run is None
            with pytest.raises(ValueError, match="create tower choices"):
                controller.preview_faces("compact-box")
            with pytest.raises(ValueError, match="create tower choices"):
                controller.select("compact-box")


@pytest.mark.skipif(tk is None, reason="Tk is unavailable in this Python runtime")
class TestFixtureDemoTkSmoke:
    def test_widgets_start_with_selection_disabled(self):
        try:
            root = tk.Tk()
        except tk.TclError as exc:
            pytest.skip(f"Tcl/Tk cannot initialize: {exc}")
        try:
            with tempfile.TemporaryDirectory() as directory:
                app = FixtureDemoApp(FixtureDemoController(directory), root)
                assert list(app.canvases) == ["compact-box", "stepped-box", "gatehouse"]
                assert str(app.select_buttons["compact-box"]["state"]) == "disabled"
                assert str(app.select_buttons["stepped-box"]["state"]) == "disabled"
                assert str(app.select_buttons["gatehouse"]["state"]) == "disabled"
                assert str(app.reset_buttons["compact-box"]["state"]) == "disabled"
                assert str(app.reset_buttons["stepped-box"]["state"]) == "disabled"
                assert str(app.reset_buttons["gatehouse"]["state"]) == "disabled"
        finally:
            root.destroy()
