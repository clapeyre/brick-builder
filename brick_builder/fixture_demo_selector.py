"""Small offline Tk fixture selector for the tiny red tower demo.

This is intentionally a fixture demonstration: the controller delegates all
artifact creation and explicit selection to :mod:`brick_builder.demo_replay`.
The canvases project the generated canonical LEGO geometry with the existing
box projection helper; no image files or provider output are involved.
"""

from __future__ import annotations

import argparse
import json
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

    @property
    def generated(self) -> bool:
        return self.candidate_set_run is not None and self.result is not None

    def create_tower_choices(self) -> dict[str, Any]:
        """Create a fresh contained two-candidate tower run."""
        run = _next_directory(self.run_root, "tower-choices")
        result = replay_candidate_set(_REQUEST, _BRIEF, _CANDIDATES, run, _PALETTE)
        self.candidate_set_run = run
        self.result = result
        self.last_selection = None
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

    def preview_faces(self, candidate_id: str) -> tuple[dict[str, Any], ...]:
        """Return deterministic Canvas-ready faces from generated model geometry."""
        if not self.generated:
            raise ValueError("create tower choices before rendering previews")
        if candidate_id not in self.candidate_ids:
            raise ValueError(f"unknown candidate id: {candidate_id}")
        model_path = self.candidate_set_run / "candidates" / candidate_id / "legoized.json"  # type: ignore[operator]
        model = json.loads(model_path.read_text(encoding="utf-8"))
        palette = load_palette(_PALETTE)
        profiles = profiles_from_palette(palette)
        faces: list[dict[str, Any]] = []
        for placement in model["parts"]:
            profile = profiles[placement["part"]]
            bbox, _, _ = transformed_profile(profile, placement)
            block = Block(placement["id"], ((bbox[0] + bbox[3]) / 2, (bbox[1] + bbox[4]) / 2, (bbox[2] + bbox[5]) / 2), (bbox[3] - bbox[0], bbox[4] - bbox[1], bbox[5] - bbox[2]), _COLOURS.get(placement["colour"], "#888888"))
            faces.extend(project_box(block, yaw=-35.0, pitch=25.0, width=360, height=260, scale=8.0))
        faces.sort(key=lambda face: (face["depth"], face["block_id"], face["name"]))
        return tuple(faces)


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
        for candidate_id, label in (("compact-box", "Compact tower"), ("stepped-box", "Stepped tower")):
            panel = ttk.Frame(comparison)
            panel.pack(side="left", fill="both", expand=True, padx=4)
            ttk.Label(panel, text=label).pack()
            canvas = tk.Canvas(panel, width=360, height=260, background="#f6f7fb", highlightthickness=1, highlightbackground="#c4c9d4")
            canvas.pack()
            self.canvases[candidate_id] = canvas
            button = ttk.Button(panel, text=f"Select {label}", command=lambda item=candidate_id: self._select(item), state="disabled")
            button.pack(pady=6)
            self.select_buttons[candidate_id] = button

    def _create(self) -> None:
        try:
            self.controller.create_tower_choices()
            for candidate_id, canvas in self.canvases.items():
                canvas.delete("all")
                for face in self.controller.preview_faces(candidate_id):
                    points = [coordinate for point in face["points"] for coordinate in point]
                    canvas.create_polygon(*points, fill=face["color"], outline="#26354a")
                self.select_buttons[candidate_id].configure(state="normal")
            self.status.set("Choose one tower. Selection writes a fresh auditable bundle.")
        except (OSError, ValueError, KeyError) as exc:
            self.status.set(f"Could not create choices: {exc}")

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
