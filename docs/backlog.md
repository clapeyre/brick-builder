# Brick Builder backlog

This is for deferred maintenance and cleanup, not ordered product milestones.
Move an item into `docs/project-roadmap.md` when it becomes active delivery work.

## CLI surface cleanup

- [ ] Decide which interface is public: the agent-facing JSON contract, a
  human-facing shell, or both.
- [ ] Add a Click-based human facade with grouped commands for model, demo,
  concept, LEGOization, and evidence workflows.
- [ ] Preserve existing JSON artifacts, exit codes, and compatibility aliases
  while migrating callers and documentation.
- [ ] Reconcile duplicate Python, Pi-tool, and live-run operation names before
  removing any flat commands.
- [ ] Add deprecation/help coverage and document the final human versus
  agent-facing boundary.
