# Brick Builder project roadmap and handoff

Status: active planning record, last updated 2026-08-31.

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
- a portable Hermes skill and live Hermes smoke test.

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
    -> bounded creative brief
    -> semantic component graph
    -> coarse stud-grid spatial scaffold
    -> LEGO part assembly
    -> deterministic validation and repair
    -> fixed-view renders and visual critique
    -> child selection and revision
    -> final Studio inspection and adult-controlled export
```

The semantic and spatial layers are missing today. They are the next product
risk to address.

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

### Milestone 3A: design-intent representation

Define a versioned representation between natural language and individual LEGO
parts. Begin with one family, preferably a simple creature, rather than trying
to cover creatures, vehicles, and buildings simultaneously.

The representation should include:

- semantic components such as body, head, tail, legs, wings, and eyes;
- parent/attachment, symmetry, ordering, and grounding relationships;
- component importance and recognizability priorities;
- coarse dimensions and positions measured in studs and plates;
- landmarks such as eye positions, tail tip, feet, and wing tips;
- target front, side, top, and three-quarter silhouettes where useful;
- global part-count, size, palette, colour, and style constraints.

Deliver hand-authored examples before asking a model to create these documents.

Acceptance gates:

- the schema can express at least three visibly different small creature plans;
- invalid component relationships produce actionable diagnostics;
- a human can inspect the document and understand the intended 3D composition;
- tests cover versioning, bounds, symmetry, attachment references, and required
  landmarks;
- no LEGO part placement is required to judge whether the plan resembles its
  brief.

### Milestone 3B: spatial scaffold renderer

Turn a design-intent document into a simple, deterministic 3D proxy composed of
boxes, wedges, spines, or occupied stud-grid cells. Produce fixed-camera renders
or another readily inspectable representation.

Acceptance gates:

- front, side, top, and three-quarter views are reproducible;
- component colours or labels make the semantic decomposition obvious;
- dimensions and landmarks agree with the structured document;
- the home beta tester can distinguish intentionally different concepts before
  any LEGO filling occurs.

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

### Milestone 3D: Pi parity slice

Reproduce the bounded Hermes workflow in Pi without changing the Python core.
The initial tool surface should be domain-specific, approximately:

- inspect the supported palette;
- submit or revise a bounded creative brief;
- submit or revise a design-intent document;
- generate or inspect a spatial scaffold;
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
4. Give each subagent one independent deliverable: implementation, tests,
   reference examples, or review. Avoid an indefinitely running subagent that
   accumulates the whole project history.
5. Keep one root agent responsible for integration, verification, and the final
   commit for that slice.
6. Commit coherent increments as they pass their acceptance gates.
7. At the end of the task, update `Current verified state`, the applicable
   milestone, and `Next recommended task` below.

Use a continuation in the same task for immediate debugging of work that task
just performed. Start a new task when changing milestones, when the required
context is already in the repository, or when the conversation has accumulated
substantial exploratory history unrelated to the next implementation slice.

## Next recommended task

Implement only Milestone 3A: the design-intent representation for one constrained
creature family.

Before implementation, decide the smallest useful creature vocabulary and write
three hand-authored concepts, including a simple dragon-like example. Do not add
Pi, visual-model calls, general text-to-3D generation, or LEGOization in that
task. The output should be a reviewable semantic/spatial plan, its schema,
validation, examples, and tests.

Suggested opening prompt for the fresh task:

> Read `AGENTS.md`, `PROJECT_BRIEF.md`, `docs/project-roadmap.md`,
> `docs/design-conventions.md`, and the active palette completely. Implement
> only Milestone 3A from the roadmap, including its hand-authored examples,
> validators, tests, documentation update, and a coherent git commit. Preserve
> the existing deterministic model and Hermes integration. Use subagents only
> for bounded independent implementation, test, or review work.
