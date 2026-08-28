from dataclasses import dataclass
from typing import Any, Iterable
import json
from pathlib import Path

from .ldraw import LDrawLibrary


@dataclass(frozen=True)
class ValidationIssue:
    path: str
    message: str
    code: str = "INVALID_MODEL"


class ValidationError(ValueError):
    def __init__(self, issues: Iterable[ValidationIssue]):
        self.issues = tuple(issues)
        super().__init__("; ".join(f"{issue.path}: {issue.message}" for issue in self.issues))


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _valid_rotation(matrix: Any) -> bool:
    if not isinstance(matrix, list) or len(matrix) != 9 or not all(_is_int(v) for v in matrix):
        return False
    rows = [matrix[i : i + 3] for i in range(0, 9, 3)]
    columns = [[rows[row][column] for row in range(3)] for column in range(3)]
    if any(sum(value * value for value in vector) != 1 for vector in rows + columns):
        return False
    if any(sum(rows[row][column] * rows[row][other] for row in range(3)) != 0 for column in range(3) for other in range(column + 1, 3)):
        return False
    determinant = (
        rows[0][0] * (rows[1][1] * rows[2][2] - rows[1][2] * rows[2][1])
        - rows[0][1] * (rows[1][0] * rows[2][2] - rows[1][2] * rows[2][0])
        + rows[0][2] * (rows[1][0] * rows[2][1] - rows[1][1] * rows[2][0])
    )
    return determinant == 1


def validate_schema(model: Any) -> tuple[ValidationIssue, ...]:
    """Validate the JSON document shape, independently of catalog/geometry rules."""
    try:
        import jsonschema
        schema_path = Path(__file__).with_name("schema") / "canonical-model-v1.schema.json"
        if not schema_path.is_file():
            schema_path = Path(__file__).parents[1] / "schema" / "canonical-model-v1.schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        validator = jsonschema.Draft202012Validator(schema)
        return tuple(ValidationIssue(".".join(str(p) for p in error.absolute_path) or "$", error.message, "SCHEMA_INVALID")
                     for error in sorted(validator.iter_errors(model), key=lambda e: list(e.absolute_path)))
    except ImportError:
        return (ValidationIssue("$", "jsonschema dependency is required for structural validation", "SCHEMA_DEPENDENCY"),)


def validate_model(model: Any, palette: dict[str, Any], library: LDrawLibrary | None = None) -> None:
    issues: list[ValidationIssue] = list(validate_schema(model))
    if not isinstance(model, dict):
        raise ValidationError(issues)
    placements = model.get("parts")
    if not isinstance(placements, list) or not placements:
        issues.append(ValidationIssue("parts", "must be a non-empty array", "SCHEMA_PARTS"))
        raise ValidationError(issues)
    palette_parts = {part["ldraw_file"] for part in palette.get("parts", [])}
    palette_colours = {colour["ldraw_code"] for colour in palette.get("colours", [])}
    seen_ids: set[str] = set()
    for index, placement in enumerate(placements):
        path = f"parts[{index}]"
        if not isinstance(placement, dict):
            issues.append(ValidationIssue(path, "must be an object", "SCHEMA_PART"))
            continue
        placement_id = placement.get("id")
        if not isinstance(placement_id, str) or not placement_id:
            issues.append(ValidationIssue(f"{path}.id", "must be a non-empty string", "INVALID_ID"))
        elif placement_id in seen_ids:
            issues.append(ValidationIssue(f"{path}.id", f"duplicate placement id {placement_id!r}", "DUPLICATE_ID"))
        else:
            seen_ids.add(placement_id)
        part = placement.get("part")
        if not isinstance(part, str) or part != part.lower() or not part.endswith(".dat"):
            issues.append(ValidationIssue(f"{path}.part", "must be a lowercase LDraw .dat filename", "INVALID_PART_ID"))
        elif part not in palette_parts:
            issues.append(ValidationIssue(f"{path}.part", f"{part!r} is not in the configured palette", "PART_NOT_IN_PALETTE"))
        elif library is not None and not library.has_part(part):
            issues.append(ValidationIssue(f"{path}.part", f"{part!r} is not present in the discovered LDraw library", "PART_NOT_IN_LIBRARY"))
        colour = placement.get("colour")
        if not _is_int(colour) or colour not in palette_colours:
            issues.append(ValidationIssue(f"{path}.colour", f"must be one of the palette LDraw codes: {sorted(palette_colours)}", "COLOUR_NOT_IN_PALETTE"))
        translation = placement.get("translation_ldu")
        if not isinstance(translation, list) or len(translation) != 3 or not all(_is_int(v) for v in translation):
            issues.append(ValidationIssue(f"{path}.translation_ldu", "must contain exactly three integer LDraw coordinates", "INVALID_TRANSLATION"))
        matrix = placement.get("matrix")
        if not _valid_rotation(matrix):
            issues.append(ValidationIssue(f"{path}.matrix", "must be a proper orthonormal 90-degree rotation matrix", "INVALID_ROTATION"))
    if issues:
        raise ValidationError(issues)
    from .geometry import validate_geometry
    geometry = validate_geometry(model, palette)
    if geometry.issues:
        raise ValidationError(geometry.issues)
