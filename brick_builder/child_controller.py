"""Minimal headless controller for the offline child-facing creative loop."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from os import PathLike
from typing import Any, Mapping, Sequence

from .candidate_composition import CandidateCompositionResult, compose_candidate_set, select_candidate
from .candidate_rendering import render_candidate_set
from .selected_candidate_redesign import SelectedCandidateRedesignSession
from .spatial_concept import GenericBoxConcept
from .visual_critique import critique_candidate_set


FORMAT = "brick-builder.child-controller/v1"


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(value, str):
        path.write_text(value, encoding="utf-8", newline="\n")
    else:
        path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


def _next_run(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    index = 1
    while True:
        candidate = root / f"generation-{index:03d}"
        if not candidate.exists():
            return candidate
        index += 1


class ChildController:
    """Offline, non-Tk state machine around the existing candidate contracts.

    It deliberately accepts already validated ``GenericBoxConcept`` objects;
    natural-language interpretation remains outside this deterministic layer.
    """

    def __init__(self, run_root: str | PathLike[str], palette: Mapping[str, Any] | str | PathLike[str]) -> None:
        self.run_root = Path(run_root).expanduser().resolve()
        self.palette = copy.deepcopy(palette) if isinstance(palette, Mapping) else Path(palette).expanduser().resolve()
        self.generation_run: Path | None = None
        self.composition: CandidateCompositionResult | None = None
        self.rendering: dict[str, Any] | None = None
        self.critique: dict[str, Any] | None = None
        self.session: SelectedCandidateRedesignSession | None = None
        self.selection_receipt: dict[str, Any] | None = None
        self.selection_receipt_hash: str | None = None
        self._proposal_state = "none"
        self._last_operation: str | None = None
        self._last_result: dict[str, Any] | None = None

    @property
    def generated(self) -> bool:
        return self.composition is not None and self.composition.success and self.generation_run is not None

    @property
    def candidate_cards(self) -> tuple[dict[str, Any], ...]:
        if not self.generated or self.composition is None:
            return ()
        critique_by_id = {item["id"]: item for item in (self.critique or {}).get("candidates", [])}
        cards = []
        for candidate in self.composition.candidates:
            cards.append({
                "id": candidate["id"],
                "label": candidate["source_concept"].get("label", candidate["id"]),
                "family": candidate.get("family"),
                "status": candidate.get("status"),
                "model_id": candidate.get("model_id"),
                "render_evidence": (self.rendering or {}).get("candidates", []),
                "critique": critique_by_id.get(candidate["id"]),
            })
        # Preserve composition input order; no score, rank, or winner is added.
        for card in cards:
            card["render_evidence"] = next(
                (item.get("render_evidence") for item in (self.rendering or {}).get("candidates", []) if item.get("id") == card["id"]),
                None,
            )
        return tuple(cards)

    def create_candidate_set(self, request_text: str, concepts: Sequence[GenericBoxConcept]) -> dict[str, Any]:
        """Compose, render, critique, and persist one fresh contained run."""
        result = compose_candidate_set(request_text, concepts, self.palette)
        run = _next_run(self.run_root)
        snapshot = result.snapshot()
        _write(run / "candidate-set.json", snapshot)
        for index, candidate in enumerate(result.candidates, start=1):
            candidate_id = candidate.get("id") if isinstance(candidate.get("id"), str) else f"candidate-{index:02d}"
            child = run / "candidates" / candidate_id
            _write(child / "bridge.json", candidate)
            bridge = candidate.get("bridge")
            assembly = bridge.get("assembly") if isinstance(bridge, Mapping) else None
            compiled = assembly.get("compiled_ldr") if isinstance(assembly, Mapping) else None
            if candidate.get("status") == "success" and isinstance(compiled, str):
                _write(child / "final.ldr", compiled)
        rendering = render_candidate_set(snapshot, run, self.palette)
        _write(run / "candidate-rendering.json", rendering)
        critique_snapshot = None
        if result.success:
            critique_snapshot = critique_candidate_set(rendering).snapshot()
            _write(run / "visual-critique.json", critique_snapshot)
        self.generation_run, self.composition = run, result
        self.rendering, self.critique = rendering, critique_snapshot
        self.session = None
        self.selection_receipt = None
        self.selection_receipt_hash = None
        self._proposal_state, self._last_operation, self._last_result = "none", "generate", None
        return self.snapshot()

    generate = create_candidate_set

    def select(self, candidate_id: str) -> dict[str, Any]:
        if not self.generated or self.composition is None or self.generation_run is None:
            raise ValueError("generate a successful candidate set before selecting a candidate")
        receipt = select_candidate(self.composition, candidate_id)
        self.session = SelectedCandidateRedesignSession(self.composition, candidate_id, self.palette)
        self.selection_receipt = receipt
        self.selection_receipt_hash = hashlib.sha256(_canonical(receipt).encode("utf-8")).hexdigest()
        selection_dir = self.generation_run / "selection"
        _write(selection_dir / "selection.json", {**receipt, "selection_receipt_hash": self.selection_receipt_hash})
        self._persist_session()
        self._proposal_state, self._last_operation, self._last_result = "none", "select", None
        return copy.deepcopy(receipt)

    def _require_session(self) -> SelectedCandidateRedesignSession:
        if self.session is None:
            raise ValueError("select a candidate before editing")
        return self.session

    def _persist_session(self) -> None:
        if self.session is None or self.generation_run is None:
            return
        directory = self.generation_run / "selection"
        _write(directory / "selected-candidate-redesign.json", self.session.serialize())
        _write(directory / "selected-candidate-bridge.json", self.session.bridge_evidence or {})
        if isinstance(self.session.compiled_ldr, str):
            _write(directory / "selected-final.ldr", self.session.compiled_ldr)

    def focus(self, point: Any, radius: float | None = None, *, block_id: str | None = None) -> Any:
        result = self._require_session().set_focus(point, radius, block_id=block_id)
        self._proposal_state, self._last_operation = "none", "focus"
        self._persist_session()
        return result

    set_focus = focus

    def lock(self) -> tuple[str, ...]:
        result = self._require_session().lock_selected()
        self._proposal_state, self._last_operation = "none", "lock"
        self._persist_session()
        return result

    lock_selected = lock

    def toggle_lock(self, block_id: str) -> bool:
        result = self._require_session().toggle_lock(block_id)
        self._proposal_state, self._last_operation = "none", "toggle-lock"
        self._persist_session()
        return result

    def set_radius(self, radius: float) -> Any:
        result = self._require_session().set_radius(radius)
        self._proposal_state, self._last_operation = "none", "radius"
        self._persist_session()
        return result

    def unlock_all(self) -> None:
        self._require_session().unlock_all()
        self._proposal_state, self._last_operation = "none", "unlock-all"
        self._persist_session()

    def propose(self, instruction: str) -> dict[str, Any]:
        result = self._require_session().propose(instruction)
        self._proposal_state, self._last_operation, self._last_result = "proposed", "propose", copy.deepcopy(result)
        self._persist_session()
        return result

    def retry(self, instruction: str | None = None) -> dict[str, Any]:
        result = self._require_session().retry(instruction)
        self._proposal_state, self._last_operation, self._last_result = "proposed", "retry", copy.deepcopy(result)
        self._persist_session()
        return result

    def accept(self) -> dict[str, Any]:
        result = self._require_session().accept()
        self._proposal_state = "accepted" if result.get("success") else "rejected"
        self._last_operation, self._last_result = "accept", copy.deepcopy(result)
        self._persist_session()
        return result

    def undo(self) -> Any:
        result = self._require_session().undo()
        self._proposal_state, self._last_operation, self._last_result = "undone", "undo", None
        self._persist_session()
        return result

    def restart(self) -> None:
        """Clear active interaction references while retaining generation evidence."""
        self.session = None
        self.selection_receipt = None
        self.selection_receipt_hash = None
        self._proposal_state, self._last_operation, self._last_result = "none", "restart", None

    def snapshot(self) -> dict[str, Any]:
        return {
            "format": FORMAT,
            "generated": self.generated,
            "generation_run": str(self.generation_run) if self.generation_run else None,
            "candidate_set_hash": self.composition.candidate_set_hash if self.composition else None,
            "selection_enabled": self.generated,
            "candidate_cards": [copy.deepcopy(card) for card in self.candidate_cards],
            "selection_receipt": copy.deepcopy(self.selection_receipt),
            "selection_receipt_hash": self.selection_receipt_hash,
            "selected_candidate_id": self.session.selected_candidate_id if self.session else None,
            "proposal_status": self._proposal_state,
            "proposal": copy.deepcopy(self._last_result) if self._proposal_state in {"proposed", "rejected"} else None,
            "last_operation": self._last_operation,
            "last_result": copy.deepcopy(self._last_result),
            "redesign": self.session.snapshot() if self.session else None,
        }


ChildFacingController = ChildController
