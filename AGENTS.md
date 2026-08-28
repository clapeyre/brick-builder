# Brick Builder agent instructions

## Project context

- This is a personal, open-source project intended for publication on GitHub.
- The owner works at NVIDIA, but this project must remain completely separate from NVIDIA and all other employer resources.
- Never introduce confidential information, internal code, customer material, work credentials, proprietary prompts, or employer-specific workflows.
- Prefer dependencies and assets with clear licenses that are compatible with public redistribution. Record attribution and license obligations as dependencies are added.
- The primary beta tester is the owner's six-year-old child. Optimize for delight, clarity, short feedback loops, and adult-supervised use.
- Small LEGO elements are a physical safety concern. Do not represent the application as unsupervised play guidance, and do not automate purchasing or public sharing without an explicit adult action.

## Product direction

- The initial product designs LEGO models from existing catalog elements; it does not design new physical brick geometries.
- Start with a deliberately small palette: common rigid parts, ordinary stud-based connections, limited colors, modest part counts, and mostly orthogonal construction.
- Initial design families are vehicles, creatures, and small buildings.
- Defer Technic mechanisms, flexible parts, complex hinges, minifigures, custom parts, and unrestricted catalogs until the core is reliable.
- Treat the roadmap as ordered steps, not calendar commitments.

## Architecture principles

- Keep the canonical design outside the BrickLink Studio GUI.
- Use a compact, versioned, structured design representation and compile it deterministically to LDraw `.ldr` or `.mpd` files.
- Use BrickLink Studio primarily for import, inspection, rendering, stability/collision feedback, parts information, and instructions.
- Prefer one orchestrating Hermes agent with a small set of precise tools before introducing multiple specialist agents.
- Let the model propose designs; use deterministic code to validate known constraints.
- Add a final Studio/UI inspection layer for errors or quality problems that deterministic validators miss. GUI inspection complements rather than replaces deterministic validation.
- Preserve reproducible trajectories: request, structured specification, generated design, validator results, repair attempts, renders, and selected output.

## Quality bar

- Favor a small, reliable, test-driven system over broad but inconsistent capability.
- Every validator failure should be actionable and reproducible.
- Maintain hand-authored reference models and representative prompt-based evaluations.
- Test actual physical builds when practical; digital validity is not sufficient evidence of buildability or fun.
- Keep all external writes, purchasing, publishing, and account actions behind explicit adult approval.
