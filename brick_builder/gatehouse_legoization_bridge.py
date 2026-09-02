"""Provider-neutral bridge for a bounded three-box gatehouse composition."""

from __future__ import annotations

import json
from dataclasses import dataclass
from os import PathLike
from typing import Any, Mapping

from .legoization import LEGOizationResult, GatehouseScaffold, legoize_gatehouse
from .palette import load_palette
from .spatial_concept import GenericBoxConcept

FORMAT = "brick-builder.gatehouse-legoization-bridge/v1"
DEFAULT_COLOUR = 4
MAX_WIDTH_STUDS = 16
MAX_TOWER_WIDTH_STUDS = 8
MAX_OPENING_WIDTH_STUDS = 8
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


def legoize_accepted_gatehouse(
    concept: GenericBoxConcept,
    palette: Mapping[str, Any] | str | PathLike[str],
    *,
    colour: int = DEFAULT_COLOUR,
) -> GatehouseLEGOizationBridgeResult:
    """Infer and map exactly two towers plus one bridge to ``legoize_gatehouse``.

    Spatial x/z units are studs and y units are bricks.  The bridge is inferred
    as the widest box; the remaining two boxes must be equal symmetric towers.
    No provider-supplied semantic role or repair is trusted.
    """
    if not isinstance(concept, GenericBoxConcept):
        raise TypeError("concept must be a GenericBoxConcept")
    source = concept.to_dict()
    diagnostics: list[str] = []
    if len(concept.boxes) != 3:
        return GatehouseLEGOizationBridgeResult(
            "rejected", source, None,
            ("THREE_BOXES_REQUIRED: provide exactly two towers and one full-width bridge",),
        )

    def integral_dimensions(box: Any, label: str) -> tuple[int, int, int] | None:
        values = box.size
        names = ("width_studs", "height_bricks", "depth_studs")
        invalid = False
        for name, value in zip(names, values):
            if abs(value - round(value)) > EPSILON:
                diagnostics.append(f"NON_INTEGRAL_DIMENSION: {label}.{name}={value:g} must be an integer")
                invalid = True
        return None if invalid else tuple(int(round(value)) for value in values)  # type: ignore[return-value]

    dimensions = {box.id: integral_dimensions(box, box.id) for box in concept.boxes}
    if any(value is None for value in dimensions.values()):
        return GatehouseLEGOizationBridgeResult("rejected", source, None, tuple(diagnostics))

    ordered = sorted(concept.boxes, key=lambda box: (-dimensions[box.id][0], box.id))  # type: ignore[index]
    bridge = ordered[0]
    towers = ordered[1:]
    bridge_width, bridge_height, bridge_depth = dimensions[bridge.id]  # type: ignore[misc]
    tower_width, tower_height, tower_depth = dimensions[towers[0].id]  # type: ignore[misc]
    other_width, other_height, other_depth = dimensions[towers[1].id]  # type: ignore[misc]

    if bridge_width <= tower_width:
        diagnostics.append("BRIDGE_NOT_WIDER: bridge must span beyond both tower widths")
    if (tower_width, tower_height, tower_depth) != (other_width, other_height, other_depth):
        diagnostics.append("TOWERS_NOT_EQUAL: both towers must have identical dimensions")
    if bridge_depth != tower_depth:
        diagnostics.append("DEPTH_MISMATCH: bridge and towers must have the same depth")
    for label, box in (("bridge", bridge), ("left_tower", towers[0]), ("right_tower", towers[1])):
        if abs(box.center[2]) > EPSILON:
            diagnostics.append(f"NOT_CENTERED: {label} center z must be zero")
    base = sorted(towers, key=lambda box: box.center[0])
    left, right = base
    if abs(left.center[0] + right.center[0]) > EPSILON:
        diagnostics.append("TOWERS_NOT_SYMMETRIC: tower centers must mirror around x=0")
    if abs(bridge.center[0]) > EPSILON:
        diagnostics.append("NOT_CENTERED: bridge center x must be zero")
    left_bottom = left.center[1] - left.size[1] / 2
    right_bottom = right.center[1] - right.size[1] / 2
    tower_top = left.center[1] + left.size[1] / 2
    bridge_bottom = bridge.center[1] - bridge.size[1] / 2
    if abs(left_bottom) > EPSILON or abs(right_bottom) > EPSILON:
        diagnostics.append("NOT_GROUNDED: both tower bottoms must lie on spatial y=0")
    if abs(bridge_bottom - tower_top) > EPSILON:
        diagnostics.append("BRIDGE_HEIGHT_MISMATCH: bridge must sit directly atop the towers")
    opening_width = bridge_width - 2 * tower_width
    if opening_width <= 0:
        diagnostics.append("OPENING_NOT_POSITIVE: gateway opening must be positive")
    expected_left = -(opening_width + tower_width) / 2
    if abs(left.center[0] - expected_left) > EPSILON:
        diagnostics.append("TOWERS_MISALIGNED: tower positions must define a centered opening")

    for name, value, limit in (
        ("width_studs", bridge_width, MAX_WIDTH_STUDS),
        ("tower_width_studs", tower_width, MAX_TOWER_WIDTH_STUDS),
        ("opening_width_studs", opening_width, MAX_OPENING_WIDTH_STUDS),
        ("depth_studs", bridge_depth, MAX_DEPTH_STUDS),
        ("tower_height_bricks", tower_height, MAX_HEIGHT_BRICKS),
        ("bridge_height_bricks", bridge_height, MAX_HEIGHT_BRICKS),
    ):
        if not 1 <= value <= limit:
            diagnostics.append(f"OUT_OF_BOUNDS: {name}={value} must be between 1 and {limit}")
    if diagnostics:
        return GatehouseLEGOizationBridgeResult("rejected", source, None, tuple(diagnostics))

    palette_data = load_palette(palette) if isinstance(palette, (str, PathLike)) else dict(palette)
    if colour not in {item.get("ldraw_code") for item in palette_data.get("colours", [])}:
        return GatehouseLEGOizationBridgeResult(
            "rejected", source, None,
            (f"COLOUR_NOT_IN_PALETTE: LDraw colour {colour} is not available",),
        )
    mapping = {
        "spatial_units": {"x": "stud", "y": "brick", "z": "stud"},
        "roles": {
            "left_tower": {"source_ref": left.id, "width_studs": tower_width, "height_bricks": tower_height, "depth_studs": tower_depth},
            "right_tower": {"source_ref": right.id, "width_studs": tower_width, "height_bricks": tower_height, "depth_studs": tower_depth},
            "bridge": {"source_ref": bridge.id, "width_studs": bridge_width, "height_bricks": bridge_height, "depth_studs": bridge_depth},
        },
        "opening_width_studs": opening_width,
        "origin": "centered at x=0,z=0 with grounded towers at y=0",
        "ldraw_colour": colour,
    }
    lego = legoize_gatehouse(
        GatehouseScaffold(bridge_width, tower_width, opening_width, tower_height, bridge_height, bridge_depth,
                          model_id=f"{concept.id}-legoized-gatehouse", name=f"{concept.label} LEGOized gatehouse"),
        palette_data, colour=colour,
    )
    diagnostics.extend(lego.coverage.diagnostics)
    return GatehouseLEGOizationBridgeResult(
        "success" if lego.valid else "rejected", source, mapping, tuple(diagnostics), lego, _compiled_ldr(lego.model)
    )
