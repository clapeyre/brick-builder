"""Deterministic offline semantic-critique evidence over existing artifacts.

This is intentionally an evidence contract, not a vision system.  A caller
declares bounded expectations in a checked-in fixture; the evaluator compares
those expectations with successful composition data and existing
visual-critique observations.  Unsupported dimensions remain explicit rather
than being guessed.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
from dataclasses import dataclass
from os import PathLike
from pathlib import Path
from typing import Any, Mapping


FORMAT = "brick-builder.semantic-critique/v1"
FIXTURE_FORMAT = "brick-builder.semantic-critique-fixture/v1"
DIMENSIONS = ("identity", "silhouette", "landmarks", "proportions", "symmetry", "accidental_artifacts")
STATUSES = {"observed", "missing", "not-assessed"}
_DIMENSION_KEYS = {
    "identity": {"family", "model_id"},
    "silhouette": {"camera_id", "occupancy", "aspect"},
    "landmarks": {"camera_id", "required"},
    "proportions": {"camera_id", "aspect"},
    "symmetry": {"camera_id", "required"},
    "accidental_artifacts": {"camera_id", "forbid"},
}


class SemanticCritiqueError(ValueError):
    """Raised when semantic-critique evidence or its fixture is malformed."""


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _hash(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _mapping(value: Any, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise SemanticCritiqueError(f"{path} must be an object")
    return value


def _text(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SemanticCritiqueError(f"{path} must be a non-empty string")
    return value.strip()


def _finite(value: Any, path: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise SemanticCritiqueError(f"{path} must be a finite number")
    return float(value)


def _range(value: Any, path: str) -> tuple[float, float]:
    raw = _mapping(value, path)
    unknown = sorted(set(raw) - {"min", "max"})
    if unknown:
        raise SemanticCritiqueError(f"{path} contains unsupported keys: {', '.join(unknown)}")
    low = _finite(raw.get("min"), f"{path}.min")
    high = _finite(raw.get("max"), f"{path}.max")
    if low > high:
        raise SemanticCritiqueError(f"{path}.min must not exceed {path}.max")
    return low, high


def _composition_candidate(composition: Any, candidate_id: str) -> Mapping[str, Any]:
    if hasattr(composition, "snapshot") and callable(composition.snapshot):
        composition = composition.snapshot()
    source = _mapping(composition, "composition")
    if source.get("format") != "brick-builder.candidate-composition/v1":
        raise SemanticCritiqueError("composition must use brick-builder.candidate-composition/v1")
    if source.get("status") != "success":
        raise SemanticCritiqueError("composition must have status 'success' before semantic critique")
    candidates = source.get("candidates")
    if not isinstance(candidates, list):
        raise SemanticCritiqueError("composition.candidates must be a list")
    matches = [item for item in candidates if isinstance(item, Mapping) and item.get("id") == candidate_id]
    if len(matches) != 1 or matches[0].get("status") != "success":
        raise SemanticCritiqueError(f"candidate {candidate_id!r} is not a unique successful composition candidate")
    return matches[0]


def _critique_entry(critique: Any, candidate_id: str) -> Mapping[str, Any]:
    source = _mapping(critique, "visual_critique")
    if source.get("format") != "brick-builder.visual-critique/v1":
        raise SemanticCritiqueError("visual_critique must use brick-builder.visual-critique/v1")
    candidates = source.get("candidates")
    if not isinstance(candidates, list):
        raise SemanticCritiqueError("visual_critique.candidates must be a list")
    matches = [item for item in candidates if isinstance(item, Mapping) and item.get("id") == candidate_id]
    if len(matches) != 1:
        raise SemanticCritiqueError(f"visual_critique has no unique entry for candidate {candidate_id!r}")
    return matches[0]


def _validate_fixture(fixture: Any) -> Mapping[str, Any]:
    source = _mapping(fixture, "fixture")
    if source.get("format") != FIXTURE_FORMAT:
        raise SemanticCritiqueError(f"fixture.format must be {FIXTURE_FORMAT}")
    expected = _mapping(source.get("expected"), "fixture.expected")
    unknown = sorted(set(expected) - set(DIMENSIONS))
    if unknown:
        raise SemanticCritiqueError(f"fixture.expected contains unsupported dimensions: {', '.join(unknown)}")
    missing = [name for name in DIMENSIONS if name not in expected]
    if missing:
        raise SemanticCritiqueError(f"fixture.expected is missing dimensions: {', '.join(missing)}")
    for dimension in DIMENSIONS:
        value = _mapping(expected[dimension], f"fixture.expected.{dimension}")
        unknown = sorted(set(value) - _DIMENSION_KEYS[dimension])
        if unknown:
            raise SemanticCritiqueError(
                f"fixture.expected.{dimension} contains unsupported keys: {', '.join(unknown)}"
            )
    return source


def _camera(entry: Mapping[str, Any], camera_id: str, path: str) -> Mapping[str, Any] | None:
    cameras = entry.get("cameras")
    if not isinstance(cameras, list):
        raise SemanticCritiqueError("visual_critique candidate.cameras must be a list")
    matches = [item for item in cameras if isinstance(item, Mapping) and item.get("camera_id") == camera_id]
    if len(matches) > 1:
        raise SemanticCritiqueError(f"{path} has duplicate camera {camera_id!r}")
    return matches[0] if matches else None


def _evidence_ref(camera: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    if camera is None:
        return []
    evidence = camera.get("evidence")
    return [copy.deepcopy(dict(evidence))] if isinstance(evidence, Mapping) else []


def _finding(status: str, expectation: Any, *, detail: str, refs: list[dict[str, Any]]) -> dict[str, Any]:
    return {"status": status, "expectation": copy.deepcopy(expectation), "finding": detail, "source_evidence": refs}


def _engineering(candidate: Mapping[str, Any]) -> dict[str, Any]:
    bridge = candidate.get("bridge")
    assembly = bridge.get("assembly") if isinstance(bridge, Mapping) else None
    if not isinstance(assembly, Mapping):
        return {"status": "missing", "valid": False, "structural_valid": False, "diagnostics": ["missing bridge assembly evidence"]}
    return {
        "status": bridge.get("status", "missing"),
        "valid": bool(assembly.get("valid")),
        "structural_valid": bool(assembly.get("structural_valid")),
        "diagnostics": list(bridge.get("diagnostics", [])) if isinstance(bridge.get("diagnostics", []), (list, tuple)) else ["bridge diagnostics must be a list"],
        "source_evidence": [{"artifact_hashes": copy.deepcopy(candidate.get("artifact_hashes", {}))}],
    }


def evaluate_semantic_critique(composition: Any, candidate_id: str, visual_critique: Any, fixture: Any) -> "SemanticCritiqueResult":
    """Evaluate one declared fixture against one successful candidate."""
    candidate_id = _text(candidate_id, "candidate_id")
    declared = _validate_fixture(fixture)
    composition_snapshot = composition.snapshot() if hasattr(composition, "snapshot") and callable(composition.snapshot) else composition
    composition_snapshot = _mapping(composition_snapshot, "composition")
    candidate = _composition_candidate(composition, candidate_id)
    critique = _critique_entry(visual_critique, candidate_id)
    expected = declared["expected"]
    findings: dict[str, dict[str, Any]] = {}

    identity = expected["identity"]
    refs: list[dict[str, Any]] = [{"candidate_set_hash": composition_snapshot.get("candidate_set_hash")}]
    identity_values = {key: candidate.get(key) for key in ("family", "model_id")}
    checks = [(key, value) for key, value in identity.items() if key in {"family", "model_id"}]
    if not checks:
        findings["identity"] = _finding("not-assessed", identity, detail="fixture declares no supported identity fields", refs=refs)
    else:
        failed = [key for key, value in checks if identity_values.get(key) != value]
        findings["identity"] = _finding("observed", identity, detail="identity expectations satisfied" if not failed else f"identity expectation not met: {', '.join(failed)}", refs=refs)
        if failed:
            findings["identity"]["status"] = "missing"

    silhouette = expected["silhouette"]
    camera_id = _text(silhouette.get("camera_id"), "fixture.expected.silhouette.camera_id")
    camera = _camera(critique, camera_id, "fixture.expected.silhouette")
    observations = camera.get("observations", {}).get("silhouette") if camera else None
    if not isinstance(observations, Mapping) or observations.get("occupancy") is None or observations.get("aspect") is None:
        findings["silhouette"] = _finding("missing", silhouette, detail=f"camera {camera_id!r} has no bounded silhouette observation", refs=_evidence_ref(camera))
    else:
        checks = []
        for key in ("occupancy", "aspect"):
            if key in silhouette:
                low, high = _range(silhouette[key], f"fixture.expected.silhouette.{key}")
                checks.append((key, low <= float(observations[key]) <= high))
        findings["silhouette"] = _finding("observed" if all(ok for _, ok in checks) else "missing", silhouette, detail="silhouette expectations satisfied" if all(ok for _, ok in checks) else "one or more silhouette bounds were not met", refs=_evidence_ref(camera))

    landmark_expectations = expected["landmarks"].get("required", [])
    if not isinstance(landmark_expectations, list):
        raise SemanticCritiqueError("fixture.expected.landmarks.required must be a list")
    camera_id = _text(expected["landmarks"].get("camera_id"), "fixture.expected.landmarks.camera_id")
    camera = _camera(critique, camera_id, "fixture.expected.landmarks")
    landmark_visibility = camera.get("observations", {}).get("landmark_visibility") if camera else None
    if not isinstance(landmark_visibility, Mapping):
        findings["landmarks"] = _finding("missing", expected["landmarks"], detail=f"camera {camera_id!r} has no landmark visibility observation", refs=_evidence_ref(camera))
    else:
        invalid = [item for item in landmark_expectations if not isinstance(item, Mapping) or not isinstance(item.get("id"), str)]
        if invalid:
            raise SemanticCritiqueError("fixture.expected.landmarks.required entries must contain string id fields")
        failed = [item["id"] for item in landmark_expectations if landmark_visibility.get(item["id"]) is not bool(item.get("visible", True))]
        findings["landmarks"] = _finding("observed" if not failed else "missing", expected["landmarks"], detail="landmark expectations satisfied" if not failed else f"landmark expectations not met: {', '.join(failed)}", refs=_evidence_ref(camera))

    proportions = expected["proportions"]
    camera_id = proportions.get("camera_id", silhouette.get("camera_id"))
    if not isinstance(camera_id, str) or not camera_id.strip():
        findings["proportions"] = _finding("not-assessed", proportions, detail="fixture declares no supported camera", refs=[])
    else:
        camera = _camera(critique, camera_id, "fixture.expected.proportions")
        shape = camera.get("observations", {}).get("silhouette") if camera else None
        if not isinstance(shape, Mapping) or shape.get("aspect") is None or "aspect" not in proportions:
            findings["proportions"] = _finding("not-assessed", proportions, detail="proportion aspect evidence is unavailable", refs=_evidence_ref(camera))
        else:
            low, high = _range(proportions["aspect"], "fixture.expected.proportions.aspect")
            ok = low <= float(shape["aspect"]) <= high
            findings["proportions"] = _finding("observed" if ok else "missing", proportions, detail="proportion expectation satisfied" if ok else "proportion aspect bound was not met", refs=_evidence_ref(camera))

    for dimension in ("symmetry", "accidental_artifacts"):
        expectation = expected[dimension]
        findings[dimension] = _finding("not-assessed", expectation, detail=f"no deterministic {dimension.replace('_', ' ')} observation is present in visual-critique/v1", refs=[])

    artifact = {
        "format": FORMAT,
        "prompt_fixture": composition_snapshot.get("request_text"),
        "candidate_id": candidate_id,
        "candidate": {
            "id": candidate_id,
            "model_id": candidate.get("model_id"),
            "artifact_hashes": copy.deepcopy(candidate.get("artifact_hashes", {})),
        },
        "fixture_format": declared["format"],
        "fixture_hash": _hash(declared),
        "dimensions": findings,
        "engineering_validation": _engineering(candidate),
        "semantic_resemblance_evaluated": False,
        "traceability": {
            "candidate_set_hash": composition_snapshot.get("candidate_set_hash"),
            "visual_critique_format": visual_critique.get("format") if isinstance(visual_critique, Mapping) else None,
            "visual_critique_hash": _hash(visual_critique),
        },
    }
    return SemanticCritiqueResult(artifact)


@dataclass(frozen=True)
class SemanticCritiqueResult:
    artifact: Mapping[str, Any]

    def snapshot(self) -> dict[str, Any]:
        return copy.deepcopy(dict(self.artifact))

    def serialize(self) -> str:
        return _canonical(self.artifact)

    def write(self, path: str | PathLike[str]) -> Path:
        """Persist the canonical semantic-critique artifact at an explicit path."""
        target = Path(path).expanduser().resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(self.serialize() + "\n", encoding="utf-8", newline="\n")
        return target


evaluate = evaluate_semantic_critique
