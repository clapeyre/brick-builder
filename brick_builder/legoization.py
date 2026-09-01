"""The deliberately small, deterministic 3C wall-box LEGOization bridge.

This module deals only in axis-aligned, one-stud-deep wall boxes.  Coverage is
reported independently from canonical-model validation: a partial fill can be
structurally sound while still failing to satisfy its target volume.
"""

from dataclasses import dataclass
from typing import Any, Mapping

from .geometry import profiles_from_palette
from .validation import ValidationError, ValidationIssue, validate_model

IDENTITY = [1, 0, 0, 0, 1, 0, 0, 0, 1]


@dataclass(frozen=True)
class WallBoxScaffold:
    """A finite wall target, measured in studs and plate-height layers."""

    width_studs: int
    height_bricks: int | None = None
    depth_studs: int = 1
    model_id: str = "legoized-wall-box"
    name: str = "LEGOized wall box"
    height_plates: int | None = None


@dataclass(frozen=True)
class CoverageReport:
    required: tuple[tuple[int, int, int], ...]
    covered: tuple[tuple[int, int, int], ...]
    uncovered: tuple[tuple[int, int, int], ...]
    diagnostics: tuple[str, ...]

    @property
    def complete(self) -> bool:
        return not self.uncovered


@dataclass(frozen=True)
class LEGOizationResult:
    model: dict[str, Any]
    coverage: CoverageReport
    structural_valid: bool
    structural_issues: tuple[ValidationIssue, ...]

    @property
    def valid(self) -> bool:
        return self.coverage.complete and self.structural_valid


def _scaffold(value: WallBoxScaffold | Mapping[str, Any]) -> WallBoxScaffold:
    if isinstance(value, WallBoxScaffold):
        result = value
    elif isinstance(value, Mapping):
        result = WallBoxScaffold(**value)
    else:
        raise TypeError("scaffold must be a WallBoxScaffold or mapping")
    for field in ("width_studs", "depth_studs"):
        number = getattr(result, field)
        if not isinstance(number, int) or isinstance(number, bool) or number <= 0:
            raise ValueError(f"{field} must be a positive integer")
    heights = (result.height_bricks, result.height_plates)
    if sum(height is not None for height in heights) != 1:
        raise ValueError("specify exactly one of height_bricks or height_plates")
    height = result.height_bricks if result.height_bricks is not None else result.height_plates
    if not isinstance(height, int) or isinstance(height, bool) or height <= 0:
        raise ValueError("wall height must be a positive integer")
    if not result.model_id or not result.name:
        raise ValueError("model_id and name must be non-empty")
    return result


def legoize_wall_box(
    scaffold: WallBoxScaffold | Mapping[str, Any],
    palette: Mapping[str, Any],
    *,
    colour: int = 4,
) -> LEGOizationResult:
    """Fill one wall-box scaffold using the largest supported brick runs.

    Coordinates in coverage cells are ``(x, layer, z)`` with the origin at the
    lower-left of the target.  Only a one-stud-deep target is in this slice;
    other depths intentionally produce actionable uncovered diagnostics.
    """
    target = _scaffold(scaffold)
    profiles = profiles_from_palette(dict(palette))
    rectangular_parts = sorted(
        (profile for profile in profiles.values()
         if profile.category in {"brick", "plate"} and profile.z_studs == 1),
        key=lambda profile: (-profile.height_plates, -profile.x_studs, profile.part),
    )
    total_height_plates = (target.height_bricks * 3 if target.height_bricks is not None
                           else target.height_plates)
    assert total_height_plates is not None
    required = tuple(
        (x, layer, z)
        for layer in range(total_height_plates)
        for z in range(target.depth_studs)
        for x in range(target.width_studs)
    )
    parts: list[dict[str, Any]] = []
    covered: set[tuple[int, int, int]] = set()
    plate_layer = 0
    while plate_layer < total_height_plates:
        remaining_height = total_height_plates - plate_layer
        part_height = next(
            (profile.height_plates for profile in rectangular_parts
             if profile.height_plates <= remaining_height),
            None,
        )
        if part_height is None:
            break
        layer_parts = [profile for profile in rectangular_parts
                       if profile.height_plates == part_height]
        # Alternate the seam direction for odd widths.  This staggers the
        # unavoidable 1-stud remainder and gives adjacent layers a stud
        # connection through their broad bricks.
        reverse = target.width_studs % 2 == 1 and (plate_layer // part_height) % 2 == 1
        cursor = target.width_studs if reverse else 0
        while (cursor > 0 if reverse else cursor < target.width_studs):
            remaining = cursor if reverse else target.width_studs - cursor
            profile = next((candidate for candidate in layer_parts if candidate.x_studs <= remaining), None)
            if profile is None:
                break
            # RectProfile origins are centered; z=10 places a one-stud wall's
            # bounding edge on the absolute 20 LDU mesh grid.
            # The scaffold's x=0 boundary is the global mesh origin.  Using
            # the run's centre (rather than centring the whole wall) keeps
            # every individual brick edge on an absolute 20 LDU grid even
            # when the wall has odd width.
            start = cursor - profile.x_studs if reverse else cursor
            x_ldu = (start + profile.x_studs / 2) * 20
            parts.append({
                "id": f"wall-p{plate_layer:02d}-x{start:02d}",
                "part": profile.part,
                "colour": colour,
                # Layer zero is the lowest target plate.  A brick occupies
                # three such layers beneath its LDraw top plane; preserving
                # that convention lets a one-plate remainder sit directly on
                # top of a brick at the same stud ports.
                "translation_ldu": [int(x_ldu), -(plate_layer + profile.height_plates - 3) * 8, 10],
                "matrix": IDENTITY.copy(),
            })
            covered.update(
                (x, height, 0)
                for height in range(plate_layer, plate_layer + profile.height_plates)
                for x in range(start, start + profile.x_studs)
            )
            cursor = start if reverse else start + profile.x_studs
        plate_layer += part_height
    covered_cells = tuple(cell for cell in required if cell in covered)
    uncovered = tuple(cell for cell in required if cell not in covered)
    diagnostics = []
    if target.depth_studs != 1:
        diagnostics.append(
            f"UNFILLED_TARGET_REGION: depth {target.depth_studs} is outside the one-stud wall tiler; "
            f"uncovered cells include z=1..{target.depth_studs - 1}"
        )
    if uncovered and target.depth_studs == 1:
        diagnostics.append(
            "UNFILLED_TARGET_REGION: no supported rectangular brick run fits "
            f"the remaining cells (first uncovered cell {uncovered[0]})"
        )
    report = CoverageReport(required, covered_cells, uncovered, tuple(diagnostics))
    model = {"schema_version": 1, "model_id": target.model_id, "name": target.name, "parts": parts}
    issues: tuple[ValidationIssue, ...]
    try:
        validate_model(model, dict(palette))
        issues = ()
    except ValidationError as exc:
        issues = exc.issues
    return LEGOizationResult(model, report, not issues, issues)


# Explicitly named alias for callers that want to emphasize the input type.
legoize_wall_box_scaffold = legoize_wall_box
