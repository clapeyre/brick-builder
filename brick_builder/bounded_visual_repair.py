"""Bounded, provider-neutral visual repair operations.

This module owns one deliberately small operation: decreasing the height of a
selected one-box candidate by an integral number of plates.  Proposal and
acceptance remain owned by :class:`SelectedCandidateRedesignSession`, so the
existing reversible redesign and LEGOization bridge contracts are exercised.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
from os import PathLike
from pathlib import Path
from typing import Any, Mapping

from .candidate_composition import CandidateCompositionResult
from .local_redesign import EditProposal
from .selected_candidate_redesign import SelectedCandidateRedesignSession


FORMAT = "brick-builder.bounded-visual-repair/v1"
OPERATION = "decrease-height"
MAX_REDUCTION_PLATES = 2


class BoundedVisualRepairError(ValueError):
    """Raised when the selected candidate cannot be used for this operation."""


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _hash(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _source(value: CandidateCompositionResult | Mapping[str, Any]) -> CandidateCompositionResult:
    if isinstance(value, CandidateCompositionResult):
        return value
    if not isinstance(value, Mapping) or value.get("format") != "brick-builder.candidate-composition/v1":
        raise BoundedVisualRepairError("composition must be a CandidateCompositionResult or its v1 snapshot")
    candidates = value.get("candidates")
    if not isinstance(candidates, list) or not isinstance(value.get("candidate_set_hash"), str):
        raise BoundedVisualRepairError("composition snapshot is incomplete")
    return CandidateCompositionResult(
        str(value.get("request_text", "")), tuple(copy.deepcopy(candidates)),
        str(value.get("status", "")), value["candidate_set_hash"],
    )


def _reduction(value: Any) -> tuple[int | None, str | None]:
    if isinstance(value, bool) or not isinstance(value, int):
        return None, "plates must be an integer from 1 to 2"
    amount = value
    if amount < 0:
        return None, "plates must be positive; negative reductions are not allowed"
    if amount == 0:
        return None, "plates must be at least 1"
    if amount > MAX_REDUCTION_PLATES:
        return None, "plates must not exceed the bound of 2"
    return amount, None


def _rejected(source: CandidateCompositionResult, candidate_id: Any, plates: Any, diagnostic: str) -> dict[str, Any]:
    baseline = next((item for item in source.candidates if isinstance(item, Mapping) and item.get("id") == candidate_id), None)
    return {
        "format": FORMAT,
        "operation": {"name": OPERATION, "parameters": {"candidate_id": candidate_id, "plates": plates}},
        "candidate_id": candidate_id,
        "candidate_set_hash": source.candidate_set_hash,
        "status": "rejected",
        "accepted": False,
        "baseline_preserved": True,
        "diagnostics": [diagnostic],
        "baseline": copy.deepcopy(baseline),
        "proposal": None,
        "bridge": None,
        "claims": {"ranking": False, "resemblance": False, "child_preference": False},
    }


def decrease_height(
    composition: CandidateCompositionResult | Mapping[str, Any],
    candidate_id: str,
    plates: Any,
    palette: Mapping[str, Any] | str | PathLike[str],
) -> dict[str, Any]:
    """Propose and validate one explicit grounded height reduction.

    Invalid inputs and bridge failures return a rejection artifact without
    mutating the accepted baseline.  Source/composition contract failures are
    raised because there is no valid baseline session to preserve.
    """
    source = _source(composition)
    if not source.success:
        raise BoundedVisualRepairError("composition must be a successful candidate set")
    amount, error = _reduction(plates)
    if error:
        return _rejected(source, candidate_id, plates, error)
    if not isinstance(candidate_id, str) or not candidate_id.strip():
        return _rejected(source, candidate_id, plates, "candidate_id must be a non-empty string")
    selected = next((item for item in source.candidates if item.get("id") == candidate_id), None)
    if not isinstance(selected, Mapping) or selected.get("status") != "success":
        return _rejected(source, candidate_id, plates, f"candidate {candidate_id!r} is not a successful candidate")
    if selected.get("family") != "one-box":
        return _rejected(source, candidate_id, plates, "decrease-height supports only one-box candidates")
    geometry = selected.get("source_concept", {}).get("geometry")
    if not isinstance(geometry, list) or len(geometry) != 1 or not isinstance(geometry[0], Mapping):
        return _rejected(source, candidate_id, plates, "selected one-box candidate geometry is incomplete")

    raw = geometry[0]
    block_id, center, size = raw.get("ref"), raw.get("center"), raw.get("size")
    if not isinstance(block_id, str) or not isinstance(center, list) or not isinstance(size, list) or len(center) != 3 or len(size) != 3:
        return _rejected(source, candidate_id, plates, "selected one-box geometry has invalid block fields")
    height = size[1]
    if isinstance(height, bool) or not isinstance(height, (int, float)) or not math.isfinite(float(height)) or not float(height).is_integer():
        return _rejected(source, candidate_id, plates, "baseline height must be an integer number of plates")
    if height - amount <= 0:
        return _rejected(source, candidate_id, plates, "reduction would violate the positive-height bridge bound")

    session = SelectedCandidateRedesignSession(source, candidate_id, palette)
    baseline = copy.deepcopy(session.bridge_evidence)
    block = session.blocks[0]
    if block.id != block_id:
        return _rejected(source, candidate_id, plates, "selected one-box geometry does not match the redesign session")
    new_height = int(height) - amount
    after_block = block.moved(center=(block.center[0], new_height / 2, block.center[2]), size=(block.size[0], new_height, block.size[2]))
    proposal = EditProposal(
        instruction=f"decrease height by {amount} plate(s)", before=session.blocks,
        after=(after_block,), changed_ids=(block_id,), selected_ids=(block_id,),
        spillover_ids=(), protected_ids=(), locked_ids=tuple(sorted(session.locked_ids)),
        expansion_limit=0.0, retry_number=0,
    )
    object.__setattr__(proposal, "_focus_point", block.center)
    object.__setattr__(proposal, "_focus_radius", 1.0)
    session.redesign.local.proposal = proposal
    proposal_record = copy.deepcopy(proposal.contract)
    session.redesign.evidence.append({"operation": "propose", "proposal": proposal_record})
    accepted = session.accept()
    success = accepted.get("success") is True
    return {
        "format": FORMAT,
        "operation": {"name": OPERATION, "parameters": {"candidate_id": candidate_id, "plates": amount}},
        "candidate_id": candidate_id,
        "candidate_set_hash": source.candidate_set_hash,
        "status": "accepted" if success else "rejected",
        "accepted": success,
        "baseline_preserved": not success and session.accepted_concept.to_dict() == session.source_concept.to_dict(),
        "baseline": {"candidate": copy.deepcopy(selected), "bridge": baseline, "evidence_hash": _hash(baseline)},
        "proposal": proposal_record,
        "bridge": accepted.get("bridge"),
        "diagnostics": list(accepted.get("diagnostics", [])),
        "result": {"height_before_plates": int(height), "height_after_plates": new_height, "grounded": True},
        "claims": {"ranking": False, "resemblance": False, "child_preference": False},
        "session": json.loads(session.serialize()),
    }


apply_decrease_height = decrease_height


def write_repair_artifact(result: Mapping[str, Any], path: str | PathLike[str]) -> Path:
    """Persist a returned repair artifact at an explicit path."""
    target = Path(path).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(_canonical(result) + "\n", encoding="utf-8", newline="\n")
    return target
