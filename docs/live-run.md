# Adult-supervised live concept run

Delivery slice 1 provides a small, provider-neutral command for testing the
real concept-to-candidate path. It accepts ordinary request text, gives Pi
only Brick Builder domain tools, and writes evidence beneath a fresh run
directory. It does not select a candidate or expose shell/filesystem tools.

## Configure outside the repository

Create a provider configuration somewhere outside this repository. The file
contains no credential. By default, the runner reads Pi credentials from the
current user's `$HOME/.pi/agent/auth.json` (on Windows,
`C:\Users\<user>\.pi\agent\auth.json`). An optional `apiKeyEnv` can be used
instead when environment-based authentication is preferred.

```json
{
  "provider": "openai",
  "model": "YOUR_MODEL_ID",
  "api": "openai-responses",
  "baseUrl": "https://api.openai.com/v1"
}
```

Supported API values are `openai-completions`, `openai-responses`,
`anthropic-messages`, and `google-generative-ai`. Do not put an API key in this
repository, the configuration committed here, or a run artifact.

## Run

From `pi-adapter`, use a new caller-owned run directory for each attempt. With
credentials in the default Pi `auth.json`, no environment-variable command is
needed:

```powershell
pnpm live --config "C:\path\outside\brick-builder\provider.json" --run-root "C:\path\to\runs\live-001" "Make a tiny red lookout tower"
```

The runner reads both the global `auth.json` and `settings.json`, while still
explicitly allowlisting only the Brick Builder domain tools for this session.
Global settings therefore control Pi behavior such as model preferences, but
cannot enable shell, filesystem, or unrelated extension tools here. To use a
non-default auth file, add `"authPath": "C:\\path\\outside\\auth.json"` to the
provider config.

If Python is not on PATH, pass the approved project Python explicitly with
`--python`. The command returns status `success` when two or three concepts
compose into valid candidates, `clarification` for one concise question, and a
nonzero exit code for provider failure or bounded exhaustion.

The run contains `request.json`, `trajectory.json`, `live-run.json`,
`candidate-set.json`, `selection-ready.json`, candidate render evidence, and
per-candidate `.ldr` files on success. `selection-ready.json` is an index only;
candidate choice remains a separate explicit operation. Engineering validation
is recorded separately from resemblance, and the output still requires adult
inspection in BrickLink Studio.

The live provider smoke is manual and adult-supervised. The automated contract
remains the offline scripted Pi test suite; no credentials or network access are
needed to run those tests.
