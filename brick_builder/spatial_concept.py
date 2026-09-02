"""Deterministic offline contract for the first spatial-concept MVP slice.

This module is deliberately provider-neutral.  A provider (or a scripted test
fixture) supplies a JSON-like response; this session validates and retains the
response before any LEGOization is attempted.
"""

from __future__ import annotations

import json
import hashlib
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .local_redesign import Block, CAMERA_PRESETS, project_box


FORMAT = "brick-builder.spatial-concept/v1"
MAX_ATTEMPTS = 3
MIN_CONCEPTS = 2
MAX_CONCEPTS = 3
MAX_BOXES_PER_CONCEPT = 12
MIN_DIMENSION = 0.5
MAX_DIMENSION = 16.0
MAX_ABS_COORDINATE = 32.0


class SpatialConceptError(ValueError):
    """Raised when a provider response cannot satisfy the session contract."""


@dataclass(frozen=True)
class GenericBoxConcept:
    """A schema-validated, inspectable concept made only of generic boxes."""

    id: str
    label: str
    boxes: tuple[Block, ...]
    render: Mapping[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "geometry": [
                {
                    "ref": box.id,
                    "center": list(box.center),
                    "size": list(box.size),
                    "color": box.color,
                }
                for box in self.boxes
            ],
            "render": dict(self.render),
        }


def render_concept(concept: GenericBoxConcept, path: str | Path) -> dict[str, Any]:
    """Write the fixed, deterministic SVG preview for one concept."""
    output = Path(path)
    faces: list[tuple[float, str, str]] = []
    camera = concept.render["camera"]
    yaw, pitch = CAMERA_PRESETS[camera]
    for box in concept.boxes:
        for face in project_box(box, yaw=yaw, pitch=pitch, width=430, height=360, scale=24):
            points = " ".join(f"{x:.2f},{y:.2f}" for x, y in face["points"])
            svg = f'<polygon points="{points}" fill="{face["color"]}" stroke="#26354a" stroke-width="1"/>'
            faces.append((float(face["depth"]), box.id, svg))
    faces.sort(key=lambda item: (item[0], item[1], item[2]))
    body = "\n".join(item[2] for item in faces)
    content = f'<svg xmlns="http://www.w3.org/2000/svg" width="430" height="360" viewBox="0 0 430 360"><rect width="430" height="360" fill="#f6f7fb"/><g>{body}</g></svg>\n'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(content, encoding="utf-8", newline="\n")
    return {
        "file": output.name,
        "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
        "geometry_refs": [box.id for box in concept.boxes],
        "visible_polygon_count": len(faces),
    }


def write_session_artifacts(session: "SpatialConceptSession", run_dir: str | Path) -> dict[str, Any]:
    """Persist one accepted/clarification session and its previews under run_dir."""
    root = Path(run_dir)
    root.mkdir(parents=True, exist_ok=True)
    snapshot = session.snapshot()
    (root / "spatial-concept-session.json").write_text(
        json.dumps(snapshot, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    renders = []
    if session.status == "success":
        for concept in session.concepts:
            renders.append(render_concept(concept, root / f"render-{concept.id}.svg"))
    return {**snapshot, "run_dir": str(root), "renders": renders}


def _finite_number(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SpatialConceptError(f"{name} must be a finite number")
    number = float(value)
    if not math.isfinite(number):
        raise SpatialConceptError(f"{name} must be a finite number")
    return number


def _text(value: Any, name: str, *, max_length: int = 160) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SpatialConceptError(f"{name} must be a non-empty string")
    if len(value) > max_length:
        raise SpatialConceptError(f"{name} is too long (maximum {max_length} characters)")
    return value


def _validate_render(value: Any, box_refs: tuple[str, ...]) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise SpatialConceptError("render must be an object")
    camera = value.get("camera", "three-quarter")
    if camera not in CAMERA_PRESETS:
        raise SpatialConceptError("render.camera must be a supported camera preset")
    width = _finite_number(value.get("width", 430), "render.width")
    height = _finite_number(value.get("height", 360), "render.height")
    scale = _finite_number(value.get("scale", 24), "render.scale")
    if width != 430 or height != 360 or scale != 24:
        raise SpatialConceptError("render dimensions and scale must use the fixed MVP values")
    refs = value.get("geometry_refs", list(box_refs))
    if refs != list(box_refs):
        raise SpatialConceptError("render.geometry_refs must match geometry order")
    return {
        "camera": camera,
        "width": 430,
        "height": 360,
        "scale": 24,
        "geometry_refs": list(box_refs),
    }


def _validate_concept(value: Any, index: int) -> GenericBoxConcept:
    if not isinstance(value, dict):
        raise SpatialConceptError(f"concept {index} must be an object")
    concept_id = _text(value.get("id"), f"concept {index}.id", max_length=48)
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,47}", concept_id):
        raise SpatialConceptError(
            f"concept {index}.id must contain only letters, numbers, '_' or '-'"
        )
    label = _text(value.get("label"), f"concept {index}.label")
    geometry = value.get("geometry")
    if not isinstance(geometry, list) or not 1 <= len(geometry) <= MAX_BOXES_PER_CONCEPT:
        raise SpatialConceptError(
            f"concept {index}.geometry must contain 1-{MAX_BOXES_PER_CONCEPT} boxes"
        )
    boxes: list[Block] = []
    refs: set[str] = set()
    for box_index, raw_box in enumerate(geometry, start=1):
        if not isinstance(raw_box, dict):
            raise SpatialConceptError(f"concept {index} box {box_index} must be an object")
        ref = _text(raw_box.get("ref"), f"concept {index} box {box_index}.ref", max_length=48)
        if ref in refs:
            raise SpatialConceptError(f"concept {index} has duplicate geometry ref {ref!r}")
        refs.add(ref)
        center = raw_box.get("center")
        size = raw_box.get("size")
        if not isinstance(center, list) or len(center) != 3:
            raise SpatialConceptError(f"geometry ref {ref!r} center must have three values")
        if not isinstance(size, list) or len(size) != 3:
            raise SpatialConceptError(f"geometry ref {ref!r} size must have three values")
        center_values = tuple(_finite_number(item, f"geometry ref {ref!r} center") for item in center)
        size_values = tuple(_finite_number(item, f"geometry ref {ref!r} size") for item in size)
        if any(abs(item) > MAX_ABS_COORDINATE for item in center_values):
            raise SpatialConceptError(f"geometry ref {ref!r} is outside the coordinate bound")
        if any(item < MIN_DIMENSION or item > MAX_DIMENSION for item in size_values):
            raise SpatialConceptError(f"geometry ref {ref!r} has out-of-bounds dimensions")
        color = raw_box.get("color", "#2878b5")
        if not isinstance(color, str) or len(color) != 7 or not color.startswith("#"):
            raise SpatialConceptError(f"geometry ref {ref!r} color must be a #rrggbb string")
        try:
            int(color[1:], 16)
        except ValueError as exc:
            raise SpatialConceptError(f"geometry ref {ref!r} color must be a #rrggbb string") from exc
        boxes.append(Block(ref, center_values, size_values, color.lower()))
    render = _validate_render(value.get("render", {}), tuple(box.id for box in boxes))
    # Exercise the existing deterministic projection as part of validation.
    yaw, pitch = CAMERA_PRESETS[render["camera"]]
    for box in boxes:
        project_box(box, yaw=yaw, pitch=pitch, width=430, height=360, scale=24)
    return GenericBoxConcept(concept_id, label, tuple(boxes), render)


class SpatialConceptSession:
    """Fixed-attempt, offline session for validating spatial concepts."""

    def __init__(self, request_text: str) -> None:
        if not isinstance(request_text, str) or not request_text.strip():
            raise ValueError("request_text must be a non-empty string")
        self.request_text = request_text
        self.max_attempts = MAX_ATTEMPTS
        self.attempts = 0
        self.status = "pending"
        self.clarification: str | None = None
        self.concepts: tuple[GenericBoxConcept, ...] = ()
        self.feedback: tuple[str, ...] = ()

    def submit(self, response: Mapping[str, Any]) -> dict[str, Any]:
        if self.status == "exhausted":
            raise SpatialConceptError("session attempt limit already exhausted")
        if self.status in {"clarification", "success"}:
            raise SpatialConceptError("session already has a terminal result")
        self.attempts += 1
        try:
            if not isinstance(response, dict):
                raise SpatialConceptError("response must be an object")
            kind = response.get("kind")
            if kind == "clarification":
                question = _text(response.get("question"), "clarification.question", max_length=240)
                self.clarification = question
                self.status = "clarification"
                self.feedback = ()
            elif kind == "concepts":
                raw_concepts = response.get("concepts")
                if not isinstance(raw_concepts, list) or not MIN_CONCEPTS <= len(raw_concepts) <= MAX_CONCEPTS:
                    raise SpatialConceptError("concepts must contain exactly 2 or 3 proposals")
                concepts = tuple(_validate_concept(item, index) for index, item in enumerate(raw_concepts, start=1))
                if len({concept.id for concept in concepts}) != len(concepts):
                    raise SpatialConceptError("concept ids must be distinct")
                self.concepts = concepts
                self.status = "success"
                self.feedback = ()
            else:
                raise SpatialConceptError("response.kind must be 'clarification' or 'concepts'")
        except SpatialConceptError as exc:
            message = str(exc)
            self.feedback = (message,)
            if self.attempts >= self.max_attempts:
                self.status = "exhausted"
            return self.snapshot()
        return self.snapshot()

    def snapshot(self) -> dict[str, Any]:
        return {
            "format": FORMAT,
            "request_text": self.request_text,
            "status": self.status,
            "attempts": self.attempts,
            "max_attempts": self.max_attempts,
            "clarification": self.clarification,
            "concepts": [concept.to_dict() for concept in self.concepts],
            "feedback": list(self.feedback),
        }

    def serialize(self) -> str:
        return json.dumps(self.snapshot(), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
