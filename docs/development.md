# Developer quickstart

For a new Git worktree, first read [worktree-setup.md](worktree-setup.md).
Worktrees do not include ignored virtual environments or Node dependencies;
the guide gives the canonical bootstrap commands and the required wording for
setup, test, and execution-environment status.

Create an isolated environment (PowerShell):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
```

The deterministic slice uses Python and `unittest`; structural validation depends on the declared `jsonschema` package.

Run all tests from the repository root:

```powershell
python -m unittest discover -s tests -v
```

Compile a hand-authored reference model to LDraw:

```powershell
python -m brick_builder.cli examples/reference_models/tiny-red-wall.json out/tiny-red-wall.ldr
```

Compile the rotated one-stud Studio smoke test:

```powershell
python -m brick_builder.cli examples/reference_models/rotated-one-stud.json out/rotated-one-stud.ldr
```

Importing that file into Studio should show two perpendicular 1 x 2 bricks
in one connected group with no collision. Because the connection is a single
stud cantilever, treat stability feedback conservatively and inspect it in
Studio before building.

The default palette is packaged at `brick_builder/palettes/classic-core-v0.json`; use `--palette`
to select another versioned palette. Compilation validates the model first and
then writes a stable single-model `.ldr` file. The compiler does not bundle
LDraw geometry or Studio data.

To validate against a local LDraw installation, pass a library root to
`discover_ldraw_library(...)` or set `BRICK_BUILDER_LDRAW_LIBRARY`. A valid
root contains `parts/` and `LDConfig.ldr`. Discovery is read-only. On Windows,
the detector also checks the usual BrickLink Studio 2.0 `ldraw` locations.

The generated files still need manual import into BrickLink Studio. That
inspection remains the source of visual appearance, detailed collision and
stability feedback, and build-instruction checks; the deterministic slice now
covers conservative rectangular connectivity and basic AABB collisions.

The validator now performs two distinct checks: document shape (`validate_schema`)
and semantic/catalog/geometry checks (`validate_model`). Rectangular bricks,
plates, and tiles use project-authored parametric profiles. Slopes and other
non-rectangular elements remain intentionally deferred.

## Agent-facing CLI contract

The installed `brick-builder` command (or `python -m brick_builder.cli`) emits
exactly one JSON object on stdout. `catalog` returns the palette vocabulary;
`validate` returns `valid`, model identity, part count, and structured issues;
`analyze` adds deterministic bounds, dimensions, roots, graph edges, and basic
collision/disconnection counts; `compile` additionally returns the output path
and SHA-256 of the emitted LDraw file. Exit code 0 means success; code 2 means
an input or validation error. Each issue contains `code`, `path`, `message`,
and a deterministic `repair_hint`. The optional `--ldraw-library` argument
selects a read-only local LDraw installation.

The optional `demo-generate` command is an offline canned-fixture smoke test
using an injectable adapter; it is not a natural-language provider and is not
the Hermes orchestration path. Real Hermes orchestration belongs in
`hermes/skills/brick-builder/SKILL.md`, where Hermes writes specifications,
candidates, and command records and invokes the deterministic CLI tools for
validation, analysis, and compilation.

To install the repository skill locally, copy `hermes/skills/brick-builder/`
to `%LOCALAPPDATA%/hermes/skills/brick-builder/` on Windows or
`~/.hermes/skills/brick-builder/` on Linux/macOS, then run `/reload-skills`.
A future raw GitHub install can use
`hermes skills install <raw-GitHub-SKILL.md-URL>` once a public URL exists; no
remote repository is assumed here. An adult smoke prompt is: “Make a tiny red
wall using only basic rectangular bricks.” Review the generated run directory
and import the final LDraw file into Studio before any physical build. The
Hermes skill is repository documentation, not Python package data.
