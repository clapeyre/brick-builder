"""Disposable local-redesign interaction probe for Milestone 3A.

This module deliberately does not use the canonical LEGO model document.  It
models a small blockout as inspectable boxes and provides a deterministic,
canned edit loop that is useful for trying the interaction before choosing a
production spatial representation.

The :class:`LocalRedesignSession` is the testable core.  ``python -m
brick_builder.local_redesign`` opens the optional Tk UI when a desktop Python
installation is available.
"""

from __future__ import annotations

import copy
import math
from dataclasses import dataclass, replace
from typing import Iterable

try:  # Tk is optional: the deterministic session remains usable headlessly.
    import tkinter as tk
    from tkinter import ttk
except ImportError:  # pragma: no cover - depends on the Python distribution.
    tk = None  # type: ignore[assignment]
    ttk = None  # type: ignore[assignment]


Vector3 = tuple[float, float, float]


def _vector(value: Iterable[float]) -> Vector3:
    values = tuple(float(item) for item in value)
    if len(values) != 3:
        raise ValueError("a 3D vector must contain exactly three values")
    return values  # type: ignore[return-value]


@dataclass(frozen=True)
class Block:
    """One generic box in the disposable spatial blockout."""

    id: str
    center: Vector3
    size: Vector3
    color: str

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("block id must not be empty")
        if any(value <= 0 for value in self.size):
            raise ValueError("block size must be positive")

    def moved(
        self,
        *,
        center: Iterable[float] | None = None,
        size: Iterable[float] | None = None,
        color: str | None = None,
    ) -> "Block":
        return replace(
            self,
            center=_vector(center) if center is not None else self.center,
            size=_vector(size) if size is not None else self.size,
            color=color if color is not None else self.color,
        )


@dataclass(frozen=True)
class Focus:
    point: Vector3
    radius: float

    def __post_init__(self) -> None:
        if self.radius <= 0:
            raise ValueError("focus radius must be positive")


@dataclass(frozen=True)
class EditProposal:
    """A fully inspectable before/after local edit, not a production schema."""

    instruction: str
    before: tuple[Block, ...]
    after: tuple[Block, ...]
    changed_ids: tuple[str, ...]
    selected_ids: tuple[str, ...]
    spillover_ids: tuple[str, ...]
    protected_ids: tuple[str, ...]
    locked_ids: tuple[str, ...]
    expansion_limit: float
    retry_number: int

    @property
    def contract(self) -> dict:
        """Return a JSON-friendly edit record for inspection and replay."""
        return {
            "selection": {
                "point": list(self._focus_point),
                "radius": self._focus_radius,
                "block_ids": list(self.selected_ids),
            },
            "instruction": self.instruction,
            "protected": list(self.protected_ids),
            "locked": list(self.locked_ids),
            "boundary": ["generic box attachment boundary"],
            "invariants": [
                "protected blocks remain identical",
                "locked blocks remain identical",
            ],
            "expansion_limit": {"world_units": self.expansion_limit},
            "before": [
                block_to_dict(block)
                for block in self.before
                if block.id in self.changed_ids
            ],
            "after": [
                block_to_dict(block)
                for block in self.after
                if block.id in self.changed_ids
            ],
            "changed_ids": list(self.changed_ids),
            "spillover_ids": list(self.spillover_ids),
            "result": "proposed",
            "retry_number": self.retry_number,
        }

    # Focus is stored privately on the proposal only to make a standalone
    # contract useful.  ``propose`` fills these fields through object.__setattr__
    # after construction; they are intentionally not part of the exploratory
    # data shape returned by ``contract``.
    _focus_point: Vector3 = (0.0, 0.0, 0.0)
    _focus_radius: float = 0.0


@dataclass(frozen=True)
class _Snapshot:
    blocks: tuple[Block, ...]
    focus: Focus
    locked_ids: frozenset[str]
    yaw: float
    pitch: float


def block_to_dict(block: Block) -> dict:
    return {
        "id": block.id,
        "center": list(block.center),
        "size": list(block.size),
        "color": block.color,
    }


def make_blocky_boat() -> tuple[Block, ...]:
    """Return a deliberately crude, generic-box boat blockout."""
    # The IDs are stable geometry references, not semantic part ontology.
    return (
        Block("block-01", (0, 0, 0), (8, 2, 4), "#2878b5"),
        Block("block-02", (-4, 1.5, 0), (2, 1, 4), "#3f9bd3"),
        Block("block-03", (4, 1.5, 0), (2, 1, 4), "#3f9bd3"),
        Block("block-04", (0, 2.0, 0), (6, 1, 2), "#f0c75e"),
        Block("block-05", (-2.8, 2.8, 0), (1.4, 1.4, 1.4), "#e85d5d"),
        Block("block-06", (0, 2.8, 0), (1.4, 1.4, 1.4), "#e85d5d"),
        Block("block-07", (2.8, 2.8, 0), (1.4, 1.4, 1.4), "#e85d5d"),
        Block("block-08", (0, 4.2, 0), (1.2, 2.2, 1.2), "#f7f7f2"),
    )


class LocalRedesignSession:
    """State machine for focus, locks, canned proposals, and exact undo."""

    def __init__(self, blocks: Iterable[Block] | None = None) -> None:
        initial = tuple(blocks if blocks is not None else make_blocky_boat())
        if not initial:
            raise ValueError("a blockout must contain at least one block")
        if len({block.id for block in initial}) != len(initial):
            raise ValueError("block ids must be unique")
        self.blocks: tuple[Block, ...] = initial
        self.focus = Focus((0.0, 0.0, 0.0), 3.0)
        self.locked_ids: set[str] = set()
        self.yaw = -25.0
        self.pitch = 20.0
        self.proposal: EditProposal | None = None
        self._undo: list[_Snapshot] = []
        self._retry_number = 0

    @property
    def selected_ids(self) -> tuple[str, ...]:
        return tuple(
            block.id
            for block in self.blocks
            if self._distance(block.center, self.focus.point) <= self.focus.radius
        )

    def set_focus(self, point: Iterable[float], radius: float | None = None) -> Focus:
        self.focus = Focus(_vector(point), self.focus.radius if radius is None else float(radius))
        self._invalidate_proposal()
        return self.focus

    def set_radius(self, radius: float) -> Focus:
        return self.set_focus(self.focus.point, radius)

    def rotate(self, yaw_delta: float = 0.0, pitch_delta: float = 0.0) -> tuple[float, float]:
        self.yaw = (self.yaw + float(yaw_delta)) % 360.0
        self.pitch = max(-75.0, min(75.0, self.pitch + float(pitch_delta)))
        return self.yaw, self.pitch

    def toggle_lock(self, block_id: str) -> bool:
        self._require_block(block_id)
        if block_id in self.locked_ids:
            self.locked_ids.remove(block_id)
            locked = False
        else:
            self.locked_ids.add(block_id)
            locked = True
        self._invalidate_proposal()
        return locked

    def lock_selected(self) -> tuple[str, ...]:
        self.locked_ids.update(self.selected_ids)
        self._invalidate_proposal()
        return tuple(sorted(self.locked_ids))

    def unlock_all(self) -> None:
        self.locked_ids.clear()
        self._invalidate_proposal()

    def propose(self, instruction: str) -> EditProposal:
        """Make a deterministic canned local edit, including one spillover box."""
        instruction = instruction.strip()
        if not instruction:
            raise ValueError("describe the local change first")
        selected = set(self.selected_ids)
        if not selected:
            raise ValueError("click a block to place the focus before proposing a redesign")

        by_id = {block.id: block for block in self.blocks}
        # A nearby box just outside the radius demonstrates that focus is
        # guidance and makes spillover visible.  It is never chosen if locked.
        nearby = sorted(
            (
                block
                for block in self.blocks
                if block.id not in selected and block.id not in self.locked_ids
            ),
            key=lambda block: self._distance(block.center, self.focus.point),
        )
        spillover: set[str] = set()
        if nearby and self._distance(nearby[0].center, self.focus.point) <= self.focus.radius + 2.5:
            spillover.add(nearby[0].id)
        affected = selected | spillover
        changed: dict[str, Block] = {}
        retry_offset = self._retry_number * 0.25
        lower = instruction.lower()
        for block_id in sorted(affected):
            block = by_id[block_id]
            if block_id in self.locked_ids:
                continue
            # The words alter the canned shape slightly; this is intentionally
            # a simulation, not language understanding or an LLM call.
            if any(word in lower for word in ("tall", "high", "tower")):
                size = (block.size[0], block.size[1] + 0.8 + retry_offset, block.size[2])
            elif any(word in lower for word in ("wide", "broad")):
                size = (block.size[0] + 0.8 + retry_offset, block.size[1], block.size[2])
            elif any(word in lower for word in ("stripe", "colour", "color", "bright", "red")):
                size = block.size
            else:
                size = (block.size[0], block.size[1] + 0.45 + retry_offset, block.size[2])
            color = "#f5a623" if block.color != "#f5a623" else "#8dd35f"
            if any(word in lower for word in ("blue", "water")):
                color = "#2878b5"
            changed[block_id] = block.moved(size=size, color=color)

        after = tuple(changed.get(block.id, block) for block in self.blocks)
        changed_ids = tuple(
            block.id
            for block, replacement in zip(self.blocks, after)
            if block != replacement
        )
        # A proposal which targets only locked blocks is useful feedback and
        # must never silently alter an unlocked block.
        spillover_ids = tuple(
            block_id for block_id in sorted(spillover) if block_id in changed_ids
        )
        protected_ids = tuple(block.id for block in self.blocks if block.id not in changed_ids)
        proposal = EditProposal(
            instruction=instruction,
            before=copy.deepcopy(self.blocks),
            after=after,
            changed_ids=changed_ids,
            selected_ids=tuple(sorted(selected)),
            spillover_ids=spillover_ids,
            protected_ids=protected_ids,
            locked_ids=tuple(sorted(self.locked_ids)),
            expansion_limit=2.5,
            retry_number=self._retry_number,
        )
        object.__setattr__(proposal, "_focus_point", self.focus.point)
        object.__setattr__(proposal, "_focus_radius", self.focus.radius)
        self.proposal = proposal
        return proposal

    def retry(self, instruction: str | None = None) -> EditProposal:
        """Generate another canned proposal without changing focus or locks."""
        if self.proposal is None and instruction is None:
            raise ValueError("make an initial proposal before retrying")
        request = instruction if instruction is not None else self.proposal.instruction
        self._retry_number += 1
        return self.propose(request)

    def accept(self) -> tuple[Block, ...]:
        if self.proposal is None:
            raise ValueError("there is no proposal to accept")
        self._undo.append(_Snapshot(self.blocks, self.focus, frozenset(self.locked_ids), self.yaw, self.pitch))
        self.blocks = copy.deepcopy(self.proposal.after)
        self.proposal = None
        self._retry_number = 0
        return self.blocks

    def undo(self) -> tuple[Block, ...]:
        if not self._undo:
            raise ValueError("nothing to undo")
        snapshot = self._undo.pop()
        self.blocks = copy.deepcopy(snapshot.blocks)
        self.focus = snapshot.focus
        self.locked_ids = set(snapshot.locked_ids)
        self.yaw = snapshot.yaw
        self.pitch = snapshot.pitch
        self.proposal = None
        self._retry_number = 0
        return self.blocks

    def snapshot(self) -> dict:
        """Return a deep, JSON-friendly state snapshot for interaction evidence."""
        return {
            "blocks": [block_to_dict(block) for block in self.blocks],
            "focus": {"point": list(self.focus.point), "radius": self.focus.radius},
            "locked_ids": sorted(self.locked_ids),
            "camera": {"yaw": self.yaw, "pitch": self.pitch},
            "proposal": self.proposal.contract if self.proposal else None,
        }

    def _require_block(self, block_id: str) -> None:
        if block_id not in {block.id for block in self.blocks}:
            raise KeyError(f"unknown block id: {block_id}")

    def _invalidate_proposal(self) -> None:
        self.proposal = None
        self._retry_number = 0

    @staticmethod
    def _distance(left: Vector3, right: Vector3) -> float:
        return math.sqrt(sum((a - b) ** 2 for a, b in zip(left, right)))


class LocalRedesignApp:
    """Small Tk canvas UI for trying the session with a mouse."""

    def __init__(self, root: tk.Tk | None = None) -> None:
        if tk is None or ttk is None:
            raise RuntimeError("the local prototype UI requires a Python build with tkinter")
        self.root = root or tk.Tk()
        self.root.title("Brick Builder — local redesign prototype")
        self.session = LocalRedesignSession()
        self._drag_start: tuple[int, int] | None = None
        self._status = tk.StringVar(value="Exploration: click a block to place the focus.")
        self._radius = tk.DoubleVar(value=self.session.focus.radius)
        self._request = tk.StringVar(value="make this area taller and friendlier")
        self._build()
        self._draw()

    def _build(self) -> None:
        toolbar = ttk.Frame(self.root, padding=8)
        toolbar.pack(fill="x")
        ttk.Label(toolbar, text="Local request").pack(side="left")
        ttk.Entry(toolbar, textvariable=self._request, width=38).pack(side="left", padx=(6, 12))
        ttk.Button(toolbar, text="Propose", command=self._propose).pack(side="left")
        ttk.Button(toolbar, text="Retry", command=self._retry).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Accept", command=self._accept).pack(side="left")
        ttk.Button(toolbar, text="Undo", command=self._undo).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Lock selected", command=self._lock).pack(side="left")

        controls = ttk.Frame(self.root, padding=(8, 0, 8, 8))
        controls.pack(fill="x")
        ttk.Label(controls, text="Focus radius").pack(side="left")
        ttk.Scale(
            controls,
            from_=1,
            to=8,
            variable=self._radius,
            command=self._radius_changed,
        ).pack(side="left", fill="x", expand=True, padx=8)
        ttk.Button(
            controls, text="Rotate left", command=lambda: self._rotate(-12, 0)
        ).pack(side="left")
        ttk.Button(
            controls, text="Rotate right", command=lambda: self._rotate(12, 0)
        ).pack(side="left", padx=4)
        ttk.Button(controls, text="Tilt", command=lambda: self._rotate(0, 8)).pack(side="left")
        ttk.Button(controls, text="Unlock all", command=self._unlock).pack(side="left", padx=(4, 0))

        legend = ttk.Label(
            self.root,
            text="Focus/selected: blue  |  Locked: purple  |  Changed: orange  |  Spillover: dashed orange",
            padding=(8, 0, 8, 6),
        )
        legend.pack(fill="x")

        comparison = ttk.Frame(self.root)
        comparison.pack(fill="both", expand=True)
        canvas_options = {
            "width": 430,
            "height": 360,
            "background": "#f6f7fb",
            "highlightthickness": 1,
            "highlightbackground": "#c4c9d4",
        }
        self.before = tk.Canvas(comparison, **canvas_options)
        self.after = tk.Canvas(comparison, **canvas_options)
        self.before.pack(side="left", fill="both", expand=True, padx=(8, 4), pady=4)
        self.after.pack(side="left", fill="both", expand=True, padx=(4, 8), pady=4)
        self.before.bind("<Button-1>", self._focus_click)
        self.after.bind("<Button-1>", self._focus_click)
        self.before.bind("<ButtonPress-3>", self._rotate_start)
        self.before.bind("<B3-Motion>", self._rotate_drag)
        self.after.bind("<ButtonPress-3>", self._rotate_start)
        self.after.bind("<B3-Motion>", self._rotate_drag)
        ttk.Label(self.root, textvariable=self._status, padding=8).pack(fill="x")

    def _project(self, point: Vector3, width: int = 430, height: int = 360) -> tuple[float, float]:
        yaw = math.radians(self.session.yaw)
        pitch = math.radians(self.session.pitch)
        x, y, z = point
        xr = x * math.cos(yaw) - z * math.sin(yaw)
        zr = x * math.sin(yaw) + z * math.cos(yaw)
        yr = y * math.cos(pitch) - zr * math.sin(pitch)
        return width / 2 + xr * 24, height / 2 - yr * 24

    def _draw(self) -> None:
        for canvas in (self.before, self.after):
            canvas.delete("all")
        proposal = self.session.proposal
        self._draw_scene(self.before, self.session.blocks, proposal, is_after=False)
        self._draw_scene(self.after, proposal.after if proposal else self.session.blocks, proposal, is_after=True)
        self.before.create_text(
            12,
            12,
            text="BEFORE — persistent concept",
            anchor="nw",
            fill="#273142",
            font=("Segoe UI", 11, "bold"),
        )
        self.after.create_text(
            12,
            12,
            text="AFTER — proposed local redesign",
            anchor="nw",
            fill="#273142",
            font=("Segoe UI", 11, "bold"),
        )
        if proposal:
            changed = ", ".join(proposal.changed_ids) or "none"
            spill = ", ".join(proposal.spillover_ids) or "none"
            self._status.set(
                f"Review — changed: {changed}. "
                f"Spillover outside focus: {spill}. Locks preserved."
            )
        else:
            point = tuple(round(value, 1) for value in self.session.focus.point)
            self._status.set(
                f"Selection: focus {point}, radius {self.session.focus.radius:.1f}. "
                "Right-drag to rotate."
            )

    def _draw_scene(
        self,
        canvas: tk.Canvas,
        blocks: tuple[Block, ...],
        proposal: EditProposal | None,
        *,
        is_after: bool,
    ) -> None:
        changed = set(proposal.changed_ids) if proposal else set()
        selected = set(self.session.selected_ids)
        for block in blocks:
            cx, cy = self._project(block.center)
            sx, sy = block.size[0] * 12, block.size[1] * 12
            # A simple isometric-ish box; the z extent adds a visible depth cue.
            depth = block.size[2] * 7
            polygon = [
                cx - sx,
                cy - sy,
                cx + sx,
                cy - sy,
                cx + sx + depth,
                cy - sy - depth / 2,
                cx - sx + depth,
                cy - sy - depth / 2,
            ]
            outline = "#26354a"
            width = 1
            dash = None
            if block.id in selected:
                outline, width = "#1677ff", 3
            if block.id in self.session.locked_ids:
                outline, width = "#7a3db8", 3
            if block.id in changed:
                outline, width = ("#de5b22" if is_after else "#8f9aa8"), 3
                spillover = set(proposal.spillover_ids) if proposal else set()
                dash = (6, 3) if block.id in spillover else None
            canvas.create_polygon(*polygon, fill=block.color, outline=outline, width=width, dash=dash)
            canvas.create_text(cx, cy - sy - 7, text=block.id, fill="#1d2735", font=("Segoe UI", 8))
        px, py = self._project(self.session.focus.point)
        radius = self.session.focus.radius * 24
        canvas.create_oval(
            px - radius,
            py - radius,
            px + radius,
            py + radius,
            outline="#1677ff",
            dash=(3, 3),
            width=2,
        )
        canvas.create_oval(px - 4, py - 4, px + 4, py + 4, fill="#1677ff", outline="white", width=1)

    def _find_block(self, event: tk.Event) -> Block | None:
        return min(
            self.session.blocks,
            key=lambda block: (
                (self._project(block.center)[0] - event.x) ** 2
                + (self._project(block.center)[1] - event.y) ** 2
            ),
        )

    def _focus_click(self, event: tk.Event) -> None:
        block = self._find_block(event)
        if block:
            self.session.set_focus(block.center)
            self._draw()

    def _radius_changed(self, value: str) -> None:
        self.session.set_radius(float(value))
        self._draw()

    def _rotate(self, yaw: float, pitch: float) -> None:
        self.session.rotate(yaw, pitch)
        self._draw()

    def _rotate_start(self, event: tk.Event) -> None:
        self._drag_start = (event.x, event.y)

    def _rotate_drag(self, event: tk.Event) -> None:
        if self._drag_start:
            old_x, old_y = self._drag_start
            self.session.rotate((event.x - old_x) * 0.7, (event.y - old_y) * 0.4)
            self._drag_start = (event.x, event.y)
            self._draw()

    def _propose(self) -> None:
        try:
            self.session.propose(self._request.get())
            self._draw()
        except ValueError as exc:
            self._status.set(str(exc))

    def _retry(self) -> None:
        try:
            self.session.retry()
            self._draw()
        except ValueError as exc:
            self._status.set(str(exc))

    def _accept(self) -> None:
        try:
            self.session.accept()
            self._draw()
        except ValueError as exc:
            self._status.set(str(exc))

    def _undo(self) -> None:
        try:
            self.session.undo()
            self._draw()
        except ValueError as exc:
            self._status.set(str(exc))

    def _lock(self) -> None:
        self.session.lock_selected()
        self._draw()

    def _unlock(self) -> None:
        self.session.unlock_all()
        self._draw()


def main() -> None:
    """Launch the disposable local-redesign interaction prototype."""
    if tk is None:
        raise SystemExit("the local prototype UI requires a Python build with tkinter")
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        raise SystemExit(
            "the local prototype UI requires a Python installation with working "
            f"Tcl/Tk support: {exc}"
        ) from exc
    LocalRedesignApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
