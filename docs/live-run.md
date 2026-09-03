# Adult-supervised live concept run

Delivery slice 1 provides a small, provider-neutral command for testing the
real concept-to-candidate path. It accepts ordinary request text, gives Pi
only Brick Builder domain tools, and writes evidence beneath a fresh run
directory. It does not select a candidate or expose shell/filesystem tools.

## Configure outside the repository

Create a provider configuration somewhere outside this repository. The file
contains no credential; `apiKeyEnv` names an environment variable that the
adult sets for the command's process.

```json
{
  "provider": "openai",
  "model": "YOUR_MODEL_ID",
  "api": "openai-responses",
  "baseUrl": "https://api.openai.com/v1",
  "apiKeyEnv": "BRICK_BUILDER_API_KEY"
}
```

Supported API values are `openai-completions`, `openai-responses`,
`anthropic-messages`, and `google-generative-ai`. Do not put an API key in this
repository, the configuration committed here, or a run artifact.

## Run

From `pi-adapter`, set the adult-controlled environment variable and use a new
caller-owned run directory for each attempt:

```powershell
$env:BRICK_BUILDER_API_KEY = "<adult-supplied-key>"
pnpm live --config "C:\path\outside\brick-builder\provider.json" --run-root "C:\path\to\runs\live-001" "Make a tiny red lookout tower"
```

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
