"""Provider-neutral composition of the supported concept-family bridges.

This is an orchestration contract only.  It deliberately has no ranking,
repair, or automatic selection: every supplied concept is evaluated in input
order and selection is a separate operation requiring an exact successful ID.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from os import PathLike
from typing import Any, Mapping, Sequence

from .gatehouse_legoization_bridge import legoize_accepted_gatehouse
from .legoization_bridge import legoize_accepted_box
from .spatial_concept import GenericBoxConcept
from .stepped_legoization_bridge import legoize_accepted_stepped_boxes


FORMAT = "brick-builder.candidate-composition/v1"
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,47}$")


class CandidateCompositionError(ValueError):
    """Raised when the candidate-set envelope cannot be evaluated."""


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _hash(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _normalized_number(value: Any) -> int | float:
    """Canonicalize equivalent numeric values before geometry hashing."""
    number = float(value)
    if number.is_integer():
        return int(number)
    return number


def _geometry_key(concept: GenericBoxConcept) -> tuple[tuple[tuple[int | float, ...], tuple[int | float, ...]], ...]:
    """Return geometry only, independent of names, refs, cameras, and order."""
    boxes = (
        (
            tuple(_normalized_number(value) for value in box.center),
            tuple(_normalized_number(value) for value in box.size),
        )
        for box in concept.boxes
    )
    return tuple(sorted(boxes))


def _geometry_hash(concept: GenericBoxConcept) -> str:
    return _hash({"boxes": _geometry_key(concept)})


def _source(value: Any) -> dict[str, Any]:
    if isinstance(value, GenericBoxConcept):
        try:
            return value.to_dict()
        except Exception as exc:  # malformed hand-constructed concepts remain evidence
            return {"id": getattr(value, "id", None), "error": str(exc)}
    return {"value": repr(value)}


def _malformed(value: Any, index: int) -> tuple[str, dict[str, Any]]:
    candidate_id = getattr(value, "id", None)
    label = candidate_id if isinstance(candidate_id, str) else f"candidate-{index}"
    return label, {
        "id": label,
        "source_concept": _source(value),
        "family": None,
        "status": "failed",
        "model_id": None,
        "diagnostics": (f"MALFORMED_CANDIDATE: candidate {index} must be a GenericBoxConcept",),
        "artifact_hashes": {"evidence": _hash({"id": label, "status": "failed", "diagnostics": [f"MALFORMED_CANDIDATE: candidate {index} must be a GenericBoxConcept"]})},
    }


def _family(box_count: int) -> tuple[str, Any] | None:
    if box_count == 1:
        return "one-box", legoize_accepted_box
    if box_count == 2:
        return "stepped-box", legoize_accepted_stepped_boxes
    if box_count == 3:
        return "gatehouse", legoize_accepted_gatehouse
    return None


@dataclass(frozen=True)
class CandidateCompositionResult:
    request_text: str
    candidates: tuple[dict[str, Any], ...]
    status: str
    candidate_set_hash: str

    @property
    def success(self) -> bool:
        return self.status == "success"

    def snapshot(self) -> dict[str, Any]:
        return {
            "format": FORMAT,
            "request_text": self.request_text,
            "status": self.status,
            "candidates": list(self.candidates),
            "candidate_set_hash": self.candidate_set_hash,
        }

    def serialize(self) -> str:
        return _canonical(self.snapshot())


def compose_candidate_set(
    request_text: str,
    concepts: Sequence[GenericBoxConcept],
    palette: Mapping[str, Any] | str | PathLike[str],
) -> CandidateCompositionResult:
    """Evaluate exactly two or three concepts without ranking or selecting."""
    if not isinstance(request_text, str) or not request_text.strip():
        raise CandidateCompositionError("request_text must be a non-empty string")
    if not isinstance(concepts, (list, tuple)) or len(concepts) not in {2, 3}:
        raise CandidateCompositionError("candidate set must contain exactly two or three concepts")

    records: list[dict[str, Any]] = []
    ids: set[str] = set()
    duplicate = False
    geometries: dict[str, tuple[int, str | None]] = {}
    for index, concept in enumerate(concepts, start=1):
        if not isinstance(concept, GenericBoxConcept):
            _id, record = _malformed(concept, index)
            records.append(record)
            continue
        source = _source(concept)
        candidate_id = concept.id
        diagnostics: list[str] = []
        geometry_hash = _geometry_hash(concept)
        previous_geometry = geometries.get(geometry_hash)
        if previous_geometry is None:
            geometries[geometry_hash] = (index, candidate_id if isinstance(candidate_id, str) else None)
        else:
            previous_index, previous_id = previous_geometry
            previous_label = previous_id if previous_id is not None else f"candidate {previous_index}"
            diagnostics.append(
                "DUPLICATE_GEOMETRY: candidate "
                f"{candidate_id!r} repeats normalized box geometry from {previous_label!r} "
                f"(geometry hash {geometry_hash[:16]}); change a box center or size"
            )
            duplicate = True
        if not isinstance(candidate_id, str) or not _ID.fullmatch(candidate_id):
            diagnostics.append("MALFORMED_ID: candidate id must contain only letters, numbers, '_' or '-'")
        elif candidate_id in ids:
            diagnostics.append(f"DUPLICATE_ID: candidate id {candidate_id!r} is not unique")
            duplicate = True
        ids.add(candidate_id)
        family = _family(len(concept.boxes)) if isinstance(concept.boxes, (tuple, list)) else None
        if family is None:
            diagnostics.append("UNSUPPORTED_SHAPE: supported candidates contain one, two, or three boxes")
        if diagnostics:
            records.append({
                "id": candidate_id,
                "source_concept": source,
                "family": family[0] if family else None,
                "status": "failed",
                "model_id": None,
                "diagnostics": tuple(diagnostics),
                "geometry_hash": geometry_hash,
                "artifact_hashes": {"source": _hash(source), "evidence": _hash({"id": candidate_id, "diagnostics": diagnostics, "geometry_hash": geometry_hash})},
            })
            continue
        if any(item.startswith("DUPLICATE_GEOMETRY:") for item in diagnostics):
            records.append({
                "id": candidate_id,
                "source_concept": source,
                "family": family[0],
                "status": "failed",
                "model_id": None,
                "diagnostics": tuple(diagnostics),
                "geometry_hash": geometry_hash,
                "artifact_hashes": {"source": _hash(source), "evidence": _hash({"id": candidate_id, "diagnostics": diagnostics, "geometry_hash": geometry_hash})},
            })
            continue
        try:
            bridge = family[1](concept, palette)
            bridge_snapshot = bridge.snapshot()
            successful = bridge.success
            diagnostic_values = list(bridge.diagnostics)
            assembly = bridge_snapshot.get("assembly", {})
            model_id = assembly.get("model", {}).get("model_id") if isinstance(assembly, dict) else None
            artifact_hashes = {
                "source": _hash(source),
                "evidence": _hash(bridge_snapshot),
            }
            if bridge.compiled_ldr is not None:
                artifact_hashes["final.ldr"] = hashlib.sha256(bridge.compiled_ldr.encode("utf-8")).hexdigest()
            records.append({"id": candidate_id, "source_concept": source, "family": family[0],
                            "status": "success" if successful else "failed", "model_id": model_id,
                            "diagnostics": tuple(diagnostic_values), "geometry_hash": geometry_hash, "artifact_hashes": artifact_hashes,
                            "bridge": bridge_snapshot})
        except Exception as exc:
            records.append({"id": candidate_id, "source_concept": source, "family": family[0],
                            "status": "failed", "model_id": None,
                            "diagnostics": (f"BRIDGE_ERROR: {type(exc).__name__}: {exc}",),
                            "geometry_hash": geometry_hash,
                            "artifact_hashes": {"source": _hash(source), "evidence": _hash({"id": candidate_id, "error": str(exc), "geometry_hash": geometry_hash})}})

    if duplicate:
        status = "rejected"
    else:
        status = "success" if all(item["status"] == "success" for item in records) else "rejected"
    material = {"format": FORMAT, "request_text": request_text, "candidates": records}
    return CandidateCompositionResult(request_text, tuple(records), status, _hash(material))


def select_candidate(result: CandidateCompositionResult, candidate_id: str) -> dict[str, Any]:
    """Create provenance for one explicitly declared successful candidate."""
    if not isinstance(result, CandidateCompositionResult):
        raise TypeError("result must be a CandidateCompositionResult")
    if not isinstance(candidate_id, str) or not _ID.fullmatch(candidate_id):
        raise CandidateCompositionError("selected candidate id is malformed")
    if not result.success:
        raise CandidateCompositionError("candidate set is not a successful selectable set")
    matches = [item for item in result.candidates if item["id"] == candidate_id]
    if len(matches) != 1 or matches[0]["status"] != "success":
        raise CandidateCompositionError(f"candidate {candidate_id!r} is not a declared successful candidate")
    selected = matches[0]
    return {
        "format": "brick-builder.candidate-selection/v1",
        "candidate_set_hash": result.candidate_set_hash,
        "selected_candidate_id": candidate_id,
        "selected_family": selected["family"],
        "selected_model_id": selected["model_id"],
        "selected_artifact_hashes": dict(selected["artifact_hashes"]),
        "source_concept_id": selected["source_concept"]["id"],
    }
