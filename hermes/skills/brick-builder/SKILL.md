---
name: brick-builder
description: Design small LEGO models with deterministic checks.
version: 0.1.0
author: Corentin Lapeyre, Hermes Agent
license: MIT
platforms: [windows, linux, macos]
metadata:
  hermes:
    tags: [lego, ldraw, modeling]
    related_skills: []
---

# Brick Builder

Use this skill for requests to design a small model from the packaged Brick
Builder palette. Do not use it for purchasing, publishing, unsupervised child
play, Studio GUI automation, slopes, wheels, hinges, or unrestricted catalogs.

## Prerequisites

Start Hermes from the Brick Builder repository root. Ensure the `brick-builder`
command is installed in the active environment. The adult should review the
request and output before any physical build.

## When to Use

Use this skill for a small vehicle, creature, or building made from the
packaged rigid-part palette, with ordinary stud connections, orthogonal
construction, and a modest part count. Countertriggers: do not use it for
purchasing, publishing, sharing, unsupervised child play, Studio GUI
automation, slopes, wheels, hinges, flexible or Technic parts, custom parts,
or an unrestricted catalog.

## How to Run / Quick Reference

Hermes writes `request.txt`, `spec.json`, `candidate-N.json`,
`validation-N.json`, `analysis-N.json`, `repair-feedback-N.json`,
`catalog.json`, `compile.json`, and `manifest.json` using `write_file` in a
unique `runs/<run-id>/` directory. Hermes itself writes the structured spec,
candidates, and command records; the
deterministic CLI only validates, analyzes, and compiles them.

Use exact commands:

```text
terminal(command="brick-builder catalog")
terminal(command="brick-builder validate runs/<run-id>/candidate-1.json")
terminal(command="brick-builder analyze runs/<run-id>/candidate-1.json")
terminal(command="brick-builder compile runs/<run-id>/candidate-1.json runs/<run-id>/final.ldr")
terminal(command="brick-builder manifest runs/<run-id> --outcome success --attempts 1 --max-attempts 3")
terminal(command="brick-builder manifest runs/<run-id> --outcome exhausted --attempts 3 --max-attempts 3")
```

The offline fixture is only a smoke test, not Hermes orchestration:

```text
terminal(command="brick-builder demo-generate \"Make a tiny red wall\" --run-dir runs/demo")
```

## Procedure

1. Write `request.txt` and `spec.json`, recording family, palette, part limit,
   orthogonal constraint, and unique run directory.
2. Run `catalog`, record its complete JSON as `catalog.json`, then write
   exactly one candidate as `candidate-1.json` with `write_file`.
3. Run `validate` and `analyze`, recording complete results as
   `validation-1.json` and `analysis-1.json`; proceed only on exit code 0.
4. On failure, write structured issues and `repair_hint` values to
   `repair-feedback-N.json`, correct once, and repeat for at most three total
   candidates.
5. Compile the first valid candidate; preserve `final.ldr` and the complete
   result as `compile.json` with `write_file`.
6. Finalize `manifest.json` with request/palette hashes, attempt count,
   outcome, and artifact hashes using the `manifest` command above (use
   `--outcome exhausted` after the bound). Report success only when validation
   and compilation both return exit code 0.

## Pitfalls

Do not invent geometry or colours, confuse LDraw Y-down coordinates, ignore
grid alignment, or treat digital validity as proof of stability. Preserve all
failed candidates and diagnostics. This skill is repo documentation, not
Python package data, and is installed separately.

## Verification

Only report success when validation and compilation return exit code 0. Studio
import is an adult-supervised visual check; digital validity does not prove
physical stability or child safety. Never purchase, publish, or share without
an explicit adult action.

Install locally by copying `hermes/skills/brick-builder/` to
`~/.hermes/skills/brick-builder/`, then run `/reload-skills`. A future raw
GitHub installation may use `hermes skills install <raw-GitHub-SKILL.md-URL>`
once a public URL exists; no remote repository URL is assumed here.
