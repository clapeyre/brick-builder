# Brick Builder project brief

## Vision

Build a child-friendly agentic system that turns a creative request such as "a tiny red dragon with wheels" into a small selection of attractive, physically plausible LEGO models. A child can select a candidate, ask for simple changes, and—with adult involvement—export the result to BrickLink Studio with a parts list and building instructions.

The project is also a personal re-entry exercise in agentic engineering, drawing on the owner's background in computational physics, simulation, and AI for science. It is intended to become a public GitHub project and may continue beyond the initial sequence of work if the home beta tester enjoys it.

## Users

- Primary creative user and beta tester: a six-year-old child with high expectations.
- Supervising user: a parent who controls exports, publishing, purchases, configuration, and potentially unsafe or expensive actions.
- Secondary audience: developers interested in verifier-guided agents for constrained physical design.

## Agreed initial scope

- Design models using existing LEGO catalog elements, not new custom brick geometry.
- Use a constrained palette of roughly 20–50 common rigid part types.
- Focus on conventional stud-based, mostly orthogonal connections.
- Support a limited color palette and configurable part-count and size bounds.
- Begin with vehicles, creatures, and small buildings.
- Defer Technic, flexible parts, advanced hinges, custom parts, and unrestricted catalogs.
- Produce multiple visibly different candidates rather than one opaque answer.
- Provide simple revision controls such as "more silly," "stronger," "fewer pieces," and color changes.

## Proposed system shape

1. Accept a child's text or voice request.
2. Convert it into a bounded structured specification.
3. Generate a versioned LEGO design document.
4. Compile the design deterministically to LDraw.
5. Run deterministic validation and bounded repair loops.
6. Render several candidates for visual comparison.
7. Let the child choose and revise a candidate.
8. Perform a final BrickLink Studio/UI inspection.
9. Export the selected model, parts list, and instructions behind an adult-controlled action.

The structured design document—not the Studio GUI—is the canonical representation. Studio is a downstream inspection, rendering, stability/collision, and instruction environment.

## Validation layers

### Deterministic validation

- Schema and version validity
- Real part and supported color identifiers
- Legal discrete transformations
- Collision and impossible overlap
- Connection validity and connected-component checks
- Floating or unsupported subassemblies
- Approximate center-of-mass and support checks
- Part-count, size, inventory, and cost limits
- Feasible assembly ordering where possible

### Visual and Studio/UI verification

After deterministic validation, open or import the candidate in Studio and inspect the rendered model and Studio feedback. This layer should identify problems that are difficult to encode completely, including visual incoherence, obscured or inaccessible placements, surprising Studio collision/stability results, poor instruction ordering, and discrepancies between the internal representation and imported model.

This is a complementary verifier. Known geometric and catalog rules should remain deterministic and testable rather than being delegated to visual judgment.

## Ordered implementation steps

### Step 1: Deterministic design engine

- Select and license-check the initial parts/catalog data.
- Define the structured design schema and coordinate conventions.
- Compile the schema to `.ldr` or `.mpd`.
- Implement initial validators and clear failure reports.
- Create several small hand-authored reference models.
- Verify clean import into BrickLink Studio.

Initial decisions are recorded in [docs/design-conventions.md](docs/design-conventions.md). The first configurable palette proposal is the packaged [brick_builder/palettes/classic-core-v0.json](brick_builder/palettes/classic-core-v0.json). It uses LDraw identifiers, colours, units, axes, and transforms rather than introducing project-specific geometry conventions.

### Step 2: Agentic generation and repair

- Create a bounded harness adapter around the deterministic commands; retain the
  Hermes skill as a reference while evaluating Pi as the product-facing harness.
- Translate natural-language requests into bounded creative briefs, semantic
  component graphs, and coarse spatial scaffolds before placing LEGO parts.
- Generate schema-conforming candidates.
- Feed validator failures into a bounded repair loop.
- Preserve complete, reproducible run artifacts.
- Add visual diversity between candidates.

### Step 3: Child-friendly interaction

- Add a simple local interface with large controls and candidate renders.
- Support short, concrete revisions and undo/restart.
- Consider voice input after text interaction is reliable.
- Keep export, publishing, purchasing, and configuration in an adult area.

### Step 4: Studio inspection, evaluation, and hardening

- Add the Studio/UI verification pass where reliable automation is feasible.
- Maintain a representative prompt suite and measurable success criteria.
- Track validity rate, repair count, latency, connectivity, part count, and candidate diversity.
- Physically build representative outputs and record real-world failures.
- Generate useful parts lists and build instructions.
- Prepare public documentation, licensing, attribution, and a demonstration for GitHub.

## Initial success criteria

- Ordinary in-scope prompts usually produce at least one valid model without manual file editing.
- Outputs use supported real parts and colors and form an intentional connected assembly.
- Failures are captured with enough context to reproduce and diagnose them.
- A child can understand the candidate choices and request a revision in a few interactions.
- Several generated models are successfully built with physical bricks.
- The public repository contains no employer or customer material and has auditable dependency and asset provenance.

## Current harness choices

- The deterministic core is harness-agnostic. Pi is the leading direction for a
  minimal shipped agent; Hermes Desktop/Hermes Agent remains the proven reference
  integration until a Pi vertical slice reaches parity.
- Begin with one orchestrating agent and precise local tools. Introduce specialist agents only in response to measured failure modes.
- Codex and the owner's personal ChatGPT subscription may be used to develop the project. Direct API-backed runtime functionality may involve separate provider configuration or billing and should not be assumed to be included automatically.
- Keep the deterministic core harness-agnostic. Publish useful integration assets such as skills and selected portable context/configuration files, but leave provider choice and broader harness deployment to users; a comprehensive beginner deployment tutorial is not an initial goal.

The detailed current sequence and task handoff are maintained in
[docs/project-roadmap.md](docs/project-roadmap.md).
