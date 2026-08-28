import json
from pathlib import Path
from typing import Any

from .validation import validate_model


def compile_model(model: dict[str, Any], output_path: str | Path, palette: dict[str, Any], library=None) -> Path:
    """Validate and deterministically compile one canonical model to a single-model .ldr."""
    validate_model(model, palette, library)
    output = Path(output_path)
    lines = [
        f"0 Brick Builder model: {model['model_id']}",
        f"0 Name: {model.get('name', model['model_id'])}",
        "0 Author: Brick Builder deterministic compiler",
        "0 !BRICK_BUILDER_SCHEMA_VERSION 1",
    ]
    for placement in model["parts"]:
        values = placement["translation_ldu"] + placement["matrix"]
        lines.append("1 " + " ".join(str(value) for value in [placement["colour"], *values, placement["part"]]))
    output.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return output


def load_and_compile(model_path: str | Path, output_path: str | Path, palette: dict[str, Any], library=None) -> Path:
    model = json.loads(Path(model_path).read_text(encoding="utf-8"))
    return compile_model(model, output_path, palette, library)
