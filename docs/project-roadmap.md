# Brick Builder project roadmap and handoff

Status: active planning record, last updated 2026-09-02.

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

Deferred cleanup and upgrade ideas are tracked in [`docs/backlog.md`](backlog.md);
they are not ordered delivery milestones until promoted here.

If a completed milestone changes the plan, update this document in the same
commit. Do not rely on a previous agent's conversational context to carry a
decision forward.

## MVP definition

The first showcaseable MVP is a child-facing creative loop, not a general CAD
tool and not a fixed-command toy. A child may make an ordinary-language
request, choose among a few visibly distinct proposed concepts, focus a region
or lock what they like, and make an ordinary-language local change request.
The agent must show a bounded, reversible proposal with any spillover made
visible. Accepted designs proceed through deterministic LEGO validation and can
be inspected in Studio by an adult.

The internal representation may be deliberately constrained and structured so
it can be validated, but the child must not need a universal creature, vehicle,
or building ontology or a prescribed revision vocabulary. Model-generated
labels can be temporary, design-specific conveniences; spatial focus, locks,
and explicit before/after evidence are the durable interaction contract.

The MVP is successful when a supervised child can recognize their idea in at
least one proposal, select and revise it through this loop, and an adult can
inspect the resulting valid assembly. It is also a technical showcase of
verifier-guided physical design: the model proposes, while deterministic code
checks known engineering constraints and preserves the full evidence trail.

## Current verified state

The repository contains the deterministic foundation, bounded agent harnesses,
and offline candidate, rendering, selection, headless child-facing controller,
critique-operation evaluation, semantic-critique evidence, and prompt-set
evaluation demonstrations, and one bounded visual-repair operation.
It does not yet demonstrate that a model understands an arbitrary creative
request or performs a real child-facing local redesign on a LEGO candidate.

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
- a restricted Pi adapter with real scripted `AgentSession` coverage for
  validation, compilation, candidate replay, explicit selection, brief
  submission, bounded repair/exhaustion, cancellation, and provider failure;
- offline candidate-set and selection artifacts that preserve validation,
  LDraw, render-evidence, manifest, and receipt provenance.
- composed one-box, stepped-box, and gatehouse concept candidates with stable
  IDs, deterministic fixed-camera render evidence, and bounded visual
  observations for silhouette bounds, aspect, part visibility, and landmarks;
- an explicitly selected composed candidate can enter the reversible local
  redesign session, preserve provenance and hard locks, and produce a revised
  LEGO assembly only after its original family bridge accepts the proposal;

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

#### 3C third bounded slice: centered two-tier stepped box

Status: verified (2026-09-02).

Extend the deterministic LEGOization bridge with exactly one new scaffold
family: a grounded, two-stud-deep rectangular base with a centered, narrower
rectangular upper tier. Each tier has an explicit positive brick height; the
upper tier must fit on the base with an even stud-width difference so centering
stays on the established 20 LDU grid. Reuse the existing rectangular brick and
plate palette and retain coverage and structural validity as independent
results.

Acceptance gates:

- a checked-in `4 x 2` base plus centered `2 x 2` upper-tier fixture produces
  deterministic, complete, connected, grounded output using only supported
  rectangular parts;
- the report accounts for every base and upper-tier target cell in a shared
  absolute cell space, while the existing one- and two-depth box behavior is
  byte-for-byte unchanged;
- invalid tier geometry and unsupported depth return actionable input or
  uncovered-region failures; no partial output is reported as successful;
- focused tests prove repeatability, centering, coverage/structure separation,
  and preservation of the existing box cases.

Explicit non-goals: arbitrary voxel or multi-branch scaffolds, overhangs,
slopes, search optimization, inventory use, live providers, Pi/Hermes changes,
Studio automation, visual critique, UI work, and child testing.

Observed results (2026-09-02):

- `SteppedBoxScaffold` and `legoize_stepped_box` cover a checked-in `4 x 2`
  base plus centered `2 x 2` upper tier in one absolute `(x, layer, z)` cell
  space; the assembled model is grounded, connected, and deterministic;
- the upper tier starts on the base's top plate layer and its width is centered
  on the established stud grid; malformed tier dimensions reject before a
  candidate is produced, while unsupported depth remains incomplete with the
  existing actionable uncovered-region diagnostic;
- the original one- and two-depth box tiler was not changed. Focused tests,
  the full Python suite, byte-compilation, and diff checks pass.

#### 3C fourth bounded slice: stepped fixture in offline demo replay

Status: verified (2026-09-02).

Route one explicitly tagged, checked-in stepped scaffold fixture through the
existing fixture-driven demo replay. The replay selects the existing wall-box
or centered stepped-box LEGOizer from the scaffold's declared kind; it must not
infer a shape family from creative text. Add a matching request and brief so a
fresh replay demonstrates the new non-box shape through validation, LDraw,
fixed renders, render evidence, and a manifest.

Acceptance gates:

- the existing untagged wall-box fixture continues through its prior path with
  stable successful artifacts;
- a tagged stepped fixture produces a repeatable, valid, complete contained
  run with the existing named artifacts and a visibly multi-tier three-quarter
  render;
- unsupported known scaffolds still stop before final LDraw and render output;
  an unknown scaffold kind yields an actionable contained failure rather than
  silently selecting a LEGOizer;
- no new provider, Pi, Hermes, UI, renderer, or production brief/scaffold
  schema is introduced.

Explicit non-goals: natural-language parsing, live provider or vision calls,
automatic scaffold selection, arbitrary scaffold unions, visual resemblance
scoring, Studio automation, and child testing.

Observed results (2026-09-02):

- the replay now routes only an explicit `kind: "stepped_box"` fixture to the
  centered stepped LEGOizer; the pre-existing untagged fixture retains its
  wall-box route and creative request text is never used for dispatch;
- the checked-in stepped request, brief, and scaffold replay deterministically
  to a complete valid two-tier model, LDraw file, fixed SVG renders, render
  evidence, and manifest; the upper tier is visibly elevated in the
  three-quarter projection;
- an unknown scaffold kind produces contained `failure.json` evidence and a
  failed manifest before any canonical model, LDraw, or render output exists;
- 65 Python tests, byte-compilation, and diff checks pass. Pi, Hermes, UI, and
  renderer behavior were not changed.

#### 3C fifth bounded slice: offline candidate-set replay

Status: verified (2026-09-02).

Compose the existing fixture-driven replay into one bounded candidate set for a
single checked-in request and brief. A candidate-set fixture explicitly lists
two stable candidate identifiers and their scaffold fixtures. The replay must
run each candidate inside its own child run directory, preserve its ordinary
validation/LDraw/render/evidence/manifest artifacts, and write a root index
that records each candidate's outcome and child-manifest hash. It must never
rank, select, or claim a preferred candidate.

Acceptance gates:

- one checked-in request and brief yield two distinct, valid deterministic
  candidates: compact box and centered stepped box;
- repeated runs produce byte-identical candidate index data and per-candidate
  manifest file hashes; root artifacts are contained under the declared run
  root;
- a candidate failure remains attributable to its stable identifier and makes
  the set unsuccessful without deleting or disguising the other candidate's
  artifacts;
- malformed candidate identifiers or duplicate identifiers fail before child
  run directories are created; no automatic ranking, selection, provider,
  Pi, Hermes, UI, or renderer changes are introduced.

Explicit non-goals: natural-language candidate generation, model ranking,
selection persistence, child interaction, live provider or vision calls,
arbitrary candidate counts, Studio automation, and inventory optimization.

Observed results (2026-09-02):

- `demo-candidate-set` replays an explicit two-candidate fixture for one
  checked-in tiny-red-tower request and brief: a compact box and a centered
  stepped tower, each under `candidates/<stable-id>/` with its ordinary
  validation, LDraw, renders, render evidence, and manifest;
- the root run preserves the request, brief, exact candidate-set fixture, and
  a `candidate-index.json` containing only stable ids, outcome/status, model
  id, and each child manifest's SHA-256; no score, winner, or selection is
  emitted;
- malformed or duplicate ids fail before a run root exists. If a validly
  declared candidate later fails, its identifier remains in the index and the
  successful sibling's artifacts remain available;
- 68 Python tests, byte-compilation, and diff checks pass. No Pi, Hermes, UI,
  provider, or renderer changes were made.

#### 3C sixth bounded slice: deterministic two-tower gatehouse

Status: verified (2026-09-02).

Add one explicitly parameterized gatehouse scaffold to the deterministic
LEGOization core: two equal rectangular towers with an open central gateway
below one full-width top bridge. Keep the shape two studs deep and compose it
only from the existing validated rectangular palette and stud-based
connections. This establishes a deliberately small architectural silhouette
before it is admitted to a demo or selector.

Acceptance gates:

- a checked-in six-stud-wide, two-stud-deep gatehouse fixture deterministically
  produces a complete, grounded, structurally valid canonical assembly;
- coverage treats the central lower gateway as intentionally absent while
  requiring every occupied tower and bridge cell;
- malformed tower/opening dimensions reject clearly, and unsupported depth
  reports the current actionable incomplete-coverage diagnostic;
- existing wall-box and stepped-box tilers remain behaviorally unchanged, with
  focused tests, the full Python suite, byte-compilation, and diff checks
  passing.

Explicit non-goals: arbitrary spatial unions, doors, windows, arches, slopes,
roofs, decorative details, automatic scaffold dispatch, demo/selector changes,
Studio automation, live providers, and physical-build claims.

Observed results (2026-09-02):

- `GatehouseScaffold` composes two equal two-stud-deep tower volumes and a
  full-width upper bridge through the existing rectangular LEGOizers; the
  checked-in six-wide fixture is deterministic, complete, grounded, connected,
  and structurally valid;
- the canonical coverage target excludes the central lower gateway cells while
  including their bridge-layer cells, so an opening cannot be mistaken for
  accidental missing coverage;
- malformed width decomposition rejects before model construction, while a
  depth-three request preserves the existing actionable uncovered-region path;
- 81 Python tests, byte-compilation, and diff checks pass. No demo, selector,
  provider, Pi, Hermes, Studio, or rendering behavior changed.

#### 3C seventh bounded slice: explicit gatehouse replay candidate

Status: verified (2026-09-02).

Admit the verified gatehouse only through an explicitly tagged offline replay
fixture and a bounded three-candidate set. Dispatch remains solely on
`scaffold.kind`; the candidate-set fixture, rather than creative text or
shape inference, declares the third stable candidate.

Acceptance gates:

- a tagged gatehouse fixture replays to complete canonical validation, LDraw,
  fixed renders, render evidence, and a manifest;
- a checked-in three-candidate fixture produces compact box, stepped box, and
  gatehouse children in stable declared order, all with their own auditable
  artifacts and no selected/winner field;
- the prior two-candidate tower fixture remains accepted for the existing local
  selector, while unrecognized kinds retain their contained actionable failure
  path;
- all candidate-set cardinality remains deliberately bounded and explicit;
  focused tests, the full suite, byte-compilation, and diff checks pass.

Explicit non-goals: automatic candidate generation, ranking, selection changes,
selector/UI changes, free-text understanding, arbitrary candidate counts,
provider/Pi/Hermes work, Studio automation, and physical-build claims.

Observed results (2026-09-02):

- `replay_demo` now routes only an explicit `kind: "gatehouse"` fixture to
  `legoize_gatehouse`; unknown kinds preserve the contained failure artifact
  path and list the complete accepted-kind vocabulary;
- the new `candidate-set-towers-with-gatehouse.json` fixture yields three
  declared, valid children in order: compact box, stepped box, and gatehouse,
  each with validation, LDraw, fixed SVG renders, render evidence, and a
  manifest;
- the existing two-choice fixture is unchanged and the replay contract accepts
  only exactly two or exactly three candidates, preserving the current selector
  without opening arbitrary candidate counts;
- 82 Python tests, byte-compilation, and diff checks pass. No selector, Pi,
  Hermes, provider, Studio, rendering, ranking, or selection behavior changed.

#### 4A first bounded slice: explicit selected-candidate receipt

Status: verified (2026-09-02).

Add one adult-controlled, deterministic selection action over a completed
candidate-set run. Given an exact valid candidate id and a fresh destination,
it verifies the root index against the candidate's child manifest, copies the
selected canonical model, LDraw, fixed renders, render evidence, validation,
and analysis unchanged, then writes a selection receipt and manifest that bind
the source candidate-set and child-manifest hashes. Selection is an explicit
choice, never a ranking or regeneration.

Acceptance gates:

- selecting `compact-box` or `stepped-box` produces a separate auditable,
  byte-identical selected-output bundle with no model mutation;
- selection rejects an unknown or failed id, candidate-index/child-manifest
  mismatch, or missing/hash-mismatched selected artifact before creating its
  output directory;
- selection receipt and manifest identify the selected stable id, model id,
  source candidate-set manifest hash, child manifest hash, and selected
  artifact hashes without depending on source absolute paths;
- existing candidate replay and both candidate artifact chains remain
  unchanged; no UI, ranking, live provider, Pi/Hermes, Studio, purchasing, or
  publishing action is introduced.

Explicit non-goals: child-facing controls, candidate comparison UI, automatic
choice, local redesign, live models, physical-build claims, external export,
or destructive replacement of a previous selection.

Observed results (2026-09-02):

- `select-candidate` accepts an explicit valid stable id from a successful
  candidate-set run and creates a fresh bundle containing byte-identical
  canonical model, LDraw, validation, analysis, fixed renders, and render
  evidence;
- `selection.json` and the selection manifest bind the chosen id/model to
  source root and child-manifest SHA-256 values plus each copied artifact hash,
  without storing source paths or changing the source candidate run;
- unknown, failed, tampered, index/child-manifest-mismatched, or palette-
  mismatched selections fail before a destination exists. No ranking or model
  rewrite occurs;
- 70 Python tests, byte-compilation, and diff checks pass. No UI, Pi, Hermes,
  provider, Studio, purchasing, or publishing behavior was added.

#### 4A second bounded slice: local fixture-demo selector

Status: verified (2026-09-02).

Build a small local Tk demonstration around the existing offline tower
candidate-set and explicit selection contracts. One `Create tower choices`
action creates a fresh contained candidate run; two side-by-side deterministic
canvas previews identify the compact and stepped candidates; two explicit
selection buttons write the existing auditable selected-output bundle and show
its local destination. The screen is a fixture demo, not a claim that free
text is being understood or that a child has validated the interaction.

Acceptance gates:

- a testable non-Tk controller creates the existing two-candidate run and can
  select only an explicitly named candidate into a fresh bundle;
- the Tk view has one generation action, two visibly distinct deterministic
  previews with stable candidate labels, disabled selection before generation,
  and an explicit result/status after selection;
- no network/provider, model generation, general filesystem tool, Pi/Hermes,
  Studio, purchasing, publishing, or silent selection is introduced; run
  artifacts stay beneath a user-supplied run root;
- focused controller tests, the existing full test suite, byte-compilation,
  and diff checks pass. A real Tk smoke is reported only when the local Python
  runtime can initialize Tcl/Tk.

Explicit non-goals: free-text parsing, voice, child-comprehension claims,
responsive production design, undo/retry/local redesign, image export,
candidate ranking, Studio launch, and physical-build claims.

Observed results (2026-09-02):

- `python -m brick_builder.fixture_demo_selector --run-root <directory>`
  provides one explicit `Create tower choices` action, side-by-side labelled
  compact and stepped projections derived from the generated canonical models,
  and disabled selection controls until a candidate set exists;
- a headless `FixtureDemoController` creates fresh contained candidate runs
  and explicitly selects either stable id through the verified selection
  receipt contract; it cannot select before generation or infer an id;
- controller tests verify distinct previews and contained selected bundles.
  The bundled Python runtime's Tcl/Tk lacks `init.tcl`, so its widget smoke is
  correctly skipped; no screenshot or visual-judgment claim is made;
- 73 Python tests, byte-compilation, and diff checks pass. No provider,
  network, Pi, Hermes, Studio, purchasing, publishing, or model generation was
  added.

#### 4A selector follow-up: dependency and failed-run guard

Status: verified (2026-09-02).

Harden the local fixture selector against an interpreter missing the project's
runtime dependency or any other failed candidate set. The controller must not
enter its generated state, load a preview, or enable selection when the replay
returns an unsuccessful result. It must surface an actionable, non-technical
setup message that identifies the missing `jsonschema` dependency when that is
the cause and preserves the failed run's artifacts for diagnosis.

Acceptance gates:

- a simulated failed candidate-set result leaves controller generation false
  and selection impossible, while identifying the stable failed candidates and
  actionable issue codes in its error;
- the Tk view keeps both selection buttons disabled after failed generation and
  displays the actionable status rather than a missing-file traceback;
- local setup instructions state how to install the project dependencies into
  the same desktop Python interpreter that launches the selector;
- successful controller and existing candidate/selection behavior remain
  unchanged; no auto-install, network call, provider, Pi/Hermes, or general
  filesystem capability is introduced.

Explicit non-goals: automatic dependency installation, hiding failed artifacts,
free-text generation, UI redesign, ranking, Studio launch, or child testing.

Observed results (2026-09-02):

- candidate-set replay now preserves structured failures in each candidate
  index entry. The fixture controller only enters generated state when the set
  succeeds; otherwise it leaves selection and preview unavailable and reports
  the stable ids and underlying diagnostic;
- the observed missing-`jsonschema` desktop-interpreter failure is surfaced as
  `SCHEMA_DEPENDENCY` with a setup pointer rather than a missing
  `legoized.json` error. Failed run artifacts remain available for diagnosis;
- [`docs/demo-setup.md`](demo-setup.md) supplies Windows PowerShell commands
  for a dedicated `.demo-venv` using the same desktop Python that launches the
  selector; that environment is ignored by Git. The application never installs
  dependencies itself;
- 74 Python tests, byte-compilation, and diff checks pass; one Tk smoke is
  skipped solely because the bundled runtime cannot initialize Tcl/Tk.

#### 4A selector follow-up: fitted interactive previews

Status: verified (2026-09-02).

Correct the fixture selector's actual-canvas preview behavior. Canonical model
coordinates are LDraw units, so each candidate preview must first center its
model bounds and derive a deterministic scale that fits the visible canvas
with padding. Add per-candidate mouse-drag rotation and an explicit reset to
the fixed three-quarter view; the preview must redraw from the exact generated
canonical model after every view change.

Acceptance gates:

- compact and stepped models fit completely within their canvases with visible
  bounded geometry and distinct projected silhouettes at the default view;
- drag events update only the interacted candidate's yaw/pitch and redraw its
  deterministic generated-model projection; reset restores the named default
  view exactly;
- controller-level tests verify centering, fit bounds, distinct candidates,
  independent rotation, and reset without requiring Tk; a widget smoke is
  reported only if Tcl/Tk initializes;
- candidate generation/selection artifacts and all offline, provider, Pi,
  Hermes, Studio, and safety boundaries remain unchanged.

Explicit non-goals: photorealistic rendering, Studio rendering, free-camera
physics, mesh editing, free-text generation, new candidate shapes, UI polish,
or child-comprehension claims.

Observed results (2026-09-02):

- previews now center the transformed canonical bounds at the canvas origin,
  calculate a padded deterministic fit scale from the active yaw/pitch, and
  globally depth-sort all generated-model faces. Both candidates are visible
  and distinct at the default three-quarter view;
- dragging a generated preview updates only that candidate's yaw/pitch and
  redraws it; its Reset view button restores the exact default. Drag and Reset
  controls remain inert/disabled before successful generation;
- controller tests cover canvas fit, distinct projections, independent
  rotation, and exact reset. The bundled runtime still cannot initialize Tcl/Tk
  for a visual smoke, so no screenshot-based visual claim is made;
- 76 Python tests, byte-compilation, and diff checks pass. Candidate artifacts
  and restricted integrations remain unchanged.

#### 4A selector follow-up: natural horizontal drag direction

Status: verified (2026-09-02).

Reverse only the fixture selector's horizontal mouse-drag yaw mapping so a
rightward drag turns the displayed 3D model rightward under the current
orthographic projection. Preserve per-candidate state, vertical pitch mapping,
and exact Reset view behavior.

Acceptance gates:

- a rightward controller/UI drag produces the yaw direction that moves the
  model's visible orientation rightward; a leftward drag is its inverse;
- vertical drag, independent candidate camera state, deterministic fitting,
  and reset remain unchanged;
- focused tests express the screen-drag-to-yaw mapping independently of Tk,
  and the full suite, byte-compilation, and diff checks pass.

Explicit non-goals: changing canonical LDraw rotations, local-redesign drag
behavior, camera presets, free-camera physics, or any generation/selection
artifact.

Observed results (2026-09-02):

- the fixture selector now maps positive horizontal screen movement to negative
  camera yaw, which makes a rightward drag turn the displayed model rightward
  under its existing projection convention. Vertical pitch mapping is
  unchanged;
- focused tests assert the screen-drag mapping, independent candidate state,
  and retained exact reset behavior; no canonical, local-redesign, generation,
  selection, or integration behavior changed;
- 77 Python tests, byte-compilation, and diff checks pass. The bundled
  runtime's Tk smoke remains skipped solely for its missing Tcl/Tk data.

#### 4A selector follow-up: explicit three-choice gatehouse layout

Status: verified (2026-09-02).

Connect the already verified, separately checked-in three-candidate replay
fixture to the fixture selector. The screen must show compact tower, stepped
tower, and gatehouse as three equal explicit choices, each projecting only its
generated canonical model and retaining independent drag/reset and selection
state.

Acceptance gates:

- one generation action yields the declared compact-box, stepped-box, and
  gatehouse candidate order, with an individually fitted, visibly bounded
  preview and explicit selection control for each;
- all three camera states are independent; drag/reset and explicit selection
  preserve the existing auditable candidate and selected-bundle contracts;
- all controls remain disabled after startup or failed generation, and a
  failed three-candidate run continues to report actionable diagnostics;
- controller tests cover all three choices, the existing full suite,
  byte-compilation, and diff checks pass; a Tk smoke is reported only if Tcl/Tk
  initializes.

Explicit non-goals: free-text generation, automatic choice or ranking,
responsive production layout, image export, new LEGO geometry, candidate-set
cardinality changes, Pi/Hermes work, Studio launch, and child testing.

Observed results (2026-09-02):

- the fixture selector now consumes only the separately declared three-choice
  fixture and presents compact tower, stepped tower, and gatehouse side by
  side, each from its generated canonical model;
- each choice has independently fitted drag/reset preview state and an explicit
  selection button that writes the existing auditable selection bundle;
- controller and Tk smoke assertions cover all three disabled startup controls,
  three generated previews, gatehouse selection, and cross-choice camera-state
  isolation; no generic gallery or candidate-set expansion was introduced;
- 82 Python tests, byte-compilation, and diff checks pass. The bundled runtime
  skips the widget smoke solely because its Tcl/Tk data cannot initialize.

#### 4A selector follow-up: canonical vertical orientation and face ordering

Status: verified (2026-09-03).

Correct the fixture selector's projection boundary for canonical LDraw
coordinates. LDraw model bounds use positive Y downward, while the generic
box projector's screen convention uses positive Y upward; the adapter must
normalize that axis before projecting the generated candidate models. Preserve
the existing bounded camera controls and ensure the resulting painter order
does not make visible panels appear in front of nearer geometry.

Acceptance gates:

- the three generated candidates appear upright at the default three-quarter
  view, with upper courses and the gatehouse bridge above their supports;
- visible faces are drawn back-to-front for the normalized canonical geometry,
  with regression coverage for overlapping stepped and gatehouse panels;
- drag, reset, fitting, candidate order, explicit selection, and selection
  artifacts remain unchanged;
- focused projection/selector tests, the full Python suite, byte-compilation,
  diff checks, and a desktop Tk smoke pass.

Explicit non-goals: new geometry, camera redesign, photorealistic rendering,
free-text generation, candidate ranking, child testing, Studio automation,
export, purchasing, publishing, or changes to the local-redesign coordinate
convention.

Observed results (2026-09-03):

- canonical LDraw candidate bounds now invert only the vertical center at the
  selector/render boundary, so the upper courses and gatehouse bridge project
  above their supports without changing canonical files or local-redesign
  coordinates;
- the deterministic SVG render path uses the same normalization, keeping its
  face depth order consistent with the comparison previews;
- a regression test covers upright compact, stepped, and gatehouse candidates;
  the existing global face-depth sort, drag/reset, fitting, candidate order,
  and explicit selection behavior remain intact;
- 138 Python tests pass with one known bundled-runtime Tk skip, 8 desktop
  selector tests pass including the real Tk smoke, byte-compilation, and diff
  checks pass.

#### 4A selector follow-up: depth-buffered preview occlusion

Status: verified (2026-09-03).

Correct remaining visual clipping in the comparison canvases. The current
orthographic face list is deterministic and back-to-front, but a painter
order cannot resolve every overlap between projected cuboid panels. Add a
small UI-local software depth buffer that chooses the nearest visible face at
each preview pixel, while retaining the existing face projection contract for
tests and other consumers.

Acceptance gates:

- overlapping stepped and gatehouse panels are occluded according to their
  projected depth rather than whichever polygon was drawn last;
- the default and dragged previews remain bounded, upright, deterministic,
  and visually distinguishable, with no change to canonical model artifacts;
- startup/failed-generation controls, independent drag/reset state, and
  explicit selection remain unchanged;
- focused raster-occlusion tests, the full Python suite, byte-compilation,
  diff checks, and a desktop Tk smoke pass.

Explicit non-goals: new geometry, camera redesign, photorealistic rendering,
free-text generation, candidate ranking, child testing, Studio automation,
export, purchasing, publishing, or changes to the local-redesign coordinate
convention.

Observed results (2026-09-03):

- the comparison canvases now resolve each pixel against the projected face
  depth, so nearer stepped and gatehouse panels occlude farther faces even
  when the input polygon order is reversed;
- depth interpolation uses the existing orthographic projection and leaves
  canonical models, camera state, fitting, drag/reset, and selection artifacts
  unchanged;
- a focused overlapping-face regression passes, along with the existing
  orientation, candidate, and selection coverage;
- 139 Python tests pass with one known bundled-runtime Tk skip, 9 desktop
  selector tests pass including the real Tk smoke, byte-compilation, and diff
  checks pass.

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

#### 3D third bounded slice: offline candidate-set and selection receipt

Status: verified (2026-09-02).

Expose the already verified fixture-driven candidate-set replay and explicit
selected-candidate receipt through the existing restricted Pi adapter. The
adapter may receive only checked-in fixture identifiers and an explicit stable
candidate id; it must create all replay and selected-bundle artifacts beneath
its caller-provided run root. Preserve the existing deterministic Python
candidate replay, fixture selector, and selection-bundle contracts.

Acceptance gates:

- Pi exposes narrowly named candidate-set replay and explicit candidate
  selection domain tools in addition to the existing surface, while
  `noTools: "builtin"` remains configured and no generic shell or filesystem
  tool is introduced;
- a real scripted offline Pi `AgentSession` replays the declared candidate set,
  selects an explicit valid stable id, and produces an auditable selection
  receipt whose source and selected artifacts remain under its run root;
- invalid fixture identifiers, invalid candidate ids, and path-escape attempts
  are rejected without creating output outside the supplied run root;
- existing fixture selector, Python candidate replay and receipt tests,
  adapter/session tests, and Hermes behavior remain passing.

Explicit non-goals: live provider calls or credentials, free-text candidate
generation, ranking or automatic selection, Pi-driven UI changes, Studio
automation, arbitrary filesystem or shell access, new LEGOization shapes, and
changes to the deterministic Python core or fixture selector.

Observed results (2026-09-02):

- `brick_demo_candidate_set` accepts only the checked-in
  `towers-with-gatehouse` fixture and writes its replay at
  `runRoot/candidate-set`; `brick_select_candidate` accepts only one of the
  three declared stable ids and derives both the source and receipt destination
  under that same root;
- the Pi configuration still uses `noTools: "builtin"`; the adapter adds no
  general shell or filesystem operation. TypeScript tests cover direct replay
  and selection plus real scripted-session call sequences, rejected fixture/id
  values, and run-root read containment;
- the verified repair below resolves the broken transitive runtime dependency
  and terminal provider outcome classification; all 10 emitted Node adapter
  tests now pass alongside the Python suite and TypeScript type-check.

#### 3D third-slice repair: restore pinned Pi-session test runtime

Status: verified (2026-09-02).

Repair only the broken transitive runtime dependency that prevents the
already-pinned Pi adapter from loading its real offline session tests. Preserve
the direct Pi package pins, the restricted domain-tool surface, and all
existing Python behavior. The repair must be lockfile/package-resolution
bounded; it must not patch `node_modules`, vendor third-party code, widen Pi
permissions, or change application behavior.

Acceptance gates:

- a clean frozen-lockfile installation supplies the module imported by the Pi
  dependency graph, without committing generated dependency directories;
- TypeScript type-check and emitted Node tests run the real offline
  `AgentSession` suite, including candidate replay and explicit receipt
  selection, without provider credentials or network calls;
- direct Pi packages remain exact-pinned at `0.84.4`; no shell/filesystem tool,
  live provider, credential, or UI behavior is introduced;
- Python suite, byte-compilation, and diff checks remain passing.

Explicit non-goals: changing application source to work around third-party
package internals, updating Pi to a different release, adding dependencies for
unrelated features, modifying the deterministic Python core, or committing
`node_modules`, `dist`, or package-store artifacts.

Observed results (2026-09-02):

- the workspace-level pnpm override resolves the exact Pi packages' broken
  transitive `typebox@1.3.7` request to the compatible `typebox@1.3.6`; the
  two direct Pi package pins remain exactly `0.84.4` and the direct
  `@sinclair/typebox` declaration remains unchanged;
- a clean frozen-lockfile installation and emitted Node runner now load and
  execute the real offline Pi session suite. Package-store hard links require
  the runner to execute outside this worktree's restricted filesystem sandbox;
  this is an execution boundary, not a new application permission.

#### 3D third-slice repair follow-up: scripted provider terminal outcome

Status: verified (2026-09-02).

Correct the Pi-session outcome classification only if the real pinned Pi
runtime records a scripted provider failure as a terminal event without
throwing from `prompt()` or `waitForIdle()`. Preserve the existing outcome
artifact format, restricted tool surface, and cancellation behavior.

Acceptance gates:

- the scripted provider-failure case records `provider-error`, while the
  existing success, malformed-call, exhaustion, and cancellation cases retain
  their asserted statuses;
- the emitted Node test suite passes under an execution environment permitted
  to read the lockfile-installed package store; no live provider or credential
  is used;
- Python tests, type-checking, byte-compilation, and diff checks pass.

Explicit non-goals: changing Pi versions or dependencies, generalizing error
handling outside the scripted session wrapper, changing tools, or adding live
provider behavior.

Observed results (2026-09-02):

- the session wrapper now recognizes Pi's terminal assistant message with
  `stopReason: "error"` as `provider-error`, while cancellation retains
  precedence and successful scripted sessions remain `completed`;
- all 10 emitted Node adapter tests pass, covering the new candidate replay and
  selection receipt flow plus success, malformed calls, exhaustion,
  cancellation, and provider failure. No provider credentials or network calls
  are used by those sessions.

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

#### 3E first bounded slice: offline render-evidence contract

Status: verified (2026-09-02).

Extend the checked-in offline demo replay with one deterministic
`render-evidence.json` artifact. It must record the fixed camera identifiers,
render file hashes, rendered part identifiers, and conservative projected
evidence for each camera (visible polygon count and non-background bounds).
The artifact is an auditable input to a later visual critique; it is not a
claim that the model resembles its request.

Acceptance gates:

- repeated fixed-input demo replays produce byte-identical render evidence and
  retain the existing fixed SVG render outputs;
- the successful demo records evidence for front and three-quarter cameras,
  with non-empty, distinct projections and the accepted model's part ids;
- failed or unsupported scaffolds stop before render evidence and final LDraw,
  retaining the current actionable failure path;
- the manifest includes render evidence, while existing deterministic
  LEGOization, validation, Pi, Hermes, and renderer behavior remain passing.

Explicit non-goals: live model or vision-provider calls, semantic resemblance
scores, automatic revision, new camera controls, UI changes, Studio automation,
new LEGOization shapes, and child testing.

Observed results (2026-09-02):

- successful replays now write deterministic `render-evidence.json` entries
  for the existing `front` and `three-quarter` SVG cameras, including each
  file's SHA-256, rendered part ids, polygon count, and projected bounds;
- repeated replays yield byte-identical evidence, and the manifest hashes the
  new artifact alongside the unchanged render files;
- unsupported scaffolds still stop before final LDraw, SVGs, or render
  evidence; 60 Python tests, byte-compilation, and diff checks pass;
- this is rendering provenance only, not a resemblance score or automated
  visual critique.

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

## Recent completed work and next recommended task

### 3D third bounded slice: offline end-to-end demo replay

Status: verified (2026-09-01).

Build one replayable, no-credential demonstration that connects the already
implemented layers: a checked-in creative request and brief, an inspectable
axis-aligned spatial scaffold, deterministic LEGOization, canonical validation
and analysis, deterministic LDraw compilation, fixed-view render output, and a
complete per-run manifest. The request-to-brief and brief-to-scaffold inputs
may be scripted fixtures for this first demonstration; this slice proves the
artifact chain and its boundaries, not live model quality.

Acceptance gates:

- one checked-in demo request produces a contained run directory with every
  named stage artifact and stable hashes for deterministic outputs;
- the recorded scaffold is passed to the existing LEGOization path, and the
  accepted assembly is independently validated, analyzed, compiled, and
  rendered from fixed views;
- a deterministic failed or unsupported scaffold stops before final LDraw
  output with actionable evidence, rather than producing a claimed successful
  demo;
- the Pi adapter can expose the demo only through its existing restricted
  domain surface or a narrowly documented domain operation; it gains no shell
  or arbitrary filesystem capability;
- existing Python, Pi adapter, Hermes, renderer, and two-depth scaffold
  behavior remain passing and unchanged outside this composed path.

Explicit non-goals: a live provider or credentials, freeform generation,
production brief/scaffold schemas, UI refinement, Studio automation, broad
new LEGOization shapes, visual critique, and child testing.

Observed results (2026-09-01):

- `demo-replay` composes checked-in request and brief fixtures, the existing
  two-stud scaffold tiler, canonical validation and analysis, deterministic
  LDraw compilation, two fixed-view SVG renders, and a hashed manifest under
  one fresh run directory;
- the depth-three fixture records coverage and `failure.json`, then stops
  before creating `final.ldr`; it does not present a partial assembly as a
  successful demo;
- the existing five-tool Pi adapter, Hermes files, renderer behavior, and
  deterministic tilers were left unchanged; 60 Python tests, compilation, and
  diff checks pass.

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

### 3D fourth bounded slice: offline brief-to-candidate agent contract

Status: verified (2026-09-02).

Move one step beyond replay-only fixtures without introducing a live provider:
through a real, scripted Pi `AgentSession`, allow the model to submit a small,
validated creative brief and request a declared candidate set from a bounded
vocabulary of already supported scaffold families.  The result must retain the
existing candidate replay, validation, compilation, render-evidence, manifest,
and selection contracts.  This slice establishes the agent-facing creative
handoff and repair boundary; it does not claim open-ended natural-language
design ability.

Acceptance gates:

- a scripted Pi session can submit a schema-validated brief for one supported
  small-building request and create the existing declared candidate set inside
  its confined run root;
- malformed or unsupported briefs yield actionable tool results and a bounded
  repair/exhaustion outcome, with no candidate artifacts presented as success;
- the session remains restricted to explicit Brick Builder domain tools, with
  no Pi built-ins, shell, arbitrary filesystem access, credentials, network,
  ranking, or automatic selection;
- accepted output is traceable from brief through candidate-set index to its
  existing validation, LDraw, render-evidence, and manifest artifacts;
- the deterministic Python core, existing replay fixtures, selector, Hermes
  integration, and current Pi session tests retain their behavior.

Explicit non-goals: a live provider call, unrestricted free-text
interpretation, automatic shape invention, arbitrary scaffold geometry,
semantic resemblance scoring, visual critique, Pi-driven editing, Studio
automation, child testing, purchasing, publishing, and external export.

Observed results (2026-09-02):

- the Pi adapter accepts only a schema-validated `brick-builder.demo-brief/v1`
  brief for `small-building-tower`, persists it under the caller run root, and
  maps requests to the checked-in three-choice tower fixture without accepting
  model-controlled paths, ranking, or selection;
- real scripted Pi `AgentSession` tests cover malformed repair, bounded
  exhaustion without candidate artifacts, and successful traceability through
  candidate index, validation, LDraw, render-evidence, and manifest artifacts;
- the explicit domain-only tool surface and `noTools: "builtin"` remain in
  force; no live provider, credentials, network, shell, or arbitrary filesystem
  operation was introduced;
- 10 compiled TypeScript tests, TypeScript type-check, and diff checks pass.
  Existing Python, replay, selector, Hermes, and core behavior were unchanged.

### MVP slice 1: natural-language request to spatial concept session

Status: verified (2026-09-02).

Begin the actual creative loop without imposing a child-facing ontology or
revision command grammar. An adult-configured provider may receive a
natural-language request and either ask one concise clarification or propose a
small, bounded set of inspectable generic-box spatial concepts. Each concept
uses stable geometry references only; any labels are model-specific and
non-canonical. The model output is schema-validated and retained as an
auditable artifact before any LEGOization attempt.

Acceptance gates:

- ordinary natural-language request text is preserved verbatim and is not
  mapped through a required list of child-facing intent labels or revision
  commands;
- a bounded agent session records either an actionable clarification or two or
  three distinct generic-box concept proposals with stable geometry references,
  bounded dimensions, and reproducible renders;
- malformed, out-of-bounds, or unsupported spatial proposals produce
  actionable feedback to the model and exhaust within a fixed attempt limit;
- the existing spatial-focus contract can select a region of a proposed
  concept, retain hard locks, and record an ordinary-language local-redesign
  request with visible spillover and exact undo;
- live provider use is explicit adult configuration. Scripted offline sessions
  remain the required automated evidence; no credentials are committed, and Pi
  retains only explicit domain tools with no shell or arbitrary filesystem
  access.

Explicit non-goals: a universal semantic ontology, a required command grammar,
claims that every request is understood, unrestricted geometry, automatic
whole-model rewrites after a concept is selected, child testing before the loop
is coherent, Studio automation, purchasing, publishing, or physical-build
claims.

Observed results (2026-09-02):

- `brick_builder.spatial_concept` preserves request text verbatim and validates
  either one clarification or two/three generic-box concepts with stable safe
  identifiers, bounded dimensions, fixed camera descriptors, and actionable
  three-attempt feedback;
- the `spatial-concepts` CLI writes the validated session plus deterministic SVG
  previews under the supplied run directory, and the Pi adapter exposes it only
  through `brick_spatial_concepts` while retaining `noTools: "builtin"`;
- full Python and Pi verification now passes in the bootstrapped worktree after
  elevated frozen-lockfile setup; the Pi suite includes the real scripted
  session and concept submission coverage.

The follow-on MVP slice should connect accepted spatial concepts to progressively
broader deterministic LEGOization, while retaining the same focus/lock/local
redesign contract. This sequencing makes model understanding observable and
correctable before expanding the physical LEGO shape vocabulary.

### MVP slice 1 follow-up: accepted concept to local redesign session

Status: verified (2026-09-02).

Connect one accepted `brick-builder.spatial-concept/v1` concept to the existing
spatial-focus and local-redesign protocol. The concept remains generic-box
geometry: this slice makes selection, locks, ordinary-language local edits,
visible spillover, retry, accept, and exact undo replayable from the accepted
concept without introducing semantic part names or LEGOization.

Acceptance gates:

- an accepted concept can be restored by stable geometry references into a
  local-redesign session without changing its boxes or camera evidence;
- focus selection, hard locks, and an ordinary-language local request are
  recorded together with before/after geometry, changed ids, and spillover;
- a local proposal cannot change locked or protected boxes, retry preserves the
  focus and locks, accept records the resulting concept, and undo restores the
  exact accepted starting state;
- a bounded offline adapter/session test can perform the flow through explicit
  Brick Builder domain operations while retaining `noTools: "builtin"`;
- existing spatial-concept, local-redesign, renderer, Python, Hermes, and Pi
  behavior remains passing.

Explicit non-goals: semantic ontology or resemblance scoring, free-form whole
model regeneration, LEGOization, Studio automation, UI changes, live provider
calls, child testing, purchasing, publishing, or external export.

Observed results (2026-09-02):

- `ConceptRedesignSession` restores one accepted generic-box concept into the
  existing local-redesign contract while preserving stable boxes and camera;
- focus, hard locks, ordinary-language proposals, visible spillover, retry,
  accept, and exact undo are recorded in deterministic serialized evidence;
- the CLI persists the pre-accept state so undo remains correct across separate
  contained domain calls, and the Pi adapter exposes the flow through
  `brick_concept_redesign` with no new built-ins or filesystem surface;
- 91 Python tests and 15 Pi adapter tests pass, with TypeScript type-checking,
  byte-compilation, and diff checks passing.

### MVP slice 1 LEGOization bridge: one aligned spatial box

Status: verified (2026-09-02).

Connect one accepted generic-box concept to the existing deterministic wall-box
LEGOization path. The bridge supports exactly one axis-aligned box whose width,
depth, and height are expressed in integral studs/plates within the existing
small bounds. It records the source concept and conversion diagnostics before
returning the existing LEGO assembly, coverage report, structural validation,
and deterministic compiled output.

Acceptance gates:

- an accepted one-box concept converts to the existing wall-box scaffold with
  an explicit, reproducible unit mapping and no model-controlled filesystem
  path;
- complete target coverage and structural validity remain separate reported
  gates, and accepted output is byte-identical for repeated inputs;
- unsupported multi-box, non-integral, non-grounded, or out-of-bounds concepts
  return actionable diagnostics without presenting a partial LEGO assembly as
  success;
- a bounded offline adapter/session test can request the bridge through an
  explicit domain operation while Pi retains `noTools: "builtin"`;
- existing spatial concept, local redesign, LEGOization, renderer, Python,
  Hermes, and Pi behavior remains passing.

Explicit non-goals: arbitrary multi-box unions, semantic resemblance, shape
invention, unrestricted dimensions, automatic repair, Studio automation, UI
changes, live providers, child testing, purchasing, publishing, or export.

Observed results (2026-09-02):

- `legoize_accepted_box` maps exactly one centered, grounded generic box from
  spatial stud/plate units into the existing wall-box LEGOization path and
  retains the source concept, mapping, coverage, structural issues, and
  deterministic LDraw text;
- multi-box, non-integral, translated, ungrounded, out-of-bounds, and
  unavailable-colour inputs return actionable rejection diagnostics without a
  successful partial assembly;
- `legoize-concept` writes contained bridge evidence and `final.ldr` only for
  successful conversions, while `brick_legoize_concept` exposes the operation
  through Pi's explicit domain-only tool surface;
- 94 Python tests and 16 Pi adapter tests pass, with TypeScript type-checking,
  byte-compilation, and diff checks passing.

### MVP slice 1 LEGOization bridge: two aligned stepped boxes

Status: verified (2026-09-02).

Extend the accepted-concept bridge to exactly two generic boxes that match the
existing stepped-box LEGOization contract: a grounded base and a directly
attached, centered, narrower upper tier. Preserve explicit spatial units,
source geometry references, separate coverage and structural validity, and
contained deterministic LDraw output.

Acceptance gates:

- valid two-tier concepts map deterministically to `legoize_stepped_box` with
  no model-controlled paths or silent geometry repair;
- overlapping, gapped, miscentered, depth-mismatched, non-integral,
  out-of-bounds, or wrong-cardinality concepts return actionable diagnostics
  without successful partial output;
- a bounded offline adapter/session test can request the stepped bridge through
  an explicit Pi domain operation while retaining `noTools: "builtin"`;
- existing spatial concept, local redesign, one-box LEGOization, renderer,
  Python, Hermes, and Pi behavior remains passing.

Explicit non-goals: arbitrary multi-box unions, gatehouses, semantic
resemblance, shape invention, automatic repair, Studio automation, UI changes,
live providers, child testing, purchasing, publishing, or export.

Observed results (2026-09-02):

- `legoize_accepted_stepped_boxes` maps exactly two grounded, centered generic
  boxes with a directly attached narrower upper tier to the existing stepped
  LEGOization path, retaining source refs, explicit unit mapping, coverage,
  structural validity, and deterministic LDraw output;
- overlapping, gapped, miscentered, depth-mismatched, non-integral,
  out-of-bounds, and wrong-cardinality concepts return actionable diagnostics
  without successful partial output;
- `legoize-stepped-concept` writes contained bridge evidence and `final.ldr`
  only on success, while `brick_legoize_stepped_concept` exposes the operation
  through Pi's explicit domain-only tool surface;
- 97 Python tests and 17 Pi adapter tests pass, with TypeScript type-checking,
  byte-compilation, and diff checks passing.

### MVP slice 1 LEGOization bridge: bounded gatehouse composition

Status: verified (2026-09-02).

Extend the accepted-concept bridge to exactly three generic boxes matching the
existing gatehouse LEGOization contract: two equal grounded towers and one
full-width bridge directly attached at their top, leaving a positive opening.
The bridge retains source geometry, explicit unit mapping, separate coverage
and structural validity, and contained deterministic LDraw output.

Acceptance gates:

- valid three-box concepts map deterministically to `legoize_gatehouse` without
  semantic labels or silent geometry repair;
- tower widths/heights/depths match, the bridge spans the complete width, the
  opening is positive, all boxes are centered/aligned/grounded as required,
  and dimensions remain within the existing small bounds;
- overlapping, gapped, miscentered, non-integral, wrong-cardinality, and
  out-of-bounds concepts return actionable diagnostics without successful
  partial output;
- a bounded offline adapter/session test can request the gatehouse bridge
  through an explicit Pi domain operation while retaining `noTools: "builtin"`;
- existing spatial concept, local redesign, one-box, stepped-box, renderer,
  Python, Hermes, and Pi behavior remains passing.

Explicit non-goals: arbitrary multi-box unions, semantic resemblance, shape
invention, automatic repair, Studio automation, UI changes, live providers,
child testing, purchasing, publishing, or export.

Observed results (2026-09-02):

- `legoize_accepted_gatehouse` maps exactly two equal grounded towers plus a
  centered full-width bridge with a positive opening to the existing
  `legoize_gatehouse` path, retaining source refs, unit mapping, coverage,
  structural validity, and deterministic LDraw output;
- overlapping, gapped, miscentered, non-integral, wrong-cardinality,
  depth-mismatched, and out-of-bounds concepts return actionable diagnostics
  without successful partial output;
- `legoize-gatehouse-concept` writes contained bridge evidence and `final.ldr`
  only on success, while `brick_legoize_gatehouse_concept` exposes the bounded
  operation through Pi's explicit domain-only tool surface;
- 100 Python tests and 18 Pi adapter tests pass, with TypeScript type-checking,
  byte-compilation, and diff checks passing.

### MVP slice 1 candidate composition: supported concept families

Status: verified (2026-09-02).

Compose the supported one-box, stepped-box, and gatehouse concept bridges into
one explicit candidate-set contract. The set preserves the raw request, each
candidate's source concept and bridge evidence, stable candidate IDs, and
success/failure diagnostics. Selection is an explicit user-provided ID and
produces a provenance receipt; the system does not rank or automatically select
among candidates.

Acceptance gates:

- a bounded set of two or three accepted concepts is evaluated through the
  existing supported family bridges without changing their geometry or
  silently repairing failures;
- the candidate index records stable IDs, bridge family, status, model ID,
  artifact hashes, and actionable failure evidence under one contained run
  root;
- explicit selection accepts only a successful declared ID and records the
  source candidate-set hash, candidate artifact hashes, and selected model;
- malformed, duplicate, unsupported, or failed candidates cannot be presented
  as a successful selectable set, and no ranking or automatic selection is
  introduced;
- an offline Pi session exercises candidate composition and explicit selection
  through domain-only tools with `noTools: "builtin"`, while existing Python,
  LEGOization bridges, Hermes, renderer, and Pi behavior remains passing.

Explicit non-goals: new LEGO shapes, semantic scoring, ranking, automatic
selection, free-form candidate generation, live providers, UI changes, Studio
automation, child testing, purchasing, publishing, or export.

Observed results (2026-09-02):

- `compose_candidate_set` dispatches two or three accepted concepts in input
  order to the existing one-box, stepped-box, and gatehouse bridges without
  ranking or automatic selection;
- the CLI writes one contained `candidate-set.json`, per-candidate bridge
  evidence, successful `final.ldr` artifacts, and an explicit selection receipt
  carrying the candidate-set and artifact hashes;
- the Pi adapter exposes only the two named domain tools, keeps `noTools` set to
  `builtin`, and a real scripted `AgentSession` composes and explicitly selects
  a candidate;
- 103 Python tests and 20 Pi adapter tests pass, with TypeScript type-checking,
  byte-compilation, and diff checks passing.

### MVP slice 1 render evidence and bounded visual critique

Status: verified (2026-09-02).

Extend the composed concept-candidate path with deterministic fixed-camera render
evidence and a deliberately narrow critique contract. Successful candidates
retain per-camera render hashes, rendered part identifiers, polygon counts, and
projected non-background bounds. The critique reports auditable structural
visual signals such as silhouette occupancy, aspect ratio, and landmark
visibility; it does not claim semantic resemblance or alter a model.

Acceptance gates:

- each successful composed candidate is rendered from the existing fixed
  `front` and `three-quarter` cameras beneath its contained candidate run;
- repeated fixed-input runs produce byte-identical render files and evidence,
  while failed candidates stop before render evidence and final LDraw output;
- the critique artifact records per-candidate, per-camera evidence references
  and bounded deterministic observations without ranking or selecting a
  candidate;
- the CLI and restricted Pi path expose the evidence/critique result without
  adding shell, filesystem, network, provider, or credential access;
- existing candidate composition, LEGOization, renderer, replay, Pi, Hermes,
  and local-redesign behavior remains passing.

Explicit non-goals: vision or live model providers, semantic resemblance
scoring, automatic visual repair, candidate ranking or selection, new cameras,
new LEGO geometry, UI changes, Studio automation, child testing, purchasing,
publishing, or export.

Observed results (2026-09-02):

- successful composed candidates now receive the existing deterministic
  `front` and `three-quarter` renders beneath their contained candidate run,
  alongside per-camera hashes, rendered part IDs, polygon counts, and projected
  non-background bounds;
- repeated fixed-input candidate rendering is byte-identical, while failed
  candidates remain indexed and receive no render evidence;
- `visual-critique.json` records evidence references plus bounded deterministic
  silhouette occupancy/aspect, visible-part, and optional landmark observations
  without ranking, selection, semantic resemblance claims, or repair;
- the existing restricted Pi candidate-composition tool returns the rendering
  and critique artifacts while `noTools` remains `builtin`; 110 Python tests
  and 20 Pi adapter tests pass, with TypeScript type-checking, byte-compilation,
  and diff checks passing.

### MVP slice 1 selected candidate local redesign

Status: verified (2026-09-02).

Bind one explicitly selected composed candidate to the existing reversible
local-redesign contract. Preserve the selected candidate's canonical LEGO model
and source spatial concept, expose focus, locks, bounded proposals, retry,
accept, and exact undo, and re-run the candidate's deterministic LEGOization
bridge before committing an accepted revised assembly. A bridge rejection must
remain actionable and must not replace the current accepted assembly.

Acceptance gates:

- only a successful declared candidate ID from a successful candidate set can
  start a redesign session, with the source candidate-set hash and model ID
  retained in the session state;
- the session reconstructs the editable spatial concept from the selected
  candidate provenance and preserves hard locks, focus, bounded spillover,
  retry semantics, and exact undo;
- accepting a proposal runs the same one-box, stepped-box, or gatehouse bridge
  against the proposed concept, writes revised LEGO evidence and `final.ldr`
  only after deterministic validation succeeds, and leaves the prior accepted
  state intact on rejection;
- the CLI and restricted Pi path expose the session through named domain
  operations under the caller run root, with `noTools: "builtin"` and no live
  providers, shell, arbitrary filesystem access, ranking, or auto-selection;
- existing candidate composition, rendering, visual critique, LEGOization,
  local-redesign, replay, Pi, Hermes, and renderer behavior remains passing.

Explicit non-goals: open-ended semantic repair, new LEGO geometry, automatic
candidate selection, visual ranking, live providers, Studio automation,
child-facing UI, child testing, purchasing, publishing, or export.

Observed results (2026-09-02):

- a successful candidate-set snapshot and explicit candidate ID start a
  serializable redesign session retaining the candidate-set hash, selection
  receipt, selected family, model ID, source concept, and canonical bridge
  evidence;
- focus, locks, bounded proposals, retry, accept, and exact undo are preserved
  through the existing local-redesign contract, including locked-block and
  spillover evidence;
- accepted proposals are re-run through the original one-box, stepped-box, or
  gatehouse bridge before the revised bridge evidence and `selected-final.ldr`
  are written; non-integral proposals remain rejected with the prior accepted
  concept and proposal available;
- the restricted Pi adapter exposes the state machine through one named domain
  tool with `noTools` still `builtin`; 137 Python tests and 21 Pi adapter tests
  pass, with TypeScript type-checking, byte-compilation, and diff checks passing.

### MVP slice 1 headless child-facing controller

Status: verified (2026-09-02).

Add a small non-Tk controller that composes the supported concept candidates,
retains their fixed render/critique evidence, exposes large stable candidate
cards, and binds an explicit selection to the selected-candidate redesign
session. The controller reports proposal/acceptance state and supports restart
without claiming a visual preference or ranking candidates.

Acceptance gates:

- a fresh controller run creates the existing contained candidate, render, and
  critique artifacts and exposes stable candidate cards only after successful
  composition;
- selection is disabled before a successful candidate set, accepts only an
  explicitly named successful ID, and retains the selection receipt and
  candidate-set hash;
- bounded focus, lock, propose, retry, accept, and undo actions are delegated
  to the selected-candidate redesign contract, with proposal status and
  actionable rejection visible in the controller snapshot;
- restart clears active selection/proposal state without deleting source
  evidence, and repeated fixed-input runs remain deterministic;
- the controller is headless-testable and adds no live provider, shell,
  arbitrary filesystem, ranking, automatic selection, Studio, export, or
  unsupervised child-play capability.

Explicit non-goals: Tk or production UI, voice input, semantic resemblance
judgment, child preference evaluation, live providers, visual repair, new LEGO
geometry, Studio automation, purchasing, publishing, or export.

Observed results (2026-09-02):

- the controller creates a fresh contained generation run with the existing
  candidate-set, per-candidate bridge/final-model, fixed render, and critique
  artifacts;
- stable input-ordered candidate cards appear only after successful composition;
  the controller exposes no ranking or automatic selection;
- explicit selection starts the selected-candidate redesign session and retains
  its receipt and candidate-set hash;
- proposal, acceptance, rejection, retry, undo, and restart state are visible;
  a failed bridge preserves the proposal and accepted state, while restart
  preserves the source generation evidence;
- 121 Python tests, 21 Pi adapter tests, TypeScript type-checking,
  byte-compilation, and diff checks pass.

### Milestone 3E remaining work

Status: open; the completed slices provide the deterministic evidence boundary
but not the remaining visual-critique gates.

Still outstanding for Milestone 3E:

- semantic critique of identity, silhouette, landmarks, proportions, symmetry,
  and accidental visual artifacts; the current critique reports deterministic
  render and geometry observations without claiming resemblance;
- broader semantic critique findings into bounded visual repair operations that
  preserve successful subassemblies where possible and revalidate each revision;
- a small checked-in prompt evaluation set demonstrating improvement more often
  than regression across those visual repairs;
- supervised child-preference evidence, recorded as evaluation evidence rather
  than deterministic truth.

Studio/UI inspection, physical-build evidence, and release/publication work are
later Milestone 5 concerns and are not counted as unfinished 3E gates.

### MVP slice 2: offline critique-to-operation evaluation

Status: verified (2026-09-02).

Add a deterministic, offline contract that turns the existing render and
geometry observations into a small declared visual-operation proposal. Exercise
it with a checked-in evaluation fixture containing a baseline candidate and one
bounded revision. The operation must be explainable, applied through the
existing selected-candidate redesign path, and followed by engineering
validation; this slice measures traceability and validity, not resemblance
quality.

Acceptance gates:

- a versioned critique-evaluation artifact records the prompt fixture,
  baseline candidate, observation findings, declared operation, result, and
  engineering validation outcome;
- only a small allowlisted operation vocabulary is accepted, with explicit
  parameters and actionable rejection for unknown, malformed, or unbounded
  operations;
- a valid operation produces a fresh proposal through the existing reversible
  redesign contract, preserves the baseline evidence, and re-runs deterministic
  validation before acceptance;
- a failed operation or validation leaves the accepted baseline intact and
  retains the rejection evidence;
- repeated fixed-input evaluation is byte-identical and a small fixture reports
  improvement/regression fields without presenting them as semantic truth.

Explicit non-goals: live vision or model providers, automatic unbounded repair,
semantic resemblance scoring, ranking, child preference testing, new LEGO
geometry, UI/Tk work, Studio automation, export, purchasing, publishing, or
physical-build claims.

Observed results (2026-09-02):

- a versioned `brick-builder.critique-operation-evaluation/v1` artifact records
  the prompt fixture, selected baseline, deterministic critique observations,
  declared operation, redesign proposal, engineering validation, and result;
- only the bounded `recolor` and `increase-height` operations are accepted,
  with explicit target and parameter validation; malformed, unknown, and
  out-of-bound operations are rejected before redesign;
- accepted operations flow through the selected-candidate redesign contract,
  while failed bridge validation leaves the baseline accepted concept intact
  and records actionable rejection diagnostics;
- evaluation artifacts are canonically serializable and writable to an explicit
  path; the checked-in fixture reports engineering-validity preservation or
  loss and explicitly leaves semantic resemblance unevaluated;
- 126 Python tests, 21 Pi adapter tests, TypeScript type-checking,
  byte-compilation, and diff checks pass.

This verifies the traceable operation boundary, not the full Milestone 3E
visual-repair or evaluation gates.

### MVP slice 3: offline semantic-critique evidence fixture

Status: verified (2026-09-02).

Add a deterministic fixture-driven contract that records semantic critique
findings for one supported candidate against explicitly declared expectations.
The fixture may describe the intended identity, silhouette, landmarks,
proportions, symmetry, and accidental artifacts; the evaluator reports each
dimension as observed, missing, or not assessed from existing render/geometry
evidence. It must keep this evidence separate from deterministic engineering
validity and must not collapse findings into a resemblance score.

Acceptance gates:

- a versioned artifact records the prompt fixture, candidate and render-evidence
  references, declared expectations, per-dimension findings, and separate
  engineering-validation evidence;
- identity, silhouette, landmarks, proportions, symmetry, and accidental
  artifacts have explicit bounded fields with actionable validation for
  malformed or unsupported fixture data;
- repeated fixed-input evaluation is byte-identical, preserves source evidence
  references, and emits no rank, winner, preference, or resemblance score;
- the checked-in fixture demonstrates both a satisfied and an unsatisfied
  expectation without claiming that either is deterministic semantic truth;
- the contract remains offline and consumes existing evidence only; no visual
  provider, automatic repair, or candidate selection is introduced.

Explicit non-goals: live vision or model providers, pixel-level perception,
resemblance scoring, ranking, child preference testing, automatic repair,
critique-to-operation dispatch, new LEGO geometry, UI/Tk work, Studio
automation, export, purchasing, publishing, or physical-build claims.

Observed results (2026-09-02):

- a versioned `brick-builder.semantic-critique/v1` artifact records the prompt
  fixture, selected candidate provenance, declared expectations, per-dimension
  findings, render-evidence references, and separate engineering validation;
- the checked-in fixture reports a satisfied identity and silhouette expectation,
  an unsatisfied landmark expectation, and explicit `not-assessed` results for
  unsupported symmetry and accidental-artifact observations;
- malformed dimensions, invalid ranges, unsupported fixture keys, unsuccessful
  candidates, and missing visual-critique evidence are rejected actionably;
- repeated fixed-input evaluations are byte-identical, artifacts are writable
  to an explicit path, and the result explicitly records that resemblance was
  not evaluated or reduced to a score;
- 130 Python tests, 21 Pi adapter tests, TypeScript type-checking,
  byte-compilation, and diff checks pass.

This verifies fixture-grounded semantic evidence, not semantic truth or a
complete visual-repair evaluation.

### MVP slice 4: offline prompt evaluation set

Status: verified (2026-09-02).

Add a small deterministic evaluation-set contract over checked-in baseline and
revision evidence. Each case records a prompt fixture, the selected candidate,
the declared bounded operation, semantic-critique findings before and after,
and engineering-validation outcomes. The evaluator compares only declared
findings and validity outcomes, so it can report improvement, regression, or
unchanged evidence without ranking candidates or inventing semantic truth.

Acceptance gates:

- a versioned evaluation-set artifact records every case, its prompt and
  candidate provenance, operation-evaluation reference, before/after critique
  findings, and case outcome;
- at least one checked-in-style case reports improvement or preservation and at
  least one reports regression/rejection, with engineering validity kept
  separate from semantic-critique findings;
- case inputs validate the existing semantic-critique and critique-operation
  formats, reject duplicate or malformed cases actionably, and retain source
  hashes for deterministic replay;
- repeated fixed-input evaluation is byte-identical and the aggregate reports
  counts and evidence without ranks, winners, preference labels, or
  resemblance scores;
- the contract remains offline and does not perform new repair, selection, or
  provider calls.

Explicit non-goals: live vision or model providers, automatic repair, new LEGO
geometry, candidate ranking, child preference testing, UI/Tk work, Studio
automation, export, purchasing, publishing, or physical-build claims.

Observed results (2026-09-02):

- a versioned `brick-builder.prompt-evaluation/v1` artifact records each case's
  prompt, selected candidate, operation evidence, before/after semantic
  findings, engineering-validity comparison, outcome, and source hashes;
- the checked-in-style cases report improvement, rejection, and regression
  separately, while preserving the distinction between engineering validity and
  declared semantic findings;
- duplicate cases, prompt/candidate/hash mismatches, inconsistent operation
  status, and malformed validity fields are rejected actionably;
- repeated fixed-input aggregation is byte-identical, writable to an explicit
  path, and emits no ranks, winners, preferences, or resemblance scores;
- 134 Python tests, 21 Pi adapter tests, TypeScript type-checking,
  byte-compilation, and diff checks pass.

This verifies offline evaluation bookkeeping, not evidence that visual repairs
improve real-world resemblance or child preference.

### Test workflow slice: pytest-native test modules

Status: verified (2026-09-03).

Complete the pytest migration by converting the existing Python test modules
from `unittest.TestCase` methods to native pytest classes and assertions. Keep
the current scenarios and coverage, using pytest fixtures/setup, `pytest.raises`,
pytest skip markers, and plain assertions. The suite must have one supported
Python test framework rather than relying on pytest's unittest compatibility
plugin.

Acceptance gates:

- all existing Python test modules are collected as pytest-native tests with
  no `unittest.TestCase`, `unittest.main`, or `self.assert*` test-framework
  usage;
- setup, exception, and conditional Tk behavior retain their existing
  semantics under pytest;
- `python -m pytest -q` passes the complete suite in the core environment and
  the focused selector suite passes in the desktop environment;
- no production dependency, product behavior, test scenario, or integration
  boundary changes.

Explicit non-goals: new test scenarios, third-party pytest plugins, product
changes, UI changes, and changes to the deterministic test fixtures.

Observed result: all 22 Python test modules are pytest-native. The strict core
run with pytest's unittest compatibility plugin disabled passes with 138 tests
passed and 1 expected Tk smoke-test skip; the focused desktop selector run
passes 9 tests in the real Tk environment. The repository contains no
unittest test-framework imports or compatibility constructs. Mocking uses
pytest's built-in `monkeypatch` and `capsys` fixtures. Compilation and diff
checks also pass. No scenarios, fixtures, production code, or integration
boundaries changed.

### MVP slice 5: bounded grounded height reduction

Status: verified (2026-09-02).

Add one explicit visual-repair operation, `decrease-height`, for a selected
one-box candidate. It accepts an integral reduction in plates within a small
bound, preserves the box's grounded origin, and routes the resulting proposal
through the existing reversible selected-candidate redesign and LEGOization
bridge. This is an operation contract and validity demonstration, not a claim
that shorter is visually better for every prompt.

Acceptance gates:

- the operation has a versioned, explainable artifact with target block,
  bounded integral amount, before/after proposal, and engineering validation;
- a valid reduction creates an accepted, grounded candidate with a changed
  height and preserves the baseline evidence for comparison;
- reductions that would violate the positive-height bound or any bridge rule
  are rejected without changing the accepted baseline and retain diagnostics;
- malformed, unknown, fractional, negative, and over-bound parameters are
  rejected actionably;
- repeated fixed-input repairs are deterministic and add no ranking,
  resemblance score, automatic selection, or child-preference claim.

Explicit non-goals: general visual repair planning, multi-box height edits,
semantic quality claims, live vision or model providers, automatic unbounded
repair, new LEGO geometry, child testing, UI/Tk work, Studio automation,
export, purchasing, publishing, or physical-build claims.

Observed results (2026-09-02):

- the versioned `brick-builder.bounded-visual-repair/v1` artifact records the
  selected candidate, integral reduction, baseline bridge evidence, explicit
  before/after proposal, bridge result, grounding result, and safety claims;
- a one-plate reduction changes a grounded one-box candidate from height 3 to
  height 2 and is accepted through the selected-candidate redesign session and
  existing LEGOization bridge validation;
- zero, negative, fractional, non-integer-typed, over-bound, and
  positive-height-violating reductions are rejected with baseline preservation
  and actionable diagnostics;
- repeated fixed-input repairs are deterministic and make no ranking,
  resemblance, or child-preference claim;
- 137 Python tests, 21 Pi adapter tests, TypeScript type-checking,
  byte-compilation, and diff checks pass.

This verifies one bounded repair operation, not broad visual-repair quality.

### Test workflow slice: pytest runner

Status: verified (2026-09-03).

Make pytest the supported Python test runner without changing the existing
test coverage or product behavior. Add a project test extra and pytest
discovery configuration, update the development/worktree instructions, and
verify that the complete suite runs through `python -m pytest`.

Acceptance gates:

- a fresh test-capable editable install provides pytest through a declared
  optional dependency;
- pytest discovers and passes the complete existing Python suite, including
  the conditional Tk smoke behavior;
- documented commands no longer require `unittest discover`;
- no test coverage, product dependency, runtime behavior, or roadmap scope is
  changed by the runner migration.

Explicit non-goals: rewriting every existing assertion into pytest style,
new fixtures, plugin adoption, product changes, UI changes, and new test
scenarios.

Observed results (2026-09-03):

- `pytest>=8,<9` is declared in the optional `[test]` extra and pytest is
  configured to discover the existing `tests/test_*.py` suite;
- `python -m pytest -q` passes with 138 tests and one expected bundled-runtime
  Tk skip; the desktop `.demo-venv` selector path passes all 9 focused tests;
- development, fresh-worktree, and local-redesign instructions now use pytest
  commands, while the existing test coverage and test behavior remain intact;
- no production dependency, product runtime, UI behavior, or integration
  boundary changed. The test classes remain unittest-compatible as an
  intentionally bounded migration step.

## MVP delivery reset: work that must happen before another child test

The local-redesign probe has answered its narrow question: spatial focus, hard
locks, disclosed spillover, retry, accept, and undo are directionally the right
interaction model. It is not a child-ready product and must not receive further
UI polish before the system can show a result genuinely tied to an ordinary
language request.

The immediate target is one adult-supervised, live, end-to-end vertical run:

```text
ordinary language request
  -> live configured model proposes bounded spatial concepts
  -> deterministic concept validation and LEGO candidate composition
  -> visible candidate renders and explicit choice
  -> contained evidence and LDraw output for adult inspection
```

This is a narrow proof that the central product promise works. It is not a
claim that every request is understood, that the system is ready for unsupervised
child use, or that the supported shapes are already broad enough for creatures
and vehicles.

### Delivery slice 1: adult-configured live concept-to-candidate run

Status: implementation complete; manual live smoke verified (2026-09-03). The
compiled Pi runtime suite is verified. This supersedes the previous
recommendation to run a child-preference evaluation now.

Use the existing restricted Pi agent and spatial-concept/candidate contracts
with one real, adult-configured model provider. Given ordinary request text,
the agent must either ask one concise clarification or use only explicit Brick
Builder domain tools to submit two or three bounded generic-box concepts and
compose them into supported LEGO candidates. The run must save its request,
model/tool trajectory, concepts, validation feedback, candidate renders,
selection-ready index, and LDraw artifacts under a fresh caller-owned run
directory.

Acceptance gates:

- an adult can supply a provider/model configuration outside the repository and
  launch one documented local command with ordinary request text;
- one real provider session completes a contained run that records either an
  actionable clarification or two/three valid, visibly distinct LEGO candidate
  outputs derived from the model's submitted concepts;
- malformed or unsupported concept proposals return deterministic feedback to
  the same bounded session; exhaustion and provider failure retain usable
  diagnostics and never present a successful candidate set;
- Pi exposes only named Brick Builder domain tools, keeps `noTools: "builtin"`,
  does not provide generic shell/filesystem access, and records no credentials
  in artifacts, commits, logs, or documentation examples;
- existing offline scripted sessions remain the automated test contract. The
  live run is a manual adult-supervised smoke, not a CI dependency;
- the result can be opened or inspected as LDraw by an adult, with engineering
  validation reported separately from any claim of resemblance.

Explicit non-goals: provider-specific credentials in source control, automatic
purchase/publish/export, unrestricted geometry, universal semantic ontology,
model ranking, automatic candidate selection, child-facing UI polish, child
testing, Studio automation, or claims of physical buildability.

The checked-in implementation is documented in
[`docs/live-run.md`](live-run.md). It uses an external provider configuration
whose credential is named by an environment variable, creates a caller-owned
Pi runtime with `noTools: "builtin"`, preserves the raw request and sanitized
trajectory, and writes a selection-ready candidate index without selecting a
candidate. A real provider smoke still requires an adult-supplied configuration
and must be reported separately from the offline automated evidence.

#### Delivery slice 1 verification recovery

Status: verified (2026-09-03); the manual provider smoke also passed and the
path may proceed to Delivery slice 2 after the follow-up below is tracked.

The root integrator requested elevated access for the actual compiled Pi runtime
command, ran the documented offline frozen-lockfile setup and emitted Node test
suite in that same environment, and recorded 31 passing tests with zero
failures. The Python suite recorded 138 passing tests and one expected skip.
The same adult-supervised live request then completed on its second bounded
session, producing two successful candidates with renders and LDraw artifacts.
The unresolved local package-link report is not a product diagnosis and must
not be handed to the owner as an action item. If elevation is denied or the
runtime suite still fails after correct elevated setup, retain the exact output
as a reproducible verification failure and stop this delivery path pending
root investigation.

#### Delivery slice 1 follow-up: isolate proposal artifacts and propagate palette color

Status: verified (2026-09-03); the bounded live smoke, offline Python suite,
and compiled Pi runtime suite all pass for this slice.

The live smoke exposed two bounded implementation gaps:

- each repair proposal writes candidate directories beneath the same run root,
  while later proposals overwrite the root-level candidate index. Historical
  proposal directories therefore remain mixed with the final candidate set;
- the model's source hex color is retained in concept and bridge evidence, but
  the LEGOization bridges currently default every emitted part to LDraw color
  `4` (Red), so a requested supported color such as Green is silently replaced.

Acceptance gates:

- each proposal is either isolated under an explicit attempt/proposal evidence
  path or removed from the final presentation with a manifest that clearly
  distinguishes historical evidence from the final candidate set;
- a supported requested color is mapped deterministically to the palette's
  LDraw color code, recorded as both source and mapped color, and applied to
  every emitted part; unsupported or ambiguous colors fail explicitly rather
  than silently falling back to Red;
- failed historical candidates retain their diagnostics and do not receive
  `final.ldr`, while the final selection-ready index references only the latest
  successful candidates;
- focused regression tests cover proposal artifact isolation, green-color
  propagation, and the existing no-ranking/no-automatic-selection boundary.

Implementation notes (2026-09-03): live attempts now write under distinct
`attempts/attempt-NN/` roots, and repeated candidate proposals within an attempt
write under distinct `proposals/proposal-NN/` roots. The root
`selection-ready.json` points only to the successful candidates from the final
proposal. Earlier attempts and failed proposals remain auditable without being
mixed into the presented candidate set. Source hex colours are resolved against
the active palette's named colours; the mapping records source and LDraw colour
code, and unsupported or mixed colours are rejected. The focused Python suite
passes with 143 passed and one expected skip; the elevated compiled Pi runtime
suite passes all 33 tests. A fresh adult-supervised live smoke for “Make a tiny
green lookout tower” succeeded on attempt 1 with three candidates, each mapped
from `#2e8b57` to LDraw code `2` and each producing `final.ldr`. A bridge-shaped
smoke also remained correctly bounded and auditable when its proposals were
rejected for geometry diagnostics.

Explicit non-goals: ranking or automatic selection, expanded geometry families,
arbitrary colors outside the supported palette, inventory claims, purchasing,
publishing, or child-facing UI changes.

#### Delivery slice 1.5: keep internal bridge families out of general live generation

Status: verified (2026-09-03); the neutral live-provider smoke and offline
regression gates pass.

Bound the next cleanup around the live model boundary. The general live concept
proposer should receive one neutral candidate-composition tool, neutral geometry
guidance, and neutral validation feedback. Existing one-box, stepped-box, and
gatehouse bridges remain available to the deterministic compiler and offline
fixture workflows, but their implementation names must not prime or constrain
ordinary live requests.

Acceptance gates:

- the live Pi session exposes no family-specific bridge tools or family-specific
  names in its system prompt;
- the live candidate-composition result hides internal family/model identifiers
  from the model while retaining full family-specific evidence on disk for
  deterministic selection and redesign;
- neutral live generation still supports two or three distinct candidates,
  deterministic validation/repair, isolated artifacts, explicit selection, and
  the existing no-ranking/no-automatic-selection boundary;
- regression tests prove that fixture-only family vocabulary remains available
  to offline workflows but is absent from the live model-facing tool surface.

Explicit non-goals: redesigning the deterministic bridge families, expanding the
part catalog or geometry vocabulary, adding semantic family classification,
ranking, automatic selection, UI work, purchasing, publishing, or Studio
automation.

Implementation notes (2026-09-03): the live session now supplies only the
neutral candidate-composition tool and uses neutral grounded/grid-alignment
guidance. Its model-visible result is a projected status/diagnostic/hash view;
the raw candidate-set artifact still retains family, model, bridge, and source
evidence for explicit selection and redesign. The full tool surface and named
family behavior remain available to offline fixture and deterministic tests. The
elevated compiled Pi runtime suite passes all 35 tests, the Python suite passes
143 tests with one expected skip, and a fresh adult-supervised “Make a tiny red
lookout tower” smoke succeeded on attempt 2 without exposing the internal family
vocabulary to the live tool surface. Its root selection index resolved to the
nested successful proposal artifact.

#### Delivery slice 1.6: reject geometrically duplicate live candidates

Status: verified (2026-09-03); duplicate geometry is rejected and the live
repair path produces distinct candidates.

Require candidate diversity to be based on normalized geometry rather than
provider-chosen names, refs, or camera labels. Identical box geometry should
produce an actionable deterministic diagnostic and cause the bounded live
session to repair the set, while materially different geometry remains in the
declared input order.

Acceptance gates:

- duplicate geometry is detected independent of candidate ID, label, geometry
  refs, or render camera;
- rejected duplicates retain diagnostics and do not produce misleading final
  artifacts, while the model receives enough neutral feedback to repair them;
- distinct candidates continue to preserve their raw source concepts, mapped
  colors, LDraw output, and explicit-selection provenance;
- regression coverage proves duplicate rejection, deterministic hashing, and
  preservation of the no-ranking/no-automatic-selection boundary.

Explicit non-goals: ranking candidates, choosing the most different option,
semantic similarity or visual-quality scoring, new geometry families, UI work,
purchasing, publishing, or Studio automation.

Implementation notes (2026-09-03): candidate composition now derives a
deterministic geometry-only hash from normalized box centers and sizes, sorted
independently of box refs, candidate identity, labels, colors, and render
cameras. A later matching candidate is retained as failed raw evidence with an
actionable `DUPLICATE_GEOMETRY` diagnostic; the first occurrence and all
materially different candidates remain in input order. Focused candidate
composition tests cover metadata/order independence, deterministic hashes, and
the existing explicit-selection/no-ranking boundary. No Pi prompt or UI change
was made. The full Python suite passes with 145 tests and one expected skip, and
the elevated compiled Pi runtime suite passes all 35 tests. A fresh
adult-supervised “A small green beam bridge” smoke succeeded on attempt 1 after
repair, with three unique geometry hashes and three unique emitted `.ldr`
hashes.

### Delivery slice 2: live focused redesign of a selected concept

Status: planned; start only after Delivery slice 1 passes its live smoke.

Connect the same adult-configured live session to the existing selected-candidate
redesign contract. After an adult explicitly chooses a candidate and supplies a
spatial focus and optional locks, an ordinary-language local request must cause
the model to submit one bounded replacement spatial proposal. The system must
show before/after geometry, disclose spillover, preserve locks, re-LEGOize and
validate on acceptance, and retain exact undo.

Acceptance gates:

- one real live session demonstrates candidate choice, focus, an
  ordinary-language local request, a bounded visible proposal, accept or undo,
  and a revalidated LDraw result;
- locked geometry is never changed; any spillover is explicit; a rejected
  bridge/validation result leaves the previous accepted candidate intact;
- the live session records model/tool trajectory and diagnostics, while the
  automated suite covers equivalent scripted success, rejection, exhaustion,
  and provider-failure paths;
- no generic Pi tools, credential persistence, whole-model silent rewrite,
  ranking, purchasing, publishing, or Studio automation is introduced.

### Delivery slice 3: minimal showcase surface and supervised child trial

Status: planned; start only after Delivery slice 2 produces a result worth
showing.

Make the smallest local screen that invokes the proven live path and displays
the resulting candidate cards plus the existing focus/lock/before-after/undo
state. Do not add visual polish, voice, accounts, publishing, or broad settings.
Use it for one supervised child session and record whether the child recognizes
an idea, chooses a candidate, understands a focused revision, and enjoys the
result. Treat the observations as product evidence, not deterministic labels.

## Handoff rules for delivery slices

Each delivery slice is implementation work. A Luna High orchestrator owns the
slice end to end: it must first delegate one bounded implementation attempt to
a Luna Medium subagent, independently review and verify the result, and report
the exact live/manual evidence separately from automated evidence. The root
integrator retains authority for commits, pushes, and any network/elevation
request. Do not begin a later delivery slice while the prior slice is
uncommitted, unverified, or lacks its stated live smoke evidence.
