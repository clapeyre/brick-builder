import assert from "node:assert/strict";
import { mkdtemp, readFile, stat, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";
import { readLiveRunConfig, runLiveConceptToCandidate, type LiveRunContext } from "../src/live_run.js";

async function root() { return mkdtemp(join(tmpdir(), "brick-builder-live-run-")); }

test("preserves the raw request and exposes only Brick Builder tools to the runner", async () => {
  const runRoot = await root();
  let seen: LiveRunContext | undefined;
  const result = await runLiveConceptToCandidate({ runRoot, request: "  Build a tiny red tower!  ", provider: "adult-provider", model: "adult-model", runner: async (context) => { seen = context; return { status: "success", trajectory: [{ type: "tool", name: "brick_concept_candidate_set" }] }; } });
  assert.equal(result.status, "success");
  assert.equal(JSON.parse(await readFile(join(runRoot, "request.json"), "utf8")).request, "  Build a tiny red tower!  ");
  assert.equal(seen?.sessionOptions.noTools, "builtin");
  assert.deepEqual(seen?.domainTools.map((tool) => tool.name), ["brick_catalog", "brick_validate", "brick_analyze", "brick_compile", "brick_demo_generate", "brick_demo_candidate_set", "brick_select_candidate", "brick_submit_brief", "brick_request_candidates", "brick_spatial_concepts", "brick_concept_redesign", "brick_legoize_concept", "brick_legoize_stepped_concept", "brick_legoize_gatehouse_concept", "brick_concept_candidate_set", "brick_select_concept_candidate", "brick_selected_candidate_redesign"]);
  assert.equal(JSON.stringify(result).includes("credential"), false);
  await stat(join(runRoot, "trajectory.json"));
  await stat(join(runRoot, "live-run.json"));
});

test("records clarification and session-factory results without serializing provider configuration", async () => {
  const runRoot = await root();
  const result = await runLiveConceptToCandidate({ runRoot, request: "make something", provider: "private-provider", model: "private-model", sessionFactory: async (context) => async () => ({ status: "clarification", message: "What color should it be?", artifacts: { candidate_count: 0 }, trajectory: [{ type: "assistant", text: "What color should it be?" }] }) });
  assert.equal(result.status, "clarification");
  assert.equal(result.message, "What color should it be?");
  const artifact = JSON.parse(await readFile(join(runRoot, "live-run.json"), "utf8"));
  assert.equal(artifact.provider, "private-provider");
  assert.equal(artifact.model, "private-model");
  assert.equal("credentials" in artifact, false);
});

test("omits provider labels that could contain secret material", async () => {
  const runRoot = await root();
  await runLiveConceptToCandidate({ runRoot, request: "make a tower", provider: "Bearer secret-value", model: "model", runner: async () => ({ status: "success" }) });
  const artifact = JSON.parse(await readFile(join(runRoot, "live-run.json"), "utf8"));
  assert.equal("provider" in artifact, false);
  assert.equal(artifact.model, "model");
});

test("turns repeated deterministic failures into exhaustion and preserves provider failure diagnostics", async () => {
  const exhaustedRoot = await root();
  let calls = 0;
  const exhausted = await runLiveConceptToCandidate({ runRoot: exhaustedRoot, request: "make a tower", maxAttempts: 2, runner: async ({ attempt }) => { calls++; return { status: "failure", message: `invalid concepts ${attempt}`, feedback: [{ code: "INVALID_CONCEPT" }] }; } });
  assert.equal(calls, 2);
  assert.equal(exhausted.status, "exhaustion");
  assert.match(exhausted.message ?? "", /exhausted/);

  const providerRoot = await root();
  const provider = await runLiveConceptToCandidate({ runRoot: providerRoot, request: "make a tower", runner: async () => ({ status: "provider-failure", message: "provider unavailable" }) });
  assert.equal(provider.status, "provider-failure");
  assert.equal(provider.message, "provider unavailable");
});

test("loads an external provider config without accepting a credential value", async () => {
  const runRoot = await root();
  const configPath = join(runRoot, "provider.json");
  await writeFile(configPath, JSON.stringify({ provider: "adult-provider", model: "model", api: "openai-responses", baseUrl: "https://example.test/v1", apiKey: "must-not-be-used" }));
  const config = await readLiveRunConfig(configPath);
  assert.deepEqual(config, { provider: "adult-provider", model: "model", api: "openai-responses", baseUrl: "https://example.test/v1" });
});

test("retains optional external auth path and environment compatibility", async () => {
  const runRoot = await root();
  const configPath = join(runRoot, "provider.json");
  await writeFile(configPath, JSON.stringify({ provider: "provider", model: "model", api: "openai-responses", baseUrl: "https://example.test/v1", authPath: "C:\\Secrets\\auth.json", apiKeyEnv: "BRICK_BUILDER_API_KEY" }));
  assert.deepEqual(await readLiveRunConfig(configPath), { provider: "provider", model: "model", api: "openai-responses", baseUrl: "https://example.test/v1", authPath: "C:\\Secrets\\auth.json", apiKeyEnv: "BRICK_BUILDER_API_KEY" });
});

test("rejects an unsafe credential environment name and unsupported API", async () => {
  const runRoot = await root();
  const configPath = join(runRoot, "provider.json");
  await writeFile(configPath, JSON.stringify({ provider: "provider", model: "model", api: "unsupported", baseUrl: "https://example.test", apiKeyEnv: "BRICK-BUILDER-KEY" }));
  await assert.rejects(() => readLiveRunConfig(configPath), /unsupported live provider API/);
  await writeFile(configPath, JSON.stringify({ provider: "provider", model: "model", api: "openai-responses", baseUrl: "https://example.test", apiKeyEnv: "BRICK-BUILDER-KEY" }));
  await assert.rejects(() => readLiveRunConfig(configPath), /apiKeyEnv must be an environment variable name/);
});

test("does not overwrite an existing run directory", async () => {
  const runRoot = await root();
  await writeFile(join(runRoot, "existing.txt"), "keep");
  await assert.rejects(() => runLiveConceptToCandidate({ runRoot, request: "make a tower", runner: async () => ({ status: "success" }) }), /fresh or empty/);
  assert.equal(await readFile(join(runRoot, "existing.txt"), "utf8"), "keep");
});
