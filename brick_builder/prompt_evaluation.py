"""Deterministic aggregation of checked-in offline prompt evaluation evidence.

The evaluator consumes artifacts already produced by ``semantic_critique`` and
``critique_operations``.  It does not perform another critique or redesign;
it only validates provenance and compares declared finding states and bridge
validity between a baseline and a revision.
"""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass
from os import PathLike
from pathlib import Path
from typing import Any, Mapping


FORMAT = "brick-builder.prompt-evaluation/v1"
SEMANTIC_FORMAT = "brick-builder.semantic-critique/v1"
OPERATION_FORMAT = "brick-builder.critique-operation-evaluation/v1"
DIMENSIONS = ("identity", "silhouette", "landmarks", "proportions", "symmetry", "accidental_artifacts")
_FINDING_STATES = {"observed", "missing", "not-assessed"}


class PromptEvaluationError(ValueError):
    """Raised when a prompt evaluation set is malformed or inconsistent."""


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _hash(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _mapping(value: Any, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise PromptEvaluationError(f"{path} must be an object")
    return value


def _text(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PromptEvaluationError(f"{path} must be a non-empty string")
    return value.strip()


def _boolean(value: Any, path: str) -> bool:
    if not isinstance(value, bool):
        raise PromptEvaluationError(f"{path} must be boolean")
    return value


def _source_hashes(artifact: Mapping[str, Any]) -> dict[str, str]:
    """Keep both the artifact hash and the hashes declared inside it."""
    return {"artifact": _hash(artifact), **{
        key: value for key, value in artifact.items()
        if key.endswith("_hash") and isinstance(value, str)
    }}


def _validate_semantic(value: Any, path: str) -> Mapping[str, Any]:
    source = _mapping(value, path)
    if source.get("format") != SEMANTIC_FORMAT:
        raise PromptEvaluationError(f"{path}.format must be {SEMANTIC_FORMAT}")
    _text(source.get("prompt_fixture"), f"{path}.prompt_fixture")
    _text(source.get("candidate_id"), f"{path}.candidate_id")
    _text(source.get("fixture_hash"), f"{path}.fixture_hash")
    candidate = _mapping(source.get("candidate"), f"{path}.candidate")
    _text(candidate.get("id"), f"{path}.candidate.id")
    if candidate["id"] != source["candidate_id"]:
        raise PromptEvaluationError(f"{path}.candidate.id must match candidate_id")
    _text(candidate.get("model_id"), f"{path}.candidate.model_id")
    if not isinstance(candidate.get("artifact_hashes"), Mapping):
        raise PromptEvaluationError(f"{path}.candidate.artifact_hashes must be an object")
    dimensions = _mapping(source.get("dimensions"), f"{path}.dimensions")
    missing = [name for name in DIMENSIONS if name not in dimensions]
    unknown = sorted(set(dimensions) - set(DIMENSIONS))
    if missing:
        raise PromptEvaluationError(f"{path}.dimensions is missing: {', '.join(missing)}")
    if unknown:
        raise PromptEvaluationError(f"{path}.dimensions contains unsupported keys: {', '.join(unknown)}")
    for name in DIMENSIONS:
        finding = _mapping(dimensions[name], f"{path}.dimensions.{name}")
        if finding.get("status") not in _FINDING_STATES:
            raise PromptEvaluationError(f"{path}.dimensions.{name}.status is unsupported")
        if not isinstance(finding.get("source_evidence"), list):
            raise PromptEvaluationError(f"{path}.dimensions.{name}.source_evidence must be a list")
    engineering = _mapping(source.get("engineering_validation"), f"{path}.engineering_validation")
    _boolean(engineering.get("valid"), f"{path}.engineering_validation.valid")
    _boolean(engineering.get("structural_valid"), f"{path}.engineering_validation.structural_valid")
    if source.get("semantic_resemblance_evaluated") is not False:
        raise PromptEvaluationError(f"{path}.semantic_resemblance_evaluated must be false")
    trace = _mapping(source.get("traceability"), f"{path}.traceability")
    _text(trace.get("candidate_set_hash"), f"{path}.traceability.candidate_set_hash")
    _text(trace.get("visual_critique_hash"), f"{path}.traceability.visual_critique_hash")
    return source


def _validate_operation(value: Any, path: str) -> Mapping[str, Any]:
    source = _mapping(value, path)
    if source.get("format") != OPERATION_FORMAT:
        raise PromptEvaluationError(f"{path}.format must be {OPERATION_FORMAT}")
    prompt = _text(source.get("prompt_fixture"), f"{path}.prompt_fixture")
    candidate_id = _text(source.get("candidate_id"), f"{path}.candidate_id")
    _text(source.get("candidate_set_hash"), f"{path}.candidate_set_hash")
    baseline = _mapping(source.get("baseline"), f"{path}.baseline")
    candidate = _mapping(baseline.get("candidate"), f"{path}.baseline.candidate")
    if candidate.get("id") != candidate_id:
        raise PromptEvaluationError(f"{path}.baseline.candidate.id must match candidate_id")
    if not isinstance(candidate.get("artifact_hashes"), Mapping):
        raise PromptEvaluationError(f"{path}.baseline.candidate.artifact_hashes must be an object")
    if not isinstance(baseline.get("critique_observations"), Mapping):
        raise PromptEvaluationError(f"{path}.baseline.critique_observations must be an object")
    baseline_engineering = _mapping(baseline.get("engineering_validation"), f"{path}.baseline.engineering_validation")
    _boolean(baseline_engineering.get("valid"), f"{path}.baseline.engineering_validation.valid")
    _boolean(baseline_engineering.get("structural_valid"), f"{path}.baseline.engineering_validation.structural_valid")
    result = _mapping(source.get("result"), f"{path}.result")
    if result.get("status") not in {"accepted", "rejected"}:
        raise PromptEvaluationError(f"{path}.result.status must be accepted or rejected")
    _boolean(result.get("accepted"), f"{path}.result.accepted")
    if result["accepted"] != (result["status"] == "accepted"):
        raise PromptEvaluationError(f"{path}.result.accepted must match result.status")
    revision = _mapping(result.get("engineering_validation"), f"{path}.result.engineering_validation")
    _boolean(revision.get("valid"), f"{path}.result.engineering_validation.valid")
    _boolean(revision.get("structural_valid"), f"{path}.result.engineering_validation.structural_valid")
    comparison = _mapping(source.get("comparison"), f"{path}.comparison")
    if comparison.get("semantic_resemblance_evaluated") is not False:
        raise PromptEvaluationError(f"{path}.comparison.semantic_resemblance_evaluated must be false")
    _mapping(source.get("operation"), f"{path}.operation")
    trace = _mapping(source.get("traceability"), f"{path}.traceability")
    if trace.get("baseline_candidate_set_hash") != source["candidate_set_hash"]:
        raise PromptEvaluationError(f"{path}.traceability baseline candidate_set_hash does not match")
    return source


def _finding_outcome(before: str, after: str) -> str:
    if before == after:
        return "unchanged"
    if before == "missing" and after == "observed":
        return "improved"
    if before == "observed" and after == "missing":
        return "regressed"
    return "changed"


def _case(value: Any, index: int) -> dict[str, Any]:
    source = _mapping(value, f"cases[{index}]")
    case_id = _text(source.get("id"), f"cases[{index}].id")
    before = _validate_semantic(source.get("baseline_semantic_critique"), f"cases[{index}].baseline_semantic_critique")
    after = _validate_semantic(source.get("revision_semantic_critique"), f"cases[{index}].revision_semantic_critique")
    operation = _validate_operation(source.get("critique_operation_evaluation"), f"cases[{index}].critique_operation_evaluation")
    prompt = _text(source.get("prompt_fixture"), f"cases[{index}].prompt_fixture")
    candidate_id = _text(source.get("candidate_id"), f"cases[{index}].candidate_id")
    if prompt != before["prompt_fixture"] or prompt != after["prompt_fixture"] or prompt != operation["prompt_fixture"]:
        raise PromptEvaluationError(f"cases[{index}] prompt_fixture provenance does not match all source artifacts")
    if candidate_id != before["candidate_id"] or candidate_id != after["candidate_id"] or candidate_id != operation["candidate_id"]:
        raise PromptEvaluationError(f"cases[{index}] candidate_id provenance does not match all source artifacts")
    candidate_set_hash = operation["candidate_set_hash"]
    for label, artifact in (("baseline", before), ("revision", after)):
        trace_hash = artifact["traceability"]["candidate_set_hash"]
        if trace_hash != candidate_set_hash:
            raise PromptEvaluationError(f"cases[{index}] {label} candidate_set_hash does not match operation evidence")
    op_candidate = operation["baseline"]["candidate"]
    if dict(op_candidate.get("artifact_hashes", {})) != dict(before["candidate"].get("artifact_hashes", {})):
        raise PromptEvaluationError(f"cases[{index}] baseline candidate artifact hashes do not match")
    findings = {}
    for dimension in DIMENSIONS:
        left = before["dimensions"][dimension]["status"]
        right = after["dimensions"][dimension]["status"]
        findings[dimension] = {"baseline": left, "revision": right, "outcome": _finding_outcome(left, right)}
    baseline_valid = operation["baseline"]["engineering_validation"].get("valid")
    revision_valid = operation["result"]["engineering_validation"]["valid"]
    engineering_outcome = "unchanged" if baseline_valid == revision_valid else ("improved" if revision_valid else "regressed")
    finding_outcomes = [item["outcome"] for item in findings.values()]
    improved = "improved" in finding_outcomes
    regressed = "regressed" in finding_outcomes
    if operation["result"]["status"] == "rejected":
        outcome = "rejection"
    elif regressed or engineering_outcome == "regressed":
        outcome = "regression"
    elif improved or engineering_outcome == "improved":
        outcome = "improvement"
    else:
        outcome = "unchanged"
    return {
        "id": case_id, "prompt_fixture": prompt, "candidate_id": candidate_id,
        "candidate_set_hash": candidate_set_hash, "outcome": outcome,
        "semantic_findings": findings,
        "engineering_validity": {"baseline": baseline_valid, "revision": revision_valid, "outcome": engineering_outcome},
        "operation_status": operation["result"]["status"],
        "source_hashes": {"baseline_semantic": _hash(before), "revision_semantic": _hash(after), "critique_operation": _hash(operation)},
    }


@dataclass(frozen=True)
class PromptEvaluationSetResult:
    artifact: Mapping[str, Any]

    def snapshot(self) -> dict[str, Any]:
        return copy.deepcopy(dict(self.artifact))

    def serialize(self) -> str:
        return _canonical(self.artifact)

    def write(self, path: str | PathLike[str]) -> Path:
        target = Path(path).expanduser().resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(self.serialize() + "\n", encoding="utf-8", newline="\n")
        return target


def evaluate_prompt_evaluation_set(value: Mapping[str, Any] | list[Mapping[str, Any]]) -> PromptEvaluationSetResult:
    """Validate and aggregate a versioned set of baseline/revision cases."""
    if isinstance(value, list):
        source = {"format": FORMAT, "cases": value}
    else:
        source = _mapping(value, "evaluation_set")
        if source.get("format") != FORMAT:
            raise PromptEvaluationError(f"evaluation_set.format must be {FORMAT}")
    cases = source.get("cases")
    if not isinstance(cases, list) or not cases:
        raise PromptEvaluationError("evaluation_set.cases must be a non-empty list")
    seen: set[str] = set()
    evaluated = []
    for index, item in enumerate(cases):
        result = _case(item, index)
        if result["id"] in seen:
            raise PromptEvaluationError(f"cases contains duplicate id {result['id']!r}")
        seen.add(result["id"])
        evaluated.append(result)
    counts = {name: sum(item["outcome"] == name for item in evaluated) for name in ("improvement", "regression", "rejection", "unchanged")}
    artifact = {
        "format": FORMAT,
        "cases": evaluated,
        "summary": {"case_count": len(evaluated), "outcomes": counts},
        "semantic_resemblance_evaluated": False,
        "provenance": {"input_case_ids": [item["id"] for item in evaluated], "evaluation_set_hash": _hash(evaluated)},
    }
    return PromptEvaluationSetResult(artifact)


evaluate = evaluate_prompt_evaluation_set
