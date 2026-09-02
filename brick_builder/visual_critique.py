"""Provider-neutral deterministic observations over existing render evidence.

This module is deliberately downstream of composition and rendering.  It does
not inspect pixels, call a provider, rank candidates, or repair a model.  The
caller supplies the already-produced ``render-evidence`` metadata, either
inside each candidate record or in ``render_evidence_by_candidate``.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from typing import Any, Mapping, Sequence


FORMAT = "brick-builder.visual-critique/v1"
MAX_CANDIDATES = 3
MAX_CAMERAS = 8
MAX_PARTS = 512


class VisualCritiqueError(ValueError):
    """Raised when the bounded visual-critique input is incomplete or invalid."""


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _number(value: Any, path: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise VisualCritiqueError(f"{path} must be a finite number")
    return float(value)


def _text(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise VisualCritiqueError(f"{path} must be a non-empty string")
    if len(value) > 512:
        raise VisualCritiqueError(f"{path} is too long (maximum 512 characters)")
    return value


def _part_ids(candidate: Mapping[str, Any], path: str) -> tuple[str, ...]:
    model: Any = candidate.get("model")
    if model is None:
        bridge = candidate.get("bridge")
        assembly = bridge.get("assembly") if isinstance(bridge, Mapping) else None
        model = assembly.get("model") if isinstance(assembly, Mapping) else None
    parts = model.get("parts") if isinstance(model, Mapping) else candidate.get("part_ids")
    if parts is None:
        return ()
    if isinstance(parts, Mapping) or not isinstance(parts, (list, tuple)):
        raise VisualCritiqueError(f"{path}.parts must be a list when supplied")
    if len(parts) > MAX_PARTS:
        raise VisualCritiqueError(f"{path}.parts exceeds the bound of {MAX_PARTS}")
    ids: list[str] = []
    for index, part in enumerate(parts):
        value = part.get("id") if isinstance(part, Mapping) else part
        ids.append(_text(value, f"{path}.parts[{index}].id"))
    if len(set(ids)) != len(ids):
        raise VisualCritiqueError(f"{path}.parts contains duplicate ids")
    return tuple(sorted(ids))


def _landmarks(candidate: Mapping[str, Any], path: str) -> tuple[dict[str, Any], ...]:
    raw = candidate.get("landmarks", ())
    if not isinstance(raw, (list, tuple)):
        raise VisualCritiqueError(f"{path}.landmarks must be a list when supplied")
    result: list[dict[str, Any]] = []
    for index, item in enumerate(raw):
        if not isinstance(item, Mapping):
            raise VisualCritiqueError(f"{path}.landmarks[{index}] must be an object")
        landmark_id = _text(item.get("id"), f"{path}.landmarks[{index}].id")
        refs = item.get("part_ids", [])
        if not isinstance(refs, (list, tuple)) or not refs:
            raise VisualCritiqueError(f"{path}.landmarks[{index}].part_ids must be a non-empty list")
        part_ids = tuple(sorted(_text(ref, f"{path}.landmarks[{index}].part_ids[]") for ref in refs))
        result.append({"id": landmark_id, "part_ids": list(part_ids)})
    if len({item["id"] for item in result}) != len(result):
        raise VisualCritiqueError(f"{path}.landmarks contains duplicate ids")
    return tuple(sorted(result, key=lambda item: item["id"]))


def _evidence(value: Any, path: str, *, inline_renders: Any = None) -> Mapping[str, Any]:
    # candidate_rendering exposes the same render entries alongside a
    # relative artifact reference.  Accept that equivalent record shape so
    # critique remains a pure consumer of existing evidence.
    if isinstance(value, str) and inline_renders is not None:
        value = {"schema_version": 1, "renders": inline_renders, "artifact_ref": value}
    if not isinstance(value, Mapping):
        raise VisualCritiqueError(f"{path} must be a render-evidence object; provide existing render metadata")
    if value.get("schema_version") != 1:
        raise VisualCritiqueError(f"{path}.schema_version must be 1")
    renders = value.get("renders")
    if not isinstance(renders, (list, tuple)) or not renders:
        raise VisualCritiqueError(f"{path}.renders must contain at least one camera entry")
    if len(renders) > MAX_CAMERAS:
        raise VisualCritiqueError(f"{path}.renders exceeds the bound of {MAX_CAMERAS} cameras")
    return value


def _observation(render: Mapping[str, Any], expected: tuple[str, ...], landmarks: tuple[dict[str, Any], ...], path: str, artifact_ref: str | None = None) -> dict[str, Any]:
    camera = _text(render.get("camera_id"), f"{path}.camera_id")
    file_ref = _text(render.get("file"), f"{path}.file")
    sha256 = _text(render.get("sha256"), f"{path}.sha256")
    visible_raw = render.get("rendered_part_ids", [])
    if not isinstance(visible_raw, (list, tuple)):
        raise VisualCritiqueError(f"{path}.rendered_part_ids must be a list")
    visible = tuple(sorted({_text(item, f"{path}.rendered_part_ids[]") for item in visible_raw}))
    bounds = render.get("non_background_bounds")
    silhouette: dict[str, Any] = {"occupancy": None, "aspect": None, "bounds": None}
    if bounds is not None:
        if not isinstance(bounds, Mapping) or not isinstance(bounds.get("x"), (list, tuple)) or not isinstance(bounds.get("y"), (list, tuple)) or len(bounds["x"]) != 2 or len(bounds["y"]) != 2:
            raise VisualCritiqueError(f"{path}.non_background_bounds must contain two-value x and y ranges")
        x0, x1 = (_number(item, f"{path}.non_background_bounds.x") for item in bounds["x"])
        y0, y1 = (_number(item, f"{path}.non_background_bounds.y") for item in bounds["y"])
        width = max(0.0, x1 - x0)
        height = max(0.0, y1 - y0)
        canvas_width = _number(render.get("canvas_width", 640), f"{path}.canvas_width")
        canvas_height = _number(render.get("canvas_height", 480), f"{path}.canvas_height")
        if canvas_width <= 0 or canvas_height <= 0:
            raise VisualCritiqueError(f"{path}.canvas dimensions must be positive")
        silhouette = {
            "occupancy": round(width * height / (canvas_width * canvas_height), 6),
            "aspect": round(width / height, 6) if height else None,
            "bounds": {"x": [x0, x1], "y": [y0, y1]},
        }
    part_visibility = {part_id: part_id in visible for part_id in expected}
    landmark_visibility = {
        item["id"]: all(part_id in visible for part_id in item["part_ids"])
        for item in landmarks
    }
    evidence_ref: dict[str, Any] = {"file": file_ref, "sha256": sha256}
    if artifact_ref is not None:
        evidence_ref["artifact"] = artifact_ref
    return {
        "camera_id": camera,
        "evidence": evidence_ref,
        "observations": {
            "silhouette": silhouette,
            "visible_part_ids": list(visible),
            "part_visibility": part_visibility,
            "landmark_visibility": landmark_visibility,
        },
    }


@dataclass(frozen=True)
class VisualCritiqueResult:
    """Stable, non-ranking observations for a successful candidate set."""

    candidates: tuple[dict[str, Any], ...]

    def snapshot(self) -> dict[str, Any]:
        return {"format": FORMAT, "candidates": list(self.candidates)}

    def serialize(self) -> str:
        return _canonical(self.snapshot())


def critique_candidate_set(
    composed: Mapping[str, Any] | Any | Sequence[Mapping[str, Any]],
    *,
    render_evidence_by_candidate: Mapping[str, Mapping[str, Any]] | None = None,
) -> VisualCritiqueResult:
    """Observe a successful composition snapshot without choosing a candidate.

    ``composed`` may be a ``CandidateCompositionResult``, its snapshot, or a
    bounded sequence of equivalent successful candidate records.  Evidence is
    metadata from the existing renderer, not image data; references remain
    unchanged in the result.
    """
    if hasattr(composed, "snapshot") and callable(composed.snapshot):
        composed = composed.snapshot()
    if isinstance(composed, Mapping):
        if composed.get("status") != "success":
            raise VisualCritiqueError("composition must have status 'success' before visual critique")
        records = composed.get("candidates")
    else:
        records = composed
    if not isinstance(records, (list, tuple)) or not 1 <= len(records) <= MAX_CANDIDATES:
        raise VisualCritiqueError(f"candidates must contain 1-{MAX_CANDIDATES} records")
    external = render_evidence_by_candidate or {}
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, candidate in enumerate(records, start=1):
        if not isinstance(candidate, Mapping):
            raise VisualCritiqueError(f"candidate {index} must be an object")
        candidate_id = _text(candidate.get("id"), f"candidate {index}.id")
        if candidate_id in seen:
            raise VisualCritiqueError(f"candidate {candidate_id!r} is duplicated")
        seen.add(candidate_id)
        if candidate.get("status") not in {"success", "valid"}:
            raise VisualCritiqueError(f"candidate {candidate_id!r} must be successful before critique")
        evidence = candidate.get("render_evidence")
        if evidence is None:
            evidence = external.get(candidate_id)
        if evidence is None:
            raise VisualCritiqueError(f"candidate {candidate_id!r} has no render evidence; supply existing render-evidence metadata")
        expected = _part_ids(candidate, f"candidate {candidate_id!r}")
        landmarks = _landmarks(candidate, f"candidate {candidate_id!r}")
        evidence_data = _evidence(
            evidence,
            f"candidate {candidate_id!r}.render_evidence",
            inline_renders=candidate.get("renders"),
        )
        renders = evidence_data["renders"]
        artifact_ref = evidence_data.get("artifact_ref") if isinstance(evidence_data.get("artifact_ref"), str) else None
        observations = tuple(_observation(render, expected, landmarks, f"candidate {candidate_id!r}.renders[{i}]", artifact_ref) for i, render in enumerate(renders))
        if len({item["camera_id"] for item in observations}) != len(observations):
            raise VisualCritiqueError(f"candidate {candidate_id!r} has duplicate camera ids")
        result.append({"id": candidate_id, "model_id": candidate.get("model_id"), "cameras": list(observations)})
    return VisualCritiqueResult(tuple(result))


critique_composed_candidates = critique_candidate_set
