"""Explicit candidate selection bound to the reversible concept redesign contract."""

from __future__ import annotations

import copy
import json
from os import PathLike
from typing import Any, Mapping

from .candidate_composition import CandidateCompositionResult, select_candidate
from .concept_redesign import ConceptRedesignSession, _concept_from_dict
from .gatehouse_legoization_bridge import legoize_accepted_gatehouse
from .legoization_bridge import legoize_accepted_box
from .palette import load_palette
from .stepped_legoization_bridge import legoize_accepted_stepped_boxes
from .spatial_concept import GenericBoxConcept


FORMAT = "brick-builder.selected-candidate-redesign/v1"
_BRIDGES = {
    "one-box": legoize_accepted_box,
    "stepped-box": legoize_accepted_stepped_boxes,
    "gatehouse": legoize_accepted_gatehouse,
}


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _result(value: CandidateCompositionResult | Mapping[str, Any]) -> CandidateCompositionResult:
    if isinstance(value, CandidateCompositionResult):
        return value
    if not isinstance(value, Mapping) or value.get("format") != "brick-builder.candidate-composition/v1":
        raise ValueError("candidate composition must be a CandidateCompositionResult or its snapshot")
    candidates = value.get("candidates")
    if not isinstance(candidates, list) or not isinstance(value.get("candidate_set_hash"), str):
        raise ValueError("candidate composition snapshot is incomplete")
    return CandidateCompositionResult(
        value.get("request_text", ""), tuple(copy.deepcopy(candidates)),
        value.get("status", ""), value["candidate_set_hash"],
    )


def _concept_from_blocks(base: GenericBoxConcept, blocks: tuple[Any, ...]) -> GenericBoxConcept:
    return GenericBoxConcept(base.id, base.label, blocks, dict(base.render))


class SelectedCandidateRedesignSession:
    """A provider-neutral session rooted at one explicitly selected candidate."""

    def __init__(
        self,
        composition: CandidateCompositionResult | Mapping[str, Any],
        candidate_id: str,
        palette: Mapping[str, Any] | str | PathLike[str],
    ) -> None:
        source_result = _result(composition)
        self.selection_receipt = select_candidate(source_result, candidate_id)
        selected = next(item for item in source_result.candidates if item["id"] == candidate_id)
        family = self.selection_receipt["selected_family"]
        if family not in _BRIDGES:
            raise ValueError(f"unsupported selected family: {family!r}")
        self.candidate_set_hash = source_result.candidate_set_hash
        self.selected_candidate_id = candidate_id
        self.selected_model_id = self.selection_receipt["selected_model_id"]
        self.selected_family = family
        self.request_text = source_result.request_text
        self.palette = (
            copy.deepcopy(palette)
            if isinstance(palette, Mapping)
            else load_palette(palette)
        )
        self.source_concept = _concept_from_dict(selected["source_concept"])
        self.redesign = ConceptRedesignSession(self.source_concept, self.request_text)
        self.bridge_evidence = copy.deepcopy(selected.get("bridge"))
        self.compiled_ldr = self._compiled_from_bridge(self.bridge_evidence)
        self._bridge_undo: list[dict[str, Any]] = []

    @classmethod
    def from_candidate_composition(
        cls, composition: CandidateCompositionResult | Mapping[str, Any], candidate_id: str,
        palette: Mapping[str, Any] | str | PathLike[str],
    ) -> "SelectedCandidateRedesignSession":
        return cls(composition, candidate_id, palette)

    @property
    def blocks(self):
        return self.redesign.blocks

    @property
    def accepted_concept(self):
        return self.redesign.accepted_concept

    @property
    def focus(self):
        return self.redesign.focus

    @property
    def locked_ids(self):
        return self.redesign.locked_ids

    @property
    def proposal(self):
        return self.redesign.local.proposal

    def set_focus(self, point, radius=None, *, block_id=None):
        return self.redesign.set_focus(point, radius, block_id=block_id)

    def set_radius(self, radius):
        return self.redesign.local.set_radius(radius)

    def lock_selected(self):
        return self.redesign.lock_selected()

    def toggle_lock(self, block_id: str):
        return self.redesign.toggle_lock(block_id)

    def unlock_all(self):
        return self.redesign.local.unlock_all()

    def propose(self, instruction: str):
        return self.redesign.propose(instruction)

    def retry(self, instruction: str | None = None):
        return self.redesign.retry(instruction)

    def accept(self) -> dict[str, Any]:
        proposal = self.redesign.local.proposal
        if proposal is None:
            raise ValueError("there is no proposal to accept")
        proposed = _concept_from_blocks(self.redesign.starting_concept, proposal.after)
        bridge = _BRIDGES[self.selected_family](proposed, self.palette)
        evidence = bridge.snapshot()
        if not bridge.success:
            rejection = {
                "status": "rejected", "success": False,
                "diagnostics": list(bridge.diagnostics), "bridge": evidence,
                "action": "adjust the proposal or retry; the accepted concept and proposal remain available",
            }
            self.redesign.evidence.append({"operation": "reject", "bridge": copy.deepcopy(evidence)})
            return rejection

        self._bridge_undo.append({
            "accepted_concept": self.redesign.accepted_concept.to_dict(),
            "bridge": copy.deepcopy(self.bridge_evidence),
            "compiled_ldr": self.compiled_ldr,
        })
        self.redesign.accept()
        self.bridge_evidence = evidence
        self.compiled_ldr = bridge.compiled_ldr
        self.redesign.evidence[-1]["bridge"] = copy.deepcopy(evidence)
        return {
            "status": "success", "success": True,
            "accepted_concept": self.accepted_concept.to_dict(),
            "bridge": copy.deepcopy(evidence), "compiled_ldr": bridge.compiled_ldr,
        }

    def undo(self):
        concept = self.redesign.undo()
        if self._bridge_undo:
            previous = self._bridge_undo.pop()
            self.bridge_evidence = previous["bridge"]
            self.compiled_ldr = previous["compiled_ldr"]
            self.redesign.accepted_concept = _concept_from_dict(previous["accepted_concept"])
        return concept

    def snapshot(self) -> dict[str, Any]:
        return {
            "format": FORMAT,
            "request_text": self.request_text,
            "candidate_set_hash": self.candidate_set_hash,
            "selection_receipt": copy.deepcopy(self.selection_receipt),
            "selected_candidate_id": self.selected_candidate_id,
            "selected_model_id": self.selected_model_id,
            "selected_family": self.selected_family,
            "source_concept": self.source_concept.to_dict(),
            "palette": copy.deepcopy(self.palette),
            "redesign": self.redesign.snapshot(),
            "bridge_evidence": copy.deepcopy(self.bridge_evidence),
            "compiled_ldr": self.compiled_ldr,
            "bridge_undo": copy.deepcopy(self._bridge_undo),
        }

    def serialize(self) -> str:
        return _canonical(self.snapshot())

    @classmethod
    def from_serialized(cls, payload: str | Mapping[str, Any]) -> "SelectedCandidateRedesignSession":
        value = json.loads(payload) if isinstance(payload, str) else payload
        if not isinstance(value, Mapping) or value.get("format") != FORMAT:
            raise ValueError("unsupported selected-candidate-redesign state format")
        session = cls.__new__(cls)
        session.request_text = value["request_text"]
        session.candidate_set_hash = value["candidate_set_hash"]
        session.selection_receipt = copy.deepcopy(value["selection_receipt"])
        session.selected_candidate_id = value["selected_candidate_id"]
        session.selected_model_id = value["selected_model_id"]
        session.selected_family = value["selected_family"]
        if session.selected_family not in _BRIDGES:
            raise ValueError("unknown selected family")
        session.palette = copy.deepcopy(value["palette"])
        session.source_concept = _concept_from_dict(value["source_concept"])
        session.redesign = ConceptRedesignSession.from_serialized(value["redesign"])
        session.bridge_evidence = copy.deepcopy(value.get("bridge_evidence"))
        session.compiled_ldr = value.get("compiled_ldr")
        session._bridge_undo = copy.deepcopy(value.get("bridge_undo", []))
        return session

    @staticmethod
    def _compiled_from_bridge(bridge: Mapping[str, Any] | None) -> str | None:
        assembly = bridge.get("assembly") if isinstance(bridge, Mapping) else None
        return assembly.get("compiled_ldr") if isinstance(assembly, Mapping) else None
