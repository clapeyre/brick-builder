"""Small offline Tk fixture selector for the tiny red tower demo.

This is intentionally a fixture demonstration: the controller delegates all
artifact creation and explicit selection to :mod:`brick_builder.demo_replay`.
The canvases project the generated canonical LEGO geometry with the existing
box projection helper; no image files or provider output are involved.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

from .demo_replay import replay_candidate_set, select_candidate
from .geometry import profiles_from_palette, transformed_profile
from .local_redesign import Block, project_box
from .palette import load_palette

try:  # Tk is optional; the controller remains usable in headless runtimes.
    import tkinter as tk
    from tkinter import ttk
except ImportError:  # pragma: no cover - depends on Python distribution.
    tk = None  # type: ignore[assignment]
    ttk = None  # type: ignore[assignment]


_ROOT = Path(__file__).resolve().parents[1]
_REQUEST = _ROOT / "examples" / "demo" / "tiny-red-tower.request.txt"
_BRIEF = _ROOT / "examples" / "demo" / "tiny-red-tower.brief.json"
_CANDIDATES = _ROOT / "examples" / "demo" / "candidate-set-boxes.json"
_PALETTE = _ROOT / "brick_builder" / "palettes" / "classic-core-v0.json"
_CANDIDATE_IDS = ("compact-box", "stepped-box")
_COLOURS = {0: "#202124", 1: "#0055bf", 2: "#237841", 4: "#c91a09", 14: "#f2cd37", 15: "#ffffff", 25: "#fe8a18"}
_PREVIEW_WIDTH = 360
_PREVIEW_HEIGHT = 260
_PREVIEW_PADDING = 20
_DEFAULT_YAW = -35.0
_DEFAULT_PITCH = 25.0
_BOX_CORNERS = tuple((sx, sy, sz) for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1))


def _next_directory(parent: Path, stem: str) -> Path:
    parent.mkdir(parents=True, exist_ok=True)
    number = 1
    while True:
        candidate = parent / f"{stem}-{number:03d}"
        if not candidate.exists():
            return candidate
        number += 1


class FixtureDemoController:
    """Headless state machine for generating and explicitly selecting choices."""

    candidate_ids = _CANDIDATE_IDS

    def __init__(self, run_root: str | Path) -> None:
        self.run_root = Path(run_root).expanduser().resolve()
        self.candidate_set_run: Path | None = None
        self.result: dict[str, Any] | None = None
        self.last_selection: dict[str, Any] | None = None
        self._preview_views: dict[str, dict[str, float]] = {
            candidate_id: {"yaw": _DEFAULT_YAW, "pitch": _DEFAULT_PITCH}
            for candidate_id in self.candidate_ids
        }

    @property
    def generated(self) -> bool:
        return self.candidate_set_run is not None and bool(self.result and self.result.get("valid"))

    def create_tower_choices(self) -> dict[str, Any]:
        """Create a fresh contained two-candidate tower run."""
        run = _next_directory(self.run_root, "tower-choices")
        result = replay_candidate_set(_REQUEST, _BRIEF, _CANDIDATES, run, _PALETTE)
        if not result.get("valid"):
            self.candidate_set_run = None
            self.result = None
            self.last_selection = None
            failures = []
            for entry in result.get("candidate_index", []):
                if entry.get("status") != "valid":
                    issues = entry.get("issues") or [{"message": "candidate replay failed"}]
                    detail = "; ".join(f"{issue.get('code', 'ERROR')}: {issue.get('message', 'unknown failure')}" for issue in issues)
                    failures.append(f"{entry.get('id', '<unknown>')} ({detail})")
            if not failures and result.get("issues"):
                failures.append("candidate set (" + "; ".join(
                    f"{issue.get('code', 'ERROR')}: {issue.get('message', 'unknown failure')}"
                    for issue in result["issues"]
                ) + ")")
            summary = "; ".join(failures) or str(result.get("outcome", "failed"))
            if "SCHEMA_DEPENDENCY" in summary:
                summary += " Install this project into the same Python interpreter used to launch the demo (see docs/demo-setup.md)."
            raise ValueError(f"candidate replay failed: {summary}")
        self.candidate_set_run = run
        self.result = result
        self.last_selection = None
        self.reset_all_previews()
        return result

    def select(self, candidate_id: str) -> dict[str, Any]:
        """Select exactly one named candidate into a fresh contained bundle."""
        if not self.generated:
            raise ValueError("create tower choices before selecting a candidate")
        if candidate_id not in self.candidate_ids:
            raise ValueError(f"unknown candidate id: {candidate_id}")
        destination = _next_directory(self.run_root / "selections", candidate_id)
        selected = select_candidate(self.candidate_set_run, candidate_id, destination, _PALETTE)  # type: ignore[arg-type]
        self.last_selection = selected
        return selected

    def _preview_blocks(self, candidate_id: str) -> tuple[Block, ...]:
        if not self.generated:
            raise ValueError("create tower choices before rendering previews")
        if candidate_id not in self.candidate_ids:
            raise ValueError(f"unknown candidate id: {candidate_id}")
        model_path = self.candidate_set_run / "candidates" / candidate_id / "legoized.json"  # type: ignore[operator]
        model = json.loads(model_path.read_text(encoding="utf-8"))
        palette = load_palette(_PALETTE)
        profiles = profiles_from_palette(palette)
        blocks: list[Block] = []
        for placement in model["parts"]:
            profile = profiles[placement["part"]]
            bbox, _, _ = transformed_profile(profile, placement)
            blocks.append(Block(placement["id"], ((bbox[0] + bbox[3]) / 2, (bbox[1] + bbox[4]) / 2, (bbox[2] + bbox[5]) / 2), (bbox[3] - bbox[0], bbox[4] - bbox[1], bbox[5] - bbox[2]), _COLOURS.get(placement["colour"], "#888888")))
        return tuple(blocks)

    def preview_state(self, candidate_id: str) -> dict[str, float]:
        """Return a copy of the pure view state for one generated candidate."""
        if candidate_id not in self.candidate_ids:
            raise ValueError(f"unknown candidate id: {candidate_id}")
        return dict(self._preview_views[candidate_id])

    def rotate_preview(self, candidate_id: str, delta_yaw: float = 0.0, delta_pitch: float = 0.0) -> dict[str, float]:
        """Apply a deterministic drag delta to one candidate's camera only."""
        state = self.preview_state(candidate_id)
        state["yaw"] += float(delta_yaw)
        state["pitch"] = max(-89.0, min(89.0, state["pitch"] + float(delta_pitch)))
        self._preview_views[candidate_id] = state
        return dict(state)

    def drag_preview(self, candidate_id: str, screen_dx: float = 0.0, screen_dy: float = 0.0) -> dict[str, float]:
        """Apply a screen-space drag using the preview's natural direction convention.

        The orthographic preview's horizontal screen axis is opposite the
        camera yaw axis, so dragging right decreases yaw.  Vertical movement
        retains the existing pitch direction.
        """
        return self.rotate_preview(candidate_id, delta_yaw=-float(screen_dx), delta_pitch=float(screen_dy))

    def reset_preview(self, candidate_id: str) -> dict[str, float]:
        if candidate_id not in self.candidate_ids:
            raise ValueError(f"unknown candidate id: {candidate_id}")
        self._preview_views[candidate_id] = {"yaw": _DEFAULT_YAW, "pitch": _DEFAULT_PITCH}
        return self.preview_state(candidate_id)

    def reset_all_previews(self) -> None:
        for candidate_id in self.candidate_ids:
            self.reset_preview(candidate_id)

    def preview_projection(self, candidate_id: str) -> tuple[dict[str, Any], ...]:
        """Project centered generated geometry into the fitted preview canvas."""
        blocks = self._preview_blocks(candidate_id)
        state = self.preview_state(candidate_id)
        mins = [min(block.center[index] - block.size[index] / 2 for block in blocks) for index in range(3)]
        maxes = [max(block.center[index] + block.size[index] / 2 for block in blocks) for index in range(3)]
        center = tuple((mins[index] + maxes[index]) / 2 for index in range(3))
        centered = tuple(Block(block.id, tuple(block.center[index] - center[index] for index in range(3)), block.size, block.color) for block in blocks)
        yaw_radians, pitch_radians = math.radians(state["yaw"]), math.radians(state["pitch"])
        cy, sy = math.cos(yaw_radians), math.sin(yaw_radians)
        cp, sp = math.cos(pitch_radians), math.sin(pitch_radians)
        projected: list[tuple[float, float]] = []
        for block in centered:
            for sx, sy_sign, sz in _BOX_CORNERS:
                x = block.center[0] + sx * block.size[0] / 2
                y = block.center[1] + sy_sign * block.size[1] / 2
                z = block.center[2] + sz * block.size[2] / 2
                xr = x * cy - z * sy
                zr = x * sy + z * cy
                yr = y * cp - zr * sp
                projected.append((xr, -yr))
        span_x = max(point[0] for point in projected) - min(point[0] for point in projected)
        span_y = max(point[1] for point in projected) - min(point[1] for point in projected)
        scale = min((_PREVIEW_WIDTH - 2 * _PREVIEW_PADDING) / span_x if span_x else 1.0, (_PREVIEW_HEIGHT - 2 * _PREVIEW_PADDING) / span_y if span_y else 1.0)
        faces: list[dict[str, Any]] = []
        for block in centered:
            faces.extend(project_box(block, yaw=state["yaw"], pitch=state["pitch"], width=_PREVIEW_WIDTH, height=_PREVIEW_HEIGHT, scale=scale))
        faces.sort(key=lambda face: (face["depth"], face["block_id"], face["name"]))
        return tuple(faces)

    def preview_faces(self, candidate_id: str) -> tuple[dict[str, Any], ...]:
        """Backward-compatible alias for the fitted pure projection."""
        return self.preview_projection(candidate_id)


class FixtureDemoApp:
    """Minimal Tk view with generation, previews, and explicit choices."""

    def __init__(self, controller: FixtureDemoController, root: Any = None) -> None:
        if tk is None or ttk is None:
            raise RuntimeError("the fixture demo requires a Python build with tkinter")
        self.controller = controller
        self.root = root or tk.Tk()
        self.root.title("Brick Builder — tower choices")
        self.status = tk.StringVar(value="Create tower choices to begin.")
        self._build()

    def _build(self) -> None:
        toolbar = ttk.Frame(self.root, padding=8)
        toolbar.pack(fill="x")
        ttk.Button(toolbar, text="Create tower choices", command=self._create).pack(side="left")
        ttk.Label(self.root, textvariable=self.status, padding=(8, 0, 8, 8)).pack(fill="x")
        comparison = ttk.Frame(self.root, padding=8)
        comparison.pack(fill="both", expand=True)
        self.canvases: dict[str, Any] = {}
        self.select_buttons: dict[str, Any] = {}
        self.reset_buttons: dict[str, Any] = {}
        self._drag_start: dict[str, tuple[float, float]] = {}
        for candidate_id, label in (("compact-box", "Compact tower"), ("stepped-box", "Stepped tower")):
            panel = ttk.Frame(comparison)
            panel.pack(side="left", fill="both", expand=True, padx=4)
            ttk.Label(panel, text=label).pack()
            canvas = tk.Canvas(panel, width=360, height=260, background="#f6f7fb", highlightthickness=1, highlightbackground="#c4c9d4")
            canvas.pack()
            self.canvases[candidate_id] = canvas
            canvas.bind("<ButtonPress-1>", lambda event, item=candidate_id: self._press(item, event))
            canvas.bind("<B1-Motion>", lambda event, item=candidate_id: self._drag(item, event))
            reset_button = ttk.Button(panel, text="Reset view", command=lambda item=candidate_id: self._reset_view(item), state="disabled")
            reset_button.pack()
            self.reset_buttons[candidate_id] = reset_button
            button = ttk.Button(panel, text=f"Select {label}", command=lambda item=candidate_id: self._select(item), state="disabled")
            button.pack(pady=6)
            self.select_buttons[candidate_id] = button

    def _create(self) -> None:
        for canvas in self.canvases.values():
            canvas.delete("all")
        for button in self.select_buttons.values():
            button.configure(state="disabled")
        for button in self.reset_buttons.values():
            button.configure(state="disabled")
        try:
            self.controller.create_tower_choices()
            for candidate_id, canvas in self.canvases.items():
                canvas.delete("all")
                for face in self.controller.preview_faces(candidate_id):
                    points = [coordinate for point in face["points"] for coordinate in point]
                    canvas.create_polygon(*points, fill=face["color"], outline="#26354a")
                self.select_buttons[candidate_id].configure(state="normal")
                self.reset_buttons[candidate_id].configure(state="normal")
            self.status.set("Drag either tower to rotate it, or choose one. Selection writes a fresh auditable bundle.")
        except (OSError, ValueError, KeyError) as exc:
            self.status.set(f"Could not create choices: {exc}")

    def _press(self, candidate_id: str, event: Any) -> None:
        if not self.controller.generated:
            return
        self._drag_start[candidate_id] = (event.x, event.y)

    def _drag(self, candidate_id: str, event: Any) -> None:
        if not self.controller.generated:
            return
        previous = self._drag_start.get(candidate_id)
        if previous is None:
            self._press(candidate_id, event)
            return
        self._drag_start[candidate_id] = (event.x, event.y)
        self.controller.drag_preview(candidate_id, event.x - previous[0], event.y - previous[1])
        self._draw_preview(candidate_id)

    def _reset_view(self, candidate_id: str) -> None:
        if not self.controller.generated:
            return
        self.controller.reset_preview(candidate_id)
        self._draw_preview(candidate_id)

    def _draw_preview(self, candidate_id: str) -> None:
        canvas = self.canvases[candidate_id]
        canvas.delete("all")
        for face in self.controller.preview_faces(candidate_id):
            points = [coordinate for point in face["points"] for coordinate in point]
            canvas.create_polygon(*points, fill=face["color"], outline="#26354a")

    def _select(self, candidate_id: str) -> None:
        try:
            selected = self.controller.select(candidate_id)
            self.status.set(f"Selected {candidate_id}; bundle: {selected['run_dir']}")
        except (OSError, ValueError) as exc:
            self.status.set(f"Could not select {candidate_id}: {exc}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Show the offline tiny red tower fixture selector")
    parser.add_argument("--run-root", required=True, help="directory beneath which fresh demo artifacts are written")
    args = parser.parse_args(argv)
    if tk is None:
        raise SystemExit("the fixture demo requires a Python build with tkinter")
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        raise SystemExit(f"the fixture demo requires working Tcl/Tk support: {exc}") from exc
    FixtureDemoApp(FixtureDemoController(args.run_root), root).root.mainloop()


if __name__ == "__main__":
    main()
