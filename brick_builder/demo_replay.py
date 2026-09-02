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
from .legoization import legoize_stepped_box, legoize_wall_box
from .local_redesign import Block, project_box
from .palette import load_palette
from .validation import repair_hint, validate_model


COLOURS = {0: "#202124", 1: "#0055bf", 2: "#237841", 4: "#c91a09", 14: "#f2cd37", 15: "#ffffff", 25: "#fe8a18"}

# These are deliberately local, fixed replay cameras.  They are kept as
# named data rather than accepting camera input so evidence can be compared
# byte-for-byte across runs.
RENDER_CAMERAS = {
    "front": (0.0, 0.0),
    "three-quarter": (-35.0, 25.0),
}


def _write(path: Path, value: Any) -> None:
    if isinstance(value, str):
        path.write_text(value, encoding="utf-8", newline="\n")
    else:
        path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def _render(model: dict[str, Any], palette: dict[str, Any], path: Path, yaw: float, pitch: float) -> dict[str, Any]:
    profiles = profiles_from_palette(palette)
    faces: list[tuple[float, str, tuple[tuple[float, float], ...], str]] = []
    for placement in model["parts"]:
        profile = profiles[placement["part"]]
        bbox, _, _ = transformed_profile(profile, placement)
        block = Block(placement["id"], ((bbox[0] + bbox[3]) / 2, (bbox[1] + bbox[4]) / 2, (bbox[2] + bbox[5]) / 2), (bbox[3] - bbox[0], bbox[4] - bbox[1], bbox[5] - bbox[2]), COLOURS.get(placement["colour"], "#888888"))
        for face in project_box(block, yaw=yaw, pitch=pitch, width=640, height=480, scale=3.2):
            points = " ".join(f"{x:.2f},{y:.2f}" for x, y in face["points"])
            faces.append((face["depth"], placement["id"], face["points"], f'<polygon points="{points}" fill="{face["color"]}" stroke="#26354a" stroke-width="1"/>'))
    faces.sort(key=lambda item: (item[0], item[1], item[3]))
    body = "\n".join(item[3] for item in faces)
    _write(path, f'<svg xmlns="http://www.w3.org/2000/svg" width="640" height="480" viewBox="0 0 640 480"><rect width="640" height="480" fill="#f6f7fb"/><g>{body}</g></svg>\n')
    projected_points = [point for _depth, _part_id, face_points, _svg in faces for point in face_points]
    # The SVG intentionally remains unchanged; this metadata is extracted
    # from the same projected polygons used to write it.
    if projected_points:
        bounds: dict[str, list[float]] | None = {
            "x": [round(min(point[0] for point in projected_points), 2), round(max(point[0] for point in projected_points), 2)],
            "y": [round(min(point[1] for point in projected_points), 2), round(max(point[1] for point in projected_points), 2)],
        }
    else:
        bounds = None
    return {
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "rendered_part_ids": sorted({part_id for _depth, part_id, _face_points, _svg in faces}),
        "visible_polygon_count": len(faces),
        "non_background_bounds": bounds,
    }


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
    # Existing fixtures intentionally omit ``kind`` and retain the original
    # wall-box route.  New fixture families must opt in explicitly; creative
    # request text is never used to infer a LEGOizer.
    scaffold_kind = scaffold.get("kind", "wall_box")
    legoizer_scaffold = {key: value for key, value in scaffold.items() if key != "kind"}
    if scaffold_kind == "wall_box":
        result = legoize_wall_box(legoizer_scaffold, palette)
    elif scaffold_kind == "stepped_box":
        result = legoize_stepped_box(legoizer_scaffold, palette)
    else:
        issue = {
            "code": "UNKNOWN_SCAFFOLD_KIND",
            "path": "scaffold.kind",
            "message": f"unsupported scaffold kind {scaffold_kind!r}; expected 'wall_box' or 'stepped_box'",
            "repair_hint": "Set scaffold.kind to 'wall_box' or 'stepped_box'.",
        }
        _write(root / "failure.json", {"valid": False, "issues": [issue]})
        manifest = finalize_manifest(root, outcome="failed", attempts=1, max_attempts=1, palette_path=palette_path, adapter="OfflineEndToEndReplay")
        return {"valid": False, "outcome": "failed", "run_dir": str(root), "manifest": manifest, "issues": [issue]}
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
    render_evidence = {"schema_version": 1, "renders": []}
    for camera_id, (yaw, pitch) in RENDER_CAMERAS.items():
        filename = f"render-{camera_id}.svg"
        metadata = _render(model, palette, root / filename, yaw, pitch)
        render_evidence["renders"].append({"camera_id": camera_id, "file": filename, **metadata})
    _write(root / "render-evidence.json", render_evidence)
    manifest = finalize_manifest(root, outcome="success", attempts=1, max_attempts=1, palette_path=palette_path, adapter="OfflineEndToEndReplay")
    return {"valid": True, "outcome": "success", "run_dir": str(root), "model_id": model["model_id"], "ldr_sha256": hashlib.sha256(output.read_bytes()).hexdigest(), "manifest": manifest}
