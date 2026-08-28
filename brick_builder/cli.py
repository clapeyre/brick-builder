"""Machine-readable command-line contract for Brick Builder."""

import argparse
import hashlib
import json
from importlib.resources import files
from pathlib import Path

from .compiler import compile_model
from .generation import finalize_manifest, generate
from .geometry import profiles_from_palette, validate_geometry
from .ldraw import discover_ldraw_library
from .palette import load_palette
from .validation import ValidationError, repair_hint, validate_model


DEFAULT_PALETTE = files("brick_builder").joinpath("palettes/classic-core-v0.json")


def _issues(exc: ValidationError) -> list[dict[str, str]]:
    return [
        {
            "code": issue.code,
            "path": issue.path,
            "message": issue.message,
            "repair_hint": repair_hint(issue.code),
        }
        for issue in exc.issues
    ]


def _load(args):
    palette = load_palette(args.palette)
    library = (
        discover_ldraw_library(args.ldraw_library)
        if getattr(args, "ldraw_library", None)
        else None
    )
    model = (
        json.loads(Path(args.model).read_text(encoding="utf-8"))
        if getattr(args, "model", None)
        else None
    )
    return palette, library, model


def _catalog(args):
    palette = load_palette(args.palette)
    profiles = profiles_from_palette(palette)
    parts = []
    for part in sorted(palette["parts"], key=lambda value: value["ldraw_file"]):
        item = {
            "part": part["ldraw_file"],
            "name": part["name"],
            "category": part["category"],
        }
        profile = profiles.get(part["ldraw_file"])
        if profile:
            item.update(
                x_studs=profile.x_studs,
                z_studs=profile.z_studs,
                height_plates=profile.height_plates,
            )
        parts.append(item)
    colours = [
        {"code": colour["ldraw_code"], "name": colour["name"]}
        for colour in sorted(palette["colours"], key=lambda value: value["ldraw_code"])
    ]
    return {
        "schema_version": 1,
        "palette_version": palette.get("id"),
        "supported_categories": ["brick", "plate", "tile"],
        "deferred_categories": sorted(
            {
                part["category"]
                for part in palette["parts"]
                if part["category"] not in {"brick", "plate", "tile"}
            }
        ),
        "allowed_colours": colours,
        "parts": parts,
    }


def _validate(args):
    model = None
    try:
        palette, library, model = _load(args)
        validate_model(model, palette, library)
        return {
            "valid": True,
            "model_id": model.get("model_id"),
            "name": model.get("name"),
            "part_count": len(model.get("parts", [])),
            "issues": [],
        }
    except (ValidationError, OSError, ValueError) as exc:
        issues = (
            _issues(exc)
            if isinstance(exc, ValidationError)
            else [{
                "code": "INPUT_ERROR",
                "path": "$",
                "message": str(exc),
                "repair_hint": "Check the model and palette paths and JSON syntax.",
            }]
        )
        result = {"valid": False, "issues": issues}
        if isinstance(model, dict):
            result.update(
                model_id=model.get("model_id"),
                name=model.get("name"),
                part_count=len(model.get("parts", [])),
            )
        return result


def _analyze(args):
    result = _validate(args)
    if not result["valid"]:
        return result
    palette, _, model = _load(args)
    analysis = validate_geometry(model, palette)
    bounds = list(analysis.overall_bounds)
    dimensions = [bounds[index + 3] - bounds[index] for index in range(3)]
    return {
        **result,
        "edges": [list(edge) for edge in analysis.edges],
        "bounds_ldu": {
            "x": [bounds[0], bounds[3]],
            "y": [bounds[1], bounds[4]],
            "z": [bounds[2], bounds[5]],
        },
        "dimensions": {
            "ldu": {"x": dimensions[0], "y": dimensions[1], "z": dimensions[2]},
            "studs": {"x": dimensions[0] / 20, "z": dimensions[2] / 20},
            "plates": {"y": dimensions[1] / 8},
        },
        "grounded_ids": list(analysis.grounded_ids),
        "root_id": analysis.root_id,
        "collision_count": sum(
            issue.code == "GEOMETRY_OVERLAP" for issue in analysis.issues
        ),
        "disconnection_count": sum(
            issue.code == "DISCONNECTED_ASSEMBLY" for issue in analysis.issues
        ),
    }


def _compile(args):
    result = _validate(args)
    if not result["valid"]:
        return result
    palette, library, model = _load(args)
    output = compile_model(model, args.output, palette, library)
    return {
        "valid": True,
        "output_path": str(output),
        "model_id": model["model_id"],
        "name": model.get("name"),
        "part_count": len(model["parts"]),
        "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
        "issues": [],
    }


def generate_command(args):
    result = generate(args.request, args.palette, args.run_dir, max_attempts=args.max_attempts)
    return {
        "valid": result.valid,
        "attempts": result.attempts,
        "run_dir": str(result.run_dir),
        "model_id": result.model.get("model_id") if result.model else None,
    }


def manifest_command(args):
    return finalize_manifest(
        args.run_dir,
        outcome=args.outcome,
        attempts=args.attempts,
        max_attempts=args.max_attempts,
        palette_path=args.palette,
    )


def main(argv=None):
    if argv is None:
        import sys

        argv = sys.argv[1:]
    if (
        len(argv) >= 2
        and argv[0] not in {"catalog", "validate", "analyze", "compile", "demo-generate", "manifest", "-h", "--help"}
        and not argv[0].startswith("-")
    ):
        argv = ["compile", *argv]

    parser = argparse.ArgumentParser(description="Brick Builder machine-readable tools")
    subparsers = parser.add_subparsers(dest="command", required=True)

    catalog_parser = subparsers.add_parser("catalog")
    catalog_parser.add_argument("--palette", type=Path, default=DEFAULT_PALETTE)
    catalog_parser.set_defaults(handler=_catalog)

    for name, handler in (("validate", _validate), ("analyze", _analyze)):
        command_parser = subparsers.add_parser(name)
        command_parser.add_argument("model", type=Path)
        command_parser.add_argument("--palette", type=Path, default=DEFAULT_PALETTE)
        command_parser.add_argument("--ldraw-library", type=Path)
        command_parser.set_defaults(handler=handler)

    compile_parser = subparsers.add_parser("compile")
    compile_parser.add_argument("model", type=Path)
    compile_parser.add_argument("output", type=Path)
    compile_parser.add_argument("--palette", type=Path, default=DEFAULT_PALETTE)
    compile_parser.add_argument("--ldraw-library", type=Path)
    compile_parser.set_defaults(handler=_compile)

    generate_parser = subparsers.add_parser("demo-generate")
    generate_parser.add_argument("request")
    generate_parser.add_argument("--run-dir", type=Path, default=Path("runs/hermes-generated"))
    generate_parser.add_argument("--max-attempts", type=int, default=3)
    generate_parser.add_argument("--palette", type=Path, default=DEFAULT_PALETTE)
    generate_parser.set_defaults(handler=lambda args: generate_command(args))

    manifest_parser = subparsers.add_parser("manifest")
    manifest_parser.add_argument("run_dir", type=Path)
    manifest_parser.add_argument("--outcome", required=True)
    manifest_parser.add_argument("--attempts", type=int, required=True)
    manifest_parser.add_argument("--max-attempts", type=int, required=True)
    manifest_parser.add_argument("--palette", type=Path, default=DEFAULT_PALETTE)
    manifest_parser.set_defaults(handler=manifest_command)

    args = parser.parse_args(argv)
    try:
        result = args.handler(args)
        print(json.dumps(result, sort_keys=True, separators=(",", ":")))
        return 0 if result.get("valid", True) else 2
    except (OSError, ValueError) as exc:
        print(json.dumps({
            "valid": False,
            "issues": [{
                "code": "INPUT_ERROR",
                "path": "$",
                "message": str(exc),
                "repair_hint": "Check command arguments and input files.",
            }],
        }, sort_keys=True, separators=(",", ":")))
        return 2
    except Exception as exc:
        print(json.dumps({
            "valid": False,
            "issues": [{
                "code": "INTERNAL_ERROR",
                "path": "$",
                "message": str(exc),
                "repair_hint": "Report this unexpected error with reproduction details.",
            }],
        }, sort_keys=True, separators=(",", ":")))
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
