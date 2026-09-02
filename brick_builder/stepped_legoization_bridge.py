"""Provider-neutral bridge for exactly two aligned stepped spatial boxes."""

from __future__ import annotations

import json
from dataclasses import dataclass
from os import PathLike
from typing import Any, Mapping

from .legoization import LEGOizationResult, SteppedBoxScaffold, legoize_stepped_box
from .palette import load_palette
from .spatial_concept import GenericBoxConcept


FORMAT = "brick-builder.stepped-legoization-bridge/v1"
DEFAULT_COLOUR = 4
MAX_WIDTH_STUDS = 16
MAX_DEPTH_STUDS = 2
MAX_HEIGHT_BRICKS = 4
EPSILON = 1e-9


@dataclass(frozen=True)
class SteppedLEGOizationBridgeResult:
    """Deterministic accepted assembly or actionable rejection."""

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


def legoize_accepted_stepped_boxes(
    concept: GenericBoxConcept,
    palette: Mapping[str, Any] | str | PathLike[str],
    *,
    colour: int = DEFAULT_COLOUR,
) -> SteppedLEGOizationBridgeResult:
    """Map exactly two generic boxes to :func:`legoize_stepped_box`.

    Spatial x/z units are studs and spatial y units are bricks.  The lower box
    is grounded at y=0; the upper box sits directly on it.  Both boxes are
    centered on x=z=0 and share a two-stud-or-less depth.
    """
    if not isinstance(concept, GenericBoxConcept):
        raise TypeError("concept must be a GenericBoxConcept")
    source = concept.to_dict()
    diagnostics: list[str] = []
    if len(concept.boxes) != 2:
        diagnostics.append("TWO_BOXES_REQUIRED: provide exactly a grounded base and upper tier")
        return SteppedLEGOizationBridgeResult("rejected", source, None, tuple(diagnostics))

    ordered = sorted(concept.boxes, key=lambda box: (box.center[1] - box.size[1] / 2, box.id))
    base, upper = ordered
    def dimensions(box: Any, label: str) -> tuple[int, int, int] | None:
        values = (box.size[0], box.size[1], box.size[2])
        names = ("width_studs", "height_bricks", "depth_studs")
        for name, value in zip(names, values):
            if abs(value - round(value)) > EPSILON:
                diagnostics.append(f"NON_INTEGRAL_DIMENSION: {label}.{name}={value:g} must be an integer")
        if any(abs(value - round(value)) > EPSILON for value in values):
            return None
        return tuple(int(round(value)) for value in values)  # type: ignore[return-value]

    base_dims = dimensions(base, "base")
    upper_dims = dimensions(upper, "upper")
    if base_dims is None or upper_dims is None:
        return SteppedLEGOizationBridgeResult("rejected", source, None, tuple(diagnostics))
    base_width, base_height, base_depth = base_dims
    upper_width, upper_height, upper_depth = upper_dims

    for label, box in (("base", base), ("upper", upper)):
        if abs(box.center[0]) > EPSILON or abs(box.center[2]) > EPSILON:
            diagnostics.append(f"NOT_CENTERED: {label} center x and z must be zero")
    if base_depth != upper_depth:
        diagnostics.append("DEPTH_MISMATCH: base and upper tiers must have the same depth")
    if base_depth > MAX_DEPTH_STUDS:
        diagnostics.append(f"OUT_OF_BOUNDS: depth_studs={base_depth} must be between 1 and {MAX_DEPTH_STUDS}")
    if upper_width >= base_width:
        diagnostics.append("UPPER_NOT_NARROWER: upper width must be narrower than base width")
    if (base_width - upper_width) % 2:
        diagnostics.append("UPPER_NOT_CENTERABLE: base and upper widths must differ by an even number of studs")
    base_bottom = base.center[1] - base.size[1] / 2
    base_top = base.center[1] + base.size[1] / 2
    upper_bottom = upper.center[1] - upper.size[1] / 2
    if abs(base_bottom) > EPSILON:
        diagnostics.append("NOT_GROUNDED: base bottom must lie on spatial y=0")
    if upper_bottom < base_top - EPSILON:
        diagnostics.append("OVERLAPPING_TIERS: upper tier must not overlap the grounded base")
    elif abs(upper_bottom - base_top) > EPSILON:
        diagnostics.append("TIER_GAP_UNSUPPORTED: upper tier must sit directly on the base")
    for name, value, upper_bound in (
        ("base_width_studs", base_width, MAX_WIDTH_STUDS),
        ("upper_width_studs", upper_width, MAX_WIDTH_STUDS),
        ("base_height_bricks", base_height, MAX_HEIGHT_BRICKS),
        ("upper_height_bricks", upper_height, MAX_HEIGHT_BRICKS),
    ):
        if not 1 <= value <= upper_bound:
            diagnostics.append(f"OUT_OF_BOUNDS: {name}={value} must be between 1 and {upper_bound}")
    if diagnostics:
        return SteppedLEGOizationBridgeResult("rejected", source, None, tuple(diagnostics))

    palette_data = load_palette(palette) if isinstance(palette, (str, PathLike)) else dict(palette)
    if colour not in {item.get("ldraw_code") for item in palette_data.get("colours", [])}:
        return SteppedLEGOizationBridgeResult(
            "rejected", source, None,
            (f"COLOUR_NOT_IN_PALETTE: LDraw colour {colour} is not available",),
        )
    mapping = {
        "spatial_units": {"x": "stud", "y": "brick", "z": "stud"},
        "tiers": {
            "base": {"source_ref": base.id, "width_studs": base_width, "height_bricks": base_height, "depth_studs": base_depth},
            "upper": {"source_ref": upper.id, "width_studs": upper_width, "height_bricks": upper_height, "depth_studs": upper_depth},
        },
        "origin": "centered at x=0,z=0 with grounded base at y=0",
        "ldraw_colour": colour,
    }
    lego = legoize_stepped_box(
        SteppedBoxScaffold(base_width, upper_width, base_height, upper_height, base_depth,
                           model_id=f"{concept.id}-legoized-stepped", name=f"{concept.label} LEGOized stepped"),
        palette_data, colour=colour,
    )
    diagnostics.extend(lego.coverage.diagnostics)
    return SteppedLEGOizationBridgeResult(
        "success" if lego.valid else "rejected", source, mapping, tuple(diagnostics), lego, _compiled_ldr(lego.model)
    )
