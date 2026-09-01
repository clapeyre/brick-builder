# Brick Builder project roadmap and handoff

Status: active planning record, last updated 2026-09-01.

This document is the durable handoff between development tasks. It records the
current state, architectural direction, ordered milestones, and acceptance
gates. Chat transcripts are useful design history, but they are not the project
source of truth.

## Product goal

Build a child-friendly system that turns a creative request into several small,
recognizable, physically plausible LEGO models. The primary beta tester is six
years old; an adult controls configuration, export, publishing, purchasing, and
physical-build decisions.

The project uses existing catalog parts and a deliberately constrained palette.
It does not design new brick geometry. The deterministic core remains separate
from NVIDIA and all other employer resources and is intended for public release
on GitHub.

## Source-of-truth order

Every implementation task should read these files before making changes:

1. `AGENTS.md` for durable safety, scope, and engineering rules.
2. `PROJECT_BRIEF.md` for the product vision and broad system shape.
3. This roadmap for current status, decisions, and the next milestone.
4. `docs/design-conventions.md` and the active palette when geometry, parts,
   connections, or compilation are involved.

If a completed milestone changes the plan, update this document in the same
commit. Do not rely on a previous agent's conversational context to carry a
decision forward.

## Current verified state

The repository currently contains the deterministic foundation and a bounded
Hermes generation experiment.

Completed capabilities include:

- a versioned canonical LEGO model document;
- LDraw identifiers, units, coordinates, and transformations;
- a small proposed LEGO Classic-oriented palette;
- deterministic `.ldr` compilation;
- schema, palette, transform, stud-grid, collision, grounding, and connectivity
  checks for the supported rectangular parts;
- hand-authored reference models inspected successfully in BrickLink Studio;
- an agent-facing command-line interface with actionable diagnostics;
- a bounded three-attempt generation and repair workflow;
- reproducible run artifacts and hashes;
- a portable Hermes skill and live Hermes smoke test;
- a disposable local-redesign interaction prototype using generic box
  primitives, spatial focus and radius, hard locks, explicit spillover,
  before/after review, retry, accept, and exact undo;
- a deterministic solid-box projection layer with shaded cuboid faces, global
  depth ordering, four reproducible cameras, and replayable focus/edit
  references.
- a bounded deterministic wall-box LEGOization baseline using the existing
  rectangular brick and plate profiles, with checked-in scaffold input,
  target-volume coverage reporting, and structural validation kept separate.

The Hermes experiment proves that an agent can write a candidate, receive
deterministic feedback, repair invalid geometry, and compile a valid result. It
does **not** yet prove that an assembly resembles the creative request. At
present, semantic design is effectively a direct language-model jump from the
request to placed bricks.

## Architectural direction

### Canonical layers

The intended design pipeline is:

```text
child's request
    -> several inexpensive whole-model blockouts
    -> child selects a persistent starting concept
    -> child focuses a point, region, or provisional agent-suggested group
    -> agent proposes a local redesign with visible spillover
    -> child accepts, retries, adjusts focus, locks geometry, or undoes
    -> repeated refinement of the spatial concept
    -> LEGOization and deterministic validation
    -> final Studio inspection and adult-controlled export
```

The missing product capability is not a universal ontology of creature,
vehicle, or building parts. Region names such as `head`, `bow`, `grille`, or
`tower` may be generated for one design as convenient labels, but the core
editing protocol must remain spatial and model-specific.

A selection expresses the user's focus, not necessarily an inviolable cutting
plane. The agent may discover that a good local redesign requires adjacent
changes. Such spillover must be bounded, shown explicitly in a before/after
preview, and reversible. Explicit locks and recorded invariants are hard
constraints; ordinary focus is guidance. When a concept becomes a LEGO
assembly, selection may combine spatial distance with connection and
subassembly relationships.

The first interaction proposal and edit-contract draft are recorded in
[`docs/local-edit-vertical-slice.md`](local-edit-vertical-slice.md). Its example
JSON is exploratory and must not be promoted directly into a production schema
without prototype evidence.

The system must distinguish two kinds of feedback:

- engineering feedback: invalid part, collision, disconnection, unsupported
  component, unstable support, or impossible assembly;
- design feedback: poor silhouette, missing landmark, weak resemblance,
  confusing proportions, or unattractive composition.

Known engineering rules belong in deterministic code. Design feedback may use
renders, a vision-capable model, and the child's judgment, but must result in
explicit localized revisions that are revalidated.

### Harness decision

The deterministic Python core remains harness-agnostic. The intended shipped
agent should be a narrowly bounded LEGO application rather than a general
desktop agent with a LEGO skill.

Pi is the leading product-facing harness direction because it can provide a
small, explicit tool surface and can later be embedded behind a dedicated user
interface. Hermes remains a useful reference adapter until a Pi vertical slice
reaches parity. Do not remove the Hermes integration merely to begin the Pi
work.

The first Pi integration should be a thin TypeScript layer over the existing
Python JSON commands. It should pin an exact compatible Pi release and expose
only Brick Builder tools. It should not rewrite the deterministic engine, grant
generic shell access, or depend immediately on unstable low-level harness
internals.

Provider choice, credentials, and billing remain user configuration. The public
repository may ship the agent, prompts, skills, schemas, policies, and concise
configuration examples, but a comprehensive beginner tutorial for deploying a
general agent harness is out of scope.

## Ordered milestones

These are ordered steps, not calendar commitments. One Codex task should own at
most one milestone or one clearly bounded slice of a milestone.

### Milestone 3A: local-redesign interaction prototype

Status: implemented and verified as a disposable probe on 2026-08-31.

Build a deliberately disposable interaction prototype before defining the next
production schema. Use a crude blocky boat so the experiment does not depend on
predefined vehicle features such as a front grille. The prototype tests whether
a user can refine one area without triggering an opaque whole-model rewrite.

The prototype should provide:

- a rotatable blockout assembled from simple boxes;
- a click-selected focus point and adjustable radius;
- an ordinary-language local redesign request;
- a canned or simulated proposal rather than a live model integration;
- a before/after comparison that marks all changed geometry;
- explicit indication of changes outside the focus radius;
- the ability to accept, retry, undo, and lock selected blocks.

The focus radius is guidance. A proposal may affect adjacent geometry when
needed, but must disclose the spillover. Locked blocks are hard constraints.
Agent-suggested semantic groups may be explored later as a convenience, not as
the canonical representation.

Acceptance gates:

- the user can rotate the blockout and place or adjust a spatial focus;
- the selected focus and any hard-locked geometry are visually unambiguous;
- the proposal identifies every changed block, including spillover;
- retry preserves the focus and locks unless the user changes them;
- undo restores the exact previous state;
- no animal, vehicle, or building part ontology is required;
- the prototype contains no live LLM call, LEGOization, Pi integration, Studio
  automation, purchasing, publishing, or claims of physical buildability;
- the interaction produces enough evidence to choose the next spatial
  representation rather than treating the prototype's data structures as the
  production design.

Milestones after 3A remain provisional until the interaction prototype has been
tried. Revise their interfaces and ordering from observed use rather than
forcing the prototype to validate the earlier plan.

Observed results:

- A pure Python session state machine and a standard-library Tk interface keep
  the probe isolated from the canonical LEGO schema, deterministic engine, and
  Hermes adapter.
- Stable generic-box identifiers plus a world-space focus point and radius are
  sufficient to reproduce selection, hard locks, changed geometry, and one
  bounded adjacent spillover change without a semantic-parts ontology.
- The comparison needs both styling and text: the prototype uses a legend,
  outlines, dashed spillover, block identifiers, and an explicit list of every
  changed block. Relying on color alone was not judged sufficient.
- Retry preserves focus and locks. Changing focus, radius, or locks starts a
  fresh proposal sequence so retry variation cannot leak into a new edit.
- Accept records the complete persistent concept, focus, locks, and camera;
  undo restores those values exactly.
- Forty-four automated tests pass. A Tk-capable desktop Python also passed an
  automated widget-level smoke covering click focus, radius, drag rotation,
  lock/unlock, propose, retry, accept, both comparison canvases, and exact
  undo. The bundled Codex Python used for the isolated test environment cannot
  initialize Tcl/Tk because it lacks `init.tcl`; this is a development-runtime
  limitation, not evidence that every desktop Python installation can render
  the interface.
- The probe supports choosing simple primitives with stable identifiers as the
  leading Milestone 3B representation. It does not yet establish the best
  child-facing selection gesture: clicking currently snaps focus to a block
  center, and a short supervised child trial should compare that with free
  surface picking before the production renderer fixes the interaction.
- The supervising user then tried the running interface and confirmed that
  rotation, focus movement, feedback, retry, and undo work coherently. The
  blocks read as flat upward-facing planes rather than solid volumes. This is
  accepted as a 3A shortcut and becomes the first concrete 3B rendering defect.

### Milestone 3B: production spatial representation and renderer

Adult usability threshold: **met** on 2026-09-01. The supervising user finds
the prototype sufficiently clear to continue engineering toward an end-to-end
demo. The home beta-tester comprehension trial is deferred to Milestone 4; no
child-facing rendering or concept-distinction claim has been made yet.

Choose the smallest production representation justified by the prototype. It
may use boxes, other simple primitives, occupied cells, or another inspectable
spatial form. It must support stable geometry references, reproducible renders,
focus selection, hard locks, and before/after differences without requiring a
universal semantic-parts ontology.

Acceptance gates:

- front, side, top, and three-quarter views are reproducible;
- selected, changed, spilled-over, and locked geometry are distinguishable;
- saved focus and edit references resolve to the same geometry on replay;
- an adult can inspect intentionally different concepts and the edit state
  before any LEGO filling occurs.

Bounded first implementation slice, recorded 2026-09-01:

- retain generic axis-aligned boxes with stable identifiers as the only spatial
  primitive;
- render actual cuboid faces with deterministic occlusion/depth ordering rather
  than the 3A single-plane approximation;
- provide reproducible front, side, top, and three-quarter cameras;
- carry the existing focus, lock, changed, and spillover states into the solid
  renderer with both styling and textual identification;
- preserve exact session replay and undo for fixed inputs;
- keep the renderer small and local rather than reproducing Studio's LEGO CAD,
  connectivity, instruction, or parts-management features.

Slice acceptance gates:

- a non-cubic box visibly presents appropriate top and side faces in the
  three-quarter view;
- all four named cameras produce deterministic projected geometry and visibly
  distinct orientations;
- selected, locked, changed, and spilled-over boxes remain identifiable in
  before/after review;
- stable box and focus references survive serialization and replay;
- the existing deterministic core, canonical LEGO schema, CLI, and Hermes
  adapter remain unchanged and all existing tests continue to pass.

Explicit non-goals for this slice are freeform mesh editing, Studio automation,
LEGOization, connectivity, collision or stability feedback, instructions,
live model calls, Pi integration, and a universal semantic-parts ontology.
Child-comprehension evidence is deferred to Milestone 4 and is not an
engineering gate for the end-to-end demo path.

Slice implementation result, 2026-09-01:

- the single-plane approximation was replaced with projected cuboid faces and
  deterministic back-to-front drawing across the complete scene;
- front, side, top, and three-quarter camera presets are available alongside
  custom drag rotation;
- the original attempt exposed a geometry/normal mismatch on four faces; root
  review corrected the cuboid topology and added projected-area and front-face
  dimension assertions so an edge-on face cannot satisfy the solid-box gate;
- versioned session replay now validates stable block, focus, lock, camera,
  changed, and spillover references and reconstructs an in-review proposal;
- selected, locked, changed, and spilled-over styling and textual identifiers
  remain present in both canvases;
- fifty-one automated tests, Python compilation, and diff checks pass. A real
  Tk widget/canvas smoke rendered 24 visible faces in the three-quarter view
  and eight correctly oriented front faces for the eight-block boat;
- Windows screen capture timed out at the Computer Use approval boundary, so
  no screenshot-based visual judgment is claimed. The supervising user has
  since judged the prototype good enough to proceed; child-comprehension
  evaluation is intentionally deferred to Milestone 4.

### Milestone 3C: initial LEGOization

Implement a deterministic or search-guided baseline that fills simple scaffold
volumes with supported rectangular bricks and plates. Start with torso-like and
wall-like volumes; appendages and slopes can follow after the baseline works.

Optimization priorities should be explicit, for example:

1. cover required volumes and landmarks;
2. maintain legal stud connections and grounding;
3. avoid collisions and inaccessible placements;
4. use fewer and larger pieces where appropriate;
5. preserve important silhouette features;
6. respect inventory constraints when an inventory is available.

Acceptance gates:

- at least one hand-authored scaffold becomes a connected valid assembly;
- results are deterministic for a fixed input and configuration;
- failures explain which target regions could not be filled;
- the output passes the existing validators and imports on the Studio stud grid;
- tests separate target coverage from structural validity.

#### 3C first bounded slice: deterministic wall-box LEGOization

Status: verified first slice (2026-09-01).

Implement one deliberately narrow bridge from a hand-authored, axis-aligned
wall-like box scaffold to the existing canonical model.  The scaffold is a
finite stud-grid target volume.  A deterministic tiler may choose only the
currently supported rectangular bricks and plates from the existing palette,
then must report both the occupied target volume and any target cells it could
not cover.  The result is accepted only when the canonical validator separately
reports a connected, valid assembly.

Acceptance gates for this slice:

- one checked-in wall-like scaffold produces byte-for-byte identical canonical
  output for repeated fixed-input runs;
- its target-volume coverage report identifies required, covered, and uncovered
  cells; no uncovered cells are present in the successful reference case;
- an intentionally unfillable target produces a deterministic, actionable
  uncovered-region diagnostic rather than an invalid candidate;
- the successful candidate passes the existing structural validators, including
  grounding and connectivity, independently of coverage;
- focused tests prove that coverage and structural validity are distinct checks;
- the existing deterministic core, CLI, Hermes integration, and any 3B renderer
  files present in the checkout remain unchanged in behavior.

Explicit non-goals for this slice: live LLM calls, Pi integration, Studio
automation, UI expansion, inventory optimization, complex or non-rectangular
parts, appendages/slopes, and a universal semantic ontology.

Observed results (2026-09-01):

- `examples/scaffolds/wall-box-5x2.json` deterministically produces a
  four-part canonical model with complete target coverage, no structural
  issues, and absolute 20 LDU mesh-aligned bounds;
- an intentionally unsupported depth-two target reports all twelve uncovered
  plate-cells with an `UNFILLED_TARGET_REGION` diagnostic while its one-stud
  partial assembly is structurally valid;
- a four-plate-high wall uses a supported rectangular plate above a brick,
  proving this slice accepts both supported rectangular bricks and plates;
- 40 deterministic unit and CLI tests pass. No Studio automation or
  child-tester review was performed.

#### 3C second bounded slice: two-stud-deep rectangular box

Status: verified second slice (2026-09-01).

Extend only the deterministic scaffold tiler so a hand-authored, solid
two-stud-deep rectangular box can be covered by existing rectangular bricks
and plates. Preserve the one-stud wall behavior exactly. Permit only identity
and existing vertical 90-degree rotations; use deterministic placement order
and keep coverage cells and canonical structural validation separate.

Acceptance gates:

- a checked-in two-stud-deep box scaffold yields repeatable complete coverage
  and a connected, grounded canonical model;
- an intentionally unsupported depth retains an actionable uncovered-region
  diagnostic; no silent partial success is permitted;
- tests cover both orientations, deterministic output, coverage reporting, and
  the separation of coverage from structural validity;
- the Python CLI, Pi adapter, Hermes integration, renderer, and existing
  one-stud wall case retain their behavior.

Explicit non-goals: arbitrary depth, search optimization, inventory use,
slopes/complex parts, live providers, Pi changes, UI changes, Studio
automation, and universal semantic labels.

Observed results (2026-09-01):

- `examples/scaffolds/box-4x2x2.json` deterministically produces a fully
  covered, grounded, connected canonical assembly using only the existing
  rectangular brick and plate palette;
- depth-two placement supports only identity and vertical 90-degree rotation;
  successful reports have no uncovered-region diagnostics, while depth three
  retains a deterministic `UNFILLED_TARGET_REGION` diagnostic and cannot be
  reported as a valid result;
- coverage remains separate from structural validity, including a complete but
  disconnected two-depth test case;
- 58 Python tests and Python byte-compilation pass. Pi, Hermes, the CLI, and
  the local renderer were not changed.

### Milestone 3D: Pi parity slice

#### 3D first bounded slice: offline Pi domain-tool contract

Status: verified first slice (2026-09-01). The supervising user has
confirmed that the current local interface is clear enough for adult-guided
use. Child-comprehension evaluation is deferred to Milestone 4 and does not
block the end-to-end demo path.

Add a small pinned TypeScript Pi adapter that exposes only offline,
domain-specific wrappers over the existing Python JSON CLI. The first slice
must cover palette inspection, canonical-model validation and analysis,
deterministic compilation, and the existing offline demo-generation workflow.
It must own an explicit per-run directory under a caller-provided root, and it
must never expose a generic shell or arbitrary file-write tool to Pi.

Acceptance gates for this slice:

- the Pi package version is exact-pinned and its adapter configuration exposes
  only the documented Brick Builder domain operations;
- scripted fake-model tests cover success, a rejected malformed tool call,
  bounded repair/exhaustion, cancellation, and provider failure without a live
  provider or credential;
- identical accepted canonical models compile to identical LDraw output through
  the adapter; all paths remain contained in the supplied run root;
- run artifacts are complete and auditable, and the Python core, CLI, and
  Hermes integration retain their current behavior;
- Hermes remains installed and its existing smoke workflow remains passing.

Explicit non-goals: a live provider call, credentials, Pi-driven UI changes,
Studio automation, arbitrary shell/filesystem access, inventory optimization,
new LEGOization shapes, and replacing Hermes.

Observed results (2026-09-01):

- `pi-adapter/` pins `@earendil-works/pi-coding-agent` at `0.84.4`; its
  session configuration disables Pi built-in tools and supplies only five
  Brick Builder domain wrappers;
- the wrappers invoke the existing Python JSON CLI with `shell: false`, write
  only beneath their caller-provided run root, and cover catalog, validation,
  analysis, compilation, and the existing offline demo fixture;
- four compiled TypeScript tests pass for success/deterministic compilation,
  malformed data and path escape rejection, bounded exhaustion, cancellation,
  and simulated provider failure. No provider credentials or live call were
  used;
- the existing 55 Python tests continue to pass and Hermes remains untouched.

#### 3D second bounded slice: scripted Pi-session contract

Status: verified (2026-09-01).

Exercise the existing offline domain-tool adapter through Pi agent sessions
backed by scripted, in-memory model responses. This slice must prove that the
Pi runtime receives the narrow Brick Builder tool set—not a generic shell or
filesystem—and that tool calls, malformed calls, bounded repair, exhaustion,
cancellation, and provider failure have auditable session outcomes. No live
provider, credential, or user-facing Pi UI is permitted.

Acceptance gates:

- a scripted successful session uses the domain tools to validate and compile a
  known canonical model into its run root;
- scripted malformed call, bounded repair/exhaustion, cancellation, and
  provider failure cases each produce deterministic, asserted outcomes;
- all generated artifacts remain inside the declared run root and the session
  configuration exposes no Pi built-in tool;
- the existing adapter wrapper tests, Python CLI tests, and Hermes smoke
  contract retain their behavior.

Explicit non-goals: live provider calls or credentials, a model-selection UI,
new domain operations, Pi-driven editing, arbitrary filesystem or shell tools,
Studio automation, and changes to the deterministic Python core.

Observed results (2026-09-01):

- the adapter now runs a real in-memory Pi `AgentSession` using Pi's pinned
  faux provider; it retains `noTools: "builtin"` and supplies only the five
  existing Brick Builder domain tools;
- scripted session tests assert validate-and-compile success, malformed model
  arguments followed by repair, bounded exhaustion, cancellation, and a
  provider failure; every session writes an auditable `session-outcome.json`
  alongside the already confined run artifacts;
- the adapter's direct Pi AI dependency is exact-pinned at `0.84.4`, matching
  the pinned coding-agent release; no provider credential or network is used;
- seven compiled TypeScript tests, all 58 Python tests, TypeScript type-check,
  and diff checks pass. The original `tsx` runner cannot start in this Codex
  Windows runtime because `uv_os_get_passwd` returns `ENOMEM`; compiling first
  and using Node's native test runner verifies the same test module instead.
  Hermes files and the deterministic Python core remain unchanged.

Reproduce the bounded Hermes workflow in Pi without changing the Python core.
The initial tool surface should be domain-specific, approximately:

- inspect the supported palette;
- submit or revise a bounded creative request;
- generate or inspect the chosen spatial concept representation;
- submit a focused redesign request with locks and invariants;
- request LEGOization;
- validate and analyze an assembly;
- compile and finalize a successful run.

The integration owns paths and run directories. The model must not receive
arbitrary filesystem writes or a general shell in the shipped configuration.

Acceptance gates:

- the existing simple prompts complete through Pi with bounded attempts;
- fake or scripted model tests cover success, repair, malformed tool calls,
  exhaustion, cancellation, and provider failure;
- identical accepted canonical assemblies compile to identical output;
- run artifacts are complete and auditable;
- model provider and model remain replaceable configuration;
- Hermes is retained until this slice is demonstrably no worse as an adapter.

### Milestone 3E: rendered visual critique and local redesign

Render valid LEGO candidates from fixed cameras and add a deliberately bounded
visual critique pass. Critique should answer targeted questions about identity,
silhouette, landmarks, proportions, symmetry, and accidental visual artifacts.

Criticism must be translated into operations such as `enlarge head`, `lengthen
tail`, `raise wings`, or `move eyes`, rather than regenerating the entire model
without explanation. Every edited result returns through deterministic
validation.

Acceptance gates:

- the system records renders, critique, chosen revision operations, and results;
- semantic resemblance and engineering validity are reported separately;
- visual repair is bounded and preserves successful subassemblies when possible;
- a small prompt evaluation set demonstrates improvement more often than
  regression;
- child preference is recorded as evaluation evidence, not treated as a
  deterministic truth label.

### Milestone 4: child interaction and candidate selection

Create a simple local interface only after the design loop produces worthwhile
candidates. Begin with large candidate images, short revision controls, undo,
and restart. Voice can follow reliable text interaction.

Configuration, Studio export, publishing, purchasing, and any external account
action remain in an adult-controlled area.

### Milestone 5: Studio inspection, physical builds, and release hardening

Add Studio or GUI inspection only for information that deterministic tools and
controlled renders do not provide adequately. Computer Use is an optional
high-cost perception and actuation layer, not the primary design representation.

Maintain prompt evaluations, physically build representative models, record
real-world failures, verify licences and attribution, and prepare the public
GitHub repository. Do not claim physical buildability solely from digital
validation.

## Task and subagent working method

Long-running conversation history must not be required to perform repository
work. Use the following working method:

1. Start a fresh Codex task for each milestone or bounded slice.
2. Point it to `AGENTS.md`, `PROJECT_BRIEF.md`, and this roadmap.
3. Ask the root agent to inspect the current worktree and recent commits before
   proposing edits.
4. For every implementation slice, give at least one `gpt-5.6-luna` subagent
   the first bounded implementation attempt. Give each subagent one independent
   deliverable and avoid an indefinitely running subagent that accumulates the
   whole project history.
5. Keep one root agent responsible for integration, verification, and the final
   commit for that slice.
6. Commit coherent increments as they pass their acceptance gates and push the
   verified commits regularly to the configured `origin`.
7. At the end of the task, update `Current verified state`, the applicable
   milestone, and `Next recommended task` below.

Use a continuation in the same task for immediate debugging of work that task
just performed. Start a new task when changing milestones, when the required
context is already in the repository, or when the conversation has accumulated
substantial exploratory history unrelated to the next implementation slice.

## Next recommended task

Build a single bounded end-to-end demo path before further UI refinement. It
should take one deliberately narrow creative request through a recorded brief,
an inspectable spatial scaffold, deterministic LEGOization, validation,
compilation, fixed-view output, and an auditable run manifest. Use scripted or
checked-in inputs first; a live provider, credentials, and public sharing still
require explicit adult approval.

The demo must retain the current hard constraints: no generic shell or
filesystem access for Pi, no silent whole-model rewrite after a concept is
selected, deterministic engineering validation separated from resemblance,
and all artifacts contained in a per-run directory. Improve the child-facing
UI only after this vertical path produces a result worth testing with a child.

The deferred Milestone 4 trial should then evaluate child comprehension of
candidate choice, focus, locks, spillover, accept, and undo using the
end-to-end demo rather than the early renderer prototype in isolation.
