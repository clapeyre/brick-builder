"""Provider-neutral bridge from one accepted generic box to LEGOization.

The bridge is intentionally a contract boundary: it validates the spatial
concept, records the unit/colour mapping, and delegates part selection and
validation to :func:`legoize_wall_box`.  It never repairs or writes a
model-controlled path.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from os import PathLike
from typing import Any, Mapping

from .legoization import LEGOizationResult, WallBoxScaffold, legoize_wall_box
from .palette import load_palette
from .colour_mapping import resolve_source_colour
from .spatial_concept import GenericBoxConcept


FORMAT = "brick-builder.legoization-bridge/v1"
DEFAULT_COLOUR = None
MAX_WIDTH_STUDS = 16
MAX_DEPTH_STUDS = 2
MAX_HEIGHT_PLATES = 12
EPSILON = 1e-9


@dataclass(frozen=True)
class LEGOizationBridgeResult:
    """Deterministic success or actionable rejection from the bridge."""

    status: str
    source_concept: dict[str, Any]
    mapping: dict[str, Any] | None
    diagnostics: tuple[str, ...]
    legoization: LEGOizationResult | None = None
    compiled_ldr: str | None = None

    @property
    def success(self) -> bool:
        return self.status == "success"

    def snapshot(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "format": FORMAT,
            "status": self.status,
            "source_concept": self.source_concept,
            "mapping": self.mapping,
            "diagnostics": list(self.diagnostics),
        }
        if self.legoization is not None:
            report = self.legoization.coverage
            result["assembly"] = {
                "model": self.legoization.model,
                "coverage": {
                    "required": [list(cell) for cell in report.required],
                    "covered": [list(cell) for cell in report.covered],
                    "uncovered": [list(cell) for cell in report.uncovered],
                    "diagnostics": list(report.diagnostics),
                    "complete": report.complete,
                },
                "coverage_complete": report.complete,
                "structural_valid": self.legoization.structural_valid,
                "structural_issues": [
                    {"path": issue.path, "message": issue.message, "code": issue.code}
                    for issue in self.legoization.structural_issues
                ],
                "valid": self.legoization.valid,
                "compiled_ldr": self.compiled_ldr,
            }
        return result

    def serialize(self) -> str:
        return json.dumps(self.snapshot(), sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _compiled_ldr(model: Mapping[str, Any]) -> str:
    """Mirror the existing compiler's deterministic text format in memory."""
    lines = [
        f"0 Brick Builder model: {model['model_id']}",
        f"0 Name: {model.get('name', model['model_id'])}",
        "0 Author: Brick Builder deterministic compiler",
        "0 !BRICK_BUILDER_SCHEMA_VERSION 1",
    ]
    for placement in model["parts"]:
        values = placement["translation_ldu"] + placement["matrix"]
        lines.append("1 " + " ".join(str(value) for value in [placement["colour"], *values, placement["part"]]))
    return "\n".join(lines) + "\n"


def _source(concept: GenericBoxConcept) -> dict[str, Any]:
    return concept.to_dict()


def legoize_accepted_box(
    concept: GenericBoxConcept,
    palette: Mapping[str, Any] | str | PathLike[str],
    *,
    colour: int | None = DEFAULT_COLOUR,
) -> LEGOizationBridgeResult:
    """Convert exactly one accepted, centered, grounded generic box.

    Spatial units are explicit: ``x`` and ``z`` size are studs, ``y`` size is
    plates, and the box's bottom face must be at y=0.  The wall-box path is
    centered at the origin, so x/z centers must also be zero; rejecting them
    avoids silently losing a source translation.
    """
    if not isinstance(concept, GenericBoxConcept):
        raise TypeError("concept must be a GenericBoxConcept")
    source = _source(concept)
    diagnostics: list[str] = []
    if len(concept.boxes) != 1:
        diagnostics.append("MULTI_BOX_UNSUPPORTED: provide exactly one generic box")
        return LEGOizationBridgeResult("rejected", source, None, tuple(diagnostics))

    box = concept.boxes[0]
    width, height, depth = box.size
    values = (("width_studs", width), ("height_plates", height), ("depth_studs", depth))
    for name, value in values:
        if abs(value - round(value)) > EPSILON:
            diagnostics.append(f"NON_INTEGRAL_DIMENSION: {name}={value:g} must be an integer")
    if abs(box.center[1] - height / 2) > EPSILON:
        diagnostics.append("NOT_GROUNDED: box bottom must lie on spatial y=0")
    if abs(box.center[0]) > EPSILON or abs(box.center[2]) > EPSILON:
        diagnostics.append("TRANSLATION_UNSUPPORTED: box center x and z must be zero")
    if diagnostics:
        return LEGOizationBridgeResult("rejected", source, None, tuple(diagnostics))

    width_i, height_i, depth_i = int(round(width)), int(round(height)), int(round(depth))
    bounds = (("width_studs", width_i, 1, MAX_WIDTH_STUDS),
              ("depth_studs", depth_i, 1, MAX_DEPTH_STUDS),
              ("height_plates", height_i, 1, MAX_HEIGHT_PLATES))
    for name, value, lower, upper in bounds:
        if not lower <= value <= upper:
            diagnostics.append(f"OUT_OF_BOUNDS: {name}={value} must be between {lower} and {upper}")
    if diagnostics:
        return LEGOizationBridgeResult("rejected", source, None, tuple(diagnostics))

    palette_data = load_palette(palette) if isinstance(palette, (str, PathLike)) else dict(palette)
    if colour is None:
        colour, colour_error = resolve_source_colour(box.color, palette_data)
        if colour_error:
            return LEGOizationBridgeResult("rejected", source, None, (colour_error,))
    palette_colours = {item.get("ldraw_code") for item in palette_data.get("colours", [])}
    if colour not in palette_colours:
        return LEGOizationBridgeResult(
            "rejected", source, None,
            (f"COLOUR_NOT_IN_PALETTE: LDraw colour {colour} is not available",),
        )
    mapping = {
        "spatial_units": {"x": "stud", "y": "plate", "z": "stud"},
        "dimensions": {"width_studs": width_i, "height_plates": height_i, "depth_studs": depth_i},
        "origin": "wall-box centered at x=0,z=0 with bottom at y=0",
        "source_color": box.color,
        "mapped_colour": colour,
        "ldraw_colour": colour,
    }
    lego = legoize_wall_box(
        WallBoxScaffold(width_i, height_plates=height_i, depth_studs=depth_i,
                        model_id=f"{concept.id}-legoized", name=f"{concept.label} LEGOized"),
        palette_data,
        colour=colour,
    )
    return LEGOizationBridgeResult("success", source, mapping, tuple(lego.coverage.diagnostics), lego, _compiled_ldr(lego.model))
