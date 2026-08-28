"""Small injectable generation/repair loop used by the Hermes adapter."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any, Protocol

from .compiler import compile_model
from .geometry import validate_geometry
from .palette import load_palette
from .validation import ValidationError, repair_hint, validate_model


class GenerationAdapter(Protocol):
    def generate(
        self, request: str, attempt: int, feedback: list[dict[str, str]]
    ) -> dict[str, Any]: ...


class OfflineDemoAdapter:
    """Offline demo/test fixture, not a natural-language model."""

    def generate(
        self, request: str, attempt: int, feedback: list[dict[str, str]]
    ) -> dict[str, Any]:
        del attempt, feedback
        identity = [1, 0, 0, 0, 1, 0, 0, 0, 1]
        return {
            "schema_version": 1,
            "model_id": "hermes-generated",
            "name": request.strip()[:80] or "Generated model",
            "parts": [
                {
                    "id": "base",
                    "part": "3001.dat",
                    "colour": 4,
                    "translation_ldu": [0, 0, 0],
                    "matrix": identity,
                },
                {
                    "id": "top",
                    "part": "3001.dat",
                    "colour": 1,
                    "translation_ldu": [0, -24, 0],
                    "matrix": identity,
                },
            ],
        }


@dataclass(frozen=True)
class GenerationResult:
    valid: bool
    attempts: int
    run_dir: Path
    model: dict[str, Any] | None


def _write(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _software_version() -> str:
    """Return the installed package version, with a source-tree fallback."""
    try:
        return version("brick-builder")
    except PackageNotFoundError:
        return "0.1.0"


def _canonical_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def finalize_manifest(
    run_dir: str | Path,
    *,
    outcome: str,
    attempts: int,
    max_attempts: int,
    palette_path: str | Path,
    adapter: str | None = None,
) -> dict[str, Any]:
    """Hash a run's artifacts and atomically replace its manifest."""
    root = Path(run_dir)
    if not root.is_dir():
        raise ValueError(f"run directory does not exist: {root}")
    if outcome not in {"success", "exhausted"}:
        raise ValueError("outcome must be 'success' or 'exhausted'")
    if not isinstance(attempts, int) or isinstance(attempts, bool) or attempts < 0:
        raise ValueError("attempts must be a non-negative integer")
    if not isinstance(max_attempts, int) or isinstance(max_attempts, bool) or max_attempts <= 0:
        raise ValueError("max_attempts must be a positive integer")
    if attempts > max_attempts:
        raise ValueError("attempts must not exceed max_attempts")
    palette = load_palette(palette_path)
    files = sorted(
        path
        for path in root.iterdir()
        if path.is_file() and path.name not in {"manifest.json", ".manifest.json.tmp"}
    )
    manifest: dict[str, Any] = {
        "schema_version": 1,
        "software_version": _software_version(),
        "palette_id": palette.get("id"),
        "palette_sha256": _canonical_hash(palette),
        "attempts": attempts,
        "max_attempts": max_attempts,
        "outcome": outcome,
        "files": {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in files
        },
    }
    request_file = root / "request.txt"
    if request_file.is_file():
        manifest["request_sha256"] = hashlib.sha256(request_file.read_bytes()).hexdigest()
    if adapter is not None:
        manifest["adapter"] = adapter
    temporary = root / ".manifest.json.tmp"
    _write(temporary, manifest)
    temporary.replace(root / "manifest.json")
    return manifest


def _analysis_document(analysis: Any) -> dict[str, Any]:
    bounds = analysis.overall_bounds
    if bounds is None:
        bounds_ldu = None
        dimensions = None
    else:
        bounds = list(bounds)
        dimensions_ldu = [bounds[index + 3] - bounds[index] for index in range(3)]
        bounds_ldu = {
            "x": [bounds[0], bounds[3]],
            "y": [bounds[1], bounds[4]],
            "z": [bounds[2], bounds[5]],
        }
        dimensions = {
            "ldu": {axis: dimensions_ldu[index] for index, axis in enumerate(("x", "y", "z"))},
            "studs": {"x": dimensions_ldu[0] / 20, "z": dimensions_ldu[2] / 20},
            "plates": {"y": dimensions_ldu[1] / 8},
        }
    return {
        "edges": [list(edge) for edge in analysis.edges],
        "bounds_ldu": bounds_ldu,
        "dimensions": dimensions,
        "grounded_ids": list(analysis.grounded_ids),
        "root_id": analysis.root_id,
        "collision_count": sum(issue.code == "GEOMETRY_OVERLAP" for issue in analysis.issues),
        "disconnection_count": sum(issue.code == "DISCONNECTED_ASSEMBLY" for issue in analysis.issues),
    }


def generate(
    request: str,
    palette_path: str | Path,
    run_dir: str | Path,
    adapter: GenerationAdapter | None = None,
    max_attempts: int = 3,
) -> GenerationResult:
    if max_attempts <= 0:
        raise ValueError("max_attempts must be positive")
    palette = load_palette(palette_path)
    adapter = adapter or OfflineDemoAdapter()
    root = Path(run_dir)
    if root.exists():
        index = 1
        while root.with_name(f"{root.name}-{index:03d}").exists():
            index += 1
        root = root.with_name(f"{root.name}-{index:03d}")
    root.mkdir(parents=True, exist_ok=False)
    (root / "request.txt").write_text(request + "\n", encoding="utf-8")
    spec = {
        "request": request,
        "max_attempts": max_attempts,
        "palette": palette.get("id"),
        "constraints": {
            "categories": ["brick", "plate", "tile"],
            "orthogonal": True,
        },
    }
    _write(root / "spec.json", spec)
    feedback: list[dict[str, str]] = []
    final = None
    for attempt in range(1, max_attempts + 1):
        candidate = adapter.generate(request, attempt, feedback)
        _write(root / f"candidate-{attempt}.json", candidate)
        try:
            validate_model(candidate, palette)
            analysis = validate_geometry(candidate, palette)
            analysis_doc = _analysis_document(analysis)
            analysis_doc["issues"] = []
            _write(root / f"validation-{attempt}.json", {"valid": True, "issues": []})
            _write(root / f"analysis-{attempt}.json", analysis_doc)
            final = candidate
            break
        except ValidationError as exc:
            feedback = [
                {
                    "code": issue.code,
                    "path": issue.path,
                    "message": issue.message,
                    "repair_hint": repair_hint(issue.code),
                }
                for issue in exc.issues
            ]
            _write(root / f"validation-{attempt}.json", {"valid": False, "issues": feedback})
            _write(root / f"repair-feedback-{attempt}.json", feedback)
    if final is not None:
        compile_model(final, root / "final.ldr", palette)
        _write(root / "final.json", final)
        outcome = "success"
    else:
        outcome = "exhausted"
    manifest = finalize_manifest(
        root,
        outcome=outcome,
        attempts=min(attempt, max_attempts),
        max_attempts=max_attempts,
        palette_path=palette_path,
        adapter=type(adapter).__name__,
    )
    return GenerationResult(final is not None, manifest["attempts"], root, final)
