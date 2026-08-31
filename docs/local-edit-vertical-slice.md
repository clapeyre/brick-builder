# Local redesign vertical slice

Status: interaction proposal for review, 2026-08-31.

## Question being tested

Can a user improve one recognizable area of a rough 3D concept without asking
the model to regenerate the whole design and without defining a universal
ontology of animals, vehicles, buildings, or their parts?

The initial scenario is deliberately concrete:

> Generate a crude blocky vehicle, select its front, ask "make this look like a
> grille," review only the local change, then accept, retry, or undo it.

This scenario is an interaction probe. It does not commit the product to a
vehicle-only vocabulary or require the current LEGO palette to build the final
vehicle.

## Proposed user flow

1. The system proposes a few inexpensive whole-model blockouts.
2. The user chooses one as the persistent starting concept.
3. The user selects an editable spatial region by clicking, brushing, lassoing,
   or accepting an agent-suggested boundary.
4. The user describes the desired local change in ordinary language.
5. The system makes a proposal subject to an explicit edit boundary.
6. The interface shows the original and proposed versions and identifies what
   changed and what was preserved.
7. The user accepts the proposal, retries within the same boundary, adjusts the
   boundary, or undoes the edit.

Whole-model generation is useful during exploration. After the user selects a
concept, local redesign is the default. A local request must not silently turn
into another whole-model generation.

## Minimal edit contract

The protocol is spatial and model-specific. Region labels such as `front area`,
`head`, `tower`, or `engine` are free text, not members of a global ontology.

Every proposed local edit records:

- `selection`: the cells, primitives, parts, or bounding volume that may change;
- `instruction`: the user's requested change;
- `protected`: geometry outside the editable region that must remain unchanged;
- `boundary`: attachment surfaces or interfaces that the replacement must
  preserve;
- `invariants`: selected properties such as overall width, symmetry, ground
  clearance, or camera-facing orientation;
- `expansion_limit`: how far the proposal may extend beyond the selection;
- `before` and `after`: reproducible references to the affected geometry;
- `result`: accepted, retried, rejected, or undone.

Example:

```json
{
  "selection": {
    "label": "front region",
    "geometry_ref": "concept-a/region-4"
  },
  "instruction": "Make this look like the front grille of a friendly little delivery truck.",
  "protected": ["cab", "chassis", "wheels"],
  "boundary": ["rear attachment plane"],
  "invariants": ["overall width", "left-right symmetry", "ground clearance"],
  "expansion_limit": {
    "studs": 1
  }
}
```

The exact JSON shape is intentionally not yet a schema. It exists to make the
interaction testable before implementation decisions become durable.

## What must remain deterministic

Deterministic checks should answer engineering questions around a proposal:

- Did geometry outside the authorized selection change?
- Does the replacement still meet its recorded boundary?
- Did the proposal exceed its expansion limit?
- Did it introduce collisions, disconnections, or grounding failures?
- Can the before/after difference be reproduced and audited?

The user decides whether the result actually resembles a grille, head, tail, or
other desired feature. The system should not disguise that design judgment as a
deterministic validity claim.

## First prototype acceptance gates

- A user can distinguish exploration, selection, and review states.
- The selected region and protected remainder are visually unambiguous.
- The proposed change is shown against the original version.
- Retry preserves the same selection unless the user explicitly changes it.
- Undo restores the exact prior concept.
- The interaction does not require predefined vehicle or creature part names.
- The recorded contract contains enough information to detect an unauthorized
  whole-model rewrite.

## Out of scope for the interaction probe

- Final LEGO part placement or LEGOization
- Production rendering or Studio automation
- Automatic semantic segmentation
- A complete animal, vehicle, or building vocabulary
- Voice input, purchasing, publishing, or physical-build claims
- Choosing Pi or another runtime harness

## Decisions to make after reviewing the interaction

1. Whether the first spatial representation should use cells, simple
   primitives, or grouped LEGO parts.
2. Whether selection begins as a bounding box, a brush/lasso, or numbered
   precomputed regions.
3. How much automatic expansion is tolerable before the system must ask the
   user to enlarge the selection.
4. Whether symmetry is an explicit invariant or a first-class linked edit.
5. Which single model family provides the cheapest meaningful implementation
   test after the interaction is accepted.
