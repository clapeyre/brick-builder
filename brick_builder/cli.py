"""Machine-readable command-line contract for Brick Builder."""

import argparse
import hashlib
import json
import re
from importlib.resources import files
from pathlib import Path

from .compiler import compile_model
from .concept_redesign import ConceptRedesignSession, _concept_from_dict
from .candidate_composition import CandidateCompositionResult, compose_candidate_set, select_candidate as select_composed_candidate
from .demo_replay import replay_candidate_set, replay_demo, select_candidate
from .generation import finalize_manifest, generate
from .geometry import profiles_from_palette, validate_geometry
from .ldraw import discover_ldraw_library
from .palette import load_palette
from .legoization_bridge import legoize_accepted_box
from .spatial_concept import SpatialConceptSession, write_session_artifacts
from .stepped_legoization_bridge import legoize_accepted_stepped_boxes
from .gatehouse_legoization_bridge import legoize_accepted_gatehouse
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


def demo_replay_command(args):
    return replay_demo(args.request_file, args.brief, args.scaffold, args.run_dir, args.palette)


def demo_candidate_set_command(args):
    return replay_candidate_set(args.request_file, args.brief, args.candidates, args.run_dir, args.palette)


def select_candidate_command(args):
    return select_candidate(args.candidate_set_run, args.candidate_id, args.destination, args.palette)


def spatial_concepts_command(args):
    request = args.request.read_text(encoding="utf-8")
    response = json.loads(args.response.read_text(encoding="utf-8"))
    session = SpatialConceptSession(request)
    result = session.submit(response)
    if result["status"] in {"success", "clarification"}:
        return {"valid": True, **write_session_artifacts(session, args.run_dir)}
    return {**result, "valid": False}


def concept_redesign_command(args):
    state_path = args.run_dir / "concept-redesign.json"
    if args.operation == "start":
        if args.concept is None:
            raise ValueError("--concept is required for start")
        concept = json.loads(args.concept.read_text(encoding="utf-8"))
        session = ConceptRedesignSession(_concept_from_dict(concept), args.request_text)
    else:
        session = ConceptRedesignSession.from_serialized(state_path.read_text(encoding="utf-8"))
    if args.operation == "focus":
        session.set_focus(json.loads(args.point), args.radius, block_id=args.block_id)
    elif args.operation == "lock":
        session.lock_selected()
    elif args.operation == "propose":
        session.propose(args.instruction)
    elif args.operation == "retry":
        session.retry(args.instruction)
    elif args.operation == "accept":
        session.accept()
    elif args.operation == "undo":
        session.undo()
    elif args.operation != "start":
        raise ValueError(f"unsupported redesign operation: {args.operation}")
    args.run_dir.mkdir(parents=True, exist_ok=True)
    state_path.write_text(session.serialize() + "\n", encoding="utf-8", newline="\n")
    return {"valid": True, **session.snapshot(), "state_path": str(state_path)}


def legoize_concept_command(args):
    concept = _concept_from_dict(json.loads(args.concept.read_text(encoding="utf-8")))
    palette = load_palette(args.palette)
    result = legoize_accepted_box(concept, palette, colour=args.colour)
    output = result.snapshot()
    args.run_dir.mkdir(parents=True, exist_ok=True)
    (args.run_dir / "legoization-bridge.json").write_text(
        json.dumps(output, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8", newline="\n",
    )
    if result.success and result.compiled_ldr is not None:
        (args.run_dir / "final.ldr").write_text(result.compiled_ldr, encoding="utf-8", newline="\n")
    return {"valid": result.success, **output, "run_dir": str(args.run_dir)}


def legoize_stepped_concept_command(args):
    concept = _concept_from_dict(json.loads(args.concept.read_text(encoding="utf-8")))
    palette = load_palette(args.palette)
    result = legoize_accepted_stepped_boxes(concept, palette, colour=args.colour)
    output = result.snapshot()
    args.run_dir.mkdir(parents=True, exist_ok=True)
    (args.run_dir / "stepped-legoization-bridge.json").write_text(
        json.dumps(output, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8", newline="\n",
    )
    if result.success and result.compiled_ldr is not None:
        (args.run_dir / "final.ldr").write_text(result.compiled_ldr, encoding="utf-8", newline="\n")
    return {"valid": result.success, **output, "run_dir": str(args.run_dir)}


def legoize_gatehouse_concept_command(args):
    concept = _concept_from_dict(json.loads(args.concept.read_text(encoding="utf-8")))
    result = legoize_accepted_gatehouse(concept, load_palette(args.palette), colour=args.colour)
    output = result.snapshot()
    args.run_dir.mkdir(parents=True, exist_ok=True)
    (args.run_dir / "gatehouse-legoization-bridge.json").write_text(
        json.dumps(output, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8", newline="\n",
    )
    if result.success and result.compiled_ldr is not None:
        (args.run_dir / "final.ldr").write_text(result.compiled_ldr, encoding="utf-8", newline="\n")
    return {"valid": result.success, **output, "run_dir": str(args.run_dir)}


def concept_candidate_set_command(args):
    request = args.request.read_text(encoding="utf-8")
    raw_concepts = json.loads(args.concepts.read_text(encoding="utf-8"))
    if not isinstance(raw_concepts, list):
        raise ValueError("concepts input must be a list")
    concepts = []
    for value in raw_concepts:
        try:
            concepts.append(_concept_from_dict(value))
        except (TypeError, ValueError, KeyError):
            concepts.append(value)
    result = compose_candidate_set(request, concepts, load_palette(args.palette))
    output = result.snapshot()
    args.run_dir.mkdir(parents=True, exist_ok=True)
    (args.run_dir / "candidate-set.json").write_text(
        json.dumps(output, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8", newline="\n",
    )
    for index, candidate in enumerate(result.candidates, start=1):
        candidate_id = candidate.get("id")
        directory_name = candidate_id if isinstance(candidate_id, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,47}", candidate_id) else f"candidate-{index:02d}"
        child = args.run_dir / "candidates" / directory_name
        child.mkdir(parents=True, exist_ok=True)
        (child / "bridge.json").write_text(
            json.dumps(candidate, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8", newline="\n",
        )
        bridge = candidate.get("bridge")
        assembly = bridge.get("assembly") if isinstance(bridge, dict) else None
        compiled = assembly.get("compiled_ldr") if isinstance(assembly, dict) else None
        if candidate.get("status") == "success" and isinstance(compiled, str):
            (child / "final.ldr").write_text(compiled, encoding="utf-8", newline="\n")
    return {"valid": result.success, **output, "run_dir": str(args.run_dir)}


def select_composed_candidate_command(args):
    value = json.loads(args.candidate_set.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("candidate-set artifact must be an object")
    result = CandidateCompositionResult(
        value.get("request_text", ""), tuple(value.get("candidates", [])), value.get("status", ""), value.get("candidate_set_hash", "")
    )
    receipt = select_composed_candidate(result, args.candidate_id)
    args.run_dir.mkdir(parents=True, exist_ok=True)
    (args.run_dir / "selection.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )
    return {"valid": True, **receipt, "run_dir": str(args.run_dir)}


def main(argv=None):
    if argv is None:
        import sys

        argv = sys.argv[1:]
    if (
        len(argv) >= 2
        and argv[0] not in {"catalog", "validate", "analyze", "compile", "demo-generate", "demo-replay", "demo-candidate-set", "select-candidate", "spatial-concepts", "concept-redesign", "legoize-concept", "legoize-stepped-concept", "legoize-gatehouse-concept", "concept-candidate-set", "select-concept-candidate", "manifest", "-h", "--help"}
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

    replay_parser = subparsers.add_parser("demo-replay")
    replay_parser.add_argument("--request-file", type=Path, required=True)
    replay_parser.add_argument("--brief", type=Path, required=True)
    replay_parser.add_argument("--scaffold", type=Path, required=True)
    replay_parser.add_argument("--run-dir", type=Path, required=True)
    replay_parser.add_argument("--palette", type=Path, default=DEFAULT_PALETTE)
    replay_parser.set_defaults(handler=demo_replay_command)

    candidate_set_parser = subparsers.add_parser("demo-candidate-set")
    candidate_set_parser.add_argument("--request-file", type=Path, required=True)
    candidate_set_parser.add_argument("--brief", type=Path, required=True)
    candidate_set_parser.add_argument("--candidates", type=Path, required=True)
    candidate_set_parser.add_argument("--run-dir", type=Path, required=True)
    candidate_set_parser.add_argument("--palette", type=Path, default=DEFAULT_PALETTE)
    candidate_set_parser.set_defaults(handler=demo_candidate_set_command)

    selection_parser = subparsers.add_parser("select-candidate")
    selection_parser.add_argument("--candidate-set-run", type=Path, required=True)
    selection_parser.add_argument("--candidate-id", required=True)
    selection_parser.add_argument("--destination", type=Path, required=True)
    selection_parser.add_argument("--palette", type=Path, default=DEFAULT_PALETTE)
    selection_parser.set_defaults(handler=select_candidate_command)

    spatial_parser = subparsers.add_parser("spatial-concepts")
    spatial_parser.add_argument("--request", type=Path, required=True)
    spatial_parser.add_argument("--response", type=Path, required=True)
    spatial_parser.add_argument("--run-dir", type=Path, required=True)
    spatial_parser.set_defaults(handler=spatial_concepts_command)

    redesign_parser = subparsers.add_parser("concept-redesign")
    redesign_parser.add_argument("operation", choices=("start", "focus", "lock", "propose", "retry", "accept", "undo"))
    redesign_parser.add_argument("--run-dir", type=Path, required=True)
    redesign_parser.add_argument("--concept", type=Path)
    redesign_parser.add_argument("--request-text", default="")
    redesign_parser.add_argument("--point", default="[0, 0, 0]")
    redesign_parser.add_argument("--radius", type=float, default=3.0)
    redesign_parser.add_argument("--block-id")
    redesign_parser.add_argument("--instruction")
    redesign_parser.set_defaults(handler=concept_redesign_command)

    legoize_parser = subparsers.add_parser("legoize-concept")
    legoize_parser.add_argument("--concept", type=Path, required=True)
    legoize_parser.add_argument("--run-dir", type=Path, required=True)
    legoize_parser.add_argument("--palette", type=Path, default=DEFAULT_PALETTE)
    legoize_parser.add_argument("--colour", type=int, default=4)
    legoize_parser.set_defaults(handler=legoize_concept_command)

    stepped_parser = subparsers.add_parser("legoize-stepped-concept")
    stepped_parser.add_argument("--concept", type=Path, required=True)
    stepped_parser.add_argument("--run-dir", type=Path, required=True)
    stepped_parser.add_argument("--palette", type=Path, default=DEFAULT_PALETTE)
    stepped_parser.add_argument("--colour", type=int, default=4)
    stepped_parser.set_defaults(handler=legoize_stepped_concept_command)

    gatehouse_parser = subparsers.add_parser("legoize-gatehouse-concept")
    gatehouse_parser.add_argument("--concept", type=Path, required=True)
    gatehouse_parser.add_argument("--run-dir", type=Path, required=True)
    gatehouse_parser.add_argument("--palette", type=Path, default=DEFAULT_PALETTE)
    gatehouse_parser.add_argument("--colour", type=int, default=4)
    gatehouse_parser.set_defaults(handler=legoize_gatehouse_concept_command)

    concept_set_parser = subparsers.add_parser("concept-candidate-set")
    concept_set_parser.add_argument("--request", type=Path, required=True)
    concept_set_parser.add_argument("--concepts", type=Path, required=True)
    concept_set_parser.add_argument("--run-dir", type=Path, required=True)
    concept_set_parser.add_argument("--palette", type=Path, default=DEFAULT_PALETTE)
    concept_set_parser.set_defaults(handler=concept_candidate_set_command)

    concept_select_parser = subparsers.add_parser("select-concept-candidate")
    concept_select_parser.add_argument("--candidate-set", type=Path, required=True)
    concept_select_parser.add_argument("--candidate-id", required=True)
    concept_select_parser.add_argument("--run-dir", type=Path, required=True)
    concept_select_parser.set_defaults(handler=select_composed_candidate_command)

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
