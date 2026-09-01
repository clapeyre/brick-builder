"""Contained, offline replay of the first Brick Builder end-to-end path.

The inputs are deliberately fixtures rather than production brief/scaffold
schemas.  Every stage is written beneath one run directory and the final
manifest hashes the complete artifact chain.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .compiler import compile_model
from .generation import _analysis_document, finalize_manifest
from .geometry import profiles_from_palette, transformed_profile, validate_geometry
from .legoization import legoize_wall_box
from .local_redesign import Block, project_box
from .palette import load_palette
from .validation import repair_hint, validate_model


COLOURS = {0: "#202124", 1: "#0055bf", 2: "#237841", 4: "#c91a09", 14: "#f2cd37", 15: "#ffffff", 25: "#fe8a18"}


def _write(path: Path, value: Any) -> None:
    if isinstance(value, str):
        path.write_text(value, encoding="utf-8", newline="\n")
    else:
        path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def _render(model: dict[str, Any], palette: dict[str, Any], path: Path, yaw: float, pitch: float) -> None:
    profiles = profiles_from_palette(palette)
    faces: list[tuple[float, str, str]] = []
    for placement in model["parts"]:
        profile = profiles[placement["part"]]
        bbox, _, _ = transformed_profile(profile, placement)
        block = Block(placement["id"], ((bbox[0] + bbox[3]) / 2, (bbox[1] + bbox[4]) / 2, (bbox[2] + bbox[5]) / 2), (bbox[3] - bbox[0], bbox[4] - bbox[1], bbox[5] - bbox[2]), COLOURS.get(placement["colour"], "#888888"))
        for face in project_box(block, yaw=yaw, pitch=pitch, width=640, height=480, scale=3.2):
            points = " ".join(f"{x:.2f},{y:.2f}" for x, y in face["points"])
            faces.append((face["depth"], placement["id"], f'<polygon points="{points}" fill="{face["color"]}" stroke="#26354a" stroke-width="1"/>'))
    faces.sort(key=lambda item: (item[0], item[1], item[2]))
    body = "\n".join(item[2] for item in faces)
    _write(path, f'<svg xmlns="http://www.w3.org/2000/svg" width="640" height="480" viewBox="0 0 640 480"><rect width="640" height="480" fill="#f6f7fb"/><g>{body}</g></svg>\n')


def replay_demo(request_path: str | Path, brief_path: str | Path, scaffold_path: str | Path, run_dir: str | Path, palette_path: str | Path) -> dict[str, Any]:
    """Replay checked-in fixtures into a fresh contained run directory."""
    request_path, brief_path, scaffold_path = map(Path, (request_path, brief_path, scaffold_path))
    root = Path(run_dir)
    if root.exists():
        raise ValueError(f"run directory already exists: {root}")
    root.mkdir(parents=True)
    palette = load_palette(palette_path)
    request = request_path.read_text(encoding="utf-8")
    brief = json.loads(brief_path.read_text(encoding="utf-8"))
    scaffold = json.loads(scaffold_path.read_text(encoding="utf-8"))
    _write(root / "request.txt", request)
    _write(root / "brief.json", brief)
    _write(root / "scaffold.json", scaffold)
    result = legoize_wall_box(scaffold, palette)
    _write(root / "coverage.json", {"required": [list(c) for c in result.coverage.required], "covered": [list(c) for c in result.coverage.covered], "uncovered": [list(c) for c in result.coverage.uncovered], "complete": result.coverage.complete, "diagnostics": list(result.coverage.diagnostics)})
    if not result.coverage.complete or not result.structural_valid:
        issues = [{"code": i.code, "path": i.path, "message": i.message, "repair_hint": repair_hint(i.code)} for i in result.structural_issues]
        if not result.coverage.complete:
            issues.append({"code": "UNFILLED_TARGET_REGION", "path": "scaffold", "message": "; ".join(result.coverage.diagnostics), "repair_hint": "Use a supported one- or two-stud depth scaffold."})
        _write(root / "failure.json", {"valid": False, "issues": issues})
        manifest = finalize_manifest(root, outcome="failed", attempts=1, max_attempts=1, palette_path=palette_path, adapter="OfflineEndToEndReplay")
        return {"valid": False, "outcome": "failed", "run_dir": str(root), "manifest": manifest, "issues": issues}
    model = result.model
    _write(root / "legoized.json", model)
    validate_model(model, palette)
    analysis = validate_geometry(model, palette)
    _write(root / "validation.json", {"valid": True, "issues": []})
    _write(root / "analysis.json", _analysis_document(analysis))
    output = compile_model(model, root / "final.ldr", palette)
    _render(model, palette, root / "render-front.svg", 0, 0)
    _render(model, palette, root / "render-three-quarter.svg", -35, 25)
    manifest = finalize_manifest(root, outcome="success", attempts=1, max_attempts=1, palette_path=palette_path, adapter="OfflineEndToEndReplay")
    return {"valid": True, "outcome": "success", "run_dir": str(root), "model_id": model["model_id"], "ldr_sha256": hashlib.sha256(output.read_bytes()).hexdigest(), "manifest": manifest}
