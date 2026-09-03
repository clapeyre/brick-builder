import assert from "node:assert/strict";
import { mkdtemp, readFile, readdir, stat, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";
import { LIVE_SYSTEM_PROMPT, readLiveRunConfig, runLiveConceptToCandidate, type LiveRunContext } from "../src/live_run.js";
import { BrickBuilderAdapter, createBrickBuilderTools } from "../src/index.js";

async function root() { return mkdtemp(join(tmpdir(), "brick-builder-live-run-")); }

test("live candidate contract documents the JSON shape consumed by the Python concept parser", () => {
  const tool = createBrickBuilderTools(new BrickBuilderAdapter({ runRoot: "C:/runs/test" })).find((item) => item.name === "brick_concept_candidate_set")!;
  assert.match(tool.description, /id, label, geometry, render/);
  assert.match(tool.description, /center:\[x,y,z\]/);
  assert.match(tool.description, /geometry_refs/);
});

test("live prompt uses neutral layout guidance without internal family vocabulary", () => {
  assert.doesNotMatch(LIVE_SYSTEM_PROMPT.toLowerCase(), /gatehouse|stepped-box|one-box|legoize|bridge/);
  assert.match(LIVE_SYSTEM_PROMPT, /integer centers and integer positive sizes/);
  assert.match(LIVE_SYSTEM_PROMPT, /touching faces align exactly on the grid/);
});

test("preserves the raw request and exposes only Brick Builder tools to the runner", async () => {
  const runRoot = await root();
  let seen: LiveRunContext | undefined;
  const result = await runLiveConceptToCandidate({ runRoot, request: "  Build a tiny red tower!  ", provider: "adult-provider", model: "adult-model", runner: async (context) => { seen = context; return { status: "success", trajectory: [{ type: "tool", name: "brick_concept_candidate_set" }] }; } });
  assert.equal(result.status, "success");
  assert.equal(JSON.parse(await readFile(join(runRoot, "request.json"), "utf8")).request, "  Build a tiny red tower!  ");
  assert.equal(seen?.sessionOptions.noTools, "builtin");
  assert.deepEqual(seen?.domainTools.map((tool) => tool.name), ["brick_concept_candidate_set"]);
  assert.deepEqual((seen?.sessionOptions.customTools as any[]).map((tool) => tool.name), ["brick_concept_candidate_set"]);
  assert.doesNotMatch((seen?.domainTools[0].description ?? "").toLowerCase(), /gatehouse|stepped|one-box|bridge/);
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

test("isolates each bounded attempt under its own auditable artifact root", async () => {
  const runRoot = await root();
  const attemptRoots: string[] = [];
  const result = await runLiveConceptToCandidate({
    runRoot, request: "make a bridge", maxAttempts: 2,
    runner: async ({ attemptRoot }) => {
      attemptRoots.push(attemptRoot);
      await writeFile(join(attemptRoot, "proposal-marker.json"), JSON.stringify({ attemptRoot }));
      return { status: "failure", feedback: [{ code: "INVALID_CONCEPT" }] };
    },
  });
  assert.equal(result.status, "exhaustion");
  assert.equal(new Set(attemptRoots).size, 2);
  assert.deepEqual(await readdir(join(runRoot, "attempts")), ["attempt-01", "attempt-02"]);
  await stat(join(runRoot, "attempts", "attempt-01", "proposal-marker.json"));
  await stat(join(runRoot, "attempts", "attempt-02", "proposal-marker.json"));
  assert.equal((await readdir(runRoot)).includes("candidates"), false);
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
