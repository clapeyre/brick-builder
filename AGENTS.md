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
- Prefer one narrowly bounded orchestrating agent with a small set of precise tools before introducing multiple specialist agents. Keep the deterministic core harness-agnostic; Pi is the leading product-facing harness direction, while the existing Hermes integration remains a reference until Pi reaches parity.
- Let the model propose designs; use deterministic code to validate known constraints.
- Add a final Studio/UI inspection layer for errors or quality problems that deterministic validators miss. GUI inspection complements rather than replaces deterministic validation.
- Preserve reproducible trajectories: request, structured specification, generated design, validator results, repair attempts, renders, and selected output.

## Quality bar

- Favor a small, reliable, test-driven system over broad but inconsistent capability.
- Every validator failure should be actionable and reproducible.
- Maintain hand-authored reference models and representative prompt-based evaluations.
- Test actual physical builds when practical; digital validity is not sufficient evidence of buildability or fun.
- Keep all external writes, purchasing, publishing, and account actions behind explicit adult approval.

## Development workflow

- Default to `gpt-5.6-terra` at medium reasoning for the root integrator and
  `gpt-5.6-luna` at medium reasoning for the required first implementation
  attempt. Explicit user or task-specific model and reasoning choices take
  precedence. If either default is unavailable, report the constraint rather
  than silently substituting another model or reasoning level.
- Before implementation begins, record the bounded slice, acceptance gates, and
  explicit non-goals in `docs/project-roadmap.md` or a document linked from it.
- For every implementation slice, the root agent must first delegate an
  implementation attempt to at least one `gpt-5.6-luna` subagent. Documentation-
  only planning changes do not require this step. If Luna subagents are
  unavailable, report that constraint instead of silently bypassing the trial.
- Treat the Luna result as an implementation attempt, not as accepted output.
  The root agent remains responsible for inspecting the repository, resolving
  conflicts, integrating or rewriting the work, running verification, and
  deciding whether the acceptance gates are satisfied.
- Give each subagent a bounded deliverable and avoid concurrent edits to the same
  files. Prefer one implementation task with a root integrator over several
  user-visible tasks writing to the repository independently.
- Commit coherent increments after their relevant checks pass. Push verified
  commits regularly to the already configured `origin` so progress is backed up
  and reviewable. Do not change the remote or repository visibility, push
  secrets or generated run artifacts, or push a knowingly failing increment
  unless the owner explicitly requests it.
- The root integrator owns commits, pushes, and all external Git/network
  operations. Subagents may inspect Git state and prepare a bounded handoff,
  but must not push, change remotes, alter SSH or credential settings, or switch
  transport as a workaround.
- In Codex tasks using **Ask for approval** or **Approve for me**, commands run
  sandboxed by default. Before an operation needing network or access beyond
  the workspace—such as dependency installation or repair, a Pi runner that
  needs pnpm's package store, or `git push`—the root integrator must request
  elevated access. It must not first run the same command in the sandbox,
  retry a blocked command, or treat the resulting access error as a project
  failure.
- **Approve for me** changes who reviews an elevation request; it does not give
  ordinary commands unrestricted network or filesystem access. The agent must
  still request elevation and wait for the result. Only the owner chooses
  **Full access** in the Codex UI. Do not ask the owner to reproduce routine
  project commands manually in PowerShell merely because an elevation request
  is needed or rejected; report the request and outcome instead.
- If a subagent cannot push because its execution environment blocks GitHub or
  SSH access, it must not retry or diagnose credentials. It should report the
  prepared files, verification performed, and (if one exists) the commit hash
  to the root integrator as a handoff; this is not a product verification
  failure.
