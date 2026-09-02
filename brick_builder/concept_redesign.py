"""Provider-neutral bridge from an accepted spatial concept to local redesign.

This is deliberately a thin composition layer.  Generic boxes, focus, locks,
and canned local proposals remain owned by the existing contracts; this module
records the accepted concept and the evidence needed to replay the interaction.
"""

from __future__ import annotations

import copy
import json
from typing import Any, Mapping

from .local_redesign import Block, LocalRedesignSession, block_from_dict
from .spatial_concept import GenericBoxConcept, SpatialConceptSession


FORMAT = "brick-builder.concept-redesign/v1"


def _concept_from_dict(value: Mapping[str, Any]) -> GenericBoxConcept:
    geometry = value.get("geometry")
    if not isinstance(geometry, list) or not isinstance(value.get("id"), str):
        raise ValueError("accepted concept must contain an id and geometry")
    try:
        boxes = tuple(
            block_from_dict({"id": item["ref"], "center": item["center"], "size": item["size"], "color": item["color"]})
            for item in geometry
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("accepted concept geometry is invalid") from exc
    refs = [block.id for block in boxes]
    render = value.get("render")
    if not isinstance(render, dict) or render.get("geometry_refs") != refs:
        raise ValueError("accepted concept render references do not match geometry")
    label = value.get("label")
    if not isinstance(label, str) or not label:
        raise ValueError("accepted concept label must be a non-empty string")
    return GenericBoxConcept(value["id"], label, boxes, dict(render))


class ConceptRedesignSession:
    """Replayable local-redesign session rooted at one accepted concept."""

    def __init__(self, concept: GenericBoxConcept, request_text: str = "") -> None:
        if not isinstance(concept, GenericBoxConcept):
            raise TypeError("concept must be a GenericBoxConcept")
        self.request_text = request_text
        self.accepted_concept = concept
        self.starting_concept = concept
        self.local = LocalRedesignSession(concept.boxes)
        camera = concept.render.get("camera")
        if camera in ("front", "side", "top", "three-quarter"):
            self.local.set_camera(camera)
        self.evidence: list[dict[str, Any]] = []
        self._undo_state: str | None = None

    @classmethod
    def from_spatial_session(
        cls, session: SpatialConceptSession, concept_id: str, request_text: str | None = None
    ) -> "ConceptRedesignSession":
        if session.status != "success":
            raise ValueError("spatial concept session has no accepted concepts")
        concept = next((item for item in session.concepts if item.id == concept_id), None)
        if concept is None:
            raise KeyError(f"unknown concept id: {concept_id}")
        return cls(concept, session.request_text if request_text is None else request_text)

    @property
    def blocks(self) -> tuple[Block, ...]:
        return self.local.blocks

    @property
    def focus(self):
        return self.local.focus

    @property
    def locked_ids(self) -> set[str]:
        return self.local.locked_ids

    def set_focus(self, point, radius=None, *, block_id=None):
        return self.local.set_focus(point, radius, block_id=block_id)

    def lock_selected(self):
        return self.local.lock_selected()

    def toggle_lock(self, block_id: str):
        return self.local.toggle_lock(block_id)

    def propose(self, instruction: str) -> dict[str, Any]:
        proposal = self.local.propose(instruction)
        self._assert_locked_unchanged(proposal.after)
        record = copy.deepcopy(proposal.contract)
        record["retry_number"] = proposal.retry_number
        self.evidence.append({"operation": "propose", "proposal": record})
        return record

    def retry(self, instruction: str | None = None) -> dict[str, Any]:
        focus, locks = self.local.focus, frozenset(self.local.locked_ids)
        proposal = self.local.retry(instruction)
        if self.local.focus != focus or frozenset(self.local.locked_ids) != locks:
            raise AssertionError("retry changed focus or locks")
        self._assert_locked_unchanged(proposal.after)
        record = copy.deepcopy(proposal.contract)
        record["retry_number"] = proposal.retry_number
        self.evidence.append({"operation": "retry", "proposal": record})
        return record

    def accept(self) -> GenericBoxConcept:
        self._undo_state = self.local.serialize()
        self.local.accept()
        self.accepted_concept = GenericBoxConcept(
            self.starting_concept.id,
            self.starting_concept.label,
            self.local.blocks,
            dict(self.starting_concept.render),
        )
        self.evidence.append({"operation": "accept", "concept": self.accepted_concept.to_dict()})
        return self.accepted_concept

    def undo(self) -> GenericBoxConcept:
        if self._undo_state is not None:
            self.local = LocalRedesignSession.from_serialized(self._undo_state)
            self._undo_state = None
        else:
            self.local.undo()
        self.accepted_concept = GenericBoxConcept(
            self.starting_concept.id,
            self.starting_concept.label,
            self.local.blocks,
            dict(self.starting_concept.render),
        )
        self.evidence.append({"operation": "undo", "concept": self.accepted_concept.to_dict()})
        return self.accepted_concept

    def snapshot(self) -> dict[str, Any]:
        return {
            "format": FORMAT,
            "request_text": self.request_text,
            "starting_concept": self.starting_concept.to_dict(),
            "accepted_concept": self.accepted_concept.to_dict(),
            "local_redesign": json.loads(self.local.serialize()),
            "undo_state": json.loads(self._undo_state) if self._undo_state is not None else None,
            "evidence": copy.deepcopy(self.evidence),
        }

    def serialize(self) -> str:
        return json.dumps(self.snapshot(), sort_keys=True, separators=(",", ":"), ensure_ascii=False)

    @classmethod
    def from_serialized(cls, payload: str | Mapping[str, Any]) -> "ConceptRedesignSession":
        value = json.loads(payload) if isinstance(payload, str) else payload
        if not isinstance(value, Mapping) or value.get("format") != FORMAT:
            raise ValueError("unsupported concept-redesign state format")
        starting = _concept_from_dict(value["starting_concept"])
        session = cls(starting, value.get("request_text", ""))
        session.local = LocalRedesignSession.from_serialized(value["local_redesign"])
        undo_state = value.get("undo_state")
        session._undo_state = json.dumps(undo_state, sort_keys=True, separators=(",", ":")) if undo_state is not None else None
        session.accepted_concept = _concept_from_dict(value["accepted_concept"])
        evidence = value.get("evidence", [])
        if not isinstance(evidence, list):
            raise ValueError("evidence must be a list")
        session.evidence = copy.deepcopy(evidence)
        return session

    def _assert_locked_unchanged(self, after: tuple[Block, ...]) -> None:
        before = {block.id: block for block in self.local.blocks}
        after_by_id = {block.id: block for block in after}
        for block_id in self.local.locked_ids:
            if after_by_id[block_id] != before[block_id]:
                raise AssertionError(f"locked box changed: {block_id}")
