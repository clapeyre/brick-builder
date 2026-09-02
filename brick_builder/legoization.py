"""The deliberately small, deterministic 3C rectangular-box LEGOization bridge.

This module deals only in axis-aligned, one- and two-stud-deep boxes. Coverage is
reported independently from canonical-model validation: a partial fill can be
structurally sound while still failing to satisfy its target volume.
"""

from dataclasses import dataclass
from typing import Any, Mapping

from .geometry import profiles_from_palette
from .validation import ValidationError, ValidationIssue, validate_model

IDENTITY = [1, 0, 0, 0, 1, 0, 0, 0, 1]
ROTATE_Y_90 = [0, 0, -1, 0, 1, 0, 1, 0, 0]


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
class SteppedBoxScaffold:
    """A two-tier box with a centered, narrower upper tier.

    Heights are deliberately expressed as positive brick counts. The upper
    tier starts on the top of the base; both tiers use the same depth.
    """

    base_width_studs: int
    upper_width_studs: int
    base_height_bricks: int
    upper_height_bricks: int
    depth_studs: int = 2
    model_id: str = "legoized-stepped-box"
    name: str = "LEGOized stepped box"


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
    lower-left of the target.  One- and two-stud-deep targets are supported;
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
    if target.depth_studs == 2:
        # For the two-stud slice, tile each horizontal layer in a fixed
        # row-major order.  A rotated profile is still an ordinary LDraw
        # part; rotation is around the vertical Y axis only.
        candidates = []
        for profile in profiles.values():
            if profile.category not in {"brick", "plate"}:
                continue
            for matrix, width, depth in ((IDENTITY, profile.x_studs, profile.z_studs),
                                         (ROTATE_Y_90, profile.z_studs, profile.x_studs)):
                if width <= target.width_studs and depth <= target.depth_studs:
                    candidates.append((profile, matrix, width, depth))
        candidates.sort(key=lambda item: (-item[2] * item[3], -item[2], -item[3],
                                          item[0].height_plates, item[0].part,
                                          tuple(item[1])))
        while plate_layer < total_height_plates:
            remaining_height = total_height_plates - plate_layer
            part_height = max((p[0].height_plates for p in candidates
                               if p[0].height_plates <= remaining_height), default=None)
            if part_height is None:
                break
            layer_candidates = [item for item in candidates if item[0].height_plates == part_height]
            layer_covered: set[tuple[int, int]] = set()
            for z in range(target.depth_studs):
                for x in range(target.width_studs):
                    if (x, z) in layer_covered:
                        continue
                    choice = next((item for item in layer_candidates
                                   if x + item[2] <= target.width_studs
                                   and z + item[3] <= target.depth_studs
                                   and all((xx, zz) not in layer_covered
                                           for xx in range(x, x + item[2])
                                           for zz in range(z, z + item[3]))), None)
                    if choice is None:
                        continue
                    profile, matrix, width, depth = choice
                    x_ldu = int((x + width / 2) * 20)
                    z_ldu = int((z + depth / 2) * 20)
                    parts.append({
                        "id": f"box2-p{plate_layer:02d}-x{x:02d}-z{z:02d}",
                        "part": profile.part,
                        "colour": colour,
                        "translation_ldu": [x_ldu, -(plate_layer + profile.height_plates - 3) * 8, z_ldu],
                        "matrix": list(matrix),
                    })
                    cells = {(xx, zz) for xx in range(x, x + width)
                             for zz in range(z, z + depth)}
                    layer_covered.update(cells)
                    covered.update((xx, height, zz) for xx, zz in cells
                                   for height in range(plate_layer, plate_layer + part_height))
            plate_layer += part_height
    else:
        # Preserve the original one-stud tiler byte-for-byte.  Unsupported
        # depths intentionally retain its useful partial candidate and
        # uncovered-region diagnostic.
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
            reverse = target.width_studs % 2 == 1 and (plate_layer // part_height) % 2 == 1
            cursor = target.width_studs if reverse else 0
            while (cursor > 0 if reverse else cursor < target.width_studs):
                remaining = cursor if reverse else target.width_studs - cursor
                profile = next((candidate for candidate in layer_parts if candidate.x_studs <= remaining), None)
                if profile is None:
                    break
                start = cursor - profile.x_studs if reverse else cursor
                x_ldu = (start + profile.x_studs / 2) * 20
                parts.append({
                    "id": f"wall-p{plate_layer:02d}-x{start:02d}",
                    "part": profile.part,
                    "colour": colour,
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
    if target.depth_studs not in {1, 2}:
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


def legoize_stepped_box(
    scaffold: SteppedBoxScaffold | Mapping[str, Any],
    palette: Mapping[str, Any],
    *,
    colour: int = 4,
) -> LEGOizationResult:
    """Build a centered, narrower upper tier on a rectangular base.

    Coverage cells use one absolute ``(x, layer, z)`` space.  Unsupported
    depths intentionally return the underlying partial candidate and its
    uncovered-region diagnostic, while malformed tier geometry is rejected
    before any model is produced.
    """
    if isinstance(scaffold, SteppedBoxScaffold):
        target = scaffold
    elif isinstance(scaffold, Mapping):
        target = SteppedBoxScaffold(**scaffold)
    else:
        raise TypeError("scaffold must be a SteppedBoxScaffold or mapping")

    for field in ("base_width_studs", "upper_width_studs", "base_height_bricks",
                  "upper_height_bricks", "depth_studs"):
        value = getattr(target, field)
        if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
            raise ValueError(f"{field} must be a positive integer")
    if target.upper_width_studs >= target.base_width_studs:
        raise ValueError("upper_width_studs must be narrower than base_width_studs")
    if (target.base_width_studs - target.upper_width_studs) % 2:
        raise ValueError("base and upper widths must differ by an even number of studs")
    if not target.model_id or not target.name:
        raise ValueError("model_id and name must be non-empty")

    offset = (target.base_width_studs - target.upper_width_studs) // 2
    base = legoize_wall_box(
        WallBoxScaffold(target.base_width_studs, target.base_height_bricks,
                        target.depth_studs), palette, colour=colour)
    upper = legoize_wall_box(
        WallBoxScaffold(target.upper_width_studs, target.upper_height_bricks,
                        target.depth_studs), palette, colour=colour)

    base_layers = target.base_height_bricks * 3
    parts: list[dict[str, Any]] = []
    for source, prefix, x_shift, y_shift in (
        (base, "step-base", 0, 0),
        (upper, "step-upper", offset, -base_layers),
    ):
        for part in source.model["parts"]:
            translated = dict(part)
            translated["id"] = f"{prefix}-{part['id']}"
            translated["translation_ldu"] = [
                part["translation_ldu"][0] + x_shift * 20,
                part["translation_ldu"][1] + y_shift * 8,
                part["translation_ldu"][2],
            ]
            translated["matrix"] = list(part["matrix"])
            parts.append(translated)

    required = tuple(
        (x, layer, z)
        for layer in range((target.base_height_bricks + target.upper_height_bricks) * 3)
        for z in range(target.depth_studs)
        for x in (
            range(target.base_width_studs)
            if layer < base_layers
            else range(offset, offset + target.upper_width_studs)
        )
    )
    covered = set()
    for report, x_shift, layer_shift in (
        (base.coverage, 0, 0), (upper.coverage, offset, base_layers)
    ):
        covered.update((x + x_shift, layer + layer_shift, z)
                       for x, layer, z in report.covered)
    covered_cells = tuple(cell for cell in required if cell in covered)
    uncovered = tuple(cell for cell in required if cell not in covered)
    diagnostics = list(base.coverage.diagnostics) + list(upper.coverage.diagnostics)
    model = {"schema_version": 1, "model_id": target.model_id,
             "name": target.name, "parts": parts}
    try:
        validate_model(model, dict(palette))
        issues: tuple[ValidationIssue, ...] = ()
    except ValidationError as exc:
        issues = exc.issues
    return LEGOizationResult(
        model, CoverageReport(required, covered_cells, uncovered, tuple(diagnostics)),
        not issues, issues,
    )


# Explicitly named alias for callers that want to emphasize the input type.
legoize_wall_box_scaffold = legoize_wall_box
