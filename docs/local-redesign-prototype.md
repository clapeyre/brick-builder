# Disposable local-redesign prototype

This is the Milestone 3A interaction probe. It uses a crude blocky boat made
from generic boxes; it is deliberately separate from the canonical LEGO model
schema and does not claim physical buildability.

From the repository root, run:

```powershell
python -m brick_builder.local_redesign
```

The chosen Python installation must include working Tcl/Tk support. The
headless session tests do not require Tcl/Tk.

Click a box to place the focus, adjust the radius, and use the request field to
describe a local change. The canned proposal is shown in the `AFTER` canvas;
changed boxes use an orange outline and any change just outside the focus uses
a dashed orange outline and is listed as spillover. The legend identifies
selected geometry in blue and hard locks in purple; the review status names
every changed block. Right-drag either canvas to
rotate the blockout. `Lock selected` makes the currently focused boxes hard
constraints. `Retry` keeps focus and locks, `Accept` applies the proposal, and
`Undo` restores the exact pre-accept concept.

The deterministic state machine can be exercised without opening a window:

```powershell
python -m unittest tests.test_local_redesign -v
```

This experiment intentionally has no live model call, LEGOization, Pi or
Hermes integration, Studio automation, purchasing, publishing, or semantic
parts ontology.
