"""Provider-neutral bridge from three generic boxes to a bounded gatehouse."""

from __future__ import annotations

import json
from dataclasses import dataclass
from os import PathLike
from typing import Any, Mapping

from .legoization import GatehouseScaffold, LEGOizationResult, legoize_gatehouse
from .palette import load_palette
from .spatial_concept import GenericBoxConcept


FORMAT = "brick-builder.gatehouse-legoization-bridge/v1"
DEFAULT_COLOUR = 4
MAX_WIDTH_STUDS = 16
MAX_DEPTH_STUDS = 2
MAX_HEIGHT_BRICKS = 4
EPSILON = 1e-9


@dataclass(frozen=True)
class GatehouseLEGOizationBridgeResult:
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


def legoize_gatehouse_concept(
    concept: GenericBoxConcept,
    palette: Mapping[str, Any] | str | PathLike[str],
    *,
    colour: int = DEFAULT_COLOUR,
) -> GatehouseLEGOizationBridgeResult:
    """Map exactly two equal towers and one spanning bridge to gatehouse LEGO."""
    if not isinstance(concept, GenericBoxConcept):
        raise TypeError("concept must be a GenericBoxConcept")
    source = concept.to_dict()
    diagnostics: list[str] = []
    if len(concept.boxes) != 3:
        diagnostics.append("THREE_BOXES_REQUIRED: provide exactly two towers and one bridge")
        return GatehouseLEGOizationBridgeResult("rejected", source, None, tuple(diagnostics))

    boxes = sorted(concept.boxes, key=lambda box: (box.center[1] - box.size[1] / 2, box.id))
    low = boxes[:2]
    bridge = boxes[2]
    tower_a, tower_b = low

    def integral_dimensions(box: Any, label: str) -> tuple[int, int, int] | None:
        values = tuple(box.size)
        names = ("width_studs", "height_bricks", "depth_studs")
        invalid = False
        for name, value in zip(names, values):
            if abs(value - round(value)) > EPSILON:
                diagnostics.append(f"NON_INTEGRAL_DIMENSION: {label}.{name}={value:g} must be an integer")
                invalid = True
        return None if invalid else tuple(int(round(value)) for value in values)

    tower_a_dims = integral_dimensions(tower_a, "tower_a")
    tower_b_dims = integral_dimensions(tower_b, "tower_b")
    bridge_dims = integral_dimensions(bridge, "bridge")
    if tower_a_dims is None or tower_b_dims is None or bridge_dims is None:
        return GatehouseLEGOizationBridgeResult("rejected", source, None, tuple(diagnostics))
    tower_width, tower_height, tower_depth = tower_a_dims
    if tower_a_dims != tower_b_dims:
        diagnostics.append("TOWERS_MUST_MATCH: both towers must have equal width, height, and depth")
    bridge_width, bridge_height, bridge_depth = bridge_dims

    for label, box in (("tower_a", tower_a), ("tower_b", tower_b), ("bridge", bridge)):
        if abs(box.center[2]) > EPSILON:
            diagnostics.append(f"NOT_ALIGNED: {label} center z must be zero")
    if bridge_depth != tower_depth:
        diagnostics.append("DEPTH_MISMATCH: bridge and towers must have the same depth")
    if tower_depth > MAX_DEPTH_STUDS:
        diagnostics.append(f"OUT_OF_BOUNDS: depth_studs={tower_depth} must be between 1 and {MAX_DEPTH_STUDS}")

    a_bottom = tower_a.center[1] - tower_a.size[1] / 2
    b_bottom = tower_b.center[1] - tower_b.size[1] / 2
    a_top = tower_a.center[1] + tower_a.size[1] / 2
    b_top = tower_b.center[1] + tower_b.size[1] / 2
    bridge_bottom = bridge.center[1] - bridge.size[1] / 2
    if abs(a_bottom) > EPSILON or abs(b_bottom) > EPSILON:
        diagnostics.append("NOT_GROUNDED: both towers must have bottoms at spatial y=0")
    if abs(bridge_bottom - a_top) > EPSILON or abs(bridge_bottom - b_top) > EPSILON:
        diagnostics.append("BRIDGE_NOT_DIRECTLY_ATOP: bridge bottom must equal both tower tops")

    if abs(tower_a.center[0] + tower_b.center[0]) > EPSILON:
        diagnostics.append("TOWERS_NOT_CENTERED: tower centers must be symmetric around x=0")
    if abs(bridge.center[0]) > EPSILON:
        diagnostics.append("NOT_CENTERED: bridge center x must be zero")
    if abs(tower_a.center[0] - tower_b.center[0]) <= tower_width - EPSILON:
        diagnostics.append("TOWERS_OVERLAP: towers must be separated by a positive opening")
    opening = abs(tower_a.center[0] - tower_b.center[0]) - tower_width
    if opening <= EPSILON or abs(opening - round(opening)) > EPSILON:
        diagnostics.append("POSITIVE_INTEGRAL_OPENING_REQUIRED: opening must be a positive integer number of studs")
    if bridge_width != 2 * tower_width + int(round(opening)):
        diagnostics.append("BRIDGE_MUST_BE_FULL_WIDTH: bridge width must exactly span both towers and opening")

    for label, value, upper in (
        ("tower_width_studs", tower_width, MAX_WIDTH_STUDS),
        ("bridge_width_studs", bridge_width, MAX_WIDTH_STUDS),
        ("tower_height_bricks", tower_height, MAX_HEIGHT_BRICKS),
        ("bridge_height_bricks", bridge_height, MAX_HEIGHT_BRICKS),
    ):
        if not 1 <= value <= upper:
            diagnostics.append(f"OUT_OF_BOUNDS: {label}={value} must be between 1 and {upper}")
    if diagnostics:
        return GatehouseLEGOizationBridgeResult("rejected", source, None, tuple(diagnostics))

    palette_data = load_palette(palette) if isinstance(palette, (str, PathLike)) else dict(palette)
    if colour not in {item.get("ldraw_code") for item in palette_data.get("colours", [])}:
        return GatehouseLEGOizationBridgeResult("rejected", source, None, (f"COLOUR_NOT_IN_PALETTE: LDraw colour {colour} is not available",))
    mapping = {
        "spatial_units": {"x": "stud", "y": "brick", "z": "stud"},
        "tower_refs": [tower_a.id, tower_b.id],
        "bridge_ref": bridge.id,
        "dimensions": {"width_studs": bridge_width, "tower_width_studs": tower_width, "opening_width_studs": int(round(opening)), "tower_height_bricks": tower_height, "bridge_height_bricks": bridge_height, "depth_studs": tower_depth},
        "origin": "centered at x=0,z=0 with grounded towers at y=0",
        "ldraw_colour": colour,
    }
    lego = legoize_gatehouse(GatehouseScaffold(bridge_width, tower_width, int(round(opening)), tower_height, bridge_height, tower_depth, model_id=f"{concept.id}-legoized-gatehouse", name=f"{concept.label} LEGOized gatehouse"), palette_data, colour=colour)
    diagnostics.extend(lego.coverage.diagnostics)
    return GatehouseLEGOizationBridgeResult("success" if lego.valid else "rejected", source, mapping, tuple(diagnostics), lego, _compiled_ldr(lego.model))
