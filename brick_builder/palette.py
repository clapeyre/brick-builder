import json
from pathlib import Path
from typing import Any

from .errors import BrickBuilderError


class PaletteError(BrickBuilderError):
    pass


def load_palette(path: str | Path | Any) -> dict[str, Any]:
    """Load and lightly validate a versioned palette document."""
    palette_path = Path(path) if isinstance(path, (str, Path)) else path
    try:
        data = json.loads(palette_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PaletteError(f"Cannot load palette {palette_path}: {exc}") from exc
    if not isinstance(data, dict) or data.get("schema_version") != 1:
        raise PaletteError("Palette must be an object with schema_version 1")
    colours = data.get("colours")
    parts = data.get("parts")
    if not isinstance(colours, list) or not isinstance(parts, list):
        raise PaletteError("Palette must contain 'colours' and 'parts' arrays")
    colour_codes = [item.get("ldraw_code") for item in colours if isinstance(item, dict)]
    part_ids = [item.get("ldraw_file") for item in parts if isinstance(item, dict)]
    if len(colour_codes) != len(set(colour_codes)):
        raise PaletteError("Palette contains duplicate LDraw colour codes")
    if len(part_ids) != len(set(part_ids)):
        raise PaletteError("Palette contains duplicate LDraw part identifiers")
    if any(not isinstance(code, int) or isinstance(code, bool) for code in colour_codes):
        raise PaletteError("Every palette colour code must be an integer")
    if any(not isinstance(part_id, str) or part_id != part_id.lower() or not part_id.endswith(".dat") for part_id in part_ids):
        raise PaletteError("Every palette part identifier must be a lowercase .dat filename")
    return data
