"""Contained fixed-camera rendering for composed concept candidates."""

from __future__ import annotations

import json
import re
from os import PathLike
from pathlib import Path
from typing import Any, Mapping

from .demo_replay import RENDER_CAMERAS, _render
from .palette import load_palette


FORMAT = "brick-builder.candidate-rendering/v1"
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,47}$")


def _write(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def render_candidate_set(
    candidate_set: Mapping[str, Any],
    run_dir: str | Path,
    palette: Mapping[str, Any] | str | Path,
) -> dict[str, Any]:
    """Render every successful candidate with the fixed replay cameras.

    Candidate composition decides success; this function only renders the
    already compiled model stored in a successful bridge snapshot. Failed
    candidates remain represented in the returned index but receive no render
    artifacts.
    """
    if not isinstance(candidate_set, Mapping):
        raise ValueError("candidate set must be an object")
    candidates = candidate_set.get("candidates")
    if not isinstance(candidates, list):
        raise ValueError("candidate set must contain a candidate list")
    root = Path(run_dir)
    palette_data = load_palette(palette) if isinstance(palette, (str, PathLike)) else dict(palette)
    records: list[dict[str, Any]] = []
    for candidate in candidates:
        if not isinstance(candidate, Mapping):
            raise ValueError("candidate record must be an object")
        candidate_id = candidate.get("id")
        if not isinstance(candidate_id, str) or not _ID.fullmatch(candidate_id):
            raise ValueError("candidate id must be a safe stable identifier")
        if candidate.get("status") != "success":
            records.append({"id": candidate_id, "status": "failed", "diagnostics": list(candidate.get("diagnostics", []))})
            continue
        bridge = candidate.get("bridge")
        assembly = bridge.get("assembly") if isinstance(bridge, Mapping) else None
        model = assembly.get("model") if isinstance(assembly, Mapping) else None
        if not isinstance(model, dict) or not isinstance(model.get("parts"), list):
            raise ValueError(f"successful candidate {candidate_id!r} has no canonical model")
        child = root / "candidates" / candidate_id
        if not child.is_dir():
            raise ValueError(f"candidate run directory is missing: {candidate_id}")
        render_evidence: dict[str, Any] = {"schema_version": 1, "renders": []}
        for camera_id, (yaw, pitch) in RENDER_CAMERAS.items():
            filename = f"render-{camera_id}.svg"
            metadata = _render(model, palette_data, child / filename, yaw, pitch)
            render_evidence["renders"].append({"camera_id": camera_id, "file": filename, **metadata})
        evidence_path = child / "render-evidence.json"
        _write(evidence_path, render_evidence)
        records.append({
            "id": candidate_id,
            "status": "success",
            "model_id": model.get("model_id"),
            "part_ids": [part.get("id") for part in model["parts"] if isinstance(part, Mapping)],
            "render_evidence": f"candidates/{candidate_id}/render-evidence.json",
            "renders": render_evidence["renders"],
        })
    return {
        "format": FORMAT,
        "status": "success" if candidate_set.get("status") == "success" else "rejected",
        "candidates": records,
    }
