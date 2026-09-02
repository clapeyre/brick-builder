# Worktree setup and verification status

Git worktrees contain the tracked repository files, but they deliberately do
not include ignored, machine-local dependencies. Treat every new worktree as a
fresh development environment until its setup commands have completed.

## Bootstrap a new worktree

Run these commands from the worktree root in Windows PowerShell.

```powershell
# Python deterministic core
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .

# Pi adapter
pnpm --dir pi-adapter install --frozen-lockfile
```

The Python editable install supplies the declared `jsonschema` dependency. The
Pi command uses `pi-adapter/pnpm-lock.yaml`, including the pinned transitive Pi
packages. Do not commit `.venv`, `.demo-venv`, `node_modules`, `dist`, or a
pnpm package store.

For the offline fixture demo, follow [demo-setup.md](demo-setup.md) instead:
it intentionally uses a separate `.demo-venv` and the exact interpreter that
launches the demo.

## Classify verification results accurately

Use one of these statuses in agent summaries:

| Situation | Status to report | Next action |
| --- | --- | --- |
| The worktree has not been bootstrapped, and Python cannot import `jsonschema` or Node cannot resolve a declared package. | **Setup prerequisite** | State the missing setup command; do not call this a product verification failure. |
| Dependencies are installed, but a test or validator fails. | **Verification failure** | Report the failing command and relevant error. |
| Dependencies are installed, but the restricted execution sandbox prevents a package loader, hard link, or other runtime operation. | **Execution-environment limitation** | Report the command, the sandbox limitation, and whether the same command needs an approved unrestricted run. |

`@earendil-works/pi-telemetry` is transitive to the pinned Pi runtime. A
missing-module error first calls for a clean frozen-lockfile install in the
current worktree; it does not by itself justify changing Pi versions or adding
that package directly to `package.json`.

## Standard agent wording

Before claiming that full verification is pending, state which category applies.
For example:

> Full Pi verification is a setup prerequisite in this fresh worktree:
> `pi-adapter/node_modules` has not been installed. Run
> `pnpm --dir pi-adapter install --frozen-lockfile`, then rerun `<command>`.

Or, when setup has completed:

> Full Pi verification is blocked by the restricted execution environment:
> `<command>` cannot load the installed package-store link there. This is not a
> source-test failure; rerun the same command outside the restriction to verify.
