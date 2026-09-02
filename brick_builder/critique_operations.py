"""Deterministic offline critique-to-operation evaluation contract.

This module turns existing render/geometry observations into a declared,
allowlisted operation and applies it through the selected-candidate redesign
session.  It deliberately reports engineering validity and traceability only;
it does not score resemblance or choose an operation automatically.
"""

from __future__ import annotations

import copy
import hashlib
import json
from os import PathLike
from pathlib import Path
from typing import Any, Mapping

from .candidate_composition import CandidateCompositionResult
from .selected_candidate_redesign import SelectedCandidateRedesignSession


FORMAT = "brick-builder.critique-operation-evaluation/v1"
MAX_PARAMETER_KEYS = 3
MAX_HEIGHT_DELTA = 2
_COLOURS = {"red": "make it red", "green": "make it green", "blue": "make it blue"}
_OPERATIONS = {"recolor", "increase-height"}


class CritiqueOperationError(ValueError):
    """Raised when an offline critique-operation evaluation is malformed."""


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _hash(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _mapping(value: Any, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise CritiqueOperationError(f"{path} must be an object")
    return value


def _text(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CritiqueOperationError(f"{path} must be a non-empty string")
    return value.strip()


def _critique_for_candidate(critique: Mapping[str, Any], candidate_id: str) -> dict[str, Any]:
    if critique.get("format") != "brick-builder.visual-critique/v1":
        raise CritiqueOperationError("critique must use brick-builder.visual-critique/v1")
    candidates = critique.get("candidates")
    if not isinstance(candidates, list):
        raise CritiqueOperationError("critique.candidates must be a list")
    matches = [item for item in candidates if isinstance(item, Mapping) and item.get("id") == candidate_id]
    if len(matches) != 1:
        raise CritiqueOperationError(f"critique has no unique entry for candidate {candidate_id!r}")
    return copy.deepcopy(dict(matches[0]))


def _operation(value: Any) -> dict[str, Any]:
    operation = _mapping(value, "operation")
    name = _text(operation.get("name"), "operation.name")
    parameters = _mapping(operation.get("parameters"), "operation.parameters")
    if name not in _OPERATIONS:
        raise CritiqueOperationError(f"operation.name {name!r} is not allowlisted; choose recolor or increase-height")
    if len(parameters) > MAX_PARAMETER_KEYS:
        raise CritiqueOperationError(f"operation.parameters has more than {MAX_PARAMETER_KEYS} keys")
    if name == "recolor":
        colour = _text(parameters.get("color"), "operation.parameters.color").lower()
        if colour not in _COLOURS:
            raise CritiqueOperationError("operation.parameters.color must be red, green, or blue")
        allowed = {"color", "block_id"}
    else:
        delta = parameters.get("plates")
        if isinstance(delta, bool) or not isinstance(delta, int) or not 1 <= delta <= MAX_HEIGHT_DELTA:
            raise CritiqueOperationError("operation.parameters.plates must be an integer from 1 to 2")
        allowed = {"plates", "block_id"}
    unknown = sorted(set(parameters) - allowed)
    if unknown:
        raise CritiqueOperationError(f"operation.parameters contains unsupported keys: {', '.join(unknown)}")
    block_id = parameters.get("block_id", "box")
    if not isinstance(block_id, str) or not block_id.strip():
        raise CritiqueOperationError("operation.parameters.block_id must be a non-empty string")
    result = {"name": name, "parameters": dict(parameters)}
    result["parameters"]["block_id"] = block_id
    return result


def _source_result(value: CandidateCompositionResult | Mapping[str, Any]) -> CandidateCompositionResult:
    if isinstance(value, CandidateCompositionResult):
        return value
    if not isinstance(value, Mapping) or value.get("format") != "brick-builder.candidate-composition/v1":
        raise CritiqueOperationError("composition must be a CandidateCompositionResult or its v1 snapshot")
    candidates = value.get("candidates")
    if not isinstance(candidates, list) or not isinstance(value.get("candidate_set_hash"), str):
        raise CritiqueOperationError("composition snapshot is incomplete")
    return CandidateCompositionResult(
        str(value.get("request_text", "")), tuple(copy.deepcopy(candidates)),
        str(value.get("status", "")), value["candidate_set_hash"],
    )


def _validation(bridge: Mapping[str, Any] | None) -> dict[str, Any]:
    assembly = bridge.get("assembly") if isinstance(bridge, Mapping) else None
    return {
        "status": bridge.get("status") if isinstance(bridge, Mapping) else "missing",
        "valid": bool(assembly.get("valid")) if isinstance(assembly, Mapping) else False,
        "structural_valid": bool(assembly.get("structural_valid")) if isinstance(assembly, Mapping) else False,
        "diagnostics": list(bridge.get("diagnostics", [])) if isinstance(bridge, Mapping) else ["missing bridge evidence"],
    }


class CritiqueOperationEvaluation:
    """Immutable-shaped result with a canonical, replayable artifact."""

    def __init__(self, artifact: Mapping[str, Any]) -> None:
        self._artifact = copy.deepcopy(dict(artifact))

    def snapshot(self) -> dict[str, Any]:
        return copy.deepcopy(self._artifact)

    def serialize(self) -> str:
        return _canonical(self._artifact)

    def write(self, path: str | PathLike[str]) -> Path:
        """Persist the canonical evaluation artifact at an explicit path."""
        target = Path(path).expanduser().resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(self.serialize() + "\n", encoding="utf-8", newline="\n")
        return target

    @property
    def success(self) -> bool:
        return self._artifact["result"]["status"] == "accepted"


def evaluate_critique_operation(
    composition: CandidateCompositionResult | Mapping[str, Any],
    candidate_id: str,
    critique: Mapping[str, Any],
    operation: Mapping[str, Any],
    palette: Mapping[str, Any] | str | PathLike[str],
) -> CritiqueOperationEvaluation:
    """Apply one declared operation and return its deterministic evaluation.

    The selected redesign session owns proposal/rejection semantics and bridge
    revalidation.  This function adds only the versioned evaluation envelope.
    """
    source = _source_result(composition)
    if not source.success:
        raise CritiqueOperationError("composition must be a successful candidate set")
    if not isinstance(candidate_id, str) or not candidate_id:
        raise CritiqueOperationError("candidate_id must be a non-empty string")
    critique_entry = _critique_for_candidate(_mapping(critique, "critique"), candidate_id)
    declared = _operation(operation)
    selected = next((item for item in source.candidates if item.get("id") == candidate_id), None)
    if not isinstance(selected, Mapping) or selected.get("status") != "success":
        raise CritiqueOperationError(f"candidate {candidate_id!r} is not successful")
    geometry = selected.get("source_concept", {}).get("geometry", [])
    block_ids = {item.get("ref") for item in geometry if isinstance(item, Mapping)}
    block_id = declared["parameters"]["block_id"]
    if block_id not in block_ids:
        raise CritiqueOperationError(f"operation target block_id {block_id!r} is not in the selected candidate")
    session = SelectedCandidateRedesignSession(source, candidate_id, palette)
    baseline = copy.deepcopy(session.bridge_evidence)
    block = next(item for item in geometry if item.get("ref") == block_id)
    session.set_focus(tuple(block["center"]), radius=1, block_id=block_id)
    if declared["name"] == "recolor":
        instruction = _COLOURS[declared["parameters"]["color"].lower()]
    else:
        instruction = "make it taller"
    proposal = session.propose(instruction)
    accepted = session.accept()
    revision_bridge = accepted.get("bridge") if isinstance(accepted, Mapping) else None
    revision_validation = _validation(revision_bridge)
    baseline_validation = _validation(baseline)
    status = "accepted" if accepted.get("success") is True else "rejected"
    artifact = {
        "format": FORMAT,
        "prompt_fixture": source.request_text,
        "candidate_id": candidate_id,
        "candidate_set_hash": source.candidate_set_hash,
        "baseline": {
            "candidate": copy.deepcopy(selected),
            "critique_observations": critique_entry,
            "evidence_hash": _hash({"candidate": selected, "critique": critique_entry}),
            "engineering_validation": baseline_validation,
        },
        "operation": declared,
        "proposal": copy.deepcopy(proposal),
        "result": {
            "status": status,
            "accepted": status == "accepted",
            "engineering_validation": revision_validation,
            "baseline_preserved": status != "accepted" and session.accepted_concept.to_dict() == session.source_concept.to_dict(),
            "rejection_diagnostics": list(accepted.get("diagnostics", [])),
        },
        "comparison": {
            "improvement": {"engineering_validity_preserved": revision_validation["valid"] and baseline_validation["valid"]},
            "regression": {"engineering_validity_lost": baseline_validation["valid"] and not revision_validation["valid"]},
            "semantic_resemblance_evaluated": False,
        },
        "traceability": {
            "baseline_candidate_set_hash": source.candidate_set_hash,
            "baseline_evidence_hash": _hash({"candidate": selected, "critique": critique_entry}),
            "proposal_operation": declared["name"],
            "redesign_format": "brick-builder.selected-candidate-redesign/v1",
        },
    }
    return CritiqueOperationEvaluation(artifact)


evaluate = evaluate_critique_operation
